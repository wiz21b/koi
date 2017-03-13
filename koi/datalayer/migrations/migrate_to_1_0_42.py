from datetime import date
from sqlalchemy.sql import select,func,and_,or_

from Logging import mainlog,init_logging
from Configurator import init_i18n,load_configuration,configuration,resource_dir
init_logging()
init_i18n()
load_configuration()

from db_mapping import metadata
from datalayer.database_session import init_db_session

from datalayer.database_session import session
from db_mapping import Employee,RoleType


init_db_session(configuration.database_url, metadata, False or configuration.echo_query)

from dao import dao

def alter_structure():
    pass

def alter_data():

    q = session().query(Employee).filter(Employee.roles != None).all()

    mainlog.info("Updating {} records".format(len(q)))

    for employee in q:
        if len(employee.roles) > 0:
            mainlog.info(employee)

            # The roles attributes is not easy to work with :-(
            r = employee.roles
            r.add(RoleType.view_prices)
            employee.roles = r

    session().commit()


alter_structure()
alter_data()
