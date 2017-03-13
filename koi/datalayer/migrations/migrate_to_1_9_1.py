import os.path
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
parser.add_argument('--db-url', default=configuration.database_url, help='Database connection URL {}'.format(configuration.get("Database","admin_url")))

from sqlalchemy import create_engine
from sqlalchemy.schema import CreateTable
def dump(sql, *multiparams, **params):
    print(sql.compile(dialect=engine.dialect))
engine = create_engine('postgresql://', strategy='mock', executor=dump)
# print(CreateTable(Operation.__table__).compile(engine))


def alter_structure():
    # DROP not null constraint on reference

    session().connection().execute("alter table horse.template_documents alter column reference set default NULL")
    session().connection().execute("alter table horse.template_documents alter column reference drop not null")
    session().commit()
    session().connection().execute("update horse.template_documents set reference = NULL where reference = ''")
    session().connection().execute("alter table horse.template_documents add unique(reference)")
    session().commit()


def alter_data():
    pass


args = parser.parse_args()
init_db_session(args.db_url, metadata, True or configuration.echo_query)

alter_structure()
alter_data()
print("Done")


from koi.doc_manager.server_setup import register_module
import koi.reporting.preorder.preorder_report as report
register_module(report)

