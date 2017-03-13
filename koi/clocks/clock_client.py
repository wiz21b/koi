#from guppy import hpy;
#hp=hpy()

# 5000046 : Non billable

import os
import re
from datetime import date
import sys

if sys.version[0] == '3':
    pass
else:
    pass

from datetime import datetime
from PySide.QtCore import *
from PySide.QtGui import *

clock_client_id = None
if __name__ == "__main__":
    if len(sys.argv) > 1:
        clock_client_id = sys.argv[1]
    elif 'VNCDESKTOP' in os.environ:
        clock_client_id = os.environ['VNCDESKTOP']
    else:
        print("Please provide a suitable clock delivery_slips ID")
        print("It is either a command line parameter or the env. variable VNCDESKTOP")
        exit()


    from koi.base_logging import init_logging
    init_logging("clock_client_{}.log".format("_".join(clock_client_id.strip().split())))

    from koi.Configurator import init_i18n,load_configuration
    load_configuration("server.cfg")
    init_i18n()

from koi.Configurator import resource_dir

from koi.tools.chrono import *

from koi.server.MemoryLogger import MemLogger
from koi.User import User
from koi.Task import TaskSet


from koi.db_mapping import TaskActionReportType

from koi.server import ClockServer,ServerException
from koi.dao import dao
from koi.translators import duration_to_hm,time_to_hm,date_to_dm

# import gettext
# path = 'C:\PORT-STC\pl\eclipse_workspace\PL\koi\i18n'
# lang1 = gettext.translation('horse',path,languages=['en'])
# lang1.install(unicode=True)



class MainWindow(QWidget):

    WelcomeScreen = 1
    TaskSelectorScreen = 2
    TaskConfirmedScreen = 3
    ProblemScreen = 4
    UserInformationScreen = 5

    def __init__(self,clock_client_id,mem_logger,dao):
        super(MainWindow,self).__init__()

        self.clock_client_id = clock_client_id

        self.smallfont = QFont("Arial",24,QFont.Normal)
        self.smallfontbold = QFont("Arial",24,QFont.Bold)
        self.bigfont = QFont("Arial",40,QFont.Bold)
        self.thinfont = QFont("Arial",12,QFont.Normal)
        self.thinfontbold = QFont("Arial",12,QFont.Bold)
        self.ultrathinfont = QFont("Arial",10,QFont.Normal)

        self.server_direct = ClockServer(dao)

        self.mem_logger = mem_logger
        self.mem_logger.clear_errors()

        self.force_screen_update = False

        self.ongoing_tasks = None
        self.last_input_activity = datetime.now()
        self.current_user = None
        self.current_user_id = None
        self.task = None
        self.users = None
        self.tasks_set = TaskSet('http://localhost:8080',mem_logger)
        self.current_screen = self.WelcomeScreen
        self.problem = ""
        self.current_task = None
        self.record_presence = None
        # self.server = server

        self.in_carousel = None
        self.carousel_page = 0
        self.carousel_max_page = 0
        self.task_selector_page_length = 4

        self.resize(800,600)

        self.last_error = None
        self.old_screen = None
        self.current_screen = self.WelcomeScreen

        self.logo = QImage(os.path.join(resource_dir,r"logo_pl.JPG")).scaledToWidth(400)
        self.task_started_icon = QImage(os.path.join(resource_dir,r"task_started.png"))
        self.task_completed_icon = QImage(os.path.join(resource_dir,r"task_completed.png"))
        self.day_in_icon = QImage(os.path.join(resource_dir,r"day_in.png"))
        self.day_out_icon = QImage(os.path.join(resource_dir,r"day_out.png"))

        self.input = u""


        self.timer = QTimer(self)
        self.timer.timeout.connect(self.repaint) # timerUpdate)
        self.timer.start(1000)

        self.in_reload = False
        self.timer2 = QTimer(self)
        self.timer2.timeout.connect(self.reload_information) # timerUpdate)
        self.timer2.start(1000)

        # self.setAttribute(Qt.WA_PaintOnScreen) # Disable double buffering, only on X11
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setAutoFillBackground(False)



    @Slot()
    def reload_information(self):
        # print hp.heap()

        if (datetime.now() - self.last_input_activity).seconds > 10:
            self.current_user_id = self.current_user = None

            if self.current_screen != self.WelcomeScreen:
                self._moveToScreen(self.WelcomeScreen)

            # Clearing the input is important because it allows to
            # recover from an incomplete/bad barcode scan.
            self.input = ""

            self.task_selector_page = 0
        return

        self.timer2.stop()
        if self.in_reload:
            print("Too soon")
            return
        self.in_reload = True
        users = None

        # FIXME Users are downloade once !!!

        if self.users is None:
            try:
                # For some reason, if the server proxy fails once at connection
                # it will fail forever. Therefore, in case of error, I have
                # to recreate it so that it forgets the failure.

                self.server = xmlrpclib.ServerProxy('http://localhost:8080',verbose=False)
                users = self.server.usersInformation()

            except Exception as e:
                self.mem_logger.error(1,"Unable to contact the data server")

            # Make sure we don't destroy our current users list if he one we've
            # requested never came.

            if users is not None:
                self.users = dict()
                for u in users:
                    u = User.from_hash(u)
                    self.users[u.identifier] = u

        self.tasks_set.export_timetracks()
        self.tasks_set.reload()
        self.in_reload = False
        self.timer2.start(2000)



    def _startCarousel(self):
        mainlog.debug("Init carousel {} / {} = {}".format(len(self.ongoing_tasks), self.task_selector_page_length,len(self.ongoing_tasks) / self.task_selector_page_length))

        self.in_carousel = True

        self.carousel_page = 0
        self.carousel_max_page = 0

        # Since we compute a max_page, the "status page" at the end
        # of the carousel is automatically counted in.

        if self.ongoing_tasks:
            self.carousel_max_page += len(self.ongoing_tasks) / self.task_selector_page_length
            if len(self.ongoing_tasks) % self.task_selector_page_length > 0:
                self.carousel_max_page += 1

        mainlog.debug("Init carousel {} / {} = {}; max_page = {}".format(len(self.ongoing_tasks), self.task_selector_page_length,len(self.ongoing_tasks) / self.task_selector_page_length, self.carousel_max_page))


    def _moveToScreen(self,screen):
        self.old_screen = None
        self.current_screen = screen
        self.update()


    def _loadUser(self,identifier):
        try:
            h =  self.server_direct.getEmployeeInformation(identifier,self.clock_client_id,date.today())
            return h
        except ServerException as e:
            self.mem_logger.error(e.code, e.msg)
        return False

        # try:
        #     server = xmlrpclib.ServerProxy('http://localhost:8080',verbose=False)
        #     return server.getEmployeeInformation(identifier)
        # except Exception,e:
        #     self.mem_logger.error(1,"Unable to contact the data server")
        #     self.mem_logger.exception(e)


    def _setCurrentUser(self,h):
        self.current_user_id = h['employee_id']

        self.current_user = rpctools.hash_to_object(h)

        if h['picture_data']:
            image = QImage.fromData(QByteArray(str(h['picture_data'])))
            image = image.scaledToHeight(128)
            self.current_user.image = image
        else:
            self.current_user.image = None

    def _loadOngoingTasksForUser(self,identifier):
        """ Pay attention ! Returns None if there was problem
        while getting the ongoing tasks. Returns [] is there
        is no ongoing tasks to download. """

        try:
            # server = xmlrpclib.ServerProxy('http://localhost:8080',verbose=False)
            # ongoing_tasks = rpctools.hash_to_object(server.getOngoingTasksInformation(identifier))

            r = self.server_direct.getOngoingTasksInformation(identifier)
            ongoing_tasks = rpctools.hash_to_object(r)
            if ongoing_tasks is None:
                ongoing_tasks = []

            mainlog.debug("_loadOngoingTasksForUser : {} tasks".format(len(ongoing_tasks)))

            for t in ongoing_tasks:
                # details = server.getMoreTaskInformation(t.task_id)
                details = self.server_direct.getMoreTaskInformation(t.task_id)

                mainlog.debug(details)

                if details['task_type'] == 'TaskOnOperation':
                    setattr(t,'customer_name',details['customer_name'])
                    setattr(t,'description',details['description'])
                    setattr(t,'order_part_description',details['order_part_description'])
                    setattr(t,'order_id',details['order_id'])
                    setattr(t,'order_part_id',details['order_part_id'])
                    setattr(t,'order_description',details['order_description'])
                    setattr(t,'operation_definition',details['operation_definition'])
                    setattr(t,'operation_definition_short',details['operation_definition_short'])
                elif details['task_type'] == 'TaskOnNonBillable':
                    setattr(t,'description',details['description'])

            return ongoing_tasks
        except AssertionError as e:
            raise e
            self.mem_logger.error(1,"Unable to contact the data server")
            self.mem_logger.exception(e)



    def _loadTaskInformation(self,identifier):
        try:
            server = xmlrpclib.ServerProxy('http://localhost:8080',verbose=False,allow_none=True)
            h = server.getTaskInformation(identifier)
            t = rpctools.hash_to_object(h)
            details = server.getMoreTaskInformation(t.task_id)
            setattr(t,'customer_name',details['customer_name'])
            setattr(t,'description',details['description'])
            setattr(t,'order_part_description',details['order_part_description'])
            setattr(t,'order_id',details['order_id'])
            setattr(t,'order_part_id',details['order_part_id'])
            setattr(t,'order_description',details['order_description'])
            setattr(t,'operation_definition',details['operation_definition'])
            return t
        except xmlrpclib.Fault as e:
            if e.faultCode == 1000:
                self.mem_logger.error(1,_("Task doesn't exist"))
            else:
                self.mem_logger.error(9999,"Unable to contact the data server")
                self.mem_logger.exception(e)

    def _recordPointage(self,barcode,employee_id):
        # server = xmlrpclib.ServerProxy('http://localhost:8080',verbose=False)

        try:
            h = self.server_direct.recordPointage(barcode, employee_id,
                                                  datetime.strftime(datetime.now(), "%Y%m%dT%H:%M:%S"),
                                                  self.clock_client_id)
            h['task_code'] = barcode
            self.current_task = rpctools.hash_to_object(h)

            # FIXME My protocol is not nice; hash_to_object should handle
            # that itself

            self.last_action_kind = self.current_task.action_kind
            return True

        except xmlrpclib.Fault as e:
            self.mem_logger.error(e.faultCode, e.faultString)

        return False

    # def _clear_presence(self):
    #     self.presence_employee_id,self.presence_time = None,None

    # def _note_presence(self,employee_id,t):
    #     if self.presence_employee_id <> employee_id:
    #         self._push_presence(employee_id,t)
    #         self.presence_employee_id,self.presence_time = employee_id,t

    # def _push_presence(self,employee_id,t):
    #     if self.presence_employee_id:
    #         self._record_presence(self.presence_employee_id,self.presence_time)
    #         self._clear_presence()


    def _record_presence(self,employee_id,t):
        try:
            self.server_direct.recordPresence(employee_id,t,self.clock_client_id)
        except xmlrpclib.Fault as e:
            self.mem_logger.error(e.faultCode, e.faultString)



    def keyPressEvent(self,event):

        self.last_input_activity = datetime.now()

        if event.key() == Qt.Key_Backspace:
            if len(self.input) > 0:
                self.input = self.input[0:(len(self.input)-1)]
                self.update()
                return
        else:
            if event.key() not in (Qt.Key_Enter,Qt.Key_Return):
                self.input = self.input + event.text()

            if "quit" in self.input or "exit" in self.input:
                exit()
            elif (len(self.input) == 12) or (event.key() in (Qt.Key_Enter,Qt.Key_Return)):

                identifier = -1
                if not re.match("^(x|X)?[0-9]+$", self.input):
                    self.input = u""
                    self.update()
                    return
                else:
                    if (self.input[0] in ('x','X')) and len(self.input) > 1:
                        # No X, don't enter the check digit
                        identifier = int(self.input[1:len(self.input)])
                    elif len(self.input) > 1:
                        identifier = int(self.input[0:-1]) # Remove the check digit
                    else:
                        self.mem_logger.error(0,"Bad code {}".format(self.input))
                        self.input = u""
                        self.update()
                        return

                    mainlog.debug("Good bar code {}".format(identifier))
                    self.input = u""

                    mainlog.debug("Barcode without check digit : {}".format(identifier))

                    # if (self.users is not None) and ( (identifier - 99900) in self.users):
                    if identifier < 200 :

                        h = self._loadUser(identifier)
                        if h:
                            self._record_presence(h['employee_id'], datetime.now(),)

                            if self.current_user_id != h['employee_id']:
                                self._setCurrentUser(h)
                                self.ongoing_tasks = self._loadOngoingTasksForUser(identifier)
                                self._startCarousel()
                                self._moveToScreen(self.UserInformationScreen)
                            else:
                                # We should be in the task selector right now
                                # By forcing a redraw, we request the task
                                # selector to draw its next page

                                self.carousel_page += 1
                                if self.carousel_page > self.carousel_max_page:
                                    self.carousel_page = 0

                                mainlog.debug("Carousel next page {}".format(self.carousel_page))
                                self._moveToScreen(self.UserInformationScreen)
                                return

                        else:
                            # There was an error while getting the user
                            self.update()
                            return



                    elif  identifier >= 200 and self.current_user is not None:

                        if self._recordPointage(identifier, self.current_user.employee_id):
                            self.ongoing_tasks = self._loadOngoingTasksForUser(self.current_user.employee_id)
                            self._moveToScreen(self.TaskConfirmedScreen)
                            self.update()
                            self._startCarousel()

                    elif  identifier >= 200 and self.current_user is None:
                        self.mem_logger.error(0,"Please scan your identification badge before scanning a task")
                        self.update() # Froce quick refresh

            elif len(self.input) > 13:
                self.input = u""
                self.update()
                return
            elif len(self.input) < 13:
                # self.update()
                return

    def _clipToRect(self,painter,x,y,w,h):
        p = QPainterPath()
        p.moveTo(x,y)
        p.lineTo(x+w,y)
        p.lineTo(x+w,y+h)
        p.lineTo(x,y+h)

        painter.setClipping(False)
        # painter.fillRect(x-2, y-2, w+4, h+4, Qt.red)

        painter.setClipping(True)
        painter.setClipPath(p)


    def _drawTimer(self,painter):
        smallfont = QFont("Arial",20,QFont.Bold)
        bigfont = QFont("Arial",32,QFont.Bold)
        month_names = ['Jan','Fev','Mars','Avr','Mai','Juin','Juil','Aout','Sept','Oct','Nov','Dec']


        margin = 10

        # Draw date and time
        t = datetime.now()

        if True or self.old_screen is None or t.minute == 1:
            painter.setFont(smallfont)

            fm = painter.fontMetrics()
            w,h = fm.width("99 AAAA 9999"), fm.height()
            x,y = self.width() - w - margin, self.height() - 100
            self._clipToRect(painter,x,y,w,h)
            self._drawBaseFooter(painter)

            # The date
            d = "{} {} {}".format(t.day,month_names[t.month-1],t.year)
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(self.width() - fm.width(d) - margin,self.height() - 100 + fm.height() - 5,d)

        # The time
        painter.setFont(bigfont)
        fm = painter.fontMetrics()
        w,h = fm.width("99:99"), fm.height()
        x,y = self.width() - w - margin, self.height() - h - margin

        self._clipToRect(painter,x,y,w,h)
        self._drawBaseFooter(painter)

        x = self.width() - w - margin
        d = "{:0>2}".format(t.hour)

        painter.setPen(Qt.GlobalColor.white)
        painter.drawText(x,self.height()-margin - 5,d)

        x = x + painter.fontMetrics().width("99")
        if t.second % 2 == 0:
            painter.drawText(x, self.height()-margin - 5,":")

        x = x + painter.fontMetrics().width(":")
        d = "{:0>2}".format(t.minute)
        painter.drawText(x,self.height()-margin - 5,d)

        painter.setClipping(False)




    def _drawRealTimeInformation(self,painter):
        margin = 10
        bigfont = QFont("Arial",32,QFont.Bold)
        smallfont = QFont("Arial",20,QFont.Bold)

        # Draw error conditions

        err = self.mem_logger.last_error(10)

        if err != self.last_error:
            painter.setFont(smallfont)
            fm = painter.fontMetrics()
            w = fm.width("999 AAAA 9999")
            r = QRect(margin, self.height() - 100, self.width() - w, 100)

            self._clipToRect(painter,r.x(),r.y(),r.width(),r.height())
            self._drawBaseFooter(painter)

            if err:
                painter.setPen(Qt.GlobalColor.red)
                painter.drawText(r,Qt.AlignLeft | Qt.TextWordWrap, u"[{}] {}".format(err.code,err.message))

            self.last_error = err

        # Draw user input
        # painter.setFont(smallfont)
        # painter.setPen(Qt.GlobalColor.white)
        # painter.drawText(margin,self.height()-margin - 1,u"IN:{}".format(self.input))


    def _drawBaseFooter(self,painter):
        pen = QPen()
        pen.setColor(Qt.GlobalColor.black)
        pen.setWidth(3)

        qp = QPainterPath()
        h = 100
        rad = 10
        qp.addRoundedRect(pen.width(),self.height()-h-pen.width(),self.width() - 2*pen.width(),h,10,10)

        gradient = QLinearGradient(0,+0,0,1)
        gradient.setCoordinateMode(QGradient.ObjectBoundingMode)
        gradient.setColorAt(0,QColor(130,130,200))
        gradient.setColorAt(1,QColor(30,30,100))
        brush = QBrush(gradient)
        painter.fillPath(qp,brush)

        painter.setPen(pen)
        painter.drawPath(qp)

        qp = QPainterPath()
        h = 20
        qp.addRoundedRect(10,self.height()-94-pen.width(),self.width() - 2*10,30,10,10)
        gradient = QLinearGradient(0,+0,0,1)
        gradient.setCoordinateMode(QGradient.ObjectBoundingMode)
        gradient.setColorAt(0,QColor(255,255,255,88))
        gradient.setColorAt(1,QColor(0,0,0,0))
        brush = QBrush(gradient)
        painter.fillPath(qp,brush)


    def _drawBaseScreen(self,painter):

        margin = 10
        bigfont = QFont("Arial",32,QFont.Bold)
        smallfont = QFont("Arial",20,QFont.Bold)
        month_names = ['Jan','Fev','Mars','Avr','Mai','Juin','Juil','Aout','Sept','Oct','Nov','Dec']

        # Fill the area with a background

        gradient = QLinearGradient(0,+0,0,1)
        gradient.setCoordinateMode(QGradient.ObjectBoundingMode)
        gradient.setColorAt(1,QColor(200,200,255,255))
        gradient.setColorAt(0,QColor(255,255,255,255))
        brush = QBrush(gradient)
        # painter.fillPath(glass,brush)

        painter.fillRect(0,0,self.width(),self.height(),brush)

        # The identity of the user

        if self.current_user is not None:

            margin = 5

            w = h = 0
            if self.current_user.image:
                w = self.current_user.image.width()
                h = self.current_user.image.height()

            x = self.width() - w - margin
            r = 10

            # Draw the picture of the user
            if self.current_user.image:
                qp_clip = QPainterPath()
                qp_clip.addRoundedRect(x+r/2, margin+r/2,w - r,h - r,r,r)

                painter.setClipPath(qp_clip)
                painter.setClipping(True)
                painter.drawImage(QPoint(self.width() - self.current_user.image.width() - margin, margin),self.current_user.image)
                painter.setClipping(False)


            # Draw the identity panel
            qp = self.identity_painter_path(margin)

            if self.current_user.image:
                qp.addRoundedRect(x+r/2, margin+r/2,w - r,h - r,r,r)

            gradient = QLinearGradient(0,+0,0,1)
            gradient.setCoordinateMode(QGradient.ObjectBoundingMode)
            gradient.setColorAt(0,QColor(130,130,200))
            gradient.setColorAt(1,QColor(30,30,100))
            brush = QBrush(gradient)
            painter.fillPath(qp,brush)

            # Draw glass reflection

            glass = QPainterPath()
            glass.addRoundedRect(10,10,self.width() - 2*10,20,10,10)
            gradient = QLinearGradient(0,+0,0,1)
            gradient.setCoordinateMode(QGradient.ObjectBoundingMode)
            gradient.setColorAt(0,QColor(255,255,255,88))
            gradient.setColorAt(1,QColor(0,0,0,0))
            brush = QBrush(gradient)
            painter.fillPath(glass,brush)

            # Draw the borders

            qp = self.identity_painter_path(margin)
            pen = QPen()
            pen.setColor(Qt.GlobalColor.black)
            pen.setWidth(3)
            painter.setPen(pen)
            painter.drawPath(qp)

            painter.setFont(smallfont)
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(15,35,u"{}".format(self.current_user.fullname))


    def _drawUserInformationScreen(self,painter):
        self.smallfontbold = QFont("Arial",24,QFont.Bold)

        if self.carousel_page == self.carousel_max_page:
            self._drawUserData(painter)
        else:
            self._drawTaskSelector(painter,self.carousel_page)

        if self.carousel_max_page > 0: # That is, we're in carousel "mode"
            pen = QPen()
            pen.setColor(Qt.GlobalColor.red)
            painter.setPen(pen)
            painter.setFont(self.smallfontbold)

            text = _("There's more... Scan again !")
            r = QRect(0,self.height() - 150,self.width(),150)
            br = painter.boundingRect(r, Qt.AlignRight, text)
            painter.drawText(r, Qt.AlignRight, text)


    def _drawTaskSelector(self,painter,page):
        bigfont = QFont("Arial",40,QFont.Bold)
        smallfont = QFont("Arial",24,QFont.Bold)
        thinfont = QFont("Arial",12,QFont.Normal)
        thinfontbold = QFont("Arial",12,QFont.Bold)
        ultrathinfont = QFont("Arial",10,QFont.Normal)


        pen = QPen()
        pen.setColor(Qt.GlobalColor.black)
        pen.setWidth(1)
        painter.setPen(pen)

        # draw information field
        painter.setFont(bigfont)
        y = self._printAt(painter,10,50,700,_("Scan an operation"))
        y = y + 50

        # Draw task selection with barcodes
        vspace = 10
        i = 0
        base_x = 50


        if self.ongoing_tasks and len(self.ongoing_tasks) > 0:
            y += 3*vspace
            painter.setFont(smallfont)
            y += self._printAt(painter, 10, y,self.width(),_("Ongoing tasks :"))
            y += 1*vspace
            painter.drawLine(0,y,self.width(),y)
            y += 1*vspace

            s = self.task_selector_page_length * page
            for task in self.ongoing_tasks[s:s+self.task_selector_page_length]:

                if task.__klass__ == 'TaskOnOperation':

                    text = u"{}{}-{}".format( task.order_id, task.order_part_id, task.operation_definition_short)
                    painter.setFont(thinfontbold)

                    x = self._drawTextBox(painter,base_x,y,text,pen).right()
                    x += 20

                    # y += self._printAt(painter,30,y,700,u"{}{} |{}| :  {}".format( task.order_id, task.order_part_id, task.operation_definition_short, task.description).encode(sys.getdefaultencoding(),'ignore'))

                    painter.setFont(thinfontbold)
                    y += self._printAt(painter,x,y,700,u"{}".format( task.description).encode(sys.getdefaultencoding(),'ignore'))

                    painter.setFont(thinfont)
                    y += self._printAt(painter,x,y,700,u"Partie {}".format( task.order_part_description).encode(sys.getdefaultencoding(),'ignore'))

                    painter.setFont(ultrathinfont)
                    y += self._printAt(painter,x,y,700,u"{}".format(task.customer_name).encode(sys.getdefaultencoding(),'ignore'))

                elif task.__klass__ == 'TaskOnNonBillable':

                    painter.setFont(thinfontbold)
                    br = self._drawTextBox(painter,base_x,y,u"{}".format( task.description).encode(sys.getdefaultencoding(),'ignore'),pen)
                    painter.setFont(thinfontbold)
                    self._printAt(painter,br.right() + 20,y,700,_("Warning ! Task without customer !"))

                    y += br.height()


                y += 1*vspace
                painter.drawLine(0,y,self.width(),y)
                y += 1*vspace

                i = i + 1



    def _drawWelcomeScreen(self,painter):

        bigfont = QFont("Arial",32,QFont.Bold)
        painter.setFont(bigfont)

        h = self.height() - 100

        dy = (datetime.now().second % 2) * 20
        painter.setPen(Qt.GlobalColor.black)

        s = _("Good morning !")
        if datetime.now().hour > 20:
            s = _("Good evening !")

        w = painter.fontMetrics().width(s)
        painter.drawText((self.width() - w)/2,h/2 - 20 +dy,s)

        s = "Veuillez scanner votre badge !"
        w = painter.fontMetrics().width(s)
        painter.drawText((self.width() - w)/2,h/2 + 60+dy,s)

        # Logo
        painter.drawImage(QPoint((self.width() - self.logo.width())/2, 10),self.logo)







    def _drawProblemScreen(self,painter):
        smallfont = QFont("Arial",24,QFont.Normal)
        smallfontbold = QFont("Arial",24,QFont.Bold)
        bigfont = QFont("Arial",40,QFont.Bold)
        midfont = QFont("Arial",32,QFont.Normal)

        painter.setPen(Qt.GlobalColor.red)
        painter.setFont(bigfont)
        painter.drawText(10,100,self.problem)
        painter.setFont(midfont)
        painter.setPen(Qt.GlobalColor.black)
        painter.drawText(10,150,_("Check with management"))

        if self.current_task:
            vspace = 34
            y = 240
            painter.setFont(smallfontbold)
            painter.setPen(Qt.GlobalColor.black)
            painter.drawText(60,y,u"Operation {}".format( self.current_task.description))
            painter.setFont(smallfont)
            painter.drawText(60,y+vspace,u"Commande {} pour {}".format(self.current_task.order_id, self.current_task.customer_name))
            painter.drawText(60,y+2*vspace,u"Partie {}".format( self.current_task.order_part_description))



    def _drawUserData(self,painter):

        painter.setPen(Qt.GlobalColor.black)
        painter.setFont(self.bigfont)

        y = 50
        y += self._printAt(painter,10,y,700,_("Your status"))
        y += 50
        painter.setFont(self.smallfont)
        # h['presence_begin'],h['presence_total'] = self.dao.employee_dao.presence(user_id)

        if self.current_user.presence_begin[0]:
            y += self._printAt(painter,10,y,700,_("Day started on {}").format(time_to_hm(self.current_user.presence_begin[0])))

        t = self.current_user.presence_total

        if self.current_user.presence_total[0]:
            y += self._printAt(painter,10,y,700,_("Hours : {}").format(duration_to_hm(self.current_user.presence_total[0])))


        y += 20
        painter.drawLine(0,y,self.width(),y)
        y += 20

        nb_times = len(self.current_user.presence_begin)
        x = (self.width() - 100*nb_times) / 2

        self._printAt(painter,self.width() - nb_times*100 - x,y+50, 200,_("Start"))
        self._printAt(painter,self.width() - nb_times*100 - x ,y+100, 200,_("Total"))


        painter.drawLine(x,y+45,self.width()-x,y+45)

        # most recent first
        for i in range(1,nb_times):

            self._printAt(painter,self.width() - i*100 -x ,y, self.width() - i*100,date_to_dm(self.current_user.presence_day[i]))

            begin = self.current_user.presence_begin[i]
            txt = "-"
            if begin:
                txt = time_to_hm(begin)

            self._printAt(painter,self.width() - i*100 -x ,y+50, self.width() - i*100,txt)


            total = self.current_user.presence_total[i]
            txt = "-"
            if total:
                txt = duration_to_hm(total)

            self._printAt(painter,self.width() - i*100 -x ,y+100, self.width() - i*100,txt)



    def _drawTaskConfirmedScreen(self,painter):
        smallfont = QFont("Arial",24,QFont.Normal)
        smallfontbold = QFont("Arial",24,QFont.Bold)
        bigfont = QFont("Arial",40,QFont.Bold)
        thinfont = QFont("Arial",12,QFont.Normal)
        thinfontbold = QFont("Arial",12,QFont.Bold)
        ultrathinfont = QFont("Arial",10,QFont.Normal)

        painter.setPen(Qt.GlobalColor.black)

        painter.setFont(smallfont)
        if self.last_action_kind == TaskActionReportType.start_task:
            msg = _("You're beginning the task")
            # self._drawTriangle(painter)
            painter.drawImage(QPoint((self.width() - self.task_started_icon.width())/2, 350),self.task_started_icon)

        elif self.last_action_kind == TaskActionReportType.stop_task:
            msg = _("You've finished the task")
            # self._drawTick(painter)
            painter.drawImage(QPoint((self.width() - self.task_completed_icon.width())/2, 350),self.task_completed_icon)

        elif self.last_action_kind == TaskActionReportType.day_in:
            msg = _("Clock in !")
            painter.drawImage(QPoint((self.width() - self.day_in_icon.width())/2, 250),self.day_in_icon)

        elif self.last_action_kind == TaskActionReportType.day_out:
            msg = _("Clock out !")
            painter.drawImage(QPoint((self.width() - self.day_out_icon.width())/2, 250),self.day_out_icon)

        painter.setFont(bigfont)
        y = self._printAt(painter,10,50,700,msg)
        y = y + 50 + 50


        pen = QPen()
        pen.setColor(Qt.GlobalColor.black)
        pen.setWidth(1)

        # painter.setFont(bigfont)
        if self.current_task:
            if self.current_task.task_type == 'TaskOnOperation':
                vspace = 34
                base_x = x = 20
                task = self.current_task

                painter.setFont(smallfontbold)
                task_label = u"{} / {}-{}".format( task.order_part_label, task.operation_position, task.operation_definition)
                br = self._drawTextBox(painter,base_x,y,task_label,pen)

                ny = self._printAt(painter,br.right() + 20, y,790-br.right()-20,u"{}".format( task.operation_description))

                y += max( br.height(), ny)
                y += 10

                painter.setFont(smallfont)
                y += self._printAt(painter,x,y,700,u"Partie {}".format(task.order_part_description))
                y += 10
                painter.setFont(thinfont)
                y += self._printAt(painter,x,y,700,task.customer_name)
                self.draw_visual_clue(painter,self.current_task.task_code)

            elif self.current_task.task_type == 'TaskOnNonBillable':
                vspace = 34
                y = 200
                task = self.current_task
                painter.setFont(smallfontbold)
                painter.drawText(60,y,u"{}".format( task.description).encode(sys.getdefaultencoding(),'ignore'))
                y += 30

                pen = QPen()
                pen.setColor(Qt.GlobalColor.red)
                painter.setPen(pen)
                painter.drawText(60,y,u"{}".format( _("Non billable task !")).encode(sys.getdefaultencoding(),'ignore'))


    def paintEvent(self,event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.current_screen != self.old_screen:
            self._drawBaseScreen(painter)

            if self.current_screen == self.TaskSelectorScreen:
                self._drawTaskSelector(painter)
            elif self.current_screen == self.TaskConfirmedScreen:
                self._drawTaskConfirmedScreen(painter)
            elif self.current_screen == self.ProblemScreen:
                self._drawProblemScreen(painter)
            elif self.current_screen == self.UserInformationScreen:
                self._drawUserInformationScreen(painter)
            else:
                self._drawWelcomeScreen(painter)

            self._drawBaseFooter(painter)
            self._drawTimer(painter) # Relies on old_screen

            # We do this here so that old_screen == none allows us to detect
            # the first time we draw
            self.old_screen = self.current_screen

        self._drawTimer(painter)
        self._drawRealTimeInformation(painter)


    def identity_painter_path(self,margin):
        qp = QPainterPath()
        ew = self.width() - margin
        r = 10
        midh = 50

        # Starting top, left
        qp.moveTo(margin+r,margin)

        # going right
        qp.lineTo(ew - r,margin)
        qp.quadTo(QPoint(ew,margin), QPoint(ew,margin+r))

        if self.current_user.image:
            pich = self.current_user.image.height() + margin
            picw = self.current_user.image.width()
            # Down
            qp.lineTo(ew,pich - r)
            qp.quadTo(QPoint(ew,pich), QPoint(ew-r,pich))
            # left
            qp.lineTo(ew - picw+r,pich)
            qp.quadTo(QPoint(ew-picw,pich), QPoint(ew-picw,pich-r))
            # Up
            qp.lineTo(ew - picw, midh)
            qp.quadTo(QPoint(ew-picw,midh-r), QPoint(ew-picw-r,midh-r))
        else:
            qp.lineTo(ew, midh - 2*r)
            qp.quadTo(QPoint(ew,midh-r), QPoint(ew-r,midh-r))

        # Left
        qp.lineTo(margin+r, midh-r)
        qp.quadTo(QPoint(margin,midh-r), QPoint(margin,midh-2*r))

        # Up
        qp.lineTo(margin, margin + r)
        qp.quadTo(QPoint(margin,margin), QPoint(margin+r,margin))

        return qp

    def _drawTick(self,painter):
        pen = QPen()
        pen.setColor(Qt.GlobalColor.black)
        pen.setWidth(1)

        p = QPainterPath()

        d = [(-32.195904,10.69785),(-21.900195,78.05403),(-22.772712,-62.46173),(-21.90019273,8.5214),(13.34952073,0),(21.463934,64.18413),(19.7189,-0.453),(24.954004,-83.85643),(19.282645,-14.68625)]

        # for i in range(len(d)):
        #     x,y = d[i][0],d[i][1]

        x,y = 300 + d[0][0],300 + d[0][1]
        p.moveTo(x,y)
        for i in range(len(d)):
            pt = d[i]
            x += pt[0]
            y += pt[1]
            p.lineTo(x,y)
        painter.fillPath(p,QBrush(Qt.GlobalColor.green))
        painter.drawPath(p)


    def _drawTriangle(self,painter):
        w = 50
        for i in range(3):
            x,y = 300 + i*w*1.25, 350
            pen = QPen()
            pen.setColor(Qt.GlobalColor.black)
            pen.setWidth(1)

            p = QPainterPath()
            p.moveTo(x,y)
            p.lineTo(x+w,y+w)
            p.lineTo(x,y+2*w)
            p.lineTo(x,y)
            painter.fillPath(p,QBrush(Qt.GlobalColor.green))
            painter.drawPath(p)


    def _printAt(self,painter,x,y,max_w,text):
        r = QRect(x,y,max_w,150)
        painter.drawText(r,Qt.AlignLeft | Qt.TextWordWrap, text)
        br = painter.boundingRect(r,Qt.AlignLeft | Qt.TextWordWrap, text)
        return br.height()


    def _drawTextBox(self,painter,x,y,text,pen):
        rad = 5
        r = QRect(x+rad,y+rad,500,150)
        br = painter.boundingRect(r,Qt.AlignLeft | Qt.TextWordWrap, text)

        bpen = QPen()
        bpen.setColor(Qt.GlobalColor.black)
        bpen.setWidth(2)
        painter.setPen(bpen)

        qp = QPainterPath()

        br = QRect(br.x() - rad, br.y() - rad, br.width() + 2*rad, br.height() + 2*rad)
        qp.addRoundedRect(br,rad,rad)
        painter.fillPath(qp,QBrush(Qt.GlobalColor.white))
        painter.drawPath(qp)

        painter.setPen(pen)
        painter.drawText(r,Qt.AlignLeft | Qt.TextWordWrap, text)

        return br


    def draw_visual_clue(self,painter,ident):

        painter.save()
        shapes = [ [ (0,0),(1,0),(0.5,1) ],
                   [ (0,0),(1,0),(0,1),(1,1) ],
                   [ (0,0),(1,0),(1,1),(0,1) ],
                   [ (0,0.5), (0.5,1), (1,0.5), (0.5,0) ],
                   [ (0,1),(1,1),(0.5,0) ] ] # Plus an additional shape : the circle

        pen = QPen()
        pen.setWidthF(0.05)
        pen.setJoinStyle(Qt.MiterJoin)
        if ident % 2 == 0:
            pen.setStyle(Qt.SolidLine)
        else:
            pen.setStyle(Qt.DotLine)

        ident = ident / 2
        p = QPainterPath()
        if ident % 2 == 0:
            p.moveTo(0.5,0)
            p.lineTo(0.5,1)

        ident = ident / 2
        sndx = (ident) % (len(shapes)+1)
        if sndx < len(shapes):
            d = shapes[sndx]
            p.moveTo(d[0][0],d[0][1])
            for ndx in range(len(d)-1):
                p.lineTo(d[ndx+1][0],d[ndx+1][1])
            p.lineTo(d[0][0],d[0][1])
        else:
            p.addEllipse(0,0,1,1)

        painter.setPen(pen)
        size = 60
        painter.translate((800-size-50),600-100-50-size)
        painter.scale(size,size)
        painter.drawPath(p)
        painter.restore()





def all_systems_go():
    mem_logger = MemLogger()
    app = QApplication(sys.argv)
    window = MainWindow(clock_client_id,mem_logger,dao)
    window._loadUser(9999999) # Preload for faster startup
    window.show()

    if False:
        h = window._loadUser(16)
        # h['picture_data'] = None
        window._setCurrentUser(h)
        # window._recordPointage(5000042, 16) # Non billable
        window._recordPointage(10084780, 16) # operation
        window._moveToScreen(window.TaskConfirmedScreen)
        window.update()

    mainlog.info("Startup completed. Ready.")
    app.exec_()

if __name__ == "__main__":
    all_systems_go()
