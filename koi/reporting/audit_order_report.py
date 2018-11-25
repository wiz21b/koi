if __name__ == "__main__":
    from koi.base_logging import init_logging
    init_logging("rlab.log")
    from Configurator import configuration,mainlog,init_i18n,load_configuration
    init_i18n()
    load_configuration()
    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session,session
    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)

import os

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab import platypus
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.units import cm,mm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from koi.Configurator import resource_dir,mainlog
pdfmetrics.registerFont(TTFont('DejaVuSansMono', os.path.join(resource_dir,'DejaVuSansMono.ttf'))) # FIXME

from koi.dao import dao
from koi.reporting.utils import make_pdf_filename,open_pdf,basic_PDF,NumberedCanvas
from koi.datalayer.audit_trail_service import audit_trail_service
from koi.translators import crlf_to_br,time_to_timestamp

def print_order_audit_report(order_id):

    strip_style = ParagraphStyle(name = "regular", fontName = 'Helvetica-Bold', fontSize=16,spaceAfter=0, spaceBefore=0)
    s = ParagraphStyle(name = "regular", fontName = 'Courier', fontSize=8)
    order_style = ParagraphStyle(name = "regular", fontName = 'Helvetica-Bold', fontSize=14, spaceAfter=6, spaceBefore=12)
    small = ParagraphStyle(name = "regular", fontName = 'Helvetica', fontSize=8)
    right_align = ParagraphStyle(name = "right_align", fontName = 'Helvetica', fontSize=12,alignment=TA_RIGHT)
    complete_document = []
    spacer = platypus.Spacer(1,50)

    order = dao.order_dao.find_by_id_frozen(order_id)
    customer = dao.customer_dao.find_by_id_frozen(order.customer_id)


    data_ops = []
    data_ops.append([_("What"), _("Who"), _("When")])

    trail = audit_trail_service.audit_trail_for_order(order_id)

    if len(trail) > 0:
        for audit_trail in trail:
            data_ops.append([time_to_timestamp(audit_trail.when),
                             audit_trail.fullname[0:18],
                             Paragraph(crlf_to_br(u"{} - {}".format(audit_trail.what, audit_trail.detailed_what or "")),s) ])

        t = platypus.Table(data_ops,repeatRows=1, colWidths=[3*cm,4*cm,A4[0] - 8*cm])
        ts = platypus.TableStyle([('FONT', (0, 0), (-1, -1), 'Courier', 8)])
        ts.add('INNERGRID', (0, 0), (-1, -1), 0.5, colors.gray)
        ts.add('ALIGN', (0, 0), (-1, -1), 'LEFT')

        ts.add('BOX', (0, 0), (-1, -1), 1, colors.black)
        ts.add('BACKGROUND', (0, 0), (-1, 0), (0.9,0.9,0.9))


        t.setStyle(ts)
        t.hAlign = "LEFT"
        complete_document.append(t)
    else:
        complete_document.append(Paragraph(_("There's no audit information for this order."),s))

    filename = make_pdf_filename("OrderAudit_")
    ladderDoc = basic_PDF(filename)

    ladderDoc.title = customer.fullname
    ladderDoc.subject = _(u"Order audit {}".format(order.user_label))

    ladderDoc.build(complete_document,canvasmaker=NumberedCanvas)
    open_pdf(filename)
    return True


if __name__ == "__main__":
    print_order_audit_report(5125)
