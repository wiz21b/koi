if __name__ == "__main__":
    from koi.base_logging import init_logging
    from koi.Configurator import init_i18n,load_configuration,configuration

    init_logging()
    init_i18n()
    load_configuration("server.cfg","server_config_check.cfg")

    import argparse
    parser = argparse.ArgumentParser(description='This is an Horse! initialisation script.')
    parser.add_argument('--db-url', default=configuration.get("Database", "admin_url"), help='Database connection URL {}'.format(configuration.get("Database","admin_url")))
    args = parser.parse_args()


    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session
    init_db_session(args.db_url, metadata, True or configuration.echo_query)


import os.path

from koi.Configurator import resource_dir
from koi.base_logging import mainlog
from koi.doc_manager.client_utils import upload_template
from koi.server.json_decorator import JsonCallWrapper
from koi.doc_manager.documents_service import DocumentsService


from koi.reporting.order_confirmation.order_confirmation_report2 import HORSE_REFERENCE, print_order_confirmation_report

__author__ = 'stc'

class PluginBase:
    templates = []

    def _register_horse_template_online(self, description, fn, ref):
        documents_service = JsonCallWrapper( DocumentsService(), JsonCallWrapper.HTTP_MODE)

        doc_id = documents_service.reference_to_document_id(ref)
        if not doc_id:
            doc_id = upload_template(os.path.join(resource_dir, fn))
            documents_service.update_template_description(doc_id,description,ref)
        else:
            mainlog.debug("I didn't add {} with reference {} because it's already there".format(fn,ref))


    def online_registration(self):
        for ref, filename, description in self.templates:
            self._register_horse_template_online(description, filename, ref)


class PluginDefinition(PluginBase):
    family = "Report"
    menu = ["EditOrderParts.main", "OverviewOrderParts.contextual"]
    name = _("Order confirmation")
    reference = 'report.order.confirmation'
    templates = [ (HORSE_REFERENCE, 'order_confirmation.report.docx', _('Order confirmation'))]


    def action(self, context):
        print_order_confirmation_report(context.order_id)


if __name__ == "__main__":

    plugin = PluginDefinition()
    plugin.online_registration()