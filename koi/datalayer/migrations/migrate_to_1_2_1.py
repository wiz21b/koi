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
from koi.datalayer.supplier_mapping import Supplier
from koi.datalayer.supply_order_mapping import SupplyOrderPart,SupplyOrder

from koi.doc_manager.documents_mapping import *
from koi.doc_manager.documents_service import documents_service

parser = argparse.ArgumentParser(description='This is an Horse! migration script.')
parser.add_argument('--db-url', default=configuration.database_url, help='Database connection URL {}'.format(configuration.database_url))



def alter_structure():
    try:
        session().connection().execute("alter table horse.supply_orders add column active boolean not null constraint is_true default true")
        session().commit()
    except Exception as ex:
        session().rollback()
        mainlog.exception(ex)

def alter_data():
    # For the moment I skip this because I think that adding a role that is not
    # supported by the user session might lock people out of Horse
    # return


    import os
    import shutil

    q = session().query(Document).order_by(Document.document_id).all()
    for document in q:

        path, filename = os.path.split(document.server_location)
        new_path = documents_service._make_path_to_document(document.document_id, document.filename)

        mainlog.debug(u"Document {} -> filename:{} -- new_name:{}".format(document.document_id,
                                                                          document.filename,
                                                                          new_path))

        try:
            
            shutil.copy(document.server_location, new_path)
            document.server_location = new_path

        except Exception as ex:
            mainlog.error("Unable to copy !")
            mainlog.exception(ex)
            session().rollback()
            return

    session().commit()


args = parser.parse_args()
init_db_session(args.db_url, metadata, True or configuration.echo_query)
from koi.dao import dao
alter_structure()
#alter_data()
print("Done")
