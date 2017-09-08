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

import json
from pprint import pprint

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
from koi.datalayer.DeclEnumP3 import DeclEnumType
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import ColumnProperty, joinedload

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

import sqlalchemy

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
        print( relation.mapper.class_)
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

from datetime import datetime
import zlib
from time import time

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





