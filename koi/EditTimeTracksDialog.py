if __name__ == "__main__":
    import sys
    from PySide.QtGui import QApplication

    from koi.base_logging import mainlog,init_logging
    from koi.Configurator import init_i18n,load_configuration

    init_logging()
    init_i18n()
    load_configuration()

from datetime import datetime

from PySide.QtCore import Qt,Slot
from PySide.QtGui import QLabel, QHeaderView, QDialog, QDialogButtonBox, QStandardItem, QMessageBox
from PySide.QtGui import QVBoxLayout,QHBoxLayout

from koi.gui.dialog_utils import TitleWidget, showTableEntryErrorBox
from koi.gui.ProxyModel import Prototype,PrototypeController, DurationPrototype
from koi.translators import date_to_s, duration_to_hm
from koi.PotentialTasksCache import PotentialTasksCache
from koi.TaskService import *
from koi.machine.machine_service import machine_service
from koi.gui.ComboDelegate import AutoComboDelegate
from koi.gui.completer import AutoCompleteComboBox
from koi.gui.ProxyModel import OrderPartIdentifierValidator,StandardTableDelegate


class ConstrainedMachineSelectorDelegate(AutoComboDelegate):
    def __init__(self,parent=None):
        super(ConstrainedMachineSelectorDelegate,self).__init__(parent)

    def get_displayed_data(self,index):
        if index.isValid():
            machine_id = index.data(Qt.UserRole)
            if machine_id is not None:
                return machine_service.find_machine_by_id(machine_id).fullname

        return None

    def createEditor(self,parent,option,index):

        proxy = index.model().index(index.row(),index.column()-2).data(Qt.UserRole) # FIXME hardcoding columns is baaaad :-)

        if not proxy:
            return

        machines = machine_service.find_machines_for_operation_definition(proxy.operation_definition_id)
        editor = AutoCompleteComboBox(self,parent)
        editor.section_width = [400]

        labels = [None] # Null machine is OK
        items = [None]
        for m in machines:
            labels.append(m.fullname)
            items.append(m.machine_id)

        mainlog.debug(labels)

        editor.make_str_model(labels, items)

        # if option:
        #     editor.setGeometry(option.rect)

        return editor

    def setModelData(self,editor,model,index):
        ndx = editor.currentIndex()
        if ndx < 0:
            ndx = 0

        data = editor.itemData( ndx, Qt.UserRole)
        model.setData(index,data,Qt.UserRole)


    def setEditorData(self,editor,index):
        return


class ConstrainedMachineSelectorPrototype(Prototype):

    def __init__(self,field,title,editable=True,nullable=False):
        super(ConstrainedMachineSelectorPrototype,self).__init__(field, title,editable,nullable)

        self.set_delegate(ConstrainedMachineSelectorDelegate())



class ImputableSelectorDelegate(StandardTableDelegate):

    def __init__(self,parent=None):
        super(ImputableSelectorDelegate,self).__init__(parent)
        self.identifier_validator = OrderPartIdentifierValidator()
        self._date = date.today() # FIXME

    def get_displayed_data(self,index):
        if index.isValid():
            imputable_proxy = index.data(Qt.UserRole)
            if imputable_proxy is not None:
                return imputable_proxy.identifier

        return None

    def createEditor(self,parent,option,index):
        mainlog.debug("ImputableSelectorDelegate : createEditor")

        # Regular string editor
        editor = super(ImputableSelectorDelegate,self).createEditor(parent,option,index)
        editor.setValidator(self.identifier_validator)
        return editor

    def setEditorData(self,editor,index):
        editor.setText(self.get_displayed_data(index))

    def setModelData(self,editor,model,index):
        if editor.text() and len(editor.text()) > 0:

            proxy = ImputableProxy(self._date)
            proxy.set_on_identifier(editor.text())
            model.setData(index,proxy,Qt.UserRole)
        else:
            model.setData(index,None,Qt.UserRole)


class ImputableSelectorPrototype(Prototype):
    def __init__(self,field,title,editable=True,nullable=False):
        super(ImputableSelectorPrototype,self).__init__(field, title,editable,nullable)
        self.set_delegate(ImputableSelectorDelegate(None))






class ProxyTaskComboDelegate(AutoComboDelegate):
    """ The task combo delegate, if used as an editor, it must be
    located on a column at the *right* of an 'order part' column.
    """

    def __init__(self,items,on_date,section_width = None,parent=None):
        super(ProxyTaskComboDelegate,self).__init__(parent)
        if on_date is None:
            raise Exception("Invalid date")
        self.on_date = on_date


    def createEditor(self,parent,option,index):

        # We get the "imputable proxy". Normally it has been "set"
        # with an identifier
        # It will tell us what we can record time on (operations or operation definitions)

        left_side = index.model().index(index.row(),index.column()-1).data(Qt.UserRole)

        if not left_side:
            left_side = ImputableProxy(self.on_date)
            left_side.set_on_identifier("")

        editor = AutoCompleteComboBox(self,parent)
        editor.section_width = [400]

        self.labels = []
        for t in left_side.imputable_tasks:
            self.labels.append(t.description or "")
        self.items = left_side.imputable_tasks

        editor.make_str_model(self.labels, self.items)

        if option:
            editor.setGeometry(option.rect)

        return editor

    def get_displayed_data(self,index):
        d = index.model().data( index,Qt.UserRole)
        if d:
            res = d.description
        else:
            res = None
        return res


    def setModelData(self,editor,model,index):
        ndx = editor.currentIndex()

        if ndx < 0:
            ndx = 0

        data = editor.itemData( ndx, Qt.UserRole)
        model.setData(index,data,Qt.UserRole)



class ProxyTaskComboPrototype(Prototype):

    def __init__(self,field,title,on_date,editable=True,nullable=False):
        super(ProxyTaskComboPrototype,self).__init__(field, title,editable,nullable)

        if on_date is None:
            raise "Invalid date"

        self.set_delegate(ProxyTaskComboDelegate(None,on_date,None))

    def set_task_cache(self,cache):
        pass
        # self.delegate().set_task_cache(cache)




def prevent_row_delete_message():
    showWarningBox(_("You can't delete this row"),
                   _("You cannot delete this line because it was automatically created from time recordings. If you really want to delete it, then you must delete its time recordings. After doing so, the program will automatically conclude that the time record is not necessary anymore"))

def prevent_row_update_message():
    showWarningBox(_("You can't modify this row"),
                   _("You cannot update this line because it was automatically created from time recordings. If you really want to change the time spent on the task, you need to create another row with the same task and a positive or negative amount of hours if you want to add or remove hours"))

class EditTimeTracksDialog (QDialog):


    @Slot(QStandardItem)
    def data_changed_slot(self,item):
        # mainlog.debug("data_changed_slot")
        self.model_data_changed = True

        m = self.controller.model
        sum_hours = 0
        for i in range(m.rowCount()):
            ndx = m.index(i,2)
            #mainlog.debug("editTT : {}: {}".format(i, m.data(ndx,Qt.UserRole)))
            try:
                sum_hours = sum_hours + float(m.data(ndx,Qt.UserRole))
            except:
                pass

        mainlog.debug("Sum = {}".format(sum_hours))
        self.sum_hours_label.setText(duration_to_hm(sum_hours))


    def __init__(self,parent,dao,day):
        super(EditTimeTracksDialog,self).__init__(parent)

        self.edit_date = day

        title = _("Time spent on tasks")
        self.setWindowTitle(title)

        top_layout = QVBoxLayout()
        self.title_widget = TitleWidget(title,self)
        top_layout.addWidget(self.title_widget)

        hlayout = QHBoxLayout()
        self.timesheet_info_label = QLabel("Name",self)
        hlayout.addWidget(self.timesheet_info_label)
        hlayout.addStretch()
        top_layout.addLayout(hlayout)
        info = QLabel(_("On the table below you can have two kinds of line. The grey line which shows the time spent on a task computed on the basis of the actual time recordings. Since those are computed automaticaly, you can't change them. The other lines in black, are those that you will encode have encoded yourself. They represent hours to add or remove to those of the grey lines. So, for example, if you want to remove 3 hours on a task, you encode the task with a duration of three hours."),self)
        info.setWordWrap(True)
        top_layout.addWidget(info)

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.StandardButton.Cancel)
        self.buttons.addButton( QDialogButtonBox.Ok)

        if dao.task_dao.tasks_count() > 0:

            prototype = []
            prototype.append( ImputableSelectorPrototype(None, _('Order Part'), nullable=True))

            # BUG today is wrong... Must be the imputation date
            self.task_on_orderpart_prototype = ProxyTaskComboPrototype('task', _('Task'),on_date=date.today(),editable=True,nullable=False)
            prototype.append( self.task_on_orderpart_prototype)

            prototype.append( DurationPrototype('duration',_('Duration'), format_as_float=False))
            prototype.append( ConstrainedMachineSelectorPrototype('machine_id',_('Machine'),nullable=True))
            # prototype.append( TimestampPrototype('start_time',_('Start time'),fix_date=day,nullable=True,editable=True))
            # prototype.append( TimestampPrototype('encoding_date',_('Recorded at'),editable=False))

            self.controller = PrototypeController(self,prototype)

            self.controller.setModel(TrackingProxyModel(self,prototype))
            self.controller.view.horizontalHeader().setResizeMode(1, QHeaderView.Stretch)
            self.controller.view.enable_edit_panel()

            self.controller.model.rowsInserted.connect(self.data_changed_slot)
            self.controller.model.rowsRemoved.connect(self.data_changed_slot)
            self.controller.model.dataChanged.connect(self.data_changed_slot)

            # self.employee_select = QComboBox()
            # self.employee_select.setModel(self.dao.employee_dao.list_model())
            # self.employee_select.setCurrentIndex(0)
            # self.set_on_selected_employee()
            # top_layout.addWidget(self.employee_select)

            top_layout.addWidget(self.controller.view) # self.time_tracks_view)

            hlayout = QHBoxLayout()
            self.sum_hours_label = QLabel("12345")
            self.sum_hours_label.setObjectName("important") # Used for CSS
            hlayout.addStretch()
            hlayout.addWidget(QLabel(_("Sum of durations")))
            hlayout.addWidget(self.sum_hours_label)

            top_layout.addLayout(hlayout)

            top_layout.addWidget(self.buttons)
            self.setLayout(top_layout)

            self.buttons.accepted.connect(self.accept)
            self.buttons.rejected.connect(self.reject)
            # self.employee_select.activated.connect(self.employee_changed)


            self.resize(800,400)
            self.setSizeGripEnabled(True)

        else:
            top_layout.addWidget(QLabel("There are no task in the system " +
                                        "for you to report on. Create some " +
                                        "tasks first",self))
            top_layout.addWidget(self.buttons)
            self.setLayout(top_layout)
            self.buttons.accepted.connect(self.accept_direct)
            self.buttons.rejected.connect(self.reject)


    def keyPressEvent(self,event):

        # The goal here is to make sure the accept signal is called only
        # if the user clicks on the "OK" button /with the mouse/ and,
        # not with the keyboard.

        if event.key() in (Qt.Key_Enter, Qt.Key_Return):
            return
        else:
            super(EditTimeTracksDialog,self).keyPressEvent(event)


    def set_employee_and_date(self,employee_id, edit_date): # FIXME move this into constructore and remove call in using class... Or change the timestamp prototype

        employee = dao.employee_dao.find_by_id_frozen(employee_id)
        timetracks = dao.timetrack_dao.all_work_for_employee_date(employee_id,edit_date)
        self.task_cache = PotentialTasksCache(dao.task_dao, edit_date)

        mainlog.debug("set_employee_and_date : timetracks are")
        proxified_timetracks = []
        for timetrack in timetracks:
            mainlog.debug(timetrack)
            proxified_timetracks.append(TimetrackProxy(timetrack))
        mainlog.debug("done")

        self.edit_date = edit_date
        self.task_on_orderpart_prototype.on_date = edit_date
        self.timesheet_info_label.setText(_("Timesheet for <b>{}</b> on <b>{}</b>").format(employee.fullname,date_to_s(edit_date,True)))

        self.task_on_orderpart_prototype.set_task_cache(self.task_cache)

        self.controller.model._buildModelFromObjects(proxified_timetracks)

        self.controller.model.set_row_protect_func(lambda obj,row: obj is not None and obj.managed_by_code,
                                                   prevent_row_delete_message)
        self.controller.model.row_update_protect_func = lambda obj,row: obj and obj.managed_by_code
        self.controller.model.row_update_protect_announce = prevent_row_update_message

        for i in range(len(timetracks)):
            row = self.controller.model.table[i]
            imputable = ImputableProxy(edit_date)
            imputable.set_on_timetrack(timetracks[i])
            row[0] = imputable

        # for row in self.controller.model.table:
        #     if row[1]:
        #         row[0] = row[1].operation.production_file.order_part

        # self.controller.model_data_changed = False # FIXME dirty (encapsulate in controller plz)
        self.current_employee_id_selected = employee_id

        self.controller.view.setFocus(Qt.OtherFocusReason)
        self.controller.view.setCurrentIndex(self.controller.model.index(0,0))

        # FIXME Better separate presentation and data layer !!!
        session().commit()

        self.data_changed_slot(None)


    # @Slot(int)
    # def employee_changed(self,ndx):

    #     # Pay attention ! At this point the rdopdown already report the
    #     # new selection, not the one that is used for the table !

    #     mainlog.debug("Employee changed to {}, was {}".format(ndx,employee))

    #     if self.current_employee_selected != ndx:

    #         # Actually changed

    #         if not self.model_data_changed:
    #             self.set_on_selected_employee()
    #         else:
    #             ret = saveCheckBox()

    #             if ret == QMessageBox.Save:
    #                 if self.save():
    #                     self.set_on_selected_employee()
    #                 else:
    #                     self.employee_select.setCurrentIndex(self.current_employee_selected)
    #             elif ret == QMessageBox.Cancel:
    #                 # User has cancelled or save didn't work out => we reset to the old value
    #                 self.employee_select.setCurrentIndex(self.current_employee_selected)
    #             else: # QMessageBox.Discard
    #                 self.set_on_selected_employee()


    def save(self):
        mainlog.debug("EditTimeTracksDialog.save()")
        errors = self.controller.model.validate()
        if errors:
            showTableEntryErrorBox(errors)
            return False

        tt_start_time = datetime( self.edit_date.year, self.edit_date.month, self.edit_date.day, 6, 0, 0)
        edited_proxy_tts = self.controller.model.model_to_objects( lambda : TimetrackProxy())
        employee_id = self.current_employee_id_selected

        # for tt in edited_proxy_tts:
        #     mainlog.debug(type(tt))
        #     mainlog.debug(str(tt))

        try:
            save_proxy_timetracks(edited_proxy_tts, tt_start_time, employee_id)
            return True
        except Exception as e:
            msgBox = QMessageBox(self)
            msgBox.setIcon(QMessageBox.Critical)
            msgBox.setText("There was an error while saving your data");
            msgBox.setInformativeText(str(e));
            msgBox.setStandardButtons(QMessageBox.Ok);
            # msgBox.setDefaultButton(QMessageBox.Ok);
            ret = msgBox.exec_();
            return False


    @Slot()
    def accept(self):
        if self.save():
            mainlog.debug("Clearing model {}".format(self.controller.model))

            # Don't forget to clear the model so we don't keep any
            # references to anything

            self.controller.model.clear()
            return super(EditTimeTracksDialog,self).accept()
        else:
            mainlog.debug("accept was not accepted :-)")

    @Slot()
    def accept_direct(self):
        super(EditTimeTracksDialog,self).accept()
        self.controller.model.clear()

    @Slot()
    def reject(self):
        super(EditTimeTracksDialog,self).reject()
        self.controller.model.clear()



if __name__ == "__main__":
    from koi.junkyard.services import services
    app = QApplication(sys.argv)
    d = EditTimeTracksDialog(None,dao,date(2013,8,10))
    # d.set_employee_and_date( dao.employee_dao.find_by_id(100), date(2013,8,10))
    d.set_employee_and_date( services.employees.find_by_id(100), date(2013,8,10))
    d.exec_()
