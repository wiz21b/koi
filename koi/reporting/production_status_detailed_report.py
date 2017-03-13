if __name__ == "__main__":
    from koi.base_logging import init_logging
    init_logging("rlab.log")
    from koi.Configurator import configuration,mainlog,init_i18n,load_configuration
    init_i18n()
    load_configuration()



from reportlab.lib.styles import ParagraphStyle
from reportlab import platypus
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.units import cm,mm
from reportlab.lib import colors

import os
from koi.Configurator import resource_dir
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
# reportlab.rl_config.warnOnMissingFontGlyphs = 0
pdfmetrics.registerFont(TTFont('DejaVuSansMono', os.path.join(resource_dir,'DejaVuSansMono.ttf')))

from koi.datalayer.database_session import session
from koi.db_mapping import Order,OrderPart,ProductionFile,Operation,TaskOnOperation,TimeTrack,Customer,OrderStatusType
from sqlalchemy.orm import join,contains_eager,subqueryload,subqueryload_all
from koi.translators import date_to_dm,nice_round

from koi.reporting.utils import make_pdf_filename,open_pdf,basic_PDF,NumberedCanvas


def print_production_status_detailed(dao):

    strip_style = ParagraphStyle(name = "regular", fontName = 'Helvetica-Bold', fontSize=16,spaceAfter=0, spaceBefore=0)
    s = ParagraphStyle(name = "regular", fontName = 'Courrier', fontSize=7)
    order_style = ParagraphStyle(name = "regular", fontName = 'Helvetica-Bold', fontSize=14, spaceAfter=6, spaceBefore=12)
    small = ParagraphStyle(name = "regular", fontName = 'Helvetica', fontSize=8)
    right_align = ParagraphStyle(name = "right_align", fontName = 'Helvetica', fontSize=12,alignment=TA_RIGHT)
    complete_document = []
    spacer = platypus.Spacer(1,50)

    # Pay attention ! Since this query is quite big, I got correlation
    # issues. These were solved by disabling correlation on Operation.description

    # In SQLA, outerjoin = LEFT outer join (all lefts, null on right if necessary)
    # Operation.task.of_type(TaskOnOperation) : join along task over TaskOnOperation subtype (cf. SQLA documentation)
    # I also had issue when moving SQLA 8.x to 9.x. I had to replace the contains_eager(...,Operation.task.of_type(TaskOnOperation),...)
    # with contains_eager(...,Operation.task,...). A few test have shown it works, but I'm not 100% sure
    # why... I think using of_type(...) in contains_eager is faulty but SQLA didn't complain...

    # outerjoin(Operation.task.of_type(TaskOnOperation)).\
    r = session().query(Order).\
        outerjoin(OrderPart).\
        outerjoin(ProductionFile).\
        outerjoin(Operation).\
        outerjoin(TaskOnOperation).\
        outerjoin(TimeTrack).join(Customer).\
        options(contains_eager(Order.parts,OrderPart.production_file,ProductionFile.operations, Operation.tasks, TaskOnOperation.timetracks)).\
        filter(Order.state == OrderStatusType.order_ready_for_production).\
        order_by(Customer.fullname,Order.accounting_label,OrderPart.position,Operation.position).\
        all()

    orders = []
    for order in r:
        if order not in orders:
            orders.append(order)


    opdefs = dao.operation_definition_dao.all_direct()
    opdef_from_id = dict()
    for opdef in opdefs:
        opdef_from_id[opdef.short_id] = opdef

    operations_columns = 10

    data_ops = []
    data_ops.append([_("NOrd"), _("Customer (d/l-Price)")] + [ str(i) for i in range(1,operations_columns+1)]+ [_('Tot')])
    data_ops.append([_("QLft"), _("Designation")] +[''] * operations_columns + [""])

    highlights = []
    current_line = 0
    orders_separators_rows = []


    for order in orders:


        for part in order.parts:
            qty_left_to_do = part.qty - part.tex2

            if qty_left_to_do > 0 and part.operations:

                dl = "-"
                if part.deadline:
                    dl = date_to_dm(part.deadline)

                data1 = [part.human_identifier,
                         u"{} ({},{}€)".format(order.customer.fullname[0:10],
                                             dl,
                                             nice_round(part.sell_price,1) or "-")]
                data2 = [part.qty,part.description[0:26].replace('\t',' ')] # qty_left_to_do

                total_planned_hours = total_done_hours = 0
                total_planned_hours_left = 0

                for op in part.operations:
                    done_hours = 0

                    employee = None
                    multi_employee = ""

                    if op.tasks:

                        for task in op.tasks:
                            for t in task.timetracks:
                                done_hours += t.duration
                                if not employee:
                                    # We take the first employee
                                    employee = t.employee
                                elif employee != t.employee:
                                    multi_employee = "+"

                        total_done_hours += done_hours


                    if op.operation_model:
                        if not employee:
                            employee = ""
                        else:
                            employee = employee.fullname[0:2] + multi_employee

                        time_planned         = op.planned_hours * qty_left_to_do
                        total_planned_hours_left += time_planned
                        total_planned_hours += op.planned_hours * part.qty

                        data1.append(u"{}-{}".format(op.operation_model.short_id, nice_round(time_planned,10)))
                        data2.append(u"{} {}".format(employee,nice_round(done_hours,10)))

                        if done_hours > time_planned:
                            r,c=len(data_ops)+1,len(data1)-1
                            highlights.append( (c,r,c,r) )

                    if len(data1) >= 2 + operations_columns:
                        # Too many operations for one line, so I break the line.
                        data_ops.append(data1)
                        data_ops.append(data2)

                        data1 = ["","--->"]
                        data2 = ["","--->"]

                r = 2 + operations_columns - len(data1)
                if r > 0:
                    data1 += [""]*r
                    data2 += [""]*r

                data1.append(nice_round(total_planned_hours_left,1))
                data2.append(nice_round(total_done_hours,1))

                if total_done_hours > 0 and total_done_hours >= 0.6*total_planned_hours:
                    c = len(data2) - 1
                    r = len(data_ops) + 1
                    highlights.append( (c,r,c,r) )


                data_ops.append(data1)
                data_ops.append(data2)

        orders_separators_rows.append(len(data_ops) - 1)

    t = platypus.Table(data_ops,repeatRows=2)
    ts = platypus.TableStyle([('FONT', (0, 0), (-1, -1), 'Courier', 8)])
    ts.add("LEFTPADDING", (0, 0), (-1, -1), 0.5*mm)
    ts.add("RIGHTPADDING", (0, 0), (-1, -1), 0.5*mm)
    ts.add("TOPPADDING", (0, 0), (-1, -1), 1*mm)
    ts.add("BOTTOMPADDING", (0, 0), (-1, -1), 1*mm)
    ts.add('INNERGRID', (0, 0), (-1, -1), 0.5, colors.gray)
    ts.add('ALIGN', (2, 0), (-1, -1), 'RIGHT')

    ts.add('FONT', (0, 0), (-1, 1), 'Courier-Bold', 8)

    ts.add('BOX', (0, 0), (0, -1), 1, colors.black)
    ts.add('BOX', (1, 0), (1, -1), 1, colors.black)

    ts.add('BOX', (-1, 0), (-1, -1), 1, colors.black) # Totals
    ts.add('BOX', (0, 0), (-1, 1), 1, colors.black) # Header
    ts.add('BOX', (0, 0), (-1, -1), 1, colors.black)
    ts.add('BACKGROUND', (0, 0), (-1, 1), (0.9,0.9,0.9))


    for i in range(int(len(data_ops) / 2)):
        if i % 2 == 0:
            # ts.add('BOX',        (0, i*2), (-1, i*2+1), 1, colors.black)
            ts.add('BACKGROUND', (0, i*2), (-1, i*2+1), (0.95,0.95,0.95))

    for h in highlights:
        ts.add('BOX', (h[0], h[1]), (h[2], h[3]), 2, colors.black)

    for i in orders_separators_rows:
        ts.add('LINEBELOW', (0, i), (-1, i), 1, colors.black)

    t.setStyle(ts)
    t.hAlign = "LEFT"
    complete_document.append(t)
    complete_document.append(platypus.Spacer(0,10))

    session().close()

    filename = make_pdf_filename("ProductionDetails_")
    ladderDoc = basic_PDF(filename)

    ladderDoc.title = ""
    ladderDoc.subject = _("Order production details")

    ladderDoc.build(complete_document,canvasmaker=NumberedCanvas)
    open_pdf(filename)
    return True


if __name__ == "__main__":
    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session,session
    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)
    from koi.dao import DAO
    import logging
    #mainlog.setLevel(logging.DEBUG)
    dao = DAO()
    dao.set_session(session())
    print_production_status_detailed(dao)
