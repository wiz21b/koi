if __name__ == "__main__":
    from koi.base_logging import init_logging
    init_logging("rlab.log")
    from koi.Configurator import configuration,init_i18n,load_configuration
    init_i18n()
    load_configuration()



import os
import calendar
from datetime import date,datetime,timedelta

from reportlab.lib.styles import ParagraphStyle
from reportlab import platypus
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.units import cm,mm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from sqlalchemy.orm import join,contains_eager,subqueryload,subqueryload_all

from koi.Configurator import mainlog,resource_dir
from koi.db_mapping import DeliverySlip,Order,OrderPart,ProductionFile,Operation,TaskOnOperation,TimeTrack,Customer,OrderStatusType
from koi.translators import date_to_dm,nice_round,date_to_my,amount_to_short_s,duration_to_s,crlf_to_br

from koi.reporting.utils import make_pdf_filename,open_pdf,basic_PDF,NumberedCanvas

# reportlab.rl_config.warnOnMissingFontGlyphs = 0
pdfmetrics.registerFont(TTFont('DejaVuSansMono', os.path.join(resource_dir,'DejaVuSansMono.ttf')))


def _last_moment_of_month(month_date):
    """ Compute the last moment of the month. Any timestamp greater
    than tha is in the next month. The accuracy of the computation
    must be sufficient for comparing timestamps in database as well.
    """

    first_of_month = datetime(month_date.year,month_date.month,1)
    first_of_next_month = first_of_month + timedelta(calendar.monthrange(month_date.year,month_date.month)[1])

    # PostgreSQL has microsecond accuracy for its timestamp and so
    # does Python. So the way I compute the first moment of the
    # month below is OK.

    return first_of_next_month - timedelta(microseconds=1)


def _first_moment_of_month(month_date):
    return datetime(month_date.year,month_date.month,1)



def print_monthly_report(dao,month_date):

    strip_style = ParagraphStyle(name = "regular", fontName = 'Helvetica-Bold', fontSize=16,spaceAfter=0, spaceBefore=0)
    s = ParagraphStyle(name = "regular", fontName = 'Courrier', fontSize=7)
    order_style = ParagraphStyle(name = "regular", fontName = 'Helvetica-Bold', fontSize=14, spaceAfter=6, spaceBefore=12)
    small = ParagraphStyle(name = "regular", fontName = 'Helvetica', fontSize=8)
    small_right = ParagraphStyle(name = "regular", fontName = 'Helvetica', fontSize=8, alignment=TA_RIGHT)
    client = ParagraphStyle(name = "regular", fontName = 'Helvetica-Bold', fontSize=9)
    right_align = ParagraphStyle(name = "right_align", fontName = 'Courier', fontSize=8, alignment=TA_RIGHT)
    right_align_bold = ParagraphStyle(name = "right_align", fontName = 'Courier-Bold', fontSize=8, alignment=TA_RIGHT)
    complete_document = []
    spacer = platypus.Spacer(1,50)


    ts_begin = _first_moment_of_month(month_date)
    ts_end = _last_moment_of_month(month_date)

    # mainlog.debug("Turnover from {} to {} ({})".format(ts_begin, ts_end, month_date))

    # data_ops = [[crlf_to_br(h) for h in [_('Ord.'),_('Description'),_('Hours'),_('Qties'),_('Sell\nprice'),_('To bill\nthis month'),_('Encours')]]]
    data_ops = [[_('Ord.'),_('Description'),_('Hours'),_('Qties'),_('Sell\nprice'),_('To bill\nthis month'),_('Encours')]]

    ts = platypus.TableStyle([('FONT', (0, 0), (-1, -1), 'Courier', 8)])

    last_order_id = None

    total_sell_price = 0
    total_encours = 0
    total_to_facture = 0

    sub_total_sell_price = 0
    sub_total_encours = 0
    sub_total_h_done = sub_total_h_planned = 0
    sub_total_to_facture = 0

    row = 1
    first_row = True
    row_in_order = 0

    mainlog.debug("dao.order_dao.order_parts_for_monthly_report(month_date):")
    for part_data  in dao.order_dao.order_parts_for_monthly_report(month_date):

        if last_order_id != part_data.order_id:

            last_order_id = part_data.order_id

            if not first_row and row_in_order >= 2:
                # Display sums only if there is more than one row
                # for the order (if only one row, then showing a
                # sum doesn't add any information to the user)

                ts.add('LINEABOVE', (5, row), (-1, row), 0.5, colors.black)
                ts.add('LINEABOVE', (2, row), (2, row), 0.5, colors.black)
                data_ops.append(['', '',
                                 Paragraph('{} / {}'.format(duration_to_s(sub_total_h_done), duration_to_s(sub_total_h_planned)),small_right),
                                 '',
                                 '', # Paragraph(amount_to_short_s(sub_total_sell_price) or "0,00" ,right_align),
                                 Paragraph(amount_to_short_s(sub_total_to_facture) or "0,00",right_align_bold),
                                 Paragraph(amount_to_short_s(sub_total_encours) or "0,00",right_align)])
                row += 1

            sub_total_sell_price = 0
            sub_total_encours = 0
            sub_total_h_done = sub_total_h_planned = 0
            sub_total_to_facture = 0
            row_in_order = 0

            ts.add('LINEABOVE', (0, row), (-1, row), 0.5, colors.black)
            data_ops.append(['', Paragraph(part_data.customer_name, client), '', '', '', '', ''])
            row += 1

        facture_explain = ""
        q_out_this_month = part_data.part_qty_out - part_data.q_out_last_month
        # Only give an explanation if all the qty were not done
        # together
        if part_data.q_out_last_month > 0 and q_out_this_month > 0 and q_out_this_month < part_data.qty:
            facture_explain = "({}) ".format(q_out_this_month)

        if part_data.total_estimated_time > 0:
            qty_work = "{} / {}".format(duration_to_s(part_data.part_worked_hours) or "0,00",
                                        duration_to_s(part_data.total_estimated_time))
        else:
            qty_work = "-"

        if part_data.qty > 0:
            qty_str = "{} / {}".format(part_data.part_qty_out, part_data.qty)
        else:
            qty_str = "-"

        data_ops.append([Paragraph(part_data.human_identifier,small),
                         Paragraph(part_data.description,small),
                         Paragraph(qty_work,small_right),
                         Paragraph(qty_str,small_right),
                         Paragraph(amount_to_short_s(part_data.total_sell_price),right_align),
                         Paragraph(facture_explain + amount_to_short_s(part_data.bill_this_month) ,right_align_bold),
                         Paragraph(amount_to_short_s(part_data.encours),right_align)])

        # if part_data.bill_this_month or True:
        #     print("{} {} {}".format(part_data.human_identifier, part_data.part_qty_out, amount_to_short_s(part_data.bill_this_month)))

        row_in_order += 1
        row += 1

        sub_total_sell_price += total_sell_price
        sub_total_to_facture += part_data.bill_this_month
        sub_total_encours += part_data.encours

        sub_total_h_done += part_data.part_worked_hours or 0
        sub_total_h_planned += part_data.total_estimated_time or 0

        total_to_facture += part_data.bill_this_month
        total_encours += part_data.encours

        first_row = False

    data_ops.append(['', '', '', '',
                     '', # Removed total_sell_price because it is misleading
                     Paragraph(amount_to_short_s(total_to_facture),right_align_bold),
                     Paragraph(amount_to_short_s(total_encours),right_align)])

    ts.add('LINEABOVE', (0, len(data_ops)-1), (-1, len(data_ops)-1), 1, colors.black)

    ts.add('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 9)
    ts.add('LINEBELOW', (0, 0), (-1, 0), 1, colors.black)

    t = platypus.Table(data_ops,repeatRows=1,colWidths=[1.50*cm, 6*cm, 2.5*cm, 1.75*cm, 2.25*cm, 2.25*cm])


    t.setStyle(ts)
    t.hAlign = "LEFT"
    complete_document.append(t)
    complete_document.append(platypus.Spacer(0,10))

    filename = make_pdf_filename("MonthlyOverview_")
    ladderDoc = basic_PDF(filename)

    ladderDoc.subject = _("Monthly financial report")
    ladderDoc.title = date_to_my(month_date,True)

    ladderDoc.build(complete_document,canvasmaker=NumberedCanvas)
    open_pdf(filename)
    return True


if __name__ == "__main__":
    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session,session
    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)
    from koi.dao import DAO
    dao = DAO(session())
    print_monthly_report(dao,date(2015,6,15))
