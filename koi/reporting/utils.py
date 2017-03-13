import os
import tempfile
import subprocess
from decimal import *
from datetime import datetime

from reportlab.pdfgen import canvas
from reportlab import platypus
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm,inch
from reportlab.platypus import Paragraph,BaseDocTemplate
from reportlab.platypus.flowables import Flowable,PageBreak

from koi.translators import date_to_dmy,crlf_to_br,EURO_SIGN
from koi.session.UserSession import user_session
from koi.Configurator import resource_dir,configuration
from koi.base_logging import mainlog


def escape_html(s):
    """ Prepares a string to be rendered in ReportLab report.
    This means :
    - escaping HTML entities
    - replacing \n by <br/> (so we introduce html entities here)
    - make sure a string is never None (ReportLab doesn't like it
    """

    if s:
        return str(s.replace('&','&amp;').replace('<','&lt;').replace('\n','<br/>'))
    else:
        return u""


def split_long_string(s, part_length=20):
    """ Reportlab has hard times fitting too long strings into table cells.
    This funcion is here to help him a bit.

    :param s:
    :param part_length:
    :return:
    """

    if len(s) > part_length:
        i = 0
        new_s = ""
        while i + part_length < len(s):

            chunk = s[i:i+part_length]

            new_s = new_s + chunk

            if " " not in chunk:
                new_s = new_s + " "

            i += part_length

        new_s = new_s + s[i:len(s)] + " "
        return new_s
    else:
        return s

class GraphicalAnnotation(Flowable):
    '''A hand flowable.'''
    def __init__(self, ident=0, size=None, fillcolor=colors.lightgrey, strokecolor=colors.black):
        if size is None: size=2*cm
        self.fillcolor, self.strokecolor = fillcolor, strokecolor
        self.xoffset = 0
        self.size = size
        # self.width = size
        # self.height = size
        # normal size is 4 inches
        self.scale = 0.8
        self.ident = ident

    def wrap(self, *args):
        #  return (self.xoffset, self.size)
        return (self.size, self.size)

    def draw(self):
        canvas = self.canv
        canvas.setLineWidth(0.1*cm)
        canvas.setFillColor(self.fillcolor)
        canvas.setStrokeColor(self.strokecolor)
        canvas.translate((1-self.scale)*self.size/2,(1-self.scale)*self.size/2)
        canvas.scale(self.scale, self.scale)
        canvas.setFillColor(self.fillcolor)
        canvas.setLineJoin(2)

        ident = self.ident
        shapes = [ [ (0,0),(1,0),(0.5,1) ],
                   [ (0,0),(1,0),(0,1),(1,1) ],
                   [ (0,0),(1,0),(1,1),(0,1) ],
                   [ (0,0.5), (0.5,1), (1,0.5), (0.5,0) ],
                   [ (0,1),(1,1),(0.5,0) ] ]

        if self.ident % 2 == 1:
            canvas.setDash(3,2)

        p = canvas.beginPath()

        ident = ident // 2
        if self.ident % 2 == 0:
            p.moveTo(0.5*self.size,0)
            p.lineTo(0.5*self.size,1*self.size)

        ident = ident // 2
        sndx = (ident) % (len(shapes)+1)
        if sndx < len(shapes):
            d = shapes[sndx]
            p.moveTo(d[0][0]*self.size,d[0][1]*self.size)
            for ndx in range(len(d)-1):
                p.lineTo(d[ndx+1][0]*self.size,d[ndx+1][1]*self.size)
        else:
            p.ellipse(0,0,1*self.size,1*self.size)

        p.close()

        canvas.drawPath(p)


class MultiPageDocument(BaseDocTemplate):
    def handle_pageBegin(self):
        '''override base method to add a change of page template after the firstpage.
        '''
        self._handle_pageBegin()
        self._handle_nextPageTemplate('Later')

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
                             _("Page {} of {}, printed on {} by {}").format(self._pageNumber, page_count, date_to_dmy(datetime.today(), full_month=True), user_session.name or '-'))



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



def simple_background(canvas,document):
    header_text = document.title
    sub_header_text = document.subject

    canvas.saveState()
    margin = 0.2*inch
    if header_text:
        canvas.setFont('Helvetica-Bold', 16)
        canvas.drawString(margin,A4[1] - 0.15*inch - margin,header_text )

    if sub_header_text:
        canvas.setFont('Helvetica-Bold', 32)
        canvas.drawString(margin,A4[1] - 0.15*inch - margin - 0.45*inch,sub_header_text)

    w = 1.5*inch
    h = w/257.0*86.0
    canvas.drawImage(os.path.join(resource_dir,"logo_pl.JPG"), A4[0] - w - margin, A4[1] - h - margin, width=w, height=h)

    p = canvas.beginPath()
    p.moveTo(0, A4[1] - h - 2*margin)
    p.lineTo(A4[0], A4[1] - h - 2*margin)
    canvas.drawPath(p)


    canvas.restoreState()


def simple_customer_background(canvas,document):
    header_text = document.title
    sub_header_text = document.subject

    canvas.saveState()
    # canvas.drawImage("background.jpg", 0,0, A4[0], A4[1])

    canvas.drawImage(os.path.join(resource_dir,"letter_header.png"), (A4[0] - 18.924*cm)/2,A4[1]-3.294*cm - 0.5*cm,18.924*cm,3.294*cm)
    canvas.drawImage(os.path.join(resource_dir,"letter_footer.png"), (A4[0] - 18.911*cm)/2,0.8*cm,18.911*cm,1.532*cm)

    canvas.setLineWidth(0.1)
    canvas.setFillColorRGB(0.8,0.8,0.8)
    # canvas.rect(1*cm,23*cm, A4[0]-2*cm,1*cm,stroke=True,fill=True)

    # canvas.setFillColorRGB(1,0,0)
    # canvas.rect(1*cm,3*cm, (A4[0]-2*cm)/2,5*cm,stroke=True,fill=False)
    # canvas.rect(1*cm+ (A4[0]-2*cm)/2, 3*cm, (A4[0]-2*cm)/2,5*cm,stroke=True,fill=False)

    # if header_text:
    #     canvas.setFont('Helvetica-Bold', 16)
    #     canvas.setFillColorRGB(0,0,0)
    #     canvas.drawString(1.25*cm,23.3*cm,header_text)

    # if sub_header_text:
    #     canvas.setFont('Helvetica', 14)
    #     canvas.setFillColorRGB(0,0,0)
    #     canvas.drawRightString(A4[0] - 1.2*cm,23.3*cm,sub_header_text)

    canvas.restoreState()



def moneyfmt(value, places=2, curr= EURO_SIGN, sep=' ', dp=',',
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
    q = Decimal(10) ** -places      # 2 places --> '0.01'
    sign, digits, exp = value.quantize(q).as_tuple()
    result = []
    digits = list(map(str, digits))
    build, next = result.append, digits.pop
    build(curr)
    if sign:
        build(trailneg)
    for i in range(places):
        build(next() if digits else '0')
    if places:
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
    return ''.join(reversed(result))


basic_frame_dimensions = [0.2*inch, 0.2*inch, A4[0] - 0.4*inch, A4[1] - 1.2*inch]

def basic_PDF(name="form_letter.pdf", body_frame = None):
    ladderDoc = platypus.BaseDocTemplate(filename=name,pagesize=A4,
                                         rightMargin=72,leftMargin=72,
                                         topMargin=72,bottomMargin=18,showBoundary=0)
    if not body_frame:
        body_frame = platypus.Frame(0.2*inch, 0.2*inch, A4[0] - 0.4*inch, A4[1] - 1.2*inch)
    else:
        mainlog.debug("Using given body frame : {}".format(body_frame))

    page_template = platypus.PageTemplate(id='AllPages',frames=[body_frame],onPage=simple_background)
    ladderDoc.addPageTemplates([page_template])
    return ladderDoc

def changing_headers_PDF(name="form_letter.pdf"):
    ladderDoc = platypus.BaseDocTemplate(filename=name,pagesize=A4,
                                         rightMargin=72,leftMargin=72,
                                         topMargin=72,bottomMargin=18,showBoundary=0)

    margin = 0.2*inch
    header_frame = platypus.Frame(margin,A4[1] - 0.15*inch - margin,
                                  A4[0] - 0.4*inch, 1.2*inch)
    subheader_frame = platypus.Frame(margin,A4[1] - 0.15*inch - margin - 0.45*inch,
                                     A4[0] - 0.4*inch, 1.2*inch)

    body_frame = platypus.Frame(0.2*inch,0.2*inch,A4[0] - 0.4*inch, A4[1] - 1.2*inch)

    page_template = platypus.PageTemplate(id='begin_section',frames=[header_frame,subheader_frame,body_frame],onPage=simple_background)
    # page_template_content = platypus.PageTemplate(id='content',frames=[body_frame],onPage=simple_background)

    ladderDoc.addPageTemplates(page_template)
    # ladderDoc.addPageTemplates([page_template,page_template_content])
    return ladderDoc



def customer_PDF(name="form_letter.pdf"):
    ladderDoc = MultiPageDocument(filename=name,pagesize=A4,
                                  rightMargin=72,leftMargin=72,
                                  topMargin=72,bottomMargin=18,showBoundary=0,allowSplitting=1,_pageBreakQuick=0)

    address_header_frame = platypus.Frame(A4[0] - 4*inch, A4[1] - 4*inch - 2.1*inch,
                                          3*inch, 4*inch + 1.5*inch,
                                          showBoundary=False)

    document_reference_frame = platypus.Frame(1*cm, 23*cm, A4[0]-2*cm, 5*cm,
                                              showBoundary=True)


    # left_header_frame2 = platypus.Frame(1*cm,23*cm, 7.5*cm, 1*cm,showBoundary=False,leftPadding=0, bottomPadding=0,rightPadding=0, topPadding=0)
    # header2_frame_right = platypus.Frame(12*cm,23*cm, 7.5*cm, 1*cm,showBoundary=True)

    body_frame = platypus.Frame(1*cm,3*cm, A4[0] - 2*cm,  21*cm, id='body', showBoundary=False)
    page_template = platypus.PageTemplate(id='First',
                                          frames=[address_header_frame, body_frame],
                                          onPage=simple_customer_background)

    body_frame = platypus.Frame(1*cm,3*cm, A4[0] - 2*cm,  21*cm, id='body', showBoundary=False)
    page_template2 = platypus.PageTemplate(id='Later',frames=[body_frame],onPage=simple_customer_background)

    ladderDoc.addPageTemplates([page_template,page_template2])

    return ladderDoc



def make_pdf_filename(prefix_tmpfile):
    tmpfile = tempfile.mkstemp(prefix=prefix_tmpfile, suffix='.PDF')
    os.close(tmpfile[0]) # Close the handle
    return tmpfile[1]

def make_temp_file(prefix_tmpfile, extension):
    tmpfile = tempfile.mkstemp(prefix=prefix_tmpfile, suffix='.' + extension)
    os.close(tmpfile[0]) # Close the handle
    return tmpfile[1]

def make_home_file( filename):
    return os.path.join( os.path.expanduser("~"), filename)


def open_pdf(filename):
    # os.startfile(tmpfile[1]) # Use the OS's default PDF viewer

    pdf_cmd = configuration.get('Programs','pdf_viewer')
    mainlog.debug("Opening PDF {} with {}".format(filename, pdf_cmd))
    if pdf_cmd:
        # Start our own viewer (which is way faster than acrobat)
        p1 = subprocess.Popen([pdf_cmd,filename])
        p1.wait()

def open_docx(filename):
    import win32com.client
    word = win32com.client.dynamic.Dispatch('Word.Application')
    word.Visible = True
    doc = word.Documents.Open(filename)

def open_xlsx(filename):
    import win32com.client
    # http://stackoverflow.com/questions/26907177/key-error-while-using-cx-freeze-for-making-exe
    word = win32com.client.dynamic.Dispatch('Excel.Application')
    word.Visible = True
    doc = word.Workbooks.Open(filename)


def append_general_conditions(complete_document):
    complete_document.append(PageBreak())
    f = open(os.path.join(resource_dir,"general_conditions.txt"), mode="r", encoding='utf-8')
    txt = f.read()
    f.close()
    txt = crlf_to_br(txt)
    general_conditions_style = ParagraphStyle(name = "regular", fontName = 'Helvetica', fontSize=10, spaceAfter=6)
    complete_document.append(Paragraph(txt,general_conditions_style))
    return complete_document


header_fnt = ParagraphStyle(name = "header", fontName = 'Helvetica-Bold', fontSize=15, leading=18)
header_small_fnt = ParagraphStyle(name = "header", fontName = 'Helvetica', fontSize=13, leading=18,alignment=TA_RIGHT)

def append_header_block(complete_document, title, ddate):
    # Header frame

    data_ops = [ [Paragraph(title,header_fnt),
                  Paragraph(date_to_dmy(ddate,full_month=True),header_small_fnt) ] ]

    t = MyTable(data_ops, colWidths=[A4[0]-5*cm - 2*cm, 5*cm])
    t.spaceAfter = 1*cm

    ts = platypus.TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.Color(0.8,0.8,0.8))])
    ts.add('BOX', (0, 0), (-1, -1), 1, colors.black)
    ts.add('ALIGN', (0, 0), (0, 0), 'LEFT')
    ts.add('ALIGN', (1, 0), (1, 0), 'RIGHT')
    t.setStyle(ts)
    complete_document.append(t)


def smart_join(strings, spacer=" "):
    return spacer.join( [s for s in strings if s])