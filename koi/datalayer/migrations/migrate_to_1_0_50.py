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

import argparse

parser = argparse.ArgumentParser(description='This is an Horse! migration script.')
parser.add_argument('--db-url', default=configuration.database_url, help='Database connection URL {}'.format(configuration.database_url))




def alter_structure():

    try:
        session().connection().execute("drop table horse.supplier_orders")
        session().commit()
    except Exception as ex:
        session().rollback()

    try:
        session().connection().execute("drop table horse.achat_parts")
        session().commit()
    except Exception as ex:
        session().rollback()

    try:
        session().connection().execute("drop table horse.achats")
        session().commit()
    except Exception as ex:
        session().rollback()

    try:
        session().connection().execute("drop table horse.suppliers")
        session().commit()
    except Exception as ex:
        session().rollback()
        pass

    SupplyOrderPart.__table__.drop(db_engine(), checkfirst=True)
    SupplyOrder.__table__.drop(db_engine(), checkfirst=True)
    Supplier.__table__.drop(db_engine(), checkfirst=True)

    Supplier.__table__.create()
    SupplyOrder.__table__.create()
    SupplyOrderPart.__table__.create()

    session().connection().execute("GRANT ALL ON horse.suppliers  TO horse_clt ;")
    session().connection().execute("GRANT ALL ON horse.supply_orders  TO horse_clt ;")
    session().connection().execute("GRANT ALL ON horse.supply_order_parts  TO horse_clt ;")

    session().connection().execute("GRANT ALL ON SEQUENCE  horse.suppliers_supplier_id_seq TO horse_clt ;")
    session().connection().execute("GRANT ALL ON SEQUENCE  horse.supply_orders_supply_order_id_seq TO horse_clt;")
    session().connection().execute("GRANT ALL ON SEQUENCE  horse.supply_order_parts_supply_order_part_id_seq TO horse_clt;")


    session().connection().execute("alter table horse.filter_queries drop constraint fq_by_name;")
    session().connection().execute("ALTER TABLE horse.filter_queries ADD COLUMN \"family\" character varying;")
    session().connection().execute("UPDATE horse.filter_queries SET family='order_parts_overview';")
    session().connection().execute("ALTER TABLE horse.filter_queries ALTER COLUMN \"family\" SET NOT NULL;")
    session().connection().execute("alter table horse.filter_queries add constraint fq_by_name unique (family,name);")

    session().connection().execute("CREATE TYPE horse.ck_special_activity_type AS ENUM ('holidays','partial_activity','unemployment','sick_leave','other');")
    session().connection().execute("ALTER TABLE horse.special_activities ADD COLUMN activity_type horse.ck_special_activity_type NOT NULL DEFAULT 'other';")

    session().commit()


def alter_data():

#     session().connection().execute("""
# update horse.delivery_slip_parts
# set sell_price = horse.delivery_slip_parts.quantity_out * horse.order_parts.sell_price
# from horse.order_parts
# where horse.order_parts.order_part_id = horse.delivery_slip_parts.order_part_id
# """
    session().commit()



args = parser.parse_args()
init_db_session(args.db_url, metadata, True or configuration.echo_query)
alter_structure()
alter_data()
