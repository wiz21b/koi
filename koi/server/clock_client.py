#from guppy import hpy;
#hp=hpy()

# 5000046 : Non billable

import os
import re
from datetime import date
import sys
import logging

try:
    from xmlrpclib import ServerProxy,Fault
except ImportError:
    from xmlrpc.client import ServerProxy,Fault

from datetime import datetime
from PySide.QtCore import *
from PySide.QtGui import *

from koi.base_logging import mainlog
from koi.Configurator import configuration
from koi.python3 import DeclEnum

import random



clock_client_id = None
if __name__ == "__main__":
    if len(sys.argv) > 1:
        clock_client_id = sys.argv[1]
    elif 'VNCDESKTOP' in os.environ:
        clock_client_id = os.environ['VNCDESKTOP']
    else:
        print("Please provide a suitable clock client ID")
        print("It is either a command line parameter or the env. variable VNCDESKTOP")
        exit()


    from koi.base_logging import init_logging
    init_logging("clock_client_{}.log".format("_".join(clock_client_id.strip().split())))

    from koi.Configurator import init_i18n,load_configuration
    load_configuration("server.cfg","server_config_check.cfg")
    init_i18n()

    from koi.datalayer.sqla_mapping_base import metadata
    from koi.datalayer.database_session import init_db_session

    mainlog.debug("Starting server, DB is : {}".format(configuration.get('Database','url')))
    init_db_session(configuration.get('Database','url'), metadata, False or configuration.echo_query)


from koi.Configurator import resource_dir

from koi.tools.chrono import *

from koi.BarCodeBase import BarCodeIdentifier

from koi.server.MemoryLogger import MemLogger
from koi.server import rpctools
from koi.Task import TaskSet

from koi.datalayer.generic_access import DictAsObj
from koi.db_mapping import TaskActionReportType, Operation, OperationDefinition
from koi.db_mapping import Employee
from koi.machine.machine_mapping import Machine

from koi.server.server import ClockServer
from koi.server.json_decorator import ServerException
from koi.dao import dao
from koi.translators import duration_to_hm, date_to_dm

from koi.server.clock_service import ClockService
from koi.server.json_decorator import JsonCallWrapper

# import gettext
# path = 'C:\PORT-STC\pl\eclipse_workspace\PL\koi\i18n'
# lang1 = gettext.translation('horse',path,languages=['en'])
# lang1.install(unicode=True)

class ClockErrors(DeclEnum):
    identify_first = 101, _("Scan identity badge first")

class MainWindow(QWidget):

    # 752, 568 is the size of the raspbian resolution I managed to get
    # but the actual size of the scereen is 800x600

    SCREEN_WIDTH = 800 # 752
    SCREEN_HEIGHT = 600 # 568


    WelcomeScreen = 1
    TaskSelectorScreen = 2
    TaskConfirmedScreen = 3
    ProblemScreen = 4
    UserInformationScreen = 5
    SelectMachineForOperationScreen = 6
    OperationStartedScreen = 7
    OperationFinishedScreen = 8
    PresenceActionScreen = 9
    UnbillableOperationStartedScreen = 10
    UnbillableOperationFinishedScreen = 11

    month_names = ['Jan','Fev','Mars','Avr','Mai','Juin','Juil','Aout','Sept','Oct','Nov','Dec']

    content_margin = 15

    # Number of tasks per page when displaying onoign tasks (really depends
    # on the "height" of a task on the screen => approximate !)
    task_selector_page_length = 3

    # global_text_color = Qt.GlobalColor.black
    global_text_color = Qt.GlobalColor.white
    dimmed_text_color = QColor(200,200,200)
    guidelines_color = Qt.GlobalColor.green
    guidelines_color_flash = Qt.GlobalColor.yellow

    def __init__(self,clock_client_id,mem_logger,dao,font_database, call_mode=JsonCallWrapper.DIRECT_MODE):
        super(MainWindow,self).__init__()

        # time before the current dialog is reset to show the welcome screen again
        # expressed in seconds
        self.time_before_dialog_reset = 60

        # Id of the clock
        self.clock_client_id = clock_client_id

        self._user_guidelines = []
        # self._user_guidelines = ["The wuick brown fox jumps", "over the lazy dog", "and is very happy"]

        # f = "Arial"
        f = "DejaVu Sans"

        self.bigfontbold = font_database.font(f,"Bold",30)
        self.bigfontbold.setPixelSize(50)
        self.bigfontbold.setWeight(QFont.Bold)

        self.bigfont = font_database.font(f,"Normal",30)
        self.bigfont.setPixelSize(50)

        self.midfont = font_database.font(f,"Normal",12)
        self.midfont.setPixelSize(40)

        self.smallfont = font_database.font(f,"Normal",26)
        self.smallfont.setPixelSize(30)

        self.smallfontbold = font_database.font(f,"Bold",26)
        self.smallfontbold.setPixelSize(30)
        self.smallfontbold.setWeight(QFont.Bold)

        self.thinfont = QFont(f,20,QFont.Normal)
        self.thinfont.setPixelSize(20)

        self.thinfontbold = QFont(f,20,QFont.Bold)

        self.ultrathinfont = QFont(f,16,QFont.Normal)
        self.ultrathinfont.setPixelSize(16)

        self.server_direct = ClockServer(dao)

        self.mem_logger = mem_logger

        self.force_screen_update = False

        self.input_changed = True
        self.colleagues = []
        self.ongoing_tasks = None
        self.last_input_activity = datetime.now()
        self.current_user = None
        self.current_user_id = None
        self.selected_machine = None
        self.task = None
        self.users = None
        self.tasks_set = TaskSet('http://localhost:8080',mem_logger)
        self.current_screen = self.WelcomeScreen
        self.problem = ""
        self.current_task = None
        # self.server = server

        self.in_carousel = None
        self.carousel_page = 0
        self.carousel_max_page = 0



        self.resize( MainWindow.SCREEN_WIDTH, MainWindow.SCREEN_HEIGHT)

        self.last_error = None

        self.old_screen = None
        self.current_screen = self.WelcomeScreen

        self.logo = QImage(os.path.join(resource_dir,r"logo_pl.png")).scaledToWidth(400)

        self.background = QImage(os.path.join(resource_dir,r"background.png")).scaledToWidth(800)

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


        self.clock_service = JsonCallWrapper( ClockService(),call_mode) # JsonCallWrapper.IN_PROCESS_MODE)

    def _reset_clock(self):
        # Clearing the input is important because it allows to
        # recover from an incomplete/bad barcode scan.
        self.input = ""
        self.input_changed = True
        self.current_user_id = self.current_user = None
        self.task_selector_page = 0

        if self.current_screen != self.WelcomeScreen:
            self._moveToScreen(self.WelcomeScreen)


    @Slot()
    def reload_information(self):
        # print hp.heap()


        if (datetime.now() - self.last_input_activity).seconds > self.time_before_dialog_reset:
            self._reset_clock()

        return

        # self.timer2.stop()
        # if self.in_reload:
        #     return
        # self.in_reload = True
        # users = None

        # # FIXME Users are downloade once !!!

        # if self.users is None:
        #     try:
        #         # For some reason, if the server proxy fails once at connection
        #         # it will fail forever. Therefore, in case of error, I have
        #         # to recreate it so that it forgets the failure.

        #         self.server = ServerProxy('http://localhost:8080',verbose=False)
        #         users = self.server.usersInformation()

        #     except Exception as e:
        #         self.mem_logger.error(1,"Unable to contact the data server")

        #     # Make sure we don't destroy our current users list if he one we've
        #     # requested never came.

        #     if users is not None:
        #         self.users = dict()
        #         for u in users:
        #             u = User.from_hash(u)
        #             self.users[u.identifier] = u

        # self.tasks_set.export_timetracks()
        # self.tasks_set.reload()
        # self.in_reload = False
        # self.timer2.start(2000)



    def _startCarousel(self):
        mainlog.debug("Init carousel {} / {} = {}".format(len(self.ongoing_tasks), self.task_selector_page_length,len(self.ongoing_tasks) / self.task_selector_page_length))

        self.in_carousel = True

        self.carousel_page = 0
        self.carousel_max_page = 0

        # Since we compute a max_page, the "status page" at the end
        # of the carousel is automatically counted in.

        if self.ongoing_tasks:
            self.carousel_max_page += int( len(self.ongoing_tasks) / self.task_selector_page_length )
            if len(self.ongoing_tasks) % self.task_selector_page_length > 0:
                self.carousel_max_page += 1
        else:
            self.carousel_max_page = 1

        mainlog.debug("Init carousel {} / {} = {}; max_page = {}".format(len(self.ongoing_tasks), self.task_selector_page_length,len(self.ongoing_tasks) / self.task_selector_page_length, self.carousel_max_page))


    def _moveToScreen(self,screen):
        self.old_screen = None
        self.current_screen = screen
        self.update()


    def _loadOperationDetail(self, employee_id, operation_id):
        """ Load the detail of an operation, regardless it
        has imputations or not.

        So this does not load a task.

        The machines are the machines available for that operation.
        """

        operation, machines, next_action_kind, colleagues = self.clock_service.get_operation_information(employee_id, operation_id)
        return operation, machines, next_action_kind, colleagues


    def _loadOperationDefinitionDetail(self, employee_id, operation_definition_id):

        mainlog.debug("_loadOperationDefinitionDetail")
        operation_definition,next_action_kind = self.clock_service.get_operation_definition_information(employee_id, operation_definition_id)
        mainlog.debug("_loadOperationDefinitionDetail - done")
        return operation_definition,next_action_kind



    def _loadUser(self,identifier):
        chrono_start()
        d = date.today() # - timedelta(days=360)
        pers_data = self.clock_service.get_person_data(identifier, d)
        # h =  self.server_direct.getEmployeeInformation(identifier,self.clock_client_id,date.today())
        chrono_click("User {} / {} loaded".format(identifier, pers_data.employee_id))
        return pers_data

        # try:
        #     server = xmlrpclib.ServerProxy('http://localhost:8080',verbose=False)
        #     return server.getEmployeeInformation(identifier)
        # except Exception,e:
        #     self.mem_logger.error(1,"Unable to contact the data server")
        #     self.mem_logger.exception(e)

    def _record_presence(self,employee_id,t,action):
        self.clock_service.record_presence(employee_id,t,self.clock_client_id, action)

    def _setCurrentUser(self,pers_data):
        self.current_user_id = pers_data.employee_id

        self.current_user = pers_data

        if False and pers_data.picture_data:
            # mainlog.debug("Processing picture data {}".format(len(h['picture_data'])))

            image = QImage.fromData(QByteArray(pers_data.picture_data))
            image = image.scaledToHeight(96)
            self.current_user.image = image
            mainlog.debug("Processing picture data -- done")
        else:
            self.current_user.image = None

    def _loadOngoingTasksForUser(self,identifier):

        mainlog.debug("_loadOngoingTasksForUser -- getting in with user id {}".format(identifier))

        try:

            ongoing_tasks = []

            for t in self.clock_service.get_ongoing_tasks(identifier,
                                                          datetime.now()):

                details = self.clock_service.get_task_data(t.task_id)
                mainlog.debug("_loadOngoingTasksForUser : details")
                mainlog.debug(details)

                ongoing_tasks.append(DictAsObj(details))

            return ongoing_tasks
        except AssertionError as e:
            raise e
            self.mem_logger.error(1,"Unable to contact the data server")
            self.mem_logger.exception(e)



    # def _loadTaskInformation(self,identifier):
    #     try:
    #         server = ServerProxy('http://localhost:8080',verbose=False,allow_none=True)
    #         h = server.getTaskInformation(identifier)
    #         t = rpctools.hash_to_object(h)
    #         details = server.getMoreTaskInformation(t.task_id)
    #         setattr(t,'customer_name',details['customer_name'])
    #         setattr(t,'description',details['description'])
    #         setattr(t,'order_part_description',details['order_part_description'])
    #         setattr(t,'order_id',details['order_id'])
    #         setattr(t,'order_part_id',details['order_part_id'])
    #         setattr(t,'order_description',details['order_description'])
    #         setattr(t,'operation_definition',details['operation_definition'])
    #         return t
    #     except Fault as e:
    #         if e.faultCode == 1000:
    #             self.mem_logger.error(1,_("Task doesn't exist"))
    #         else:
    #             self.mem_logger.error(9999,"Unable to contact the data server")
    #             self.mem_logger.exception(e)


    def _recordPointageOnOperation(self, operation_id, employee_id, action_kind, machine_id):
        mainlog.debug("_recordPointageOnOperation {} {} {} {}".format(operation_id, employee_id, action_kind, machine_id))
        try:
            self.clock_service.record_pointage_on_operation(
                operation_id,
                employee_id,
                datetime.now(),
                self.clock_client_id,
                action_kind,
                machine_id)

        except ServerException as ex:
            self.mem_logger.exception(ex)


    def _recordPointageOnOperationDefinition(self, operation_definition_id, employee_id, action_kind):
        mainlog.debug("_recordPointageOnOperationDefinition {} {} {}".format(operation_definition_id, employee_id, action_kind))

        self.clock_service.record_pointage_on_unbillable (
            operation_definition_id,
            employee_id,
            datetime.now(),
            self.clock_client_id,
            action_kind)


    def _recordPointage(self,barcode,employee_id):
        # server = xmlrpclib.ServerProxy('http://localhost:8080',verbose=False)

        try:
            ongoing_tasks = self.clock_service.record_pointage(barcode, employee_id,
                                                               datetime.now(),
                                                               self.clock_client_id)

            mainlog.debug(ongoing_tasks)

            # h = self.server_direct.recordPointage(barcode, employee_id,
            #                                       datetime.strftime(datetime.now(), "%Y%m%dT%H:%M:%S"),
            #                                       self.clock_client_id)

            ongoing_tasks['task_code'] = barcode

            # h['task_code'] = barcode
            self.current_task = rpctools.hash_to_object(ongoing_tasks)

            # FIXME My protocol is not nice; hash_to_object should handle
            # that itself

            self.last_action_kind = self.current_task.action_kind
            return True

        except Fault as e:
            self.mem_logger.exception(e)

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




    def _drawPresenceActionScreen(self, painter):

        if self.presence_action == TaskActionReportType.day_in:

            msg = _("Clock in !")
            painter.drawImage(QPoint((self.width() - self.day_in_icon.width())/2, 250),self.day_in_icon)

        elif self.presence_action == TaskActionReportType.day_out:

            msg = _("Clock out !")
            painter.drawImage(QPoint((self.width() - self.day_out_icon.width())/2, 250),self.day_out_icon)

        self._drawScreenTitle(painter, msg)


    def _operation_definition_scanned(self, operation_definition_id):
        mainlog.debug("_operation_definition_scanned")

        self.operation_definition, self.next_action = self._loadOperationDefinitionDetail(self.current_user_id, operation_definition_id)

        if not self.operation_definition:
            self.mem_logger.error(6,_("The operation definition with {} is unknown").format(operation_definition_id))
            return

        if self.next_action == TaskActionReportType.start_task:

            self._recordPointageOnOperationDefinition(operation_definition_id, self.current_user_id, TaskActionReportType.start_task)

            mainlog.debug("*** --- "*20)

            self.ongoing_tasks = self._loadOngoingTasksForUser(self.current_user_id)
            self._moveToScreen(self.UnbillableOperationStartedScreen)
            self._startCarousel()
            self._setUserGuidelines()

        elif self.next_action == TaskActionReportType.stop_task:

            self._recordPointageOnOperationDefinition(operation_definition_id, self.current_user_id, TaskActionReportType.stop_task)
            self.ongoing_tasks = self._loadOngoingTasksForUser(self.current_user_id)
            self._moveToScreen(self.UnbillableOperationFinishedScreen)
            self._startCarousel()
            self._setUserGuidelines()

        else:
            self.mem_logger.error(6,_("Bad state"))
            mainlog.error("Can't handle next action for simple operation. Next action= {}".format(self.next_action))


    def _presence_scanned(self, action_type):

        self._record_presence(self.current_user_id, datetime.now(),action_type)

        self._setUserGuidelines()

        if action_type == TaskActionReportType.day_out:
            # Day out can potentially stop ongoing tasks
            # so we need to reload the information
            self.ongoing_tasks = self._loadOngoingTasksForUser(self.current_user_id)

        self.presence_action = action_type
        self._moveToScreen(self.PresenceActionScreen)



    def _user_scanned(self, employee_id):

        if self.current_user_id != employee_id:
            # First record presence (else the presence in person's data
            # won't be correct !)
            self._record_presence(employee_id, datetime.now(), TaskActionReportType.presence)
            pers_data = self._loadUser(employee_id)

            self._setCurrentUser(pers_data)
            self.ongoing_tasks = self._loadOngoingTasksForUser(pers_data.employee_id)
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


        self._setUserGuidelines()



    def _operation_scanned(self, operation_id):

        self.operation, self.machines, self.next_action, self.colleagues = self._loadOperationDetail(self.current_user_id, operation_id)

        # mainlog.debug("************************************************** Barcode for operation {}, screen={}, next_action={}".format(operation_id, self.current_screen, self.next_action))

        if not self.operation:
            # If there was a problem, then operation
            # is null.
            # We assume the problem has already been reported
            # in the log elsewhere.
            return

        if not self.machines:
            self.selected_machine = None

            #if self.current_screen in (self.UserInformationScreen, self.OperationStartedScreen, self.OperationFinishedScreen):

            # no machine => direct task action report recording

            if self.next_action == TaskActionReportType.start_task:
                self._recordPointageOnOperation(operation_id, self.current_user_id, TaskActionReportType.start_task, None)
                self.ongoing_tasks = self._loadOngoingTasksForUser(self.current_user_id)
                self._moveToScreen(self.OperationStartedScreen)
                self._setUserGuidelines()
            elif self.next_action == TaskActionReportType.stop_task:
                self._recordPointageOnOperation(operation_id, self.current_user_id, TaskActionReportType.stop_task, None)
                self.ongoing_tasks = self._loadOngoingTasksForUser(self.current_user_id)
                self._moveToScreen(self.OperationFinishedScreen)
                self._setUserGuidelines()
            else:
                self.mem_logger.error(6,_("Bad state"))
                mainlog.error("Can't handle next action for simple operation {}".format(self.next_action))

        elif self.machines:
            mainlog.debug("going to machine selection screen for a start or stop")
            # machine => machine select before going further
            self._moveToScreen(self.SelectMachineForOperationScreen)
            self._setUserGuidelines()

        else:
            self.mem_logger.error(5,_("Nothing to do with operation {}").format(operation_id))
            mainlog.error("Nothing to do with operation {}".format(operation_id))



    def _machine_scanned(self, machine_id):
        mainlog.debug("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! Barcode for machine")

        if self.current_screen == self.SelectMachineForOperationScreen:

            m = [m for m in self.machines if m.machine_id == machine_id]
            if m:
                self.selected_machine = m[0]
            else:
                self.selected_machine = None

            if self.selected_machine:

                self.next_action = self.clock_service.get_next_action_for_employee_operation_machine(
                    self.current_user_id, self.operation.operation_id, self.selected_machine.machine_id)

                mainlog.debug("Next action for task = {}".format(self.next_action))

                self._recordPointageOnOperation(self.operation.operation_id, self.current_user_id, self.next_action,self.selected_machine.machine_id)

                mainlog.debug("Machine barcode scanned and OK")
                self.ongoing_tasks = self._loadOngoingTasksForUser(self.current_user_id)
                self._startCarousel()

                self._setUserGuidelines()

                if self.next_action == TaskActionReportType.start_task:
                    self._moveToScreen(self.OperationStartedScreen)
                elif self.next_action == TaskActionReportType.stop_task:
                    self._moveToScreen(self.OperationFinishedScreen)

            else:
                m = self.clock_service.get_machine_data(machine_id)

                self.mem_logger.error(3,_("The machine {} is not allowed for the operation").format(m.fullname))

        else:
            self.mem_logger.error(3,_("Machine barcode makes no sense here"))


    def keyPressEvent(self,event):

        self.last_input_activity = datetime.now()
        self.input_changed = event.key() not in (Qt.Key_Enter,Qt.Key_Return)

        if event.key() == Qt.Key_Backspace:
            if len(self.input) > 0:
                self.input = self.input[0:(len(self.input)-1)]
                self.update()
                return
        else:
            if event.key() not in (Qt.Key_Enter,Qt.Key_Return):
                self.input = self.input + event.text()

            # mainlog.debug("{} - {}".format(self.input, len(self.input)))

            BARCODE_LENGTH = 13

            if "quit" in self.input or "exit" in self.input:
                exit()

            elif len(self.input) > BARCODE_LENGTH:
                mainlog.debug("Clearing the input 'cos it's too long")
                self.input = u""
                self.update()
                return

            elif (len(self.input) == BARCODE_LENGTH) or (event.key() in (Qt.Key_Enter,Qt.Key_Return)):

                identifier = -1
                if not re.match("^(x|X)?[0-9]+$", self.input):
                    self.input = u""
                    self.update()
                    return
                else:
                    if (self.input[0] in ('x','X')) and len(self.input) > 1:

                        # X command allow to type in a barcode identifier without
                        # the check digit

                        # If entry starts with X, then don't enter the check digit
                        identifier = int(self.input[1:len(self.input)])
                    elif len(self.input) > 1:
                        # Regular barcode.
                        identifier = int(self.input[0:-1]) # Remove the check digit
                    else:
                        self.mem_logger.error(0,"Bad barcode {}".format(self.input))
                        self.input = u""
                        self.update()
                        return

                    # This is very important as it ensures that we don't get
                    # stuck with a half-encoded barcode
                    self.input = u""

                    self.mem_logger.clear_errors()
                    self.last_error = None

                    # At this point, the identifier is the barcode less
                    # the check digit.

                    mainlog.debug("Barcode without check digit : {}".format(identifier))


                    data = None
                    try:
                        data = BarCodeIdentifier.barcode_to_id(identifier)
                    except Exception as ex:
                        self.mem_logger.error(2,_("Unrecognized barcode"))
                        return


                    try:
                        if data[0] == Employee:
                            employee_id = data[1]
                            self._user_scanned(employee_id)
                        else:

                            if self.current_user:

                                if data[0] == Machine:
                                    machine_id = data[1]
                                    self._machine_scanned( machine_id)

                                elif data[0] == Operation:
                                    operation_id = data[1]
                                    self._operation_scanned(operation_id)

                                elif data[0] in (TaskActionReportType.day_in, TaskActionReportType.day_out):
                                    self._presence_scanned(data[0])

                                elif data[0] == OperationDefinition:
                                    operation_definition_id = data[1]
                                    self._operation_definition_scanned(operation_definition_id)

                            else:
                                self.mem_logger.error(ClockErrors.identify_first.value,
                                                      ClockErrors.identify_first.description)
                    except Exception as sx:
                        self.mem_logger.exception(sx)

                    self.update()
            elif len(self.input) < BARCODE_LENGTH:
                self.update()
                return


    def _clipToRect(self,painter,x,y,w,h):
        p = QPainterPath()
        p.moveTo(x,y)
        p.lineTo(x+w,y)
        p.lineTo(x+w,y+h)
        p.lineTo(x,y+h)

        painter.setClipping(False)
        # painter.fillRect(x-2, y-2, w+4, h+4, Qt.red)

        painter.setClipPath(p)
        painter.setClipping(True)


    def _drawTimer2(self,painter):

        t = datetime.now()

        painter.setFont(self.thinfont)
        painter.setPen(self.dimmed_text_color)

        cursor = "#"
        if t.second % 2 == 0:
            cursor=" "

        d = "{} {} {} {:0>2}:{:0>2}".format(t.day,self.month_names[t.month-1],t.year,t.hour,t.minute)

        fm = painter.fontMetrics()
        w,h = fm.boundingRect(d).width() + 5, fm.height() # +5 because the width computation is sometimes a bit wrong
        x,y = self.width() - w - self.content_margin, self.height() - h - self.content_margin

        self._clipToRect(painter,x,y,w,h)
        self._fillBackground(painter)

        painter.drawText(x,y + fm.height(),d)
        painter.setClipping(False)


    def _drawTimer(self,painter):
        margin = 10

        # Draw date
        t = datetime.now()

        if True or self.old_screen is None or t.minute == 1:
            painter.setFont(self.smallfont)

            fm = painter.fontMetrics()
            w,h = fm.boundingRect("19 Mnnn 9999").width(), fm.height()
            x,y = self.width() - w - margin, self.height() - 100
            self._clipToRect(painter,x,y,w,h)
            self._drawBaseFooter(painter)

            # painter.fillRect(0,0,self.width(),self.height(),QColor(255,0,0))
            # The date
            d = "{} {} {}".format(t.day,self.month_names[t.month-1],t.year)
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(self.width() - fm.width(d) - margin,self.height() - 100 + fm.height() - 5,d)

        # The time

        # We have a blinking cursor. I've tried to blink the ":"
        # between minutes and hours, but that requires a lot of calculations
        # on font size which, in the end, never are pixel accurate. So
        # I've abandonned that lead and chosen something much easier.

        cursor = "."
        if t.second % 2 == 0:
            cursor=" "

        d = "{:0>2}:{:0>2}{}".format(t.hour, t.minute,cursor)

        painter.setFont(self.bigfont)

        # We use clipping to optimize repainting over the same place.
        # This help us to avoid a lot of traffic on VNC setups
        fm = painter.fontMetrics()
        w,h = fm.width("99:99_"), fm.height()
        x,y = self.width() - w - margin, self.height() - h - margin
        self._clipToRect(painter,x,y,w,h)
        self._drawBaseFooter(painter)

        # painter.fillRect(0,0,self.width(),self.height(),QColor(255,0,0))

        x = self.width() - fm.width("99:99_") - margin

        painter.setPen(Qt.GlobalColor.white)
        painter.drawText(x,self.height() -margin - 5,d)

        painter.setClipping(False)




    def _drawRealTimeInformation(self,painter):

        margin = 10
        err = self.mem_logger.last_error(4)

        # mainlog.debug("_drawRealTimeInformation err={}".format(err))

        if not err and self.last_error:
            # mainlog.debug("Trigeering redraw")

            self.last_error = None
            self.old_screen = None

        elif err and err != self.last_error:

            # Draw error box

            self.last_error = err

            painter.setFont(self.thinfont)
            fm = painter.fontMetrics()

            w = fm.boundingRect("19 Mmmm 9999").width()

            r = QRect(margin, self.height() - 100, self.width() - w - 2*margin, 100)

            self._clipToRect(painter,r.x(),r.y(),r.width(),r.height())
            self._drawBaseFooter(painter)

            if err:
                painter.setClipping(False)
                painter.setPen(Qt.GlobalColor.red)
                painter.setFont(self.smallfont)

                r = QRect(self.content_margin*5, 10,
                          self.width() - 2*5*self.content_margin,20)

                err_msg = u"[{}] {}".format(err.code,err.message)

                br = painter.boundingRect(r, Qt.AlignLeft | Qt.TextWordWrap, err_msg)

                r.setHeight(br.height())
                r.setWidth(br.width())

                r_boundary = QRect(r.x(), r.y(), r.width(), r.height())

                growth = self.content_margin * 3
                r_boundary.adjust(- growth,- growth, growth, growth)


                screen_center = QPoint(int(self.width()/2), int(self.height()/2))
                r_boundary.moveCenter( screen_center )
                r.moveCenter( screen_center )

                painter.fillRect(r_boundary,
                                 QBrush(QColor(196,0,0)))

                painter.drawRect(r_boundary)

                painter.setPen(QColor(255,255,255))
                painter.drawText(r,Qt.AlignLeft | Qt.TextWordWrap, err_msg)


            painter.setClipping(False)


        # Draw user input

        painter.setFont(self.smallfont)
        painter.setPen(Qt.GlobalColor.white)
        fm = painter.fontMetrics()

        w,h = fm.width("M"*20), fm.height()
        x,y = margin, self.height()-margin - 1 - h
        self._clipToRect(painter, x,y,w,h)

        if not self.input:
            self._fillBackground(painter)

        elif len(self.input) > 12:
            painter.drawText(margin, self.height()-margin - 1, self.input)

        painter.setClipping(False)


    def _drawBaseFooter(self,painter):
        pen = QPen()
        pen.setColor(Qt.GlobalColor.black)
        pen.setWidth(2)

        # qp = QPainterPath()
        # h = 100
        # rad = 10
        # qp.addRoundedRect(pen.width(),self.height()-h-pen.width(),self.width() - 2*pen.width(),h,10,10)

        # gradient = QLinearGradient(0,+0,0,1)
        # gradient.setCoordinateMode(QGradient.ObjectBoundingMode)
        # gradient.setColorAt(0,QColor(130,130,200))
        # gradient.setColorAt(1,QColor(30,30,100))
        # brush = QBrush(gradient)
        # painter.fillPath(qp,brush)

        # painter.setPen(pen)
        # painter.drawPath(qp)

        # qp = QPainterPath()
        # h = 20
        # qp.addRoundedRect(10,self.height()-94-pen.width(),self.width() - 2*10,30,10,10)
        # gradient = QLinearGradient(0,+0,0,1)
        # gradient.setCoordinateMode(QGradient.ObjectBoundingMode)
        # gradient.setColorAt(0,QColor(255,255,255,88))
        # gradient.setColorAt(1,QColor(0,0,0,0))
        # brush = QBrush(gradient)
        # painter.fillPath(qp,brush)


    def _fillBackground(self, painter):
        # Fill the area with a background

        # gradient = QLinearGradient(0,+0,0,1)
        # gradient.setCoordinateMode(QGradient.ObjectBoundingMode)
        # gradient.setColorAt(0,QColor(0,0,0,255))
        # gradient.setColorAt(1,QColor(100,100,100,255))
        # brush = QBrush(gradient)
        # painter.fillRect(0,0,self.width(),self.height(),brush)


        random.seed(1)
        brushes = [QBrush(QColor(x*0,x*2,x*4)) for x in range(1,6)  ]
        w = 25

        y = 0
        while y < self.height():
            x = 0
            while x < self.width():

                ndx = float(y) / self.width() + (-0.5 + random.random()) / 2.0

                if ndx > 1:
                    ndx = 1
                elif ndx < 0:
                    ndx = 0

                painter.fillRect(x,y,w,w,brushes[ int(ndx*(len(brushes)-1))])
                x+=w
            y+=w


        painter.drawImage(QPoint(0, 0),self.background)


    def _drawBaseScreen(self,painter):

        margin = 10
        self._fillBackground(painter)

        # The identity of the user

        if self.current_user is not None:

            y_margin = 5

            w = h = 0
            if self.current_user.image:
                w = self.current_user.image.width()
                h = self.current_user.image.height()

            x = self.width() - w - margin
            r = 10

            painter.setFont(self.smallfont)
            painter.setPen(self.dimmed_text_color)
            painter.drawText(self.content_margin,35,u"{}".format(self.current_user.fullname))

            self._draw_separator_line(painter, 50)

            painter.setPen(self.global_text_color)

            # Draw the picture of the user
            if self.current_user.image:
                x = self.width() - self.current_user.image.width() - self.content_margin
                qp_clip = QPainterPath()
                qp_clip.addRoundedRect(x+r/2, y_margin+r/2,w - r,h - r,r,r)

                painter.setClipPath(qp_clip)
                painter.setClipping(True)
                painter.drawImage(QPoint(x, y_margin),self.current_user.image)
                painter.setClipping(False)


            # # Draw the identity panel
            # qp = self.identity_painter_path(margin)

            # if self.current_user.image:
            #     qp.addRoundedRect(x+r/2, margin+r/2,w - r,h - r,r,r)

            # gradient = QLinearGradient(0,+0,0,1)
            # gradient.setCoordinateMode(QGradient.ObjectBoundingMode)
            # gradient.setColorAt(0,QColor(130,130,200))
            # gradient.setColorAt(1,QColor(30,30,100))
            # brush = QBrush(gradient)
            # painter.fillPath(qp,brush)

            # # Draw glass reflection

            # glass = QPainterPath()
            # glass.addRoundedRect(10,10,self.width() - 2*10,20,10,10)
            # gradient = QLinearGradient(0,+0,0,1)
            # gradient.setCoordinateMode(QGradient.ObjectBoundingMode)
            # gradient.setColorAt(0,QColor(255,255,255,88))
            # gradient.setColorAt(1,QColor(0,0,0,0))
            # brush = QBrush(gradient)
            # painter.fillPath(glass,brush)

            # # Draw the borders

            # qp = self.identity_painter_path(margin)
            # pen = QPen()
            # pen.setColor(Qt.GlobalColor.black)
            # pen.setWidth(3)
            # painter.setPen(pen)
            # painter.drawPath(qp)



    def _draw_separator_line(self, painter, y):
        # painter.setPen(Qt.GlobalColor.white)
        painter.setPen(QColor(128,128,128))

        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.drawLine(int(self.content_margin/3), y,
                         self.width() - int(self.content_margin/3), y )
        painter.setRenderHint(QPainter.Antialiasing)

    def _drawScreenTitle(self, painter, title):
        # Draw the title

        painter.setFont(self.bigfont)
        painter.setPen(self.global_text_color)
        y = self._printAt(painter,self.content_margin,60,self.width() - 100,title)

        y = 60 + int(self.bigfont.pixelSize() * 1.33)

        self._draw_separator_line(painter, y)

        y = y + 20

        return y


    def _drawUserInformationScreen(self,painter):

        # We draw the user data on the last page of the carousel
        # We choose to do so to ensure the people are focused
        # on their tasks rather than their time

        if self.carousel_page == self.carousel_max_page:
            self._drawUserData(painter)
        else:
            self._drawTaskSelector(painter,self.carousel_page)

        if self.carousel_max_page > 0: # That is, we're in carousel "mode"
            pen = QPen()
            pen.setColor(Qt.GlobalColor.red)
            painter.setPen(pen)
            painter.setFont(self.smallfontbold)

            self._setUserGuidelines([_("There's more... Scan again !")])
        else:
            self._setUserGuidelines([_("Scan an operation to start !")])





    def _drawTaskSelector(self,painter,page):
        thinfontbold = QFont("Arial",12,QFont.Bold)
        ultrathinfont = QFont("Arial",10,QFont.Normal)

        y = self._drawScreenTitle(painter, _("Ongoing tasks"))

        pen = QPen()
        pen.setColor(self.global_text_color)
        pen.setWidth(1)
        painter.setPen(pen)

        # Draw task selection with barcodes
        vspace = 10
        i = 0
        base_x = 30


        if not self.ongoing_tasks:

            y = self.height() / 2

            painter.setFont(self.smallfont)
            # self._drawTextBox(painter,base_x,y,_("You have no ongoing task"),pen)
            self._drawTextCenter(painter, y, _("You have no ongoing task"))

        elif self.ongoing_tasks and len(self.ongoing_tasks) > 0:

            s = self.task_selector_page_length * page
            for task in self.ongoing_tasks[s:s+self.task_selector_page_length]:

                # mainlog.debug("Displaying... {}".format(type(task.task_type)))
                # mainlog.debug(task)

                if task.task_type == 'TaskOnOperation':

                    # FIXME Super bad names "task.order_id, task.order_part_id"

                    text = self._task_label( "{}{}".format( task.order_id, task.order_part_id),
                                             task.position or "", task.operation_definition_short)
                    painter.setFont(self.smallfontbold)

                    bbox = self._drawTextBox(painter,base_x,y,text,pen)
                    x = bbox.right()
                    painter.setPen(pen)

                    x += 20

                    # y += self._printAt(painter,30,y,700,u"{}{} |{}| :  {}".format( task.order_id, task.order_part_id, task.operation_definition_short, task.description).encode(sys.getdefaultencoding(),'ignore'))

                    painter.setFont(self.smallfont)
                    # y += self._printAt(painter,x,y,self.width()-100,u"{}".format( task.description))

                    if task.machine_label:
                        painter.setPen(Qt.GlobalColor.yellow)
                        painter.setFont(self.smallfont)
                        y += self._printAt(painter,x,y,self.width()-100,u"Machine {}".format( task.machine_label))
                        painter.setPen(self.global_text_color)

                    painter.setFont(self.thinfont)
                    y += self._printAt(painter,x,y,self.width()-100,u"Partie {}".format( task.order_part_description))

                    # painter.setFont(self.ultrathinfont)
                    # y += self._printAt(painter,x,y,self.width()-100,u"{}".format(task.customer_name))

                    y = max( bbox.bottom(), y)

                elif task.task_type == 'TaskOnNonBillable':

                    painter.setFont(self.smallfontbold)
                    br = self._drawTextBox(painter,base_x,y,task.description,pen)
                    painter.setFont(self.smallfont)
                    painter.setPen(self.global_text_color)
                    br = self._printAtBR(painter,
                                         br.right() + 20,y,
                                         self.width()-br.right()-20,_("Warning ! Task without customer !") * 2)

                    y += br.height()

                else:
                    raise Exception("Unsupported task type ")


                y += 1*vspace

                self._draw_separator_line(painter, y)

                y += 1*vspace

                i = i + 1

        msgs = [_("Scan an operation")]
        if self.carousel_max_page > 0: # That is, we're in carousel "mode"
            msgs.append(_("There's more... Scan again !"))

        self._setUserGuidelines(msgs)


    def _drawWelcomeScreen(self,painter):

        painter.setFont(self.bigfont)
        painter.setPen(self.global_text_color)

        dy = (datetime.now().second % 2) * 20

        s = _("Good morning !")
        if datetime.now().hour > 18:
            s = _("Good evening !")

        fm = painter.fontMetrics()
        br = fm.boundingRect(s)

        painter.drawText((self.width() - br.width())/2, int((self.height()/2 + br.height()/2)), s)

        msgs = [_("Please scan your badge")]
        self._setUserGuidelines(msgs)

        # Logo
        painter.drawImage(QPoint((self.width() - self.logo.width())/2, 10),self.logo)







    # def _drawProblemScreen(self,painter):
    #     smallfont = QFont(self.title_font_family,24,QFont.Normal)
    #     smallfontbold = QFont("Arial",24,QFont.Bold)
    #     bigfont = QFont("Arial",40,QFont.Bold)
    #     midfont = QFont("Arial",32,QFont.Normal)

    #     painter.setPen(Qt.GlobalColor.red)
    #     painter.setFont(bigfont)
    #     painter.drawText(10,100,self.problem)
    #     painter.setFont(midfont)
    #     painter.setPen(Qt.GlobalColor.black)
    #     painter.drawText(10,150,_("Check with management"))

    #     if self.current_task:
    #         vspace = 34
    #         y = 240
    #         painter.setFont(smallfontbold)
    #         painter.setPen(Qt.GlobalColor.black)
    #         painter.drawText(60,y,u"Operation {}".format( self.current_task.description))
    #         painter.setFont(smallfont)
    #         painter.drawText(60,y+vspace,u"Commande {} pour {}".format(self.current_task.order_id, self.current_task.customer_name))
    #         painter.drawText(60,y+2*vspace,u"Partie {}".format( self.current_task.order_part_description))



    def _drawUserData(self,painter):
        """ Draws the user data, its presence, etc.
        Its current activity imust drawn somewhere else.
        """

        painter.setFont(self.smallfont)
        # h['presence_begin'],h['presence_total'] = self.dao.employee_dao.presence(user_id)

        if self.current_user.activity_hours:

            painter.setPen(Qt.GlobalColor.black)
            TODAY = 0

            # y += self._printAt(painter,10,y,700,_("Day started on {}").format(time_to_hm(self.current_user.activity[TODAY].first_time)))

            # if self.current_user.presence_total[0]:
            #     y += self._printAt(painter,10,y,700,_("Hours : {}").format(duration_to_hm(self.current_user.presence_total[0])))

            # y += 20
            # painter.drawLine(0,y,self.width(),y)
            # y += 20

            nb_times = len(self.current_user.activity_hours)
            fm = painter.fontMetrics()
            br1 = fm.boundingRect("12h59m")
            w1 = br1.width()
            br2 = fm.boundingRect("31/12")
            w2 = br2.width()
            block_w = max(w1,w2)
            block_space = 20

            y = int( (self.height() -  (br1.height() + br2.height())) / 2)
            x = (self.width() - (block_w+block_space)*nb_times) / 2

            left_x = x

            # most recent first
            for i in range(len(self.current_user.activity_hours)):

                mainlog.debug(self.current_user.activity_hours[i])
                
                t1 = date_to_dm(self.current_user.activity_hours[i].day)

                t2 = "-"
                total = self.current_user.activity_hours[i].duration
                if total:
                    t2 = duration_to_hm(total)

                rad = 5
                qp = QPainterPath()
                br = QRect(x - rad,y - rad, block_w + 2*rad, 100 + 2*rad)
                qp.addRoundedRect(br,rad,rad)
                painter.fillPath(qp,QBrush(Qt.GlobalColor.white))
                painter.drawPath(qp)
                painter.drawLine(br.x(),br.y()+45,br.right(),br.y()+45)

                self._printAt(painter, x, y, self.width(), t1)
                self._printAt(painter, x ,y+50, self.width(),t2)

                x+= block_w + block_space


        self._drawScreenTitle(painter, _("Your activity"))



    def _drawBasicOperationData(self, painter, operation, dy, machine = ""):

        mainlog.debug("_drawBasicOperationData")
        mainlog.debug(operation)


        task_label = self._task_label(operation.order_part_identifier,
                                      operation.position,
                                      operation.operation_definition_short)

        painter.setFont(self.bigfontbold) # bigfontbold
        br = self._drawTextBox(painter, self.content_margin, dy, task_label, QColor(48,48,48))


        if machine:
            painter.setPen(Qt.GlobalColor.yellow)
            painter.setFont(self.midfont)
            ny = br.y() + self._printAt(painter, br.right() + 20, br.y() + 5, self.width()-(br.right() + 20) - self.content_margin, machine)

            ny = max( ny, br.bottom())
        else:

            ny = br.bottom()
            ny += self.smallfont.pixelSize()

        painter.setPen(self.global_text_color)
        painter.setFont(self.smallfont)
        d = operation.description.replace("\n",' /// ')
        if len(d) > 120:
            d = d[0:120] + u"..."
        ny += self._printAt(painter, self.content_margin, ny, self.width()-10-self.content_margin, d)

        # painter.setFont(self.smallfont)
        # ny += self._printAt(painter, br.right() + 25, ny,790-br.right()-20,u"{}".format( operation.operation_definition_description))

        # Contextualize the operation a bit

        painter.setPen(self.dimmed_text_color)
        painter.setFont(self.thinfont)
        ny += self._printAt(painter, self.content_margin, ny,self.width()-10-br.right()-20, _("Part {}").format(operation.order_part_description))

        ny += self.smallfont.pixelSize()


        painter.setPen(self.dimmed_text_color)

        return ny


    def _drawOperationDetail(self, painter, operation):
        """ Draw the detail of an operation (not a task !)
        The details are meant to be shown in the case there's
        only one operation displayed (that is, they're not displayed
        in a list of operations)
        """

        ny = self._drawScreenTitle(painter, _("Task selection"))


        if self.machines:
            painter.setFont(self.smallfontbold)
            painter.setPen(Qt.GlobalColor.red)

            ny += self.smallfontbold.pixelSize()

            if len(self.machines) == 1:
                txt = _("You're working on this task !")
            else:
                txt = _("You're working on this task with {} machines!").format(len(self.machines))

            ny += self._drawTextCenter(painter, ny, txt)

            ny = self._drawBasicOperationData(painter, self.operation, ny, ", ".join( [m.fullname for m in self.machines]))
        else:
            ny = self._drawBasicOperationData(painter, self.operation, ny)


        ny += 10

        # Maybe the current user is already working on it

        if self.ongoing_tasks and not self.machines:
            # The test on machines helps to not show a message that is already shown above

            for task in self.ongoing_tasks:
                mainlog.debug("Looking at {}".format(task))
                if task.task_type == 'TaskOnOperation' and task.operation_id == self.operation.operation_id:

                    painter.setPen(Qt.GlobalColor.red)
                    ny += self._printAt(painter, self.content_margin, ny, self.width()-10-self.content_margin,
                                        _("You are already working on that operation !"))


        # Maybe there's someone else working on that operation already
        # (or the user himself, on a different machine)

        if len(self.colleagues) > 1:
            s = _("Other people on this operation : ")
            comma = False
            for cdata in self.colleagues:
                if cdata.reporter_id != self.current_user_id:
                    if comma:
                        s = s + u", "
                    else:
                        comma = True

                    s += cdata.fullname

            ny += self._printAt(painter, self.content_margin, ny, self.width()-10-self.content_margin,s)

        return ny


    def _drawSelectMachineForOperationScreen(self, painter):
        machines_in_use = []
        if self.ongoing_tasks:
            for task in self.ongoing_tasks:
                if task.task_type == 'TaskOnOperation' and \
                   task.operation_id == self.operation.operation_id:
                    machines_in_use.append(task.machine_id)

        m_names = []
        for m in self.machines:
            if m.machine_id in machines_in_use:
                m_names.append(m)

        old_machines = self.machines
        self.machines = m_names
        ny = self._drawOperationDetail( painter, self.operation)
        ny += 30

        self.machines = old_machines


        if not machines_in_use :
            self._setUserGuidelines([_("Select a machine to start on this operation")])
        elif len(self.machines) == 1:
            self._setUserGuidelines([_("Select current machine to stop") ])
        else:
            self._setUserGuidelines([_("Select current machine to stop"),
                                     _("Select another machine to start") ])



    def _drawOperationStartedScreen(self,painter):

        ny = self._drawScreenTitle(painter, _("You're beginning the task"))

        if self.selected_machine:
            ny = self._drawBasicOperationData(painter, self.operation, ny, self.selected_machine.fullname)
        else:
            ny = self._drawBasicOperationData(painter, self.operation, ny)

        # if self.selected_machine:
        #     painter.setPen(self.global_text_color)
        #     painter.setFont(self.thinfontbold)
        #     ny += 10
        #     ny += self._printAt(painter, self.content_margin, ny, self.width()-10 - self.content_margin, _("Machine {}").format(self.selected_machine.fullname))

        painter.drawImage(QPoint((self.width() - self.task_started_icon.width())/2, 350),self.task_started_icon)

        self._setUserGuidelines()


    def _drawOperationFinishedScreen(self,painter):

        ny = self._drawScreenTitle(painter, _("You've finished the task"))

        if self.selected_machine:
            ny = self._drawBasicOperationData(painter, self.operation, ny, self.selected_machine.fullname)
        else:
            ny = self._drawBasicOperationData(painter, self.operation, ny)

        painter.drawImage(QPoint((self.width() - self.task_completed_icon.width())/2, 350),self.task_completed_icon)

        self._setUserGuidelines()



    def _drawUnbillableOperationDetail(self, painter, operation_definition):
        """ Draw the detail of an operation (not a task !)
        The details are meant to be shown in the case there's
        only one operation displayed (that is, they're not displayed
        in a list of operations)
        """

        y = 300
        base_x = x = 20

        painter.setFont(self.bigfont)
        painter.setPen(self.global_text_color)

        # ny = self._printAt(painter, 50, y, 800,
        #                    self.operation_definition.description)

        self._drawTextCenter(painter, 250, self.operation_definition.description)



    def _drawUnbillableOperationStartedScreen(self,painter):

        self._drawScreenTitle(painter, _("You're beginning the task"))

        ny = self._drawUnbillableOperationDetail(painter, self.operation_definition)
        painter.drawImage(QPoint((self.width() - self.task_started_icon.width())/2, 350),self.task_started_icon)

        self._setUserGuidelines()


    def _drawUnbillableOperationFinishedScreen(self,painter):

        self._drawScreenTitle(painter, _("You've finished the task"))

        ny = self._drawUnbillableOperationDetail(painter, self.operation_definition)
        painter.drawImage(QPoint((self.width() - self.task_completed_icon.width())/2, 350),self.task_completed_icon)
        self._setUserGuidelines()


    def _drawTaskConfirmedScreen(self,painter):

        ny = self._drawOperationDetail( painter, self.operation)

        painter.setPen(self.global_text_color)

        painter.setFont(self.smallfont)
        if self.next_action == TaskActionReportType.start_task:
            msg = _("You're beginning the task")
            # self._drawTriangle(painter)
            painter.drawImage(QPoint((self.width() - self.task_started_icon.width())/2, 300),self.task_started_icon)

        elif self.next_action == TaskActionReportType.stop_task:
            msg = _("You've finished the task")
            # self._drawTick(painter)
            painter.drawImage(QPoint((self.width() - self.task_completed_icon.width())/2, 300),self.task_completed_icon)

        elif self.next_action == TaskActionReportType.day_in:
            msg = _("Clock in !")
            painter.drawImage(QPoint((self.width() - self.day_in_icon.width())/2, 200),self.day_in_icon)

        elif self.next_action == TaskActionReportType.day_out:
            msg = _("Clock out !")
            painter.drawImage(QPoint((self.width() - self.day_out_icon.width())/2, 200),self.day_out_icon)

        painter.setFont(self.bigfont)
        y = self._printAt(painter,10,50,self.width()-100,msg)
        y = y + 50 + 50


        pen = QPen()
        pen.setColor(Qt.GlobalColor.black)
        pen.setWidth(1)

        # painter.setFont(self.bigfont)
        if self.current_task:
            if self.current_task.task_type == 'TaskOnOperation':
                vspace = 34
                base_x = x = 20
                task = self.current_task

                painter.setFont(self.smallfontbold)
                task_label = self._task_label( task.order_part_label, task.operation_position, task.operation_definition_short_id)

                br = self._drawTextBox(painter,base_x,y,task_label,pen)

                ny = self._printAt(painter,br.right() + 20, y,self.width()-10-br.right()-20,task.operation_description)

                y += max( br.height(), ny)
                y += 10

                painter.setFont(self.smallfont)
                y += self._printAt(painter,x,y,self.width()-100,u"Partie {}".format(task.order_part_description))
                y += 10
                painter.setFont(self.thinfont)
                # y += self._printAt(painter,x,y,self.width()-100,task.customer_name)
                self.draw_visual_clue(painter,self.current_task.task_code)

                if self.last_action_kind == TaskActionReportType.start_task:
                    self._setUserGuidelines([_("Select a machine")])



            elif self.current_task.task_type == 'TaskOnNonBillable':
                vspace = 34
                y = 200
                task = self.current_task
                painter.setFont(self.smallfont)
                painter.drawText(60,y,task.description)
                y += 30

                pen = QPen()
                pen.setColor(Qt.GlobalColor.red)
                painter.setPen(pen)
                painter.drawText(60,y,_("Non billable task !"))


    def _setUserGuidelines(self, msgs = []):
        self._user_guidelines = msgs

    def _drawUserGuidelines(self, painter):

        # align = [Qt.AlignRight, Qt.AlignLeft][datetime.now().second % 2]
        align = Qt.AlignHCenter | Qt.TextWordWrap
        painter.setFont(self.smallfont)
        fm = painter.fontMetrics()
        h = fm.height()
        total_height = len(self._user_guidelines) * h

        # y = self.height() - 130 - total_height
        # self._clipToRect(painter,0,y,self.width(),total_height)
        # self._fillBackground(painter)
        # painter.setClipping(False)

        seconds = datetime.now().second
        mod = min(2, len(self._user_guidelines))

        if self._user_guidelines:
            fm = painter.fontMetrics()

            r = QRect(self.content_margin,0,self.width()-2*self.content_margin,self.height())

            gls = []

            total_height = 0
            for i in range(len(self._user_guidelines)):
                txt = self._user_guidelines[i]
                br = painter.boundingRect(r, align, txt)

                gls.append( (txt, total_height) )
                total_height += br.height()
                total_height += 10 # Spacing

            y = (self.height() - 50) - total_height

            for gl_text, gl_y in gls:

                pen = QPen()

                if len(self._user_guidelines) > 1:
                    if (seconds % len(self._user_guidelines) == i):
                        pen.setColor(self.guidelines_color)

                    else:
                        pen.setColor(self.guidelines_color_flash)
                else:
                    if seconds % 2:
                        pen.setColor(self.guidelines_color)
                    else:
                        pen.setColor(self.guidelines_color_flash)

                painter.setPen(pen)

                r = QRect(self.content_margin,y + gl_y,self.width()-2*self.content_margin,self.height())

                # br = painter.boundingRect(r, align, txt)
                painter.drawText(r, align, gl_text)



    def paintEvent(self,event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setClipping(False)

        new_screen = self.current_screen != self.old_screen

        if new_screen:
            chrono_start()
            self._drawBaseScreen(painter)

        if self.input_changed or new_screen:
            self.input_changed = False
            self._drawBaseFooter(painter)

        self._drawTimer2(painter) # Relies on old_screen

        if new_screen:
            mainlog.debug("paint() : new screen ! {}".format(self.current_screen))
            if self.current_screen == self.TaskSelectorScreen:
                self._drawTaskSelector(painter)
            elif self.current_screen == self.TaskConfirmedScreen:
                self._drawTaskConfirmedScreen(painter)
            # elif self.current_screen == self.ProblemScreen:
            #     self._drawProblemScreen(painter)
            elif self.current_screen == self.UserInformationScreen:
                self._drawUserInformationScreen(painter)
            elif self.current_screen == self.SelectMachineForOperationScreen:
                self._drawSelectMachineForOperationScreen(painter)
            elif self.current_screen == self.OperationStartedScreen:
                self._drawOperationStartedScreen(painter)
            elif self.current_screen == self.OperationFinishedScreen:
                self._drawOperationFinishedScreen(painter)
            elif self.current_screen == self.PresenceActionScreen:
                self._drawPresenceActionScreen(painter)

            elif self.current_screen == self.UnbillableOperationFinishedScreen:
                self._drawUnbillableOperationFinishedScreen(painter)

            elif self.current_screen == self.UnbillableOperationStartedScreen:
                self._drawUnbillableOperationStartedScreen(painter)

            else:
                self._drawWelcomeScreen(painter)

            # We do this here so that old_screen == none allows us to detect
            # the first time we draw
            self.old_screen = self.current_screen

            chrono_click()

        # Drawn over the freshly drawn screen

        self._drawRealTimeInformation(painter)
        self._drawUserGuidelines(painter)

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


    def _drawTextCenter(self, painter, y, text):
        fm = painter.fontMetrics()
        br = fm.boundingRect(text)

        painter.drawText( (self.width() - br.width()) / 2, y, text)

        return br.height()

    def _printAt(self,painter,x,y,max_w,text):
        r = QRect(x,y,max_w,150)
        painter.drawText(r,Qt.AlignLeft | Qt.TextWordWrap, text)
        br = painter.boundingRect(r,Qt.AlignLeft | Qt.TextWordWrap, text)
        return br.height()

    def _printAtBR(self,painter,x,y,max_w,text):
        align = Qt.AlignLeft | Qt.TextWordWrap

        r = QRect(x,y,max_w,800)
        painter.drawText(r,align, text)
        br = painter.boundingRect(r, align, text)

        # fm = painter.fontMetrics()
        # br = fm.boundingRect(text)
        # br = painter.boundingRect(r,Qt.AlignLeft | Qt.TextWordWrap, text)
        return br

    def _drawTextBox(self,painter,x,y,text,pen):
        """ Draw a line of text surrounded by a box
        Font must be set in painter before calling.
        """

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

        painter.setPen(QColor(48,48,48))

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

        ident = ident // 2
        p = QPainterPath()
        if ident % 2 == 0:
            p.moveTo(0.5,0)
            p.lineTo(0.5,1)

        ident = ident // 2
        sndx = ident % (len(shapes)+1)
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

    def _task_label(self, order_part, op_position, op_def_short):
        """ Standardized text for operation box
        """

        return u"{} | {} | {}".format(order_part, op_position, op_def_short)



def all_systems_go():
    mainlog.setLevel(logging.WARNING) # logging.WARNING)

    mem_logger = MemLogger()
    app = QApplication(sys.argv)

    title_font_id  = QFontDatabase.addApplicationFont( os.path.join(resource_dir, "DejaVuSans-Bold.ttf"))
    if title_font_id == -1:
        raise Exception("Could not load font")
    title_font_id2 = QFontDatabase.addApplicationFont( os.path.join(resource_dir, "DejaVuSans.ttf"))
    if title_font_id2 == -1:
        raise Exception("Could not load font")
    font_database = QFontDatabase()


    # print("Font styles")
    # print(font_database.styles("DejaVu Sans"))

    # title_font_family  = font_database.applicationFontFamilies(title_font_id)[0]
    # title_font_family2 = font_database.applicationFontFamilies(title_font_id)[0]

    print("Families")
    print(font_database.families())
    # print(font_database.styles("DejaVu Sans"))
    # print(font_database.applicationFontFamilies(title_font_id2))

    # print(title_font_family)
    # print(title_font_family2)

    window = MainWindow(clock_client_id,mem_logger,dao,font_database)

    # window._loadUser(9999999) # Preload for faster startup


    window.show()

    # window._user_scanned(16)

    # if False:
    #     window._operation_scanned(84755)

    # if True:
    #     window._operation_scanned(127975)
    #     window._machine_scanned(11) # Bad machine

    # if False:
    #     window._operation_definition_scanned(43)

    # if False:
    #     window._presence_scanned(TaskActionReportType.day_in)

    # if False:
    #     window._operation_scanned(128117)

    mainlog.info("Startup completed. Ready.")
    app.exec_()

if __name__ == "__main__":
    all_systems_go()
