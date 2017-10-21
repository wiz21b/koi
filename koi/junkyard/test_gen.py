"""
Make recursive QtModel
----------------------

QRecursiveModel( proto, { 'parts' : QModelParts} )

class QRecursiveModel(QModel):
   def __init__( self, proto, submodels_to_proto):
      self.protorype = proto
      self.rows = []
      for submodel, proto in submodels_to_proto:

   def data(ndx):
      getattr( self.rows[ndx.row()],
               self.protoype[ndx.column()].name)

   def build_rows( self, objs):

      for i in range(len(objs)):
         self.rows[i] = objs[i]
         self.submodels_rows[i] = self.submodels_type( getattr( objs[i], objs.REL_NAME) )


Lazy or not lazy:
----------------

From server to client, it is quite possible that lazy eavaluation is not needed.
(except special case of pictures and other binary blobs)



"""

from datetime import datetime
import zlib
from time import time
import json
from pprint import pprint
import logging

from koi.base_logging import init_logging, mainlog
init_logging()

from koi.Configurator import init_i18n,load_configuration,configuration
init_i18n()
load_configuration()

from koi.db_mapping import metadata
from koi.datalayer.database_session import init_db_session

init_db_session(configuration.database_url, metadata, False or configuration.echo_query)

from koi.datalayer.database_session import session
from koi.db_mapping import Employee, FilterQuery, Order, OrderPart, Customer, ProductionFile, Operation
from koi.datalayer.employee_mapping import RoleType
from koi.datalayer.DeclEnumP3 import DeclEnumType
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import ColumnProperty, joinedload

from koi.junkyard.instrumentation import InstrumentedObject, InstrumentedRelation

import sqlalchemy

mainlog.setLevel( logging.DEBUG)

def _attribute_analysis( model):
    mainlog.debug("Analysing model {}".format(model))


    # print("-"*80)
    # for prop in inspect(model).iterate_properties:
    #     if isinstance(prop, ColumnProperty):
    #         print( type(prop.columns[0].type))
    #         print( type( inspect( getattr(model, prop.key))))

    # Warning ! Some column properties are read only !
    fnames = [prop.key for prop in inspect(model).iterate_properties
              if isinstance(prop, ColumnProperty)]

    ftypes = dict()
    for fname in fnames:
        t = inspect( getattr(model, fname)).type
        # print( type( inspect( getattr(model, fname)).type))
        ftypes[fname] = type(t)

    #print(ftypes)
    single_rnames = []
    rnames = dict()
    for key, relation in inspect(model).relationships.items():
        # print( relation.mapper.class_)
        # print( relation.argument.class_)
        if relation.uselist == False:
            single_rnames.append(key)
        else:
            rnames[key] = relation.mapper.class_

    # Order is important to rebuild composite keys (I think, not tested so far.
    # See SQLA comment for query.get operation :
    # http://docs.sqlalchemy.org/en/rel_1_0/orm/query.html#sqlalchemy.orm.query.Query.get )
    knames = [key.name for key in inspect(model).primary_key]

    mainlog.debug(
        "For model {}, I have these attributes : primary keys={}, fields={}, realtionships={} (single: {})".format(
            model, knames, fnames, rnames, single_rnames))

    return ( ftypes, rnames, single_rnames, knames)



class SqlaSession:

    def __init__(self, db_session):
        self._db_session = db_session
        self._model_analysis = dict()

    def _analyse_model(self, model):
        # Caching for performance
        if model not in self._model_analysis:
            self._model_analysis[model] = _attribute_analysis(model)
        return self._model_analysis[model]


    def copy_fields(self, org, dest, model):
        fnames, rnames, single_rnames, knames = self._analyse_model(model)
        for fname in fnames:
            setattr( dest, fname, getattr( org, fname))

    def save_object(self, llobj):

        model = llobj._model()
        fnames, rnames, single_rnames, knames = self._analyse_model( model)

        key_field = getattr( model, knames[0])
        key_value = getattr( llobj, knames[0])
        sqla_obj = self._db_session.query(model).filter(key_field == key_value).first()

        if not sqla_obj:
            sqla_obj = model()
            self._db_session.add(sqla_obj)

        self.copy_fields(llobj, sqla_obj, model)

    def load_object(self, klass, pk_field, pk_value):

        mainlog.debug("Loading object from SQL")
        obj = self._db_session.query(klass).filter( pk_field == pk_value).one()
        fnames, rnames, single_rnames, knames = self._analyse_model(klass)

        llo = LazyLoad( rnames, self, klass)
        self.copy_fields( obj, llo, klass)
        llo.clear_changes()

        self._db_session.commit()
        return llo

    def load_relationship(self, llobj, rel_field):

        fnames, rnames, single_rnames, knames = self._analyse_model( llobj._model)

        relation = getattr( llobj._model, rel_field)
        key_field = getattr(llobj._model, knames[0])
        key_value = getattr(llobj, knames[0])
        relation_model = rnames[rel_field]

        # We load the relationship in a joined load on the
        # parent entity.

        mainlog.debug("Loading relationship from SQL")
        res = self._db_session.query(llobj._model).filter( key_field == key_value).options(
            joinedload(relation)).one()

        instru = InstrumentedRelation()

        for rel_obj in getattr( res, rel_field):
            llo = LazyLoad(rnames, self, relation_model)
            self.copy_fields(rel_obj, llo, relation_model)
            llo.clear_changes()
            instru.append(llo)

        self._db_session.commit()
        return instru


class LazyLoad:
    def __init__(self, relations, session, model):

        self._session = session
        self._model = model

        fnames, rnames, single_rnames, knames = session._analyse_model( model)


        # relations says if a relationship is loaded or not
        self._relations = dict.fromkeys( rnames)

        self._iobj = InstrumentedObject()
        self._iobj.init_fields( list(fnames.keys()) + list(rnames.keys()))

    def __getattr__(self, item):
        if item in self._relations and not self._relations[item]:
            setattr( self._iobj, item, self._session.load_relationship(self, item))
            self._relations[item] = True
        return getattr( self._iobj, item)


class OrderLL(LazyLoad):
    def __init__(self):
        super().__init__( [ 'parts' ] )


sqla_session = SqlaSession( session())
o = sqla_session.load_object( Order, Order.order_id, 5255)

# print(o)
# print(o.state)
# print(o.parts)

# exit()

serialized = """{
    "fullname": "Daniel Dumont",
    "picture_data": null,
    "_roles": "modify_document_templates,modify_monthly_time_track_correction,modify_parameters,timetrack_modify,view_audit,view_financial_information,view_prices,view_timetrack",
    "employee_id": 114,
    "filter_queries": [
        {
            "family": "order_parts_overview",
            "filter_query_id": 1,
            "owner": 114,
            "name": "Finies ce mois",
            "shared": true,
            "query": "CompletionDate in CurrentMonth"
        },
        {
            "family": "order_parts_overview",
            "filter_query_id": 2,
            "owner": 114,
            "name": "Finies mois passe",
            "shared": true,
            "query": "CompletionDate in MonthBefore"
        },
        {
            "family": "order_parts_overview",
            "filter_query_id": 3,
            "owner": 114,
            "name": "En production",
            "shared": true,
            "query": "Status = ready_for_production"
        },
        {
            "family": "order_parts_overview",
            "filter_query_id": 4,
            "owner": 114,
            "name": "Devis",
            "shared": true,
            "query": "Status = preorder"
        },
        {
            "family": "order_parts_overview",
            "filter_query_id": 5,
            "owner": 114,
            "name": "Dormantes",
            "shared": true,
            "query": "Status = production_paused"
        },
        {
            "family": "order_parts_overview",
            "filter_query_id": 6,
            "owner": 114,
            "name": "offres en cours lachaussee",
            "shared": true,
            "query": "Status = preorder and client = lachaussee"
        },
        {
            "family": "order_parts_overview",
            "filter_query_id": 11,
            "owner": 114,
            "name": "suivi production 0.6 54321",
            "shared": false,
            "query": "Status = ready_for_production AND DoneHours > 0.6*PlannedHours"
        },
        {
            "family": "order_parts_overview",
            "owner": 114,
            "name": "ABNSOLUTELY TOTALLY NEW",
            "shared": false,
            "query": "Status = ready_for_production AND DoneHours > 0.9*PlannedHours"
        }
    ],
    "login": "dd",
    "is_active": true
}"""



def make_func_name( class_):
    return "dict_of_strings_to_object".format(class_.__name__)

def none_or_x(x, fun):
    if x is None:
        return None
    else:
        return fun(x)


def converter_str_to_sqla_type(ftype):
    cvrt = "lambda x : x"
    if ftype == sqlalchemy.sql.sqltypes.String:
        cvrt = "str"
    elif ftype == sqlalchemy.sql.sqltypes.Boolean:
        cvrt =  "lambda x : x not in ('False','false',0)"
    elif ftype == sqlalchemy.sql.sqltypes.Integer:
        cvrt =  "int"

    return "(lambda p : none_or_x(p,{}))".format(cvrt)

from sqlalchemy import Table, Column, Integer, String, Float, MetaData, ForeignKey, Date, DateTime, Sequence, Boolean, LargeBinary, Binary, Index, Numeric

class TypeSupport:
    pass

class SQLATypeSupport(TypeSupport):
    def __init__(self, sqla_model):
        self._model = sqla_model
        self.fnames, self.rnames, self.single_rnames, self.knames = _attribute_analysis( self._model)

        fields = dict()
        for f, t in self.fnames.items():
            #print("{} {}".format(f,t))
            if t == String:
                fields[f] = str
            elif isinstance(t, Integer):
                fields[f] = int
        self._fields = fields

    def base_type(self):
        return self._model

    def type_name(self):
        return self._model.__name__

    def make_instance_code(self):
        return "{}()".format( self.type_name())

    def fields(self):
        return self._fields.keys()

    def relations(self):
        return self.rnames

    def field_type(self, field_name):
        return self._fields[field_name]

    def field_read_code(self, repr, field_name):
        return "{}.{}".format(repr, field_name)

    def relation_read_code(self, expression, relation_name):
        return "{}.{}.iterator()".format(expression, relation_name)

    def relation_write_code(self, expression, relation_name, source_walker):
        return "{}.{} = map( serialize_relation_from_{}, {})".format( "zzz",relation_name, source_walker.type_name(), expression)

    def write_serializer_to_self_head(self, source, out_lines):
        #return
        out_lines.append("def serialize( source : {}, dest : {}):".format(  source.type_name(), self.type_name()))


    def write_serializer_to_self_tail(self, source, out_lines):
        pass


    def write_serializer_to_self_field(self, source_walker, field_name, out_lines):
        c = cast(source_walker.field_type(field_name), None)
        expr = "d.{}={}".format(field_name, c.format(source_walker.field_read_code("source", field_name)))
        out_lines.append("    {}".format(expr))


    def write_serializer_to_self_relation(self, source_walker, relation_name, out_lines):
        expr = "d.{}={}".format(relation_name,
                                self.relation_write_code(
                                    source_walker.relation_read_code("source", relation_name),
                                    relation_name,
                                    source_walker))
        out_lines.append("    {}".format(expr))

    def gen_write_field(self, instance, field, value):
        return "{}.{} = {}".format( instance, field, value)

    def gen_basetype_to_type_conversion(self, field, code):
        return "( {})".format(code)

    def gen_read_field(self, instance, field):
        return "{}.{}".format(instance, field)

    def gen_type_to_basetype_conversion(self, field, code):
        return code

    def gen_init_relation(self, instance_name, relation_name):
        return ""

    def gen_read_relation( self, instance, relation_name):
        return "{}.{}".format(instance, relation_name)


class DictTypeSupport(TypeSupport):
    def __init__(self):
        self._lines=[]

    def base_type(self):
        return dict

    def type_name(self):
        return "dict"

    def fields(self):
        return []

    def relations(self):
        return []

    def field_type(self, field_name):
        return str

    def make_instance_code(self):
        return "{}()".format( self.type_name())

    def field_read_code(self, expression, field_name):
        """ Generates a piece of code to access the field
        named filed_name from an expression of type
        dict.
        """
        return "{}['{}']".format(expression, field_name)

    def relation_read_code(self, expression, relation_name):
        return "{}['{}'].iterator()".format(expression, relation_name)

    def add_line(self, line):
        self._lines.append(line)

    def write_serializer_to_self_head(self, source, out_lines):
        """ Creates a function that will read a source
        object and serializes its content to a dict.

        :param source:
        :return:
        """

        #out_lines.append("def serialize_relationship_from_dict(d : dict)")
        out_lines.append("def serialize( source : {}, dest : {}):".format(  source.type_name(), self.type_name()))
        #out_lines.append("    d = dict()")

    def write_serializer_to_self_tail(self, source, out_lines):
        out_lines.append("    return d")

    def write_serializer_to_self_field(self, source_walker, field_name, out_lines):
        c = cast(source_walker.field_type(field_name), None)
        print(c)
        expr = "d['{}']={}".format( field_name, c.format(source_walker.field_read_code( "source",  field_name)))
        out_lines.append("    {}".format(expr))


    def write_serializer_to_self_relation(self, source_walker, relation_name, out_lines):
        expr = "d['{}']={}".format(relation_name, source_walker.relation_read_code("source", relation_name))
        out_lines.append("    {}".format(expr))

    def gen_write_field(self, instance, field, value):
        return "{}['{}'] = {}".format(instance, field, value)

    def gen_basetype_to_type_conversion(self, field, code):
        return "( {})".format( code)


    def gen_read_field(self, instance, field):
        return "{}['{}']".format(instance, field)


    def gen_type_to_basetype_conversion(self, field, code):
        return "( {})".format(code)


    def gen_init_relation(self, instance_name, relation_name):
        return "{}['{}'] = []".format(instance_name, relation_name)

    def gen_read_relation(self, instance, relation_name):
        return "{}['{}']".format(instance, relation_name)


def cast( source_type = None, dest_type = None):
    print("Casting {} -> {}".format( source_type, dest_type))

    if dest_type == None and source_type == str:
        return "{}"

print("///////////////////////////////////////")


class TypeSupportFactory:
    def __init__(self):
        self.type_supports = dict()

    def register_type_support(self, ts):
        self.type_supports[ts.base_type()] = ts

    def make_type_support(self, base_type):
        raise NotImplementedError()

    def serializer_dest_type_name(self, base_type):
        raise NotImplementedError()

    def serializer_source_type_name(self, base_type):
        raise NotImplementedError()

    def get_type_support(self, base_type):
        if base_type not in self.type_supports:
            mainlog.debug("Creating a new type support for {}".format(base_type))
            self.make_type_support(base_type)

        return self.type_supports[base_type]


class SQLAFactory(TypeSupportFactory):
    def __init__(self):
        super().__init__()

    def make_type_support(self, base_type):
        mainlog.debug("Making SQLAType support for {}".format(base_type))
        self.type_supports[base_type] = SQLATypeSupport(base_type)

    def serializer_source_type_name(self, base_type : TypeSupport):
        return str( base_type.__class__.__name__)

    def serializer_dest_type_name(self, base_type : TypeSupport):
        return str( base_type.__class__.__name__)

class DictFactory(TypeSupportFactory):
    def __init__(self):
        super().__init__()

    def make_type_support(self, base_type):
        mainlog.debug("Making DictTypeSupport support for {}".format(base_type))
        self.type_supports[base_type] = DictTypeSupport()

    def serializer_source_type_name(self, base_type):
        return "dict"

    def serializer_dest_type_name(self, base_type):
        return "dict"



SKIP = "!skip"


class CodeWriter:
    def __init__(self):
        self._code = [] # array of string
        self._indentation = 0

    def indent_right(self):
        self._indentation += 1


    def indent_left(self):
        self._indentation -= 1

        if len(self._code) >= 1 and self._code[-1]:
            self._code.append("")

    def append_blank(self):
        self._code.append("")

    def append_code(self, lines):
        if type(lines) == str:
            lines = [lines]
        elif type(lines) == list:
            pass
        else:
            raise Exception("Unexpected data")

        for line in lines:
            self._code.append("    " * self._indentation + line)


    def generated_code(self):
        return "\n".join(self._code)

class Serializer:
    def __init__(self, name, code_fragment):
        self.name, self.code_fragment = name, code_fragment


class SQLAWalker:

    def __init__(self, source_factory : TypeSupportFactory, dest_factory : TypeSupportFactory):
        self.source_factory = source_factory
        self.dest_factory = dest_factory
        self.serializers = {}

        self.fragments = []

    def gen_type_to_basetype_conversion(self, source_type, base_type):
        if source_type == String and base_type == str:
            return "{}".format

    def proto_serializer(self, walked_type_name,
                        source_type_support_factory : TypeSupportFactory,
                        dest_type_support_factory : TypeSupportFactory,
                        source_type,
                        dest_type,
                        cw : CodeWriter):

        n = self.name_serializer(walked_type_name,
                        source_type_support_factory,
                        dest_type_support_factory,
                        source_type,
                        dest_type)

        cw.append_code("def {}( source, dest = None):".format(n))
        cw.indent_right()
        cw.append_code(    "if dest is None:")
        cw.indent_right()
        cw.append_code(        "dest = {}".format( dest_type.make_instance_code()))
        cw.indent_left()
        cw.indent_left()

        return n

    def name_serializer(self, walked_type_name,
                        source_type_support_factory : TypeSupportFactory,
                        dest_type_support_factory : TypeSupportFactory,
                        source_type,
                        dest_type):
        return "serialize_{}_{}_to_{}".format(
            walked_type_name,
            source_type_support_factory.serializer_source_type_name(source_type),
            dest_type_support_factory.serializer_dest_type_name(dest_type))


    def walk(self, start_type, base_type, dest_type, relations_control = {}):

        """ Walks the structure dictated by the type encapsulated in this walker.
        Build a serializer that will gets its data from the source type
        and stores them in the destination type.
        The type encapsulated in this walker can therefore be different
        than the source type and destination type (that's unlikely though).

        :param source_type_support:
        :param dest_type_support:
        :return:
        """

        fields_to_skip = []
        fields_to_add = []
        cw = CodeWriter()

        print("{} of type {}".format(start_type,TypeSupport))
        if isinstance(start_type,TypeSupport):
            source_type_support = start_type
            start_type = source_type_support.base_type()
        else:
            source_type_support = self.source_factory.get_type_support(start_type)


        if isinstance(dest_type,TypeSupport):
            default_dest_type_support = dest_type
        else:
            default_dest_type_support = self.dest_factory.get_type_support(start_type)


        fields, relations, single_rnames, knames = _attribute_analysis(base_type)

        fields_tm = dict()
        for f, t in fields.items():
            # print("{} {}".format(f, t))
            if t == String:
                fields_tm[f] = str
            elif isinstance(t, Integer):
                fields_tm[f] = int

        fields_names = fields.keys()
        relations_names = relations

        source_instance = "source"
        dest_instance = "dest"


        serializer_func_name = self.proto_serializer( base_type.__name__,
            self.source_factory,
            self.dest_factory,
            source_type_support,
            default_dest_type_support,
            cw)

        print("Registereing serializer {} {}".format(source_type_support, serializer_func_name))

        self.serializers[ (source_type_support,base_type) ] = Serializer(serializer_func_name,cw)

        cw.indent_right()

        for field in sorted(list(fields_names) + fields_to_add):
            if field in fields_to_skip:
                continue

            read_field_code = source_type_support.gen_read_field
            conversion_out_code = source_type_support.gen_type_to_basetype_conversion
            conversion_in_code = default_dest_type_support.gen_basetype_to_type_conversion
            write_field_code = default_dest_type_support.gen_write_field

            field_transfer = \
                write_field_code(
                    dest_instance,
                    field,
                    conversion_in_code(
                        field,
                        conversion_out_code(
                            field,
                            read_field_code( source_instance, field))))

            cw.append_code(field_transfer)

        # Relation :
        # Create object or update object ?
        # for relation_name in relations_names:
        #     dest_type_support.write_serializer_to_self_relation(source_type_support, relation_name, lines)
        #     dest_type_support.write_serializer_to_self_tail(source_type_support, lines)


        def gen_copy_to_relation( source_relation_access_code,
                                  dest_relation_access_code,
                                  create_or_load_instance_code,
                                  serializer_code,
                                  cw : CodeWriter):
            cw.append_code("for item in {}:".format(source_relation_access_code))
            cw.indent_right()
            cw.append_code(    "d = {}".format(create_or_load_instance_code))

            cw.append_code(    "{}.append( {})".format(
                dest_relation_access_code,
                serializer_code('item')))
            cw.indent_left()
            return

        AUTO="!auto"

        rel_to_walk = relations_names.copy()

        for k, v in relations_control.items():
            rel_to_walk[k] = v

        # if hasattr(source_type_support, "relations_control"):
        #     for k,v in source_type_support.relations_control.items():
        #         rel_to_walk[k] = v

        for relation_name, relation in rel_to_walk.items():

            if relation == SKIP:
                cw.append_blank()
                cw.append_code('# Skipping relation {}'.format(relation_name))
                continue

            destination_type_support = default_dest_type_support

            mainlog.debug("Relation to check {}".format(relation))
            if hasattr(relation,"__mapper__"):
                mainlog.debug("Checking SQLA relationship {}".format(relation))
                rel_type_support = self.source_factory.get_type_support(relation)  # relation in the walked structure
            elif isinstance(relation, TypeSupport):
                rel_type_support = relation
            elif type(relation) == tuple:
                rel_type_support, destination_type_support = relation
            else:
                raise Exception("Unsupported type {}".format(relation))

            assert isinstance( rel_type_support, TypeSupport), "Wrong type {}".format(rel_type_support)

            create_or_load_instance_code = destination_type_support.make_instance_code()
            read_rel_code = source_type_support.gen_read_relation( source_instance, relation_name)

            if rel_type_support not in self.serializers:
                raise Exception("While producing code to handle relation \"{}.{}\", I need a serializer that reads from {} and converts to {}".format(
                    base_type.__name__,
                    relation_name,
                    rel_type_support.base_type(),
                    destination_type_support.base_type()
                ))

            serialize_code = "{}({{}}, d)".format(
                self.serializers[ (rel_type_support, ]) ].name ).format
                # self.name_serializer( relation_name,
                #                       self.source_factory,
                #                       self.dest_factory,
                #                       rel_type_support,
                #                       rel_type_support)).format
            write_rel_code = destination_type_support.gen_read_relation( dest_instance, relation_name)
            init_dest_relation = destination_type_support.gen_init_relation( dest_instance, relation_name)

            cw.append_blank()
            cw.append_code( init_dest_relation)
            # Comment aller chercher le bon serializer ???
            gen_copy_to_relation( read_rel_code,
                                  write_rel_code,
                                  create_or_load_instance_code,
                                  serialize_code,
                                  cw)

        cw.append_code("return dest")
        cw.indent_left()

        self.fragments.append(cw)

        return

    def generated_code(self):
        lines = ""
        for f in self.fragments:
            lines += f.generated_code()
            lines += "\n"
        return lines



"""
when I walk the structure, I need to know the conversions that apply.
the conversions are dictated by a overall strategy such as dict to SQLA entities
so the walker needs to know the overall strategy.
so the walker cannot be reduced to a source type and a destination type
because in the relations of the source type lie other types.

The walker walks the relationships.
Thus for each of them, it must know the appropriate source
type and destination type.
A relation (i.e. a list) of instances of source type will be serializsed.
Thererefore, the walker must know :
- the relation name in the source type
- the relation instance's type in the source type
- the serializer able to read the relation instance's type
- the serializer able to write the destination type

So to walk A.rel of type X
into dest type

the walker must know "rel", "type of rel", "dest type"



"""

from koi.datalayer.sqla_mapping_base import Base
from sqlalchemy.ext.declarative import DeclarativeMeta

class EmployeeTypeSupport(SQLATypeSupport):

    def __init__(self):
        super().__init__(Employee)

    def gen_type_to_basetype_conversion(self, field, code):
        if field == "roles":
            return "','.join([ r.name for r in {} ])".format(code)
        else:
            return code


class RoleTypeSupport(SQLATypeSupport):

    def __init__(self):
        super().__init__(Employee)


class ShortenedOperationSupport(SQLATypeSupport):
    def __init__(self):
        super().__init__(Operation)

    def gen_type_to_basetype_conversion(self, field, code):
        if field == 'value':
            return "float({})".format(code)
        else:
            return code

    relations_control = {"tasks": SKIP}

shortened_operation_support = ShortenedOperationSupport()

class ShortenedOrderPart(SQLATypeSupport):
    def __init__(self):
        super().__init__(OrderPart)

    relations_control = { "operations" : shortened_operation_support,
                          "delivery_slip_parts" : SKIP,
                          "production_file" : SKIP }


    def gen_type_to_basetype_conversion(self, field_name, field_access_code):
        """ Transform a field value into its representation
        in one of the fundamental python type"""
        if field_name in ('sell_price', 'total_sell_price'):
            return "float({})".format(field_access_code)
        elif field_name == "state":
            return "({}).value".format(field_access_code)
        else:
            return field_access_code


# dict -> QtObject
# dict -> SQLA object


#src_factory = SQLAFactory()
#dest_factory = SQLAFactory()
# src_factory = SQLAFactory()
# src_factory.register_type_support( EmployeeTypeSupport())
# dest_factory = DictFactory()


# for name, model in Base._decl_class_registry.items():
#     if not name.startswith("_sa_"):
#         w.walk(model, src_factory, dest_factory)




# w.walk(FilterQuery,
#        src_factory,
#        dest_factory)
#
#
# w.walk(Employee,
#        src_factory,
#        dest_factory,
#        fields_to_skip=["password"],
#        fields_to_add=["roles"])



"""
Si je veux optimiser le cahrgement d'un graphe SQLA.
Je commence par optimiser la requête.
Vu le fonctionnement du walker, cette requête devra forcémet
garder une structure de graphe comparable à celle de la
"declarative base" de SQLA.
Si ce n'est pas le cas, le SQLAWalker n'est d'aucune utilité.
Dans ce cas il faudrait par ex. un SQLAQueryResultWalker.
Mais le problèmes est alors : où va-t-on trouver le schema
des données ? Donc le principe du alker ne marche que quand
on connait le schema *a priori*.
On peut peut-être le tordre pour que ça marhe malgré tout.
À suivre...
"""

shortened_order_part = ShortenedOrderPart()

sqla_factory = SQLAFactory()
sqla_factory.register_type_support( shortened_operation_support)
sqla_factory.register_type_support( shortened_order_part)

dict_factory = DictFactory()
dict_ts = DictTypeSupport()

w = SQLAWalker( dict_factory, sqla_factory)
w.walk( dict_ts, Operation, shortened_operation_support, relations_control = { "tasks" : SKIP })

w.walk( dict_ts, OrderPart, shortened_order_part, relations_control = {"delivery_slip_parts" : SKIP,
                                                                     "production_file" : SKIP,
                                                                     "operations" : (dict_ts, Operation, shortened_operation_support)})
print(w.generated_code())



# duality problem : in OrderPArt I talk about the type support.
# But in the Operation, I juste make a serializer.
# Which one should we base everything on ?

w = SQLAWalker(SQLAFactory(), DictFactory())
w.walk(shortened_operation_support)
w.walk(ShortenedOrderPart())
# w.walk(Order,
#        relations_control={"tasks":SKIP})

print(" -"*80)
print(w.generated_code())

with open("test.py","w") as fout:
    fout.write("# Generated {}\n\n".format( datetime.now()))
    fout.write(w.generated_code())

import test

# exec( compile(w.generated_code(), "<string>", "exec"))

order = session().query(Order).filter(Order.order_id == 5255).one()  # 5266

pprint( test.serialize_OrderPart_ShortenedOrderPart_to_dict( order.parts[0]))

# w.walk(Employee,
#        DictFactory(),
#        DictFactory())

# w.walk(type_supports[dict],
#        type_supports[Employee])
#
# w.walk(type_supports[Employee],
#        type_supports[dict])

exit()

def walk( source_walker, dest_walker):
    if dest_walker.fields():
        fields_names = dest_walker.fields()
    elif source_walker.fields():
        fields_names = source_walker.fields()
    else:
        raise Exception("Neither Source or destination announce fields to share !")

    if dest_walker.relations():
        relations_names = dest_walker.relations()
    elif source_walker.relations():
        relations_names = source_walker.relations()
    else:
        raise Exception("Neither Source or destination announce relations to share !")


    lines = []
    dest_walker.write_serializer_to_self_head(source_walker, lines)
    for field in fields_names:
        dest_walker.write_serializer_to_self_field( source_walker, field, lines)
    for relation_name in relations_names:
        dest_walker.write_serializer_to_self_relation( source_walker, relation_name, lines)
    dest_walker.write_serializer_to_self_tail( source_walker, lines)
    print("\n".join(lines))

sqla_walker = SQLATypeSupport(Employee)
dict_walker = DictTypeSupport()
walk(dict_walker, sqla_walker)
#walk(sqla_walker, dict_walker)
exit()

def generate_DTO( the_klass, excludes = [], extra_fields=[]):
    fnames, rnames, single_rnames, knames = _attribute_analysis(the_klass)

    lines = []

    def pl(s = ""):
        lines.append(s)

    pl("class {}DTO:".format(the_klass.__name__))

    pl("    # ------------------------------------------------------------------")
    pl("    @classmethod")
    pl("    def sqla_to_dict(self, sqla):".format( make_func_name(the_klass)))
    pl("        d = dict()")

    for fname,ftype in fnames.items():
        print(ftype)
        if ftype == sqlalchemy.sql.sqltypes.Date:
            pl("        d['{}'] = none_or_x(sqla.{}, str)".format(fname,fname))
        elif ftype == DeclEnumType:
            pl("        d['{}'] = none_or_x(sqla.{}, str)".format(fname,fname))
        else:
            pl("        d['{}'] = none_or_x(sqla.{}, lambda k:k)".format(fname,fname))

    for rname,rtype in rnames.items():
        if rname not in excludes:
            pl("        d['{}'] = []".format(rname))
            pl("        for x in sqla.{}:".format(rname))
            pl("            d['{}'].append( {}DTO.sqla_to_dict( x))".format(rname,rtype.__name__))

    pl("        return d")

    pl("    # ------------------------------------------------------------------")

    pl("    def dict_of_strings_to_object(self, d):".format( make_func_name(the_klass)))
    pl("        # Copies a dict of string to a regular object, applying \n" +
       "        # conversions to strings")

    for fname,ftype in fnames.items():
        cvrt = "lambda x : x"
        if ftype == sqlalchemy.sql.sqltypes.String:
            cvrt = "str"
        elif ftype == sqlalchemy.sql.sqltypes.Boolean:
            cvrt =  "lambda x : x not in ('False','false',0)"
        elif ftype == sqlalchemy.sql.sqltypes.Integer:
            cvrt =  "int"

        pl("        self.{} = none_or_x({},{})".format(fname,
                                           "d['{}']".format(fname), cvrt))

    for rname,rtype in rnames.items():
        if rname not in excludes:
            pl("        self.{} = []".format(rname))
            pl("        r = d['{}']".format(rname))
            pl("        for i in range(len(r)):".format(rname))
            pl("            x = {}DTO()".format(rtype.__name__))
            pl("            x.{}( r[i])".format(make_func_name(rtype)))
            pl("            self.{}.append( x)".format(rname))


    pl("    # ------------------------------------------------------------------")
    pl("    def __init__(self):".format( make_func_name(the_klass)))

    for fname,ftype in fnames.items():
        pl("        self.{} = None".format(fname))

    if extra_fields:
        pl("        # extra fields")
        for fname in extra_fields:
            pl("        self.{} = None".format(fname))

    for rname,rtype in rnames.items():
        if rname not in excludes:
            pl("        self.{} = []".format(rname))

    return "\n".join(lines)



def generate_QtDTO( the_klass, excludes = [], extra_fields=[]):
    fnames, rnames, single_rnames, knames = _attribute_analysis(the_klass)

    lines = []

    def pl(s = ""):
        lines.append(s)

    pl("class {}SqlaDTO:".format(the_klass.__name__))


    # pl("    def load_from_dict(self,d):")
    # for fname,ftype in fnames.items():
    #     pl("        self.{} = {}(d['{}'])".format(fname, converter_str_to_sqla_type(ftype), fname))
    # for rname, rtype in rnames.items():
    #     if rname not in excludes:
    #         pl("        self._{} = -1".format(rname))


    pl("    def __init__(self):".format( make_func_name(the_klass)))
    for fname,ftype in fnames.items():
        pl("        self.{} = None".format(fname))

    for rname, rtype in rnames.items():
        if rname not in excludes:
            pl("        self._{} = -1".format(rname))

    for rname, rtype in rnames.items():
        if rname not in excludes:
            pl("    @property".format(rname))
            pl("    def {}(self):".format(rname))
            pl("        if self._{} == -1:".format(rname))
            pl("            res = session().query({0}).filter( {0}.{1} == self.{1}).options(joinedload({0}.{2})).one().{2}".format(
                the_klass.__name__, knames[0], rname))

            pl("            self._{} = []".format(rname))
            pl("            for i in range(len(res)):".format(rname))
            pl("                x = {}SqlaDTO()".format(rtype.__name__))
            pl("                x.load( res[i])".format())
            pl("                self._{}.append( x)".format(rname))
            pl("                session().commit()")
            pl("        return self._{}".format(rname))
            pl()


    # ------------------------------------------------------------------------------

    # Primary key or an object
    pl("    def load(self, primary_key_value):")
    pl("        if not isinstance( primary_key_value,{}):".format(the_klass.__name__))
    pl("            res = session().query({0}).filter( {0}.{1} == primary_key_value).one()".format(the_klass.__name__, knames[0]))
    pl("            commit = True")
    pl("        else:")
    pl("            res = primary_key_value")
    pl("            commit = False")

    for fname,ftype in fnames.items():
        pl("        self.{} = res.{}".format(fname,fname))

    for rname,rtype in rnames.items():
        pl("        self._{} = -1".format(rname))

    pl("        if commit:")
    pl("            session().commit()")


    pl("    # ------------------------------------------------------------------")

    # The whole problem here is to make sure we just serialize the changes
    # that occured on the Qt DTO. If we don't do that, we might trigger
    # a load of all the object's relationship when we save.

    # Therefore, from a lazy loading problem, we inherit a lazy writing
    # one... That translates to write only what needs to be xritten.
    # Which also is a problem of knowing what to delete.
    # So we basically reimplement SQLAlchemy UnitOfWork pattern...

    pl("    def to_dict(self):".format( make_func_name(the_klass)))
    pl("        d = dict()")

    for fname,ftype in fnames.items():
        print(ftype)
        if ftype == sqlalchemy.sql.sqltypes.Date:
            pl("        d['{}'] = none_or_x(self.{}, str)".format(fname,fname))
        elif ftype == DeclEnumType:
            pl("        d['{}'] = none_or_x(self.{}, str)".format(fname,fname))
        else:
            pl("        d['{}'] = none_or_x(self.{}, lambda k:k)".format(fname,fname))

    for rname,rtype in rnames.items():
        if rname not in excludes:
            pl("        d['{}'] = []".format(rname))
            pl("        for x in self.{}:".format(rname))
            pl("            d['{}'].append( x.to_dict())".format(rname,rtype.__name__))

    pl("        return d")


    return "\n".join(lines)


class QtDTO:

    def load(self, klass_name, key_attribute_name, key_value):
        # FIXME key_attrivute_name should be removed and found
        # by inspection

        sqla_model = inspect( globals()[klass_name])
        key_attribute = getattr( sqla_model, key_attribute_name)
        res = session().query(sqla_model).filter( key_attribute == key_value).one()

    def load_relationship(self, rel_klass, rel_key_attribute, parent_key_value):
        # For lazy loading only
        sqla_dto_name = "{}DTO".format(rel_klass.__name__)
        qt_dto_name = "{}QtDTO".format(rel_klass.__name__)
        res = session().query(rel_klass).filter(rel_key_attribute == parent_key_value).all()
        a = []
        for x in res:
            d = sqla_dto_name.sqla_to_dict(x)
            a.append( type( qt_dto_name).load_from_dict( d))
        session().commit()
        return a


class Proto:

    def __init__(self):
        self._simple_attr = None
        self._simple_attr_old = None

    @property
    def simple_attr(self):
        return self._simple_attr

    def to_dict(self):
        d = dict()
        if self._simple_attr != self._simple_attr_old:
            d['simple_attr'] = self._simple_attr


    def save(self):
        d = self.to_dict()
        if d:
            send(d)


from sqlalchemy.orm import RelationshipProperty

"""
mon but est de retrouver la bonne clef à utiliser dans la
classe enfant pour faire le filtre pour retrouver ses instances
filles du parent.
"""
print( inspect(Employee).relationships['filter_queries'])
print( inspect(Employee).relationships['filter_queries'].mapper)

target = inspect(Employee).relationships['filter_queries'].mapper

r = inspect(Employee).relationships['filter_queries']

print( inspect(Employee).relationships['filter_queries'].mapper.class_) # -> FilterQuery class
print( inspect(FilterQuery).relationships['owner'].mapper.class_) # -> Employee class
# ... so we can find that in an Employee one refers to a FilterQuery
# But still, no owner id...


print( FilterQuery.__table__.c.owner_id.foreign_keys)
print("**")

def find_reverse(sqla_source_attr):
    print("Analyzing {}.{}".format(sqla_source_attr.parent.class_.__name__, sqla_source_attr.key))

    # ATTENTION The following code make several assumptions such as
    # - Primary keys are made of exactly one column
    # - Foreign keys are made of exactly one column
    # - There's only one foreign key per entity to another entity

    target_class = sqla_source_attr.mapper.class_
    primary_key = inspect(sqla_source_attr).primary_key[0] # a Column object

    # For the relation to work, the target class must have
    # a foreign key to the source class (so no we don't look
    # the relationships)

    for key, a in inspect(target_class).column_attrs.items():
        foreign_keys = a.columns[0].foreign_keys

        # We locate the foriegn keys in the target class
        if foreign_keys:
            target_c = [fk for fk in foreign_keys][0].column

            # And then we look for a foreign key that refers to
            # the source entity.
            if primary_key == target_c:
                print("{}.{} (exactly {})".format(target_class.__name__, key, a))
                return (a.columns[0], primary_key)


#print(find_reverse(Employee.filter_queries))
print("////")

# for key, a in inspect(Employee).column_attrs.items():
#     if set(a.columns) == set(inspect(Employee).primary_key):
#         print(a)

relation = Employee.filter_queries
source_entity = relation.parent.class_
target_entity = relation.mapper.class_

target_foreign_keys = set()

# Which column in the trget_entity do point to the
# source entity ?

for key, a in inspect(FilterQuery).columns.items():

    # Looking for relationships is useless because
    # relationships don't give any information on the attribute
    # to join against (so we cannot build the query)
    # So our job is to find the attribute (not the column!)
    # in the target entity (in the target entity because they
    # have their own names there, it's not enough to just read the
    # source primary key)
    # which are FK's to the source. However, finding those
    # attributes is not enough. There may be a given FK present
    # more than once, which is ambiguous. SQLA has various way
    # to solve that ambiguity but I have no time right now
    # to use them.
    # We'reb basically reproducing som e SQLA functionality which
    # consists of automatically finding the matching foreign keys
    # of a relationship

    for fk in a.foreign_keys:
        # Look for the foreign key in our source entity
        ref = fk.get_referent(inspect(source_entity).mapped_table) # returns a Column
        if ref is not None:
            # The foreign key points to the source entity, so we're interested
            p = inspect(source_entity).get_property_by_column(fk.column)
            print("# {}.{} -> {}.{}".format(target_entity.__name__, a.name, source_entity.__name__, ref.name))

            if p not in target_foreign_keys:
                target_foreign_keys.add(p)
            else:
                raise Exception("The foreign key is already used once.So there is an ambiguity. FIXME more code needed here")

print(target_foreign_keys)
print("----")

# Find reverse 2, best version
def find_reverse(sqla_source_attr):
    for skey, sa in inspect(Employee).relationships.items():
        print(sa.parent.class_)
        print(sa.key)
        target_class = sa.mapper.class_
        primary_key = inspect(Employee).primary_key[0]

        print("Employee.{} --> {}".format(key, target_class.__name__))

        for key, a in inspect(target_class).column_attrs.items():
            foreign_keys = a.columns[0].foreign_keys
            if foreign_keys:
                target_c = [fk for fk in foreign_keys][0].column
                if primary_key == target_c:
                    print("  {}.{} ->  {}.{}".format(Employee.__name__, primary_key.key, target_class.__name__, key))



    # for key,a in inspect(FilterQuery).column_attrs.items():
    #     if a.columns[0].foreign_keys:
    #         print("FilterQuery.{} is a foreign key, but to what ?".format(key))
    #         target_c = [fk for fk in a.columns[0].foreign_keys][0].column
    #         print("to {}. But is it our table ?".format(target_c))
    #
    #         for key, a in inspect(Employee).column_attrs.items():
    #             if a.columns[0] == target_c:
    #                 print("it is the Employee table => Employee.{}".format(key))


qtdto = QtDTO()
# qtdto.load_relationship( FilterQuery, FilterQuery.owner_id, 12)

code = generate_QtDTO(Employee)
print(code)
exec(code)

code = generate_QtDTO(FilterQuery)
print(code)
exec(code)

fq = FilterQuerySqlaDTO()
e = EmployeeSqlaDTO()
e.load(114)
pprint(e.to_dict())
pprint(e.filter_queries[0].to_dict())


code = generate_QtDTO(Order, excludes=['tasks','documents'])
print(code)
exec(code)
code = generate_QtDTO(OrderPart, excludes=['quality_events','delivery_slip_parts','documents'])
exec(code)
code = generate_QtDTO(ProductionFile, excludes=[])
exec(code)
code = generate_QtDTO(Operation, excludes=['tasks'])
exec(code)

order = OrderSqlaDTO()


print("----------------------------------------------")
t = time()
order.load(5255)
delta = time() - t
print(order.order_id)
print(" {}".format(delta))
pprint( order.parts[0].to_dict())
delta = time() - t
print(" {}".format(delta))

exit()

order_dto = OrderDTO()


for i in range(5):
    print()
    session().expunge_all()
    t = time()
    order = session().query(Order).filter(Order.order_id == 5255).one() # 5266
    s = 0
    for i in range(len(order.parts)):
        s += len(order.parts[i].operations)
        if(len(order.parts[i].operations) > 0):
            z = order.parts[i].operations[0].description

    delta = time() - t
    print( "SQLA  {}, {} operations".format(delta,s))

    marsh = OrderDTO.sqla_to_dict(order)
    delta = time() - t
    print( "Marsh {}".format(delta))

    compressed = zlib.compress( bytes(json.dumps(marsh),"UTF-8"))
    s = json.loads( str( zlib.decompress( compressed),encoding="UTF-8"))
    order_dto.dict_of_strings_to_object(s)

    print(order_dto.parts[0].production_file[0].operations[0].description)
    delta = time() - t
    print("Json  {}, {} compressed bytes".format(delta, len(compressed)))

exit()



employee = session().query(Employee).filter(Employee.employee_id == 114).one()

#e = Employee()
#fq = FilterQuery()
#e.filter_queries.append(fq)
#print(e.filter_queries)
#d = json.loads(serialized)
#print(e.login)


d = EmployeeDTO.sqla_to_dict(employee)
pprint(d)
EmployeeDTO().dict_of_strings_to_object( d )





