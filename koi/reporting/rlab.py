# Format carte bancaire :  85,60 x 53,98 mm

import os
import tempfile
from decimal import *

from reportlab import platypus
from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch,cm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph,BaseDocTemplate

from koi.session.UserSession import user_session

if __name__ == "__main__":
    from koi.base_logging import init_logging
    init_logging("rlab.log")
    from koi.Configurator import configuration,mainlog,init_i18n,load_configuration
    init_i18n()
    load_configuration()

    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session,session
    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)
    from koi.dao import DAO
    dao = DAO(session())


from koi.reporting.utils import open_pdf

class MyTable(platypus.Table):

    guard_height = 5*cm

    """ Height of the space that must be left between the end of the table
    and the end of the frame. This makes sure that the content that fills
    that space will be tied to the table and not split on another frame """

    guard_rows = 4

    """ If the table is split, make sure the last part is at least
    made of a number of rows. If not, the split will be changed so that
    this condition is met (the table will be split "sooner") """

    def _split_util(self,availHeight,impossible):
        h = 0
        n = 1
        split_at = 0 # from this point of view 0 is the first position where the table may *always* be splitted

        for ndx in range(len(self._rowHeights)):
            rh = self._rowHeights[ndx]
            if h+rh>availHeight:
                break
            if n not in impossible:
                split_at=n
            h=h+rh
            n=n+1

        return h,split_at

    def _getFirstPossibleSplitRowPosition(self,availHeight):
        impossible={}
        if self._spanCmds:
            self._getRowImpossible(impossible,self._rowSpanCells,self._spanRanges)
        if self._nosplitCmds:
            self._getRowImpossible(impossible,self._rowNoSplitCells,self._nosplitRanges)
        h,split_at = self._split_util(availHeight,impossible)

        # print "nb rows {}, split at {}".format(len(self._rowHeights),split_at)

        if (split_at == 0 and availHeight - h < self.guard_height):
            h,split_at = self._split_util(availHeight - self.guard_height,impossible)
            return split_at

        elif (split_at > 0 and len(self._rowHeights) - split_at <= self.guard_rows):
            split_at = len(self._rowHeights) - self.guard_rows
            while split_at in impossible:
                split_at -= 1

        return split_at


from koi.BarCodeBase import BarCodeIdentifier

from koi.db_mapping import *


from koi.translators import date_to_dmy, EURO_SIGN
from koi.Configurator import resource_dir
from koi.configuration.business_functions import *



from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
# reportlab.rl_config.warnOnMissingFontGlyphs = 0
pdfmetrics.registerFont(TTFont('DejaVuSansMono', os.path.join(resource_dir,'DejaVuSansMono.ttf')))

def moneyfmt(value, places=2, curr= EURO_SIGN, sep='', dp=',',
             pos='', neg='-', trailneg=''):
    """Convert Decimal to a money formatted string.

    places:  required number of places after the decimal point
    curr:    optional currency symbol before the sign (may be blank)
    sep:     optional grouping separator (comma, period, space, or blank)
    dp:      decimal point indicator (comma or period)
             only specify as blank when places is zero
    pos:     optional sign for positive numbers: '+', space or blank
    neg:     optional sign for negative numbers: '-', '(', space or blank
    trailneg:optional trailing minus indicator:  '-', ')', space or blank

    >>> d = Decimal('-1234567.8901')
    >>> moneyfmt(d, curr='$')
    '-$1,234,567.89'
    >>> moneyfmt(d, places=0, sep='.', dp='', neg='', trailneg='-')
    '1.234.568-'
    >>> moneyfmt(d, curr='$', neg='(', trailneg=')')
    '($1,234,567.89)'
    >>> moneyfmt(Decimal(123456789), sep=' ')
    '123 456 789.00'
    >>> moneyfmt(Decimal('-0.02'), neg='<', trailneg='>')
    '<0.02>'

    """
    with localcontext() as ctx:
        ctx.prec = 10+2
        q = Decimal(10) ** -places      # 2 places --> '0.01'
        sign, digits, exp = value.quantize(q).as_tuple()
        result = []
        digits = map(str, digits)
        build, next = result.append, digits.pop
        build(curr)
        if sign:
            build(trailneg)
        for i in range(places):
            build(next() if digits else '0')
        build(dp)
        if not digits:
            build('0')
        i = 0
        while digits:
            build(next())
            i += 1
            if i == 3 and digits:
                i = 0
                build(sep)
        build(neg if sign else pos)
        result = map( lambda s: str(s), result)
        return u''.join(reversed(result))


def round(n):
    if -0.0001 < n < 0.0001:
        return ""
    elif n - int(n) < 0.00001:
        return str(int(n))
    elif n*10 - int(n*10) < 0.00001:
        return u"{:,.1f}".format(n)
    else:
        return u"{:,.2f}".format(n)



def cleanzero(n):
    if n is None or n == 0:
        return u''
    else:
        return str(n)



# class GraphicalAnnotation(Flowable):
#     '''A hand flowable.'''
#     def __init__(self, ident=0, size=None, fillcolor=colors.lightgrey, strokecolor=black):
#         if size is None: size=2*cm
#         self.fillcolor, self.strokecolor = fillcolor, strokecolor
#         self.xoffset = 0
#         self.size = size
#         # self.width = size
#         # self.height = size
#         # normal size is 4 inches
#         self.scale = 0.8
#         self.ident = ident

#     def wrap(self, *args):
#         #  return (self.xoffset, self.size)
#         return (self.size, self.size)

#     def draw(self):
#         canvas = self.canv
#         canvas.setLineWidth(0.1*cm)
#         canvas.setFillColor(self.fillcolor)
#         canvas.setStrokeColor(self.strokecolor)
#         canvas.translate((1-self.scale)*self.size/2,(1-self.scale)*self.size/2)
#         canvas.scale(self.scale, self.scale)
#         canvas.setFillColor(self.fillcolor)
#         canvas.setLineJoin(2)

#         ident = self.ident
#         shapes = [ [ (0,0),(1,0),(0.5,1) ],
#                    [ (0,0),(1,0),(0,1),(1,1) ],
#                    [ (0,0),(1,0),(1,1),(0,1) ],
#                    [ (0,0.5), (0.5,1), (1,0.5), (0.5,0) ],
#                    [ (0,1),(1,1),(0.5,0) ] ]

#         if self.ident % 2 == 1:
#             canvas.setDash(3,2)

#         p = canvas.beginPath()

#         ident = ident / 2
#         if self.ident % 2 == 0:
#             p.moveTo(0.5*self.size,0)
#             p.lineTo(0.5*self.size,1*self.size)

#         ident = ident /2
#         sndx = (ident) % (len(shapes)+1)
#         if sndx < len(shapes):
#             d = shapes[sndx]
#             p.moveTo(d[0][0]*self.size,d[0][1]*self.size)
#             for ndx in range(len(d)-1):
#                 p.lineTo(d[ndx+1][0]*self.size,d[ndx+1][1]*self.size)
#         else:
#             p.ellipse(0,0,1*self.size,1*self.size)

#         p.close()

#         canvas.drawPath(p)




def format_date(d):
    date_format = "{:%d/%b/%Y at %Hh %Mm}"
    return date_format.format(d)

def format_date_short(d):
    date_format = "{:%d %b %Y}"
    return date_format.format(d)

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        """add page info to each page (page x of y)"""
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.setFont("Helvetica", 7)
        self.drawRightString(A4[0]-1*cm, 0.5*cm,
                             _("Page {} of {}, printed on {} by {}").format(self._pageNumber, page_count, date_to_dmy(datetime.today(), full_month=True), user_session.name))

# class NumberedCanvas(canvas.Canvas):
#     def __init__(self, *args, **kwargs):
#         canvas.Canvas.__init__(self, *args, **kwargs)
#         self._codes = []
#     def showPage(self):
#         self._codes.append({'code': self._code, 'stack': self._codeStack})
#         self._startPage()
#     def save(self):
#         """add page info to each page (page x of y)"""
#         # reset page counter
#         self._pageNumber = 0
#         for code in self._codes:
#             # recall saved page
#             self._code = code['code']
#             self._codeStack = code['stack']
#             self.setFont("Helvetica", 7)
#             print "page"
#             s = "page %(this)i of %(total)i" % {
#                    'this': self._pageNumber+1,
#                    'total': len(self._codes),
#                 }
#             self.drawRightString(120*mm, 120*mm,s )
#             canvas.Canvas.showPage(self)

#         self._doc.SaveToFile(self._filename, self)

def amount_to_str(amount):
    if amount is None:
        return None

    # Display an amount in the french/belgian way
    t = u"{:,.2f}".format(float(str(amount))).replace(u",",u" ").replace(u".",u",")
    return t + EURO_SIGN




header_text = "Operations"
global sub_header_text
sub_header_text = "TO_FILL"

def funcy(canvas,document):
    global header_text
    global sub_header_text

    canvas.saveState()
    margin = 0.2*inch
    canvas.setFont('Helvetica-Bold', 16)
    canvas.drawString(margin,A4[1] - 0.2*inch - margin,header_text )

    canvas.setFont('Helvetica-Bold', 32)
    canvas.drawString(margin,A4[1] - 0.2*inch - margin - 0.40*inch,sub_header_text)

    w = 1.5*inch
    h = w/257.0*86.0
    canvas.drawImage(os.path.join(resource_dir,"logo_pl.JPG"), A4[0] - w - margin, A4[1] - h - margin, width=w, height=h)

    p = canvas.beginPath()
    p.moveTo(0, A4[1] - h - 2*margin)
    p.lineTo(A4[0], A4[1] - h - 2*margin)
    canvas.drawPath(p)


    canvas.restoreState()

    # + str(canvas.getPageNumber())



def full_background(canvas,document):
    canvas.saveState()
    # canvas.drawImage("background.jpg", 0,0, A4[0], A4[1])

    canvas.drawImage(os.path.join(resource_dir,"letter_header.png"), (A4[0] - 18.924*cm)/2,A4[1]-3.294*cm - 0.5*cm,18.924*cm,3.294*cm)
    canvas.drawImage(os.path.join(resource_dir,"letter_footer.png"), (A4[0] - 18.911*cm)/2,0.8*cm,18.911*cm,1.532*cm)

    # left_header_frame = platypus.Frame(A4[0] - 4*inch,A4[1] - 2*inch, 3*inch, 1*inch,showBoundary=True)
    # header2_frame_right = platypus.Frame(12*cm,22*cm, 7.5*cm, 1*cm,showBoundary=True)
    # body_frame = platypus.Frame(0.5*inch,3*inch, A4[0] - 1*inch,  A4[1] - 5.6*inch,showBoundary=True)
    # bottom_left_frame  = platypus.Frame(0.5*inch, 1*inch, 3.3*inch, 1.9*inch,showBoundary=True)
    # bottom_right_frame = platypus.Frame(A4[0] - 4.2*inch, 1*inch, 3.5*inch, 1.9*inch,showBoundary=True)


    canvas.setLineWidth(0.1)
    canvas.setFillColorRGB(0.8,0.8,0.8)
    canvas.rect(1*cm,23*cm, A4[0]-2*cm,1*cm,stroke=True,fill=True)

    canvas.rect(1*cm,8*cm, A4[0]-2*cm,16*cm,stroke=True,fill=False)

    canvas.setFillColorRGB(1,0,0)
    canvas.rect(1*cm,3*cm, (A4[0]-2*cm)/2,5*cm,stroke=True,fill=False)
    canvas.rect(1*cm+ (A4[0]-2*cm)/2, 3*cm, (A4[0]-2*cm)/2,5*cm,stroke=True,fill=False)

    canvas.restoreState()



def simple_customer_background(canvas,document):
    canvas.saveState()
    # canvas.drawImage("background.jpg", 0,0, A4[0], A4[1])

    canvas.drawImage(os.path.join(resource_dir,"letter_header.png"), (A4[0] - 18.924*cm)/2,A4[1]-3.294*cm - 0.5*cm,18.924*cm,3.294*cm)
    canvas.drawImage(os.path.join(resource_dir,"letter_footer.png"), (A4[0] - 18.911*cm)/2,0.8*cm,18.911*cm,1.532*cm)

    canvas.setLineWidth(0.1)
    canvas.setFillColorRGB(0.8,0.8,0.8)
    canvas.rect(1*cm,23*cm, A4[0]-2*cm,1*cm,stroke=True,fill=True)
    # canvas.rect(1*cm,8*cm, A4[0]-2*cm,16*cm,stroke=True,fill=False)

    # canvas.setFillColorRGB(1,0,0)
    # canvas.rect(1*cm,3*cm, (A4[0]-2*cm)/2,5*cm,stroke=True,fill=False)
    # canvas.rect(1*cm+ (A4[0]-2*cm)/2, 3*cm, (A4[0]-2*cm)/2,5*cm,stroke=True,fill=False)

    if header_text:
        canvas.setFont('Helvetica-Bold', 16)
        canvas.setFillColorRGB(0,0,0)
        canvas.drawString(1.25*cm,23.3*cm,header_text)

    if sub_header_text:
        canvas.setFont('Helvetica', 14)
        canvas.setFillColorRGB(0,0,0)
        canvas.drawRightString(A4[0] - 1.2*cm,23.3*cm,sub_header_text)

    canvas.restoreState()



# ladderDoc = platypus.BaseDocTemplate(filename="form_letter.pdf",pagesize=A4,
#                         rightMargin=72,leftMargin=72,
#                         topMargin=72,bottomMargin=18,showBoundary=0)
# body_frame = platypus.Frame(0.2*inch,0.2*inch,A4[0] - 0.4*inch, A4[1] - 1.2*inch)
# page_template = platypus.PageTemplate(id='AllPages',frames=[body_frame],onPage=funcy)
# ladderDoc.addPageTemplates([page_template])


#ladderDoc = platypus.BaseDocTemplate('ladders.pdf')

def make_pdf_filename(prefix_tmpfile):
    tmpfile = tempfile.mkstemp(prefix=prefix_tmpfile, suffix='.PDF')
    os.close(tmpfile[0]) # Close the handle
    return tmpfile[1]



def start_PDF(name="form_letter.pdf"):
    ladderDoc = platypus.BaseDocTemplate(filename=name,pagesize=A4,
                                         rightMargin=72,leftMargin=72,
                                         topMargin=72,bottomMargin=18,showBoundary=0)
    body_frame = platypus.Frame(0.2*inch,0.2*inch,A4[0] - 0.4*inch, A4[1] - 1.2*inch)
    page_template = platypus.PageTemplate(id='AllPages',frames=[body_frame],onPage=funcy)
    ladderDoc.addPageTemplates([page_template])
    return ladderDoc


def letter_PDF(name="form_letter.pdf"):
    ladderDoc = platypus.BaseDocTemplate(filename=name,pagesize=A4,
                                         rightMargin=72,leftMargin=72,
                                         topMargin=72,bottomMargin=18,showBoundary=0,allowSplitting=0,_pageBreakQuick=0)

    address_header_frame = platypus.Frame(A4[0] - 4*inch, A4[1] - 4*inch - 2.1*inch,
                                          3*inch, 4*inch + 1.5*inch,
                                          showBoundary=False)

    left_header_frame2 = platypus.Frame(1*cm,23*cm, 7.5*cm, 1*cm,showBoundary=False,leftPadding=0, bottomPadding=0,rightPadding=0, topPadding=0)
    header2_frame_right = platypus.Frame(12*cm,23*cm, 7.5*cm, 1*cm,showBoundary=False)

    body_frame = platypus.Frame(1*cm,6*cm, A4[0] - 2*cm,  (17-1)*cm,showBoundary=False)

    bottom_left_frame  = platypus.Frame(1*cm,3*cm, (A4[0]-2*cm)/2, 5*cm,showBoundary=False)
    bottom_right_frame = platypus.Frame(1*cm+ (A4[0]-2*cm)/2, 3*cm, (A4[0]-2*cm)/2,5*cm, showBoundary=False)

    page_template = platypus.PageTemplate(id='AllPages',frames=[address_header_frame, left_header_frame2, header2_frame_right, body_frame, bottom_left_frame, bottom_right_frame],onPage=simple_customer_background)
    ladderDoc.addPageTemplates([page_template])
    return ladderDoc


class MultiPageDocument(BaseDocTemplate):
    def handle_pageBegin(self):
        '''override base method to add a change of page template after the firstpage.
        '''
        self._handle_pageBegin()
        self._handle_nextPageTemplate('Later')


def customer_PDF(name="form_letter.pdf"):
    ladderDoc = MultiPageDocument(filename=name,pagesize=A4,
                                  rightMargin=72,leftMargin=72,
                                  topMargin=72,bottomMargin=18,showBoundary=0,allowSplitting=1,_pageBreakQuick=0)

    address_header_frame = platypus.Frame(A4[0] - 4*inch, A4[1] - 4*inch - 2.1*inch,
                                          3*inch, 4*inch + 1.5*inch,
                                          showBoundary=False)

    # left_header_frame2 = platypus.Frame(1*cm,23*cm, 7.5*cm, 1*cm,showBoundary=False,leftPadding=0, bottomPadding=0,rightPadding=0, topPadding=0)
    # header2_frame_right = platypus.Frame(12*cm,23*cm, 7.5*cm, 1*cm,showBoundary=True)
    body_frame = platypus.Frame(1*cm,3*cm, A4[0] - 2*cm,  (20)*cm, id='body', showBoundary=False)
    page_template = platypus.PageTemplate(id='First',frames=[address_header_frame, body_frame],onPage=simple_customer_background)

    body_frame = platypus.Frame(1*cm,3*cm, A4[0] - 2*cm,  20*cm, id='body', showBoundary=False)
    page_template2 = platypus.PageTemplate(id='Later',frames=[body_frame],onPage=simple_customer_background)

    ladderDoc.addPageTemplates([page_template,page_template2])

    return ladderDoc


def print_employees_badges(dao):
    global header_text
    global sub_header_text

    header_text = ""
    sub_header_text = _("Employees badges")
    s = ParagraphStyle(name = "zou", fontName = 'Helvetica', alignment=TA_CENTER)

    badges_per_line = 3
    array = []
    row = []

    employees = dao.employee_dao.all()

    if len(employees) == 0:
        return

    i = 0
    for employee in employees:
        row.append( [ Paragraph(employee.fullname,s),
                      platypus.Spacer(0,0.25*cm),
                      createBarcodeDrawing('EAN13',value=str(BarCodeIdentifier.code_for(employee)),barHeight=1*cm) ])
        i = i + 1
        if i == badges_per_line:
            array.append(row)
            row = []
            i = 0
    if i > 0:
        array.append(row)

    t = platypus.Table(array, repeatRows=0, colWidths=[6*cm]*badges_per_line,
                       rowHeights=[3*cm]*len(array)) # Repeat the table header

    ts = platypus.TableStyle([('FONT', (0, 0), (-1, -1), 'Helvetica', 8)])
    ts.add('ALIGN', (0, 0), (-1, -1), 'CENTER')
    ts.add('VALIGN', (0, 0), (-1, -1), 'MIDDLE')

    ts.add("LEFTPADDING", (0, 0), (-1, -1), 0)
    ts.add("RIGHTPADDING", (0, 0), (-1, -1), 0)
    ts.add('INNERGRID', (0,0), (-1,-1), 0.25, colors.black)
    ts.add('BOX', (0,0), (-1,-1), 0.25, colors.black)

    t.setStyle(ts)
    complete_document = []
    complete_document.append(t)


    filename = make_pdf_filename("EmployeeBadges")
    ladderDoc = start_PDF(filename)
    ladderDoc.build(complete_document,canvasmaker=NumberedCanvas)
    open_pdf(filename)


def print_non_billable_tasks(dao):
    global header_text, sub_header_text
    header_text = ""
    sub_header_text = _("Non billable tasks")

    s = ParagraphStyle(name = "zou", fontName = 'Helvetica', alignment=TA_CENTER)
    complete_document = []

    tasks_per_line = 3
    array = []
    row = []

    operation_definitions_list = dao.operation_definition_dao.all_imputable_unbillable(date.today())
    # FIXME If I don't do this, then accesing opdef description
    # after session close reopens the session...
    operation_definitions = [ (opdef.description, BarCodeIdentifier.code_for(opdef)) for opdef in operation_definitions_list]
    session().commit()


    if len(operation_definitions) > 0:
        i = 0
        for description, barcode in operation_definitions:
            row.append( [ Paragraph(description,s),
                          platypus.Spacer(0,0.5*cm),
                          createBarcodeDrawing('EAN13',value=str(barcode),width=5*cm,height=2*cm),
                          platypus.Spacer(0,0.5*cm)])
            i = i + 1
            if i == tasks_per_line:
                array.append(row)
                row = []
                i = 0

        t = platypus.Table(array, repeatRows=1, colWidths=[6*cm]*tasks_per_line) # Repeat the table header

        ts = platypus.TableStyle([('FONT', (0, 0), (-1, -1), 'Helvetica', 8)])
        ts.add('ALIGN', (0, 0), (-1, -1), 'CENTER')
        ts.add('VALIGN', (0, 0), (-1, -1), 'MIDDLE')

        ts.add("LEFTPADDING", (0, 0), (-1, -1), 0)
        ts.add("RIGHTPADDING", (0, 0), (-1, -1), 0)
        ts.add('INNERGRID', (0,0), (-1,-1), 0.25, colors.black)
        ts.add('BOX', (0,0), (-1,-1), 0.25, colors.black)

        t.setStyle(ts)
        complete_document.append(t)

    else:
        complete_document.append(Paragraph(_("There currently are no unbillable operations defined"),s))

    filename = make_pdf_filename("NonBillableTasks")
    ladderDoc = start_PDF(filename)
    ladderDoc.build(complete_document,canvasmaker=NumberedCanvas)
    open_pdf(filename)



def print_presence_tasks(dao):
    global header_text, sub_header_text
    header_text = ""
    sub_header_text = _("Presence tasks")

    s = ParagraphStyle(name = "zou", fontName = 'Helvetica', alignment=TA_CENTER)
    topstyle = ParagraphStyle(name = "zou", fontName = 'Helvetica-Bold', alignment=TA_CENTER, fontSize=24)

    array = []
    row = []

    row.append( [ Paragraph(_("Clock IN"),topstyle),
                  platypus.Spacer(0,1*cm),
                  createBarcodeDrawing('EAN13',value=str(BarCodeIdentifier.code_for(TaskActionReportType.day_in)),width=10*cm,height=4*cm),
                  platypus.Spacer(0,0.5*cm)])
    array.append(row)

    array.append([])

    row = []
    row.append( [ Paragraph(_("Clock OUT"),topstyle),
                  platypus.Spacer(0,1*cm),
                  createBarcodeDrawing('EAN13',value=str(BarCodeIdentifier.code_for(TaskActionReportType.day_out)),width=10*cm,height=4*cm),
                  platypus.Spacer(0,0.5*cm)])
    array.append(row)


    t = platypus.Table(array, repeatRows=1) # Repeat the table header

    ts = platypus.TableStyle([('FONT', (0, 0), (-1, -1), 'Helvetica', 8)])
    ts.add('ALIGN', (0, 0), (-1, -1), 'CENTER')
    ts.add('VALIGN', (0, 0), (-1, -1), 'MIDDLE')

    ts.add("LEFTPADDING", (0, 0), (-1, -1), 0)
    ts.add("RIGHTPADDING", (0, 0), (-1, -1), 0)
    ts.add('INNERGRID', (0,0), (-1,-1), 0.25, colors.black)
    ts.add('BOX', (0,0), (-1,-1), 0.25, colors.black)

    t.setStyle(ts)
    complete_document = []
    complete_document.append(t)

    filename = make_pdf_filename("NonBillableTasks")
    ladderDoc = start_PDF(filename)
    ladderDoc.build(complete_document,canvasmaker=NumberedCanvas)
    open_pdf(filename)









def print_indirects_without_order():
    for opdef in dao.operation_definition_dao.all_indirect(False):
        print( BarCodeIdentifier.code_for(opdef))





if __name__ == "__main__":

    #print_order_report(dao,4437)
    # print_order_report(dao,2001) # session ok
    # print_delivery_slip(dao,800) # session OK
    # print_production_status_detailed(dao) # session OK

    # print_preorder(dao.order_dao.find_by_id(4300))
    # print_preorder(dao.order_dao.find_by_id(4442)) # session ok
    # print_employees_badges(dao) # session ok
    # print_non_billable_tasks(dao) # Session ok
    # print_presence_tasks(dao) # session ok

    ## print_plant_intervention_sheet2(dao) ???
    ## print_indirects_without_order() What's this ?
    print_iso_status(dao,4747)
