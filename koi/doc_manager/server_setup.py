if __name__ == "__main__":
    from koi.base_logging import init_logging
    from koi.Configurator import init_i18n,load_configuration,configuration

    init_logging()
    init_i18n()
    load_configuration("server.cfg","server_config_check.cfg")

import os.path

from koi.Configurator import resource_dir
from koi.base_logging import mainlog
from koi.doc_manager.client_utils import upload_template
from koi.server.json_decorator import JsonCallWrapper
from koi.doc_manager.documents_service import DocumentsService
import inspect

def register_horse_template_online(description, fn, ref):
    documents_service = JsonCallWrapper( DocumentsService(), JsonCallWrapper.HTTP_MODE)

    doc_id = documents_service.reference_to_document_id(ref)
    if not doc_id:
        doc_id = upload_template(os.path.join(resource_dir, fn))
        documents_service.update_template_description(doc_id,description,ref)
    else:
        mainlog.debug("I didn't add {} with reference {} because it's already there".format(fn,ref))

def register_horse_template_offline(description, full_path, ref):
    """ Register a file in the template library, will do it by accessing the
    server code directly instead of via HTTP.

    :param description:
    :param full_path:
    :param ref:
    :return: None
    """
    from koi.doc_manager.documents_service import documents_service

    with open(full_path,'rb') as fh:
        doc_id = documents_service.reference_to_document_id(ref)
        if not doc_id:
            doc_id = documents_service.save_template(fh, os.path.basename(full_path))
            documents_service.update_template_description(doc_id, description, os.path.basename(full_path), ref)
        else:
            mainlog.debug("I didn't add {} with reference {} because it's already there".format(full_path,ref))

def register_module(module):
    register_horse_template_offline(module.HORSE_TITLE,
                                    os.path.join(os.path.dirname(inspect.getfile(module)),module.HORSE_TEMPLATE),
                                    module.HORSE_REFERENCE)


def register_all_files_offline():
    import koi.reporting.order_confirmation.order_confirmation_report2 as confirmation_report
    # register_horse_template_offline(_("Order confirmation letter template"),
    #                                 "order_confirmation_report.docx",
    #                                 koi.reporting.order_confirmation.order_confirmation_report2.HORSE_REFERENCE)
    register_module(confirmation_report)

    import koi.reporting.preorder.preorder_report as report
    register_module(report)


if __name__ == "__main__":
    import argparse
    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session

    parser = argparse.ArgumentParser(description='This is an Horse! initialisation script.')
    parser.add_argument('--db-url', default=configuration.database_url, help='Database connection URL {}'.format(configuration.get("Database","admin_url")))
    args = parser.parse_args()
    init_db_session(args.db_url, metadata, True or configuration.echo_query)

    # -------------------------------------------------------------

    register_all_files_offline()
