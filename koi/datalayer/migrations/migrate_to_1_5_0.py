from datetime import date
import argparse
from sqlalchemy.sql import select,func,and_,or_

from koi.base_logging import mainlog,init_logging
from koi.Configurator import init_i18n,load_configuration,configuration,resource_dir
init_logging()
init_i18n()
load_configuration("server.cfg")

from koi.db_mapping import metadata
from koi.datalayer.database_session import init_db_session,db_engine,session

from koi.people_admin.people_admin_mapping import *

parser = argparse.ArgumentParser(description='This is an Horse! migration script.')
parser.add_argument('--db-url', default=configuration.database_url, help='Database connection URL {}'.format(configuration.database_url))

from sqlalchemy import create_engine
from sqlalchemy.schema import CreateTable
def dump(sql, *multiparams, **params):
    print(sql.compile(dialect=engine.dialect))
engine = create_engine('postgresql://', strategy='mock', executor=dump)
# print(CreateTable(Operation.__table__).compile(engine))


def alter_structure():

    session().connection().execute("ALTER TABLE horse.order_parts ADD COLUMN priority INTEGER NOT NULL DEFAULT 1")
    session().connection().execute("ALTER TABLE horse.order_parts ADD CONSTRAINT valid_priority CHECK (priority IN (1,2,3,4,5))")
    session().commit()

def alter_data():
    pass


args = parser.parse_args()
init_db_session(args.db_url, metadata, True or configuration.echo_query)

alter_structure()
alter_data()
print("Done")
