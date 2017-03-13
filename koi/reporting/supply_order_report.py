if __name__ == "__main__":
    from Logging import init_logging
    init_logging("rlab.log")
    from Configurator import configuration,mainlog,init_i18n,load_configuration
    init_i18n()
    load_configuration()


import os
from datetime import datetime,date
from decimal import *

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab import platypus
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_RIGHT,TA_CENTER
from reportlab.lib.units import cm
from reportlab.platypus.doctemplate import FrameBreak
from reportlab.platypus.flowables import PageBreak
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from koi.translators import nunicode,date_to_dmy,crlf_to_br,quantity_to_str,amount_to_s
from koi.reporting.utils import MyTable,make_pdf_filename,open_pdf,customer_PDF,moneyfmt,NumberedCanvas,append_general_conditions,append_header_block,escape_html

from koi.Configurator import resource_dir
# reportlab.rl_config.warnOnMissingFontGlyphs = 0
pdfmetrics.registerFont(TTFont('DejaVuSansMono', os.path.join(resource_dir,'DejaVuSansMono.ttf')))

from koi.datalayer.supply_order_service import supply_order_service
from koi.datalayer.supplier_service import supplier_service

def _make_supply_order(supply_order_id,filename):

    global header_text
    global sub_header_text

    s = ParagraphStyle(name = "regular", fontName = 'Helvetica', fontSize=12, spaceAfter=6)
    table_style = ParagraphStyle(name = "regular", fontName = 'Helvetica', fontSize=11, spaceAfter=6)
    signatures_style = ParagraphStyle(name = "signature", fontName = 'Helvetica', fontSize=12, alignment=TA_CENTER)
    warning_style = ParagraphStyle(name = "warning", fontName = 'Helvetica-Bold', fontSize=20, spaceAfter=6,alignment=TA_CENTER, borderWidth=2, borderColor=colors.black, leading=30)
    right_align = ParagraphStyle(name = "right_align", fontName = 'Helvetica', fontSize=12,alignment=TA_RIGHT)
    complete_document = []
    spacer = platypus.Spacer(1,1*cm)

    supply_order, parts = supply_order_service.find_by_id(supply_order_id)
    supplier = supplier_service.find_by_id(supply_order.supplier_id)

    p = Paragraph(escape_html(supplier.fullname),s)
    complete_document.append(p)
    p = Paragraph(escape_html(supplier.address1),s)
    complete_document.append(p)
    p = Paragraph(escape_html(supplier.address2),s)
    complete_document.append(p)

    complete_document.append(FrameBreak())


    append_header_block(complete_document,
                        _("Order number <b>{}</b>, your ref. : {}").format(supply_order.accounting_label,
                                                                        escape_html(supply_order.supplier_reference or '-')),
                        supply_order.creation_date)

    p = Paragraph(escape_html(_("Delivery date : {}").format(date_to_dmy(supply_order.expected_delivery_date))),s)
    complete_document.append(p)

    # Well, by combining a MIDDLE VALIGN and a leading=20, I can get the
    # paragraph to be right in the middle of the cell (vertically speaking)
    # It doesn't make sense to me, it's pure trial and error...

    subtitle = ParagraphStyle(name = "subtitle", fontName = 'Helvetica', fontSize=16, leading=20)

    p = Paragraph("",s)
    complete_document.append(p)
    complete_document.append(spacer)

    data_ops = [ [ _('Ref.'),'',_('Description'),'',_('Quantity'),'',_('Unit price') ] ]

    for part in parts:
        data_ops.append([Paragraph(escape_html(part.human_identifier),table_style),
                         None,
                         Paragraph(escape_html(part.description),table_style),
                         None,
                         Paragraph(u"{}".format(quantity_to_str(part.quantity)),table_style),
                         None,
                         Paragraph(u"{}".format(amount_to_s(part.unit_price,"-")),table_style)])


    t = platypus.Table(data_ops, repeatRows=1, colWidths=[1.25*cm,0.75*cm,10*cm,0.75*cm,2*cm,0.75*cm,2.5*cm]) # Repeat the table header

    ts = platypus.TableStyle([('FONT', (0, 0), (-1, -1), 'Helvetica-Bold', 12)])
    ts.add('ALIGN', (0, 0), (-1, -1), 'LEFT')
    ts.add('VALIGN', (0, 0), (-1, -1), 'TOP')

    ts.add("LEFTPADDING", (0, 0), (-1, -1), 0)
    ts.add("RIGHTPADDING", (0, 0), (-1, -1), 0)

    # This is the header row
    ts.add('LINEBELOW', (0, 0), (0, 0), 0.5, colors.black)
    ts.add('LINEBELOW', (2, 0), (2, 0), 0.5, colors.black)
    ts.add('LINEBELOW', (4, 0), (4, 0), 0.5, colors.black)
    ts.add('LINEBELOW', (6, 0), (6, 0), 0.5, colors.black)
    ts.add('VALIGN', (0, 0), (-1, 0), 'MIDDLE')

    # for row in titles_row:
    #     ts.add('FONT', (0, row), (-1, row), 'Helvetica', 10)

    t.setStyle(ts)
    complete_document.append(t)

    complete_document.append(spacer)
    data_ops = [ [ Paragraph(_("Daniel Dumont<br/>Administrateur delegue"),signatures_style),
                   Paragraph(_("Pierre Jodogne<br/>Superviseur de production"),signatures_style)] ]
    t = platypus.Table(data_ops, repeatRows=1, colWidths=[9*cm,9*cm]) # Repeat the table header
    ts = platypus.TableStyle([('FONT', (0, 0), (-1, -1), 'Helvetica-Bold', 12)])
    ts.add('ALIGN', (0, 0), (-1, -1), 'CENTER')
    t.setStyle(ts)
    complete_document.append(t)


    ladderDoc = customer_PDF(filename)
    ladderDoc.build(complete_document,canvasmaker=NumberedCanvas)


def print_supply_order(supply_order_id):
    filename = make_pdf_filename("SupplyOrder_{}_".format(supply_order_id))
    _make_supply_order(supply_order_id,filename)
    open_pdf(filename)
    return True



if __name__ == "__main__":
    from db_mapping import metadata
    from datalayer.database_session import init_db_session
    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)
    print_supply_order(2)
