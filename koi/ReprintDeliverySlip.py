from PySide.QtCore import Slot,QModelIndex
from PySide.QtGui import QHBoxLayout,QVBoxLayout,QLineEdit,QLabel,QDialog,QDialogButtonBox, QStandardItem,QStandardItemModel,QAbstractItemView,QHeaderView

from koi.qtableviewfixed import QTableView

if __name__ == "__main__":
    import sys
    from PySide.QtGui import QApplication, QMainWindow
    from koi.base_logging import init_logging
    from koi.Configurator import init_i18n,load_configuration,configuration
    init_logging()
    init_i18n()
    load_configuration()

    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session
    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)


from koi.gui.dialog_utils import makeErrorBox, TitleWidget
from koi.Configurator import mainlog
from koi.reporting.delivery_slip_report import print_delivery_slip
from koi.translators import date_to_dmy
from koi.delivery_slips.DeliverySlipView import DeliverySlipViewWidget


class ReprintDeliverySlipDialog(QDialog):
    def __init__(self,parent,dao):
        super(ReprintDeliverySlipDialog,self).__init__(parent)
        self.dao = dao

        title = _("Print a delivery slip")
        self.setWindowTitle(title)
        top_layout = QVBoxLayout()
        self.title_widget = TitleWidget(title,None)

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.StandardButton.Cancel)
        self.buttons.addButton( QDialogButtonBox.Ok)

        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel(_("Slip number")))
        self.slip_number = QLineEdit()
        hlayout.addWidget(self.slip_number)
        hlayout.addStretch()

        self.search_results_view = QTableView()
        self.search_results_model = QStandardItemModel()
        self.search_results_model.setHorizontalHeaderLabels([_("Slip Nr"),_("Date"),_("Customer"),_("Order")])
            
        self.search_results_view.setModel(self.search_results_model)
        # self.search_results_view.setHorizontalHeader(self.headers_view)
        self.search_results_view.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.search_results_view.horizontalHeader().setResizeMode(1, QHeaderView.ResizeToContents)
        self.search_results_view.horizontalHeader().setResizeMode(2, QHeaderView.Stretch)
        self.search_results_view.verticalHeader().hide()

        self.slip_part_view = DeliverySlipViewWidget(self)

        hlayout_results = QHBoxLayout()
        hlayout_results.addWidget(self.search_results_view)
        hlayout_results.addWidget(self.slip_part_view)

        self.search_results_model.removeRows(0,self.search_results_model.rowCount())
        delivery_slips = self.dao.delivery_slip_part_dao.find_recent()
        for slip in delivery_slips:
            self.search_results_model.appendRow([QStandardItem(str(slip[0])),
                                                 QStandardItem(date_to_dmy(slip[1])),
                                                 QStandardItem(slip[2]),
                                                 QStandardItem(slip[3])])

        top_layout.addWidget(self.title_widget)
        top_layout.addLayout(hlayout)
        top_layout.addLayout(hlayout_results)
        top_layout.addWidget(self.buttons)
        top_layout.setStretch(2,100)
        self.setLayout(top_layout)

        self.search_results_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.search_results_view.setSelectionMode(QAbstractItemView.SingleSelection)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.search_results_view.activated.connect(self.row_activated)
        self.search_results_view.selectionModel().currentRowChanged .connect(self.row_selected)

    @Slot(QModelIndex,QModelIndex)
    def row_selected(self,cur_ndx,prev_ndx):
        slip_id = cur_ndx.model().index(cur_ndx.row(),0).data()
        self.slip_number.setText(str(slip_id))
        self.slip_part_view.set_delivery_slip_parts(dao.delivery_slip_part_dao.load_slip_parts_frozen(slip_id))

    @Slot(QModelIndex)
    def row_activated(self,ndx):
        slip_id = ndx.model().index(ndx.row(),0).data()
        self.slip_number.setText(str(slip_id))
        self.accept()


    @Slot()
    def accept(self):
        try:
            try:
                slip_id = int(self.slip_number.text())
            except ValueError as e:
                makeErrorBox(_("The delivery slip number {} is not valid").format(self.slip_number.text())).exec_()
                return

            if self.dao.delivery_slip_part_dao.id_exists(slip_id):
                print_delivery_slip(self.dao,slip_id)
            else:
                makeErrorBox(_("The delivery slip {} doesn't exist").format(slip_id)).exec_()
                return
        except Exception as e:
            mainlog.exception(e)
            msgBox = makeErrorBox(_("Something wrong happened while printing"))
            msgBox.exec_()

        return super(ReprintDeliverySlipDialog,self).accept()


    @Slot()
    def reject(self):
        return super(ReprintDeliverySlipDialog,self).reject()





if __name__ == "__main__":

    from koi.dao import dao

    app = QApplication(sys.argv)
    mw = QMainWindow()
    mw.setMinimumSize(1024,768)

    dialog = ReprintDeliverySlipDialog(mw,dao)
    dialog.exec_()

    # app.exec_()
