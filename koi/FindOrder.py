from PySide.QtCore import Qt,Slot,QModelIndex
from PySide.QtGui import QHBoxLayout,QVBoxLayout,QLineEdit,QLabel, QDialogButtonBox,QDialog,QHeaderView,QAbstractItemView,QTableView,QStandardItemModel,QStandardItem

from koi.gui.dialog_utils import TitleWidget, showWarningBox,make_header_model
from koi.gui.dialog_utils import showErrorBox
from koi.Configurator import mainlog
from koi.dao import dao
from koi.datalayer.data_exception import DataException


class FindOrderDialog(QDialog):
    def __init__(self,parent):
        global dao
        super(FindOrderDialog,self).__init__(parent)

        title = _("Find order")
        self.setWindowTitle(title)
        top_layout = QVBoxLayout()
        self.title_widget = TitleWidget(title,self)
        top_layout.addWidget(self.title_widget)

        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel(_("Search")))
        self.search_criteria = QLineEdit()
        self.search_criteria.setObjectName("search_criteria")
        hlayout.addWidget(self.search_criteria)
        top_layout.addLayout(hlayout)



        self.search_results_view = QTableView()

        self.headers_view = QHeaderView(Qt.Orientation.Horizontal)
        self.header_model = make_header_model([_("Preorder Nr"),_("Order Nr"),_("Customer Nr"),_("Customer"),_("Order Part")])
        self.headers_view.setModel(self.header_model) # qt's doc : The view does *not* take ownership (bt there's something with the selecion mode

        self.search_results_model = QStandardItemModel()
        self.search_results_view.setModel(self.search_results_model)

        self.search_results_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.search_results_view.setHorizontalHeader(self.headers_view)
        self.search_results_view.verticalHeader().hide()
        # self.search_results_view.horizontalHeader().setResizeMode(QHeaderView.ResizeToContents)
        self.search_results_view.horizontalHeader().setResizeMode(3, QHeaderView.Stretch)
        self.search_results_view.horizontalHeader().setResizeMode(4, QHeaderView.Stretch)

        self.search_results_view.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.StandardButton.Cancel)
        self.buttons.addButton( QDialogButtonBox.Ok)
        self.buttons.button(QDialogButtonBox.Ok).setObjectName("go_search")

        top_layout.addWidget(self.search_results_view)
        top_layout.setStretch(2,1000)
        top_layout.addWidget(self.buttons)
        self.setLayout(top_layout)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.search_results_view.activated.connect(self.row_activated)
        self.search_criteria.returnPressed.connect(self.search_criteria_submitted)

        self.setMinimumSize(800,640)

    def find_by_text(self,text):
        text = text.strip()

        try:
            too_many_results, res = dao.order_part_dao.find_ids_by_text(text.strip())

            if too_many_results:
                showWarningBox(_("Too many results"),_("The query you've given brought back too many results. Only a part of them is displayed. Consider refining your query"),object_name="too_many_results")

            return dao.order_part_dao.find_by_ids(res)

        except DataException as de:

            if de.code == DataException.CRITERIA_IS_EMPTY:
                showErrorBox(_("Error in the filter !"),
                             _("The filter can't be empty"),object_name="filter_is_empty")
            elif de.code == DataException.CRITERIA_IS_TOO_SHORT:
                showErrorBox(_("Error in the filter !"),
                             _("The filter is too short"),object_name="filter_is_too_short")
            elif de.code == DataException.CRITERIA_IS_TOO_LONG:
                showErrorBox(_("Error in the filter !"),
                             _("The filter is too long"),object_name="filter_is_too_long")

            return []
        


        # order_part_match = []
        # matches = []
        # super_matches = []

        # import re
        # re_order_part_identifier = re.compile("^([0-9]+)([A-Z]+)$")
        # re_label_identifier = re.compile("^[0-9]+$")

        # if re_order_part_identifier.match(text.upper()):
        #     # Look for an exact (and unique) match on the order part full identifier
        #     p = dao.order_part_dao.find_by_full_id(text.upper())
        #     if p:
        #         # Mimick SQLAlchemy's KeyTuples
        #         # FIXME It seems that I use something that's internal to SQLA
        #         # Search SQLA's doc for KeyedTuple to find about collections.namedtuple()

        #         from sqlalchemy.util._collections import KeyedTuple

        #         kt = KeyedTuple([p.order_id, p.order.preorder_label, p.order.accounting_label, p.order.customer_order_name, p.order.customer.fullname, p.order.creation_date, p.description, p.order_part_id, p.label],
        #                         labels=['order_id','preorder_label','accounting_label','customer_order_name','fullname','creation_date','description','order_part_id','label'])

        #         order_part_match = [ kt ]

        # if re_label_identifier.match(text):
        #     for r in dao.order_dao.find_by_labels(int(text)):
        #         super_matches.append(r)

        # for r in dao.order_dao.find_by_customer_name(text):
        #     # mainlog.debug('customer name match on {}'.format(text))
        #     matches.append(r)

        # for r in dao.order_dao.find_by_customer_order_name(text):
        #     # mainlog.debug('customer name match on {}'.format(text))
        #     matches.append(r)

        # for r in dao.order_part_dao.find_by_description(text):
        #     matches.append(r)

        # # Finally we order the matches to bring the most relevant
        # # first. The "most relevant" is really a business order.

        # return order_part_match + super_matches + \
        #     sorted(matches, lambda a,b: - cmp(a.order_id,b.order_id))


    def _search_results_to_array(self,search_results):
        array = []
        
        for res in search_results:
            # mainlog.debug("_search_results_to_array {}".format(res.creation_date))

            i = QStandardItem(res.preorder_part_label)
            row = [i,
                   QStandardItem(res.accounting_part_label),
                   QStandardItem(res.customer_order_name),
                   QStandardItem(res.fullname)]

            if 'order_part_id' in res.__dict__:
                # It's an order part

                i.setData( res.order_part_id, Qt.UserRole)
                i.setData( 'order_part', Qt.UserRole+1)
                row.append( QStandardItem(res.description))
            else:
                # It's an order

                i.setData( res.order_id, Qt.UserRole)
                i.setData( 'order', Qt.UserRole+1)
                row.append( QStandardItem())

            array.append(row)

        return array


    def load_search_results(self,text=None):
        global dao

        if text is None:
            text = self.search_criteria.text()

        db_results = self.find_by_text(text)
        array = self._search_results_to_array(db_results)

        self.search_results_model.removeRows(0,self.search_results_model.rowCount())
        for row in array:
            self.search_results_model.appendRow(row)
        mainlog.debug("Loaded model : {}".format(self.search_results_model.rowCount()))
        self.search_results_view.resizeColumnsToContents()

        if self.search_results_model.rowCount() > 0:
            self.search_results_view.setCurrentIndex(self.search_results_model.index(0,0))
            self.search_results_view.setFocus(Qt.OtherFocusReason)

        if self.search_results_model.rowCount() == 1:
            self.accept()


    def selected_item(self):
        mainlog.debug("FindOrder.selected_item")
        ndx = self.search_results_view.currentIndex()
        if ndx.isValid():
            ndx = self.search_results_view.model().index( ndx.row(), 0)

            item = ndx.data(Qt.UserRole)
            item_type = ndx.data(Qt.UserRole+1)

            if item_type == 'order':
                mainlog.debug("FindOrder.selected_item order_id={}".format(item))
                return dao.order_dao.find_by_id(item)
            elif item_type == 'order_part':
                mainlog.debug("FindOrder.selected_item order_part_id={}".format(item))
                return dao.order_part_dao.find_by_id(item)
            else:
                mainlog.error("Unsupported item type {}".format(item_type))
        else:
            mainlog.error("Invalid index")
            return None

    @Slot()
    def accept(self):
        # mainlog.debug("accept")
        # self.load_search_results()
        # mainlog.debug("accept - done")
        return super(FindOrderDialog,self).accept()

    @Slot()
    def reject(self):
        return super(FindOrderDialog,self).reject()

    @Slot()
    def search_criteria_submitted(self):
        mainlog.debug("search_criteria_submitted")
        self.load_search_results()

    @Slot(QModelIndex)
    def row_activated(self,ndx):
        mainlog.debug("row_activated")
        self.accept()

    def keyPressEvent(self,event):

        # The goal here is to make sure the accept signal is called only
        # if the user clicks on the "OK" button /with the mouse/ and,
        # not with the keyboard

        if event.key() in (Qt.Key_Enter, Qt.Key_Return):
            return
        else:
            super(FindOrderDialog,self).keyPressEvent(event)
