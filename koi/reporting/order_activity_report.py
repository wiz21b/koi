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

from reportlab.lib.styles import ParagraphStyle
from reportlab import platypus
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from koi.base_logging import mainlog
from koi.datalayer.database_session import session
from koi.dao import dao
from koi.reporting.utils import NumberedCanvas, escape_html,split_long_string,make_pdf_filename,open_pdf,basic_PDF, \
    smart_join
from koi.Configurator import resource_dir
from koi.translators import date_to_dmy, time_to_timestamp, duration_to_hm

# reportlab.rl_config.warnOnMissingFontGlyphs = 0
pdfmetrics.registerFont(TTFont('DejaVuSansMono', os.path.join(resource_dir,'DejaVuSansMono.ttf')))


def _make_iso_status(dao,order_id):

    global header_text,sub_header_text


    strip_style = ParagraphStyle(name = "regular", fontName = 'Helvetica-Bold', fontSize=16,spaceAfter=0, spaceBefore=0)
    s = ParagraphStyle(name = "regular", fontName = 'Helvetica', fontSize=12, spaceAfter=6)

    # s = getSampleStyleSheet()['BodyText']

    title_style = ParagraphStyle(name = "regular", fontName = 'Helvetica-Bold', fontSize=16, spaceAfter=24, spaceBefore=24)
    order_style = ParagraphStyle(name = "regular", fontName = 'Helvetica-Bold', fontSize=14, spaceAfter=6, spaceBefore=12)
    small = ParagraphStyle(name = "regular", fontName = 'Helvetica', fontSize=8)
    right_align = ParagraphStyle(name = "right_align", fontName = 'Helvetica', fontSize=12,alignment=TA_RIGHT)

    complete_document = []
    spacer = platypus.Spacer(1,50)

    metadata, timetracks = dao.order_dao.load_order_timetracks(order_id)
    issues = dao.quality_dao.find_by_order_id(order_id)

    header_text = u"{} [{}]".format(metadata['customer_name'], metadata['customer_order_name'])
    sub_header_text = _("Order activity report")

    # complete_document.append(Paragraph(_("Order information"),title_style))


    complete_document.append(Paragraph(_("Customer : {}").format(metadata['customer_name']),s))
    complete_document.append(Paragraph(_("Order number : {} (Horse ID:{})").format(metadata['accounting_label'] or "-", metadata['horse_order_id']),s))
    complete_document.append(Paragraph(_("Preorder number : {}").format(metadata['preorder_label'] or "-"),s))
    complete_document.append(Paragraph(_("Customer number : {}").format(metadata['customer_order_name']),s))
    complete_document.append(Paragraph(_("Creation date : {}").format(date_to_dmy(metadata['creation_date'])),s))
    complete_document.append(Paragraph(_("Completion : {}").format(date_to_dmy(metadata['completed_date'])),s))
    complete_document.append(Paragraph(_("Current state : {}").format(metadata['state'].description),s))

    complete_document.append(Paragraph(_("Activity synthesis"),title_style))

    ts = platypus.TableStyle([('FONT', (0, 0), (-1, -1), 'Helvetica', 12)])
    tdata= []
    # tdata.append([None, _("Order part")])

    for part_id, part_desc, part_state, part_completed_date, employee_timetracks, order_part_id in timetracks:

        row = [part_id,
               Paragraph( "<b>{}</b>".format(escape_html( split_long_string(part_desc) + " (" + smart_join([part_state.description,
                                                                                         date_to_dmy(part_completed_date)]) + ")")),s)]
        tdata.append(row)
        row_ndx = len(tdata)-1
        ts.add('BOX', (0,row_ndx), (-1,row_ndx), 1, colors.black)
        ts.add('BACKGROUND', (0, row_ndx), (-1, row_ndx), colors.Color(0.8,0.8,0.8))

        if employee_timetracks:
            # dunno why, ordered dicts are not ordered anymore when iterated over their '.items()'
            for employee in sorted(employee_timetracks.keys()):
                tt = employee_timetracks[employee]

                # mainlog.debug("employee : {}".format(employee))
                # mainlog.debug(timetracks[0])

                row = [None, None]
                row[1] = Paragraph( u"{} : {}".format(employee,
                                                    u"; ".join( map(lambda z: u"{} {} <b>{}</b>".format(z[0], date_to_dmy(z[1]), duration_to_hm(z[2]) ),tt))), s)
                tdata.append(row)
        else:
            tdata.append(["",_("No work reported")])


        for issue in issues:
            if issue.order_part_id == order_part_id:
                name = "?"
                if issue.who:
                    name = issue.who.fullname

                row = [ Paragraph( _("<b>QUAL !</b>"), s),
                        Paragraph( _("<b>{}</b> on {} by {} : {}").format(
                            issue.human_identifier, date_to_dmy(issue.when), escape_html(name), escape_html(issue.description) ),
                            s) ]
                tdata.append(row)


    # ts.add('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 12)

    # ts.add('INNERGRID', (0, 0), (-1, -1), 0.5, colors.black)
    ts.add('BOX', (0,0), (-1,-1), 0.25, colors.black)

    ts.add('ALIGN', (0, 0), (-1, -1), 'LEFT')
    ts.add('VALIGN', (0, 0), (-1, -1), 'TOP')

    ts.add("LEFTPADDING",  (0, 0), (0, -1), 0)
    ts.add("RIGHTPADDING", (1, 0), (-1, -1), 0)

    if tdata:
        t = platypus.Table(tdata, repeatRows=0, colWidths=[2*cm,17.5*cm])
        t.setStyle(ts)
        complete_document.append(t)

    complete_document.append(Paragraph(_("Delivery slips"),title_style))

    slips = dao.order_dao.find_by_id(order_id).delivery_slips()
    if not slips:
        complete_document.append(Paragraph( _("There are no delivery slip"),s))

    for slip in slips:

        if slip.active:
            complete_document.append(Paragraph( _("Delivery slip {} created on {}").format(slip.delivery_slip_id, date_to_dmy(slip.creation)),s))

            for ds_part in sorted(slip.delivery_slip_parts, key=lambda p:p.order_part.label):
                complete_document.append(Paragraph( _("{} : {} unit(s)").format(ds_part.order_part.label, ds_part.quantity_out),s))
        else:
            complete_document.append(Paragraph( _("Delivery slip {} DESACTIVATED").format(slip.delivery_slip_id),s))


    complete_document.append(Paragraph(_("Quality"),title_style))

    if not issues:
        complete_document.append(Paragraph( _("There are no quality issues"),s))
    else:
        for issue in issues:
            name = "?"
            if issue.who:
                name = issue.who.fullname
            complete_document.append(Paragraph( _("Issue <b>{}</b> created on {} by {} : {}").format(
                issue.human_identifier, date_to_dmy(issue.when), escape_html(name), escape_html(issue.description) ),
                s))


    def order_number_title(preorder_number, order_number, customer_number):
        t = []

        if order_number:
            t.append(str(order_number))

        if preorder_number:
            t.append(_("Preorder {}").format(preorder_number))

        # Would' be nice but takes way too much width on the paper
        # if customer_number:
        #     t.append(str(customer_number) + "lkjlkj  lkj  ///SDFSF")

        return u" / ".join(t)

    return order_number_title(metadata['preorder_label'],
                              metadata['accounting_label'],
                              metadata['customer_order_name']), complete_document

def _print_iso_status(dao,order_id,filename):
    """ This function is separated to allow for testing.

    :param dao:
    :param order_id:
    :param filename:
    :return:
    """
    order_title, complete_document = _make_iso_status(dao,order_id)

    ladderDoc = basic_PDF(filename)

    ladderDoc.title = _("Order Activity Report")
    ladderDoc.subject = order_title

    ladderDoc.build(complete_document,canvasmaker=NumberedCanvas)

def print_iso_status(dao,order_id):
    filename = make_pdf_filename("ISOReport_")
    _print_iso_status(dao,order_id,filename)
    open_pdf(filename)




if __name__ == "__main__":
    from koi.dao import DAO
    dao = DAO(session())
    print_iso_status(dao, dao.order_dao.find_by_preorder_label(5156).order_id) # 5256 with long lines
    # print_iso_status(dao, dao.order_dao.find_by_accounting_label(5563).order_id) # 5256 with long lines
