from functools import cmp_to_key

from PySide.QtCore import Qt,Slot,QModelIndex,QPoint,Signal
from PySide.QtGui import QHBoxLayout,QVBoxLayout, QAbstractItemView,QHeaderView, QMenu, QAction, QBrush,QColor, QItemSelectionModel, QItemSelection

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

from koi.Configurator import configuration
from koi.dao import dao
from koi.db_mapping import FilterQuery

from koi.gui.dialog_utils import makeErrorBox, TitleWidget, NavBar,populate_menu,SubFrame

from koi.Configurator import mainlog
from koi.reporting.delivery_slip_report import print_delivery_slip
from koi.delivery_slips.DeliverySlipView import DeliverySlipViewWidget

from koi.gui.PrototypedModelView import PrototypedModelView, PrototypedQuickView

from koi.gui.ProxyModel import IntegerNumberPrototype,DatePrototype,TextLinePrototype
from koi.gui.dialog_utils import showErrorBox
from koi.gui.horse_panel import HorsePanel
from koi.gui.PersistentFilter import PersistentFilter
from koi.datalayer.delivery_slip_query_parser import suggestion_finder, initialize_customer_cache
from koi.datalayer.data_exception import DataException

class DeliverySlipPanelModel(PrototypedModelView):
    def __init__(self,prototype,parent):
        super(DeliverySlipPanelModel,self).__init__(prototype,parent)
        self.deactivated_brush = QBrush(Qt.green)

    def data(self, index, role):

        if role in (Qt.ForegroundRole, Qt.TextColorRole):
            r = index.row()
            if r >= 0 and r < self.rowCount() and not self.objects[r].active:
                return QColor(192,192,192)
            else:
                return None
        else:
            return super(DeliverySlipPanelModel,self).data(index,role)


class DeliverySlipPanel(HorsePanel):

    delivery_slip_changed = Signal()

    def close_panel(self):
        self.filter_widget.remember_current_selection( configuration)

    def _selected_slip(self):
        cur_ndx = self.search_results_view.currentIndex()
        if cur_ndx.row() >= 0:
            return cur_ndx.model().object_at(cur_ndx.row())
        return None

    def reprint(self):
        cur_ndx = self.search_results_view.currentIndex()
        slip_id = cur_ndx.model().index(cur_ndx.row(),0).data()

        if dao.delivery_slip_part_dao.id_exists(slip_id):
            print_delivery_slip(dao,slip_id)
        else:
            makeErrorBox(_("The delivery slip {} doesn't exist").format(slip_id)).exec_()

    def desactivate(self):
        slip_id = self._selected_slip().delivery_slip_id
        mainlog.debug("Desactivate slip {}".format(slip_id))
        dao.delivery_slip_part_dao.deactivate(slip_id)
        self.refresh(slip_id)
        self.delivery_slip_changed.emit()

    def activate(self):
        slip_id = self._selected_slip().delivery_slip_id
        dao.delivery_slip_part_dao.activate(slip_id)
        self.refresh(slip_id)
        self.delivery_slip_changed.emit()

    def delete(self):
        slip_id = self._selected_slip().delivery_slip_id
        dao.delivery_slip_part_dao.delete_last(slip_id)
        self.refresh(slip_id)
        self.delivery_slip_changed.emit()

    @Slot()
    def show_actions(self):
        button = self.action_menu.parent()
        p = button.mapToGlobal(QPoint(0,button.height()))
        self.action_menu.exec_(p)

    @Slot()
    def _toggle_edit_filters(self):
        self.filter_widget.setVisible( not self.filter_widget.isVisible())

    def __init__(self,parent):
        super(DeliverySlipPanel,self).__init__(parent)

        title = _("Delivery slips")

        self.slip_data = None

        self.set_panel_title(_("Delivery slip overview"))
        self.reprint_delivery_slip = QAction(_("Reprint delivery slip"),self) # , parent
        self.reprint_delivery_slip.triggered.connect( self.reprint)
        # self.reprint_delivery_slip.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_V))
        self.reprint_delivery_slip.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        # self.controller_operation.view.addAction(self.reprint_delivery_slip)


        self.desactivate_delivery_slip = QAction(_("Desactivate delivery slip"),self) # , parent
        self.desactivate_delivery_slip.triggered.connect( self.desactivate)
        self.desactivate_delivery_slip.setShortcutContext(Qt.WidgetWithChildrenShortcut)

        self.activate_delivery_slip = QAction(_("Activate delivery slip"),self) # , parent
        self.activate_delivery_slip.triggered.connect( self.activate)
        self.activate_delivery_slip.setShortcutContext(Qt.WidgetWithChildrenShortcut)

        self.delete_delivery_slip = QAction(_("Delete delivery slip"),self) # , parent
        self.delete_delivery_slip.triggered.connect( self.delete)
        self.delete_delivery_slip.setShortcutContext(Qt.WidgetWithChildrenShortcut)


        filter_family = FilterQuery.DELIVERY_SLIPS_FAMILY
        self.filter_widget = PersistentFilter( filter_family, suggestion_finder)
        self.filter_widget.apply_filter.connect(self.apply_filter_slot)
        self.filter_widget.hide()

        navigation = NavBar( self,
                             [ (self.filter_widget.get_filters_combo(), None),
                               (_("Edit filter"),self._toggle_edit_filters),
                               (_("Action"),self.show_actions) ] )

        self.title_widget = TitleWidget(title, self, navigation) # navigation)


        self.action_menu = QMenu(navigation.buttons[0])
        list_actions = [ (self.reprint_delivery_slip,None),
                         (self.activate_delivery_slip,None),
                         (self.desactivate_delivery_slip,None),
                         # (self.delete_delivery_slip,None)
        ]
        populate_menu(self.action_menu, self, list_actions, context=Qt.WidgetWithChildrenShortcut)

        # self.setWindowTitle(title)


        top_layout = QVBoxLayout(self)

        # self.filter_line_edit = QLineEdit()

        # self.filter_line_edit = QueryLineEdit(suggestion_finder)
        initialize_customer_cache() # FIXME Not the place to do that

        # filter_family = 'delivery_slips'
        # self.filter_name = FiltersCombo(self, filter_family)
        # filter_widget = PersistentFilter(filter_family, self.filter_name)
        # filter_widget.apply_filter.connect(self.apply_filter_slot)

        self.proto = []
        self.proto.append( IntegerNumberPrototype('delivery_slip_id',_("Slip Nr"), editable=False))
        self.proto.append( DatePrototype('creation',_('Date'), editable=False))
        self.proto.append( TextLinePrototype('fullname',_('Customer'), editable=False))
        self.proto.append( TextLinePrototype('user_label',_('Order'), editable=False))

        self.search_results_model = DeliverySlipPanelModel(self.proto, self)
        self.search_results_view = PrototypedQuickView(self.proto, self)
        self.search_results_view.setModel(self.search_results_model)


        self.search_results_view.verticalHeader().hide()
        self.search_results_view.horizontalHeader().setResizeMode(1, QHeaderView.ResizeToContents)
        self.search_results_view.horizontalHeader().setResizeMode(2, QHeaderView.Stretch)
        self.search_results_view.horizontalHeader().setSortIndicatorShown(True)
        self.search_results_view.horizontalHeader().setSortIndicator(0,Qt.AscendingOrder)
        self.search_results_view.horizontalHeader().sectionClicked.connect(self._section_clicked)
        self.search_results_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.search_results_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.search_results_view.selectionModel().currentRowChanged.connect(self.row_selected)

        self.slip_part_view = DeliverySlipViewWidget(self)

        hlayout_results = QHBoxLayout()
        # w = SubFrame(_("Delivery slips"),self.search_results_view,None)
        hlayout_results.addWidget(self.search_results_view)
        w = SubFrame(_("Detail"),self.slip_part_view,None)
        hlayout_results.addWidget(w)

        top_layout.addWidget(self.title_widget)
        top_layout.addWidget(self.filter_widget)
        top_layout.addLayout(hlayout_results)
        top_layout.setStretch(2,100)
        self.setLayout(top_layout)

        self.filter_widget.load_last_filter( configuration)



    def refresh(self,slip_id):
        filter_string = self.filter_line_edit.text()
        self.apply_filter_slot(filter_string)

        if slip_id:
            ndx = self.search_results_model.find_index( lambda s:s.delivery_slip_id == slip_id)

            r = 0
            m = self.search_results_model
            if ndx:
                r = ndx.row()

            s = QItemSelection(m.index(r,0), m.index(r, m.columnCount()-1))
            self.search_results_view.selectionModel().select(s, QItemSelectionModel.Select)

    @Slot(int)
    def _section_clicked(self,logical_ndx):
        self.refresh_action()

    @Slot(str)
    def apply_filter_slot(self, filter_string):
        if filter_string:
            try:
                self.slip_data = dao.delivery_slip_part_dao.load_slip_parts_on_filter(filter_string)
            except DataException as de:
                if de.code == DataException.CRITERIA_IS_EMPTY:
                    showErrorBox(_("Error in the filter !"),_("The filter can't be empty"),object_name="filter_is_empty")
                elif de.code == DataException.CRITERIA_IS_TOO_SHORT:
                    showErrorBox(_("Error in the filter !"),_("The filter is too short"),object_name="filter_is_too_short")
                elif de.code == DataException.CRITERIA_IS_TOO_LONG:
                    showErrorBox(_("Error in the filter !"),_("The filter is too long"),object_name="filter_is_too_long")
                return
        else:
            self.slip_data = dao.delivery_slip_part_dao.find_recent2(1000)
        self.refresh_action()


    def refresh_action(self):

        if self.slip_data == None:
            self.slip_data = dao.delivery_slip_part_dao.find_recent2(1000)

        data = self.slip_data
        headers = self.search_results_view.horizontalHeader()
        section_sorted = headers.sortIndicatorSection()
        sort_criteria = self._get_sort_criteria( section_sorted)
        sort_order = None

        if sort_criteria:
            sort_order = headers.sortIndicatorOrder()
            data = sorted(data, key=cmp_to_key(sort_criteria), reverse = sort_order == Qt.DescendingOrder)

        self.search_results_model.buildModelFromObjects(data)

        if sort_criteria:
            # Changing the model removes the sort order (which makes sense because
            # changing the model may alter the order of rows)
            headers.setSortIndicator(section_sorted,sort_order)

        self.search_results_view.setFocus(Qt.OtherFocusReason)


    @Slot(QModelIndex,QModelIndex)
    def row_selected(self,cur_ndx,prev_ndx):
        if cur_ndx.model():
            slip = cur_ndx.model().object_at( cur_ndx.row())
            if slip:
                slip_id = slip.delivery_slip_id
                self.slip_part_view.set_delivery_slip_parts(dao.delivery_slip_part_dao.load_slip_parts_frozen(slip_id))

                self.activate_delivery_slip.setEnabled( not slip.active)
                self.desactivate_delivery_slip.setEnabled( slip.active)
                self.delete_delivery_slip.setEnabled( cur_ndx.row() == 0)
                return

        self.slip_part_view.set_delivery_slip_parts(None)

    SECTION_SLIP_ID = 0
    SECTION_CREATION_DATE = 1
    SECTION_CUSTOMER = 2
    SECTION_ORDER_LABEL = 3


    def _get_sort_criteria(self,section_sorted):
        sort_criteria = None

        # True if the parts of the order stay grouped
        # together in the table
        order_stay_together = True

        if section_sorted == self.SECTION_CUSTOMER: # Customer
            sort_criteria = lambda a,b: cmp(a.fullname, b.fullname) or \
                            cmp(a.delivery_slip_id,b.delivery_slip_id)
        elif section_sorted == self.SECTION_CREATION_DATE:
            sort_criteria = lambda a,b: cmp(a.creation or date(2100,1,1), b.creation or date(2100,1,1))
        elif section_sorted == self.SECTION_SLIP_ID:
            sort_criteria = lambda a,b: cmp(a.delivery_slip_id, b.delivery_slip_id)
        elif section_sorted == self.SECTION_ORDER_LABEL:
            sort_criteria = lambda a,b: cmp(a.user_label, b.user_label)
        else:
            sort_criteria = None

        if sort_criteria is not None:
            self.current_sort_criteria = sort_criteria
        else:
            sort_criteria = self.current_sort_criteria

        return sort_criteria




if __name__ == "__main__":

    from PySide.QtGui import QApplication, QMainWindow

    app = QApplication(sys.argv)
    mw = QMainWindow()
    mw.setMinimumSize(1024,768)

    widget = DeliverySlipPanel(mw)

    # widget.edit_new_order(dao.customer_dao.all()[1])
    mw.setCentralWidget(widget)
    mw.show()

    app.exec_()
