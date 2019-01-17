from reportlab.platypus.para import Para

if __name__ == "__main__":
    from koi.base_logging import init_logging
    init_logging("rlab.log")
    from koi.Configurator import configuration,init_i18n,load_configuration
    init_i18n()
    load_configuration()


from datetime import datetime,date
from decimal import *

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab import platypus
from reportlab.platypus import Paragraph, Frame, Flowable
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.units import cm
from reportlab.platypus.doctemplate import FrameBreak,NextPageTemplate,IndexingFlowable
from reportlab.platypus.flowables import PageBreak, KeepTogether, DocAssign, DocPara, DocExec, Preformatted
from reportlab.lib import colors

from koi.Configurator import mainlog
from koi.translators import nunicode,date_to_dmy,crlf_to_br
from koi.reporting.utils import MyTable,make_pdf_filename,open_pdf,customer_PDF,moneyfmt,NumberedCanvas,append_general_conditions,GraphicalAnnotation,basic_PDF,changing_headers_PDF, escape_html, basic_frame_dimensions

import os
from koi.Configurator import resource_dir
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
# reportlab.rl_config.warnOnMissingFontGlyphs = 0
pdfmetrics.registerFont(TTFont('DejaVuSansMono', os.path.join(resource_dir,'DejaVuSansMono.ttf')))

from reportlab.graphics.barcode import createBarcodeDrawing
from koi.BarCodeBase import BarCodeIdentifier
from koi.datalayer.database_session import session
from koi.server.json_decorator import ServerErrors, ServerException

sections = dict()
satisfied = False


class PageMarker(IndexingFlowable):
    def __init__(self):
        self.page_number = 0

    def draw(self):
        pass

    def wrap(self, availWidth, availHeight):
        self.page_number = self.canv.getPageNumber()
        return (0,0)

    def isIndexing(self):
        return True

    def isSatisfied(self):
        global satisfied
        # mainlog.debug("Satisified : {}".format(satisfied))
        if satisfied:
            return True
        else:
            satisfied = True
            return False

class SubSectionNumber(Preformatted):
    def __init__(self, section_id, style):
        self._section_id = section_id
        Preformatted.__init__(self, "", style)

    def wrap(self, availWidth, availHeight):

        start, end = sections[self._section_id]

        self.lines = [ "Page {}/{}".format(self.canv.getPageNumber() - start.page_number + 1, end.page_number - start.page_number + 1) ]
        return Preformatted.wrap(self, availWidth, availHeight)




class HeaderMaker:
    def __init__(self, table_data, style, col_widths):
        self.style = style
        self.table_data = table_data
        self.col_widths = col_widths

    def make(self):
        data = copy(self.table_data)
        t = platypus.Table(data, repeatRows=0, colWidths=self.col_widths)
        t.setStyle(self.style)

        spacer = platypus.Spacer(1,30)
        return [t, spacer]


class HeaderSetter(Flowable):
    def __init__( self, header_maker):
        self._header_maker = header_maker
        Flowable.__init__(self)

    def wrap(self, availWidth, availHeight): # or wrap or draw
        return (0,0)

    def draw(self):
        pass



class HeadingsFrame(Frame):
    """ This frame will inject a header on top of itself each time
    a new page is made.

    This header can be configured by using a HeaderSetter which will
    inject the configuration at the proper time. The HeaderSetter
    role will give access to a header maker which will build the
    injected header. This is rather complicated as we want some
    flexibility and need to fiddle with ReportLab's logic.
    ReportLab is not made to inject flowable "magically", so we
    somehow have to cheat it...
    """
    def __init__(self,*args,**kwargs):
        Frame.__init__(self, *args, **kwargs)
        self._header_maker = None
        self.top_of_frame = False

    def _reset(self):
        mainlog.debug("frame reset")
        r = Frame._reset(self)
        self.top_of_frame = True
        return r


    def add(self, flowable, canv, trySplit=0):
        # mainlog.debug("HeadingsFrame.add {}, at top {}".format(type(flowable), self.top_of_frame))

        if isinstance(flowable, HeaderSetter):
            self._header_maker = flowable._header_maker

        if self.top_of_frame and self._header_maker:
            self.top_of_frame = False
            mainlog.debug("add header")
            for f in self._header_maker.make():
                res = Frame.add(self, f, canv, trySplit=0)

        return Frame.add(self, flowable, canv, trySplit)


from copy import copy



def print_one_part(part,complete_document):
    # Build up a table with accompanying style

    # data_ops = [ ['Poste',None,u'Op\u00E9ration',None] ]

    # We build up a data model and the appropriate styling information

    big_order_nr = ParagraphStyle(name = "subtitle", fontName = 'Helvetica-Bold', fontSize=24, leading=26)
    subtitle = ParagraphStyle(name = "subtitle", fontName = 'Helvetica-Bold', fontSize=18, leading=20)
    s = ParagraphStyle(name = "zou", fontName = 'Helvetica', fontSize=14, leading=16) #, borderWidth=1, borderColor=colors.black)
    opNumberStyle = ParagraphStyle(name = "zou", fontName = 'Helvetica-bold', alignment=TA_CENTER, fontSize=28,leading=28) #, borderWidth=1, borderColor=colors.black)
    centered = ParagraphStyle(name = "zou", fontName = 'Helvetica-bold', alignment=TA_CENTER, fontSize=14) #, borderWidth=1, borderColor=colors.black)

    titles_row = []

    if part.production_file and len(part.production_file[0].operations) > 0:

        # print part.description
        # print len(part.production_file[0].operations)

        data_ops = [[Paragraph(part.human_identifier,big_order_nr),
                     Paragraph(crlf_to_br(part.description),subtitle)],
                    [None,
                     Paragraph(_("Quantity : {} - Deadline: {}").format(part.qty, date_to_dmy(part.deadline)),subtitle)]]
        t = platypus.Table(data_ops, repeatRows=0, colWidths=[3*cm, 19.5*cm - 3*cm])
        ts = platypus.TableStyle()
        ts.add('GRID',(0,0),(-1,-1),0.5,colors.black)
        ts.add('VALIGN', (0, 0), (-1, -1), 'TOP')
        ts.add('ALIGN', (0, 0), (1, -1), 'RIGHT')
        t.setStyle(ts)
        complete_document.append(t)

        # desc = u"<u>{}</u> {}".format(part.human_identifier,crlf_to_br(part.description))
        # complete_document.append(Paragraph(desc,subtitle))
        complete_document.append(platypus.Spacer(1,30))

        data_ops = [ ]
        ts = platypus.TableStyle()
        operation_ndx = 1
        for op in part.production_file[0].operations:

            if op.operation_model and op.operation_model.description:
                model = Paragraph(op.operation_model.short_id,centered)
            else:
                model = None

            if op.operation_model and op.operation_model.imputable:
                code = BarCodeIdentifier.code_for(op)
                barcode = createBarcodeDrawing('EAN13',value=str(code),width=6*cm,barHeight=2*cm)
                mainlog.debug("Barcode for {} is {}".format(op, code))
                graphic = GraphicalAnnotation(code,1*cm)
            else:
                barcode = None
                graphic = None

            full_desc = ""
            if op.description:
                full_desc = u"<b>{}</b> {}".format(escape_html(op.description), op.assignee.fullname)
            else:
                full_desc = "---"

            data_ops.append([Paragraph("{}".format(operation_ndx), opNumberStyle),
                             model,
                             None,
                             Paragraph(full_desc,s),
                             barcode, # barcode, graphic
                             graphic ])
            ts.add('LINEABOVE', (0, len(data_ops)-1), (-1, len(data_ops)-1), 0.5, colors.black)

            # if op.note and len(op.note) > 0:
            #     note = u"<b>Note:</b>{}".format(op.note.replace("\n","<br/>"))
            #     data_ops.append([None,None,Paragraph(note,s),None,None ])
            #     y = len(data_ops)-2
            #     ts.add('SPAN', (3,y), (4, y+1))
            operation_ndx += 1

        ts.add('GRID',(0,0),(1,-1),0.5,colors.black)
        ts.add('BOX',(0,0),(-1,-1),0.5,colors.black)
        ts.add('ALIGN', (0, 0), (1, -1), 'RIGHT')
        ts.add('ALIGN', (2, 0), (-1, -1), 'RIGHT')
        ts.add('VALIGN', (0, 0), (-1, -1), 'TOP')
        # ts.add('VALIGN', (0, 0), (0, -1), 'MIDDLE')

        ts.add('VALIGN', (4, 0), (4, -1), 'MIDDLE')
        ts.add('ALIGN',  (3, 0), (4, -1), 'RIGHT')

        ts.add("LEFTPADDING", (0, 0), (-1, -1), 0)
        ts.add("RIGHTPADDING", (0, 0), (2, -1), 0)
        ts.add("BOTTOMPADDING", (0, 0), (-1, -1), 0.75/2*cm)
        ts.add("TOPPADDING", (1, 0), (-1, -1), 0.25*cm) # .75/2*cm)
        ts.add('LINEABOVE', (0, 0), (-1, 0), 1, colors.black)
        ts.add('LINEBELOW', (0, len(data_ops)-1), (-1, len(data_ops)-1), 1, colors.black)

        t = platypus.Table(data_ops, repeatRows=0, colWidths=[1.5*cm,1.5*cm,0.5*cm,8.5*cm,6.5*cm,1*cm]) # Repeat the table header
        # t = platypus.Table(data_ops, repeatRows=1, colWidths=[3*cm,1*cm,0.5*cm,13*cm,1*cm,1*cm]) # Repeat the table header
        t.setStyle(ts)


def print_order_parts_make_procedures(order_parts_ids):
    global dao
    s = ParagraphStyle(name = "zouzz", fontName = 'Helvetica', fontSize=14, leading=16) #, borderWidth=1, borderColor=colors.black)

    filename = make_pdf_filename("PartsProcedure_{}_".format(123321))
    ladderDoc = changing_headers_PDF(filename)
    complete_document = []

    for order_id, parts_ids in dao.order_part_dao.sort_part_id_on_order(order_parts_ids).iteritems():

        complete_document.append(Paragraph('Header',s))
        complete_document.append(FrameBreak())
        complete_document.append(Paragraph('SubHeader',s))
        complete_document.append(FrameBreak())

        # complete_document.append(NextPageTemplate('content'))

        for part_id in parts_ids:
            part = dao.order_part_dao.find_by_id(part_id)
            # print_one_part(part,complete_document)

        # complete_document.append(NextPageTemplate('begin_section'))
        complete_document.append(PageBreak())

    ladderDoc.build(complete_document,canvasmaker=NumberedCanvas)
    open_pdf(filename)


def compute_strut( widths, total_width):
    s = 0
    strut_index = None
    for i in range(len(widths)):
        w = widths[i]
        if w:
            s += w
        else:
            strut_index = i

    if strut_index is not None:
        widths[strut_index] = total_width - s

    return widths

LOREM_IPSUM = "Gallia est omnis divisa in partes tres, quarum unam incolunt Belgae, aliam Aquitani, tertiam qui ipsorum lingua Celtae, nostra Galli appellantur. Hi omnes lingua, institutis, legibus inter se differunt. Gallos ab Aquitanis Garumna flumen, a Belgis Matrona et Sequana dividit."

def make_boxes(operation_ndx, op, test_mode=False):
    s = ParagraphStyle(name = "Regular", fontName = 'Helvetica', fontSize=12) #, borderWidth=1, borderColor=colors.black)
    c = ParagraphStyle(name = "Centered", fontName = 'Helvetica', alignment=TA_CENTER, fontSize=12) #, borderWidth=1, borderColor=colors.black)

    if op.operation_model and op.operation_model.description:
        model = Paragraph(op.operation_model.short_id,c) # short_id / description
    else:
        model = None

    barcode_width = 3*cm
    if op.operation_model and op.operation_model.imputable:
        code = BarCodeIdentifier.code_for(op)
        # humanReadable : remove the numbers under the barcode
        barcode = createBarcodeDrawing('EAN13',value=str(code),width=barcode_width,barHeight=1*cm,humanReadable=False)
        mainlog.debug("Barcode for {} is {}".format(op, code))
    else:
        barcode = None


    full_desc = ""
    if op.description:
        # full_desc = u"<b>{}</b>".format(crlf_to_br(op.description))
        assignee = ''
        if op.assignee:
            assignee = op.assignee.fullname
        full_desc = escape_html(op.description)

        if test_mode and operation_ndx % 2 == 1:
            full_desc = LOREM_IPSUM[0:len(op.description)]

    else:
        full_desc = "---"

    op_ndx = "{:02}".format(operation_ndx)

    data_ops = [[ Paragraph(op_ndx,c),    model,                   barcode,            None,   Paragraph("Stop",c), Paragraph("Val1",c), Paragraph("Descriptif / remarque",c), None,   Paragraph("Acc",c), Paragraph("Ref",c), Paragraph("Val2",c), Paragraph("Mac",c)],
                [ "",                     "",                      "",                 None,   "",                  "",                  "",                                   None,   "",                 "",                 "",                  ""],
                [ Paragraph(full_desc,s), "",                      "",                 None,   "",                  "",                  "",                                   None,   "",                 "",                 "",                  ""]]

    # 1.16 = EAN13 quiet zone proportion
    col_widths= [ 0.8*cm,                 0.8*cm,                  barcode_width*1.16, 0.1*cm, 1.5*cm,              1.5*cm,              None,                                 0.1*cm, 1.1*cm,             1.1*cm,             1.5*cm,              1.1*cm]

    t = platypus.Table(data_ops, repeatRows=0, colWidths=compute_strut( col_widths, 19.5*cm) )

    ts = platypus.TableStyle()

    # Tuples are (x,y)
    ts.add('BOX',(0,0),(-1,-1),1,colors.black)
    ts.add('LINEBELOW', (4, 0), (-1, 0), 0.5, colors.black)
    # Two inner grids not to overwrite the fine linebelow
    ts.add('INNERGRID',(0,0),(-1,0),1,colors.black)
    ts.add('INNERGRID',(0,1),(-1,1),1,colors.black)
    ts.add('BOX',(0,2),(-1,2),1,colors.black)

    ts.add('ALIGN',(0,0),(-1,0),"CENTER")
    ts.add('VALIGN',(0,0),(2,0),"MIDDLE")

    # First row vertical spans
    ts.add('SPAN',(0,0),(0,1))
    ts.add('LEFTPADDING',(0,0),(-1,0),0)
    ts.add('RIGHTPADDING',(0,0),(-1,0),0)

    ts.add('SPAN',(1,0),(1,1))
    ts.add('SPAN',(2,0),(2,1))

    # Separators
    ts.add('SPAN',(3,0),(3,1))
    ts.add('SPAN',(7,0),(7,1))

    ts.add('LEADING', (0, 1), (-1, 1), 1.4*cm) # Sets the row height

    # ts.add('LINEBEFORE', (3, 0), (3, 1), 1, colors.black)
    # ts.add('LINEBEFORE', (7, 0), (7, 1), 1, colors.black)

    ts.add('TOPPADDING',(4,0),(-1,0),0)
    ts.add('BOTTOMPADDING',(4,0),(-1,0),3)

    # Last row horizontal span
    ts.add('SPAN',(0,2),(-1,2))
    ts.add('TOPPADDING',(0,2),(-1,2),6)
    ts.add('BOTTOMPADDING',(0,2),(-1,2),12)

    t.setStyle(ts)

    return t


def make_quality_boxes():
    data_ops = [["Stop",
                 "Element",
                 "Q. acc",
                 "Q. ref",
                 "Visa 2" ],
                [None,None,None,None,None]]
    t = platypus.Table(data_ops, repeatRows=0, colWidths=compute_strut( [3*cm,None,3*cm,3*cm,3*cm], 19.5*cm) )
    ts = platypus.TableStyle()
    ts.add('GRID',(0,0),(-1,-1),0.5,colors.black)
    # ts.add('VALIGN', (0, 0), (-1, -1), 'TOP')
    ts.add('ALIGN', (0, 0), (-1, -1), 'LEFT')
    ts.add('LEADING', (0, 1), (-1, -1), 1.5*cm) # Sets the row height

    ts.add('LINEBEFORE', (0, 0), (0, -1), 1, colors.black)
    ts.add('LINEAFTER', (-1, 0), (-1, -1), 1, colors.black)

    t.setStyle(ts)

    return t


def make_operation_boxes(operation_ndx, op, opNumberStyle):
    s = ParagraphStyle(name = "zou", fontName = 'Helvetica', fontSize=12) #, borderWidth=1, borderColor=colors.black)
    centered = ParagraphStyle(name = "zou", fontName = 'Helvetica-bold', fontSize=14) #, borderWidth=1, borderColor=colors.black) alignment=TA_CENTER,

    operation_number = Paragraph("{}".format(operation_ndx), opNumberStyle)

    if op.operation_model and op.operation_model.description:
        model = Paragraph(op.operation_model.short_id,centered) # short_id / description
    else:
        model = None

    if op.operation_model and op.operation_model.imputable:
        code = BarCodeIdentifier.code_for(op)
        # humanReadable : remove the numbers under the barcode
        barcode = createBarcodeDrawing('EAN13',value=str(code),width=4*cm,barHeight=1*cm,humanReadable=False)
        mainlog.debug("Barcode for {} is {}".format(op, code))
        #graphic = GraphicalAnnotation(code,1*cm)
    else:
        barcode = None
        graphic = None

    full_desc = ""
    if op.description:
        # full_desc = u"<b>{}</b>".format(crlf_to_br(op.description))
        assignee = ''
        if op.assignee:
            assignee = op.assignee.fullname
        full_desc = u"<b>{}</b><br/>{}".format(escape_html(op.description), escape_html(assignee))
    else:
        full_desc = "---"

    data_ops = [[operation_number,
                 barcode,
                 model,
                 Paragraph(full_desc,s)]]
    t = platypus.Table(data_ops, repeatRows=0, colWidths=compute_strut( [1.5*cm, 4.5*cm, 1.5*cm, None], 19.5*cm) )
    ts = platypus.TableStyle()

    # ts.add('LINEABOVE', (0, len(data_ops)-1), (-1, len(data_ops)-1), 0.5, colors.black)
    ts.add('GRID',(0,0),(-1,-1),0.5,colors.black)
    ts.add('LINEBEFORE', (0, 0), (0, -1), 1, colors.black)
    ts.add('LINEAFTER', (-1, 0), (-1, -1), 1, colors.black)
    ts.add('LINEABOVE', (0, 0), (-1, 0), 1, colors.black)
    ts.add('LINEBELOW', (0, 0), (-1, 0), 0, colors.white)
    ts.add('VALIGN', (2, 0), (-1, -1), 'TOP')
    t.setStyle(ts)

    return t


subtitle_style = ParagraphStyle(name = "subtitle", fontName = 'Helvetica-Bold', fontSize=18, leading=20)
page_style = ParagraphStyle(name = "page_number", fontName = 'Helvetica', fontSize=14)



def print_bill_of_operations_report( dao, order_id, order_part_id_selection = set(), test_mode = False):
    global header_text,sub_header_text

    mainlog.debug('print_bill_of_operations_report: order_id={}, parts={}'.format(order_id, order_part_id_selection))

    o = dao.order_dao.find_by_id(order_id)

    header_text = u"{} [{}]".format(o.customer.fullname, o.customer_order_name)
    sub_header_text = u"Mode op\u00E9ratoire"

    big_order_nr = ParagraphStyle(name = "subtitle", fontName = 'Helvetica-Bold', fontSize=24, leading=26)

    topstyle = ParagraphStyle(name = "zou", fontName = 'Helvetica', fontSize=16)

    p = platypus.Paragraph(u"<b>Client {}, commande #{}</b>".format(o.customer.customer_id,o.accounting_label),topstyle)
    spacer = platypus.Spacer(1,50)

    centered = ParagraphStyle(name = "zou", fontName = 'Helvetica-bold', alignment=TA_CENTER, fontSize=14) #, borderWidth=1, borderColor=colors.black)
    s = ParagraphStyle(name = "zou", fontName = 'Helvetica', fontSize=14, leading=16) #, borderWidth=1, borderColor=colors.black)
    page_number_style = ParagraphStyle(name = "page_number_style", fontName = 'Helvetica', alignment=TA_RIGHT, fontSize=12, leading=12) #, borderWidth=1, borderColor=colors.black)
    opNumberStyle = ParagraphStyle(name = "zou", fontName = 'Helvetica-bold', alignment=TA_CENTER, fontSize=28,leading=28) #, borderWidth=1, borderColor=colors.black)
    complete_document = []

    global satisfied
    satisfied = False
    sections.clear()
    headings_frame = HeadingsFrame(*basic_frame_dimensions)
    # complete_document.append(DocAssign("i",0))

    for part in o.parts:

        if order_part_id_selection and part.order_part_id not in order_part_id_selection:
            # Ski non selected parts
            continue

        # Build up a table with accompanying style

        # data_ops = [ ['Poste',None,u'Op\u00E9ration',None] ]

        # We build up a data model and the appropriate styling information

        titles_row = []

        if part.production_file and len(part.production_file[0].operations) > 0:

            data_ops = [[Paragraph(part.human_identifier,big_order_nr),
                         Paragraph(escape_html(part.description),subtitle_style)],
                        [SubSectionNumber(part.human_identifier, page_number_style),
                         Paragraph(_("Quantity : {} - Deadline: {}").format(part.qty, date_to_dmy(part.deadline)),subtitle_style)]]

            ts = platypus.TableStyle()
            ts.add('GRID',(0,0),(-1,-1),0.5,colors.black)
            ts.add('VALIGN', (0, 0), (-1, -1), 'TOP')
            ts.add('ALIGN', (0, 1), (-1, 1), 'RIGHT')


            start_mark = PageMarker()
            complete_document.append( start_mark)

            header_maker = HeaderMaker(data_ops, ts, col_widths=compute_strut([3.8*cm, None], A4[0]-1*cm))
            complete_document.append(HeaderSetter( header_maker))

            operation_ndx = 1
            for op in part.production_file[0].operations:
                complete_document.append(
                    KeepTogether( [
                        make_boxes(operation_ndx, op, test_mode),
                        platypus.Spacer(1,0.1*cm) ] ))

                operation_ndx += 1

            end_mark = PageMarker()
            complete_document.append( end_mark)
            sections[part.human_identifier] = (start_mark, end_mark)

            complete_document.append(HeaderSetter(None))
            complete_document.append(PageBreak())
            # complete_document.append(platypus.Spacer(1,30))

    session().close() # FIXME Dirty

    if len(complete_document) > 0:
        filename = make_pdf_filename("OrderAndParts_{}_".format(order_id))
        ladderDoc = basic_PDF(filename,body_frame=headings_frame)
        ladderDoc.subject = u"Mode op\u00E9ratoire"
        ladderDoc.title = u"Client {}".format(o.customer.customer_id)

        ladderDoc.multiBuild(complete_document,canvasmaker=NumberedCanvas)
        open_pdf(filename)
        return True
    else:
        raise ServerException( ServerErrors.printing_an_empty_report)



def print_order_report(dao, order_id, test_mode=False):
    global header_text,sub_header_text

    mainlog.debug('print_order_report order_id={}'.format(order_id))

    o = dao.order_dao.find_by_id(order_id)

    header_text = u"{} [{}]".format(o.customer.fullname, o.customer_order_name)
    sub_header_text = u"Mode op\u00E9ratoire"

    big_order_nr = ParagraphStyle(name = "subtitle", fontName = 'Helvetica-Bold', fontSize=24, leading=26)

    topstyle = ParagraphStyle(name = "zou", fontName = 'Helvetica', fontSize=16)

    p = platypus.Paragraph(u"<b>Client {}, commande #{}</b>".format(o.customer.customer_id,o.accounting_label),topstyle)
    spacer = platypus.Spacer(1,50)

    centered = ParagraphStyle(name = "zou", fontName = 'Helvetica-bold', alignment=TA_CENTER, fontSize=14) #, borderWidth=1, borderColor=colors.black)
    s = ParagraphStyle(name = "zou", fontName = 'Helvetica', fontSize=14, leading=16) #, borderWidth=1, borderColor=colors.black)
    page_number_style = ParagraphStyle(name = "page_number_style", fontName = 'Helvetica', alignment=TA_RIGHT, fontSize=12, leading=12) #, borderWidth=1, borderColor=colors.black)
    opNumberStyle = ParagraphStyle(name = "zou", fontName = 'Helvetica-bold', alignment=TA_CENTER, fontSize=28,leading=28) #, borderWidth=1, borderColor=colors.black)
    complete_document = []

    global satisfied
    satisfied = False
    sections.clear()
    headings_frame = HeadingsFrame(*basic_frame_dimensions)
    # complete_document.append(DocAssign("i",0))

    for part in o.parts:

        # Build up a table with accompanying style

        # data_ops = [ ['Poste',None,u'Op\u00E9ration',None] ]

        # We build up a data model and the appropriate styling information

        titles_row = []

        if part.production_file and len(part.production_file[0].operations) > 0:

            data_ops = [[Paragraph(part.human_identifier,big_order_nr),
                         Paragraph(escape_html(part.description),subtitle_style)],
                        [SubSectionNumber(part.human_identifier, page_number_style),
                         Paragraph(_("Quantity : {} - Deadline: {}").format(part.qty, date_to_dmy(part.deadline)),subtitle_style)]]

            ts = platypus.TableStyle()
            ts.add('GRID',(0,0),(-1,-1),0.5,colors.black)
            ts.add('VALIGN', (0, 0), (-1, -1), 'TOP')
            ts.add('ALIGN', (0, 1), (-1, 1), 'RIGHT')


            start_mark = PageMarker()
            complete_document.append( start_mark)

            header_maker = HeaderMaker(data_ops, ts, col_widths=compute_strut([3.8*cm, None], A4[0]-1*cm))
            complete_document.append(HeaderSetter( header_maker))

            operation_ndx = 1
            for op in part.production_file[0].operations:
                complete_document.append(
                    KeepTogether( [
                        make_boxes(operation_ndx, op, test_mode),
                        platypus.Spacer(1,0.1*cm) ] ))

                operation_ndx += 1

            end_mark = PageMarker()
            complete_document.append( end_mark)
            sections[part.human_identifier] = (start_mark, end_mark)

            complete_document.append(HeaderSetter(None))
            complete_document.append(PageBreak())
            # complete_document.append(platypus.Spacer(1,30))

    session().close() # FIXME Dirty

    if len(complete_document) > 0:
        filename = make_pdf_filename("OrderAndParts_{}_".format(order_id))
        ladderDoc = basic_PDF(filename,body_frame=headings_frame)
        ladderDoc.subject = u"Mode op\u00E9ratoire"
        ladderDoc.title = u"Client {}".format(o.customer.customer_id)

        ladderDoc.multiBuild(complete_document,canvasmaker=NumberedCanvas)
        open_pdf(filename)
        return True
    else:
        raise ServerException( ServerErrors.printing_an_empty_report)





if __name__ == "__main__":
    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session,session
    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)
    from koi.dao import DAO
    dao = DAO(session())

    print_order_report(dao, 6300, test_mode=True) # 5229, 6005/6300


    # print_order_parts_make_procedures([95127,95432,95354])
