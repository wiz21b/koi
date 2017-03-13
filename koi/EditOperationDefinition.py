from koi.gui.ProxyUneditableTableView import ProxyUneditableTableView

#noinspection PyUnresolvedReferences
from koi.dao import dao

if __name__ == "__main__":
    import sys
    from PySide.QtGui import QApplication

    from koi.base_logging import init_logging
    from koi.Configurator import init_i18n,load_configuration,configuration

    init_logging()
    init_i18n()
    load_configuration()
    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session,session

    init_db_session(configuration.database_url, metadata, configuration.echo_query or False)

from datetime import timedelta

from PySide.QtCore import Slot, Qt
from PySide.QtGui import QDialog, QDialogButtonBox, QPushButton
from PySide.QtGui import QWidget,QVBoxLayout,QHBoxLayout,QLineEdit, QLabel, QHeaderView

from koi.db_mapping import OperationDefinition,OperationDefinitionPeriod
from koi.datalayer.database_session import session
from koi.gui.dialog_utils import TitleWidget,showErrorBox
from koi.gui.ProxyModel import TextLinePrototype, BooleanPrototype, DatePrototype,Prototype,MoneyPrototype,TrackingProxyModel,DBObjectActionTypes
from koi.datalayer.generic_access import blank_dto
from koi.date_parser import SimpleDateParser
from koi.gui.MetaFormDialog import MetaFormDialog



# from datetime import timedelta,date

# from PySide.QtGui import QHeaderView,QLabel
# from koi.ProxyUneditableTableView import ProxyUneditableTableView
# from koi.ProxyModel import Prototype,DBObjectActionTypes,BooleanPrototype,DatePrototype,MoneyPrototype, TrackingProxyModel
# from koi.db_mapping import OperationDefinition,OperationDefinitionPeriod
# from koi.dao import dao
# from koi.date_parser import SimpleDateParser



class OperationDefinitionPeriodsWidget(QWidget):
    def __init__(self, parent=None):
        super(OperationDefinitionPeriodsWidget,self).__init__(parent)

        # FIXME Pay attention, we use a non-editable table view *but*
        # the prototypes below say "editable=True". This is because
        # we'll edit the table ourselves, set dates inside it.
        # That must be copied back in the obect on save. And that
        # copy only occurs if "editable" is True.

        self.prototype = [ DatePrototype('start_date',_('Start date'),editable=True),
                           DatePrototype('end_date',_('End date'),editable=True),
                           MoneyPrototype('cost',_('Cost'),editable=True) ]

        view = ProxyUneditableTableView(self.prototype)
        view.verticalHeader().hide()

        self.model = TrackingProxyModel(self,self.prototype)
        self.model.clear()
        view.setModel(self.model)

        layout = QVBoxLayout()
        layout.addWidget(view)
        self.view = view

        blayout = QHBoxLayout()

        b = QPushButton(_("New period"))
        b.clicked.connect(self.new_period_action)
        blayout.addWidget(b)

        b = QPushButton(_("Delete last period"))
        b.clicked.connect(self.delete_last_period_action)
        blayout.addWidget(b)
        layout.addLayout(blayout)

        self.setLayout(layout)


    def setData(self,objects):
        if objects and len(objects) > 0:
            self.model._buildModelFromObjects(objects,self.prototype)
        else:
            self.model.clear()
        self.view._setup_horizontal_header(self.prototype)


    @Slot(bool) # BUG in PySide? Says bool, but doesn't pass the bool to the function
    def delete_last_period_action(self):

        #if self.model.rowCount() > 1:
            # Remove the last row
        self.model.removeRows(self.model.rowCount()-1,1)

        # The last of the periods never has an end
        m = self.model
        if m.rowCount() >= 1:
            ndx_pre_period_end = m.index(m.rowCount()-1,1)
            m.setData( ndx_pre_period_end, None, Qt.UserRole)

            self.model.reset() # Trigger redraw, rough


    def _append_period(self, cost, start_date):
        m = self.model
        if m.rowCount() >= 1:
            # Adding a period truncates the previous one if any.
            ndx_pre_period_end = m.index(m.rowCount()-1,1)
            m.setData( ndx_pre_period_end, start_date - timedelta(1), Qt.UserRole)

        m.insertRows(m.rowCount(),1,)
        ndx_new_period = m.index(m.rowCount()-1,0)
        m.setData( ndx_new_period, start_date, Qt.UserRole)
        ndx_new_period = m.index(m.rowCount()-1,1)
        m.setData( ndx_new_period, None, Qt.UserRole) # end date
        ndx_new_period = m.index(m.rowCount()-1,2)
        m.setData( ndx_new_period, cost, Qt.UserRole)


    @Slot(bool)
    def new_period_action(self):
        d = AddPeriodDialog(self)

        d.exec_()
        if d.result() == QDialog.Accepted:

            cost, start_date = d.data()
            self._append_period(cost, start_date)

        d.deleteLater()



class OperationDefinitionPeriodsPrototype(Prototype):
    def __init__(self, field, title, editable=False):
        super(OperationDefinitionPeriodsPrototype,self).__init__(field,title,editable,nullable=True,hidden=False)

    def edit_widget(self,parent):
        if not self._widget:
            self._widget = OperationDefinitionPeriodsWidget() # Pay attention, no parent !
        return self._widget

    def enable_edit_widget(self,b):
        return self._widget.setEnabled(b)

    def set_edit_widget_data(self,periods):
        self.edit_widget(None).setData(periods)

    def validate(self,value):
        if value is None or len(value) == 0:
            return _("{} can't be empty").format(self.title)
        else:
            return True

    def edit_widget_data(self):
        m = self.edit_widget(None).model
        #mainlog.debug(m.rowCount())

        periods = []

        actions = m.model_to_objects(lambda : blank_dto(OperationDefinitionPeriod))
        # mainlog.debug("Loading edit_widget_data")
        # mainlog.debug(actions)

        for i in range(len(actions)):
            action_type,op,op_ndx = actions[i]

            if action_type != DBObjectActionTypes.TO_DELETE:
                periods.append(op)

            # if action_type == DBObjectActionTypes.TO_CREATE:
            #     session().add(op)
            #     periods.append(op)

            # elif action_type == DBObjectActionTypes.TO_DELETE:
            #     mainlog.debug("delete")
            #     op = session().merge(op)
            #     session().delete(op)
            #     mainlog.debug("done delete")

            # else :
            #     mainlog.debug("Merging")
            #     op = session().merge(op)
            #     periods.append(op)

        return periods




class AddPeriodDialog(QDialog):
    def __init__(self,parent):
        super(AddPeriodDialog,self).__init__(parent)

        t = _("Add a period for an operation definition")
        self.setWindowTitle(t)
        self.title_widget = TitleWidget(t,self)

        top_layout = QVBoxLayout()
        top_layout.addWidget(self.title_widget)

        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel(_("Start time"),self))
        self.date_edit = QLineEdit(self)
        hlayout.addWidget(self.date_edit)
        top_layout.addLayout(hlayout)

        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel(_("Hourly cost"),self))
        self.hourly_cost = QLineEdit(self)
        hlayout.addWidget(self.hourly_cost)
        top_layout.addLayout(hlayout)

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.Ok)
        top_layout.addWidget(self.buttons)

        self.setLayout(top_layout) # QWidget takes ownership of the layout

        self.buttons.accepted.connect(self.accepted)

    def data(self):
        parser = SimpleDateParser()
        # the cost, the begin date
        return float(self.hourly_cost.text()),  parser.parse(self.date_edit.text())


    @Slot()
    def accepted(self):
        parser = SimpleDateParser()

        cost = 0
        try:
            cost = float(self.hourly_cost.text())
        except ValueError as ex:
            showErrorBox(_("The given cost is not valid"),
                         _("The given cost doesn't look like a cost"))
            return False


        d = parser.parse(self.date_edit.text())
        if not d:
            showErrorBox(_("The given date is not valid"),
                         _("Please check the syntax and that the date exists"))
            return False
        # elif d <= self.periods[-1].start_date:
        #     showErrorBox(_("The given date is not valid"),
        #                  _("The given date is before or equal to the current last date ({}). It must be after.").\
        #                      format(self.base_opdef.periods[-1].start_date)) # FIXME Use proper date formatter
        #     return False
        else:
            return super(AddPeriodDialog,self).accept()



class EditOperationDefinitionsDialog(MetaFormDialog):

    def __init__(self,parent):

        self.key_field = 'operation_definition_id'

        table_prototype = [TextLinePrototype('description',_('Description'),editable=False),
                           TextLinePrototype('short_id',_('ID'),editable=False)]


        form_prototype = [ TextLinePrototype('short_id',_('Short ID'),nullable=False),
                           TextLinePrototype('description',_('Description'),nullable=False),
                           BooleanPrototype('imputable',_('Imputable'),default=True,nullable=False),
                           BooleanPrototype('on_order',_('On orders'),nullable=False),
                           BooleanPrototype('on_operation',_('On operations'),default=True,nullable=False),
                           OperationDefinitionPeriodsPrototype('periods',_('Periods'),editable=True) ]

        super(EditOperationDefinitionsDialog,self).__init__(parent,
                                                            _("Edit operations"),
                                                            _("All operations"),
                                                            _("Operation"),
                                                            OperationDefinition,
                                                            table_prototype,
                                                            form_prototype,
                                                            OperationDefinition.description,
                                                            lambda opdef : opdef.short_id + opdef.description )

        self.list_view.horizontalHeader().setStretchLastSection(False)
        self.list_view.horizontalHeader().setResizeMode(0, QHeaderView.Stretch)
        self.list_view.horizontalHeader().setResizeMode(1, QHeaderView.ResizeToContents)

        self.setMinimumWidth(800)

    # FIXME

    # def check_before_save(self,opdef):

    #     opdef2 = dao.operation_definition_dao.find_by_short_id(opdef.short_id)
    #     mainlog.debug(u"check_before_save {}".format(opdef2))
    #     if opdef2 and opdef2.operation_definition_id != opdef.operation_definition_id:
    #         return _("There's already an operation with short id '{}', it is : {}").format(opdef2.short_id,opdef2.description)
    #     else:
    #         return True

    def objects_list(self):
        # FIXME database code here...

        global dao
        l = dao.operation_definition_dao.all()
        for opdef in l:
            x = opdef.operation_definition_id
            for p in opdef.periods:
                x = p.cost
                session().expunge(p)

            session().expunge(opdef)

        session().close()
        return l


    def delete_object(self, o_id):
        if not dao.operation_definition_dao.is_used(o_id):
            return super(EditOperationDefinitionsDialog, self).delete_object(o_id)
        else:
            showErrorBox(_("Operation definition already in use !"),"")
            return False


if __name__ == "__main__":

    app = QApplication(sys.argv)
    # widget = EditCustomerDialog(None)
    # widget = EditEmployeeDialog(None,dao)
    # widget = EditUserDialog(None,dao)
    widget = EditOperationDefinitionsDialog(None)
    widget.show()

    app.exec_()
