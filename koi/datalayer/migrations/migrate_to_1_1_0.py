from datetime import date
import argparse
from sqlalchemy.sql import select,func,and_,or_

from koi.base_logging import mainlog,init_logging
from koi.Configurator import init_i18n,load_configuration,configuration,resource_dir
init_logging()
init_i18n()
load_configuration()

from koi.db_mapping import metadata
from koi.datalayer.database_session import init_db_session,db_engine,session
from koi.datalayer.supplier_mapping import Supplier
from koi.datalayer.supply_order_mapping import SupplyOrderPart,SupplyOrder

from koi.doc_manager.documents_mapping import *

parser = argparse.ArgumentParser(description='This is an Horse! migration script.')
parser.add_argument('--db-url', default=configuration.database_url, help='Database connection URL {}'.format(configuration.database_url))




def alter_structure():

    documents_orders_table.drop(db_engine(), checkfirst=True)
    documents_order_parts_table.drop(db_engine(), checkfirst=True)
    TemplateDocument.__table__.drop(db_engine(), checkfirst=True)
    Document.__table__.drop(db_engine(), checkfirst=True)

    Document.__table__.create()
    TemplateDocument.__table__.create()
    documents_orders_table.create()
    documents_order_parts_table.create()

    session().connection().execute("GRANT ALL ON horse.documents TO horse_clt")
    session().connection().execute("GRANT ALL ON horse.template_documents TO horse_clt")
    session().connection().execute("GRANT ALL ON horse.documents_orders TO horse_clt")
    session().connection().execute("GRANT ALL ON horse.documents_order_parts TO horse_clt")

    # FIXME No idea why we have that sequence
    session().connection().execute("GRANT ALL ON SEQUENCE horse.documents_document_id_seq TO horse_clt")
    session().commit()

    # Bug fix
    session().connection().execute("GRANT ALL ON horse.filter_queries TO horse_clt ;")

def alter_data():
    # For the moment I skip this because I think that adding a role that is not
    # supported by the user session might lock people out of Horse
    return

    from koi.datalayer.employee_mapping import Employee,RoleType

    q = session().query(Employee).filter(Employee.roles != None).all()
    for employee in q:
        if RoleType.modify_parameters in employee.roles and RoleType.modify_document_templates not in employee.roles:
            mainlog.info(employee)

            # The roles attributes is not easy to work with :-(
            r = employee.roles
            r.add(RoleType.modify_document_templates)
            employee.roles = r

    session().commit()



args = parser.parse_args()
init_db_session(args.db_url, metadata, True or configuration.echo_query)
from koi.dao import dao
alter_structure()
alter_data()
print("Done")
