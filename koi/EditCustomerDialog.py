import sys



if __name__ == "__main__":
    from PySide.QtGui import QApplication

    from koi.base_logging import mainlog,init_logging
    from koi.Configurator import init_i18n,load_configuration,configuration

    init_logging()
    init_i18n()
    load_configuration()

    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session,session

    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)


from koi.Configurator import mainlog
from koi.db_mapping import Customer, Employee
from koi.datalayer.employee_mapping import RoleType

from koi.datalayer.database_session import session

from PySide.QtCore import Signal,Qt
from PySide.QtGui import QTableView,QStandardItemModel,QStandardItem

from koi.gui.ProxyModel import Prototype, TextLinePrototype, PicturePrototype,BooleanPrototype,TextAreaPrototype,PasswordPrototype
from koi.gui.CheckBoxDelegate import CheckBoxDelegate

from koi.dao import dao

from koi.gui.MetaFormDialog import MetaFormDialog




class EditCustomerDialog(MetaFormDialog):
    customer_changed = Signal(int)

    def __init__(self,parent):
        table_prototype = []
        table_prototype.append( TextLinePrototype('fullname',_('Name'),editable=False))

        form_prototype = [ TextLinePrototype('fullname',_('Name'),nullable=False),
                           TextLinePrototype('phone',_('Phone'),nullable=True),
                           TextLinePrototype('phone2',_('Phone 2'),nullable=True),
                           TextLinePrototype('fax',_('Fax'),nullable=True),
                           TextLinePrototype('email',_('E-Mail'),nullable=True),
                           TextLinePrototype('address1',_('Address 1'),nullable=True),
                           TextLinePrototype('address2','',nullable=True),
                           TextLinePrototype('country',_('Country'),nullable=True),
                           TextAreaPrototype('notes',_('Notes'),nullable=True),
                           # customer id is an integer but no value must be None, not zero.
                           # FIXME Ideally, I should not be using a textlineprototype for this...
                           TextLinePrototype('customer_id',_('ID'),editable=False,empty_string_as_None=True)]

        super(EditCustomerDialog,self).__init__(parent,_("Edit customer"),_("Customers"),_("Detail"),
                                                Customer,table_prototype,form_prototype,'fullname',index_builder=lambda o:o.indexed_fullname)

    def _validate_and_save(self,form_data):
        r = super(EditCustomerDialog,self)._validate_and_save(form_data)

        if r:
            self.customer_changed.emit(r)

        return r

from koi.translators import text_search_normalize


class EditEmployeeDialog(MetaFormDialog):
    def __init__(self,parent,dao):
        self.key_field = 'employee_id'

        employee_prototype = []
        employee_prototype.append( TextLinePrototype('fullname',_('Name'),editable=False))

        form_prototype = [ TextLinePrototype('fullname',_('Name'),nullable=False),
                           PicturePrototype('image',_('Picture'),nullable=True),
                           BooleanPrototype('is_active',_('Active'),nullable=False,default=True),
                           TextLinePrototype('login',_('Login'),nullable=False),
                           PasswordPrototype('password',_('Password')),
                           RoleEditPrototype('roles',_('Roles'))]

        # super(EditEmployeeDialog,self).__init__(parent,
        #                                         _("Employee edit"),
        #                                         _("All employees"),
        #                                         _("Employee data"),
        #                                         employee_prototype,
        #                                         form_prototype)

        super(EditEmployeeDialog,self).__init__(parent,_("Employee edit"),_("Employees"),_("Detail"),
                                                Employee,employee_prototype,form_prototype,'fullname',index_builder=lambda o:text_search_normalize(o.fullname))

        self.setMinimumWidth(800)



    def objects_list(self):
        global dao
        l = dao.employee_dao.all()
        for employee in l:
            x = employee.employee_id
            x = employee.image
            session().expunge(employee)
        session().close()
        return l



class RoleEditWidget(QTableView):
    def __init__(self, parent=None):
        super(RoleEditWidget,self).__init__(parent)
        self.horizontalHeader().hide()
        self.verticalHeader().hide()
        self.check_delegate = CheckBoxDelegate()
        self.setItemDelegateForColumn(0, self.check_delegate)

    def selection(self):
        s = set()
        m = self.model()
        if not m:
            return s

        for row in range(m.rowCount()):
            if m.data( m.index(row,0)) == True:
                s.add(m.data( m.index(row,1), Qt.UserRole))
        return s

    def setData(self,data):
        """ data = [ (role, role.description, role active or not (True or False, not None)) ]
        """
        m = QStandardItemModel(len(data),2)

        row = 0
        for d in data:
            item = QStandardItem()
            item.setData(d[2],Qt.EditRole)
            m.setItem(row,0,item)

            item = QStandardItem()
            item.setData(d[0],Qt.UserRole)
            item.setData(d[1],Qt.DisplayRole)
            m.setItem(row,1,item)

            row += 1

        self.setModel(m)
        self.resizeColumnsToContents()


class RoleEditPrototype(Prototype):
    def __init__(self, field, title):
        super(RoleEditPrototype,self).__init__(field,title,editable=True,nullable=True,hidden=False)

    def edit_widget(self,parent):
        if not self._widget:
            self._widget = RoleEditWidget() # Pay attention, no parent !
        return self._widget

    def enable_edit_widget(self,b):
        return self._widget.setEnabled(b)

    def set_edit_widget_data(self,data):
        mainlog.debug(u"set_edit_widget_data {}".format(data))
        chosen_roles = []
        if data is not None:
            chosen_roles = data

        data = []
        for r in RoleType.symbols():
            data.append((r,r.description,r in chosen_roles))

        self._widget.setData(data)

    def edit_widget_data(self):
        r = self._widget.selection()
        mainlog.debug(u"edit_widget_data : {}".format(r))
        return r




if __name__ == "__main__":

    app = QApplication(sys.argv)
    widget = EditEmployeeDialog(None,dao)
    # widget = EditCustomerDialog(None)
    widget.show()

    app.exec_()
