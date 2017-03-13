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
from koi.translators import text_search_normalize
from koi.user_mgmt.user_role_mapping import UserClass

class EditUserClass(MetaFormDialog):
    def __init__(self,parent):
        self.key_field = 'employee_id'

        user_class_prototype = []
        user_class_prototype.append( TextLinePrototype('name',_('Name'),editable=False))

        form_prototype = [ TextLinePrototype('name',_('Name'),nullable=False),
                           RoleEditPrototype('roles',_('Roles'),)]

        super(EditUserClass,self).__init__(parent,_("User class edit"),_("User Class"),_("Detail"),
                                                UserClass,user_class_prototype,form_prototype,'name',index_builder=lambda o:text_search_normalize(o.name))

        self.setMinimumWidth(800)


    # def objects_list(self):
    #     return []



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
        """ data = [ (role, role.description, role is selected or not (True or False, not None)) ]
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

    def default_value(self):
        return set()

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
            data.append( (r,r.description, r in chosen_roles) )

        self._widget.setData(data)

    def edit_widget_data(self):
        r = self._widget.selection()
        mainlog.debug(u"edit_widget_data : {}".format(r))
        return r




if __name__ == "__main__":

    import sys
    app = QApplication(sys.argv)
    # widget = EditEmployeeDialog(None,dao)
    widget = EditUserClass(None)
    widget.show()

    app.exec_()
