if __name__ == "__main__":
    from koi.base_logging import init_logging
    init_logging("rlab.log")
    from koi.Configurator import configuration,mainlog,init_i18n,load_configuration
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
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.lib.units import cm,mm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.barcode import createBarcodeDrawing

from reportlab.platypus import KeepTogether
from reportlab.platypus.flowables import PageBreak

from koi.Configurator import resource_dir,mainlog
pdfmetrics.registerFont(TTFont('DejaVuSansMono', os.path.join(resource_dir,'DejaVuSansMono.ttf'))) # FIXME

from koi.dao import dao
from koi.reporting.utils import make_pdf_filename,open_pdf,basic_PDF,NumberedCanvas
from koi.datalayer.audit_trail_service import audit_trail_service
from koi.translators import crlf_to_br,time_to_timestamp
from koi.BarCodeBase import BarCodeIdentifier
from koi.machine.machine_mapping import Machine
from koi.machine.machine_service import machine_service

from collections import OrderedDict


def group_by_attribute(objs, attribute):
    sm = dict()

    # Group machines per attribute

    for m in objs:
        a = getattr(m, attribute)

        if a not in sm:
            sm[a] = []

        sm[a].append(m)

    return sm



def sort_machines(machines):

    # Map id to data
    opdefs = group_by_attribute( dao.operation_definition_dao.all_frozen(), 'operation_definition_id')


    # Group machines per clock_zone and operation definition_id

    sm = group_by_attribute( machines, 'clock_zone')
    for k,v in sm.items():
        sm[k] = group_by_attribute( v, 'operation_definition_id')

    out = dict()

    for zone, machines_by_opdef in sm.items():
        if not zone:
            zone = ""

        out[zone] = dict()

        for opdefid, mlist in machines_by_opdef.items():
            opdef_name = u"<b>{}</b> {}".format(opdefs[opdefid][0].short_id,
                                                opdefs[opdefid][0].description) # group by attribute produces arrays => [0]
            out[zone][opdef_name] = mlist



    # sorted(sm[k], key=lambda n:n.fullname)

    return out



# def sort_machines(machines):

#     sm = dict()

#     for m in machines:
#         if m.operation_definition_id not in sm:
#             sm[m.operation_definition_id] = []

#         sm[m.operation_definition_id].append(m)

#     r = OrderedDict()

#     opdefs = dict() # id -> names

#     for k in sorted( sm.keys()):

#         if k not in opdefs:
#             opdef = dao.operation_definition_dao.find_by_id_frozen(k)
#             opdefs[k] = _("{} {}").format(opdef.short_id, opdef.description)

#         r[opdefs[k]] = sorted(sm[k], key=lambda n:n.fullname)

#     return r



def print_machines_barcodes():
    global header_text
    global sub_header_text

    s = ParagraphStyle(name = "zou", fontName = 'Helvetica', fontSize=14, alignment=TA_CENTER)
    title_style = ParagraphStyle(name = "regular", fontName = 'Helvetica', fontSize=24, spaceBefore=34, spaceAfter=34)
    zone_style = ParagraphStyle(name = "zone-style", fontName = 'Helvetica-Bold', fontSize=24, spaceBefore=34, spaceAfter=34)

    badges_per_line = 3

    smachines = sort_machines(machine_service.all_machines())


    # I need an instance to call barcode identifier
    barcode_machine = Machine()

    if len(smachines) == 0:
        return

    complete_document = []
    for clock_zone in sorted(smachines.keys()):

        complete_document.append( Paragraph(u">>> {}".format(clock_zone or _("Without zone")), zone_style))

        machines = smachines[clock_zone]

        if not machines:
            continue

        for operation_name, machines in machines.items():

            array = []
            row = []
            i = 0
            for machine in machines:

                barcode_machine.resource_id = machine.resource_id
                bc = createBarcodeDrawing('EAN13',value=str(BarCodeIdentifier.code_for(barcode_machine)),
                                          width=5.5*cm, barHeight=1.5*cm)

                row.append( [ Paragraph(u"{}".format(machine.fullname),s),
                              platypus.Spacer(0,0.25*cm),
                              bc ])
                i = i + 1
                if i == badges_per_line:
                    array.append(row)
                    row = []
                    i = 0

            # Handle the last non complete row
            if i > 0:
                array.append(row)

            t = platypus.Table(array, repeatRows=0, colWidths=[6.5*cm]*badges_per_line,
                               rowHeights=[3*cm]*len(array))

            ts = platypus.TableStyle([('FONT', (0, 0), (-1, -1), 'Helvetica', 8)])
            ts.add('ALIGN', (0, 0), (-1, -1), 'CENTER')
            ts.add('VALIGN', (0, 0), (-1, -1), 'MIDDLE')

            ts.add("LEFTPADDING", (0, 0), (-1, -1), 0)
            ts.add("RIGHTPADDING", (0, 0), (-1, -1), 0)
            ts.add('INNERGRID', (0,0), (-1,-1), 0.25, colors.black)
            ts.add('BOX', (0,0), (-1,-1), 0.25, colors.black)

            t.setStyle(ts)

            complete_document.append( KeepTogether([Paragraph(operation_name, title_style),
                                                    t]))

        # complete_document.append( Paragraph(_("Operation {}").format(opid), title_style))
        # complete_document.append(t)
        complete_document.append(PageBreak())

    filename = make_pdf_filename("MachineBarcodes_")
    ladderDoc = basic_PDF(filename)
    ladderDoc.title = ""
    ladderDoc.subject = _(u"Machines bar codes")

    ladderDoc.build(complete_document,canvasmaker=NumberedCanvas)
    open_pdf(filename)

if __name__ == "__main__":
    print_machines_barcodes()
