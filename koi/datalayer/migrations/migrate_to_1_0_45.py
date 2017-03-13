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
from db_mapping import OrderStatusType,OrderPartStateType,OrderPart,Order,DeliverySlip,DeliverySlipPart


init_db_session(configuration.database_url.replace('horse_clt','horse_adm'), metadata, False or configuration.echo_query)

from dao import dao

def alter_structure():
    session().connection().execute("ALTER TABLE horse.employees ADD COLUMN is_active BOOLEAN not null default true;")


def alter_data():

    mainlog.info("Setting employee is_active flag")

    session().connection().execute("""
update horse.employees
set is_active = (roles is not null) or (select count(*) from horse.timetracks where employee_id = horse.employees.employee_id and start_time > date '2013-11-01') > 0;""")

    session().commit()


alter_structure()
alter_data()
