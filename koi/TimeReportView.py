from datetime import timedelta

from PySide.QtCore import Qt, QLineF, QPointF
from PySide.QtGui import QGraphicsScene, QGraphicsView, QGraphicsSimpleTextItem, QFont, QBrush,QPen,QGraphicsItem, \
    QGraphicsLineItem,QGraphicsRectItem,QPainterPath,QLinearGradient,QGradient,QColor,QGraphicsPathItem
from PySide.QtCore import QRect

from koi.Configurator import mainlog
from koi.db_mapping import TaskOnOperation, TaskActionReportType, TaskOnOrder, TaskOnNonBillable
from koi.dao import dao
from koi.translators import time_to_hm,duration_to_hm
from koi.datalayer.tools import day_span


class HooverBar(QGraphicsRectItem):

    def __init__(self,*args):
        super(HooverBar,self).__init__(*args)
        self.setAcceptHoverEvents(True)
        self.gi = None
        self.description = [ "" ]
        self.base_font = QFont()
        self.setPen(QPen(Qt.transparent))

    def hoverEnterEvent(self,event):
        super(HooverBar,self).hoverEnterEvent(event)

        if self.gi == None:
            self.gi = QGraphicsRectItem(0, 0, 100, 100)
            self.gi.setBrush(QBrush(QColor(0,64,0,192)))
            self.gi.setPen(QPen(Qt.transparent))
            self.gi.setPos(event.scenePos().x() + 20,event.scenePos().y() + 20)

            x = y = 10
            w = 0
            for t in self.description:
                description = QGraphicsSimpleTextItem()
                description.setFont(self.base_font)
                description.setBrush(QBrush(Qt.white))
                description.setText(t)
                description.setParentItem(self.gi)
                description.setPos(x,y)
                y += description.boundingRect().height()
                w = max(w,description.boundingRect().width())
            y += x
            w += 2*x

            self.gi.setRect(0,0,w,y)
            self.scene().addItem(self.gi)


    def hoverMoveEvent(self,event):
        super(HooverBar,self).hoverMoveEvent(event)

        # if self.gi:
        #     mainlog.debug("hoverMoveEvent GI pos={}-{}".format(self.gi.pos().x(),self.gi.pos().y()))
        # mainlog.debug("hoverMoveEvent pos={}-{}".format(event.scenePos().x(),event.scenePos().y()))
        if self.gi:
            self.gi.setPos(event.scenePos().x() + 20,event.scenePos().y() + 20)


    def hoverLeaveEvent(self,event):
        super(HooverBar,self).hoverLeaveEvent(event)

        if self.gi:

            # QtDoc : Removes the item item and all its children from the scene.
            #         The ownership of item is passed on to the caller

            self.gi.setParentItem(None)
            # self.scene().removeItem(self.gi)
            self.gi = None
            # mainlog.debug("hoverLeaveEvent -- done")



def glass_path(scene,x,y,w,h,colr):

    qp = QPainterPath()
    qp.addRoundedRect(x, y, w, h, 5, 5)

    gradient = QLinearGradient(0,+0,0,1)
    gradient.setCoordinateMode(QGradient.ObjectBoundingMode)
    gradient.setColorAt(0,colr)
    gradient.setColorAt(1,colr.lighter(150))
    brush = QBrush(gradient)

    item = QGraphicsPathItem()
    item.setPath(qp)
    item.setBrush(brush)
    scene.addItem(item)

    # Draw glass reflection

    glass = QPainterPath()
    r = 3
    glass.addRoundedRect(x+r,y+r,w - 2*r,2*r,r,r)

    gradient = QLinearGradient(0,+0,0,1)
    gradient.setCoordinateMode(QGradient.ObjectBoundingMode)
    gradient.setColorAt(0,QColor(255,255,255,188))
    gradient.setColorAt(1,QColor(255,255,255,0))
    brush = QBrush(gradient)

    item = QGraphicsPathItem()
    item.setPath(glass)
    item.setBrush(brush)
    item.setPen(QPen(Qt.transparent))
    scene.addItem(item)



class MyQGraphicsSimpleTextItem(QGraphicsSimpleTextItem):
    def __init__(self,state,dialog):
        super(MyQGraphicsSimpleTextItem,self).__init__(state.description)
        self.state = state
        self.dialog = dialog

    def mouseDoubleClickEvent(self,event): # QGraphicsSceneMouseEvent
        self.dialog.save_and_accept()


class Timeline(object):
    START = 1
    END = 2
    NO_DIR = 0

    def __init__(self,base_time,flags,spans,task,task_name,span_color):
        self.span_color = span_color
        self.base_time = base_time
        self.flags = flags or []
        self.spans = spans or []
        self.task = task
        self.task_name = task_name
        self.grey_pen = QPen(Qt.gray)

    def time_to_x(self,t):
        if t > self.base_time:
            delta = t - self.base_time
            return delta.seconds / 3600.0 * 75.0
        else:
            delta = self.base_time - t
            return - delta.seconds / 3600.0 * 75.0

    def draw(self,scene,y):
        span_height = 15
        flag_height = span_height * 1.2

        min_time, max_time = day_span(self.base_time)

        # Draw a time line

        nb_hours = 12

        length = self.time_to_x(self.base_time + timedelta(float(nb_hours)/24.0))
        scene.addLine ( QLineF(0, y, length, y), QPen(Qt.gray) )

        x = self.base_time - timedelta(0,seconds=self.base_time.second, minutes=self.base_time.minute, microseconds=self.base_time.microsecond )
        end_x = self.base_time + timedelta(hours=12)

        while x <= end_x:
            tx = self.time_to_x(x)
            scene.addLine ( QLineF(tx, y - 5, tx, y + 5), QPen(Qt.gray) )

            description = QGraphicsSimpleTextItem()
            description.setText(str(x.hour))
            description.setPos(tx+5,y) # y - br.height()/2)
            description.setBrush(QBrush(Qt.gray))
            scene.addItem(description)

            x = x + timedelta(hours=1)


        # Draw spans

        total_time = timedelta(0)

        for start,end,description in self.spans:

            mainlog.debug("Span : {} -> {}".format(start, end))
            s = self.time_to_x( max(min_time, start))
            e = self.time_to_x( min(max_time, end))
            total_time += end - start

            # mainlog.debug("Total time += {}".format(end - start))

            glass_path(scene,s,y-span_height/2,e-s,span_height,QColor(self.span_color))

            r = HooverBar(QRect(s,y-span_height/2,e-s,span_height),None)

            if not description:
                r.description = [_("Duration"), duration_to_hm((end - start).total_seconds() / 3600.0)]
            elif isinstance(description,list):
                r.description = description
            else:
                r.description = [description]

            scene.addItem(r)


        # Make the timeline clickable

        r = QGraphicsRectItem(QRect(0,0,length,30),None)
        scene.addItem(r)
        r.setPos(0,y-15)
        r.setPen(QPen(Qt.transparent))
        r.setCursor(Qt.PointingHandCursor)
        r.setFlags( r.flags() | QGraphicsItem.ItemIsSelectable)
        r.setData(0,self.task)


        # Draw flags

        for t,kind,data,hoover_text in self.flags:
            x = self.time_to_x(t)

            # mainlog.debug("Drawing a flag on {} at {}".format(t,x))

            l = QGraphicsLineItem(0.0,float(-flag_height),0.0,float(+flag_height),None)
            l.setPen(QPen(Qt.black))
            scene.addItem(l)
            l.setPos(x,y)

            #scene.addLine ( QLineF(x,y-flag_height,x,y+flag_height), QPen(Qt.black) )

            if kind == Timeline.START:
                scene.addRect ( QRect(x,y-flag_height,5,5), QPen(Qt.black), QBrush(Qt.black))
                scene.addRect ( QRect(x,y+flag_height-5,5,5), QPen(Qt.black), QBrush(Qt.black))
            elif kind == Timeline.END:
                scene.addRect ( QRect(x-5,y-flag_height,5,5), QPen(Qt.black), QBrush(Qt.black))
                scene.addRect ( QRect(x-5,y+flag_height-5,5,5), QPen(Qt.black), QBrush(Qt.black))

            r = HooverBar(QRect(0,0,10,2*flag_height),None)
            r.description = hoover_text
            scene.addItem(r)

            r.setPos(x-5,y-flag_height)
            r.setPen(QPen(Qt.transparent))
            # item = scene.addRect ( QRect(x-5,y-flag_height,10,2*flag_height), QPen(Qt.white))
            r.setCursor(Qt.PointingHandCursor)
            r.setFlags( r.flags() | QGraphicsItem.ItemIsSelectable)
            r.setData(0,data)


        # Timeline's text

        description = QGraphicsSimpleTextItem()

        duration = ""
        if total_time.seconds > 60 or total_time.days > 0:
            duration = " - " + duration_to_hm(total_time.total_seconds() / 3600.0)

        tname = self.task_name.replace('\n',' ')
        if len(tname) > 80:
            tname = tname[0:80] + u"..."

        description.setText( u"{}{}".format(tname,duration))
        br = QRect(0,0,description.boundingRect().width(), description.boundingRect().height())
        description.setPos(0,y- br.height() - flag_height) # y - br.height()/2)

        r = QGraphicsRectItem(QRect(0,0,br.width() + 10,br.height() + 10),None)
        r.setPos(-5,y-5- br.height() - flag_height) # y - br.height()/2 - 5)
        r.setPen(QPen(Qt.transparent))
        r.setBrush(QBrush(QColor(255,255,255,128)))

        scene.addItem(r)
        scene.addItem(description)


class TimeReportView(QGraphicsView):

    def __init__(self,parent):
        super(TimeReportView,self).__init__(parent)
        self.title_font = QFont("Arial",12,QFont.Normal)

    def _hoover_text_for(self,tar):
        mainlog.debug("TAR.time = {} --> {}".format(tar.time, time_to_hm(tar.time)))
        hoover_text = [_("On {}").format(time_to_hm(tar.time))]
        if tar.editor:
            hoover_text.append(_("Edited by {}").format(tar.editor))
        return hoover_text


    def _make_time_line_title(self, task):
        timeline_title = ""
        if isinstance(task,TaskOnOperation):
            timeline_title = u"{}: {} {}".format(task.operation.production_file.order_part.human_identifier,
                                                 task.operation.operation_model.description,
                                                 task.description)
            if task.machine_id:
                timeline_title += _(", on {}").format(machine_service.find_machine_by_id(task.machine_id).fullname)

        elif isinstance(task,TaskOnOrder):
            timeline_title = u"{}: {} {}".format(task.order.label,
                                                 task.operation_definition.description,
                                                 task.description)
        elif isinstance(task,TaskOnNonBillable):
            timeline_title = task.operation_definition.description

        else:
            mainlog.error("Unrecognized task : {}".format(type(task)))
            return task.description

        return timeline_title


    def redraw(self,base_time,all_tars,employee_id,additional_work_timetracks,
               additional_presence_timetracks,special_activities=None, view_title=""):

        scene = QGraphicsScene()

        # This scene line is a hack to make sure I can control the "centerOn"
        # execution as I wish. This is very hackish.
        margin = 30
        scene.addLine ( QLineF(0, 0, self.width() - margin, self.height() - margin), QPen(Qt.white) )

        # Dat is heeeel belangerijk om de goede computation te doen
        all_tars = sorted(all_tars, key=lambda tar:tar.time)

        # chrono.chrono_click("Redraw step 1")
        timetracks_tars = dao.task_action_report_dao.compute_activity_timetracks_from_task_action_reports( all_tars, employee_id)

        # We got (timetrack, reports) tuples
        timetracks = [tt[0] for tt in timetracks_tars]

        # presence_time, off_time, presence_timetracks = dao.task_action_report_dao.recompute_presence_on_tars(employee_id, all_tars)

        # chrono.chrono_click("Redraw step 2")

        presence_intervals = dao.task_action_report_dao.compute_man_presence_periods(employee_id, base_time, all_tars, timetracks = [], commit=True)

        # chrono.chrono_click("Redraw step 2B")

        presence_timetracks = dao.task_action_report_dao.convert_intervals_to_presence_timetracks(presence_intervals, employee_id)

        # chrono.chrono_click("Redraw step 3")


        # FIXME this will trigger a session open... Must use the ID without a query first!
        presence_task_id = dao.task_action_report_dao.presence_task_id_regular_time()
        # chrono.chrono_click("redraw")

        # mainlog.debug("About to draw ...")
        # mainlog.debug("additional presence is")
        # for tt in additional_presence_timetracks:
        #     mainlog.debug(tt)

        # mainlog.debug("all_tars")
        # mainlog.debug(all_tars)
        # mainlog.debug("Timetracks...")
        # mainlog.debug(timetracks_tars)
        # mainlog.debug("Presenec Timetracks...")
        # mainlog.debug(presence_timetracks)



        if presence_timetracks == [] and additional_presence_timetracks:
            presence_timetracks += additional_presence_timetracks
        timetracks += additional_work_timetracks

        # mainlog.debug("Augmented  Timetracks...")
        # mainlog.debug(timetracks)
        # mainlog.debug("Augmented Presence Timetracks...")
        # for tt in presence_timetracks:
        #     mainlog.debug(tt)

        y = 0
        dy = 60

        # Title of the view

        if view_title:
            description = QGraphicsSimpleTextItem()
            description.setText( view_title)
            description.setFont( self.title_font)

            br = QRect(0,0,description.boundingRect().width(), description.boundingRect().height())
            description.setPos(0,0) # y - br.height()/2)
            scene.addItem(description)
            y += max( br.height()*2, dy)

        # Presence timeline

        pointages = []
        for tar in all_tars:
            # mainlog.debug(tar)
            # mainlog.debug(tar.kind == TaskActionReportType.presence)

            if tar.kind == TaskActionReportType.presence:
                pointages.append( (tar.time, Timeline.NO_DIR, tar, self._hoover_text_for(tar)) )
            elif tar.kind in (TaskActionReportType.day_in, TaskActionReportType.start_task):
                pointages.append( (tar.time, Timeline.START, tar, self._hoover_text_for(tar)) )
            elif tar.kind in (TaskActionReportType.day_out, TaskActionReportType.stop_task):
                pointages.append( (tar.time, Timeline.END, tar, self._hoover_text_for(tar)) )
            else:
                raise Exception("Unsupported TAR.kind. I get {}".format(tar.kind))

        periods = []
        for tt in presence_timetracks:
            periods.append( (tt.start_time, tt.start_time + timedelta(tt.duration/24.0), None))

        # Show the presence timeline

        pointages_for_presence = [p for p in pointages if p[2].kind not in (TaskActionReportType.start_task, TaskActionReportType.stop_task) ]

        if pointages_for_presence:
            tl = Timeline( base_time, pointages_for_presence, periods, None, _("Presence"), QColor(Qt.green).darker(150))
            tl.draw(scene,y)
            y += dy

        # Special activities time line

        if special_activities:
            periods = []
            for sa in special_activities:
                desc = None
                if sa.activity_type:
                    desc = sa.activity_type.description
                periods.append( (sa.start_time, sa.end_time, desc) )
            tl = Timeline( base_time, None, periods, None, _("Absence"), QColor(Qt.red).darker(150))
            tl.draw(scene,y)
            y += dy


        # Group task action reports according to their task

        task_tar = dict()
        for tar in all_tars:
            task_id = tar.task_id

            if task_id and task_id != presence_task_id:
                if not task_id in task_tar:
                    task_tar[task_id] = []

                if tar.kind == TaskActionReportType.start_task:
                    task_tar[task_id].append( (tar.time, Timeline.START, tar, self._hoover_text_for(tar)) )
                elif tar.kind == TaskActionReportType.stop_task:
                    task_tar[task_id].append( (tar.time, Timeline.END, tar, self._hoover_text_for(tar)) )

        # Group timetracks according to their task

        task_to_timetracks = dict()
        for timetrack in timetracks:
            task_id = timetrack.task_id
            if task_id and task_id != presence_task_id:
                if not task_id in task_to_timetracks:
                    task_to_timetracks[task_id] = []
                task_to_timetracks[task_id].append( timetrack )

        # Figure out all the tasks (because each task gives a timeline)
        # It is quite possible that some timetracks are not associated
        # to any TAR and vice versa.

        all_tasks = set()
        for t in timetracks:
            if t.task_id:
                all_tasks.add(t.task_id)

        for t in all_tars:
            if t.task_id:
                all_tasks.add(t.task_id)

        all_tasks = dao.task_dao.find_by_ids_frozen(all_tasks)

        # map(lambda t:t.task and all_tasks.add(t.task),timetracks)
        # map(lambda t:t.task and all_tasks.add(t.task),all_tars)

        # The presence stuff was drawn on a separate timeline => we won't draw
        # it here again.

        # Remove presence task (because it's already drawn).
        # FIXME I use the ID because of session handling

        all_tasks = list(filter(lambda t:t.task_id != presence_task_id, all_tasks))

        for task in list(sorted(all_tasks, key=lambda a: a.description)):

            # Not all TAR have a timetrack !
            periods = []
            if task.task_id in task_to_timetracks:
                for tt in task_to_timetracks[task.task_id]:
                    periods.append( (tt.start_time, tt.start_time + timedelta(tt.duration/24.0), None))

            tars = []
            if task.task_id in task_tar:
                tars = task_tar[task.task_id]

            timeline_title = task.description
            # timeline_title = self._make_time_line_title(task) # This will provide nice and complete bar titles

            if task.type == TaskOnOperation:
                tl = Timeline( base_time, tars, periods, task, timeline_title, Qt.blue)
            else:
                tl = Timeline( base_time, tars, periods, task, timeline_title, Qt.red)

            tl.draw(scene,y)
            y += dy



        self.setScene(scene)

        # See the hack top of this method !
        self.centerOn(- (self.width()-margin) / 2 , (self.height()-margin) / 2)
