import platform
from datetime import date,datetime

from PySide.QtCore import Qt,Slot, QSize
from PySide.QtGui import QDialog, QDialogButtonBox, QFormLayout, QLabel, QMessageBox
from PySide.QtGui import QVBoxLayout, QFont, QMenu

from koi.datalayer.generic_access import DictAsObj


if __name__ == '__main__':

    from koi.base_logging import mainlog,init_logging
    from koi.Configurator import init_i18n,load_configuration,configuration

    init_logging()
    init_i18n()
    load_configuration()

    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session,session

    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)



from koi.Configurator import mainlog,configuration
from koi.gui.dialog_utils import TitleWidget,saveCheckBox
from koi.gui.completer import AutoCompleteComboBox
from koi.QuickComboModel import QuickComboModel
from koi.session.UserSession import user_session


from koi.db_mapping import OrderStatusType,TaskActionReport,Task,TaskOnOrder, TaskOnNonBillable,TaskActionReportType,Operation,Order,OperationDefinition, OrderPart

from koi.datalayer.database_session import session


from koi.dao import dao
from koi.gui.dialog_utils import showWarningBox,showMultiErrorsBox
from koi.gui.editors import TimeStampEdit,TaskActionReportTypeComboBox,OrderPartIdentifierEdit,ConstrainedMachineEdit
from koi.translators import date_to_dmy
from koi.TimeReportView import TimeReportView
from koi.machine.machine_service import machine_service


class TheView(TimeReportView):

    def __init__(self,parent):
        super(TheView,self).__init__(parent)

        self.tar_menu = QMenu(_("Time tracking"),parent)
        # self.change_report_action = self.tar_menu.addAction(_("Change report"))
        self.delete_report_action = self.tar_menu.addAction(_("Delete report"))

        self.task_menu = QMenu(_("Task"),parent)
        self.add_task_report_action = self.task_menu.addAction(_("Add time"))

        self.tar_presence_menu = QMenu(_("Presence"),parent)
        self.add_presence_report_action = self.tar_presence_menu.addAction(_("Add presence report"))

        self.all_menu = QMenu(_("All"),parent)
        self.all_menu.addAction(self.add_task_report_action)
        self.all_menu.addAction(self.add_presence_report_action)


        # self.a.triggered.connect(self.editPointage)

    def mouseDoubleClickEvent( self, event):
        p = self.mapToScene(event.pos())
        item = self.scene().itemAt(p)

        if item:
            item.setSelected(True)
            selected = item.data(0)

            if hasattr(selected, "type"):
                stype = selected.type
            else:
                stype = None

            if selected is None:
                self.add_presence_report_action.trigger()
            elif stype in (Task, TaskOnOperation, TaskOnNonBillable, TaskOnOrder):
                self.add_task_report_action.trigger()


    def contextMenuEvent( self, event ) :
        p = self.mapToScene(event.pos())
        item = self.scene().itemAt(p)

        if item:
            item.setSelected(True)
            selected = item.data(0)

            if hasattr(selected, "type"):
                stype = selected.type
            else:
                stype = None


            if selected is None:
                self.tar_presence_menu.move( event.globalPos())
                self.tar_presence_menu.show()
            elif isinstance( selected, TaskActionReport):
                self.tar_menu.move( event.globalPos())
                self.tar_menu.show()
            elif stype in (Task, TaskOnOperation, TaskOnNonBillable, TaskOnOrder):
                self.task_menu.move( event.globalPos())
                self.task_menu.show()
            else:
                mainlog.debug("contextMenuEvent : can't do anything on {} (type={})".format(selected, stype))
        else:
            self.all_menu.move( event.globalPos())
            self.all_menu.show()


# class TimeReportingScannerWidget(QWidget):
#     def __init__(self,parent):
#         global configuration
#         super(TimeReportingScannerWidget,self).__init__(parent)

#         self.presence_dialog = PresenceDialog(self)
#         self.time_edit_dialog = TimeEditDialog(self)

#         title = _("Time reporting scanner")
#         self.title_widget = TitleWidget(title,self)

#         self.save_button = QPushButton(_("Save"))

#         self.view = TheView(self)
#         # self.view.setRenderHint(QPainter.Antialiasing)
#         self.view.setAlignment(Qt.AlignLeft | Qt.AlignTop)

#         self.view.add_presence_report_action.triggered.connect(self.add_presence_report)
#         self.view.add_task_report_action.triggered.connect(self.add_task_report)
#         self.view.delete_report_action.triggered.connect(self.delete_report)

#         self.save_button.clicked.connect(self.save)

#         top_layout = QVBoxLayout()
#         top_layout.addWidget(self.title_widget)
#         top_layout.addWidget(self.view)
#         top_layout.addWidget(self.save_button)

#         self.setLayout(top_layout) # QWidget takes ownership of the layout
#         self.changed = False

#         self.added_tars = []
#         self.tar_to_delete = []


#     def edited(self):
#         if self.added_tars or self.tar_to_delete:
#             return True
#         else:
#             return False

#     @Slot()
#     def save(self):
#         if self.edited():
#             dao.task_action_report_dao.update_tars(self.employee, self.base_time.date(), self.all_tars + self.added_tars, self.tar_to_delete)

#             self.added_tars = []
#             self.tar_to_delete = []
#         else:
#             mainlog.debug("nothing to save")

#         self.save_button.setEnabled( self.edited())

#     @Slot()
#     def delete_report(self):
#         mainlog.debug("delete_report")
#         for selected in self.view.scene().selectedItems():
#             t = selected.data(0)
#             # selected item might not be what we expect...
#             if isinstance(t,TaskActionReport):

#                 changed = False

#                 for at in self.added_tars:
#                     if at.task_id == t.task_id and at.time == t.time and at.kind == t.kind:
#                         self.added_tars.remove(at)
#                         changed = True
#                         break

#                 if not changed:
#                     for at in self.all_tars:
#                         if at.task_id == t.task_id and at.time == t.time and at.kind == t.kind:
#                             self.tar_to_delete.append(at)
#                             self.all_tars.remove(at)
#                             changed = True
#                             self.changed = True
#                             break

#                 if not self.changed:
#                     raise Exception("Didn't remove anything ?")

#         self._redraw()

#     @Slot()
#     def add_task_report(self):
#         if len(self.view.scene().selectedItems()) == 0:
#             self.time_edit_dialog.set_data(None,self.base_time.date())
#         else:
#             selected = self.view.scene().selectedItems()[0]
#             t = selected.data(0)
#             self.time_edit_dialog.set_data(t,self.base_time.date())

#         self.time_edit_dialog.exec_()

#         if self.time_edit_dialog.result() == QDialog.Accepted:

#             self._make_tar(self.time_edit_dialog.tar_type,
#                            self.time_edit_dialog.start_time,
#                            self.time_edit_dialog.task_id)
#             self._redraw()



#     @Slot()
#     def add_presence_report(self):
#         self.presence_dialog.exec_()

#         if self.presence_dialog.result() == QDialog.Accepted:
#             self._make_tar(self.presence_dialog.action_type,
#                            self.presence_dialog.start_time,
#                            dao.task_action_report_dao.presence_task().task_id )
#             self._redraw()
#         else:
#             mainlog.debug("Cancel")



#     def set_data(self, base_time, employee_id):
#         global dao

#         self.added_tars = []
#         self.tar_to_delete = []

#         self.employee_id = employee_id

#         self.employee = dao.employee_dao.find_by_id(employee_id)
#         self.all_tars = dao.task_action_report_dao.load_task_action_reports_for_edit(self.employee, base_time.date())

#         # self.manual_work_timetracks = dao.timetrack_dao.all_work_for_employee_date_manual(self.employee.employee_id, base_time.date())
#         # self.manual_presence_timetracks = dao.timetrack_dao.all_manual_presence_timetracks(self.employee, base_time.date())

#         self.presence_task_id = dao.task_action_report_dao.presence_task().task_id

#         self.base_time = base_time

#         self.presence_dialog.set_base_date(base_time.date())
#         self._redraw()

#         box = self.view.scene().sceneRect().size().toSize()
#         s = QSize(box.width(), box.height() + 80)
#         self.view.setMinimumSize(s)


#     def _redraw(self):

#         self.view.redraw(self.base_time,
#                          self.all_tars + self.added_tars,
#                          self.employee.employee_id,
#                          [],
#                          [])

#         self.save_button.setEnabled( self.edited())

#     def _make_tar(self,action_type, start_time, task_id):
#         mainlog.debug("_make_tar")
#         t = TaskActionReport()

#         t.kind = action_type
#         t.time = start_time
#         t.origin_location = platform.node()
#         t.editor = user_session.name
#         t.reporter_id = self.employee_id # pay attention, this will be merged, so maybe better not to rely on csacding behaviour in SQLA

#         # I've checked that
#         #  - accessing a task_id after a session close is legal
#         #  - accessing a task_id on a never-added-to-session task is legal (and gives None)

#         t.task_id = task_id
#         t.report_time = datetime.today()
#         t.status = TaskActionReport.CREATED_STATUS
#         t.processed = False

#         self.changed = True
#         self.added_tars.append(t)

#         return t









class TimeReportingScannerDialog(QDialog):

    def __init__(self,parent):
        global configuration
        super(TimeReportingScannerDialog,self).__init__(parent)

        self.presence_dialog = PresenceDialog(self)
        self.time_edit_dialog = TimeEditDialog(self)
        self.time_edit_dialog.setMinimumWidth(500)

        title = _("Time reporting scanner")
        self.setWindowTitle(title)
        self.title_widget = TitleWidget(title,self)

        info = QLabel(_("The picture below show the various actions reported for the employee (vertical lines). It also show the time spent on tasks (coloured bars). Right click on any timeline to add new actions or delete existing ones. Click anywhere else to add actions on task which are not shown below. The green bar shows the presence of the employee during the day; it doesn't show actual work. The actual work is shown on the blue bars."),self)
        info.setWordWrap(True)

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.Ok)
        self.buttons.addButton( QDialogButtonBox.Cancel)

        self.thinfont = QFont("Arial",8,QFont.Normal)

        self.view = TheView(self)
        # self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.view.add_presence_report_action.triggered.connect(self.add_presence_report)
        self.view.add_task_report_action.triggered.connect(self.add_task_report)
        self.view.delete_report_action.triggered.connect(self.delete_report)

        top_layout = QVBoxLayout()
        top_layout.addWidget(self.title_widget)
        top_layout.addWidget(info)
        top_layout.addWidget(self.view)
        top_layout.addWidget(self.buttons)

        self.setLayout(top_layout) # QWidget takes ownership of the layout
        self.buttons.accepted.connect(self.save_and_accept)
        self.buttons.rejected.connect(self.cancel)
        self.changed = False


    def set_data(self, base_time, employee_id):
        global dao

        # self.potential_tasks_cache = PotentialTasksCache(dao.task_dao,base_time.date())
        # self.time_edit_dialog.set_potential_tasks_cache(self.potential_tasks_cache)

        self.employee_id = employee_id

        self.employee = dao.employee_dao.find_by_id(employee_id)
        self.all_tars = dao.task_action_report_dao.load_task_action_reports_for_edit(self.employee, base_time.date())
        self.added_tars = []

        self.manual_work_timetracks = dao.timetrack_dao.all_work_for_employee_date_manual(self.employee.employee_id, base_time.date())
        self.manual_presence_timetracks = dao.timetrack_dao.all_manual_presence_timetracks(self.employee, base_time.date())
        self.presence_task_id = dao.task_action_report_dao.presence_task().task_id

        self.base_time = base_time

        self.tar_to_delete = []

        self.presence_dialog.set_base_date(base_time.date())
        self._redraw()

        box = self.view.scene().sceneRect().size().toSize()
        s = QSize(box.width(), box.height() + 80)
        self.view.setMinimumSize(s)


    @Slot()
    def cancel(self):
        # Revert all changes done during the course of this dialog
        # s = session()
        # for tar in self.all_tars:
        #     s.expire(tar)

        if self.changed:
            r = saveCheckBox()
            if r == QMessageBox.Save:
                self._save()
            elif r == QMessageBox.Cancel:
                return

        return super(TimeReportingScannerDialog,self).reject()

    @Slot()
    def save_and_accept(self):
        if self.changed:
            self._save()
        else:
            mainlog.debug("nothing to save")
        return super(TimeReportingScannerDialog,self).accept()


    def _save(self):
        dao.task_action_report_dao.update_tars(self.employee, self.base_time.date(), self.all_tars + self.added_tars, self.tar_to_delete)
        # the dao has commited

    def _task_id_to_task(self,task_id):
        for tar in self.all_tars + self.added_tars:
            # tar = session().merge(itar)
            if tar.task_id == task_id:
                return tar.task
                break

        if self.presence_task_id == task_id:
            return None

        return None


    def _make_tar(self,action_type, start_time, task_id):
        mainlog.debug("_make_tar")
        t = TaskActionReport()

        t.kind = action_type
        t.time = start_time
        t.origin_location = platform.node()
        t.editor = user_session.name
        t.reporter_id = self.employee_id # pay attention, this will be merged, so maybe better not to rely on csacding behaviour in SQLA

        # I've checked that
        #  - accessing a task_id after a session close is legal
        #  - accessing a task_id on a never-added-to-session task is legal (and gives None)

        t.task_id = task_id
        t.report_time = datetime.today()
        t.status = TaskActionReport.CREATED_STATUS
        t.processed = False

        self.changed = True
        self.added_tars.append(t)

        return t


    @Slot()
    def delete_report(self):
        mainlog.debug("delete_report")
        for selected in self.view.scene().selectedItems():
            t = selected.data(0)
            # selected item might not be what we expect...
            if isinstance(t,TaskActionReport):

                changed = False

                for at in self.added_tars:
                    if at.task_id == t.task_id and at.time == t.time and at.kind == t.kind:
                        self.added_tars.remove(at)
                        changed = True
                        break

                if not changed:
                    for at in self.all_tars:
                        if at.task_id == t.task_id and at.time == t.time and at.kind == t.kind:
                            self.tar_to_delete.append(at)
                            self.all_tars.remove(at)
                            changed = True
                            self.changed = True
                            break

                if not self.changed:
                    raise Exception("Didn't remove anything ?")

        self._redraw()

    @Slot()
    def add_task_report(self):
        if len(self.view.scene().selectedItems()) == 0:
            self.time_edit_dialog.set_data(None,self.base_time.date())
        else:
            selected = self.view.scene().selectedItems()[0]
            t = selected.data(0)
            self.time_edit_dialog.set_data(t,self.base_time.date())

        self.time_edit_dialog.exec_()

        if self.time_edit_dialog.result() == QDialog.Accepted:

            self._make_tar(self.time_edit_dialog.tar_type,
                           self.time_edit_dialog.start_time,
                           self.time_edit_dialog.task_id)
            self._redraw()



    @Slot()
    def add_presence_report(self):
        self.presence_dialog.exec_()

        if self.presence_dialog.result() == QDialog.Accepted:
            self._make_tar(self.presence_dialog.action_type,
                           self.presence_dialog.start_time,
                           dao.task_action_report_dao.presence_task().task_id )
            self._redraw()
        else:
            mainlog.debug("Cancel")


    def _merge_all(self, objs):
        return objs

        ret = []
        for o in objs:
            ret.append( session().merge(o))
        return ret


    def _redraw(self):

        self.view.redraw(self.base_time,
                         self.all_tars + self.added_tars,
                         self.employee.employee_id,
                         [],
                         [],
                         view_title=_("Time records for {} on {}").format(self.employee.fullname, date_to_dmy(self.base_time)))

        # self.view.redraw(self.base_time,
        #                  self._merge_all(self.all_tars + self.added_tars),
        #                  self.employee,
        #                  self._merge_all(self.manual_work_timetracks),
        #                  self._merge_all(self.manual_presence_timetracks))

        # This to make sure that we maintain no lock in the transaction
        # after having completed the drawing

        session().commit()





class PresenceDialog(QDialog):
    def __init__(self,parent):
        super(PresenceDialog,self).__init__(parent)

        self.model = QuickComboModel(None)

        self.tar_type_edit = TaskActionReportTypeComboBox("action_type",_("Action"),nullable=False)
        self.tar_type_edit.set_model([TaskActionReportType.day_in,
                                      TaskActionReportType.day_out])
        self.start_time_edit = TimeStampEdit("start_time",_("Start time"),nullable=False)
        self.form_fields = [self.tar_type_edit, self.start_time_edit]

        form_layout = QFormLayout()
        form_layout.addRow( _("Action"), self.tar_type_edit.widget)
        form_layout.addRow( _("Start time"), self.start_time_edit.widget)

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.Ok)
        self.buttons.addButton( QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.save_and_accept)
        self.buttons.rejected.connect(self.cancel)

        top_layout = QVBoxLayout()
        top_layout.addLayout(form_layout)
        top_layout.addWidget(self.buttons)

        self.setLayout(top_layout)





    def set_base_date(self,d):
        self.start_time_edit.set_base_date(d)


    @Slot()
    def cancel(self):
        self.start_time = None
        self.action_type = None
        return super(PresenceDialog,self).reject()


    def check_and_store(self,editors,obj):
        errors = []

        for editor in editors:
            check_result = editor.check()
            if check_result != True:
                errors.append(_("In field {} : {}").format(editor.field_name, check_result))

        if len(errors) == 0:
            for editor in editors:
                setattr(obj, editor.field_name, editor.value)
            return True
        else:
            return errors


    @Slot()
    def save_and_accept(self):

        check = self.check_and_store(self.form_fields,self)
        if check == True:
            return super(PresenceDialog,self).accept()
        else:
            # FIXME The following sets don't work at all (color-wise)
            # self.start_time_widget.palette().setColor(QPalette.Base, QColor(255,128,128))
            # self.start_time_widget.palette().setColor(QPalette.WindowText, QColor(255,128,128))
            showMultiErrorsBox(check)
            return




class TimeEditDialog(QDialog):

    def set_potential_tasks_cache(self,potential_tasks_cache):
        self.potential_tasks_cache = potential_tasks_cache


    def set_data(self,task,base_date):

        mainlog.debug(u"TimeEditDialog.set_data : {}".format(task))

        self.base_date = base_date
        self.start_time_editor.set_base_date(base_date)
        self.start_time_editor.set_value(None)

        op = None

        # if task:
        #     if isinstance(task,TaskOnOperation):
        #         op = task.operation
        #     elif isinstance(task,TaskOnOrder):
        #         op = task.order
        #     elif isinstance(task,TaskOnNonBillable):
        #         op = task.operation_definition
        #     else:
        #         raise Exception("Unknown TaskOnXxx type : {}".format(type(task)))

        if not task:
            mainlog.debug("TimeEditDialog: set_data No task")
            self.identifier_editor.set_value(None)
            # self.identifier_set()
            self._set_operation_for_identifier()
            self.last_validated_identifier = None
            # self.task_widget.make_str_model([], [])
            # self.machine_editor.make_str_model([], [])
            self.tar_type_editor.widget.setCurrentIndex(0)

        elif task.type == TaskOnOperation:
            # identifier = op.production_file.order_part.human_identifier

            mainlog.debug("TimeEditDialog on {}".format(task.order_part_label))

            self.identifier_editor.set_value(task.order_part_label)
            self.last_validated_identifier = task.order_part_label

            self._configure_task_combo_for_order_part(task.order_part_id)

            i = 0
            for r in self.task_widget.model().references:
                if r.operation_id == task.operation_id:
                    self.task_widget.setCurrentIndex( i)
                    break
                else:
                    i += 1

            mainlog.debug("TimeEditDialog task.machine_id = {}".format(task.machine_id))
            i = 0
            for r in self.machine_editor.model.references:
                mainlog.debug("TimeEditDialog ref = {} of type {}".format(r, type(r)))

                if (r == None and task.machine_id == None) or (r != None and r.machine_id == task.machine_id):
                    self.machine_editor.widget.setCurrentIndex( i)
                    break
                else:
                    i += 1

        elif isinstance(op,Order):

            identifier = str(op.label)
            self.identifier_editor.set_value(identifier)
            self.last_validated_identifier = identifier
            self._configure_task_combo(self.task_widget,op)

        elif isinstance(op,OperationDefinition):

            identifier = None
            self.identifier_editor.set_value(identifier)
            self.last_validated_identifier = identifier
            self._configure_task_combo(self.task_widget,None)
            i = 0
            for task in self.task_widget.model().references:
                if task.operation_definition == op:
                    self.task_widget.setCurrentIndex( i)
                    break
                else:
                    i += 1
        else:
            self.identifier_editor.set_value(None)
            self.last_validated_identifier = None
            self.task_widget.make_str_model([], [])
            # self.machine_editor.make_str_model([], [])
            self.machine_editor.set_model([])
            self.tar_type_editor.widget.setCurrentIndex(0)

        session().commit()


    def _validate_identifier(self,text):
        if text and len(text) > 0:
            # If the user didn't enter anything in the cell
            # then we won't check anything. This is to handle
            # the case where one starts editing a cell and
            # then stop editing by clicking out of the table.

            # We look for order_parts, those are named like '1234A'
            t = dao.order_part_dao.find_by_full_id(text)
            t = dao.order_part_dao.find_by_ids(t)

            session().commit()

            mainlog.debug("With identifier {}, found order part {}".format(text,t))
            if t:
                t = [part for part in t if part.accounting_part_label][0]

                if t:
                    return t
                else:
                    showWarningBox(_("Time reporting only on orders ready for production"),"")
                    return False
            else:
                # No part were found, so we look for an order
                # whose name is like '1234' (no X part)

                try:
                    oid = int(text)
                    t = dao.order_dao.find_by_accounting_label(oid,True)
                    session().commit()
                except ValueError as ex:
                    pass

                if t:
                    if t.state == OrderStatusType.order_ready_for_production:
                        return t
                    else:
                        showWarningBox(_("Time reporting only on orders ready for production"),"")
                        return False
                else:
                    showWarningBox(_("The order or order part with number {} doesn't exist.").format(text),"")
                    return False
        else:
            return None




    def _set_operation_for_identifier(self):
        identifier = self.identifier_editor.value
        self.identifier_editor.mark_current_as_original()

        tasks = self._identifier_to_task_data(identifier)

        self.task_widget.make_str_model([t.description for t in tasks],
                                        tasks)



    @Slot()
    def identifier_set(self):
        mainlog.debug("identifier_set in_validation ? {}".format(self.in_validation))

        if not self.in_validation:
            # For some reason, when I hit Enter in the field
            # method get called twice. That doesn't happen when
            # I hit tab. I guess it's because when I hit Enter
            # and show a warning dialog, this does two things.
            # First, the line edit widget detects the "enter" and
            # fires the editingFinished signal. That triggers this code
            # and shows a dialog. This in turn removes the focus
            # of the line edit which, again, triggers the editingFinished
            # signal

            self.in_validation = True

            if self.identifier_editor.changed():
                mainlog.debug("Identifier has changed")
                # self.identifier_editor.set_value(self.identifier_editor.value)
                # self.last_validated_identifier = self.identifier_widget.text()

                self._set_operation_for_identifier()

                # t = self._validate_identifier(self.identifier_editor.value)
                # if t is not False:
                #     self._configure_task_combo(self.task_widget,t)
                #     session().commit()
                # else:
                #     self.task_widget.make_str_model([], [])
                #     mainlog.debug("Setting focus")
                #     self.identifier_editor.widget.setFocus(Qt.OtherFocusReason)
            else:
                mainlog.debug("Identifier has *not* changed")

            self.in_validation = False



    @Slot(int)
    def operation_set(self, ndx):
        mainlog.debug("operation_set")

        i = self.task_widget.currentIndex()
        op = self.task_widget.itemData(i)

        if op:
            machines = machine_service.find_machines_for_operation_definition(op.operation_definition_id)

            mainlog.debug("operation_set : machines are {}".format(machines))
            mainlog.debug("operation_set : machines are types {}".format([type(m) for m in machines]))

            # machines = [machine_service.find_machine_by_id(i) for i in machine_ids]

            self.machine_editor.set_model(machines)

            # labels = []
            # items = []
            # for m in machines:
            #     labels.append(m.fullname)
            #     items.append(m.machine_id)

            # mainlog.debug(labels)
            # self.machine_editor.make_str_model(labels, items)

            # print("operation set")
            # print(op)
        else:
            self.machine_editor.set_model([])


    def __init__(self,parent):
        super(TimeEditDialog,self).__init__(parent)


        self.in_validation = False
        self.last_validated_identifier = None

        self.identifier_editor = OrderPartIdentifierEdit("identifier",_("identifier"),parent=self)
        self.identifier_editor.widget.editingFinished.connect(self.identifier_set)


        # self.identifier_widget = QLineEdit(self)
        # self.identifier_widget_validator = OrderPartIdentifierValidator()
        # self.identifier_widget.setValidator(self.identifier_widget_validator)
        # self.identifier_widget.editingFinished.connect(self.identifier_set)

        self.task_widget = AutoCompleteComboBox(None,self)
        self.task_widget.section_width = [300]
        self.task_widget.currentIndexChanged.connect(self.operation_set)

        self.tar_type_editor = TaskActionReportTypeComboBox("tar_type",_("Action"))
        self.tar_type_editor.set_model([TaskActionReportType.start_task,TaskActionReportType.stop_task])


        self.machine_editor = ConstrainedMachineEdit("machine_id",_("Machine"))
        # self.machine_editor = AutoCompleteComboBox(None,self)
        # self.machine_editor.set_model(machine_service.find_machines_for_operation_definition(proxy.operation_definition_id))


        self.start_time_editor = TimeStampEdit("start_time",_("Start time"),nullable=False)

        form_layout = QFormLayout()
        form_layout.addRow( _("Identifier"), self.identifier_editor.widget)
        form_layout.addRow( _("Task"), self.task_widget)
        form_layout.addRow( _("Machine"), self.machine_editor.widget)
        form_layout.addRow( _("Action"), self.tar_type_editor.widget)
        form_layout.addRow( _("Start time"), self.start_time_editor.widget)
        top_layout = QVBoxLayout()
        top_layout.addLayout(form_layout)

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.Ok)
        self.buttons.addButton( QDialogButtonBox.Cancel)

        top_layout.addWidget(self.buttons)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.cancel)

        self.setLayout(top_layout)


    @Slot()
    def cancel(self):
        self.start_time = None
        self.task = None
        return super(TimeEditDialog,self).reject()

    @Slot()
    def accept(self):
        """ Accepting the dialog DOESN'T imply the creation of the TAR.
        BUT it DOES imply the creation of its task. That's done this way
        to simplify the code. That rests on the hypothesis that it's
        not a problem to create a task for nothing (for exampe, the user
        creates a TAR, then deletes it, then accept the whole edit
        dialog => at that point, a task may have been created for nothing.
        """

        err = []

        if not self.start_time_editor.check():
            err.append( _("Start time is not valid"))
            self.start_time = None

        if not self.tar_type_editor.check():
            err.append(_("Type of task is not valid"))
            self.tar_type = None

        if not self.task_widget.itemData(self.task_widget.currentIndex()):
            err.append(_("No task selected"))
            self.task = None

        if len(err) > 0:
            showMultiErrorsBox(err)
            return
        else:
            task_data = self.task_widget.itemData(self.task_widget.currentIndex())

            if task_data.type == Operation:
                # Grab current machine

                mainlog.debug("Accept : {}".format(type(self.machine_editor.value)))
                mainlog.debug("Accept : {}".format(self.machine_editor.value))

                if self.machine_editor.value:
                    m_id = self.machine_editor.value.machine_id
                else:
                    m_id = None
                mainlog.debug("Accept : machine_id = {}".format(m_id))

                self.task_id = dao.task_dao._get_task_for_operation_and_machine(task_data.operation_id, m_id) # task_data.machine_id)
            elif task_data.type == Order:
                self.task_id = dao.task_dao._get_task_for_order(task_data.order_id, task_data.operation_definition_id)
            elif task_data.type == OperationDefinition:
                self.task_id = dao.task_dao._get_task_for_non_billable(task_data.operation_definition_id)
            else:
                self.task_id = None
                raise Exception("Unrecognized task type")


            self.start_time = self.start_time_editor.value
            self.tar_type = self.tar_type_editor.value

            return super(TimeEditDialog,self).accept()


    def keyPressEvent(self,event):

        # The goal here is to make sure the accept signal is called only
        # if the user clicks on the "OK" button /with the mouse/ and,
        # not with the keyboard.

        if event.key() in (Qt.Key_Enter, Qt.Key_Return):
            return
        else:
            super(TimeEditDialog,self).keyPressEvent(event)


    def _configure_task_combo_for_order_part(self, order_part_id):

        operations = dao.operation_dao.find_by_order_part_id_frozen(order_part_id)

        labels = []
        data = []

        for op in operations:
            labels.append(op.description)

            d = { "type" : Operation,
                  "operation_id" : op.operation_id,
                  "operation_definition_id" : op.operation_definition_id
            }
            data.append(DictAsObj(d))

        self.task_widget.make_str_model(labels, data)


    def _configure_task_combo(self,combo,task_data):
        # tasks = self.potential_tasks_cache.tasks_for_identifier(identifier)


        tasks = dao.task_dao.potential_imputable_tasks_flattened(task_data.type,
                                                                 task_data.operation_id,
                                                                 self.base_date)

        labels = []

        # print tasks

        for t in tasks:
            # session().merge(t)

            if isinstance(t,TaskOnOrder):
                labels.append(t.operation_definition.description)
            elif t.type == TaskOnOperation:
                labels.append( u"{}: {}".format(t.operation_definition_short_id, t.operation_description or u""))
            elif isinstance(t,TaskOnNonBillable):
                labels.append(t.operation_definition.description)
            else:
                raise Exception("Unknown TaskOnXxx type : {}".format(type(t)))

        mainlog.debug(u"Combo init identifier:{} with tasks :".format(identifier))

        for i in range(len(tasks)):
            mainlog.debug(labels[i])
            mainlog.debug(tasks[i])


    def _identifier_to_task_data(self, text):
        if text:
            text = text.strip().upper()
        else:
            text = ""

        # Use this !
        # FIXME this : from sqlalchemy.util._collections import KeyedTuple

        tasks_data = []

        if OrderPart.re_order_part_identifier.match(text):

            t = dao.order_part_dao.find_by_full_id(text)
            t = [ dao.order_part_dao.find_by_id(part_id) for part_id in t]

            # t = [part for part in t if part.accounting_part_label][0]

            if t:
                t = t[0]
                for op in t.operations:
                    d = { "type" : type(op),
                          "operation_id" : op.operation_id,
                          "operation_definition_id" : op.operation_definition_id,
                          "description" : u"[{}] {}".format(t.human_identifier,op.description)
                        }

                    tasks_data.append(d)

        elif Order.re_order_identifier.match(text):

            oid = int(text)
            order = dao.order_dao.find_by_accounting_label(oid,True)

            if order:
                for opdef in dao.operation_definition_dao.all_on_order(): # BUG Date not takne into account !!!
                    d = { "type" : type(order),
                          "operation_definition_id" : opdef.operation_definition_id,
                          "description" : u"[{}] {}".format(oid, opdef.description)
                        }
                    tasks_data.append(d)

        elif not text:

            for opdef in dao.operation_definition_dao.all_imputable_unbillable(date.today()):
                d = { "type" : OperationDefinition,
                      "operation_definition_id" : opdef.operation_definition_id,
                      "description" : u"[{}] {}".format(opdef.short_id, opdef.description)
                }

                tasks_data.append(d)

        else:
            raise Exception("Unrecognized identifier")


        tasks_data = [DictAsObj(td) for td in tasks_data]

        for td in tasks_data:
            mainlog.debug(td.type, td.description)

        return tasks_data



if __name__ == '__main__':


    import sys
    from PySide.QtGui import QApplication


    from koi.db_mapping import TaskOnOperation,Employee

    employee = Employee()
    employee.fullname = "TestName"
    user_session.open(employee)



    # 000100847802

    app = QApplication(sys.argv)


    # d = PresenceDialog(None)
    # d.set_base_date(date(2013,4,30))
    # d.exec_()

    # d = TimeEditDialog(None)
    # potential_tasks_cache = PotentialTasksCache(dao.task_dao,date(2013,4,30))
    # d.set_potential_tasks_cache(potential_tasks_cache)
    # d.set_data(None,date(2013,4,30))
    # d.exec_()

    # window = QMainWindow()
    # w = TimeReportingScannerWidget(None)
    # w.set_data(datetime(2013,4,29,6,0), 16) # or 16
    # window.setCentralWidget(w)
    # window.show()
    # app.exec_()

    d = TimeReportingScannerDialog(None)
    d.set_data(datetime(2013,4,29,6,0),16) # or 16
    d.exec_()

    """
    4000A -> choose operation -> choose machine -> choose start/stop
    4000 -> choose order-operation -> choose start/stop
    """

    text = "4000A"
