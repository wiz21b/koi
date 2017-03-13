from datetime import date

from PySide.QtCore import Qt,Slot
from PySide.QtGui import QLabel, QDialog, QDialogButtonBox
from PySide.QtGui import QVBoxLayout,QHBoxLayout

from koi.gui.dialog_utils import TitleWidget,showTableEntryErrorBox,makeErrorBox
from koi.gui.ProxyModel import PrototypeController, TimestampPrototype, TaskActionTypePrototype, TextLinePrototype,TrackingProxyModel,OrderPartOnTaskPrototype,TaskOnOrderPartPrototype
from koi.Configurator import mainlog
from koi.db_mapping import TaskActionReport,TaskOnOrder,TaskOnOperation,TaskOnNonBillable
from koi.dao import dao
from koi.translators import date_to_s

class EditTaskActionReportsDialog (QDialog):

    def __init__(self,dao,parent,edit_date):
        super(EditTaskActionReportsDialog,self).__init__(parent)

        title = _("Task actions records")
        self.setWindowTitle(title)

        self.dao = dao

        top_layout = QVBoxLayout()
        self.title_widget = TitleWidget(title,self)
        top_layout.addWidget(self.title_widget)


        hlayout = QHBoxLayout()
        self.timesheet_info_label = QLabel("Name",self)
        hlayout.addWidget(self.timesheet_info_label)
        hlayout.addStretch()
        top_layout.addLayout(hlayout)


        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.StandardButton.Cancel)
        self.buttons.addButton( QDialogButtonBox.Ok)


        prototype = []
        # prototype.append( EmployeePrototype('reporter', _('Description'), dao.employee_dao.all()))

        prototype.append( OrderPartOnTaskPrototype(None, _('Order Part'), editable=True, nullable=True))

        # BUG today is wrong... Must be the imputation date
        self.task_on_orderpart_prototype = TaskOnOrderPartPrototype('task', _('Task'),on_date=date.today(),editable=True,nullable=True)
        prototype.append( self.task_on_orderpart_prototype)

        prototype.append( TaskActionTypePrototype('kind',_('Action'),editable=True,nullable=False))
        prototype.append( TimestampPrototype('time',_('Hour'),editable=True,nullable=False,fix_date=edit_date))
        prototype.append( TimestampPrototype('report_time',_('Recorded at'),editable=False))
        prototype.append( TextLinePrototype('origin_location',_('Origin'),editable=False))
        prototype.append( TextLinePrototype('editor',_('Editor'),editable=False,default='master'))


        self.controller = PrototypeController(self,prototype)
        self.controller.setModel(TrackingProxyModel(self,prototype))
        self.controller.view.enable_edit_panel()

        top_layout.addWidget(self.controller.view) # self.time_tracks_view)
        top_layout.addWidget(self.buttons)
        self.setLayout(top_layout)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        # self.resize(640,400)


    def keyPressEvent(self,event):

        # The goal here is to make sure the accept signal is called only
        # if the user clicks on the "OK" button /with the mouse/ and,
        # not with the keyboard

        if event.key() in (Qt.Key_Enter, Qt.Key_Return):
            return
        else:
            super(EditTaskActionReportsDialog,self).keyPressEvent(event)



    def set_employee_date(self,employee, d):
        self.current_employee = employee
        self.current_date = d

        self.timesheet_info_label.setText(_("Time recordings for <b>{}</b> on <b>{}</b>").format(employee.fullname,date_to_s(d,True)))

        self.controller.model._buildModelFromObjects(
            dao.task_action_report_dao.get_reports_for_employee_on_date(employee,d))


        for i in range(len(self.controller.model.objects)):
            if self.controller.model.objects[i]:
                row = self.controller.model.table[i]
                obj = self.controller.model.objects[i].task


                if isinstance(obj,TaskOnOrder):
                    row[0] = obj.order
                elif isinstance(obj,TaskOnOperation):
                    row[0] = obj.operation.production_file.order_part
                elif isinstance(obj,TaskOnNonBillable):
                    row[0] = ""
                elif obj is None:
                    row[0] = ""
                else:
                    raise Exception("Can't work with type {}".format(type(obj)))


        self.controller.model_data_changed = False # FIXME dirty (encapsulate in controller plz)


    def save(self):
        errors = self.controller.model.validate()
        if errors is not None:
            showTableEntryErrorBox(errors)
            return False

        results = self.controller.model.model_to_objects(lambda : TaskActionReport(), None)


    def save(self):
        mainlog.debug("EditTimeTracksDialog.save()")
        errors = self.controller.model.validate()
        if errors:
            showTableEntryErrorBox(errors)
            return False

        try:
            to_delete,to_create,to_update = self.controller.model.filter_db_updates(
                self.controller.model.model_to_objects( lambda : TaskActionReport()))
            self.dao.task_action_report_dao.multi_update( to_delete,to_create,to_update, self.current_employee)
            return True
        except Exception as e:
            msgBox = makeErrorBox(_("There was an error while saving your data"),str(e))
            msgBox.exec_()
            return False


    @Slot()
    def accept(self):
        if self.save():
            super(EditTaskActionReportsDialog,self).accept()
            self.deleteLater()


    @Slot()
    def reject(self):
        super(EditTaskActionReportsDialog,self).reject()
        self.deleteLater()
