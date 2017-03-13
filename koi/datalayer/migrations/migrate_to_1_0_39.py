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
    session().connection().execute("CREATE TYPE horse.ck_order_part_state_type AS ENUM ('preorder','aborted','completed','definition','production_paused','ready_for_production');")

    session().connection().execute("ALTER TABLE horse.order_parts ADD COLUMN state horse.ck_order_part_state_type;")

    # -- The idea is to set parts' states to match the order's state

    session().connection().execute("""UPDATE horse.order_parts
    SET state = (CASE
                    WHEN orders.state = 'preorder_definition' THEN CAST('preorder' AS horse.ck_order_part_state_type)
                    WHEN orders.state = 'order_completed' THEN CAST('completed' AS horse.ck_order_part_state_type)
                    WHEN orders.state = 'order_aborted' THEN CAST('aborted' AS horse.ck_order_part_state_type)
                    WHEN orders.state = 'order_definition' THEN CAST('ready_for_production' AS horse.ck_order_part_state_type)
                    WHEN orders.state = 'order_production_paused' THEN CAST('production_paused' AS horse.ck_order_part_state_type)
                    WHEN orders.state = 'order_ready_for_production' THEN CAST('ready_for_production' AS horse.ck_order_part_state_type)
                    ELSE CAST('ready_for_production' AS horse.ck_order_part_state_type)
                 END)
    FROM horse.orders WHERE orders.order_id = order_parts.order_id;
    """)

    session().connection().execute("ALTER TABLE horse.order_parts ALTER COLUMN state SET NOT NULL;")
    session().connection().execute("ALTER TABLE horse.order_parts ADD COLUMN completed_date DATE;")

    session().connection().execute("""UPDATE horse.order_parts
    SET completed_date = orders.completed_date
    FROM horse.orders WHERE orders.order_id = order_parts.order_id;""")

    session().connection().execute("CREATE INDEX parts_state_idx ON horse.order_parts (state);")


def alter_data():

    mainlog.info("Terminating the old indirect order")

    old_indirects = dao.order_dao.find_by_accounting_label(1)
    old_indirects.state = OrderStatusType.order_completed
    old_indirects.completed_date = date(2010,1,1)
    session().commit()

    mainlog.info("Reset everything to allow for multiple runs")

    session().query(OrderPart).update( { OrderPart.state: OrderPartStateType.preorder, 
                                         OrderPart.completed_date:None} )

    parts = session().query(OrderPart,Order.state,Order.creation_date).join(Order).\
            filter(and_( Order.completed_date == None, 
                         Order.state.in_([OrderStatusType.order_completed,OrderStatusType.order_aborted]))).\
            all()

    mainlog.info("Setting completed/aborted orders without date. Updating {} records".format(len(parts)))

    for part,order_state,creation_date in parts:
        part.state = OrderPartStateType.state_from_order_state(order_state)
        part.completed_date = creation_date


    parts = session().query(OrderPart,Order.state,Order.completed_date).join(Order).\
            filter(and_( Order.completed_date != None, 
                         Order.state.in_([OrderStatusType.order_completed,OrderStatusType.order_aborted]))).\
            all()

    mainlog.info("Setting completed/aborted orders. Updating {} records".format(len(parts)))

    for part,order_state,completed_date in parts:
        part.state = OrderPartStateType.state_from_order_state(order_state)
        part.completed_date = completed_date

    mainlog.info("Setting orders which are neither completed or aborted; clearing completion dates")

    parts = session().query(OrderPart,Order.state).join(Order).\
            filter(~Order.state.in_([OrderStatusType.order_aborted,OrderStatusType.order_completed])).\
            all()

    mainlog.info("Updating {} records".format(len(parts)))

    for part,order_state in parts:
        part.state = OrderPartStateType.state_from_order_state(order_state)
        part.completed_date = None

    mainlog.info("Setting completed_date")

    parts = session().query(OrderPart.order_part_id,
                            func.max(DeliverySlip.creation).label("last_delivery")).\
        filter(
            and_( OrderPart.completed_date == None,
                  ~OrderPart.state.in_([OrderPartStateType.completed,OrderPartStateType.aborted]),
                  or_( and_(OrderPart.estimated_time_per_unit > 0, OrderPart.tex2 == OrderPart.qty),
                       and_(OrderPart.estimated_time_per_unit == 0, OrderPart.qty == 0)))).\
        outerjoin(DeliverySlipPart).\
        outerjoin(DeliverySlip).\
        group_by(OrderPart.order_part_id).\
        all()


    mainlog.info("Updating {} records".format(len(parts)))

    for part in parts:
        part.state = OrderPartStateType.completed
        part.completed_date = date.today()

    mainlog.info("Commit")

    session().commit()


alter_structure()
alter_data()
