# python -m src.datalayer.migrations.migrate_to_1_11_0
import os.path
from datetime import date
import argparse
from sqlalchemy.sql import select,func,and_,or_
from koi.datalayer.sqla_mapping_base import DATABASE_SCHEMA

from koi.base_logging import mainlog,init_logging
from koi.Configurator import init_i18n,load_configuration,configuration,resource_dir
init_logging()
init_i18n()
load_configuration("server.cfg")

from koi.db_mapping import metadata
from koi.datalayer.database_session import init_db_session,db_engine,session

from koi.doc_manager.documents_mapping import *
from koi.datalayer.quality import QualityEvent, QualityEventType
from koi.user_mgmt.user_role_mapping import UserClass

parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                 description='This is an Horse! migration script.',
                                 epilog="For example --db-url {}".format(configuration.get("Database","admin_url")))

parser.add_argument('--db-url', default=configuration.database_url, help='Database URL')

from sqlalchemy import create_engine
from sqlalchemy.schema import CreateTable
def dump(sql, *multiparams, **params):
    print(sql.compile(dialect=engine.dialect))
engine = create_engine('postgresql://', strategy='mock', executor=dump)
# print(CreateTable(Operation.__table__).compile(engine))

def full_table_name(entity_class):
    if isinstance( entity_class, Table):
        return "{}.{}".format(DATABASE_SCHEMA, entity_class.name)
    else:
        return "{}.{}".format(DATABASE_SCHEMA, entity_class.__tablename__)

from koi.datalayer.SQLAEnum import DeclEnumMeta

def create_entity(entity):

    if isinstance(entity, DeclarativeMeta):
        create_entity(entity.__table__)

    elif isinstance(entity, Table):
        entity.create()
        session().connection().execute("GRANT SELECT,INSERT,UPDATE,DELETE ON {} TO horse_clt".format(full_table_name(entity)))
        session().commit()

    else:
        raise Exception("Unrecognized entity type")

    session().commit()

from sqlalchemy.ext.declarative.api import DeclarativeMeta

def drop_entity(entity):

    if isinstance(entity, DeclarativeMeta):
        drop_entity(entity.__table__)

    elif isinstance(entity, Table):
        entity.drop(db_engine(), checkfirst=True)
        session().commit()

    elif isinstance(entity, DeclEnumMeta):
        entity.db_type().drop( bind=db_engine(), checkfirst=True)

        try:
            session().connection().execute("DROP TYPE IF EXISTS {}".format(entity.db_name()))
            session().commit()
        except Exception as ex:
            mainlog.exception(ex)
            mainlog.error("Could not : DROP TYPE  horse.ck_quality_event_type")
            session().rollback()

    else:
        raise Exception("Unrecognized entity type : {}".format(type(entity)))
    session().commit()

from koi.datalayer.SQLAEnum import EnumSymbol, DeclEnum

def extend_enumeration(enumeration : DeclEnum, symbol : EnumSymbol):

    # The following statement really wants to run outside of a transaction.
    # SO I have to use the raw_connection stuff to escape SQLA's autoamted
    # transaction management.

    # See enumeration type information
    # select enumtypid, typname, enumlabel from pg_enum join pg_type on pg_type.oid = pg_enum.enumtypid order by enumtypid, enumlabel;

    c = db_engine().raw_connection()
    cursor = c.cursor()
    cursor.execute("COMMIT") # Leave any pending transaction
    try:
        sql = "ALTER TYPE {} ADD VALUE '{}'".format(enumeration.db_type().impl.name, symbol.value)
        mainlog.debug(" /// " + sql)
        cursor.execute(sql)
    except Exception as ex:
        print(ex)
    cursor.close()
    c.close()



def alter_structure():

    ftn = full_table_name(DocumentCategory)
    doc_tn = full_table_name(Document)

    try:
        session().connection().execute("ALTER TABLE {} DROP CONSTRAINT fk_category".format(doc_tn))
        session().commit()
    except Exception as ex:
        mainlog.exception(ex)
        session().rollback()

    try:
        session().connection().execute("ALTER TABLE {} DROP COLUMN document_category_id".format(doc_tn))
        session().commit()
    except Exception as ex:
        mainlog.exception(ex)
        session().rollback()

    documents_quality_events_table.drop(db_engine(), checkfirst=True)
    session().commit()

    drop_entity(DocumentCategory)
    drop_entity(QualityEvent)
    drop_entity(UserClass)
    drop_entity(QualityEventType)

    # Creations...


    create_entity(DocumentCategory)
    session().connection().execute("ALTER TABLE {} ADD document_category_id INTEGER".format(doc_tn))
    session().connection().execute("ALTER TABLE {} ADD CONSTRAINT fk_category FOREIGN KEY(document_category_id) REFERENCES {} (document_category_id)".format(doc_tn,ftn))


    # Quality
    create_entity(QualityEvent)

    # Autoincrement implies a sequence. SQLA chooses the name of that sequence.
    session().connection().execute("GRANT USAGE, SELECT, UPDATE ON SEQUENCE horse.quality_events_quality_event_id_seq TO horse_clt")

    create_entity(documents_quality_events_table)

    from koi.db_mapping import OrderPartStateType
    extend_enumeration(OrderPartStateType, OrderPartStateType.non_conform)

    create_entity(UserClass)
    # Autoincrement implies a sequence. SQLA chooses the name of that sequence.
    session().connection().execute("GRANT USAGE, SELECT, UPDATE ON SEQUENCE horse.user_classes_user_class_id_seq TO horse_clt")

    # Fix a database issue
    session().connection().execute("GRANT SELECT,INSERT,UPDATE,DELETE ON {} TO horse_clt".format(doc_tn))
    session().commit()

    session().commit()
    
    
def alter_data():

    c = DocumentCategory()
    c.full_name = "Qualité"
    c.short_name = "Qual."
    session().add(c)
    session().commit()

    c = DocumentCategory()
    c.full_name = "Sales"
    c.short_name = "Sale"
    session().add(c)
    session().commit()

    c = DocumentCategory()
    c.full_name = "Production"
    c.short_name = "Prod"
    session().add(c)
    session().commit()



args = parser.parse_args()
init_db_session(args.db_url, metadata, True or configuration.echo_query)

alter_structure()
alter_data()
print("Done")

