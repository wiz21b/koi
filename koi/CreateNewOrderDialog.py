# DEPRECATED
# DEPRECATED
# DEPRECATED

from PySide.QtCore import Qt,Slot
from PySide.QtGui import QHBoxLayout,QVBoxLayout, QDialogButtonBox,QDialog,QLabel

if __name__ == "__main__":
    import sys
    from PySide.QtGui import QApplication

    from koi.base_logging import mainlog,init_logging
    from koi.Configurator import init_i18n,load_configuration

    init_logging()
    init_i18n()
    load_configuration()

from koi.gui.dialog_utils import makeErrorBox,TitleWidget
from koi.gui.completer import AutoCompleteComboBox
from koi.CustomerPlateWidget import CustomerPlateWidget
from koi.datalayer.database_session import session

class CreateNewOrderDialog(QDialog):
    def __init__(self,parent):
        global dao
        super(CreateNewOrderDialog,self).__init__(parent)

        self.current_customer = None

        title = _("Create new order")
        self.setWindowTitle(title)
        top_layout = QVBoxLayout()
        self.title_widget = TitleWidget(title,self)
        top_layout.addWidget(self.title_widget)

        self.customer_plate_widget = CustomerPlateWidget(self)
        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.StandardButton.Cancel)
        self.buttons.addButton( QDialogButtonBox.Ok)

        hlayout = QHBoxLayout()

        self.customer_select = AutoCompleteComboBox(None, self, None)
        self.customer_select.section_width = None # [300]
        view = []
        keys = []
        ref = []
        customers = dao.customer_dao.all()
        for c in customers:
            view.append([c.fullname])
            keys.append(c.fullname)
            ref.append(c)
        session().close() # FIXME bad data layer / presentation layer separation here

        self.customer_select.make_model( view, keys, ref )

        self.customer_plate_widget.set_customer(customers[0])

        hlayout.addWidget(QLabel(_("Customer")), 0, Qt.AlignTop)
        hlayout.addWidget(self.customer_select, 0, Qt.AlignTop)
        hlayout.addWidget(self.customer_plate_widget, 1000, Qt.AlignTop)
        hlayout.addStretch()
        top_layout.addLayout(hlayout)

        # hlayout = QHBoxLayout()
        # self.order_select = AutoCompleteComboBox()
        # self.order_select.setEnabled(False)
        # self.order_select.section_width = [100,300]
        # hlayout.addWidget(QLabel(_("Clone order")))
        # self.enable_clone = QCheckBox()
        # hlayout.addWidget(self.enable_clone)
        # hlayout.addWidget(self.order_select)
        # hlayout.addStretch()
        # top_layout.addLayout(hlayout)

        top_layout.addStretch()
        top_layout.addWidget(self.buttons)
        self.setLayout(top_layout)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        # self.customer_select.activated.connect(self.customer_selected)
        self.customer_select.list_view.itemSelected.connect(self.customer_selected)


    @Slot(int)
    def customer_selected(self,ndx):
        # mainlog.debug( "EditOrderParts (CreateNewOrderDialog): customer_selected SLOT {}".format(ndx))
        # self.current_customer = self.customer_select.itemData( ndx, Qt.UserRole)
        self.customer_plate_widget.set_customer(ndx.data(Qt.UserRole))



    @Slot()
    def accept(self):
        global dao

        # FIXME I gusess it's the one below, but I must make sure
        mainlog.debug("Accept() : Current item {}".format( self.customer_select.currentIndex()))

        # if not (self.customer_select.currentIndex() == 0 and self.customer_select.list_view.currentIndex().row() == -1):

        if self.customer_select.currentIndex() >= 0:
            customer = self.customer_select.itemData( self.customer_select.currentIndex(), Qt.UserRole)
        else:
            customer = None

        if customer is None:
            msgBox = makeErrorBox(_("Please choose a customer for the new order"))
            msgBox.exec_()
            super(CreateNewOrderDialog,self).accept()
            return False

        self.customer_select.list_view.itemSelected.disconnect()
        self.customer_select.list_view.setVisible(False)
        self.customer_select = None

        self.current_customer = customer
        # self.customer_select.hide() # FIXME Very hackish. If I don't do this then the QApplication loses focus when this dialog is closed...
        #self.setFocus()
        return super(CreateNewOrderDialog,self).accept()

    @Slot()
    def reject(self):
        return super(CreateNewOrderDialog,self).reject()


if __name__ == "__main__":

    # 000100847802

    app = QApplication(sys.argv)
    dialog = CreateNewOrderDialog(None)
    dialog.exec_()
