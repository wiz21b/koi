from functools import cmp_to_key

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

from PySide.QtGui import QWidget, QVBoxLayout,QHBoxLayout,QBrush,QColor,QHeaderView, QAbstractItemView, QLabel, QDialog, \
    QSplitter, QMenu,QCursor,QAction, QMessageBox,QLineEdit,QPalette,QApplication,QKeySequence,QItemSelectionModel,QItemSelection, QScrollArea, QSizePolicy
from PySide.QtCore import Qt, QModelIndex,QAbstractTableModel
from PySide.QtCore import Slot, Signal,QTimer,QPoint

from koi.datalayer.data_exception import DataException
from koi.dao import dao

from koi.configuration.business_functions import business_computations_service
from koi.date_utils import timestamp_to_date
from koi.translators import *
from koi.gui.dialog_utils import SubFrame, yesNoBox,showErrorBox,showWarningBox,priority_stars, priority_to_stars

from koi.qtableviewfixed import QTableView

from koi.OperationsView import OperationsOverviewWidget
#from OrderPartEdit import OrderPartsEditorDialog

from koi.gui.gui_tools import EuroLabel
from koi.datalayer.letter_position import compare_labels
from koi.datalayer.query_parser import check_parse

from koi.tools.chrono import *

from koi.gui.CopyPasteManager import copy_paste_manager
from koi.datalayer.quality import QualityEventType

from koi.quality.NonConformityDialog import NonConformityDialog
from koi.service_config import remote_documents_service

import copy


class DictOfDict(dict):
    def __init__(self, *args):
        dict.__init__(self, args)

    def rget(self, k1, k2, default_value=[]):
        """ Get the value for the key pair (k1, k2).
        """

        if not self.__contains__(k1):
            # print(k1)
            self[k1] = dict()

        if k2 not in self[k1]:
            # print(k2)
            self[k1][k2] = copy.copy(default_value)

        return self[k1][k2]


class QuickModel(QAbstractTableModel):

    def setHorizontalHeaderLabels(self,args):
        pass

    def headerData(self,section,orientation,role=Qt.DisplayRole):

        if orientation == Qt.Horizontal and section >= 0 and section < len(self.htext) and role == Qt.DisplayRole:
            #mainlog.debug("headerData {}/{} / {}".format(section, len(self.headers), role))
            return self.htext[section]
        else:
            return None

    SECTION_ACCOUNTING_LABEL = 0
    SECTION_PREORDER_LABEL = 1
    SECTION_CUSTOMER = 2
    SECTION_DESCRIPTION = 3
    SECTION_DEADLINE = 4
    SECTION_TIME = 5
    SECTION_QUANTITY = 6
    SECTION_PRICE = 7
    # SECTION_HUMAN_TIME = 8
    SECTION_PRIORITY = 8
    SECTION_GOAL = 9

    def parent(self):
        return QModelIndex()

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



    def __init__(self,parent):
        super(QuickModel,self).__init__(parent)
        self.htext = [_("# Order"),_("# Preorder"),_("Customer"),_("Description"),_("Deadline"),_("Ma. Hours"),_("Qty"),_("Sell price"),_("Priority")]
        #,_("Goal")] #,_("Notes") ,_("Material"),_("Valuation")

        self.headers = [None]
        self.table = []
        self.table_backgrounds = []
        self.table_user_roles = []
        self._prepare_colors()


    def parent(self):
        return QModelIndex()

    def index(self, row, column, parent = QModelIndex()):
        return self.createIndex(row, column)

    def rowCount(self,parent = None):
        return len(self.table)

    def columnCount(self,parent = None):
        if len(self.table) > 0:
            return len(self.htext)
        else:
            return 0

    def data(self, index, role):
        if index.row() < 0 or index.row() >= self.rowCount() or index.column() < 0 or index.column() >= self.columnCount():
            # print "TurboModel.data(). bad index {}".format(index.row())
            return None

        if self.table[index.row()] is None:
            self._buildRows(self.data_source,index.row())

        if role in (Qt.EditRole, Qt.DisplayRole):
            return self.table[index.row()][index.column()]

        elif role == Qt.BackgroundRole:
            z = self.table_backgrounds[index.row()]
            return z[index.column()]

        elif role == Qt.UserRole:
            return self.table_user_roles[index.row()][index.column()]

        elif role == Qt.TextAlignmentRole and index.column() in (self.SECTION_DEADLINE, self.SECTION_TIME, self.SECTION_QUANTITY, self.SECTION_PRICE):
            return Qt.AlignRight

        else:
            return None

    def flags(self, index):
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled


    def order_part_to_row(self, order_part_id):
        row_ndx = 0
        for part in self.data_source:
            if part.order_part_id == order_part_id:
                return row_ndx
            else:
                row_ndx += 1
        return None

    def _buildRows(self,array,row_ndx):
        part = array[row_ndx]

        row = [None]*15

        highlight_customer = (row_ndx == 0) or (row_ndx > 0 and array[row_ndx-1].order_id != part.order_id)


        part_total_estimated_time = part.estimated_time_per_unit * part.qty
        part_estimated_remaining_time = part_total_estimated_time - part.total_hours
        # encours = encours_on_params(part.tex2, part.qty,
        #                             part.total_hours,
        #                             part_total_estimated_time,
        #                             part.sell_price,
        #                             part.material_value)

        # --- View role --------------------------------

        row[self.SECTION_PREORDER_LABEL] = part.preorder_part_label or ""

        # self._set_data(model,row,0,[part.order_part_id,part.order_id],Qt.UserRole)

        row[self.SECTION_ACCOUNTING_LABEL] = part.accounting_part_label or ""

        if highlight_customer:
            row[self.SECTION_CUSTOMER] = part.fullname

        row[self.SECTION_DESCRIPTION] = part.description
        row[self.SECTION_DEADLINE] = date_to_dmy(part.deadline)
        row[self.SECTION_TIME] = "{} / {}".format(duration_to_s(part.total_hours), duration_to_s(part_total_estimated_time))
        row[self.SECTION_QUANTITY] = "{} / {}".format(part.tex2, part.qty)
        row[self.SECTION_PRICE] = amount_to_s(part.sell_price * part.qty)
        # row[self.SECTION_HUMAN_TIME] = duration_to_s(part.human_time)
        row[self.SECTION_PRIORITY] = priority_to_stars(part.priority)

        self.table[row_ndx] = row

        # --- User role ---------------------------

        row = [None] * len(self.htext)
        row[0] = [part.order_part_id, part.order_id]

        # for copy paste
        row[self.SECTION_CUSTOMER] = part.fullname
        row[self.SECTION_TIME] = (part.total_hours,part_total_estimated_time)
        row[self.SECTION_QUANTITY] = (part.tex2, part.qty)
        row[self.SECTION_PRICE] = part.sell_price * part.qty
        # row[self.SECTION_HUMAN_TIME] = part.human_time
        row[self.SECTION_PRIORITY] = part.priority

        self.table_user_roles[row_ndx] = row

        # Backgrounds

        row = [None]*len(self.htext)

        if highlight_customer:
            row = [self.light_blue] * 15

        if part.tex2 == part.qty and part.qty > 0:
            row[self.SECTION_TIME] = self.cool_brush
            row[self.SECTION_QUANTITY] = self.cool_brush

        elif part.deadline and part.deadline < date.today():
            row[self.SECTION_DEADLINE] = self.warning_brushs[0]

        ratio_hours = 0
        if part_total_estimated_time > 0:
            ratio_hours = part.total_hours / part_total_estimated_time # Hours are float => no cast needed

            if ratio_hours > 1.0:
                row[self.SECTION_TIME] = self.warning_brushs[ min(int((ratio_hours-1)*4),len(self.warning_brushs)-1) ]
            elif part.qty > 0 and part.tex2 > 0:
                ratio_qty = float(part.tex2) / float(part.qty)
                ratio_productivity = ratio_hours / ratio_qty

                if ratio_productivity > 1.0:
                    c = self.warning_brushs[ min(int((ratio_productivity-1)*4), len(self.warning_brushs)-1) ]
                    row[self.SECTION_TIME] = c
                    row[self.SECTION_QUANTITY] = c

        elif part_total_estimated_time == 0 and part.total_hours > 0:
            # Hours have been reported on a task that was not etimated
            row[self.SECTION_TIME] = self.warning_brushs[ 2 ]

        elif part_total_estimated_time == 0 and part.tex2 > 0:
            row[self.SECTION_TIME] = self.warning_brushs[ 1 ]
            row[self.SECTION_QUANTITY] = self.warning_brushs[ 1 ]

        self.table_backgrounds[row_ndx] = row


    def clear(self):
        if self.rowCount() == 0:
            return

        self.beginRemoveRows(QModelIndex(),0,max(0,self.rowCount()-1))
        self.beginRemoveColumns(QModelIndex(),0,max(0,self.columnCount()-1))
        self.table = []
        self.table_backgrounds = []
        self.table_user_roles = []
        self.endRemoveColumns()
        self.endRemoveRows()

    def buildModelFromArray(self,array):
        # Pay attention, this is tricky.
        # I have the impression that Qt's views are really picky about this
        # so, if you remove all the rows of a table, it doesn't mean
        # that you also removed all the columns (from the QTableView standpoint)
        # Therefore, to signal that we've cleared the model, we must
        # delete rows *and* columns.

        self.clear()

        # Be very carefull not to beginInsert if you actually
        # don't insert anything. This makes Qt crazy.

        if array:
            self.beginInsertRows(QModelIndex(),0,len(array)-1)
            self.beginInsertColumns(QModelIndex(),0,len(self.htext)-1)

            self.data_source = array

            self.table = [None] * len(array)
            self.table_backgrounds = [None] * len(array)
            self.table_user_roles = [None] * len(array)

            self.endInsertColumns()
            self.endInsertRows()












def bound(n,mini,maxi):
    if n < mini:
        return mini
    elif n > maxi:
        return maxi
    else:
        return n


class OrderPartNoteWidget(QLineEdit):

    #note_saved = Signal(int,unicode)

    def __init__(self,parent=None):
        super(OrderPartNoteWidget,self).__init__(parent)
        self.current_order_part_id = None
        self.editingFinished.connect(self.done_edit)

        self.kool = 10
        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self.timer_top)

    def set_order_part_id_note(self,order_part_id, notes):
        self.stop_timer()

        if order_part_id:
            self.current_order_part_id = order_part_id
            self.original_text = notes
            self.setText(notes)
            if notes:
                self.start_timer()

        else:
            self.original_text = None
            self.setText("")
            self.current_order_part_id = None

    def set_on_order_part(self,order_part):
        if order_part:
            self.set_order_part_id_note(order_part.order_part_id, order_part.notes)
        else:
            self.set_order_part_id_note(None, None)


    def done_edit(self):
        return



    def start_timer(self):
        self.kool = 10
        self.timer.start()
        self.timer_top()


    def stop_timer(self):
        self.timer.stop()
        palette = self.palette()
        palette.setColor(QPalette.Base, QColor(255,255,255))
        self.setPalette(palette)

    def timer_top(self):
        palette = self.palette()
        x = 255 - self.kool*20
        palette.setColor(QPalette.Base, QColor(x,255,x))
        self.setPalette(palette)

        if self.kool <= 0:
            self.stop_timer()
        else:
            self.kool = self.kool - 1



class CurrentOrdersOverviewWidget(QWidget):

    #htext = [_("# Order"),_("# Preorder"),_("Customer"),_("Description"),_("Deadline"),_("Hours"),_("Qty"),_("Sell price"),_("HTime"),_("Priority")] #,_("Goal")] #,_("Notes") ,_("Material"),_("Valuation")
    htext = [_("# Order"),_("# Preorder"),_("Customer"),_("Description"),_("Deadline"),_("Ma. Hours"),_("Qty"),_("Sell price"),_("Priority")] # Electro

    notes_column = -1 # len(htext) - 1

    data_changed_signal = Signal()
    order_parts_changed = Signal()

    def set_on_order_part(self,order_part_id):
        mainlog.debug("set_on_order_part {}".format(order_part_id))
        row = self._table_model.order_part_to_row(order_part_id)

        if row is not None:
            #row = self.order_part_to_row[order_part_id]
            # For some reason, the selectRow operation produces
            # its effect only if the table view has focus...
            self.table_view.setFocus(Qt.OtherFocusReason)

            # self.table_view.setCurrentIndex(self._table_model.index(row,0))
            # self.table_view.selectRow(row)


            self.table_view.selectionModel().reset()
            self.table_view.selectionModel().select( self.table_view.model().index(row,0), QItemSelectionModel.Select | QItemSelectionModel.Rows)

            # I have to do it twice, I don't know why...
            self.table_view.scrollTo( self.table_view.model().index(row,0), QAbstractItemView.EnsureVisible )
            self.table_view.scrollTo( self.table_view.model().index(row,0), QAbstractItemView.EnsureVisible )

            mainlog.debug("set_on_order_part row={}".format(row))
        else:
            mainlog.debug("set_on_order_part order_part_id not found")

    ORDER_PART_SELECTION_ACTIVE_ORDERS = 1
    ORDER_PART_SELECTION_PREORDERS = 2
    ORDER_PART_SELECTION_ON_HOLD = 4
    ORDER_PART_SELECTION_FINISHED = 8


    def set_parts_selection_criteria(self, criteria):
        """
        Criteria
         - 1 : active orders
         - 2 : preorders
         - 4 : orders on hold (not yet in prod or prod paused)
         - 8 : finished orders
        """
        self.parts_selection_criteria = criteria





    def _set_data(self,model,row,col,txt,role = Qt.DisplayRole):
        model.setData(model.index(row,col),txt,role)





    def real_deal(self,line):
        order_part_id = line.order_part_id
        if order_part_id in self.touched_order_parts:
            # Sort on entered valule
            return str(self.touched_order_parts[order_part_id])
        else:
            # Sort on original value
            return str(line.flags)


    SECTION_PREORDER_LABEL = 1
    SECTION_ACCOUNTING_LABEL = 0
    SECTION_CUSTOMER = 2
    SECTION_DESCRIPTION = 3
    SECTION_DEADLINE = 4
    SECTION_TIME = 5
    SECTION_QUANTITY = 6
    SECTION_PRICE = 7
    SECTION_GOAL = 10
    # SECTION_HUMAN_TIME = 8
    SECTION_PRIORITY = 8

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
        elif section_sorted == self.SECTION_PRIORITY: # order/part
            sort_criteria = lambda a,b: cmp(a.priority,b.priority)
        else:
            sort_criteria = None

        if sort_criteria is not None:
            self.current_sort_criteria = sort_criteria
        else:
            sort_criteria = self.current_sort_criteria

        order_stay_together = sort_criteria not in (self.SECTION_GOAL,self.SECTION_PRICE,self.SECTION_DEADLINE,self.SECTION_PRIORITY)

        return sort_criteria, order_stay_together


    def fill_model(self, parts_data = None):
        chrono_start()

        if parts_data is not None:
            self.parts_data = parts_data
        else:
            parts_data = self.parts_data


        self.order_part_to_row = dict()

        headers = self.table_view.horizontalHeader()
        model = self.table_view.model()

        section_sorted = headers.sortIndicatorSection() or self.SECTION_CUSTOMER

        sort_criteria, order_stay_together = self._get_sort_criteria(section_sorted)

        # Don't use model.clear() because it also clear the headers (and
        # their info such as resize policies)
        ## model.removeRows(0, model.rowCount())
        # model.setHorizontalHeaderLabels(self.htext) # Will set column count
        ## model.setRowCount(len(parts_data))

        sort_order = None

        if sort_criteria:
            sort_order = headers.sortIndicatorOrder()
            if sys.version[0] == '3':
                parts_data = sorted(parts_data, key=cmp_to_key(sort_criteria), reverse = sort_order == Qt.DescendingOrder)
            else:
                parts_data = sorted(parts_data, sort_criteria, reverse = sort_order == Qt.DescendingOrder)

        self._table_model.buildModelFromArray(parts_data)

        if sort_criteria:
            # Changing the model removes the sort order (which makes sense because
            # changing the model may alter the order of rows)
            headers.setSortIndicator(section_sorted,sort_order)



        if len(parts_data) == 0:
            # Must do this because when the model is empty
            # the selection is not updated, so no signal
            # is sent
            self.operations_view.fill_order_part(None)
            self.operations_subframe.set_title(_("Operations"))

        else:
            self.table_view.selectionModel().reset()
            self.table_view.selectionModel().select( self.table_view.model().index(0,0), QItemSelectionModel.Select | QItemSelectionModel.Rows)


        self.table_view.horizontalHeader().setResizeMode(self.SECTION_DESCRIPTION,QHeaderView.Stretch) # Description column wide enough
        self.table_view.horizontalHeader().resizeSection(self.SECTION_ACCOUNTING_LABEL,60)
        self.table_view.horizontalHeader().resizeSection(self.SECTION_PREORDER_LABEL,60)
        self.table_view.horizontalHeader().resizeSection(self.SECTION_CUSTOMER,100)

        chrono_click("Fill model")





    @Slot(int)
    def section_clicked(self,logical_ndx):
        self.fill_model()


    @Slot(QModelIndex,QModelIndex)
    def model_changed_slot(self,top_left, bottom_right):
        return

        ndx = self.table_view.currentIndex()
        model = self.table_view.model()
        data = model.data( model.index(ndx.row(),0), Qt.UserRole)

        # FIXME We don't track notes changes because we
        # want them to be saved instantaneously
        # But that's somehwta dirty.

        if data and top_left.column() != self.notes_column:
            order_part_id,order_id = data
            monthly_goal = model.data( model.index(ndx.row(),self.SECTION_GOAL), Qt.DisplayRole)
            # mainlog.debug("MCS : Touched order part : {} -> {}".format(order_part_id,monthly_goal))
            self.touched_order_parts[order_part_id] = monthly_goal
            self.data_changed_signal.emit()

    def data_changed(self):
        return len(self.touched_order_parts) > 0

    @Slot()
    def save_slot(self):
        if self.data_changed():
            mainlog.debug("Saving")
            dao.order_part_dao.bulk_change_flags(self.touched_order_parts)
            self.touched_order_parts.clear()
            self.data_changed_signal.emit()
        else:
            mainlog.debug("Nothing to save")

        return True

    def save_if_necessary(self):
        """ True if the user has either said he doesn't want to save or
        he saved successufly. False if the user has cancelled (no save, no "no save")
        or the save operation has failed """

        if self.data_changed():
            ynb = yesNoBox(_("Data were changed"),
                           _("You have changed some of the data in this. Do you want to save before proceeding ?"))
            if ynb == QMessageBox.Yes:
                if self.save_slot() != False:  # FIXME defensive, make sure it's True
                    # Because when I save, although the order definition is
                    # not meant to change, the order numbers (accounting label,
                    # etc.) might actually change.
                    return True
                else:
                    return False
            elif ynb == QMessageBox.No:
                return True
            elif ynb == QMessageBox.Cancel:
                return False
        else:
            return True


    @Slot()
    def monthly_goal_slot(self):
        return

        ndx = self.table_view.currentIndex()
        model = self.table_view.model()
        data = model.data( model.index(ndx.row(),0), Qt.UserRole)
        if data:
            order_part_id,order_id = data
            monthly_goal = model.data( model.index(ndx.row(),self.SECTION_GOAL), Qt.DisplayRole)
            mainlog.debug("Touched orders : {} -> {}".format(order_id,monthly_goal))
            self.touched_order_parts[order_part_id] = monthly_goal


    def filter(self,f,warn_too_many_results):

        #self.overview_frame.set_title(_("Orders for filter"))

        if " " in f.strip():
            # More than one word in the filter => I assume it's the full
            # fledged filtering

            check = check_parse(f)
            if check == True:
                self.fill_model( dao.order_dao.load_order_parts_on_filter(f))
                self.selection_criteria = f
            else:
                showErrorBox(_("Error in the filter !"),check,object_name="filter_is_wrong")
        else:
            try:

                # Disable any ordering to
                # make sure the parts are displayed in the order
                # of the query results. That's because we order things
                # "most relevant first" and that order cannot
                # be chosen by column.

                self.current_sort_criteria = None
                self.table_view.horizontalHeader().setSortIndicator(-1,Qt.AscendingOrder)

                too_many_results, res = dao.order_part_dao.find_ids_by_text(f.strip())
                self.fill_model( dao.order_part_dao.find_by_ids(res))
                self.selection_criteria = f

                if warn_too_many_results and too_many_results:
                    showWarningBox(_("Too many results"),_("The query you've given brought back too many results. Only a part of them is displayed. Consider refining your query"))

            except DataException as de:
                if warn_too_many_results:
                    if de.code == DataException.CRITERIA_IS_EMPTY:
                        showErrorBox(_("Error in the filter !"),_("The filter can't be empty"),object_name="filter_is_empty")
                    elif de.code == DataException.CRITERIA_IS_TOO_SHORT:
                        showErrorBox(_("Error in the filter !"),_("The filter is too short"),object_name="filter_is_too_short")



    def _figure_order_par_id_after_deleted_one(self):
        ndx_max, ndx_min = -1,999999999999
        for sndx in self.table_view.selectedIndexes():
            if sndx.row() > ndx_max:
                ndx_max = sndx.row()

            if sndx.row() < ndx_min:
                ndx_min = sndx.row()

        if ndx_max == -1:
            return None

        if ndx_max < self.table_view.model().rowCount() - 1:
            # We prefer to show the cursor after the just-disappeared order parts
            ndx = ndx_max + 1
        elif ndx_min >= 1:
            # If we can't go after those, we'll go just before
            ndx = ndx_min - 1
        else:
            # If neither is possible, well, we can't do anything more
            return None

        model = self.table_view.model()
        data = model.data( model.index(ndx,0), Qt.UserRole)
        order_part_id,order_id = data
        return order_part_id

    @Slot()
    def refresh_action(self, base_date, criteria, warn_too_many_results=True):

        order_part_id = self._figure_order_par_id_after_deleted_one()

        # mainlog.debug("CurrentOrderOverview : refresh action")

        mainlog.debug("refresh_action. Current order_part_id is {}".format(order_part_id))

        self.selection_criteria = criteria

        if type(criteria) == int:
            self.base_date = base_date
            self.parts_data = dao.order_dao.load_order_parts_overview(self.base_date, criteria)
            # self.overview_frame.set_title(_("Orders for {}").format(date_to_my(self.base_date,full=True)))
            self.fill_model(self.parts_data)
        else:
            self.filter(criteria,warn_too_many_results)


        if order_part_id:
            self.set_on_order_part(order_part_id)

        mainlog.debug("CurrentOrderOverview : refresh_action - done")


    @Slot(QModelIndex,QModelIndex)
    def order_part_selected(self, ndx_cur, ndx_old):

        if ndx_cur.isValid():
            data = self._table_model.data(self._table_model.index(ndx_cur.row(),0),Qt.UserRole)
            if not data: # Hack just for migration to special model
                return
            order_part_id,order_id = data

            # note = self._table_model.data(self._table_model.index(ndx_cur.row(),self.notes_column),Qt.DisplayRole)

            self.plan_order_part_id_change(order_part_id)
            # self.note_area.set_order_part_id_note(order_part_id, note)





            # Locate the appropriate parts data
            for row in self.parts_data:
                if row.order_part_id == order_part_id:
                    encours = business_computations_service.encours_on_params(
                        row.tex2, row.qty, row.total_hours,
                        row.total_estimated_time,
                        row.sell_price, row.material_value,
                        order_part_id, self.base_date)

                    self.valorisation_label.set_amount(encours)
                    self.unit_sell_price_label.set_amount(row.sell_price)

                    part     = row.accounting_part_label
                    preorder = row.preorder_part_label
                    customer = row.fullname

                    self.operations_subframe.set_title(
                        customer + "<br/>" + order_number_title( preorder, part, None))

                    # self.operations_subframe.set_title(
                    #     ellipsis( "{} {}".format( part, customer), 30))

                    break
        else:
            self.plan_order_part_id_change(order_part_id)

    def _init_speed_limit(self):
        self.pause_triggers = False
        self.future_order_part_id = None
        self.trigger = QTimer()
        self.trigger.timeout.connect(self._trigger_future_order_part_id)

    def _trigger_future_order_part_id(self):

        if not self.pause_triggers:
            self.order_part_id,self.future_order_part_id = self.future_order_part_id,None

            # order_part = dao.order_part_dao.find_by_id(self.order_part_id)

            self.operations_view.fill_order_part(self.order_part_id)
            self.employee_view.set_order_part_id(self.order_part_id)



    def plan_order_part_id_change(self,order_part_id):
        self.future_order_part_id = order_part_id
        self.pause_triggers = True
        self.trigger.setSingleShot(True)
        self.trigger.start(200) # millisec
        self.pause_triggers = False

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

    def current_part_and_order_id(self):
        ndx = self.table_view.currentIndex()
        if ndx.isValid():
            order_part_id,order_id = self._table_model.data(self._table_model.index(ndx.row(),0),Qt.UserRole)
            return order_part_id,order_id # Hey! Swapped !
        else:
            return None, None

    def _init_orders_overview(self):

        # self._table_model = QStandardItemModel(0, len(self.htext), None)

        self._table_model = QuickModel(self)
        self._table_model.setHorizontalHeaderLabels(self.htext) # Will set column count



        # self.headers_view = QHeaderView(Qt.Orientation.Horizontal,self)
        #self.header_model = headers
        #self.headers_view.setModel(self._table_model) # qt's doc : The view does *not* take ownership


        self.table_view = QTableView(None)
        # self.boolean_delegate = CheckBoxDelegate(None)
        # self.table_view.setItemDelegateForColumn(self.SECTION_GOAL, self.boolean_delegate)


        self.table_view.setModel(self._table_model)
        self.table_view.setWordWrap(False)
        self.table_view.setTextElideMode(Qt.ElideRight)

        # from ComboDelegate import TextAreaTableDelegate
        # self.description_delegate = TextAreaTableDelegate()
        # self.description_delegate.set_table(self.table_view)
        ## self.table_view.setItemDelegateForColumn(self.SECTION_DESCRIPTION, self.description_delegate)


        self.table_view.horizontalHeader().setClickable(True)
        self.table_view.horizontalHeader().setSortIndicatorShown(True)
        self.table_view.horizontalHeader().setSortIndicator(self.SECTION_ACCOUNTING_LABEL,Qt.AscendingOrder)

        self.table_view.horizontalHeader().sectionClicked.connect(self.section_clicked)

        self.table_view.verticalHeader().hide()

        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)


        self.table_view.model().dataChanged.connect(self.model_changed_slot)
        self.table_view.activated.connect(self.order_part_activated)
        self.table_view.setColumnHidden(self.SECTION_PRICE,not self.show_price_values)


        self.copy_parts_action = QAction(_("Copy order parts"),self.table_view)
        self.copy_parts_action.triggered.connect( self.copy_parts_slot)
        self.copy_parts_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_C))
        self.copy_parts_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.table_view.addAction(self.copy_parts_action)

        self.select_all_action = QAction(_("Select all"),self.table_view)
        self.select_all_action.triggered.connect( self.select_all_slot)
        self.select_all_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_A))
        self.select_all_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.table_view.addAction(self.select_all_action)


    @Slot()
    def select_all_slot(self):
        m = self.table_view.model()
        all = QItemSelection(m.index(0,0), m.index(m.rowCount()-1, m.columnCount()-1))
        self.table_view.selectionModel().select(all,QItemSelectionModel.Select)

    # @Slot()
    # def copy_operations_slot(self):
    #     # Collect the rows indices

    #     rows = set()
    #     for ndx in self.operations_view.selectedIndexes():
    #         if ndx.row() >= 0:
    #             rows.add(ndx.row())

    #     # There are no guarantee on the selectedIndexes order
    #     rows = sorted(list(rows))

    #     for row in rows:



    # @Slot()
    # def copy_parts_slot(self):
    #     mainlog.debug("CurrentOrdersOverview.copy_part_slot")
    #
    #     # Collect the rows indices
    #
    #     rows = set()
    #     for ndx in self.table_view.selectedIndexes():
    #         if ndx.row() >= 0:
    #             rows.add(ndx.row())
    #
    #     # There are no guarantee on the selectedIndexes order
    #     rows = sorted(list(rows))
    #
    #
    #     # Copy for elsewhere in Horse
    #
    #     if len(rows):
    #         order_parts_id = []
    #         for row_ndx in rows:
    #             order_part_id, order_id = self._table_model.data(self._table_model.index(row_ndx,0),Qt.UserRole)
    #             order_parts_id.append(order_part_id)
    #         copy_paste_manager.copy_parts_by_id(order_parts_id)
    #     else:
    #         # If nothing to copy then we leave the copy/paste clipboard
    #         # as it is. So one could paste again what he copied before.
    #         pass
    #
    #     # Copy for outside Horse (more eactly, copy for Excel and the likes)
    #
    #     h = []
    #     h.append(self.htext[self.SECTION_PREORDER_LABEL])
    #     h.append(self.htext[self.SECTION_ACCOUNTING_LABEL])
    #     h.append(self.htext[self.SECTION_CUSTOMER])
    #     h.append(self.htext[self.SECTION_DESCRIPTION])
    #     h.append(self.htext[self.SECTION_DEADLINE])
    #     h.append(self.htext[self.SECTION_TIME])
    #     h.append("")
    #     h.append(self.htext[self.SECTION_QUANTITY])
    #     h.append("")
    #     h.append(self.htext[self.SECTION_PRICE])
    #     h.append("")
    #     h.append(self.htext[self.SECTION_PRIORITY])
    #
    #     s = "\t".join(h) + u"\n"
    #     model = self.table_view.model()
    #
    #     for row in sorted(rows):
    #
    #         a = []
    #
    #         a.append(model.index(row,self.SECTION_PREORDER_LABEL).data() or "")
    #         a.append(model.index(row,self.SECTION_ACCOUNTING_LABEL).data() or "")
    #
    #         a.append(model.index(row,self.SECTION_CUSTOMER).data(Qt.UserRole))
    #
    #         a.append(model.index(row,remove_crlf(self.SECTION_DESCRIPTION).data()) or "")
    #         a.append(model.index(row,self.SECTION_DEADLINE).data() or "")
    #
    #         a.append(str(model.index(row,self.SECTION_TIME).data(Qt.UserRole)[0]).replace(".",",") or "")
    #         a.append(str(model.index(row,self.SECTION_TIME).data(Qt.UserRole)[1]).replace(".",",") or "")
    #
    #         a.append(str(model.index(row,self.SECTION_QUANTITY).data(Qt.UserRole)[0]).replace(".",",") or "")
    #         a.append(str(model.index(row,self.SECTION_QUANTITY).data(Qt.UserRole)[1]).replace(".",",") or "")
    #
    #         a.append(str(model.index(row,self.SECTION_PRICE).data(Qt.UserRole)).replace(".",",") or "")
    #
    #         a.append(model.index(row,self.SECTION_PRIORITY).data() or "")
    #
    #         s += u"\t".join(a)
    #         s += u"\n"
    #
    #     QApplication.clipboard().setText(s)
    #
    #
    #
    #     self.copy_parts_action = QAction(_("Copy order parts"),self.table_view)
    #     self.copy_parts_action.triggered.connect( self.copy_parts_slot)
    #     self.copy_parts_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_C))
    #     self.copy_parts_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
    #     self.table_view.addAction(self.copy_parts_action)
    #
    #     self.select_all_action = QAction(_("Select all"),self.table_view)
    #     self.select_all_action.triggered.connect( self.select_all_slot)
    #     self.select_all_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_A))
    #     self.select_all_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
    #     self.table_view.addAction(self.select_all_action)
    #

    @Slot()
    def select_all_slot(self):
        m = self.table_view.model()
        all = QItemSelection(m.index(0,0), m.index(m.rowCount()-1, m.columnCount()-1))
        self.table_view.selectionModel().select(all,QItemSelectionModel.Select)

    @Slot()
    def copy_parts_slot(self):

        # # Collect the rows indices
        #
        # rows = set()
        # for ndx in self.table_view.selectedIndexes():
        #     if ndx.row() >= 0:
        #         rows.add(ndx.row())


        h = []
        h.append(self.htext[self.SECTION_ACCOUNTING_LABEL])
        h.append(self.htext[self.SECTION_PREORDER_LABEL])
        h.append(self.htext[self.SECTION_CUSTOMER])
        h.append(self.htext[self.SECTION_DESCRIPTION])
        h.append(self.htext[self.SECTION_DEADLINE])
        h.append(self.htext[self.SECTION_TIME])
        h.append("")
        h.append(self.htext[self.SECTION_QUANTITY])
        h.append("")
        h.append(self.htext[self.SECTION_PRICE])
        # h.append(self.htext[self.SECTION_HUMAN_TIME])
        h.append(self.htext[self.SECTION_PRIORITY])

        # s = "\t".join(h) + u"\n"
        # model = self.table_view.model()
        #
        # for row in sorted(list(rows)):
        #
        #     a = []
        #
        #     a.append(model.index(row,self.SECTION_ACCOUNTING_LABEL).data() or "")
        #     a.append(model.index(row,self.SECTION_PREORDER_LABEL).data() or "")
        #
        #     a.append(model.index(row,self.SECTION_CUSTOMER).data(Qt.UserRole))
        #
        #     a.append((remove_crlf(model.index(row,self.SECTION_DESCRIPTION).data()) or "").replace("\t"," "))
        #     a.append(model.index(row,self.SECTION_DEADLINE).data() or "")
        #
        #     a.append(format_csv(model.index(row,self.SECTION_TIME).data(Qt.UserRole)[0]))
        #     a.append(format_csv(model.index(row,self.SECTION_TIME).data(Qt.UserRole)[1]))
        #
        #     a.append(format_csv(model.index(row,self.SECTION_QUANTITY).data(Qt.UserRole)[0]))
        #     a.append(format_csv(model.index(row,self.SECTION_QUANTITY).data(Qt.UserRole)[1]))
        #
        #     a.append(format_csv(model.index(row,self.SECTION_PRICE).data(Qt.UserRole)))
        #
        #     p = model.index(row,self.SECTION_PRIORITY).data(Qt.UserRole)
        #     if p:
        #         a.append(str(p))
        #     else:
        #         a.append("")
        #
        #     a = ["\"{}\"".format(x) for x in a]
        #     s += u"\t".join(a)
        #     s += u"\n"
        #
        # # mainlog.debug(s)
        # QApplication.clipboard().setText(s)
        copy_paste_manager.copy_table_view_to_csv(self.table_view,
                                                  h,
                                                  {self.SECTION_CUSTOMER : lambda index : index.data(Qt.UserRole),
                                                   self.SECTION_TIME: lambda index : [format_csv(index.data(Qt.UserRole)[0]), format_csv(index.data(Qt.UserRole)[1])],
                                                   self.SECTION_QUANTITY: lambda index : [format_csv(index.data(Qt.UserRole)[0]), format_csv(index.data(Qt.UserRole)[1])],
                                                   self.SECTION_PRICE : lambda index : index.data(Qt.UserRole),
                                                   self.SECTION_PRIORITY : lambda index : index.data(Qt.UserRole)})

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



    def order_part_info_view(self):
        self.opinfo_layout = QHBoxLayout()
        self.opinfo_layout.setSpacing(10)

        self.opinfo_layout.addWidget( QLabel(_("Valorisation")))
        self.valorisation_label = EuroLabel()
        self.opinfo_layout.addWidget( self.valorisation_label)

        self.opinfo_layout.addWidget( QLabel(_("Unit sell price")))
        self.unit_sell_price_label = EuroLabel()
        self.opinfo_layout.addWidget( self.unit_sell_price_label)

        self.valorisation_label.setVisible(self.show_price_values)
        self.unit_sell_price_label.setVisible(self.show_price_values)


    def __init__(self,parent,find_order_action_slot,create_delivery_slip_action,show_prices):
        super(CurrentOrdersOverviewWidget,self).__init__(parent)

        self.show_price_values = show_prices
        self.current_sort_criteria = 0
        self.selection_criteria = 1
        self.base_date = date.today()
        self.touched_row = set()
        # maps order_part_id -> monthlygoal (true or false)
        self.touched_order_parts = dict()

        self.create_delivery_slip_action = create_delivery_slip_action


        self._prepare_colors()
        self._init_orders_overview()

        self.edit_action = QAction(_('Edit order'),self)
        self.edit_action.triggered.connect( self.edit_order_slot)

        self.monthly_goal_action = QAction(_('Monthly goal'),self)
        self.monthly_goal_action.triggered.connect( self.monthly_goal_slot)

        # self.order_part_edit_dialog = OrderPartsEditorDialog()
        self.parts_data = []

        self.operations_view = OperationsOverviewWidget(self)
        # self.employee_view = EditableEmployeeFacesViewSimple(self)
        self.employee_view = PartActivityView(self)


        self.order_part_info_view()

        self.current_month_label = QLabel("d")


        self.note_area = OrderPartNoteWidget()
        self.note_area.setVisible(False)
        # self.note_area.note_saved.connect(self.note_saved)


        self.vlayout = QVBoxLayout(self)
        self.vlayout.setContentsMargins(0,0,0,0)

        splitter = QSplitter(Qt.Horizontal,self)

        parts_notes_layout = QVBoxLayout()
        parts_notes_layout.addWidget(self.note_area)
        parts_notes_layout.addWidget(self.table_view)

        self.overview_frame = SubFrame(_("Orders"),parts_notes_layout,splitter)
        splitter.addWidget(self.overview_frame)

        layout = QVBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.operations_view)
        layout.addLayout(self.opinfo_layout)

        # I moved the scroll area here because if I sets it inside the
        # employee_view widget, then I can't lay it out properly (it
        # doesn't use all the vertical space)

        scroll_area = QScrollArea()
        scroll_area.setWidget(self.employee_view)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        # layout.addWidget(self.employee_view)
        layout.setStretch(0,2)
        layout.setStretch(2,1)

        self.operations_subframe = SubFrame(_("Operations"),layout,splitter)
        # self.operations_subframe.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        splitter.addWidget(self.operations_subframe)

        splitter.setStretchFactor(0,2)
        splitter.setStretchFactor(1,1)

        self.vlayout.addWidget(splitter)

        self.setLayout(self.vlayout)


        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.popup_parts)
        self.operations_view.view.selectionModel().currentChanged.connect(self.operation_selection_changed)
        # self.table_view.selectionModel().currentChanged.connect(self.order_part_selected)
        self.table_view.selectionModel().selectionChanged.connect(self.selection_changed)



        self.operations_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.operations_view.customContextMenuRequested.connect(self.show_operations_popup)


        self._init_speed_limit()



    # @Slot(int,unicode)
    # def note_saved(self,order_part_id, notes):
    #     model = self.table_view.model()
    #     row = self.order_part_to_row[order_part_id]
    #     # self._set_data(model,row,self.notes_column,notes)


    @Slot()
    def selection_changed(self,selected,deselected):
        if selected and selected.indexes() and len(selected.indexes()) > 0:
            self.order_part_selected(selected.indexes()[0], None)


    @Slot(QPoint)
    def show_operations_popup(self, position):
        menu = QMenu()
        # menu.addAction(self.copy_operations_action)
        menu.addAction(self.operations_view.copy_operations_action)

        action = menu.exec_(QCursor.pos())


    @Slot(QPoint)
    def popup_parts(self,position):

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

        order_parts_ids = set().union(*orders_to_parts.values())
        # old version : reduce(lambda x,y:x.union(y), orders_to_parts.values(), set())

        if not order_parts_ids:
            return

        authorized_states = dao.order_part_dao.next_states_for_parts(order_parts_ids)

        priority_menu = QMenu(_("Priority"))
        priority_actions = []
        for i,stars in priority_stars():
            a = QAction(stars, priority_menu)
            a.setData(i)
            priority_menu.addAction(a)
            priority_actions.append(a)

        from koi.db_mapping import OrderPartStateType

        if OrderPartStateType.non_conform in authorized_states:
            quality_menu = QMenu(_("Part state to {}").format(OrderPartStateType.non_conform.description))
            quality_actions = []

            for qet in QualityEventType.symbols():
                a = quality_menu.addAction(qet.description)
                a.setData(qet)
                quality_actions.append(a)
        else:
            quality_menu = None
            quality_actions = []

        # priority_menu.triggered.connect(self.priority_menu_triggered)

        menu = QMenu()

        menu.addAction(self.edit_action)

        if self.create_delivery_slip_action:
            menu.addAction(self.create_delivery_slip_action)
        menu.addSeparator()

        menu.addMenu(priority_menu)
        menu.addSeparator()


        for nxt in authorized_states:
            if nxt != OrderPartStateType.non_conform:
                a = menu.addAction(_("Part state to {}").format(nxt.description))
                a.setData(nxt)

        if quality_menu:
            # menu.addSeparator()
            menu.addMenu(quality_menu)

        menu.addSeparator()
        menu.addAction(self.copy_parts_action)

        action = menu.exec_(QCursor.pos())

        if action in quality_actions:
            order_part_id = list(order_parts_ids)[0]
            kind = action.data()
            dialog = NonConformityDialog(self,remote_documents_service=remote_documents_service)
            mainlog.debug("Kind of nonconformity : {}".format(kind))
            dialog.set_blank_quality_issue(kind, order_part_id)
            dialog.exec_()
            if dialog.result() == QDialog.Accepted:
                business_computations_service.mark_as_non_conform( dialog.quality_event())
                self.refresh_action(self.base_date, self.selection_criteria)

        elif action in priority_actions:
            dao.order_part_dao.change_priority(order_parts_ids, action.data())
            # self.order_parts_changed.emit()
            self.refresh_action(self.base_date, self.selection_criteria)

        elif action and action.data():
            nxt = action.data()

            if nxt:
                for order_id, order_parts_ids in orders_to_parts.items():
                    # FIXME might be a bug here...
                    dao.order_dao.change_order_parts_state(order_id,order_parts_ids,nxt)

                self.refresh_action(self.base_date, self.selection_criteria)
                ndx = self.table_view.model().index(0,0)
                # self.table_view.setFocus() # Qt.OtherFocusReason)
                # self.table_view.selectionModel().setCurrentIndex( ndx, QItemSelectionModel.SelectCurrent)
                # self.table_view.setCurrentIndex( ndx)

                self.order_parts_changed.emit()



    @Slot(QModelIndex,QModelIndex)
    def operation_selection_changed(self, current, previous):

        model = self.operations_view.model

        if current.isValid() and current.row() < len(model.objects):

            op = model.objects[current.row()]

            if op and op.operation_id:
                employees = dao.operation_dao.last_employees_on_operation(op.operation_id)
                employees = [ (emp, duration_to_hm(hours))  for emp, hours in employees]
                # self.employee_view.set_model(employees)
                return

        # self.employee_view.set_model(None)


from koi.gui.ProxyModel import TextLinePrototype, DurationPrototype, DatePrototype
from koi.gui.PrototypedModelView import PrototypedModelView

class YoModel(PrototypedModelView):
    def data(self, index, role):
        if role == Qt.TextAlignmentRole and index.column() in (3):
            return Qt.AlignRight
        else:
            return super(YoModel,self).data(index,role)


class PartActivityView(QWidget):

    FONT_WIDTH = 10 # FIXME Huge approximation !

    def __init__(self, parent):
        super(PartActivityView,self).__init__(parent)


        prototype = [ TextLinePrototype('fullname',_('Name')),
                      DurationPrototype('duration',_('Duration')),
                      DatePrototype('start_time',_('Start')),
                      TextLinePrototype('short_id',_('Operation'))]

        layout = QVBoxLayout()
        self._model = YoModel(prototype, self)

        # self.view = PrototypedQuickView(prototype, None)
        # self.view.setModel(self._model)
        # layout.addWidget(self.view)

        layout.setContentsMargins(0,0,0,0)
        # from PySide.QtGui import # or QTextEdit without editing for some richer text

        self.events_view = QLabel()

        #scroll_area = QScrollArea()
        # From the doc : the scroll area will automatically resize the widget in order to avoid scroll bars where they
        # can be avoided
        # scroll_area.setWidgetResizable(True)

        self.events_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # This pushes the scroll bar to actually expand
        # self.events_view.setMinimumSize(100,1000)
        self.events_view.setAlignment(Qt.AlignTop)
        # ------



        # self.events_view.setMinimumSize(1000,1000)
        # scroll_area.setWidget(self.events_view) # WARNING ! scrollAreat takes ownership of its widget !
        # scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # layout.addWidget(scroll_area, alignment=Qt.AlignTop)
        layout.addWidget( self.events_view)

        #layout.addWidget(self.events_view)
        self.setLayout(layout)

        self._events_cache = None


    def _load_events(self, order_part_id):
        events = DictOfDict()

        works = dao.order_part_dao.work_done_on_part(order_part_id)
        slips = dao.delivery_slip_part_dao.slips_for_order_part(order_part_id)
        quality = dao.quality_dao.find_by_order_part_id(order_part_id)

        for work in works:
            d = timestamp_to_date(work.start_time)
            events.rget(d,'TIMETRACK').append(work)

        for ds in slips:
            d = timestamp_to_date(ds.creation)
            events.rget(d,'SLIP').append(ds)

        for qe in quality:
            d = timestamp_to_date(qe.when)
            events.rget(d,'QUALITY').append(qe)

        return events


    def resizeEvent(self, event):
        super(PartActivityView, self).resizeEvent(event)
        if self._events_cache:
            self._draw( self._events_cache)

    def set_order_part_id(self, order_part_id):
        self._events_cache = self._load_events( order_part_id)
        self._draw( self._events_cache)

    def _draw(self, events):

        fulltext = "<table cellspacing='0' width='100%'>"

        bgcolor = "grey"

        for date in sorted(events.keys(), reverse=True):
            # mainlog.debug("-- {}".format(date))
            date_shown = "<b>{}</b>".format(date_to_dm(date))

            if bgcolor == "lightcyan":
                bgcolor = "white"
            else:
                bgcolor = "lightcyan"


            for line in events.rget(date,'QUALITY'):
                fulltext += "<tr bgcolor=red>" \
                            "<td align='right'>{}&nbsp;</td>" \
                            "<td colspan='6'><font color=white>{}</font></td>" \
                            "</tr>".format(
                    date_shown, wrap_html_text( "{} : {}".format(line.kind.description, remove_crlf(line.description)),
                                                self.events_view.width() // self.FONT_WIDTH))
                date_shown = ""

            for line in events.rget(date,'SLIP'):
                fulltext += "<tr bgcolor=lime>" \
                            "<td align='right'>{}&nbsp;</td>" \
                            "<td colspan='6'><font color=black>{}</font></td>" \
                            "</tr>".format(
                    date_shown, _("Delivery slip {}, <b>{}</b> units").format(line.delivery_slip_id, line.quantity_out))
                date_shown = ""

            if events.rget(date,'SLIP') and events.rget(date,'TIMETRACK'):
                fulltext += "<tr bgcolor={}><td colspan='7'><font size=1>&nbsp;</font></td></tr>".format(bgcolor)

            # work = "<table>"
            for line in events.rget(date,'TIMETRACK'):
                # mainlog.debug(type(res))
                # work = """        <table>
                # <tr>
                #     <td>Name</td>
                #     <td>Duration</td>
                #     <td>Start</td>
                # </tr>"""

                fulltext += "<tr bgcolor={}>" \
                            "<td align='right'>{}&nbsp;</td>" \
                            "<td align='right'>{}&nbsp;</td>" \
                            "<td align='right'>{}&nbsp;&nbsp;&nbsp;</td>" \
                            "<td align='left' colspan='4' width='100%'>{}</td>" \
                            "</tr>".format(
                    bgcolor, date_shown, line.short_id, duration_to_s(line.duration), line.fullname)
                date_shown = ""
                #Employee.fullname, TimeTrack.duration, TimeTrack.start_time, OperationDefinition.short_id, Operation.description
            # work += "</table>"


            fulltext += "<tr bgcolor={}>".format(bgcolor) + "<td><font size=1>&nbsp;</font></td>"*7 + "</tr>"

        # fulltext += "<tr><td>MM/MM</td><td>MM.MM</td><td>MMMM</td><td></td></tr>"
        fulltext += "</table>"
        self.events_view.setText(fulltext)
        # self._model.buildModelFromObjects(res)

if __name__ == "__main__":
    employee = dao.employee_dao.any()
    app = QApplication(sys.argv)

    window = QMainWindow()
    window.setMinimumSize(1024,768)
    widget = CurrentOrdersOverviewWidget(window,None,None, False)
    widget.set_parts_selection_criteria(2) # Preorders denk ik
    widget.refresh_action(date.today(), 1)
    window.setCentralWidget(widget)
    window.show()
    # presence.refresh_action()

    app.exec_()
