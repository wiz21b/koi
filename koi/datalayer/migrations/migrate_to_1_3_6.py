from datetime import date
import argparse
from sqlalchemy.sql import select,func,and_,or_

from koi.base_logging import mainlog,init_logging
from koi.Configurator import init_i18n,load_configuration,configuration,resource_dir
init_logging()
init_i18n()
load_configuration("server.cfg")

from koi.db_mapping import metadata, Operation
from koi.datalayer.database_session import init_db_session,db_engine,session
from koi.machine.machine_mapping import *

parser = argparse.ArgumentParser(description='This is an Horse! migration script.')
parser.add_argument('--db-url', default=configuration.database_url, help='Database connection URL {}'.format(configuration.database_url))

from sqlalchemy import create_engine
from sqlalchemy.schema import CreateTable
def dump(sql, *multiparams, **params):
    print(sql.compile(dialect=engine.dialect))
engine = create_engine('postgresql://', strategy='mock', executor=dump)
# print(CreateTable(Operation.__table__).compile(engine))


def alter_structure():

    try:
        session().connection().execute("ALTER TABLE horse.machines DROP COLUMN clock_zone")
    except Exception as ex:
        session().rollback()

    session().connection().execute("ALTER TABLE horse.machines ADD clock_zone VARCHAR(10)")
    
    # Commit necessary, else the next drop table hangs ad infinitum
    session().commit()


def alter_data():

    # Fraisage numerique
    session().connection().execute("UPDATE horse.machines SET clock_zone='Zone 1' WHERE horse.machines.operation_definition_id = 9")

    # Tournage
    session().connection().execute("UPDATE horse.machines SET clock_zone='Zone 2' WHERE horse.machines.operation_definition_id in (8,18)")

    # Rectification
    session().connection().execute("UPDATE horse.machines SET clock_zone='Zone 3' WHERE horse.machines.operation_definition_id in (13,14)")

    # Others stay at NULL
    
    session().commit()
    
    pass


args = parser.parse_args()
init_db_session(args.db_url, metadata, True or configuration.echo_query)

alter_structure()
alter_data()
print("Done")
