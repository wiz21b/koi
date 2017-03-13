"""
I need a decorator to instrument the call to the function. This is only really needed
on the client side because that's where :
- I'll need to inject HTTP connection
- I'll want to be able to test the code with or without the HTTP connection


A full call...

client :
   params -> json  (atomic types, objects with model -> dict)
server :
   json -> params (dicts -> atomic types,  sqla_objects with persistence)
   call function with params
   return -> json (atomic types, objects with model -> dict)
client :
   json -> return-client-side (dict -> atomic types, objects with model)

"""
import json
import itertools
import base64
from enum import Enum
from inspect import Signature, signature, ismethod, isfunction
from json import loads, dumps
from datetime import datetime, date
from decimal import Decimal
from http.client import HTTPConnection
from urllib.parse import urlparse

import sqlalchemy
from sqlalchemy.inspection import inspect
from sqlalchemy.orm.properties import ColumnProperty
import sqlalchemy.sql.sqltypes as sqltypes

from koi.python3 import EnumSymbol
from koi.base_logging import mainlog
from koi.utils import SourceFunctionDecorator
from koi.datalayer.DeclEnumP3 import DeclEnumType

# init_test_database()



# class NullConverter:
#     @classmethod
#     def to_jsonable(self,x):
#         return x
#     @classmethod
#     def from_jsonable(self,jsonable):
#         return jsonable
#
#
# class DateConverter:
#     @classmethod
#     def to_jsonable(self,x):
#         return datetime.strftime( x, "%Y-%m-%d" )
#     @classmethod
#     def from_jsonable(self,jsonable):
#         return datetime.strptime( jsonable, "%Y-%m-%d" )
#
# class DateTimeConverter:
#     @classmethod
#     def to_jsonable(self,x):
#         return datetime.strftime( x, "%Y-%m-%dT%H:%M:%S.%f" )
#     @classmethod
#     def from_jsonable(self,jsonable):
#         return datetime.strptime( jsonable, "%Y-%m-%dT%H:%M:%S.%f" )
#
# class GuessConverter:
#     @classmethod
#     def to_jsonable(self,obj):
#         if type(obj) in (str, int, float):
#             return obj
#         elif isinstance(obj, datetime):
#             return { '__datetime__' : datetime.strftime( obj, "%Y-%m-%dT%H:%M:%S.%f" ) }
#         elif isinstance(obj, date):
#             return { '__date__' : obj.isoformat() }
#         elif isinstance(obj,bytes): # Python 3
#             return { '__bytes__' : base64.b64encode(obj).decode('ascii')}
#         elif isinstance(obj,EnumSymbol):
#             # As of Python 3.4 enums are still not supported by json module dumps/loads
#             return { '__enum__' : (obj.value, obj.cls.__name__) }
#         elif isinstance(obj, object):
#             mainlog.debug("Default encoding for {}".format(obj))
#             mainlog.debug(obj.__dict__)
#
#             # JSON encodes objects to JSON dicts. But then it decodes
#             # them as dict.
#             # Therefore, if I want to decode an object and not a dict, I have
#             # to make that explicit, hence the '__object__' key.
#             return { '__object__' : obj.__dict__ }
#         else:
#             mainlog.error("Python's json can't encode {} of type {}".format(obj, type(obj)))
#             raise Exception("Python's json can't encode {} of type {}".format(obj, type(obj)))
#
#     @classmethod
#     def from_jsonable(self,d):
#         if "__object__" in d:
#             return DictAsObj( d['__object__'])
#
#         elif "__date__" in d:
#             # mainlog.debug("json_object_hook : parsing a date : {}".format([int(x) for x in d['__date__'].split('-')]))
#             return date( *([int(x) for x in d['__date__'].split('-')]) )
#
#         elif "__datetime__" in d:
#             return datetime.strptime( d['__datetime__'], "%Y-%m-%dT%H:%M:%S.%f" )
#             #return dateutil.parser.parse(d['__date__'])
#
#         elif "__enum__" in d:
#             v,cls = d['__enum__']
#
#             try:
#                 # Remember for globals : "This is always the dictionary of the current module".
#                 # So one has to meke sure the global definitions are known here...
#                 # FIXME and that is a manual process...
#
#                 obj = globals()[cls]
#                 return obj.from_str(v)
#             except Exception as ex:
#                 mainlog.error("Globals {}".format(sorted(globals().keys())))
#                 mainlog.exception(ex)
#                 raise Exception("Can't un-json the enumeration with value '{}' of class '{}' ({})".format(v,cls, type(cls)))
#
#         elif "__bytes__" in d:
#             return base64.b64decode(d["__bytes__"])
#         else:
#             return d
#
#
# SQLA_TYPES_CONVERTERS = {sqltypes.Integer : NullConverter,
#                          sqltypes.Float : NullConverter,
#                          sqltypes.String : NullConverter,
#                          sqltypes.Boolean : NullConverter,
#                          sqltypes.Date : DateConverter,
#                          DeclEnumType : GuessConverter,
#                          sqltypes.NullType : GuessConverter}




class SQLAMetaData:
    def __init__(self, session, sqla_declarative_base):
        """

        :param session: A function that returns the SQL Alchemy's current session
        :param sqla_declarative_base:
        :return:
        """
        self.session = session
        self._field_names_cache = dict()
        self._field_types_cache = dict()

        # Preload the cache
        self._mapped_classes = dict()

        for klass in self._find_subclasses(sqla_declarative_base):
            # self.attributes_names(klass)
            self._mapped_classes[klass.__name__] = klass

    def is_class_mapped(self, klass):
        return klass in self._mapped_classes.values()

    def _find_subclasses(self, cls):
        results = []
        for sc in cls.__subclasses__():
            results.append(sc)
        return results


    def attributes_names(self, model):
        """
        :param model:
        :return: names of the fields (ColumnProperties)
                 names of the array/set base relationships
                 names of uselist=false relationshipe
                 names of the key fields
        """
        # We use a cache for an obvious performance improvement

        if model not in self._field_names_cache:
            self._field_names_cache[model] = self._attribute_analysis(model)

        return self._field_names_cache[model]



    def fields_python_types(self, model):
        if model not in self._field_types_cache:
            types = dict()
            for prop in inspect(model).iterate_properties:
                if isinstance(prop, ColumnProperty):
                    types[prop.key] = type(prop.columns[0].type)
            self._field_types_cache[model] = types

        return self._field_types_cache[model]


    def _attribute_analysis(self, model):

        mainlog.debug("Analysing model {}".format(model))
        # Warning ! Some column properties are read only !
        fnames = [prop.key for prop in inspect(model).iterate_properties
                  if isinstance(prop, ColumnProperty)]

        single_rnames = []
        rnames = []
        for key, relation in inspect(model).relationships.items():
            if relation.uselist == False:
                single_rnames.append(key)
            else:
                rnames.append(key)

        # Order is important to rebuild composite keys (I think, not tested so far.
        # See SQLA comment for query.get operation :
        # http://docs.sqlalchemy.org/en/rel_1_0/orm/query.html#sqlalchemy.orm.query.Query.get )
        knames = [key.name for key in inspect(model).primary_key]

        mainlog.debug("For model {}, I have these attributes : primary keys={}, fields={}, realtionships={} (single: {})".format(model, knames, fnames, rnames, single_rnames))

        return (fnames, rnames, single_rnames, knames)



def jsonable_to_json(data):
    # return dumps(data, indent=True, default=default_encoder)
    # return dumps(data, default=default_encoder).encode('utf-8')
    return dumps(data).encode('utf-8')

def json_to_jsonable(json_data):
    # return loads(json_data, object_hook=json_object_hook)
    # return loads(json_data.decode('utf-8'), object_hook=json_object_hook)
    return loads(json_data.decode('utf-8'))



def _has_primary_key_set(knames, d):
    """ Checks if the PK fields are present in a dict
    :param knames:
    :param d:
    :return:
    """

    mainlog.debug("_has_primary_key_set : key fields are {}".format(knames))
    mainlog.debug("_has_primary_key_set : attributes values are {}".format(d))

    for key in knames:
        if key in d and d[key]:
            return True
            break
    return False


def dict_to_sqla(metadata : SQLAMetaData, model, d, recursive_set, with_persistence=True):
    fnames, rnames, single_rnames, knames = metadata.attributes_names(model)

    if with_persistence:
        has_set_pk = _has_primary_key_set(knames, d)

        if has_set_pk:
            key = tuple( [d[key] for key in knames])
            obj = metadata.session().query(model).get(key)
            mainlog.debug("dict_to_sqla : read PK {}".format(key))
        else:
            mainlog.debug("dict_to_sqla : no PK set for {} => new SQLA object".format(model))
            obj = model()
            metadata.session().add(obj)
    else:
        mainlog.debug("dict_to_sqla : non-sqla object")
        obj = model()


    fields_python_types = metadata.fields_python_types(model)
    for fname, type_ in fields_python_types.items():
        setattr( obj, fname,
                 jsonable_to_typed_values(metadata, type_, d[fname], recursive_set, with_persistence))

    # for name in fnames:
    #     # mainlog.debug("unserialize_full: copying field {}".format(name))
    #     setattr(obj, name, d[name])

    for name in rnames:
        if name in d:
            relation = getattr(obj, name)
            relation_target_class = getattr(model, name).property.mapper.class_
            touched_objects = set()

            for dict_item in d[name]:
                # Down the rabbit hole
                sqla_obj = dict_to_sqla(metadata, relation_target_class, dict_item, recursive_set, with_persistence)

                if sqla_obj in relation:
                    touched_objects.add(sqla_obj)
                elif sqla_obj not in relation:
                    # Will SQLA load the (maybe lazy) relationship to evaluat "in" ?
                    relation.append( sqla_obj)

            # Semantic is : if an object is not referred to in the dict, then
            # we interpret that this object was deleted.
            for sqla_obj in relation:
                if sqla_obj not in touched_objects:
                    relation.remove(sqla_obj)


    for name in single_rnames:
        if name in d:
            relation_target_class = getattr(model, name).property.mapper.class_

            dict_item = d[name]
            # Down the rabbit hole
            sqla_obj = dict_to_sqla(metadata, relation_target_class, dict_item, recursive_set, with_persistence)
            setattr(obj, name, sqla_obj)

    return obj



def sqla_to_dict(metadata : SQLAMetaData, model, obj, recursive=set()):

    mainlog.debug("sqla_to_dict: model={}, obj={}, recursive_set={}".format(model, obj, recursive))

    assert model
    assert obj

    fnames, rnames, single_rnames, knames = metadata.attributes_names(model)

    #fields = list(zip( fnames, [getattr(obj,fname) for fname in fnames]))
    # def typed_values_to_jsonable(metadata : SQLAMetaData, type_, recursive_set, value):


    fields_python_types = metadata.fields_python_types(model)

    fields = []
    for fname, type_ in fields_python_types.items():
        # FIXME recursive value usage seems borken
        fields.append( (fname,
                        typed_values_to_jsonable(metadata, type_, recursive, getattr( obj, fname))))

    relations = []
    if recursive:
        serialized_relations = []

        # Regular relationships are serialized as arrays because we want
        # to preserve order. Note that the relationship in the object can
        # be a set, a list, etc.

        for relation_name in rnames:
            relation_definition = getattr(model, relation_name)
            if relation_definition in recursive:
                relation_child_model = relation_definition.property.mapper.class_
                shortened_recursion = recursive - {relation_definition}

                relation_items = getattr(obj, relation_name)
                serialized_items = [sqla_to_dict(metadata, relation_child_model, item, shortened_recursion)
                                    for item in relation_items]
                relations.append( (relation_name, serialized_items) )

        serialized_relations = []
        for relation_name in single_rnames:
            relation_definition = getattr(model, relation_name)
            if getattr(model, relation_name) in recursive:
                relation_child_model = relation_definition.property.mapper.class_
                shortened_recursion = recursive - {relation_definition}

                relation_item = getattr(obj, relation_name)
                mainlog.debug("sqla_to_dict : following single relation {}, item is {}".format(relation_name, relation_item))
                serialized_item = sqla_to_dict(metadata, relation_child_model, relation_item, shortened_recursion)
                relations.append( (relation_name, serialized_item) )


    # mainlog.debug(relations)
    d = dict( fields + relations )

    return d


class Sequence:
    def __init__(self, target):
        self.target = target

class Tuple:
    def __init__(self, *targets):
        self.targets = targets

    def __repr__(self):
        return "tuplee"





def unkeyed_tuples(d):
    class KeyedTuple(object):
        # I need a class to have self.__dict__ (object() hasn't got it)
        def __repr__(self):
            # For debugging purposes
            z = u"KeyedTuple: "
            for k,v in self.__dict__.items():
                z += u"{}='{}' ".format(k,v)
            return z

    # FIXME not really a keyed tuple (it lacks '[]' operator)
    obj = KeyedTuple()
    obj.__dict__.update(d)
    return obj



class KeyedTuplesSequence:
    def __init__(self, types, labels):
        """

        :param types: A sequence of pairs. Each pair is (key, type).
        :return:
        """
        self._types = types
        self._keys = labels

    def keys(self):
        return self._keys

    def __len__(self):
        return len(self._types)


def keyed_tuple_sequence_to_jsonable( metadata : SQLAMetaData, recursive_set, kts: KeyedTuplesSequence, kt_sequence):

    sequence_jsonable = []
    for kt in kt_sequence:

        jsonable = []
        for i in range(len(kts)):
            jsonable.append( typed_values_to_jsonable(metadata, kts._types[i], recursive_set, kt[i]))

        sequence_jsonable.append( jsonable)

    return sequence_jsonable


from sqlalchemy.util import KeyedTuple

def jsonable_to_keyed_tuple_sequence( metadata : SQLAMetaData, recursive_set, kts: KeyedTuplesSequence, kt_sequence):

    keyed_tuples = []
    for kt in kt_sequence:

        typed = []
        for i in range(len(kts)):
            typed.append( jsonable_to_typed_values(metadata, kts._types[i], kt[i], recursive_set))

        keyed_tuples.append( KeyedTuple(typed, kts.keys()))

    return keyed_tuples


# def find_keyed_tuples_sequence_types(sequence):
#     if not sequence:
#         return sequence
#
#     # We're going to guess the type of each 'column' of the keyed tuples.
#     kt_types = dict()
#
#     for k in sequence[0]._asdict().keys():
#         kt_types[k] = None
#
#     types_to_find = len(kt_types)
#
#     for kt in sequence:
#         ckt = kt._asdict()
#
#         # We want to find the types of all columns. Problem is that if a value
#         # is None at the top of a column, then we cannot guess its type. So we
#         # have to move to the next row until we find a not None value
#
#         for k,v in ckt.items():
#             if (not kt_types[k]) and v is not None:
#                 kt_types[k] = type(v)
#
#                 types_to_find -= 1
#
#         # Early out optimization
#         if types_to_find == 0:
#             break
#
#     converted_kts = []



def jsonable_to_typed_values(metadata : SQLAMetaData,type_, value, recursive_set, with_persistence=False):
    if type_ == sqlalchemy.util._collections.KeyedTuple:
        r = unkeyed_tuples(value)
        return r
    elif type_ == KeyedTuplesSequence:
        return jsonable_to_keyed_tuple_sequence(metada, recursive_set, type_, value)
    elif isinstance(type_, Sequence):
        return [jsonable_to_typed_values(metadata, type_.target, v, recursive_set, with_persistence) for v in value]
    elif isinstance(type_, Tuple):
        return [jsonable_to_typed_values(metadata, type_.targets[i], value[i], recursive_set, with_persistence) for i in range(len(type_.targets))]
    elif metadata.is_class_mapped(type_):
        return dict_to_sqla(metadata, type_, value, recursive_set, with_persistence)
    elif value is None:
        return None
    elif type_ in (int, float, str, bool, sqltypes.Integer, sqltypes.Float, sqltypes.String, sqltypes.Boolean):
        return value
    elif type_ == Decimal:
        return str(value)
    elif isinstance(type_, Enum):
        return value
    elif type_ == date:
        return datetime.strptime(value, "%Y-%m-%d").date()
    elif type_ == datetime:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f" )
    elif hasattr( type_, 'from_jsonable'):
        return type_.from_jsonable( value)
    elif type_ == bytes: # Python 3
        return base64.b64decode(value)
    else:
        raise Exception("Unsupported type definition {}".format(type_))



def typed_values_to_jsonable(metadata : SQLAMetaData, type_, recursive_set, value):
    mainlog.debug("typed_values_to_jsonable : {}, value is {}".format(type_, value))

    # Check fundamental types first to optimize conversion speed

    if value is None:
        return None
    elif type_ in (int, float, str, bool, sqltypes.Integer, sqltypes.Float, sqltypes.String, sqltypes.Boolean):
        return value
    elif type_ == Decimal:
        return Decimal(value)
    elif type_ in (date, sqltypes.Date):
        return value.strftime( "%Y-%m-%d")
    elif type_ == datetime:
        return value.strftime( "%Y-%m-%dT%H:%M:%S.%f" )
    elif isinstance(type_, Enum):
        return value
    elif type_ == KeyedTuplesSequence:
        return keyed_tuple_sequence_to_jsonable(metada, recursive_set, type_, value)
    elif type_ == sqlalchemy.util._collections.KeyedTuple:
        # We assume each keyed tuple only contains only jsonable values.
        # FIXME That's rather bold !

        r = value._asdict()
        # mainlog.debug(r)
        return r
    elif type_ == bytes: # Python 3
        return base64.b64encode(value).decode('ascii')
    elif isinstance(type_, Sequence):
        # In particular, this works for Sequence[KeyedTuples]
        return [typed_values_to_jsonable(metadata, type_.target, recursive_set, v) for v in value]
    elif isinstance(type_, Tuple):
        mainlog.debug("typed_values_to_jsonable : Tuple")
        assert len(type_.targets) == len(value), "Value (of type tuple) length doesn't match prototype's length"
        return [typed_values_to_jsonable(metadata, type_.targets[i], recursive_set, value[i]) for i in range(len(type_.targets))]
    elif metadata.is_class_mapped(type_):
        return sqla_to_dict(metadata, type_, value, recursive_set)
    elif hasattr( type_, 'to_jsonable'):
        return type_.to_jsonable( value)
    elif isinstance( value, object):
        raise Exception("Unable to transform object to jsonable : {} - {} (was it mapped ? {})".format(type_, value, metadata.is_class_mapped(type_)))
        # return value.__dict__
    else:
        mainlog.warn("Unable to serialize type {}".format(type_))
        return value




class CallMode(Enum):
    transparent = 1
    http = 2
    in_process = 3


def JsonCallable(result_encoder=None, in_recursion={}, out_recursion={}, mode=CallMode.transparent):
    """
    I need this decorator because that's a clean way to intercept calls to a
    given function/method.

    :param result_encoder:
    :param in_recursion:
    :param out_recursion:
    :param mode:
    :return:
    """

    class JsonCallableDecorator(SourceFunctionDecorator):
        """
        Big limitation : when decorating a method, don't forget
        that, at the moment you decorate the method (class definition),
        the method is *not* bound to any object (nor class).
        As far as I can see, there's no way to find the instance
        of a method before calling it (it doesnt' know its true 'self').
        """
        # def __getattr__(self, name):
        #     # This will be called if the attribute named name is not found here
        #     # (so self._decorated_func is not concerned)
        #     # Notice I get the attr from the decorated func instead of original func.
        #     # This way I hope (not tested) that this will be applied recursiveley
        #     # along the chain of decorators until an attribute with the given name
        #     # is found.
        #
        #     mainlog.debug("__getattr__")
        #     return getattr(self._original_func, name)
        #

        def __init__(self, func):
            mainlog.debug("Init JsonCallableDecorator {}".format(func))
            # self._original_func = func
            super(JsonCallableDecorator,self).__init__(func)

            self._json_callable = True # To detect this decorator

            self._call_mode = mode
            self._json_param_result_encoder = result_encoder
            self.in_recursive_set = in_recursion
            self.out_recursive_set = out_recursion
            self._call_handler = None # type: JsonCaller
            self._service_name = None

        def get_service_name(self):
            if not self._service_name:
                if self.is_method():
                    self._service_name = "{}.{}".format( type(self._instance).__name__, self._original_func.__name__)
                else:
                    self._service_name = "service.{}".format( self._original_func.__name__)
            mainlog.debug("get_service_name() = {}".format(self._service_name))
            return self._service_name

        def set_mode(self, mode : CallMode):
            assert mode
            self._call_mode = mode

        def set_call_handler(self, handler):
            global JsonCaller

            # mainlog.debug(isinstance(handler, JsonCaller))
            # mainlog.debug(isinstance(self._call_handler, JsonCaller))
            # mainlog.debug(id(JsonCaller))
            # mainlog.debug(id(JsonCaller))
            # assert isinstance(handler, JsonCaller), "{} of type {} is not a {}".format(handler, handler.__class__, JsonCaller)
            self._call_handler = handler

        def __call__(self, *args, **kwargs):
            if self._call_mode == CallMode.transparent:
                mainlog.debug("JsoncCallableDecorator : transparent call transfer")
                mainlog.debug("args = {}".format(args))
                return self.call_decorated(*args, **kwargs)

            elif self._call_mode == CallMode.http:
                assert self._call_handler, "Call handler not set for http mode"
                mainlog.debug("JsoncCallableDecorator : making http call")
                rpc_request = self._call_handler.build_client_side_rpc_request( self, *args)
                jsonable_res = self._call_handler.call_json_rpc_over_http( rpc_request)
                mainlog.debug("JsoncCallableDecorator : making http call, result is {}".format(jsonable_res))
                func_sig = signature(self._decorated_func)
                return self._call_handler.jsonable_to_return_values(func_sig, self.out_recursive_set, jsonable_res['result'])

                # return self._call_handler.jsonable_to_return_values( jsonable_res)

            elif self._call_mode == CallMode.in_process:
                assert self._call_handler, "Call handler not set for in process mode"
                mainlog.debug("JsoncCallableDecorator : making in process call, params are {}".format(args))
                return self._call_handler.in_process_call(self, *args, **kwargs)

            else:
                mainlog.error("Unsupported call mode {}, {}".format(self._call_mode, self._call_mode == CallMode.in_process))

    return JsonCallableDecorator






class JsonCaller:
    __module__ = 'koi.junkyard.dto_maker'

    def __init__(self, session_func, sqla_declarative_base, server_url):
        self._metadata = SQLAMetaData(session_func, sqla_declarative_base)
        self._server_url = server_url

    def params_to_jsonable(self, signature : Signature, in_recursive_set, values):
        """

        This is meant to be called on the delivery_slips side (when the delivery_slips invokes
        a method on a service)

        JSON-RPC : we use the call by-name convention, so we produce a dict.

        :param parameters: An ordered mapping of parameters’ names to the corresponding Parameter objects. (see Python annotation doc)
        :param values:
        :return:
        """

        mainlog.debug("params_to_jsonable: values are {}".format(values))
        parameters = signature.parameters


        param_keys = iter(parameters.keys())
        param_values = iter(parameters.values())

        first_param_key = next(iter(parameters.keys()), None) # We use default to handle empty parameters list
        if first_param_key == 'self':
            next(param_keys)
            next(param_values)

        mainlog.debug("params_to_jsonable: signature is {}".format(parameters))
        d = dict()

        for name, type_, value in zip( param_keys, param_values, values):
            if name != 'self':
                mainlog.debug("{} ({}) = {}".format(name, type_, value))
                d[name] = typed_values_to_jsonable(self._metadata, type_.annotation, in_recursive_set, value)
            else:
                mainlog.debug("Self skipped")
        return d


    def jsonable_to_params(self, signature : Signature, in_recursive_set, values):
        """

        Once the delivery_slips has issued its call. We receive the parameters as json,
        we unjson them. Then we process them here to bring them back to an
        array of stuff that can be passed to the actual service method.

        Remember we use the JSON RPC call by name convention.

        :param parameters:
        :param values:
        :return:
        """
        parameters = signature.parameters

        d = dict()
        for name, type_ in zip( parameters.keys(), parameters.values()):
            if name != 'self':
                d[name] = jsonable_to_typed_values(self._metadata, type_.annotation, values[name], in_recursive_set, with_persistence=True)
        return d


    def return_values_to_jsonable(self, signature : Signature, out_recursive_set, values):
        mainlog.debug("return_values_to_jsonable")
        return typed_values_to_jsonable(self._metadata, signature.return_annotation, out_recursive_set, values)


    def jsonable_to_return_values(self, signature : Signature, out_recursive_set, values):
        return jsonable_to_typed_values(self._metadata, signature.return_annotation, values, out_recursive_set, with_persistence=False)

    def client_side_call(self, func, *func_params):
        assert hasattr(func, '_json_callable'), "Function is not decorated as a JSON callable function"
        func_sig = signature(func._original_func)
        intermediate = jsonable_to_json(json_caller.params_to_jsonable( func_sig, func.in_recursive_set, func_params))

    def register_client_http_call(self, func : JsonCallable):
        assert hasattr(func, '_json_callable'), "Function is not decorated as a JSON callable function"
        func.set_call_handler(self)
        func.set_mode(CallMode.http)

    def register_in_process_call(self, func : JsonCallable):
        assert hasattr(func, '_json_callable'), "Function is not decorated as a JSON callable function"
        func._call_handler = self
        func.set_call_handler(self)
        func.set_mode(CallMode.in_process)

    def build_client_side_rpc_request(self, func : JsonCallable, *func_params):
        assert hasattr(func, '_json_callable'), "Function is not decorated as a JSON callable function"
        func_sig = signature(func._original_func)

        # mainlog.debug("build_client_side_rpc_request : analyzing {}".format(func))
        # if ismethod(func):
        mainlog.debug("Client calling method {}, params : {}".format(func._original_func.__name__, func_params))
        jsonrpc = {
            "jsonrpc": "2.0",
            "method": func.get_service_name(),
            "params": self.params_to_jsonable( func_sig, func.in_recursive_set, func_params),
            "id": 1}
        mainlog.debug("rpc request is : {}".format( jsonrpc))

        # elif isfunction(func):
        #     mainlog.debug("Client calling function {}, params : {}".format(func._original_func.__name__, func_params))
        #     jsonrpc = {
        #         "jsonrpc": "2.0",
        #         "method": "service." + func.__name__,
        #         "params": json_caller.params_to_jsonable( func_sig, False, func.in_recursive_set, func_params),
        #         "id": 1}
        #     mainlog.debug("rpc request is : {}".format( jsonrpc))
        # else:
        #     raise Exception("Unable to guess the type of function {} maybe {} ?".format(func, type(func)))

        return jsonrpc


    def call_json_rpc_over_http(self, rpc_request : dict):

        server_address = urlparse(self._server_url)
        # mainlog.debug("http_call to : {}".format(server_address))

        c = HTTPConnection(server_address.hostname,server_address.port)

        params = dumps(rpc_request, ensure_ascii=False).encode('utf-8')
        headers = {"Content-type": "application/json"}

        # try:
        c.request("POST", "/json_rpc3", params, headers)
        # except socket.error as err:
        #     raise ServerException(err.errno, err.strerror)

        response = c.getresponse()
        mainlog.debug("HTTP Response : {} {}".format(response.status, response.reason))

        return loads( response.read().decode('utf-8') )


    def make_func_rpc_server_callable(self, func : JsonCallable):
        """ Make a JsonCallable able to be called by jsonrpc2.
        "Able to be called" means that the parameters the function receives (which are in JSON
        format) are converted to values or objects before being passed to the
        actual function. Moreover the values/objects returned by the function are
        ready to be converted to JSON.

        Be aware that if one calls a method through RPC, the notion of "self" disappears.
        We must therefore recreate it if necessary, that is, when calling bound functions.
        (somehow, bound functions disappeared from Python 3...)

        :param func: A JsonCallable function
        :return: The jsonrpc2 callable function.
        """

        assert hasattr(func, '_json_callable'), "Function is not decorated as a JSON callable function"
        func_sig = signature(func._original_func)

        def callable_func(**func_kw_params):
            """
            Only keyword args arguments, that is JSON-RPC call-by-name.
            :param func_kw_params:
            :return:
            """

            mainlog.debug("Calling (server side) {}, params : {}".format(func._original_func, func_kw_params))

            params = self.jsonable_to_params(func_sig, func.in_recursive_set, func_kw_params)
            mainlog.debug("Actual params : {}".format(params))

            call_result = func.call_decorated(**params)

            # if func._instance:
            #     mainlog.debug("Calling (server side) method call")
            #     call_result = func( func._instance, **params)
            # else:
            #     mainlog.debug("Calling (server side) function call")
            #     call_result = func(**params)

            # jsonrpc2 will take care of transforming the "jsnonable" data into actual json
            # plus additional JSON-RPC protocol informations (such as request id).
            r = self.return_values_to_jsonable(func_sig, func.out_recursive_set, call_result)

            mainlog.debug("Calling  (server side) {}, returning : {}".format(func._original_func, r))
            return r

        return callable_func


    def in_process_call(self, func : JsonCallable, *func_params):
        """ Make an in process call. That is, a call that goes through JSON serialisation/deserialisation
        but without using an http connection. This is useful when testing
        serialisation.

        This shall be called from the JsonCallable decorator.

        :param func:
        :param func_params:
        :return:
        """

        assert hasattr(func, '_json_callable'), "Function is not decorated as a JSON callable function"
        func_sig = signature(func._original_func)

        intermediate = jsonable_to_json(
            self.params_to_jsonable( func_sig, func.in_recursive_set, func_params))

        params = self.jsonable_to_params(func_sig, func.in_recursive_set, json_to_jsonable(intermediate))
        call_result = func.call_decorated(**params)


        intermediate = jsonable_to_json(self.return_values_to_jsonable(func_sig, func.out_recursive_set, call_result))
        mainlog.debug("in process mode : {}".format(intermediate))
        return self.jsonable_to_return_values(func_sig, func.out_recursive_set, json_to_jsonable(intermediate))


def json_test_harness(json_caller : JsonCaller, func, *func_params):
    assert hasattr(func, '_json_callable'), "Function is not decorated as a JSON callable function"

    func_sig = signature(func._original_func)

    # proto_params = signature(func._original_func).parameters
    # return_proto_params = signature(func._original_func).return_annotation

    mainlog.debug("test_harness: params : {}".format(func_params))

    # Client side code...
    intermediate = jsonable_to_json(json_caller.params_to_jsonable( func_sig, func.in_recursive_set, func_params))
    mainlog.debug("intermediate params : {}".format(intermediate))

    # Server side code...
    params = json_caller.jsonable_to_params(func_sig, func.in_recursive_set, json_to_jsonable(intermediate))
    mainlog.debug("intermediate params-2 : {}".format(params))

    # PArams is expected to be a dict of parameters, beause we use
    # the call by name convention in JSON-RPC
    call_result = func(**params)

    intermediate = jsonable_to_json(json_caller.return_values_to_jsonable(func_sig, func.out_recursive_set, call_result))
    mainlog.debug("intermediate return : {}".format(  intermediate))

    # CLient side code...
    return json_caller.jsonable_to_return_values(func_sig, func.out_recursive_set, json_to_jsonable(intermediate))


