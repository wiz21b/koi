from datetime import date
from sqlalchemy.sql import select,func,and_,or_

from koi.base_logging import mainlog,init_logging
from Configurator import init_i18n,load_configuration,configuration,resource_dir
init_logging()
init_i18n()
load_configuration()

from db_mapping import metadata
from datalayer.database_session import init_db_session

from datalayer.database_session import session
from db_mapping import OrderStatusType,OrderPartStateType,OrderPart,Order,DeliverySlip,DeliverySlipPart


init_db_session(configuration.database_url.replace('horse_clt','horse_clt'), metadata, False or configuration.echo_query)

from dao import dao

def alter_structure():
    pass

def alter_data():

    q = session().query(OrderPart).filter(and_(OrderPart.state == OrderPartStateType.completed,
                                               OrderPart.completed_date == None)).all()

    mainlog.info("Updating {} completed records".format(len(q)))

    for part in q:
        part.completed_date = part.order.completed_date

    q = session().query(OrderPart).filter(and_(OrderPart.state == OrderPartStateType.aborted,
                                               OrderPart.completed_date == None)).all()

    mainlog.info("Updating {} aborted records".format(len(q)))

    for part in q:
        part.completed_date = part.order.completed_date

    session().commit()


alter_structure()
alter_data()
