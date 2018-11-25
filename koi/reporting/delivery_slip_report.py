from datetime import datetime,date
from decimal import *
import os

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab import platypus
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_RIGHT,TA_CENTER
from reportlab.lib.units import cm
from reportlab.platypus.doctemplate import FrameBreak
from reportlab.platypus.flowables import PageBreak
from reportlab.lib import colors

from koi.translators import nunicode,date_to_dmy,crlf_to_br
from koi.reporting.utils import MyTable,make_pdf_filename,open_pdf,customer_PDF,moneyfmt,NumberedCanvas,append_general_conditions,append_header_block,escape_html
from koi.Configurator import resource_dir
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
# reportlab.rl_config.warnOnMissingFontGlyphs = 0
pdfmetrics.registerFont(TTFont('DejaVuSansMono', os.path.join(resource_dir,'DejaVuSansMono.ttf')))

from koi.datalayer.database_session import session

def _make_delivery_slip(dao,slip_id,filename):

    global header_text
    global sub_header_text

    s = ParagraphStyle(name = "regular", fontName = 'Helvetica', fontSize=12, spaceAfter=6)
    warning_style = ParagraphStyle(name = "warning", fontName = 'Helvetica-Bold', fontSize=20, spaceAfter=6,alignment=TA_CENTER, borderWidth=2, borderColor=colors.black, leading=30)
    right_align = ParagraphStyle(name = "right_align", fontName = 'Helvetica', fontSize=12,alignment=TA_RIGHT)
    complete_document = []
    spacer = platypus.Spacer(1,1*cm)

    slip = dao.delivery_slip_part_dao.find_by_id(slip_id)
    order =slip.delivery_slip_parts[0].order_part.order
    c = order.customer

    p = Paragraph(escape_html(c.fullname),s)
    complete_document.append(p)
    p = Paragraph(escape_html(c.address1),s)
    complete_document.append(p)
    p = Paragraph(escape_html(c.address2),s)
    complete_document.append(p)

    complete_document.append(FrameBreak())

    append_header_block(complete_document,
                        _("Delivery slip <b>{}</b>").format(slip.delivery_slip_id),
                        slip.creation)

    # Well, by combining a MIDDLE VALIGN and a leading=20, I can get the
    # paragraph to be right in the middle of the cell (vertically speaking)
    # It doesn't make sense to me, it's pure trial and error...

    subtitle = ParagraphStyle(name = "subtitle", fontName = 'Helvetica', fontSize=16, leading=20)


    if not slip.active:
        p = Paragraph(_("!!! This delivery slip has been DEACTIVATED !!!"),warning_style)
        complete_document.append(p)
        complete_document.append(spacer)

    p = Paragraph(_("Order number <b>{}</b>").format(order.customer_order_name),s)
    complete_document.append(p)
    complete_document.append(spacer)

    data_ops = [ [_(u'Reference'), '', _(u'Designation'),'',_('Quantity')] ]

    for part in sorted(slip.delivery_slip_parts, key=lambda p:p.order_part.position):
        data_ops.append([Paragraph("<b>{}</b>".format(part.order_part.human_identifier),s),
                         None,
                         Paragraph(u"{}".format(escape_html(part.order_part.description)),s),
                         None,
                         Paragraph(u"{}".format(int(part.quantity_out)),s)])


    session().close()
    t = platypus.Table(data_ops, repeatRows=1, colWidths=[2*cm,1*cm,10*cm,1*cm,3*cm]) # Repeat the table header

    ts = platypus.TableStyle([('FONT', (0, 0), (-1, -1), 'Helvetica-Bold', 12)])
    ts.add('ALIGN', (0, 0), (-1, -1), 'LEFT')
    ts.add('VALIGN', (0, 0), (-1, -1), 'TOP')

    ts.add("LEFTPADDING", (0, 0), (-1, -1), 0)
    ts.add("RIGHTPADDING", (0, 0), (-1, -1), 0)

    # This is the header row
    ts.add('LINEBELOW', (0, 0), (0, 0), 0.5, colors.black)
    ts.add('LINEBELOW', (2, 0), (2, 0), 0.5, colors.black)
    ts.add('LINEBELOW', (4, 0), (4, 0), 0.5, colors.black)
    ts.add('VALIGN', (0, 0), (-1, 0), 'MIDDLE')

    # for row in titles_row:
    #     ts.add('FONT', (0, row), (-1, row), 'Helvetica', 10)

    t.setStyle(ts)
    complete_document.append(t)

    complete_document.append(spacer)
    p = Paragraph(_(u"Sauf avis contraire stipule ci-dessus, les marchandises circulent aux<br/> frais du client et a ses risques et perils."),s)
    complete_document.append(p)
    p = Paragraph(_(u"Les frais de port seront portes en facture."),s)
    complete_document.append(p)

    complete_document.append(spacer)

    data_ops = [ [ Paragraph(_("Signature :"),s), Paragraph(_("Reception date :"),s)] ]
    t = platypus.Table(data_ops, repeatRows=1, colWidths=[(A4[0] - 3*cm)/2,(A4[0] - 3*cm)/2]) # Repeat the table header
    complete_document.append(t)

    # append_general_conditions(complete_document)

    ladderDoc = customer_PDF(filename)
    ladderDoc.build(complete_document,canvasmaker=NumberedCanvas)


def print_delivery_slip(dao,slip_id):
    filename = make_pdf_filename("DeliverySlip_{}_".format(slip_id))
    _make_delivery_slip(dao,slip_id,filename)
    open_pdf(filename)
    return True

