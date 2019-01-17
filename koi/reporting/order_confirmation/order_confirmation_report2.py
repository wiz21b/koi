if __name__ == "__main__":
    from koi.base_logging import init_logging
    from koi.Configurator import init_i18n,load_configuration,configuration
    init_logging("rlab.log")
    init_i18n()
    load_configuration()

    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session
    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)

import os
from datetime import date
from decimal import localcontext, Decimal
from docxtpl import DocxTemplate

from koi.dao import dao
from koi.server.json_decorator import JsonCallWrapper
from koi.doc_manager.documents_service import DocumentsService
from koi.doc_manager.client_utils import download_document
from koi.reporting.utils import make_home_file, moneyfmt
from koi.portability import open_a_file_on_os
from koi.translators import amount_to_s, date_to_dmy

HORSE_REFERENCE = "order_confirmation_letter"
HORSE_TEMPLATE = "order_confirmation_report.docx"
HORSE_TITLE = _("Order confirmation template")


def print_order_confirmation_report(order_id):

    documents_service = JsonCallWrapper( DocumentsService(), JsonCallWrapper.HTTP_MODE)
    doc_id = documents_service.reference_to_document_id(HORSE_REFERENCE)

    if not doc_id:
        raise Exception(_("The template document with reference <code>{}</code> was not found. Check your templates.").format(HORSE_REFERENCE))

    tpl_path = download_document(doc_id)

    order = dao.order_dao.find_by_id(order_id)

    with localcontext() as ctx: # decimal context
        ctx.prec = 10+2
        qtize = Decimal(10)**-2

        grand_total = Decimal(0)


        parts_table = []
        for part in order.parts:

            qty = Decimal(part.qty).quantize(qtize)
            sell_price = Decimal(part.sell_price).quantize(qtize)
            total_price = (qty * sell_price).quantize(qtize)

            grand_total += total_price

            parts_table.append( {
                'ref' : part.human_identifier,
                'description' : part.description or "",
                'quantity' : part.qty,
                'unit_price' : moneyfmt(sell_price),
                'total_price' : moneyfmt( total_price),
                'deadline' : date_to_dmy( part.deadline, if_none="-")
            })


    context = {
        'customer_name' : order.customer.fullname or "",
        'customer_address1' : order.customer.address1 or "",
        'customer_address2' : order.customer.address2 or "",
        'customer_country' : order.customer.country or "",

        'order_number' : order.accounting_label or order.preorder_label,
        'order_reference_customer' : order.customer_order_name or "",
        'total_parts' : moneyfmt(grand_total),

        'items' : parts_table ,
        'date_gen' : date_to_dmy(date.today())
    }

    tpl=DocxTemplate( tpl_path)
    tpl.render(context)
    doc_path = make_home_file("order_confirmation_report_{}.docx".format(order.accounting_label or order.preorder_label))

    tpl.save(doc_path )

    os.unlink(tpl_path)

    open_a_file_on_os(doc_path)
