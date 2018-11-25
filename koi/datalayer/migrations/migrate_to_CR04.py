from koi.datalayer.migrations.migration_base import *
from koi.datalayer.database_session import init_db_session,db_engine,session

init_base()

from koi.db_mapping import OrderPart, id_generator
from koi.config_mgmt.mapping import *

def drop_column( c):

    try:
        session().connection().execute("ALTER TABLE {} DROP COLUMN document_category_id".format(doc_tn))
        session().commit()
    except Exception as ex:
        mainlog.exception(ex)
        session().rollback()


def alter_structure():

    # python -m koi.datalayer.migrations.migrate_to_CR04

    order_parts_tn = full_table_name(OrderPart)
    configuration_tn = full_table_name(Configuration)

    try:
        session().connection().execute("ALTER TABLE {} DROP configuration_id".format(order_parts_tn))
        session().commit()
    except Exception as ex:
        session().rollback()

    try:
        session().connection().execute("ALTER TABLE {} DROP CONSTRAINT fk_configuration".format(order_parts_tn))
        session().commit()
    except Exception as ex:
        session().rollback()

    drop_entity( db_engine, session, ConfigurationLine)
    drop_entity( db_engine, session, ImpactLine)
    drop_entity( db_engine, session, Configuration)
    drop_entity( db_engine, session, ArticleConfiguration)

    # It's here because it was not in the horse schema (but in the public)
    id_generator.create(checkfirst=True)

    create_entity( session, ArticleConfiguration)
    create_entity( session, Configuration)
    create_entity( session, ImpactLine)
    create_entity( session, ConfigurationLine)


    # By default added columns are nullable
    session().connection().execute("ALTER TABLE {} ADD configuration_id INTEGER".format(order_parts_tn))
    session().connection().execute("ALTER TABLE {} ADD CONSTRAINT fk_configuration FOREIGN KEY(configuration_id) REFERENCES {} (configuration_id)".format(order_parts_tn, configuration_tn))
    session().commit()

def alter_data():
    pass

alter_structure()
alter_data()
