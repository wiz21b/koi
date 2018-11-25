from PySide.QtCore import Slot,QModelIndex
from PySide.QtGui import QHBoxLayout,QVBoxLayout, QDialogButtonBox,QDialog

from koi.Configurator import mainlog,configuration


if __name__ == "__main__":
    import sys
    from PySide.QtGui import QApplication

    from koi.base_logging import init_logging

    init_logging()
    init_i18n()
    load_configuration()

    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session
    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)

from koi.gui.dialog_utils import makeErrorBox,TitleWidget
from koi.CustomerPlateWidget import SupplierContactDataWidget

from koi.datalayer.supplier_mapping import Supplier
from koi.datalayer.generic_access import generic_load_all_frozen

from koi.gui.ProxyModel import TextLinePrototype
from koi.gui.QuickPrototypedFilter import QuickPrototypedFilter



class ChooseSupplierDialog(QDialog):

    @Slot(QModelIndex)
    def _item_selected(self,ndx):
        self.accept()

    def __init__(self,parent):
        global dao
        super(ChooseSupplierDialog,self).__init__(parent)

        title = _("Choose supplier")
        self.setWindowTitle(title)
        top_layout = QVBoxLayout()
        self.title_widget = TitleWidget(title,self)
        top_layout.addWidget(self.title_widget)

        self.supplier_plate_widget = SupplierContactDataWidget(self)
        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.StandardButton.Cancel)
        self.buttons.addButton( QDialogButtonBox.Ok)

        hlayout = QHBoxLayout()

        # suppliers = dao.supplier_dao.all_frozen()
        suppliers = generic_load_all_frozen(Supplier, Supplier.fullname)


        table_prototype = [ TextLinePrototype('fullname',_('Name'),editable=False) ]
        self.filter_view = QuickPrototypedFilter(table_prototype,self)
        self.filter_view.selected_object_changed.connect(self.supplier_plate_widget.set_contact_data)
        self.filter_view.set_data(suppliers,lambda c:c.indexed_fullname)

        hlayout.addWidget(self.filter_view)
        hlayout.addWidget(self.supplier_plate_widget,1000)
        # hlayout.addStretch()
        top_layout.addLayout(hlayout)

        #top_layout.addStretch()
        top_layout.addWidget(self.buttons)
        self.setLayout(top_layout)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        self.filter_view.list_view.doubleClicked.connect(self._item_selected)
        # self.supplier_plate_widget.set_contact_data(suppliers[0])

    @Slot()
    def accept(self):
        self.supplier_id = None
        self.supplier = None

        if self.filter_view.last_selected_object:
            supplier_id = self.filter_view.last_selected_object.supplier_id
        else:
            supplier_id = None

        if supplier_id is None:
            msgBox = makeErrorBox(_("Please choose a supplier for the new order"))
            msgBox.exec_()
            super(ChooseSupplierDialog,self).reject()
            return False

        mainlog.debug("ChooseSupplierDialog.accept() : supplier_id = {}".format(supplier_id))

        self.supplier_id = supplier_id
        self.supplier = self.filter_view.last_selected_object
        return super(ChooseSupplierDialog,self).accept()

    @Slot()
    def reject(self):
        self.supplier_id = None
        return super(ChooseSupplierDialog,self).reject()


if __name__ == "__main__":

    # 000100847802

    app = QApplication(sys.argv)
    dialog = ChooseSupplierDialog(None)
    dialog.exec_()
