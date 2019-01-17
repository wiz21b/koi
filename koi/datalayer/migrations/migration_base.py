import logging
import argparse
from sqlalchemy.ext.declarative.api import DeclarativeMeta
from sqlalchemy import Sequence, Table


from koi.datalayer.SQLAEnum import EnumSymbol, DeclEnum, DeclEnumMeta
from koi.base_logging import mainlog,init_logging
from koi.Configurator import init_i18n,load_configuration,configuration
from koi.datalayer.database_session import init_db_session, DATABASE_SCHEMA


def full_entity_name(entity_class):
    if isinstance( entity_class, Table) or isinstance( entity_class, Sequence):
        return "{}.{}".format(DATABASE_SCHEMA, entity_class.name)
    else:
        return "{}.{}".format(DATABASE_SCHEMA, entity_class.__tablename__)

def drop_entity( db_engine, session, entity):

    if isinstance(entity, DeclarativeMeta):
        drop_entity(db_engine, session, entity.__table__)

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
            mainlog.error("Could not : DROP TYPE {}".format(entity.db_name()))
            session().rollback()

    else:
        raise Exception("Unrecognized entity type : {}".format(type(entity)))
    session().commit()


def create_entity( session, entity):

    if isinstance(entity, Table):
        entity.create(checkfirst=True)
        session().connection().execute("GRANT SELECT,INSERT,UPDATE,DELETE ON {} TO horse_clt".format(full_entity_name(entity)))
        session().commit()

    elif isinstance(entity, Sequence):
        entity.create(checkfirst=True)
        session().connection().execute("GRANT SELECT,UPDATE ON {} TO horse_clt".format(full_entity_name(entity)))
        session().commit()

    elif isinstance(entity, DeclEnumMeta):
        entity.create(checkfirst=True)
        session().commit()

    elif isinstance(entity, DeclarativeMeta):
        create_entity( session, entity.__table__)

    else:
        raise Exception("Unrecognized entity type")


def dump(engine, sql, *multiparams, **params):
    print(sql.compile(dialect=engine.dialect))

def extend_enumeration(db_engine, enumeration : DeclEnum, symbol : EnumSymbol):

    # The following statement really wants to run outside of a transaction.
    # SO I have to use the raw_connection stuff to escape SQLA's autoamted
    # transaction management.

    # See enumeration type information
    # select enumtypid, typname, enumlabel from pg_enum join pg_type on pg_type.oid = pg_enum.enumtypid order by enumtypid, enumlabel;

    c = db_engine().raw_connection()
    cursor = c.cursor()
    cursor.execute("COMMIT") # Leave any pending transaction
    try:
        # Will fail on duplicates
        sql = "ALTER TYPE {} ADD VALUE '{}'".format(enumeration.db_type().impl.name, symbol.value)
        cursor.execute(sql)
    except Exception as ex:
        mainlog.info("Tried " + sql)
        mainlog.error(ex)
    cursor.close()
    c.close()



def init_base():
    init_logging()
    mainlog.setLevel(logging.INFO)
    configuration.load_server_configuration()

    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description='This is an Horse! migration script.',
                                     epilog="For example --db-url {}".format(
                                         configuration.get("Database", "admin_url")))

    parser.add_argument('--db-url', default=configuration.get('Database','admin_url'),
                        help='Database URL')
    args = parser.parse_args()

    mainlog.info("Connecting to {}".format(args.db_url))
    init_i18n()
    from koi.db_mapping import metadata
    init_db_session(args.db_url, metadata, False)  # True or configuration.echo_query)
