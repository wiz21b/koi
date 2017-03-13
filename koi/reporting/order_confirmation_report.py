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


class HorseDocument:
    def __init__(self):
        self.complete_document = []
        self.base_style = ParagraphStyle(name = "regular", fontName = 'Helvetica', fontSize=11, spaceAfter=6)

    def append_header_block(self,title):
        append_header_block(self.complete_document, title, date.today())

    def add_vertical_spacer(self, length = 1*cm):
        spacer = platypus.Spacer(1,length)
        self.complete_document.append(spacer)

    def add_paragraph(self, txt, style):
        p = Paragraph(escape_html(txt), style)
        self.complete_document.append(p)

    def next_frame(self):
        self.complete_document.append(FrameBreak())

    def add_signature(self):
        data_ops = [ [ "", Paragraph(_("Signature"), style=self.base_style)] ]
        t = platypus.Table(data_ops, repeatRows=1, colWidths=[8*cm,8*cm]) # Repeat the table header
        self.complete_document.append(t)

    def add_general_conditions(self):
        append_general_conditions(self.complete_document)

    def add_table(self, header_table, table, column_widths, formats):

        def array_join(array, spacer=None):
            if not array:
                return array
            else:
                r = [array[0]]
                for i in range(1, len(array)):
                    r.append(spacer)
                    r.append(array[i])
                return r

        platypus_table = []

        header = array_join(header_table, '')
        #print(header)
        platypus_table.append(header)

        for t_row in table:
            i = 0
            row = []
            for cell in t_row:
                # print(cell)
                # print(formats[i].format(cell))
                row.append(formats[i].format(cell))
                i += 1
            #print(row)
            platypus_table.append( array_join(row,''))

        col_widths = array_join( column_widths, 0.2*cm)

        t = MyTable(platypus_table, repeatRows=1, colWidths=col_widths) # Repeat the table header
        t.spaceAfter = 1*cm

        ts = platypus.TableStyle([('FONT', (0, 0), (-1, -1), 'Helvetica-Bold', 12)])
        ts.add('ALIGN', (0, 0), (-1, -1), 'LEFT')
        ts.add('VALIGN', (0, 0), (-1, -1), 'TOP')

        ts.add("LEFTPADDING", (0, 0), (-1, -1), 0)
        ts.add("RIGHTPADDING", (0, 0), (-1, -1), 0)

        # This is the header row

        for i in range(len(header_table)):
            ts.add('LINEBELOW', (2*i, 0), (2*i, 0), 0.5, colors.black)
        ts.add('VALIGN', (0, 0), (-1, 0), 'MIDDLE')

        # for row in titles_row:
        #     ts.add('FONT', (0, row), (-1, row), 'Helvetica', 10)

        t.setStyle(ts)
        self.complete_document.append(t)


class NoFormatter:
    column_style = ParagraphStyle(name = "regular", fontName = 'Helvetica', fontSize=11, spaceAfter=6)

    def format(self,s):
        return Paragraph(escape_html(str(s)),self.column_style)

class DateFormatter:
    column_style = ParagraphStyle(name = "regular", fontName = 'Helvetica', fontSize=11, spaceAfter=6)

    def format(self,d):
        return Paragraph(date_to_dmy(d),self.column_style)

class IntegerFormatter:
    column_style = ParagraphStyle(name = "regular", fontName = 'Helvetica', fontSize=11, spaceAfter=6)

    def format(self,s):
        return Paragraph(str(s),self.column_style)

class MoneyFormatter:
    column_style = ParagraphStyle(name = "money", fontName = 'DejaVuSansMono', fontSize=11, spaceAfter=6,alignment=TA_RIGHT)

    def format(self,n):
        with localcontext() as ctx: # decimal context
            ctx.prec = 10+2
            qtize = Decimal(10)**-2

            x = Decimal(n).quantize(qtize)

            return Paragraph(moneyfmt(x),self.column_style)


def _make_order_confirmation_report(preorder,filename):

    s = ParagraphStyle(name = "regular", fontName = 'Helvetica', fontSize=11, spaceAfter=6)

    horsedoc = HorseDocument()
    horsedoc.add_paragraph(preorder.customer.fullname,s)
    horsedoc.add_paragraph(preorder.customer.address1,s)
    horsedoc.add_paragraph(preorder.customer.address2,s)
    horsedoc.add_paragraph(preorder.customer.country,s)
    horsedoc.next_frame()

    horsedoc.add_paragraph(_("We have well received your order {} and thank you heartily."))

    # Header frame

    title = ""
    if preorder.customer_order_name:
        title = _("Confirmation of order {}, your ref. : {}").format(
            preorder.preorder_label or "-",
            escape_html(preorder.customer_order_name))
    else:
        title = _("Confirmation of order {}").format(preorder.preorder_label or "-")

    horsedoc.append_header_block(title)

    # Introduction text

    # intro = preorder.preorder_print_note or ""
    # horsedoc.add_paragraph(intro,s)
    # horsedoc.add_vertical_spacer()

    # Well, by combining a MIDDLE VALIGN and a leading=20, I can get the
    # paragraph to be right in the middle of the cell (vertically speaking)
    # It doesn't make sense to me, it's pure trial and error...

    data_ops = []

    # getcontext().prec = 2

    for part in preorder.parts:

        data_ops.append( [
            part.human_identifier,
            part.description,
            part.qty,
            part.sell_price,
            part.qty * part.sell_price
        ] )

    horsedoc.add_table(
        [_(u'Reference'), _(u'Designation'), _('Quantity'), _('Unit Price'), _('Price')],
        data_ops,
        [2*cm, 8*cm, 2*cm, 3*cm, 3*cm],
        [NoFormatter(), NoFormatter(), IntegerFormatter(), MoneyFormatter(), MoneyFormatter()]
    )


    # footer = preorder.preorder_print_note_footer or ""
    # horsedoc.add_paragraph(footer,s)

    # complete_document.append(spacer)
    # p = Paragraph(_("This is a preorder."),s)
    # complete_document.append(p)

    horsedoc.add_signature()
    horsedoc.add_general_conditions()

    ladderDoc = customer_PDF(filename)
    ladderDoc.subject = date_to_dmy(datetime.today(),full_month=True) # or preorder.creation_date ?
    ladderDoc.build(horsedoc.complete_document,canvasmaker=NumberedCanvas)


def print_preorder(preorder_id):
    preorder = dao.order_dao.find_by_id(preorder_id) # open transaction !
    filename = make_pdf_filename("PreOrder_{}".format(preorder.preorder_label))
    _make_order_confirmation_report(preorder,filename)
    session().close()
    open_pdf(filename)
    return True


if __name__ == "__main__":
    from koi.dao import DAO
    dao = DAO(session())
    print_preorder(dao.order_dao.find_by_preorder_label(5200).order_id)
