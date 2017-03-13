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
from datetime import datetime,date
from decimal import *

from reportlab.lib.styles import ParagraphStyle
from reportlab import platypus
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.units import cm
from reportlab.platypus.doctemplate import FrameBreak
from reportlab.platypus.flowables import PageBreak
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from koi.datalayer.database_session import session
from koi.dao import dao
from koi.translators import nunicode,date_to_dmy,crlf_to_br
from koi.reporting.utils import MyTable,make_pdf_filename,open_pdf,customer_PDF,moneyfmt,NumberedCanvas,append_general_conditions,append_header_block,escape_html

from koi.Configurator import resource_dir
# reportlab.rl_config.warnOnMissingFontGlyphs = 0
pdfmetrics.registerFont(TTFont('DejaVuSansMono', os.path.join(resource_dir,'DejaVuSansMono.ttf')))



def _make_preorder_report(preorder,filename):

    # Session open !

    s = ParagraphStyle(name = "regular", fontName = 'Helvetica', fontSize=11, spaceAfter=6)
    money = ParagraphStyle(name = "money", fontName = 'DejaVuSansMono', fontSize=11, spaceAfter=6,alignment=TA_RIGHT)

    right_align = ParagraphStyle(name = "right_align", fontName = 'Helvetica', fontSize=11,alignment=TA_RIGHT)
    complete_document = []
    spacer = platypus.Spacer(1,1*cm)

    c = preorder.customer

    # Address frame

    p = Paragraph(escape_html(c.fullname),s)
    complete_document.append(p)
    p = Paragraph(escape_html(c.address1),s)
    complete_document.append(p)
    p = Paragraph(escape_html(c.address2),s)
    complete_document.append(p)
    p = Paragraph(escape_html(c.country),s)
    complete_document.append(p)

    complete_document.append(FrameBreak())

    # Header frame

    title = ""
    if preorder.customer_order_name:
        title = _("Preorder {}, your ref. : {}").format(preorder.preorder_label or "-",
                                                        escape_html(preorder.customer_order_name))
    else:
        title = _("Preorder {}").format(preorder.preorder_label or "-")

    append_header_block(complete_document, title, date.today())

    # Introduction text

    intro = preorder.preorder_print_note or ""
    p = Paragraph(escape_html(intro),s)
    complete_document.append(p)
    complete_document.append(spacer)




    # Well, by combining a MIDDLE VALIGN and a leading=20, I can get the
    # paragraph to be right in the middle of the cell (vertically speaking)
    # It doesn't make sense to me, it's pure trial and error...

    subtitle = ParagraphStyle(name = "subtitle", fontName = 'Helvetica', fontSize=16, leading=20)


    data_ops = [ [_(u'Reference'), '', _(u'Designation'),'',_('Deadline'),'',_('Quantity'),'',_('Unit Price'),'',_('Price')] ]

    # getcontext().prec = 2

    with localcontext() as ctx: # decimal context
        ctx.prec = 10+2
        qtize = Decimal(10)**-2

        total = Decimal(0)

        for part in preorder.parts:

            price = Decimal(int(part.qty) * part.sell_price).quantize(qtize)
            total += price

            s_qty = ''
            if part.qty > 0:
                s_qty = str(int(part.qty))

            s_price = ''
            if part.sell_price > 0 and part.qty > 0:
                s_price = moneyfmt(price)

            dl = "-"
            if part.deadline:
                dl = date_to_dmy(part.deadline)

            data_ops.append([Paragraph(u"<b>{}</b>".format(part.human_identifier),s),
                             None,
                             Paragraph(escape_html(part.description),s),
                             None,
                             Paragraph(dl,right_align),
                             None,
                             Paragraph(u"{}".format(s_qty),money),
                             None,
                             Paragraph(u"{}".format(moneyfmt(Decimal(part.sell_price).quantize(qtize))),money),
                             None,
                             Paragraph(u"{}".format(s_price),money)])

    # data_ops.append([None,
    #                  None,
    #                  None,
    #                  None,
    #                  Paragraph(_("Total"),s),
    #                  None,
    #                  Paragraph(moneyfmt(total),money)])

    t = MyTable(data_ops, repeatRows=1, colWidths=[2*cm,0.2*cm,6*cm,0.2*cm,2*cm,0.2*cm,1*cm,0.2*cm,3*cm,0.2*cm,3*cm]) # Repeat the table header
    t.spaceAfter = 1*cm

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
    ts.add('LINEBELOW', (8, 0), (8, 0), 0.5, colors.black)
    ts.add('LINEBELOW', (10, 0), (10, 0), 0.5, colors.black)
    #ts.add('LINEBELOW', (6, -2), (6, -2), 0.5, colors.black) # subtotal line
    ts.add('VALIGN', (0, 0), (-1, 0), 'MIDDLE')

    # for row in titles_row:
    #     ts.add('FONT', (0, row), (-1, row), 'Helvetica', 10)

    t.setStyle(ts)
    complete_document.append(t)

    footer = preorder.preorder_print_note_footer or ""
    p = Paragraph(escape_html(footer),s)
    complete_document.append(p)

    # complete_document.append(spacer)
    # p = Paragraph(_("This is a preorder."),s)
    # complete_document.append(p)

    data_ops = [ [ "", Paragraph(_("Signature"),s)] ]
    t = platypus.Table(data_ops, repeatRows=1, colWidths=[8*cm,8*cm]) # Repeat the table header
    complete_document.append(t)

    append_general_conditions(complete_document)

    ladderDoc = customer_PDF(filename)
    ladderDoc.subject = date_to_dmy(datetime.today(),full_month=True) # or preorder.creation_date ?
    ladderDoc.build(complete_document,canvasmaker=NumberedCanvas)


def print_preorder(preorder_id):
    preorder = dao.order_dao.find_by_id(preorder_id) # open transaction !
    filename = make_pdf_filename("PreOrder_{}".format(preorder.preorder_label))
    _make_preorder_report(preorder,filename)
    session().close()
    open_pdf(filename)
    return True


if __name__ == "__main__":
    from koi.dao import DAO
    dao = DAO(session())
    print_preorder(dao.order_dao.find_by_preorder_label(5256).order_id)
