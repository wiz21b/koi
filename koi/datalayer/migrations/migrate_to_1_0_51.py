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
from koi.datalayer.sqla_mapping_base import DATABASE_SCHEMA

from koi.datalayer.supplier_mapping import Supplier
from koi.datalayer.supply_order_mapping import SupplyOrderPart,SupplyOrder

from koi.translators import text_search_normalize

parser = argparse.ArgumentParser(description='This is an Horse! migration script.')
parser.add_argument('--db-url', default=configuration.database_url, help='Database connection URL {}'.format(configuration.database_url))

from koi.datalayer.gapless_sequence import make_gapless_seq_function

def alter_structure():
    try:
        session().connection().execute("alter table horse.supply_orders drop column accounting_label")
    except Exception as ex:
        session().rollback()

    session().connection().execute("alter table horse.supply_orders add column accounting_label integer")

    session().connection().execute("UPDATE horse.gapless_seq SET gseq_value=(select count(*) from horse.supply_orders) WHERE gseq_name = 'supply_order_id'")

    make_gapless_seq_function(DATABASE_SCHEMA, 'supply_orders', 'supply_order_id', 'accounting_label', 'supply_orders_accounting')

    session().connection().execute("UPDATE horse.supply_orders SET accounting_label=supply_order_id")

    # bug fix
    session().connection().execute("grant all on sequence horse.filter_queries_filter_query_id_seq to horse_clt")

def alter_data():


    # Fixes broken indexes

    res = session().connection().execute("select order_part_id,description from horse.order_parts")
    for r in res:

        session().connection().execute(u"update horse.order_parts set indexed_description='{}' where order_part_id = '{}'".format(text_search_normalize(r.description), r.order_part_id))

    session().commit()



args = parser.parse_args()
init_db_session(args.db_url, metadata, True or configuration.echo_query)
from koi.dao import dao
alter_structure()
alter_data()
