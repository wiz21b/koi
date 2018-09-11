import sys
from urllib.parse import urlencode
from http.client import HTTPConnection, HTTPSConnection


import socket
from koi.python3 import DeclEnum,EnumSymbol
from datetime import date,datetime
import base64
import inspect

from json import loads
from json import JSONEncoder
from jsonrpc2 import JsonRpc

import sqlalchemy.util._collections
# from koi.datalayer.sqla_mapping_base import Base


from koi.tools.chrono import *

from koi.datalayer.RollbackDecorator import RollbackDecorator

from koi.datalayer.generic_access import DictAsObj
from urllib.parse import urlparse


from koi.db_mapping import OrderStatusType, TaskActionReportType, OrderPartStateType
from koi.people_admin.people_admin_mapping import DayEventType
from koi.datalayer.quality import QualityEventType
pycharm_exceptions = [DayEventType, OrderStatusType, TaskActionReportType, QualityEventType, OrderPartStateType] # Because I fiddle with globals()


from koi.datalayer.sqla_mapping_base import metadata,Base
from koi.junkyard.sqla_dict_bridge import ChangeTracker
change_tracker = ChangeTracker(Base)

"""
    messages = {1000 : u"The task {} is not imputable",
                1001 : u"Unknown operation definition {} for non billable task",
                1003 : u"The task {} for operation definition {} is not active",
                1004 : u"Unknown operation {} for on-operation task or operation is not imputable",
                1005 : u"Operation {} is not imputable *or* order part {} is not in production",
                1006 : u"Combination of operation definition {} for order {} doesn't exist",
                1007 : u"Combination of operation definition {} for order {} is not imputable",
                1008 : u"The task for operation definition {} on order {} is not active",
                1009 : u"There's no employee with id= {}",
                1010 : u"The barcode syntax is valid but I can't make sense of it : {}",
                1012 : u"The barcode syntax is incorrect {}",
                2000 : u"Operational error {}"}
"""

# FIXME Rename this to have all errors of Horse located in the same class
# But this implies having translations as well

class ServerErrors(DeclEnum):

    def _(t):
        """ The idea here is to mark all messages for translations so
        that gettext find them when createing messages database.
        But, at the same time, we want to retain the original
        text in plain english)
        """

        return t

    general_failure = 100, _("General failure. Guru meditation. {}")

    task_not_imputable = 1000, _("The task {} is not imputable")
    operation_definition_not_imputable = 1002, _("Operation definition {} is not imputable")
    unknown_employee_id = 1009, _("There's no employee with id= {}")
    barcode_invalid = 1010, _("The barcode syntax is valid but I can't make sense of it : {}")
    bad_presence_record = 1011, _("Encountered an error '{}' while recording presence for employee_id : {}")
    barcode_syntax_invalid = 1012,  _("The barcode syntax is incorrect {}")
    operation_unknown = 1013, _("The operation {} is unknown")
    operation_definition_unknown = 1014, _("The operation definition {} is unknown")
    order_part_not_in_production_unknown = 1015, _("The order part {} is not in production")

    invalid_parameter = 1100, _("Invalid parameter {}")
    wrong_number_of_parameters = 1101, _("The number of parameters is invalid. I expected {}, you gave {}")

    too_much_off_time_on_a_day = 1150, _("Too much off time on the {}")

    file_name_cannot_be_empty = 1200, _("File name cannot be empty")
    printing_an_empty_report = 1300, _("Cannot print an empty report")

    cannot_delete_employee_because_orders = 1400, _("Cannot delete this employee because there are orders for him. Remove the orders first.")
    db_error = 2000, _("Database error {}")
    operation_non_imputable = 2005, _("Operation {} is not imputable *or* order part {} is not in production *or* is not known")
    machine_not_compatible_with_operation = 2006, _("The machine you want {} is not compatible with those ({}) associated to the operation")
    unknown_machine = 2007, _("The machine with ID {} is not known")


class ServerException(Exception):

    JSON_CODE = -32001

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        # Will return a technical version of the exception
        # in english
        return self._msg

    def _set_translation(self, base_message, args):
        if args:
            self.translated_message = _(base_message).format(*args)
        else:
            self.translated_message = _(base_message)



    def _init_from_json(self, json_dict):
        # See __init__.py in jsonrpc2 :

        # 'error':{'code': self.get_app_error_code(e),
        #          'message': str(e),
        #          'data': json.dumps(e.args)}


        mainlog.debug("Interpreting call result : {}".format(str(json_dict)))

        self.code = json_dict['code'] # Standard JSON protocol 'code' field (32000,...)
        self._msg = json_dict['message'] # Standard JSON protocol 'message' field
        args = None

        if self.code == self.JSON_CODE and 'data' in json_dict:
            base_message, args = loads( json_dict['data']) # Standard JSON protocol 'data' tuple
            self._set_translation(base_message, args)
            mainlog.debug("_init_from_json base_message:{} params:{}".format(base_message, args))
        else:
            self._set_translation(self._msg, None)

        super(ServerException,self).__init__(self._msg, args)


    def _init_for_jsonrpc2( self, code, base_message, args=None):
        """ Construct the exception in such a way that it'll be
        properly serialized by JsonRpc
        """

        self.code = code # Will be used by our patched RPC Handler

        # Set what will be returned by str(this exception)

        if args:
            m = base_message.format(*args)
        else:
            m = base_message
        self._msg = u"[{}] {}".format(code, m) # Will be used via the str() method, for technical reporting => should stay in English

        # Prepare a translated version of the message

        self._set_translation(base_message, args)

        # JsonRpc will transfer the exception's args

        # json_args = dict()
        # json_args['base_message'] = base_message # The untranslated message
        # json_args['args'] = args

        super(ServerException,self).__init__( base_message, args)


    def __init__(self, server_error=None, *args):

        # args won't be used as supplied by the caller. They'll be
        # wrapped into a dict and mixed with other JSONRpc related stuff
        # So don't expect exception.args to work as stated in the
        # Python documentation.

        if isinstance(server_error, dict):

            # When we have dict, we assume we're building an exception
            # out of a json serialized one.

            self._init_from_json(server_error)

        elif isinstance(server_error, int) or isinstance(server_error, str):

            # DEPRECATED !!!

            # One gave an error code as an integer and some parameter

            try:
                server_error = ServerErrors.from_str(str(server_error))
                self._init_for_jsonrpc2( server_error.value, server_error.description, *args)
            except Exception as ex:
                mainlog.error("Error while building an error, code {} is unknown".format(server_error))
                # The error code is not known (this happens if the server
                # is some versions ahead of the client.
                self._init_for_jsonrpc2( server_error, args[0])

        elif server_error:

            self._init_for_jsonrpc2( server_error.value, server_error.description, args)

        else:

            # No server_error => we create a blank object
            self.code = None
            self._msg = ""
            self.translated_message = ""
            super(ServerException,self).__init__()



# class ServerException(Exception):
#     def __repr__(self):
#         return self.msg

#     def __str__(self):
#         # Make sure JsonRpc2 gets the message so it can put it in the message
#         # part of the json rpc error.
#         # Note that overriding __repr__ has no effect in python 2.7
#         return self.msg

#     def _make_technical_message(self, serror, *args):

#         # The technical message has its parameters set between accolades.
#         # That's because the JSON dispatcher only return exceptions
#         # in the form "error code, message". So if we have to translate
#         # the message on client side, then we'll need to be able
#         # to extract the message parameters.

#         # If we work with regular http server, then we'd assume
#         # the message is translated server side. But with our
#         # fat client, there's no session information so it's not possible
#         # to rememeber the user's locale between client and server.
#         # Therefore we give the error message untranslated and we
#         # expect the client to translate it itself.

#         # I could also work with error codes, but there would be a slakk
#         # risk of desynchronisation between the client and the server...

#         pargs = [ u"{" + arg + u"}" for arg in args]
#         self.msg = serror.description.format(pargs)


#     def _translate_technical_message(self, msg):

#         import re
#         rp = re.compile(r'\{[^\}]+\}')

#         original_params = [ p[1:-1] for p in rp.findall(msg) ]
#         original_msg, cnt = rp.subn('{}', s)

#         return _(original_msg).format(original_params)



#     @classmethod
#     def deserialize_json(self, dikt):
#         """ Deserialize from JSON call. At this point, we have a dict
#         with code and message coming from the json dispatcher.
#         """

#         return dikt['code'], dikt['message']



#     def exception_message(self):
#         return u"[{}] {}".format(self.code, self.msg)


#     def __init__(self, serror, *args):

#         if type(serror) == dict:
#             self.code,self.msg = self.deserialize_json(serror)

#             scode = "[{}] ".format(self.code)
#             super(ServerException,self).__init__( self.exception_message())

#         elif hasattr(serror,"cls") and serror.cls == ServerErrors:
#             self.__init_helper(serror,*args)

#         elif isinstance(serror, int) or isinstance(serror, str):
#             # Deprecated !!! Use ServerError enum instead

#             try:
#                 self.__init_helper(ServerErrors.from_str(serror),*args)
#             except Exception as ex:
#                 mainlog.error("Error while building an error, code {} is unknown".format(serror))
#                 # The error code is not known (this happens if the server
#                 # is some versions ahead of the client.
#                 self.code = str(serror)
#                 self.msg = args[0]
#         else:
#             raise Exception("Can't construct a ServerException because the arguments were not recognized : {} {}".format(type(serror), args))

#     def __init_helper(self, serror, *args):
#         """ Prepare the exception with a ServerError
#         """

#         # *args is used to get a list of the parameters passed in
#         self.code = serror.value
#         msg = serror.description

#         scode = "[{}] ".format(self.code)

#         # print("Buildin message {}".format(msg))
#         # print("Buildin message {}".format(args))
#         if msg.count('{}') > len(args):
#             self.msg = msg
#         else:
#             # print("Buildin message with args")
#             self.msg = msg.format(*args)

#         super(ServerException,self).__init__(self.exception_message())

#         # We help JsonRpc to *not* display anything in the
#         # data part of an error message
#         self.args = []


class KTWrapper(object):
    """ We wrap SQLA KeyedTuples because they look like *tuples* to the dumps function. So if we don't
    wrap them, they are serialised as actual tuples, without keys (instead of keyed
    tuples). Because of that we can't deserialize them back to objects.
    That's because dumps locates tuple with instanceof(kt,tuple) which is
    less strict than type(kt) == tuple (and that fails because keyed_tuples inherits
    from tuple)
    """

    def __repr__(self):
        z = "<KTWrapper> "
        for k,v in self.keyed_tuple._asdict().items():
            z += u"{}='{}' ".format(k,v)
        return z

    def __init__(self, kt):
        self.keyed_tuple = kt

class HorseJsonEncoder(JSONEncoder):


    def default(self, obj):
        """ As stated in Python's doc : implement a default() method
        that returns a serializable object for o.
        """

        # mainlog.debug("Default encoder for {}".format(type(obj)))
        if isinstance(obj, KTWrapper):
            # Remember, KeyedTuple are first and foremost tuples and therefore, they are
            # caught by the python JSON encoder first as tuples. So I wrap the KeyedTuple
            # so that they're not tuples anymore
            return { '__keyed_tuple__' : obj.keyed_tuple._asdict() }

        elif isinstance(obj, datetime):
            return { '__datetime__' : datetime.strftime( obj, "%Y-%m-%dT%H:%M:%S.%f" ) }
        elif isinstance(obj, date):
            return { '__date__' : obj.isoformat() }
        elif isinstance(obj,EnumSymbol):
            return { '__enum__' : (obj.value, obj.cls.__name__) }
        elif isinstance(obj,bytes): # Python 3
            return { '__bytes__' : base64.b64encode(obj).decode('ascii')}
        elif isinstance(obj,memoryview): # Python 2.7
            data = base64.b64encode(obj.tobytes()).decode('ascii')
            # mainlog.debug("HorseJsonEncoder.default : type of encoded bytes data = ".format(type(data)))
            return { '__bytes__' : data}

        elif isinstance(obj, object) and hasattr(obj, '_sa_instance_state'):
            # SQLA object

            # WARNING This will fail if one has relationships in there...
            # I guess it is safe to use this encoder only for SQLA objects
            # which are not in a SQLA session

            # mainlog.debug("Default encoding for SQLA object {}".format(obj))
            d = obj.__dict__.copy()
            del d['_sa_instance_state']

            return { '__object__' : d }

        elif isinstance(obj, object):
            mainlog.debug("Default encoding for {}".format(obj))
            mainlog.debug(obj.__dict__)

            # JSON encodes objects to JSON dicts. But then it decodes
            # them as dict.
            # Therefore, if I want to decode an object and not a dict, I have
            # to make that explicit, hence the '__object__' key.
            return { '__object__' : obj.__dict__ }
        else:
            try:
                return super(HorseJsonEncoder, self).default(obj)
            except TypeError as ex:
                mainlog.error("Python's json can't encode {} of type {}".format(obj, type(obj)))
                raise ex

# Instanciation here so that we don't have to instanciate it everywhere.
horse_json_encoder = HorseJsonEncoder()

def wrap_keyed_tuples(kt_list):
    """ Wrap SQLA KeyedTuple (or list of them) so that they are properly
    serialized/dezerialized
    """

    if not kt_list:
        return kt_list
    else:
        return [KTWrapper(obj) for obj in kt_list]


def super_encoder(*args):
    # Will catch the first level of KeyedTuple.
    # This is very hack-ish. That's because there's no way to change
    # the dumps' behaviour which consists in serializing tuples as
    # simple list (dumps doesn't distinguish KeyedTuple from tuples).
    # The keyed tuple is special in the sense that we prefer to
    # see it as a dict.
    # I tried the 'default' function but it is called only when
    # dumps can't figure the type of what it serialize. In our case, dumps
    # figures it as tuple, and happily discards our default serializer.
    # I also tried to monkey-patch (or simply patch) json library but
    # it seems that all the fastest stuff is done in C => no patching
    # possible without patching the C code (and I don't have a C compiler
    # up and running on windows)...

    mainlog.debug("super encoding {} of type {}".format( args, type(args)))
    if len(args) == 0:
        return None
    elif len(args) > 1:
        # Convert many args into a list of many args
        return super_encoder(args)
    elif len(args) == 1:
        obj = args[0]

        if not obj:
            return obj
        # This is very dirty, but it's because of this : https://bitbucket.org/zzzeek/sqlalchemy/issues/3176
        elif str(type(obj)) == "<class 'sqlalchemy.util._collections.result'>":
            #print(obj)
            return KTWrapper(obj)
        elif isinstance(obj,list) or isinstance(obj,tuple):
            return [super_encoder(list_obj) for list_obj in obj]
        else:
            return obj # The JSON encoder will do the rest

def super_encoder_OLD(obj):
    # Will catch the first level of KeyedTuple.
    # This is very hack-ish. That's because there's no way to change
    # the dumps' behaviour which consists in serializing tuples as
    # simple list (dumps doesn't distinguish KeyedTupe from tuples).
    # I tried the 'default' function but it is called only when
    # dumps can't figure the type of what it serialize. In our case, dumps
    # figures it as tuple, and happily discards our default serializer.
    # I also tried to monkey-patch (or simply patch) json library but
    # it seems that all the fastest stuff is done in C => no patching
    # possible without patching the C code...

    if isinstance(obj,list) and obj and isinstance(obj[0],sqlalchemy.util._collections.KeyedTuple):
        return wrap_keyed_tuples(obj)
    elif isinstance(obj, sqlalchemy.util._collections.KeyedTuple):
        return wrap_keyed_tuples(obj)
    else:
        return obj


def json_object_hook(d):
    """ From the library reference of Python : object_hook is an optional
    function that will be called with the result of any object literal
    decoded (a dict). The return value of object_hook will be used instead
    of the dict.
    """

    if "__object__" in d:

        return DictAsObj( d['__object__'])

    #     from koi.datalayer.sqla_mapping_base import metadata,Base
    #     from koi.junkyard.sqla_dict_bridge import ChangeTracker
    #     change_tracker = ChangeTracker(Base)
    #
    #     return change_tracker.unserialize_full(d)

    elif "__keyed_tuple__" in d:
        # Namedtuple don't accept keys that starts with '_'.
        # Types construction makes me mad with object initialisation.
        # Therefore, I do this :
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
        obj.__dict__.update(d['__keyed_tuple__'])
        return obj

    elif '__sqla_object__' in d:
        # print(sorted(globals().keys()))

        # Instanciate an object based on the type in d.
        obj = globals()[d['type']]()
        obj.__dict__.update(d['__sqla_object__']) # This doens't work because SQLA's entities don't like it
        return obj

    elif "__date__" in d:
        # mainlog.debug("json_object_hook : parsing a date : {}".format([int(x) for x in d['__date__'].split('-')]))
        return date( *([int(x) for x in d['__date__'].split('-')]) )

    elif "__datetime__" in d:
        return datetime.strptime( d['__datetime__'], "%Y-%m-%dT%H:%M:%S.%f" )
        #return dateutil.parser.parse(d['__date__'])

    elif "__enum__" in d:
        v,cls = d['__enum__']

        try:
            # Remember for globals : "This is always the dictionary of the current module".
            # So one has to meke sure the global definitions are known here...
            # FIXME and that is a manual process...

            obj = globals()[cls]
            return obj.from_str(v)
        except Exception as ex:
            mainlog.error("Globals {}".format(sorted(globals().keys())))
            mainlog.exception(ex)
            raise Exception("Can't un-json the enumeration with value '{}' of class '{}' ({})".format(v,cls, type(cls)))

    elif "__bytes__" in d:
        return base64.b64decode(d["__bytes__"])
    else:
        return d


def get_class_that_defined_method(meth):
    if inspect.ismethod(meth):
        for cls in inspect.getmro(meth.__self__.__class__):
           if cls.__dict__.get(meth.__name__) is meth:
                return cls
        meth = meth.__func__ # fallback to __qualname__ parsing
    if inspect.isfunction(meth):
        cls = getattr(inspect.getmodule(meth),
                      meth.__qualname__.split('.<locals>', 1)[0].rsplit('.', 1)[0])
        if isinstance(cls, type):
            return cls
    return None # not required since None would have been implicitly returned anyway




# class deprecated_JSonServer(object):
#     """ Annotation to transform a function that returns R in a function
#     that returns a value that can be easily serialized to juson.

#     The first purpose tof this construction is to give the ability
#     to prepare the result of an arbitrary function for serialization
#     (for example, by removing some data).

#     The second purpose of this function is to have a chance
#     to properly serialize KeyedTuples.

#     Note that the result of the wrapped function is something easy to
#     serialize, not something that is serialized.
#     """

#     register = dict()

#     def __init__(self, types, encoder=super_encoder):
#         global JSonServer_wrapping_active

#         self.types = types
#         self.encoder = encoder
#         # print("Initing wrapper {}".format(JSonServer_wrapping_active))

#     def __call__(self,func,*param_types):

#         JSonServer.register[func] = self.encoder

#         def _wrapper_func(*args,**kwargs):

#             # The json dispatcher will transform a dict of params
#             # into kwargs or args, depending on how the parameters
#             # were encoded. So our code must support both
#             # types of arguments specification (positional or keyword args).
#             # In any case, the first arg will be the service's self.

#             # The parameter will be in JSON format, so we'll cast
#             # them into actual python types.

#             # print("Entering wrapper {}".format(JSonServer_wrapping_active))
#             if not JSonServer_wrapping_active[0]:
#                 # print("WRAPPING DISABLED" * 10)
#                 return func

#             prep_args = [t for t in args[1:]]

#             # mainlog.debug("types = {}".format(self.types))
#             # mainlog.debug("args = {}".format(args))
#             # mainlog.debug("kwargs = {}".format(kwargs.keys()))

#             # mainlog.debug(" func args = {}".format(inspect.getargspec(func).args))
#             # mainlog.debug(inspect.getargspec(func).args[1:])
#             if kwargs:
#                 for arg_name in inspect.getargspec(func).args[1:]:
#                     try:
#                         prep_args.append( kwargs[arg_name] )
#                     except KeyError as ke:
#                         raise Exception("While calling {}, the argument '{}' was missing".format(func, arg_name))

#             # mainlog.debug("prep_args = {}".format(prep_args))


#             if len(self.types) != len(prep_args):
#                 raise ServerException(ServerErrors.wrong_number_of_parameters,len(self.types), len(prep_args))

#             # There are three situations
#             # * Direct call to service : in that case the *args are just plain python object
#             # * Simulated HTTP call : in that case, we receive the args in a form that comes out of the "params" dict specified by the JSON spec.
#             # * Actual HTTP call : same as simulated HTTP call
#             # Therefore, the wrapper can receive the same parameter in different forms (for ex. a datetime or a JSONified datetime)
#             # We should have two code paths : one for "direct" parameters and one for "json" parameters

#             def _param_cast(param, type_):
#                 mainlog.debug("Casting {} of type {} into {}".format(param, type(param), type_))

#                 cast = None
#                 if param is None:
#                     cast = None

#                 elif type(param) == dict:
#                     mainlog.debug("It's a dict!")
#                     # FIXME So we won't be able to pass dict's in !!!
#                     cast = json_object_hook(param)

#                 elif type(param) == EnumSymbol:
#                     # There is a type impedance here. We get EnumSymbol
#                     # but the type specified in the decorator call
#                     # is the type of the enumeration (not the one of its symbols)
#                     # By not casting we actually pass handling of the
#                     # enumeration to the JSON encoder/decoder.
#                     cast = param

#                 elif type_ != type(param):
#                     mainlog.debug("Regular cast")
#                     cast = type_(param)

#                 else:
#                     # No cast at all
#                     cast = param

#                 mainlog.debug(" --> Cast to {} of type {}".format(cast, type(cast)))
#                 return cast


#             try:
#                 cast_args = [args[0]] +  [ _param_cast(v,t) for t,v in zip(self.types, prep_args)]
#             except Exception as e:
#                 mainlog.error("Unable to cast parameters")
#                 mainlog.error(u"Destination types are : {}, source types: {}, source values are : {}".format(self.types, [type(a) for a in prep_args], prep_args))

#             # mainlog.debug("Calling with final cast args = {}".format(cast_args))
#             r =  func(*cast_args)

#             return r

#             # mainlog.debug("Function returned")

#             # Allow to server functions to return tuples (for example, "return price1, time1")
#             if type(r) == tuple:
#                 return self.encoder(*r)
#             else:
#                 return self.encoder(r)

#         _wrapper_func.original_func = func
#         _wrapper_func._json_encoder = self.encoder

#         return _wrapper_func

from koi.utils import SourceFunctionDecorator
def JsonCallable(param_types = [], result_encoder=super_encoder):

    class JsonCallableDecorator(SourceFunctionDecorator):
        def __init__(self, func):
            super(JsonCallableDecorator,self).__init__(func)

            proto = inspect.getfullargspec(self._original_func)
            # In the args, we skip the 'self' (first arg)
            self._prototype = proto.args[1:]
            self._json_param_types = param_types

            i = 0
            for arg_name in proto.args[1:]:

                if arg_name not in proto.annotations:
                    mainlog.error("Untyped parameter in {}".format(func))
                    raise Exception("Untyped parameter")

                # t = proto.annotations[arg_name]
                # if not t == param_types[i]:
                #     mainlog.error("Prototypes don't match {} != {}".format( t, param_types[i]))
                #     raise Exception("Prototypes don't match {} != {}".format( t, param_types[i]))

                i += 1

            self._json_param_result_encoder = result_encoder

        # def __get__(self, instance, cls=None):
        #     print("JsonCallableDecorator.__get__")
        #     return super(JsonCallableDecorator,self).__get__(instance, cls)

        # def __call__(self, *args):
        #     print("JsonCallableDecorator.__call__ {} args:{}".format(self._original_func, args))
        #     self._original_func(*args)

    return JsonCallableDecorator

# def JsonCallable(param_types = [], result_encoder=super_encoder):
#     # Decorator with parameters, will return the actual decorator
#     # which decorates the target function
#
#     def decorator(func):
#         if isinstance(func, RollbackDecorator):
#             mainlog.debug("Wrapping {} which actually was originally {}".format(func, func.func))
#             func.__original_func = func.func
#         else:
#             func.__original_func = func
#
#         func.__prototype = inspect.getargspec(func.__original_func).args[1:]
#         func.__json_param_types = param_types
#         func.__json_param_result_encoder = result_encoder
#         return func
#
#     return decorator




# def _json_func_call(proxied_func, *args,**kwargs):

#     # The goal of this function is to proxy a given func
#     # so that it can receive and return JSON data.

#     # The json dispatcher will transform a set of params
#     # into kwargs or args, depending on how the parameters
#     # were encoded. So our code must support both
#     # types of arguments specification (positional or keyword args).
#     # In any case, the first arg will be the service's self.

#     # The parameter will be in JSON format, so we'll cast
#     # them into actual python types.

#     # print("Entering wrapper {}".format(JSonServer_wrapping_active))
#     if not JSonServer_wrapping_active[0]:
#         # print("WRAPPING DISABLED" * 10)
#         return func

#     prep_args = [t for t in args[1:]]

#     # mainlog.debug("types = {}".format(self.types))
#     # mainlog.debug("args = {}".format(args))
#     # mainlog.debug("kwargs = {}".format(kwargs.keys()))

#     # mainlog.debug(" func args = {}".format(inspect.getargspec(func).args))
#     # mainlog.debug(inspect.getargspec(func).args[1:])
#     if kwargs:
#         for arg_name in inspect.getargspec(func).args[1:]:
#             try:
#                 prep_args.append( kwargs[arg_name] )
#             except KeyError as ke:
#                 raise Exception("While calling {}, the argument '{}' was missing".format(func, arg_name))

#     # mainlog.debug("prep_args = {}".format(prep_args))


#     if len(types) != len(prep_args):
#         raise ServerException(ServerErrors.wrong_number_of_parameters,len(self.types), len(prep_args))

#     # There are three situations
#     # * Direct call to service : in that case the *args are just plain python object
#     # * Simulated HTTP call : in that case, we receive the args in a form that comes out of the "params" dict specified by the JSON spec.
#     # * Actual HTTP call : same as simulated HTTP call
#     # Therefore, the wrapper can receive the same parameter in different forms (for ex. a datetime or a JSONified datetime)
#     # We should have two code paths : one for "direct" parameters and one for "json" parameters

#     def _param_cast(param, type_):
#         mainlog.debug("Casting {} of type {} into {}".format(param, type(param), type_))

#         cast = None
#         if param is None:
#             cast = None

#         elif type(param) == dict:
#             mainlog.debug("It's a dict!")
#             # FIXME So we won't be able to pass dict's in !!!
#             cast = json_object_hook(param)

#         elif type(param) == EnumSymbol:
#             # There is a type impedance here. We get EnumSymbol
#             # but the type specified in the decorator call
#             # is the type of the enumeration (not the one of its symbols)
#             # By not casting we actually pass handling of the
#             # enumeration to the JSON encoder/decoder.
#             cast = param

#         elif type_ != type(param):
#             mainlog.debug("Regular cast")
#             cast = type_(param)

#         else:
#             cast = param

#         mainlog.debug("Casted to {} of type {}".format(cast, type(cast)))
#         return cast


#     try:
#         cast_args = [args[0]] +  [ _param_cast(v,t) for t,v in zip(self.types, prep_args)]
#     except Exception as e:
#         mainlog.error("Unable to cast parameters")
#         mainlog.error(u"Destination types are : {}, source types: {}, source values are : {}".format(self.types, [type(a) for a in prep_args], prep_args))

#     # mainlog.debug("Calling with final cast args = {}".format(cast_args))
#     r =  proxied_func(*cast_args)
#     # mainlog.debug("Function returned")

#     # Allow to server functions to return tuples (for example, "return price1, time1")
#     if type(r) == tuple:
#         return self.encoder(*r)
#     else:
#         return self.encoder(r)




def jsonFuncWrapper(decorated_func):
    """ Wraps a method so that its parameters can come from various sources,
    such as : regular python call, or JSON call.

    The method is expected to be decorated with the JsonCallable
    decorator so we can have access to some metadata we need.

    In case of JSON call, the parameters are expected to be serialised
    as JSON-RPC says it. So this wrapper will have to deserialize those
    parameters before actually calling the wrapped method.

    FIXME This whole thing is completely weird. I'm sure I missed something big
    while architecturing this...

    :param decorated_func:
    :return:
    """

    mainlog.debug("jsonFuncWrapper : wrapping decorated_func = {}".format(decorated_func))

    mainlog.debug(decorated_func.__dict__)

    if not hasattr(decorated_func, '_json_param_types'):
        raise Exception("Missing _json_param_types ! Seems like the function you're calling was not annotated as a json server one")
    else:
        mainlog.debug(decorated_func._json_param_types)

    mainlog.debug("Applying jsonFuncWrapper wrapper to {}".format(decorated_func))

    # A wrapper (not a decorator)

    func           = decorated_func
    param_types    = decorated_func._json_param_types
    result_encoder = decorated_func._json_param_result_encoder
    prototype      = decorated_func._prototype

    def _wrapper_func_json(*args,**kwargs):
        mainlog.debug("Calling jsonFuncWrapper wrapper")

        # The json dispatcher will transform a dict of params
        # into kwargs or args, depending on how the parameters
        # were encoded. So our code must support both
        # types of arguments specification (positional or keyword args).
        # In any case, the first arg will be the service's self.

        # The parameter will be in JSON format, so we'll cast
        # them into actual python types.

        # print("Entering wrapper {}".format(JSonServer_wrapping_active))
        # if not JSonServer_wrapping_active[0]:
        #     # print("WRAPPING DISABLED" * 10)
        #     return func

        prep_args = [t for t in args[1:]]

        if kwargs:

            # mainlog.debug(" -- "*20)
            # mainlog.debug(func.__prototype)
            # mainlog.debug(" -- "*20)
            # mainlog.debug(inspect.getargspec(func).args[1:])

            for arg_name in prototype: #inspect.getargspec(func).args[1:]:
                try:
                    prep_args.append( kwargs[arg_name] )
                except KeyError as ke:
                    raise Exception("While calling {}, the argument '{}' was missing".format(func, arg_name))

        mainlog.debug("types = {}".format(param_types))
        mainlog.debug("args = {}".format(args))
        mainlog.debug("kwargs = {}".format(kwargs.keys()))
        mainlog.debug("prep_args = {}".format(prep_args))
        # mainlog.debug(" func args = {}".format(inspect.getargspec(func).args))
        # mainlog.debug(inspect.getargspec(func).args[1:])


        if len(param_types) != len(prep_args):
            raise ServerException(ServerErrors.wrong_number_of_parameters,len(param_types), len(prep_args))

        # There are three situations
        # * Direct call to service : in that case the *args are just plain python object
        # * Simulated HTTP call : in that case, we receive the args in a form that comes out
        #   of the "params" dict specified by the JSON spec.
        # * Actual HTTP call : same as simulated HTTP call
        # Therefore, the wrapper can receive the same parameter in different forms
        # (for ex. a datetime or a JSONified datetime). We should have two code paths :
        # one for "direct" parameters and one for "json" parameters

        def _param_cast(param, type_):
            mainlog.debug("Casting {} of type {} into {}".format(param, type(param), type_))

            cast = None
            if param is None:
                cast = None

            elif type(param) == list and type(type_) == list:
                # In case one expects a list, the type is given as
                # [ Class ], that is a one-item list. The item
                # is the expected type of the items in the list.
                # FIXME This type checking is ignored it what's inside
                # the array/list are dictionaries (because the actualy type
                # is inferred from the JSON params dictionary)...

                cast = [ _param_cast(i,type_[0]) for i in param]

            elif type(param) == dict and '__model__' in param:
                # We leave the interpretation of the model data to the
                # caller

                mainlog.debug("It's a model!")
                cast = param

            elif type(param) == dict:
                mainlog.debug("It's a dict : {}".format(param))
                cast = json_object_hook(param)

            elif type(param) == EnumSymbol:
                # There is a type impedance here. We get EnumSymbol
                # but the type specified in the JsonCallable decorator call
                # is the type of the enumeration (not the one of its symbols)
                # By not casting we actually pass handling of the
                # enumeration to the JSON encoder/decoder.
                cast = param

            elif type_ in (str,int,float) and type_ != type(param):
                mainlog.debug("Basic type cast")
                cast = type_(param)


            elif inspect.isclass(type_) and type_ != type(param):
                mainlog.debug("Object cast")
                cast = type_()

                for k,v in param.__dict__.items():
                    setattr(cast,k,v)

            elif type_ != type(param):
                # Regular cast should be applied to "easy" types such as float, int, str, unicode,...
                mainlog.debug("Regular cast")
                cast = type_(param)

            else:
                mainlog.debug("No cast")
                cast = param

            mainlog.debug("Cast to {} of type {}".format(cast, type(cast)))
            return cast


        try:
            cast_args = []

            mainlog.debug("adding params")
            for t,v in zip(param_types, prep_args):
                mainlog.debug("    casting {} to type {}".format(v,t))
                cast_args.append(_param_cast(v,t))

            # cast_args = [args[0]] +  [ _param_cast(v,t) for t,v in zip(param_types, prep_args)]
        except Exception as e:
            mainlog.exception(e)
            mainlog.error("Unable to cast parameters")
            mainlog.error(u"Destination types are : {}".format(param_types))
            mainlog.error(u"source types: {}, source values are : {}".format([type(a) for a in prep_args], prep_args))

        mainlog.debug("Calling with final cast args = {}".format(cast_args))
        mainlog.debug(str(func))

        # The actual call to the service object
        # This is an object method call, it's a *bound* function, therefore
        # Python knows the 'self'.

        try:
            r =  func(*cast_args)
        except Exception as ex:
            mainlog.exception(ex)
            raise ex

        mainlog.debug("Function returned raw data : type = {}, data : {}".format( type(r), r))
        if type(r) == list and len(r) >= 1:
            mainlog.debug("   elements are of type {}".format( str(type( r[0]))))

        # Allow to server functions to return tuples (for example, "return price1, time1")
        if type(r) == tuple:
            return result_encoder(*r)
        else:
            return result_encoder(r)

    _wrapper_func_json.__original_func = func

    return _wrapper_func_json




# def make_server_json_dispatcher2( service):
#     json_dispatcher = dict()
#     for m_name,m in inspect.getmembers(service):
#         if inspect.ismethod(m) and hasattr(m,'original_func'):
#             # print(service.__class__.__name__)
#             endpoint_name = "{}.{}".format(service.__class__.__name__, m.original_func.__name__)
#             json_dispatcher[endpoint_name] = m
#
#     return json_dispatcher
#


def make_server_json_server_dispatcher(json_dispatcher, wrapped_service):
    """ Extends the given json dispatcher (a JsonRpc instance)
    with the marked methods of the sevrice instance. The service
    instance is expected to be wrapped in a JsonCallWrapper.

    The names of the Json methods are built with following
    a class_name_dot_method name. This introduces some hard
    coupling but right now it improves speed of development,
    so we go for it.

    The dispatcher is intended to be used in a server context
    but that's not a law...
    """

    # This has to be done after all classes definition are complete
    # else we don't have acces to class names (since they are not defined :-) )

    if not json_dispatcher or not isinstance(json_dispatcher, JsonRpc):
        raise Exception("The json rpc dispatcher is not correct")

    # Unwrapped service.
    service = wrapped_service.service

    for m_name,m in inspect.getmembers(service):

        # mainlog.debug("Analyzing {} -> {}".format(m_name, m))
        # Filter methods that were marked as being visible on the server
        if hasattr(m,'_original_func'):


            # For the published names, we use the original service
            endpoint_name = "{}.{}".format(wrapped_service.service.__class__.__name__, m._original_func.__name__)

            mainlog.debug("Registering {}".format(endpoint_name))

            # Look through RollbackDecorator

            f = getattr( wrapped_service, m._original_func.__name__)
            # if isinstance(f,RollbackDecorator):
            #     f = f.original_func

            # For the functions that will actually be called, we use
            # the wrapped service (because the methods are decorated)
            json_dispatcher[endpoint_name] = f

            mainlog.debug("Dispatcher wired to {}".format(json_dispatcher[endpoint_name]))
            # JsonFuncWrapper(original_func, param_types, result_encoder)


    # for func in JSonServer.register.keys():
    #     endpoint_name = "{}.{}".format(get_class_that_defined_method(func).__name__, func.__name__)
    #     print(endpoint_name)
    #     json_dispatcher[endpoint_name] = func

    return json_dispatcher



class JsonCallWrapper(object):
    """ Wraps a json service (an instance of a class) so that whenever its methods
    are called, they are actually called through an HTTP/Json call.
    This is done completely transparently, provided the input and
    output of the methods can be serialized/deserialized by Json.

    With this HTTP call I have round trip times of 5 milliseconds
    when the server is localhost on some simple tests
    """

    HTTP_MODE = "HTTP" # wrap for calling a http server
    IN_PROCESS_MODE = "IN PROCESS" # wrap for simulating a call to a http server
    CHERRYPY_MODE = "CHERRYPY" # wrap to expose the object's method in cherrypy server
    DIRECT_MODE = "DIRECT" # Very direct call, no JSON encode/decode whatsoever

    def __init__(self, service, mode=None):
        assert service

        self.service = service
        self.mode = mode or JsonCallWrapper.HTTP_MODE

        # mainlog.debug("JsonCallWrapper in mode {}".format(self.mode))

    def __getattr__(self, name):
        # In case you wonder, the getattr method will be called
        # to actually get the methods of the service, that's the
        # standard Python stuff...

        def direct_call(decorated_func, *args, **kwargs):

            # Direct call without a bit of parameter/return values
            # transformation
            r = decorated_func( *args, **kwargs)
            return r


        def cherrypy_call(decorated_func, *args, **kwargs):

            # We expect cherrypy to JSON-decode the parameters and to JSON-encode
            # the results for us. Note that, for latter to work, the results must
            # be in a form that can be easily JSON-encoded

            # Therefore, since JSON-decoded/encoded stuff is not completely decoded
            # we have to wrap the call in a function that will give us propoer
            # data structures.
            # return _json_func_call(wrapped_func, *args, **kwargs)

            wrapped_func = jsonFuncWrapper(decorated_func)
            return wrapped_func(*args, **kwargs)


        def in_process_call(decorated_func, the_self, *args):

            # The in_process call simulate a remote call by encoding
            # and decoding the parameters with JSON. So, although everything
            # is done locally (without actually calling a server), it
            # behaves much more like an actual remote call.

            # With a direct call
            wrapped_func = jsonFuncWrapper(decorated_func)
            # decorated_func = wrapped_func.__dict__['__original_func']

            # we get the decorated function

            mainlog.debug("in_process_call : func dict is {}".format(wrapped_func.__dict__))
            mainlog.debug("in_process_call : decorated_func is {}".format(decorated_func))

            if not hasattr(decorated_func, '_original_func'):
                raise Exception("Seems like the function youre calling was not annotated as a json server one")

            # We simulate the encoding/decoding so that it's very close to the
            # http mode

            # First we simulate encoding/decoding of the request's parameters
            #         func.__prototype = inspect.getargspec(func.__original_func).args[1:]

            # if isinstance(decorated_func, RollbackDecorator):
            #     mainlog.debug("Seeing through RollbackDecorator")
            #     mainlog.debug(decorated_func.func)
            #     param_names = inspect.getargspec(decorated_func.func)[0][1:] # Skip self parameter
            # else:
            #     param_names = inspect.getargspec(decorated_func)[0][1:] # Skip self parameter

            param_names = decorated_func._prototype
            json_params = dict(zip(param_names, args))

            # mainlog.debug("In process JSON args = {}".format(args))
            # mainlog.debug("In process JSON params = {} as {}".format(json_params, type(json_params)))

            json_params = horse_json_encoder.encode(json_params).encode('utf-8')
            mainlog.debug("In process ENCODED JSON params = {} as {}".format(json_params, type(json_params)))

            json_params = loads(json_params.decode('utf-8'), object_hook=json_object_hook)
            mainlog.debug("In process DECODED JSON params = {} as {}".format(json_params, type(json_params)))


            raw_data = wrapped_func(the_self, **json_params)
            mainlog.debug("AAA Function returned raw data : {}".format( str(raw_data)))

            # Then encoding/decoding of response

            data = horse_json_encoder.encode(raw_data).encode('utf-8')
            mainlog.debug("Encoded as : {}".format(data))

            res = loads(data.decode('utf-8'), object_hook=json_object_hook)
            mainlog.debug("Decoded as {}".format(str(res)))
            return res


        def http_call(decorated_func, *args):
            chrono_start("http_call")

            if not hasattr(decorated_func, '_original_func'): #'__original_func'):
                raise Exception("Seems like the function you are calling was not annotated as a json server one")

            mainlog.debug("http_call : decorated func is {}".format(decorated_func))

            original_func = decorated_func._original_func


            endpoint_name = "{}.{}".format(self.service.__class__.__name__,
                                           original_func.__name__)

            mainlog.debug("http_call : endpoint name is {}".format(endpoint_name))
            # Get param list, then remove 'self'
            param_names = inspect.getfullargspec(original_func).args[1:]

            rpc_data = dict()
            rpc_data['jsonrpc'] = '2.0'
            rpc_data['method'] = endpoint_name
            rpc_data['params'] = dict(zip(param_names, args))
            rpc_data['id'] = '123'

            params = urlencode(rpc_data)
            headers = {"Content-type": "application/json"}

            server_address = urlparse( configuration.get("DownloadSite","base_url"))
            mainlog.debug("http_call to : {}://{}:{}".format(server_address.scheme, server_address.hostname, server_address.port))

            if server_address.scheme == 'https':
                c = HTTPSConnection(server_address.hostname,server_address.port)
            else:
                c = HTTPConnection(server_address.hostname,server_address.port)

            try:
                params = horse_json_encoder.encode(rpc_data).encode('utf-8')
                # print(params)
                c.request("POST", "/json_rpc2", params, headers)
            except socket.error as err:
                raise ServerException(err.errno, err.strerror)

            response = c.getresponse()
            mainlog.debug("HTTP Response : {} {}".format(response.status, response.reason))

            data = response.read()
            mainlog.debug("Response from server")
            mainlog.debug(data)

            # I use the object hook to build objects instead of dicts
            res = loads(data.decode('utf-8'), object_hook=json_object_hook)

            chrono_click("End of http_call")
            if 'result' in res:
                return res['result']
            elif 'error' in res:
                mainlog.error("Method not found on the server : {}".format(endpoint_name))
                raise ServerException(res['error'])
            else:
                raise Exception("Can't read server's answer : {}".format(res['error']))


        def wrapper(*args, **kwargs):
            decorated_func = getattr(self.service, name)

            mainlog.debug("wrapper calling {} -> {} in mode {}".format(name, decorated_func, self.mode))
            if self.mode == JsonCallWrapper.HTTP_MODE:
                # That's the over-the-network call
                # See http://stackoverflow.com/questions/218616/getting-method-parameter-names-in-python
                return http_call(decorated_func, *args)
            elif self.mode == JsonCallWrapper.IN_PROCESS_MODE:
                # That's the direct call
                # server_call_result = decorated_func(*args, **kwargs)
                return in_process_call(decorated_func, self.service, *args)
            elif self.mode == JsonCallWrapper.CHERRYPY_MODE:
                return cherrypy_call(decorated_func, *args, **kwargs)

            elif self.mode == JsonCallWrapper.DIRECT_MODE:
                return direct_call(decorated_func, *args, **kwargs)

        return wrapper


class HorseJsonRpc(JsonRpc):
    # Normally, the error codes are deduced from the exception type.
    # JSON-RPC does that by binding each exception to an error code.
    # Since there are thousands of error codes available (and I can't
    # make that many exception types), I can map each of
    # the errors onto a JSON RPC error code. To achieve that, I patch
    # the JsonRpc class a bit.

    # See jsonrpc2 __init__.py to see what this patch actually does.

    def __init__(self):

        # We'll only handle the ServerException correctly (i.e.
        # with proper error codes and messages.

        # If the exception is not handled, then JsonRpc2 module will do this
        #    'error':{'code': self.get_app_error_code(e),
        #             'message': str(e),
        #             'data': json.dumps(e.args)}


        super(HorseJsonRpc, self).__init__(application_errors={ServerException : ServerException.JSON_CODE})

    def get_app_error_code(self, exc):
        if hasattr(exc,'code'):
            return exc.code
        else:
            super(HorseJsonRpc, self).get_app_error_code(exc)

#global JSonServer_wrapping_active
#JSonServer_wrapping_active = []
# JSonServer_wrapping_active[0] = 'AZE'
if __name__ == '__main__':
    global JSonServer_wrapping_active
    JSonServer_wrapping_active[0] = 'KONGO'
# print("The test {}".format(JSonServer_wrapping_active))

if __name__ == '__main__':

    #global JSonServer_wrapping_active

    from koi.base_logging import mainlog,init_logging
    from koi.Configurator import init_i18n,load_configuration,configuration

    init_logging()
    init_i18n()
    load_configuration()

    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session

    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)

    from PySide.QtGui import QApplication
    app = QApplication(sys.argv)


    print("1. ---///--- {}".format(JSonServer_wrapping_active))
    JSonServer_wrapping_active[0] = False
    print("2. ---///--- {}".format(JSonServer_wrapping_active))


    # from koi.clock_service import ClockService


#     # t = JsonCallWrapper( ClockService())
#     t = ClockService()

#     print("LAST ---///--- {}".format(JSonServer_wrapping_active))
#     t.get_person_activity(16)

#     from datetime import timedelta

#     start_date = date.today() + timedelta(-360)

#     print(t.get_person_data(16, start_date))
#     print(len(t.get_person_data(16, start_date).picture_data)) # 16, 100

#     try:
#         t.get_person_data(-1)
#         print("------------")
#         assert False
#     except ServerException as ex:
#         print("------------***************")
#         print(ex)
#     except Exception as ex:
#         print(type(ex))
#         print(type(ServerException(10,'jjj')))
#         exit()


#     chrono_click()
