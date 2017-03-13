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
    try:
        session().connection().execute("ALTER TABLE horse.template_documents DROP COLUMN reference")
        session().connection().execute("ALTER TABLE horse.template_documents DROP COLUMN language")
    except Exception as ex:
        session().rollback()

    session().connection().execute("ALTER TABLE horse.template_documents ADD COLUMN reference VARCHAR NOT NULL DEFAULT ''")
    session().connection().execute("ALTER TABLE horse.template_documents ADD COLUMN language VARCHAR NOT NULL DEFAULT ''")
    session().commit()

def alter_data():
    pass


args = parser.parse_args()
init_db_session(args.db_url, metadata, True or configuration.echo_query)

alter_structure()
alter_data()
print("Done")


from koi.doc_manager.server_setup import register_horse_template_offline
import koi.reporting.order_confirmation.order_confirmation_report2
register_horse_template_offline(_("Order confirmation letter template"),
                                "order_confirmation_report_PL.docx",
                                koi.reporting.order_confirmation.order_confirmation_report2.HORSE_REFERENCE)
