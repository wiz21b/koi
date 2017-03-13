
from datetime import timedelta
from collections import OrderedDict


if __name__ == "__main__":
    from PySide.QtGui import QApplication,QMainWindow

    from koi.base_logging import init_logging
    from koi.Configurator import init_i18n,load_configuration

    init_logging()
    init_i18n()
    load_configuration()



from koi.dao import dao
from koi.db_mapping import OrderStatusType

from PySide.QtGui import QWidget,QStandardItemModel,QVBoxLayout,QHBoxLayout,QTableView, QBrush,QColor,QHeaderView,QStandardItem,QAbstractItemView, \
    QItemSelectionModel
from PySide.QtCore import Qt,Slot,Signal,QModelIndex
from koi.translators import *
from koi.gui.dialog_utils import TitleWidget, SubFrame, NavBar


class QuickOrderViewWidget(SubFrame):
    def __init__(self,parent):
        super(QuickOrderViewWidget,self).__init__("Quick view",None,parent)

        self._table_model = QStandardItemModel(1, 2, None)
        self.table_view = QTableView(self)
        self.table_view.setModel(self._table_model)
        self.layout().addWidget(self.table_view)

        self._table_model.setHorizontalHeaderLabels(['Part Nr.','Description'])

        self.table_view.verticalHeader().hide()
        headers_view = self.table_view.horizontalHeader()
        headers_view.setResizeMode(0,QHeaderView.ResizeToContents)
        headers_view.setResizeMode(1,QHeaderView.Stretch)

    def selected_order(self,cur,prev):
        if cur.isValid():
            order_id = cur.model().index(cur.row(),0).data(Qt.UserRole)

            self._table_model.removeRows(0, self._table_model.rowCount())
            row = 0
            for label,description in dao.order_dao.load_quick_view(order_id):
                self._table_model.appendRow([QStandardItem(label),QStandardItem(description)])



class LeftRightTableView(QTableView):
    def __init__(self,parent):
        super(LeftRightTableView,self).__init__(parent)

    out_left = Signal()
    out_right = Signal()
    focus_in = Signal(QModelIndex,QModelIndex)

    def keyPressEvent(self,event):

        if event.key() == Qt.Key_Left:
            self.out_left.emit()
        elif event.key() == Qt.Key_Right:
            self.out_right.emit()
        else:
            super(LeftRightTableView,self).keyPressEvent(event)

    def focusInEvent(self,event):
        ndx = self.selectionModel().currentIndex()
        # self.focus_in.emit(ndx,None)


class WeekViewWidget(SubFrame):
    def __init__(self,parent):
        super(WeekViewWidget,self).__init__("Week",None,parent)

        self._table_model = QStandardItemModel(1, 2, None)
        self._table_model.setHorizontalHeaderLabels([_("# Ord."),_("Customer")])

        self.table_view = LeftRightTableView(self)
        self.table_view.setModel(self._table_model)
        self.table_view.verticalHeader().hide()
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.table_view.horizontalHeader().setResizeMode(0,QHeaderView.ResizeToContents)
        self.table_view.horizontalHeader().setStretchLastSection(True)

        self.preorder_brush = QBrush(QColor(255,255,128))
        self.completed_order_brush = QBrush(QColor(128,255,128))

        self.layout().addWidget(self.table_view)




    def _set_last_row(self,data,role):
        for i in range(self._table_model.columnCount()):
            self._table_model.setData(self._table_model.index(self._table_model.rowCount()-1,i),data,role)



    def set_data(self,data,base_date):
        self.set_title(date_to_dm(base_date))
        self._table_model.removeRows(0, self._table_model.rowCount())

        current_ndx = 0
        for d in data:
            order,customer_name = d

            number = order.preorder_label
            if order.accounting_label:
                number = order.accounting_label

            self._table_model.appendRow([QStandardItem(str(number)),QStandardItem(customer_name)])
            self._table_model.setData(self._table_model.index(current_ndx,0),order.order_id,Qt.UserRole)

            if order.state == OrderStatusType.order_completed:
                self._set_last_row(self.completed_order_brush,Qt.BackgroundRole)
            elif order.state == OrderStatusType.preorder_definition:
                self._set_last_row(self.preorder_brush,Qt.BackgroundRole)


            current_ndx += 1
        # Not the slightest idea why this works
        # and not resizeColumnsToContents
        for i in range(self._table_model.columnCount()):
            self.table_view.resizeColumnToContents(i)


class WeekOverviewWidget(QWidget):
    def __init__(self,parent,find_order_slot):
        super(WeekOverviewWidget,self).__init__(parent)

        self.nb_weeks = 3

        td = date.today()
        self.base_date = td - timedelta(days=td.weekday()) # Align on monday


        self.quick_order_view = QuickOrderViewWidget(self)

        self.weekview_layout = QHBoxLayout(None)
        self.weeks = []
        for i in range(self.nb_weeks):
            w = WeekViewWidget(self)
            self.weeks.append(w)
            self.weekview_layout.addWidget(w)

            w.table_view.focus_in.connect(self.quick_order_view.selected_order)
            w.table_view.selectionModel().currentChanged.connect(self.quick_order_view.selected_order)
            w.table_view.out_left.connect(self.week_before)
            w.table_view.out_right.connect(self.week_after)

        self.weekview_layout.addWidget(self.quick_order_view)

        navbar = NavBar(self, [ (_("Week before"), self.week_before),
                                (_("Week after"), self.week_after),
                                (_("Find"), find_order_slot)])
        #                        (_("Today"),self.week _today),

        navbar.buttons[2].setObjectName("specialMenuButton")

        self.vlayout = QVBoxLayout(None)
        self.vlayout.addWidget(TitleWidget(_("Deadlines Overview"),self,navbar))
        self.vlayout.addLayout(self.weekview_layout)
        self.vlayout.setStretch(0,0)
        self.vlayout.setStretch(1,200)

        self.setLayout(self.vlayout)
        self.focus()

    def set_base_date(self,d):
        self.base_date = d - timedelta(days=d.weekday())
        self.refresh_action()
        self.focus()

    @Slot()
    def week_after(self):
        self.base_date = self.base_date + timedelta(days=7)
        self.refresh_action()
        self.focus()

    @Slot()
    def week_before(self):
        self.base_date = self.base_date - timedelta(days=7)
        self.refresh_action()
        self.focus()

    @Slot()
    def refresh_action(self):
        global dao

        ndx_to_widget = OrderedDict()

        # First we build some "week buckets".
        # Each bucket will receive the order parts of the
        # corresponding week

        d = self.base_date
        for i in range(self.nb_weeks):

            # Pay attention here,
            # for date 2012-12-24, we have ndx 201252 (looks nice)
            # but for 2012-12-31, ndx is 201301 (different years !)
            # Thus using an ordered dict is super important since
            # the indices are not ordered like we would...

            iso = d.isocalendar()
            ndx = iso[0]*100 + iso[1]
            ndx_to_widget[ndx] = []

            # mainlog.debug("WeekOverview {} {}".format(d,ndx))

            d = d + timedelta(days=7)
        end_date = d - timedelta(days=1)

        # Now we distribute the order parts between
        # the buckets

        for result in dao.order_dao.load_week_overview(self.base_date,end_date):
            part,order,customer_name = result

            deadline = part.deadline.isocalendar()
            ndx = deadline[0] * 100 + deadline[1] # Year * 100 + Week
            if ndx in ndx_to_widget:
                ndx_to_widget[ndx].append((order,part,customer_name))

        # Now the buckets are filled in, we can display
        # their content

        d = self.base_date
        i = 0
        for k,v in ndx_to_widget.items():
            # One week at a time
            orders = OrderedDict()
            for e in v:
                order,part,customer_name = e
                if order not in orders:
                    orders[order] = (order, customer_name)

            self.weeks[i].set_data(orders.values(),d)
            i = i + 1
            d = d + timedelta(days=7)


    def focus(self):
        self.weeks[1].table_view.setFocus(Qt.OtherFocusReason)
        self.weeks[1].table_view.selectionModel().reset()
        self.weeks[1].table_view.selectionModel().setCurrentIndex( self.weeks[1]._table_model.index(0,0),QItemSelectionModel.ClearAndSelect)

if __name__ == "__main__":
    employee = dao.employee_dao.any()
    app = QApplication(sys.argv)

    window = QMainWindow()
    window.setMinimumSize(1024,768)
    presence = WeekOverviewWidget(window,None)
    presence.set_base_date( date(2012,12,1))
    window.setCentralWidget(presence)
    window.show()
    presence.refresh_action()

    app.exec_()
