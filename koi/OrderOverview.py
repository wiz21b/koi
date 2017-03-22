#noinspection PyUnresolvedReferences
import sys

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

from PySide.QtGui import QWidget, QVBoxLayout,QHBoxLayout, QColor, QPushButton,QLabel, QDialog,QDialogButtonBox, \
    QRadioButton, QStackedLayout, QLineEdit, QPalette,QButtonGroup,QAbstractButton, QComboBox
from PySide.QtCore import Qt,Slot,Signal,QModelIndex,QPoint

from koi.db_mapping import OrderPart, FilterQuery
from koi.dao import dao
from koi.datalayer.query_parser import find_suggestions,word_at_point

from koi.translators import *
from koi.gui.dialog_utils import TitleWidget, NavBar
from koi.gui.horse_panel import HorsePanel
from koi.Configurator import mainlog, configuration
from koi.qtableviewfixed import QTableView
from koi.session.UserSession import user_session
from koi.CurrentOrdersOverview import CurrentOrdersOverviewWidget
from koi.gui.PersistentFilter import PersistentFilter, FiltersCombo
from koi.date_utils import month_before
from koi.date_utils import _last_moment_of_month


def bound(n,mini,maxi):
    if n < mini:
        return mini
    elif n > maxi:
        return maxi
    else:
        return n



class GiveNewNameDialog(QDialog):
    def __init__(self,parent):
        super(GiveNewNameDialog,self).__init__()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(_("Please give a new name")))

        self.line_edit = QLineEdit()

        layout.addWidget(self.line_edit)

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.StandardButton.Cancel)
        self.buttons.addButton( QDialogButtonBox.Ok)
        layout.addWidget(self.buttons)

        self.setLayout(layout)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    @Slot()
    def accept(self):
        if self.line_edit.text().strip():
            return super(GiveNewNameDialog,self).accept()

    @Slot()
    def reject(self):
        return super(GiveNewNameDialog,self).reject()


class OrderOverviewWidget(HorsePanel):
    def close_panel(self):
        self.persistent_filter.remember_current_selection( configuration)

    def _set_criteria_access(self, base_date):
        return
        #
        # if base_date.year < date.today().year or \
        #    (base_date.year == date.today().year and self.base_date.month < date.today().month):
        #
        #     self.select_active_orders.setEnabled(False)
        #     self.select_preorders.setEnabled(False)
        #     self.select_orders_on_hold.setEnabled(False)
        #     self.select_orders_finished.setEnabled(True)
        #     self.select_orders_aborted.setEnabled(True)
        #
        #     # self.select_orders_finished.setChecked(True) # Preselects active order but do not trigger refresh
        #
        # else:
        #     self.select_active_orders.setEnabled(True)
        #     self.select_preorders.setEnabled(True)
        #     self.select_orders_on_hold.setEnabled(True)
        #     self.select_orders_finished.setEnabled(True)
        #     self.select_orders_aborted.setEnabled(True)
        #


    # @Slot()
    # def month_today(self):
    #     self.base_date = date.today()
    #     self.refresh_action_gui()

    @Slot()
    def month_before(self):
        self.base_date = month_before(self.base_date)
        self.refresh_action_gui()

    @Slot()
    def month_after(self):
        m = self.base_date.month

        if self.base_date.year < date.today().year or m < date.today().month:
            if m < 12:
                self.base_date = date(self.base_date.year,m + 1,self.base_date.day)
            else:
                self.base_date = date(self.base_date.year + 1,1,self.base_date.day)
            self.refresh_action_gui()


    @Slot()
    def save_slot(self):
        self.current_orders_overview.save_slot()

    # @Slot()
    # def monthly_goal_slot(self):
    #     ndx = self.table_view.currentIndex()
    #     model = self.table_view.model()
    #     data = model.data( model.index(ndx.row(),0), Qt.UserRole)
    #     if data:
    #         order_part_id,order_id = data
    #         monthly_goal = model.data( model.index(ndx.row(),7), Qt.DisplayRole)
    #         mainlog.debug("Touched orders : {} -> {}".format(order_id,monthly_goal))
    #         self.touched_orders[order_id] = monthly_goal

    def set_visibility(self, visible):
        # Make sure the cursor is in the orderparts table
        # when the panel becomes visible again.
        # This allows to hit Enter from the order parts view
        # to look at a specific order, then close the view
        # of that sepcific order with Ctrl-W and then be
        # right in the order parts list here to choose
        # another order. All with the keyboard.
        super(OrderOverviewWidget,self).set_visibility(visible)
        self.retake_focus()

    def retake_focus(self):
        if self.stack_layout.currentWidget() == self.current_orders_overview:
            self.current_orders_overview.table_view.setFocus(Qt.OtherFocusReason)
        # elif self.stack_layout.currentWidget() == self.past_orders_overview:
        #     self.past_orders_overview.table_view.setFocus(Qt.OtherFocusReason)

    def refresh_action_gui(self,warn_too_many_results=True):
        mainlog.debug("OrderOverview : refresh action")

        # Figure out selection criteria
        f = self.persistent_filter.get_filters_combo().current_filter()
        if f:
            criteria = f.query
        else:
            criteria = ""

        # criteria = None
        # if self.select_active_orders.isChecked():
        #     criteria = dao.order_part_dao.ORDER_PART_SELECTION_ACTIVE_ORDERS
        # elif self.select_preorders.isChecked():
        #     criteria = dao.order_part_dao.ORDER_PART_SELECTION_PREORDERS
        # elif self.select_orders_on_hold.isChecked():
        #     criteria = dao.order_part_dao.ORDER_PART_SELECTION_ON_HOLD
        # elif self.select_orders_finished.isChecked():
        #     criteria = dao.order_part_dao.ORDER_PART_SELECTION_COMPLETED_THIS_MONTH
        # elif self.select_orders_aborted.isChecked():
        #     criteria = dao.order_part_dao.ORDER_PART_SELECTION_ABORTED_THIS_MONTH
        # elif text_filter:
        #     criteria = text_filter
        # else:
        #     return # Filter not valid so nothing to do

        # today = date.today()
        # if self.base_date.year < today.year or self.base_date.month < today.month:

        #     # Display parts in the past

        #     if self.stack_layout.currentWidget() == self.current_orders_overview:
        #         if not self.current_orders_overview.save_if_necessary():
        #             return

        #         self.old_criteria = criteria

        #     self.stack_layout.setCurrentWidget(self.past_orders_overview)
        #     self.past_orders_overview.refresh_action(self.base_date,criteria,warn_too_many_results)
        # else:

        # Display current month's parts

        # if self.stack_layout.currentWidget() == self.past_orders_overview:
        #     mainlog.debug("remembering criteria {}".format(self.old_criteria))
        #     criteria = self.old_criteria

        #     # FIXME use a ButtonGroup to avoid that kind of stuff
        #     if criteria == dao.order_part_dao.ORDER_PART_SELECTION_ACTIVE_ORDERS:
        #         self.select_active_orders.setChecked(True)
        #     elif criteria == dao.order_part_dao.ORDER_PART_SELECTION_PREORDERS:
        #         self.select_preorders.setChecked(True)
        #     elif criteria == dao.order_part_dao.ORDER_PART_SELECTION_ON_HOLD:
        #         self.select_orders_on_hold.setChecked(True)
        #     elif criteria == dao.order_part_dao.ORDER_PART_SELECTION_COMPLETED_THIS_MONTH:
        #         self.select_orders_finished.setChecked(True)
        #     elif criteria == dao.order_part_dao.ORDER_PART_SELECTION_ABORTED_THIS_MONTH:
        #         self.select_orders_aborted.setChecked(True)
        #     else:
        #         self.super_filter_entry.setText(criteria)

        self.stack_layout.setCurrentWidget(self.current_orders_overview)
        last_date = _last_moment_of_month(self.base_date)

        self.current_orders_overview.refresh_action(last_date, criteria, warn_too_many_results)

        self._set_criteria_access(self.base_date)
        self.current_orders_overview.table_view.setFocus(Qt.OtherFocusReason)


    @Slot()
    def refresh_action(self):
        self.refresh_action_gui(warn_too_many_results=False)

    # @Slot()
    # def month_synthesis(self):
    #     d = MonthlyReportOverviewDialog(self)
    #     d.refresh_action_gui(self.base_date)
    #     d.exec_()

    # @Slot(QModelIndex,QModelIndex)
    # def order_part_selected(self, ndx_cur, ndx_old):
    #     if ndx_cur.isValid():
    #         order_part_id,order_id = self._table_model.data(self._table_model.index(ndx_cur.row(),0),Qt.UserRole)
    #         self.operations_view.set_order_part_id(order_part_id)
    #     else:
    #         self.operations_view.set_order_part_id(None)

    # @Slot()
    # def edit_order_slot(self):
    #     # Need this because there's a mismatch in the parameter
    #     # signature of the edit orders slot. See order_part_activated
    #     # below
    #     self.order_part_activated(self.table_view.currentIndex())

    @Slot(int)
    def set_on_order_part_slot(self,order_part_id):
        # Is used by othe views to set this one on
        # a specific order part
        self.current_orders_overview.set_on_order_part(order_part_id)

    order_part_activated_signal = Signal(OrderPart) # order_part_id
    order_parts_changed = Signal()

    @Slot(QModelIndex)
    def order_part_activated_slot(self,order_part_id):
        mainlog.debug("order_part_activated_slot : {}".format(order_part_id))
        order_part = dao.order_part_dao.find_by_id(order_part_id)
        self.order_part_activated_signal.emit(order_part)

    @Slot(QModelIndex)
    def order_parts_changed_slot(self):
        self.order_parts_changed.emit()

    def current_order_id(self):
        if self.stack_layout.currentWidget() == self.current_orders_overview:
            return self.current_orders_overview.current_order_id()
        # else:
        #     return self.past_orders_overview.current_order_id()


    def set_title(self):
        save_notice = ""
        if self.data_changed():
            save_notice = " <b><font color='red'>***</font></b>"
        self.title_box.set_title(_("Orders overview") + save_notice)


    def data_changed(self):
        return self.current_orders_overview.data_changed()

    @Slot()
    def super_filter(self, filter_query : str):
        self.current_orders_overview.filter( filter_query, True)

    @Slot()
    def show_actions(self):
        button = self.action_menu.parent()
        p = button.mapToGlobal(QPoint(0,button.height()))
        self.action_menu.exec_(p)


    # def _show_filter(self,fq):
    #     if fq:
    #         self.super_filter_entry.setText(fq.query)
    #         self.save_filter_button.setEnabled(fq.owner_id == user_session.user_id)
    #         self.delete_filter_button.setEnabled(fq.owner_id == user_session.user_id)

    #         if fq.shared:
    #             self.share_filter.setCheckState(Qt.Checked)
    #         else:
    #             self.share_filter.setCheckState(Qt.Unchecked)
    #     else:
    #         self.super_filter_entry.setText("")
    #         self.share_filter.setCheckState(Qt.Unchecked)
    #         self.save_filter_button.setEnabled(True)
    #         self.delete_filter_button.setEnabled(True)


    # def _load_available_queries(self,preselect_fq_id=None):
    #     self.filter_name.clear()

    #     filters = dao.filters_dao.usable_filters(user_session.user_id)

    #     ndx_to_select = None

    #     self.filter_name.addItem(None, None)
    #     i = 0
    #     for fq in filters:

    #         if preselect_fq_id == fq.filter_query_id:
    #             ndx_to_select = i

    #         n = fq.name
    #         if fq.owner_id != user_session.user_id:
    #             n = n + u" ({})".format(fq.fullname)
    #         self.filter_name.addItem(n, fq.filter_query_id)
    #         i = i + 1

    #     if ndx_to_select is not None:
    #         self.filter_name.setCurrentIndex(ndx_to_select+1) # +1 to skip the empty item
    #         self._show_filter(filters[ndx_to_select])
    #     else:
    #         self._show_filter(None)



    # @Slot()
    # def filter_activated_slot(self,ndx):

    #     fq_id = self.filter_name.itemData(self.filter_name.currentIndex())

    #     if fq_id:
    #         try:
    #             fq = dao.filters_dao.find_by_id(fq_id)
    #             self._show_filter(fq)
    #             self.super_filter()
    #         except Exception,e:
    #             showErrorBox(_("There was a problem while loading the filter. It may have been deleted by its owner"),None,e,object_name="missing_filter")
    #             # MAke sure the filter doesn't appear anymore
    #             self._load_available_queries()
    #             self._show_filter(None)
    #             return
    #     else:
    #         self._show_filter(None)

    # @Slot()
    # def delete_filter_action_slot(self):
    #     try:
    #         fq_id = None
    #         if self.filter_name.currentIndex() >= 0:
    #             fq_id = self.filter_name.itemData(self.filter_name.currentIndex())

    #         if not fq_id:
    #             showWarningBox(_("The filter you want to delete was never saved"),None,parent=self,object_name="no_need_to_delete_filter")
    #             return

    #         fq = dao.filters_dao.find_by_id(fq_id)
    #         if fq.owner_id != user_session.user_id:
    #             showWarningBox(_("You can't delete the filter because it doesn't belong to you."),None,parent=self,object_name="not_my_filter")
    #             return

    #         dao.filters_dao.delete_by_id(fq_id,user_session.user_id)
    #         self._load_available_queries()
    #     except Exception, e:
    #         mainlog.error("Can't delete fq_id = {}".format(fq_id))
    #         showErrorBox(_("There was a problem while deleting the filter."),None,e,object_name="delete_filter_fatal")


    # def _check_and_copy_filter(self,dto):

    #     fq_query = self.super_filter_entry.text()
    #     if not fq_query or not fq_query.strip():
    #         showWarningBox(_("The filter's query can't be empty"),None,parent=self,object_name="empty_filter_query")
    #         return False

    #     dto.owner_id = user_session.user_id
    #     dto.shared = self.share_filter.checkState() == Qt.Checked
    #     dto.query = fq_query
    #     return True


    # @Slot()
    # def save_filter_as_action_slot(self):
    #     d = GiveNewNameDialog(self)
    #     d.exec_()

    #     if d.result() == QDialog.Accepted:
    #         new_name = d.line_edit.text()
    #         if not dao.filters_dao.is_name_used(new_name, user_session.user_id):
    #             fq = dao.filters_dao.get_dto(None)
    #             if self._check_and_copy_filter(fq):
    #                 fq.name = new_name
    #                 fq_id = dao.filters_dao.save(fq)
    #                 self._load_available_queries(fq_id)
    #         else:
    #             showErrorBox(_("There is already a filter with that name. You must delete it first if you want to use that name."),None,None,object_name="filter_with_same_name")

    # @Slot()
    # def save_filter_action_slot(self):

    #     ndx = self.filter_name.currentIndex()
    #     fq_id = None

    #     if ndx > 0:
    #         fq_id = self.filter_name.itemData(ndx)
    #         fq = dao.filters_dao.get_dto(fq_id)

    #         if fq.owner_id == user_session.user_id:
    #             if self._check_and_copy_filter(fq):
    #                 fq.name = self.filter_name.itemText(ndx)
    #                 fq_id = dao.filters_dao.save(fq)
    #                 self._load_available_queries(fq_id)
    #         else:
    #             if yesNoBox(_("This is not your filter !"), _("OK to save it under another name ?")) == QMessageBox.Yes:
    #                 self.save_filter_as_action_slot()
    #     else:
    #         self.save_filter_as_action_slot()


    # @Slot(int,int)
    # def cursorPositionChanged_slot(self,old,new):
    #     return


    # @Slot()
    # def completEditFinished_slot(self):
    #     # self.super_filter_entry.completion.hide()
    #     self.nofocuslost = False

    @Slot(QAbstractButton)
    def button_clicked(self, button):
        return
        #
        # for b in self.button_group.buttons():
        #     if b != button:
        #         b.setChecked(False)
        # self.refresh_action_gui()

    def clear_search_buttons(self):
        return
        #
        # for b in self.button_group.buttons():
        #     b.setChecked(False)

    @Slot()
    def _toggle_edit_filters(self):
        self.persistent_filter.setVisible( not self.persistent_filter.isVisible())


    def __init__(self,parent,find_order_action_slot,create_delivery_slip_action,show_prices=True):
        super(OrderOverviewWidget,self).__init__(parent)
        self.set_panel_title(_("Order Overview"))
        self.base_date = date.today()
        self.touched_row = set()

        # maps order_id -> monthlygoal (true or false)
        self.touched_orders = dict()

        self.create_delivery_slip_action = create_delivery_slip_action

        # self.edit_action = QAction(_('Edit order'),self)
        # self.edit_action.triggered.connect( self.edit_order_slot)

	    # self.past_orders_overview = PastOrdersOverviewWidget(None,None,None,show_prices)
        self.current_orders_overview = CurrentOrdersOverviewWidget(None,None,None,show_prices)
        self.current_orders_overview.order_part_activated_signal.connect(self.order_part_activated_slot)
        self.current_orders_overview.order_parts_changed.connect(self.order_parts_changed_slot)

        # self.past_orders_overview.order_part_activated_signal.connect(self.order_part_activated_slot)


        self.vlayout = QVBoxLayout(self)

        # self.select_active_orders = QRadioButton(_("Production"),self)
        # self.select_active_orders.setToolTip(_("Order that are in production (as specified by their state)"))
        #
        # self.select_preorders = QRadioButton(_("Preorders"),self)
        #
        # self.select_orders_on_hold = QRadioButton(_("Dormant"),self)
        # self.select_orders_on_hold.setToolTip(_("Orders that are either on hold or to be defined (as specified by their state)"))
        # self.select_orders_finished = QRadioButton(_("Finished"),self)
        # self.select_orders_finished.setToolTip(_("Orders that were marked as completed this month"))
        #
        # self.select_orders_aborted = QRadioButton(_("Aborted"),self)
        # self.select_orders_aborted.setToolTip(_("Orders that were prematurely cancelled"))

        # I need a button group which is exclusive but
        # which also allows *all* the buttons to bl cleared
        # at once. The regular exclusive flags forces
        # us to have always one button checked...

        # self.button_group = QButtonGroup(self)
        # self.button_group.addButton(self.select_active_orders)
        # self.button_group.addButton(self.select_preorders)
        # self.button_group.addButton(self.select_orders_on_hold)
        # self.button_group.addButton(self.select_orders_finished)
        # self.button_group.addButton(self.select_orders_aborted)
        # self.button_group.setExclusive(False)
        # self.button_group.buttonClicked.connect(self.button_clicked)



        # I need to be able to unselect all buttons (in case I use the super filter)

        # self.select_active_orders.setAutoExclusive(False)
        # self.select_preorders.setAutoExclusive(False)
        # self.select_orders_on_hold.setAutoExclusive(False)
        # self.select_orders_finished.setAutoExclusive(False)
        # self.select_orders_aborted.setAutoExclusive(False)

        # self.select_active_orders.setChecked(True) # Preselects active order

        self.persistent_filter = PersistentFilter( FilterQuery.ORDER_PARTS_OVERVIEW_FAMILY, find_suggestions)
        self.persistent_filter.apply_filter.connect( self.super_filter)


        navigation = NavBar( self,
                             [ (self.persistent_filter.get_filters_combo(), None),
                               (_("Edit filter"),self._toggle_edit_filters),
                               (_("Find"), find_order_action_slot)] )

        self.persistent_filter.hide()
        # self.persistent_filter.select_default_filter()

        # navigation.buttons[7].setObjectName("specialMenuButton")


        # self.save_filter_action = QAction(_("Save filter"),self)
        # self.save_filter_action.triggered.connect( self.save_filter_action_slot)

        # self.save_filter_as_action = QAction(_("Save filter as"),self)
        # self.save_filter_as_action.triggered.connect( self.save_filter_as_action_slot)

        # self.delete_filter_action = QAction(_("Delete filter"),self)
        # self.delete_filter_action.triggered.connect( self.delete_filter_action_slot)

        def action_to_button(action):
            b = QPushButton(action.text())
            b.clicked.connect(action.trigger)
            return b

        # self.action_menu = QMenu(navigation.buttons[8])

        # self.filter_menu = QMenu("Filter menu")
        # self.filter_menu.addAction("filter alpha")
        # self.filter_menu.addAction("filter beta")

        # list_actions = [ (self.save_filter_action,None,None),
        #                  (self.save_filter_as_action,None,None),
        #                  (self.delete_filter_action,       None,None),
        #                  (self.filter_menu,       None,None) ]

        # populate_menu(self.action_menu, self, list_actions, context=Qt.WidgetWithChildrenShortcut)


        self.title_box = TitleWidget(_("Orders overview"),self,navigation) # + date.today().strftime("%B %Y"),self)

        self.vlayout.addWidget(self.title_box)

        self.vlayout.addWidget(self.persistent_filter)

        # hlayout_god_mode = QHBoxLayout()
        # hlayout_god_mode.addWidget(QLabel(_("Filter :")))


        # self.filter_name = QComboBox()
        # self.filter_name.setMinimumWidth(100)
        # # self.filter_name.setEditable(True)

        # I use activated so that reselecting the same index
        # triggers an action (for example, clears a badly
        # edited filter)

        # self.filter_name.activated.connect(self.filter_activated_slot)

        # hlayout_god_mode.addWidget(self.filter_name)

        # hlayout_god_mode.addWidget(QLabel(_("Query :")))

        # hlayout_god_mode.addWidget(self.super_filter_entry)

        # # self.completion.setParent(self.super_filter_entry)
        # self.super_filter_entry.cursorPositionChanged.connect(self.cursorPositionChanged_slot)
        # # self.super_filter_entry.editingFinished.connect(self.completEditFinished_slot)
        # # self.super_filter_entry.returnPressed.connect(self.super_filter)

        # self.share_filter = QCheckBox(_("Shared"))
        # hlayout_god_mode.addWidget(self.share_filter)


        # self.super_filter_button = QPushButton(_("Filter"))
        # hlayout_god_mode.addWidget(self.super_filter_button)

        # self.save_filter_button = action_to_button(self.save_filter_action)
        # hlayout_god_mode.addWidget(self.save_filter_button)

        # hlayout_god_mode.addWidget(action_to_button(self.save_filter_as_action))

        # self.delete_filter_button = action_to_button(self.delete_filter_action)
        # hlayout_god_mode.addWidget(self.delete_filter_button)

        # self.vlayout.addLayout(hlayout_god_mode)


        # self.super_filter_button.clicked.connect(self.super_filter)
        # self.select_active_orders.clicked.connect(self.refresh_action)
        # self.select_preorders.clicked.connect(self.refresh_action)
        # self.select_orders_on_hold.clicked.connect(self.refresh_action)
        # self.select_orders_finished.clicked.connect(self.refresh_action)
        # self.select_orders_aborted.clicked.connect(self.refresh_action)

        self.current_orders_overview.data_changed_signal.connect(self.set_title)

        self.stack_layout = QStackedLayout()
        self.stack_layout.addWidget(self.current_orders_overview)
        # self.stack_layout.addWidget(self.past_orders_overview)

        self.vlayout.addLayout(self.stack_layout)
        self.setLayout(self.vlayout)

        # self._load_available_queries()
        self.persistent_filter.load_last_filter(configuration)

from koi.QuickComboModel import QuickComboModel

class Blew(QWidget):
    def __init__(self):
        super(Blew,self).__init__()
        self.setWindowModality(Qt.NonModal)
        self.setWindowFlags(Qt.FramelessWindowHint) # Qt.Tool | Qt.FramelessWindowHint

        l = QHBoxLayout()
        self.items_view= QTableView()

        # Make the dropdown nice
        l.setContentsMargins(0,0,0,0)
        self.items_view.horizontalHeader().setStretchLastSection(True)
        self.items_view.horizontalHeader().hide()
        self.items_view.verticalHeader().hide()
        self.items_view.setShowGrid(False)
        self.setMinimumSize(300,100)

        self.model = QuickComboModel(self)
        self.items_view.setModel(self.model)
        l.addWidget(self.items_view)
        self.setLayout(l)


    def get_current_completion(self):
        """ Get the currently selected completion """
        return self.items_view.currentIndex().data()

    @Slot(list)
    def set_possible_completions(self,completions):
        if completions:
            self.model.buildModelFromArray(completions)
            # self.show()
        else:
            self.model.clear()
            self.hide()

    completion_discarded = Signal()

    def keyPressEvent(self,event):
        if event.key() == Qt.Key_Escape:
            event.ignore()
            self.hide()
            self.completion_discarded.emit()

        return super(Blew,self).keyPressEvent(event)



class MyLineEdit(QLineEdit):
    def __init__(self):
        super(MyLineEdit,self).__init__()
        self.completion = Blew()

        self.completion.items_view.activated.connect(self.completion_selected)
        self.completion.completion_discarded.connect(self.completion_discarded)

        # self.completer = QCompleter(["alpha","bravo"])
        # self.setCompleter(self.completer)


        self.error_shown = False

    def show_error(self):
        self.error_shown = True

        palette = self.palette()
        palette.setColor(QPalette.Base, QColor(255,0,255))
        self.setPalette(palette)

    def show_success(self):
        self.error = False

        palette = self.palette()
        palette.setColor(QPalette.Base, QColor(255,255,255))
        self.setPalette(palette)


    @Slot()
    def completion_discarded(self):
        # Transfer the focus from the completion list to
        # self.

        self.completion.hide()
        self.activateWindow()
        self.setFocus(Qt.OtherFocusReason)

    @Slot(QModelIndex)
    def completion_selected(self,ndx):
        self.completion.hide()
        self.activateWindow()
        self.setFocus(Qt.OtherFocusReason)

        t = self.text()
        cp = self.cursorPosition()
        w,start,end = word_at_point(self.text(), cp)

        action,start,end  = self.replacement_area

        completion = self.completion.get_current_completion()
        if self.quote:
            completion = u"\"{}\"".format(completion)

        completion = u" {} ".format(completion)

        if action == 'rep':
            mainlog.debug("Replacing {} in |{}|={} [{},{}] by {}".format(w,t,self.cursorPosition(),start,end,self.completion.get_current_completion()))

            t_start = (t[0:start] + completion).lstrip()
            t_end = t[end+1:len(t)]
            cp = len(t_start)
            t = t_start + t_end
        else:
            t_start = (t[0:start] + u" " + completion + u" ").lstrip()
            t_end =  t[end+1:len(t)]
            cp = len(t_start)
            t = t_start + t_end

        self.setText( t)
        self.setCursorPosition(cp)


    def cursorPos(self):
        return self.cursorRect().topLeft()

    def _show_completion(self):
        replacement_area,suggestions,quote = find_suggestions(self.text(),
                                                              self.cursorPosition())

        if suggestions:
            # mainlog.debug("Suggestions are ..." + str(suggestions))

            self.replacement_area = replacement_area
            self.quote = quote

            p = self.mapToGlobal(QPoint(self.cursorPos().x(),
                                        self.height()))
            self.completion.set_possible_completions(suggestions)
            self.completion.move(p)

            self.completion.activateWindow() # So that show works
            self.completion.show()
            self.completion.raise_()

            self.completion.items_view.setFocus(Qt.OtherFocusReason)
            self.completion.items_view.setCurrentIndex(self.completion.model.index(0,0))
        else:
            self.replacement_area = None
            self.quote = False
            self.completion.set_possible_completions(None)
            self.completion.hide()

        # self.activateWindow()
        self.setFocus(Qt.OtherFocusReason)

        return suggestions

    def keyPressEvent(self,event):
        if event.key() == Qt.Key_Down:
            self._show_completion()
            event.ignore()
            # if self.completion.model.rowCount() > 0:
            #     self.completion.activateWindow()
            #     self.completion.show()
            #     self.completion.raise_()
            #     self.completion.items_view.setFocus(Qt.OtherFocusReason)
            #     self.completion.items_view.setCurrentIndex(self.completion.model.index(0,0))
            #     mainlog.debug("Key down")
            #     event.ignore()
            return super(MyLineEdit,self).keyPressEvent(event)
        else:
            return super(MyLineEdit,self).keyPressEvent(event)



# class MyLineEdit(QWidget):
#     def __init__(self):
#         super(MyLineEdit,self).__init()
#         l = QHBoxLayout()
#         l.addWidget(QLineEdit())
#         self.setLayout(l)




if __name__ == "__main__":
    from koi.junkyard.services import services
    employee = services.employees.any()
    user_session.open(employee)

    app = QApplication(sys.argv)

    window = QMainWindow()
    window.setMinimumSize(1024,768)
    widget = OrderOverviewWidget(window,None,None)
    widget.refresh_action()
    window.setCentralWidget(widget)
    window.show()


    # presence.refresh_action()

    app.exec_()
