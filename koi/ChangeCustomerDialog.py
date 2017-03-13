from PySide.QtCore import Slot
from PySide.QtGui import QHBoxLayout,QVBoxLayout, QDialogButtonBox,QDialog

if __name__ == "__main__":
    import sys
    from PySide.QtGui import QApplication

    from koi.base_logging import init_logging
    from koi.Configurator import init_i18n,load_configuration,configuration

    init_logging()
    init_i18n()
    load_configuration()

    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session
    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)

from koi.gui.dialog_utils import makeErrorBox,TitleWidget
from koi.CustomerPlateWidget import CustomerContactDataWidget
from koi.gui.ProxyModel import TextLinePrototype
from koi.gui.QuickPrototypedFilter import QuickPrototypedFilter

#noinspection PyUnresolvedReferences
from koi.dao import dao

        
class ChangeCustomerDialog(QDialog):

    def __init__(self,parent):
        global dao
        super(ChangeCustomerDialog,self).__init__(parent)

        title = _("Choose customer")
        self.setWindowTitle(title)
        top_layout = QVBoxLayout()
        self.title_widget = TitleWidget(title,self)
        top_layout.addWidget(self.title_widget)

        self.customer_plate_widget = CustomerContactDataWidget(self)
        
        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.StandardButton.Cancel)
        self.buttons.addButton( QDialogButtonBox.Ok)

        hlayout = QHBoxLayout()

        customers = dao.customer_dao.all_frozen()
        self.customer_plate_widget.set_contact_data(customers[0])

        table_prototype = [ TextLinePrototype('fullname',_('Name'),editable=False) ]
        self.filter_view = QuickPrototypedFilter(table_prototype,self)
        self.filter_view.set_data(customers,lambda c:c.indexed_fullname)
        self.filter_view.selected_object_changed.connect(self.customer_plate_widget.set_contact_data)
        
        hlayout.addWidget(self.filter_view)
        hlayout.addWidget(self.customer_plate_widget,1000)
        top_layout.addLayout(hlayout)

        # top_layout.addStretch()
        top_layout.addWidget(self.buttons)
        self.setLayout(top_layout)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    @Slot()
    def accept(self):
        self.customer_id = None
        if self.filter_view.last_selected_object:
            customer_id = self.filter_view.last_selected_object.customer_id
        else:
            customer_id = None

        if customer_id is None:
            msgBox = makeErrorBox(_("Please choose a customer for the new order"))
            msgBox.exec_()
            # super(ChangeCustomerDialog,self).accept()
            return False

        self.customer_id = customer_id
        return super(ChangeCustomerDialog,self).accept()

    @Slot()
    def reject(self):
        self.customer_id = None
        return super(ChangeCustomerDialog,self).reject()


if __name__ == "__main__":

    # 000100847802

    app = QApplication(sys.argv)
    dialog = ChangeCustomerDialog(None)
    dialog.exec_()
