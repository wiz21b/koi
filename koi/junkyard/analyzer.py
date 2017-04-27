from sqlalchemy.orm.properties import ColumnProperty
from sqlalchemy.types import NullType
from sqlalchemy.inspection import inspect
from sqlalchemy.orm.collections import InstrumentedList, InstrumentedSet, InstrumentedDict

from koi.base_logging import mainlog

attribute_analysis_cache = dict()

def attribute_analysis(model):
    global attribute_analysis_cache

    if model not in attribute_analysis_cache:
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

        mainlog.debug("For model {}, I have these attributes : keys={}, fields={}".format(model, knames, fnames))

        attribute_analysis_cache[model] = (fnames, rnames, single_rnames, knames)

    return attribute_analysis_cache[model]


from koi.Configurator import init_i18n
init_i18n()

from koi.base_logging import init_logging, mainlog
init_logging()

from koi.Configurator import init_i18n,load_configuration,configuration
init_i18n()
load_configuration()

from koi.db_mapping import metadata
from koi.datalayer.database_session import init_db_session

init_db_session(configuration.database_url, metadata, False or configuration.echo_query)


from koi.db_mapping import OrderPart

model = OrderPart
fnames, rnames, single_rnames, knames = attribute_analysis(model)

print("def obj_to_dict( obj, d):")
for n in fnames:

    col_type = type(getattr(model, n).property.columns[0].type)

    # datetime.strftime( obj.{}, "%Y-%m-%dT%H:%M:%S.%f" )

    if col_type != NullType:
        print("    d['{}'] = str(obj.{})  # {}".format(n, n, col_type))
    else:
        print("    # {} : Can't serialize {}".format(n, col_type))


for n in knames:
    print("    d['{}'] = obj.{} # Key".format(n,n))



print("def dict_to_sqla_obj( d : dict) -> object:")
for n in fnames:

    col_type = type(getattr(model, n).property.columns[0].type)
    print("    obj.{} = d['{}']  # {}".format(n, n, col_type))
