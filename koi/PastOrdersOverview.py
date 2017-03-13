# 3728

if __name__ == "__main__":
    from PySide.QtGui import QApplication,QMainWindow

    from koi.base_logging import mainlog,init_logging
    from koi.Configurator import init_i18n,load_configuration,configuration

    init_logging()
    init_i18n()
    load_configuration()

    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session
    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)

from PySide.QtCore import Qt,Slot,Signal,QModelIndex
from PySide.QtGui import QWidget,QStandardItemModel,QVBoxLayout, QBrush,QColor,QHeaderView, QAbstractItemView, QLabel, \
    QSplitter,QItemSelectionModel, QMenu,QCursor,QAction

from koi.Configurator import mainlog
from koi.OperationsView import OperationsOverviewWidget
from koi.configuration.business_functions import *
from koi.dao import dao
from koi.datalayer.letter_position import compare_labels
from koi.gui.dialog_utils import SubFrame
from koi.qtableviewfixed import QTableView
from koi.translators import *


def month_before(d):
    if d.month > 1:
        if isinstance(d,date):
            return date(d.year,d.month-1,d.day)
        elif isinstance(d,DateTime):
            return datetime(d.year,d.month-1,d.day,d.hour,d.minute,d.second,d.microsecond,d.tzinfo)
        else:
            raise Exception("I work on ly one data and datetime")
    else:
        if isinstance(d,date):
            return date(d.year-1,12,d.day)
        elif isinstance(d,DateTime):
            return datetime(d.year-1,12,d.day,d.hour,d.minute,d.second,d.microsecond,d.tzinfo)
        else:
            raise Exception("I work on ly one data and datetime")

def bound(n,mini,maxi):
    if n < mini:
        return mini
    elif n > maxi:
        return maxi
    else:
        return n



class PastOrdersOverviewWidget(QWidget):

    htext = [_("# Order"),_("# Preorder"),_("Customer"),_("Description"),_("Deadline"),_("Hours"),_("Qty"),_("Sell price")] #,_("Notes") ,_("Material"),_("Valuation")

    def set_on_order_part(self,order_part_id):
        mainlog.debug("set_on_order_part {}".format(order_part_id))
        if self.order_part_to_row.has_key(order_part_id):
            row = self.order_part_to_row[order_part_id]
            self.table_view.setCurrentIndex(self._table_model.index(row,0))
            # self.table_view.selectRow(row)
            self.table_view.scrollTo( self._table_model.index(row,0), QAbstractItemView.PositionAtCenter )
            mainlog.debug("set_on_order_part row={}".format(row))



    def _set_data(self,model,row,col,txt,role = Qt.DisplayRole):
        model.setData(model.index(row,col),txt,role)


    def real_deal(self,line):
        order_id = line.order_id
        return str(line.flags)



    # def _get_sort_criteria(self,section_sorted):
    #     sort_criteria = None

    #     # True if the parts of the order stay grouped
    #     # together in the table
    #     order_stay_together = True

    #     if section_sorted == 1: # Customer
    #         sort_criteria = lambda a,b: cmp(a.fullname, b.fullname) or \
    #                         cmp(a.order_id,b.order_id) or cmp(a.position,b.position)
    #     elif section_sorted == 3: # Deadline
    #         sort_criteria = lambda a,b: cmp(a.deadline or date(2100,1,1),b.deadline or date(2100,1,1))
    #     elif section_sorted == 6: # Total price
    #         mainlog.debug("sorting on total price")
    #         sort_criteria = lambda a,b: cmp(b.sell_price * b.qty, a.sell_price * a.qty)
    #     elif section_sorted == 0: # order/part
    #         sort_criteria = lambda a,b: cmp(a.order_id,b.order_id) or cmp(a.position,b.position)
    #     else:
    #         sort_criteria = None

    #     if sort_criteria is not None:
    #         self.current_sort_criteria = sort_criteria
    #     else:
    #         sort_criteria = self.current_sort_criteria

    #     order_stay_together = sort_criteria not in (7,6,3)

    #     return sort_criteria, order_stay_together



    SECTION_PREORDER_LABEL = 1
    SECTION_ACCOUNTING_LABEL = 0
    SECTION_CUSTOMER = 2
    SECTION_DESCRIPTION = 3
    SECTION_DEADLINE = 4
    SECTION_TIME = 5
    SECTION_QUANTITY = 6
    SECTION_PRICE = 7
    SECTION_GOAL = 8


    def _get_sort_criteria(self,section_sorted):
        sort_criteria = None

        # True if the parts of the order stay grouped
        # together in the table
        order_stay_together = True

        if section_sorted == self.SECTION_CUSTOMER: # Customer
            sort_criteria = lambda a,b: cmp(a.fullname, b.fullname) or \
                            cmp(a.order_id,b.order_id) or cmp(a.position,b.position)
        elif section_sorted == self.SECTION_DEADLINE: # Deadline
            sort_criteria = lambda a,b: cmp(a.deadline or date(2100,1,1),b.deadline or date(2100,1,1))
        elif section_sorted == self.SECTION_PRICE: # Total price
            mainlog.debug("sorting on total price")
            sort_criteria = lambda a,b: cmp(b.sell_price * b.qty, a.sell_price * a.qty)
        elif section_sorted == self.SECTION_GOAL: # Goal
            sort_criteria = lambda a,b: cmp(self.real_deal(b),self.real_deal(a)) or \
                            cmp(a.order_id,b.order_id) or cmp(a.position,b.position)
        elif section_sorted == self.SECTION_PREORDER_LABEL: # order/part
            sort_criteria = lambda a,b: compare_labels(a.preorder_part_label,b.preorder_part_label)
        elif section_sorted == self.SECTION_ACCOUNTING_LABEL: # order/part
            sort_criteria = lambda a,b: compare_labels(a.accounting_part_label,b.accounting_part_label)
        else:
            sort_criteria = None

        if sort_criteria is not None:
            self.current_sort_criteria = sort_criteria
        else:
            sort_criteria = self.current_sort_criteria

        order_stay_together = sort_criteria not in (self.SECTION_GOAL,self.SECTION_PRICE,self.SECTION_DEADLINE)

        return sort_criteria, order_stay_together


    def fill_model(self, parts_data):

        self.order_part_to_row = dict()

        headers = self.table_view.horizontalHeader()
        model = self.table_view.model()

        section_sorted = headers.sortIndicatorSection()
        sort_criteria, order_stay_together = self._get_sort_criteria(section_sorted)

        # Don't use model.clear() because it also clear the headers (and
        # their info such as resize policies)
        model.removeRows(0, model.rowCount())
        # model.setHorizontalHeaderLabels(self.htext) # Will set column count
        model.setRowCount(len(parts_data))

        if sort_criteria:
            parts_data = sorted(parts_data,sort_criteria)

        row = 0
        old_order_id = old_customer_name = None

        for part in parts_data:

            self.order_part_to_row[part.order_part_id] = row

            part_total_estimated_time = part.estimated_time_per_unit * part.qty
            part_estimated_remaining_time = part_total_estimated_time - part.total_hours
            encours = encours_on_params(part.tex2, part.qty,
                                        part.total_hours,
                                        part_total_estimated_time,
                                        part.sell_price,
                                        part.material_value)

            self._set_data(model,row,self.SECTION_PREORDER_LABEL,part.preorder_part_label)
            self._set_data(model,row,0,[part.order_part_id,part.order_id],Qt.UserRole)

            self._set_data(model,row,self.SECTION_ACCOUNTING_LABEL,part.accounting_part_label)

            # if part.order_part_id not in self.touched_order_parts:
            #     self._set_data(model,row,self.SECTION_GOAL,part.flags)
            # else:
            #     self._set_data(model,row,self.SECTION_GOAL,self.touched_order_parts[part.order_part_id])

            if order_stay_together and part.order_id != old_order_id:
                self._set_data(model,row,self.SECTION_CUSTOMER,part.fullname)
                old_order_id = part.order_id
                for i in range(0,len(self.htext)):
                    self._set_data(model,row,i, self.light_blue, Qt.BackgroundRole)
            elif part.order_id != old_order_id:
                self._set_data(model,row,self.SECTION_CUSTOMER,part.fullname)


            self._set_data(model,row,self.SECTION_DESCRIPTION,part.description)
            self._set_data(model,row,self.SECTION_DEADLINE,date_to_dmy(part.deadline))
            self._set_data(model,row,self.SECTION_TIME,"{} / {}".format(duration_to_s(part.total_hours), duration_to_s(part_total_estimated_time)))
            self._set_data(model,row,self.SECTION_QUANTITY,"{} / {}".format(part.tex2, part.qty))
            self._set_data(model,row,self.SECTION_PRICE,amount_to_s(part.sell_price * part.qty))

            # self._set_data(model,row,self.notes_column,part.notes)

            # self._set_data(model,row,7,amount_to_s(part_material_value))
            # self._set_data(model,row,8,amount_to_s(encours))

            if part.tex2 == part.qty and part.qty > 0:
                self._set_data(model,row,self.SECTION_TIME, self.cool_brush, Qt.BackgroundRole)
                self._set_data(model,row,self.SECTION_QUANTITY, self.cool_brush, Qt.BackgroundRole)

            elif part.deadline and part.deadline < date.today():
                self._set_data(model,row,self.SECTION_DEADLINE, self.warning_brushs[0], Qt.BackgroundRole)

            ratio_hours = 0
            if part_total_estimated_time > 0:
                ratio_hours = part.total_hours / part_total_estimated_time # Hours are float => no cast needed

                if ratio_hours > 1.0:
                    self._set_data(model,row,self.SECTION_TIME,self.warning_brushs[ min(int((ratio_hours-1)*4),len(self.warning_brushs)-1) ],Qt.BackgroundRole)
                elif part.qty > 0 and part.tex2 > 0:
                    ratio_qty = float(part.tex2) / float(part.qty)

                    ratio_productivity = ratio_hours / ratio_qty

                    if ratio_productivity > 1.0:
                        c = self.warning_brushs[ min(int((ratio_productivity-1)*4), len(self.warning_brushs)-1) ]
                        self._set_data(model,row,self.SECTION_TIME,c,Qt.BackgroundRole)
                        self._set_data(model,row,self.SECTION_QUANTITY,c,Qt.BackgroundRole)

            elif part_total_estimated_time == 0 and part.total_hours > 0:
                # Hours have been reported on a task that was not etimated
                self._set_data(model,row,self.SECTION_TIME,self.warning_brushs[ 2 ],Qt.BackgroundRole)

            elif part_total_estimated_time == 0 and part.tex2 > 0:
                self._set_data(model,row,self.SECTION_TIME,self.warning_brushs[ 1 ],Qt.BackgroundRole)
                self._set_data(model,row,self.SECTION_QUANTITY,self.warning_brushs[ 1 ],Qt.BackgroundRole)


            for i in range(self.SECTION_DEADLINE,9+1):
                self._set_data(model,row,i,128+2,Qt.TextAlignmentRole)

            row += 1

        #self.table_view.selectionModel().deleteLater()
        #self.table_view.setModel(model)
        #self._table_model = model
        #self.table_view.selectionModel().currentChanged.connect(self.order_part_selected)

        # headers.setResizeMode(QHeaderView.ResizeToContents) # Description column wide enough

        # Changing the model removes the sort order (which makes sense because
        # changing the model may alter the order of rows)
        headers.setSortIndicator(section_sorted,Qt.AscendingOrder)

        if len(parts_data) == 0:
            # Must do this because when the model is empty
            # the slection is not updated, so no signal
            # is sent
            self.operations_view.fill_order_part(None)
        else:
            self.table_view.selectionModel().reset()
            self.table_view.selectionModel().select( self.table_view.model().index(0,0), QItemSelectionModel.Select | QItemSelectionModel.Rows)










    @Slot(int)
    def section_clicked(self,logical_ndx):
        self.fill_model(self.parts_data)


    @Slot()
    def refresh_action(self,base_date = None, criteria = 8,warn_too_many_results=True):
        self.selection_criteria = criteria

        if base_date:
            self.base_date = base_date

        self.overview_frame.set_title(_("Orders for {}").format(date_to_my(self.base_date,full=True)))
        self.parts_data = dao.order_dao.load_order_parts_overview(self.base_date, criteria) # finished orders
        self.fill_model(self.parts_data)

        # self.rebuild_model()
        self.table_view.setFocus()
        ndx = self.table_view.model().index(0,0)
        self.table_view.setCurrentIndex( ndx)


    @Slot(QModelIndex,QModelIndex)
    def order_part_selected(self, ndx_cur, ndx_old):
        if ndx_cur.isValid():
            order_part_id,order_id = self._table_model.data(self._table_model.index(ndx_cur.row(),0),Qt.UserRole)

            # self.operations_view.set_order_part_id(order_part_id)

            order_part = dao.order_part_dao.find_by_id(order_part_id)
            self.operations_view.fill_order_part(order_part)
            session().commit()
        else:
            # self.operations_view.set_order_part_id(None)
            self.operations_view.fill_order_part(None)

    @Slot()
    def edit_order_slot(self):
        # Need this because there's a mismatch in the parameter
        # signature of the edit orders slot. See order_part_activated
        # below
        self.order_part_activated(self.table_view.currentIndex())


    order_part_activated_signal = Signal(int) # order_part_id

    @Slot(QModelIndex)
    def order_part_activated(self,ndx):
        if ndx.isValid():
            m = ndx.model()
            order_part_id,order_id = m.data(m.index(ndx.row(),0),Qt.UserRole)
            self.order_part_activated_signal.emit(order_part_id)



    def current_order_id(self):
        ndx = self.table_view.currentIndex()
        if ndx.isValid():
            order_part_id,order_id = self._table_model.data(self._table_model.index(ndx.row(),0),Qt.UserRole)
            return order_id
        else:
            return None


    def _init_overview(self):
        self._table_model = QStandardItemModel(0, len(self.htext), None)
        self._table_model.setHorizontalHeaderLabels(self.htext) # Will set column count

        # self.headers_view = QHeaderView(Qt.Orientation.Horizontal,self)
        #self.header_model = headers
        #self.headers_view.setModel(self._table_model) # qt's doc : The view does *not* take ownership

        self.table_view = QTableView(None)

        self.table_view.setModel(self._table_model)

        self.table_view.horizontalHeader().setClickable(True)
        self.table_view.horizontalHeader().setSortIndicatorShown(True)
        self.table_view.horizontalHeader().sectionClicked.connect(self.section_clicked)
        self.table_view.selectionModel().currentChanged.connect(self.order_part_selected)
        #self.table_view.doubleClicked.connect(self.order_part_activated)
        # self.headers_view.setResizeMode(0,QHeaderView.Interactive)


        self.table_view.horizontalHeader().resizeSection(self.SECTION_ACCOUNTING_LABEL,100)
        self.table_view.horizontalHeader().resizeSection(self.SECTION_PREORDER_LABEL,100)
        self.table_view.horizontalHeader().setResizeMode(self.SECTION_CUSTOMER,QHeaderView.ResizeToContents) # Description column wide enough
        self.table_view.verticalHeader().hide()
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)


        self.operations_view = OperationsOverviewWidget(self)

        splitter = QSplitter(Qt.Horizontal,self)

        # hlayout = QHBoxLayout()
        self.overview_frame = SubFrame(_("Orders"),self.table_view,splitter)
        splitter.addWidget(self.overview_frame)
        # hlayout.setStretchFactor(w,4)

        layout = QVBoxLayout()
        layout.addWidget(self.operations_view)
        w = SubFrame(_("Operations"),layout,splitter)
        splitter.addWidget(w)

        splitter.setStretchFactor(0,2)
        splitter.setStretchFactor(1,1)

        self.vlayout = QVBoxLayout(self)
        self.vlayout.setContentsMargins(0,0,0,0)
        self.vlayout.addWidget(splitter)
        self.vlayout.setStretchFactor(splitter,1000)
        self.setLayout(self.vlayout)

        self.table_view.activated.connect(self.order_part_activated)
        self.operations_view.view.selectionModel().currentChanged.connect(self.operation_selection_changed)
        self.table_view.customContextMenuRequested.connect(self.popup)

        self.table_view.setColumnHidden(self.SECTION_PRICE,not self.show_price_values)

    def _prepare_colors(self):
        def hsl_brush(h,s,l):
            c = QColor()
            c.setHsl(h,s,l)
            return QBrush(c)

        self.warning_brush = QBrush(QColor(255,255,128))
        self.warning_brushs = [hsl_brush(64,255,192),
                               hsl_brush(32,255,216),
                               hsl_brush(0,255,216),
                               hsl_brush(0,255,128)]

        self.background_brush = QBrush(QColor(200,200,255))
        self.cool_brush = QBrush(QColor(128,255,128))
        self.light_blue = QBrush(QColor(220,220,255))
        self.dark_blue = QBrush(QColor(220,220,255))


    def __init__(self,parent,find_order_action_slot,create_delivery_slip_action,show_price_values=True):
        super(PastOrdersOverviewWidget,self).__init__(parent)

        self.show_price_values = show_price_values

        self.current_sort_criteria = 0
        self._prepare_colors()
        self.current_month_label = QLabel("d")
        self.base_date = date.today()
        self.touched_row = set()

        self.edit_action = QAction(_('Edit order'),self)
        self.edit_action.triggered.connect( self.edit_order_slot)

        # self.order_part_edit_dialog = OrderPartsEditorDialog()
        self.parts_data = []

        self._init_overview()



    @Slot()
    def popup(self,popup):

        if not self.table_view.selectedIndexes():
            return

        orders_to_parts = dict()

        for ndx in self.table_view.selectedIndexes():
            if ndx.isValid():
                order_part_id, order_id = self._table_model.data(self._table_model.index(ndx.row(),0),Qt.UserRole)

                if order_id not in orders_to_parts:
                    orders_to_parts[order_id] = set()
                orders_to_parts[order_id].add(order_part_id)


        # Since there can be more than one part selected and that those parts might have different states,
        # we have to provide a menu that allows state
        # transitions that are valid for all order parts

        order_parts_ids = reduce(lambda x,y:x.union(y), orders_to_parts.values(), set())


        menu = QMenu()

        menu.addAction(self.edit_action)
        menu.addSeparator()

        authorized_states = dao.order_part_dao.next_states_for_parts(order_parts_ids)
        for nxt in authorized_states:
            a = menu.addAction(_("Part state to {}").format(nxt.description))
            a.setData(nxt)

        action = menu.exec_(QCursor.pos())

        if action and action.data():
            nxt = action.data()

            if nxt:
                for order_id, order_parts_ids in orders_to_parts.iteritems():
                    # FIXME might be a bug here...
                    dao.order_dao.change_order_parts_state(order_id,order_parts_ids,nxt)
                self.refresh_action(self.base_date, self.selection_criteria)

    # @Slot()
    # def popup(self, pos):

    #     order_id = self.current_order_id()
    #     if not order_id:
    #         return

    #     order = dao.order_dao.find_by_id_frozen(order_id)
    #     s = order.state

    #     # for i in self.table_view.selectionModel().selection().indexes():
    #     #    print i.row(), i.column()
    #     menu = QMenu()

    #     menu.addAction(self.edit_action)
    #     menu.addSeparator()

    #     for nxt in OrderStatusType.next_states(s):
    #         a = menu.addAction(nxt.description)
    #         a.setData(nxt)


    #     action = menu.exec_(QCursor.pos())
    #     if action and action.data():
    #         dao.order_dao.change_order_state(order_id,action.data())
    #         self.refresh_action()


    @Slot(QModelIndex,QModelIndex)
    def operation_selection_changed(self, current, previous):

        model = self.operations_view.controller_operation.model

        if current.isValid() and current.row() < len(model.objects):

            op = model.objects[current.row()]

            if op and op.operation_id:
                return



if __name__ == "__main__":
    from koi.junkyard.services import services
    employee = services.employees.any()
    app = QApplication(sys.argv)

    window = QMainWindow()
    window.setMinimumSize(1024,768)
    widget = PastOrdersOverviewWidget(window,None,None)
    widget.refresh_action()
    window.setCentralWidget(widget)
    window.show()
    # presence.refresh_action()

    app.exec_()
