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

import argparse

parser = argparse.ArgumentParser(description='This is an Horse! migration script.')
parser.add_argument('--db-url', default=configuration.database_url, help='Database connection URL {}'.format(configuration.database_url))




def alter_structure():

    session().connection().execute("""CREATE SEQUENCE horse.audit_trail_id_generator INCREMENT 1 MINVALUE 0  START 0;""")

#     session().connection().execute("""CREATE TABLE horse.audit_trail
# (
#   audit_trail_id integer NOT NULL,
#   what character varying NOT NULL,
#   detailed_what character varying,
#   target_id integer NOT NULL,
#   "when" timestamp without time zone NOT NULL,
#   who_id integer,
#   who_else character varying,
#   CONSTRAINT audit_trail_pkey PRIMARY KEY (audit_trail_id),
#   CONSTRAINT audit_trail_who_id_fkey FOREIGN KEY (who_id)
#       REFERENCES employees (employee_id) MATCH SIMPLE
#       ON UPDATE NO ACTION ON DELETE NO ACTION,
#   CONSTRAINT who_is_human_or_computer CHECK (who_id IS NULL AND who_else IS NOT NULL OR who_id IS NOT NULL AND who_else IS NULL)
# )
# WITH (
#   OIDS=FALSE
# );
# """)


    # session().connection().execute("""CREATE INDEX ix_horse_audit_trail_when
    # ON horse.audit_trail
    # USING btree
    # ("when");""")



    session().connection().execute("GRANT ALL ON horse.audit_trail  TO horse_clt ;")
    session().connection().execute("GRANT ALL ON SEQUENCE horse.audit_trail_id_generator  TO horse_clt ;")

    # session().connection().execute("ALTER TABLE horse.delivery_slip ADD COLUMN active boolean DEFAULT true;")
    # session().connection().execute("ALTER TABLE horse.delivery_slip ALTER COLUMN active SET NOT NULL;")


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
init_db_session(args.db_url, metadata, False or configuration.echo_query)
from dao import dao
alter_structure()
alter_data()
