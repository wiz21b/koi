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

    pass

def alter_data():
    from koi.datalayer.employee_mapping import Employee,RoleType

    q = session().query(Employee).filter(Employee.roles != None).all()
    for employee in q:
        if RoleType.timetrack_modify in employee.roles and RoleType.view_timetrack not in employee.roles:
            mainlog.info(employee)

            # The roles attributes is not easy to work with :-(
            r = employee.roles
            r.add(RoleType.view_timetrack)
            employee.roles = r

    session().commit()



args = parser.parse_args()
init_db_session(args.db_url, metadata, True or configuration.echo_query)
from koi.dao import dao
alter_structure()
alter_data()
print("Done")
