#noinspection PyUnresolvedReferences
import sys


from datetime import date
from functools import cmp_to_key

# from pubsub import pub
from PySide.QtCore import Qt,Slot,QModelIndex,QPoint,Signal
from PySide.QtGui import QHBoxLayout,QVBoxLayout, QLabel, QAbstractItemView,QHeaderView, QItemSelectionModel, QTextEdit


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

from koi.gui.dialog_utils import showErrorBox, TitleWidget, SubFrame,showWarningBox, NavBar

from koi.Configurator import mainlog, configuration
from koi.translators import date_to_s

from koi.gui.PrototypedModelView import PrototypedModelView, PrototypedQuickView

from koi.gui.ProxyModel import DatePrototype,TextLinePrototype,FloatNumberPrototype
from koi.gui.horse_panel import HorsePanel
from koi.gui.PersistentFilter import PersistentFilter, FiltersCombo
from koi.datalayer.supply_order_service import supply_order_service
from koi.datalayer.supply_order_query_parser import check_parse, initialize_supplier_cache
from koi.QueryLineEdit import QueryLineEdit
from koi.db_mapping import FilterQuery


class SupplyOrderOverview(HorsePanel):

    def close_panel(self):
        self.filter_widget.remember_current_selection( configuration)

    def _selected_supply_order_part(self):
        cur_ndx = self.search_results_view.currentIndex()
        if cur_ndx.row() >= 0:
            return cur_ndx.model().object_at(cur_ndx.row())
        return None

    @Slot()
    def show_actions(self):
        button = self.action_menu.parent()
        p = button.mapToGlobal(QPoint(0,button.height()))
        self.action_menu.exec_(p)


    SECTION_REFERENCE = 0
    SECTION_SUPPLIER = 1
    SECTION_DEADLINE = 2
    SECTION_DESCRIPTION = 3
    SECTION_CREATION_DATE = 6

    def _make_sort_criteria(self, section_sorted, sort_order):

        sort_criteria = None

        if section_sorted == self.SECTION_REFERENCE:
            if sort_order == Qt.AscendingOrder:
                def ordering_key(p):
                    return p.accounting_label * 1000 + p.position
                sort_criteria = lambda a,b: cmp(ordering_key(a), ordering_key(b))
            else:
                def ordering_key(p):
                    return p.accounting_label * 1000 + 999-p.position
                sort_criteria = lambda a,b: cmp(ordering_key(a), ordering_key(b))
        elif section_sorted == self.SECTION_SUPPLIER:
            order_correction = +1
            if sort_order == Qt.DescendingOrder:
                order_correction = -1

            sort_criteria = lambda a,b: cmp(a.supplier_fullname, b.supplier_fullname) or \
                            cmp(a.accounting_label,b.accounting_label) or order_correction * cmp(a.position,b.position)
        elif section_sorted == self.SECTION_DEADLINE: # Deadline
            sort_criteria = lambda a,b: cmp(a.expected_delivery_date or date(2100,1,1),b.expected_delivery_date or date(2100,1,1))

        return sort_criteria


    def _fill_model(self, parts_data = None):
        """ Refills the list of parts data with given parts
        data. If no parts data are given, then the last
        data set is reused.

        This thake into account the currently selected sort
        indicator and, if any, the currently selected filter.
        """

        if parts_data is not None:
            self.parts_data = parts_data
        else:
            parts_data = self.parts_data

        view = self.search_results_view
        model = self.search_results_model
        headers = view.horizontalHeader()
        sort_order = headers.sortIndicatorOrder()
        section_sorted = headers.sortIndicatorSection()

        sort_criteria = self._make_sort_criteria(section_sorted, sort_order)
        if sort_criteria:
            sort_order = headers.sortIndicatorOrder()

            if sys.version[0] == '3':
                parts_data = sorted(parts_data, key=cmp_to_key(sort_criteria), reverse = sort_order == Qt.DescendingOrder)
            else:
                parts_data = sorted(parts_data, sort_criteria, reverse = sort_order == Qt.DescendingOrder)


        model.buildModelFromObjects(parts_data)

        if sort_criteria:
            # Changing the model removes the sort order (which makes sense because
            # changing the model may alter the order of rows)
            # => I have to reset it
            headers.setSortIndicator(section_sorted,sort_order)

        if len(parts_data) == 0:
            # Must do this because when the model is empty
            # the slection is not updated, so no signal
            # is sent
            self._fill_order_part_detail(None)
        else:
            view.selectionModel().reset()
            view.selectionModel().select( view.model().index(0,0), QItemSelectionModel.Select | QItemSelectionModel.Rows)

        view.horizontalHeader().setResizeMode(self.SECTION_DESCRIPTION,QHeaderView.Stretch)


    @Slot()
    def refresh_action(self):
        mainlog.debug("refresh_action")
        self._apply_filter(self.filter_widget.current_filter())

    @Slot(int)
    def section_clicked(self,logical_ndx):
        self._fill_model()

    @Slot(str)
    def _apply_filter(self, filter_text):
        mainlog.debug(u"_apply_filter : {}".format(filter_text))

        parts = []
        len_check = False

        if " " in filter_text.strip():
            # More than one word in the filter => I assume it's the full
            # fledged filtering

            check = check_parse(filter_text)
            if check == True:
                parts = supply_order_service.find_parts_expression_filter(filter_text)
                len_check = True
            else:
                showErrorBox(_("Error in the filter !"),check,object_name="filter_is_wrong")

        elif filter_text:
            parts = supply_order_service.find_parts_filtered(filter_text)
            len_check = True
        else:
            parts = supply_order_service.find_recent_parts()
            len_check = False

        if len_check and len(parts) >= supply_order_service.MAX_RESULTS:
            showWarningBox(_("Too many results"),_("The query you've given brought back too many results. Only a part of them is displayed. Consider refining your query"))
        self._fill_model( parts)
        self.search_results_view.setFocus(Qt.OtherFocusReason)




    def _make_supply_order_detail_view(self):

        # There's a self.proto somewhere, don't mess with it :-)

        # proto = []
        # proto.append( TextLinePrototype('description',_('Description'), editable=True,nullable=False))
        # proto.append( FloatNumberPrototype('quantity',_('Quantity'), editable=True,nullable=False))
        # proto.append( FloatNumberPrototype('unit_price',_('Unit price'), editable=True,nullable=False))

        # self.detail_model = PrototypedModelView(proto, self)
        # self.detail_view = PrototypedQuickView(proto, self)
        # self.detail_view.setModel(self.detail_model)
        # self.detail_view.verticalHeader().hide()

        self.detail_description = QTextEdit()
        self.detail_description.setTextInteractionFlags (Qt.TextBrowserInteraction)


        self.delivery_date_widget = QLabel()
        self.creation_date_widget = QLabel()
        self.supplier_reference_widget = QLabel()

        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel(_("Delivery date")))
        hlayout.addWidget(self.delivery_date_widget)
        hlayout.addStretch()

        hlayout3 = QHBoxLayout()
        hlayout3.addWidget(QLabel(_("Creation date")))
        hlayout3.addWidget(self.creation_date_widget)
        hlayout3.addStretch()

        hlayout2 = QHBoxLayout()
        hlayout2.addWidget(QLabel(_("Supplier's reference")))
        hlayout2.addWidget(self.supplier_reference_widget)
        hlayout2.addStretch()


        layout = QVBoxLayout()
        layout.addLayout(hlayout)
        layout.addLayout(hlayout3)
        layout.addLayout(hlayout2)
        layout.addWidget(self.detail_description)
        layout.addStretch()

        # layout.addWidget(self.detail_view)
        # layout.setStretch(0,1)
        # layout.setStretch(1,3)


        return layout


    @Slot()
    def _toggle_edit_filters(self):
        self.filter_widget.setVisible( not self.filter_widget.isVisible())

    def __init__(self,parent):
        super(SupplyOrderOverview,self).__init__(parent)

        initialize_supplier_cache()

        self.set_panel_title( _("Supply Orders"))

        # navigation = NavBar( self,
        #                      [ (_("Action"),self.show_actions) ] )
        # self.action_menu = QMenu(navigation.buttons[0])


        title = _("Supply orders")
        # self.setWindowTitle(title)



        filter_family = FilterQuery.SUPPLIER_ORDER_SLIPS_FAMILY
        self.filter_widget = PersistentFilter( filter_family)
        self.filter_widget.apply_filter.connect(self._apply_filter)
        self.filter_widget.hide()


        self.proto = []
        self.proto.append( TextLinePrototype('human_identifier',_("Part Nr"), editable=False))
        self.proto.append( TextLinePrototype('supplier_fullname',_('Supplier'), editable=False))
        self.proto.append( DatePrototype('expected_delivery_date',_('Deadline'), editable=True,nullable=False))
        self.proto.append( TextLinePrototype('description',_('Description'), editable=True,nullable=False))
        self.proto.append( FloatNumberPrototype('quantity',_('Quantity'), editable=True,nullable=False))
        self.proto.append( FloatNumberPrototype('unit_price',_('Unit price'), editable=True,nullable=False))
        self.proto.append( DatePrototype('creation_date',_('Creation date'), editable=False,nullable=False))

        # self.proto.append( DatePrototype('creation_date',_('Creation'), editable=False))
        # self.proto.append( DatePrototype('expected_delivery_date',_('Expected\ndelivery'), editable=False))
        # self.proto.append( TextLinePrototype('supplier_fullname',_('Supplier'), editable=False))

        self.search_results_model = PrototypedModelView(self.proto, self)
        self.search_results_view = PrototypedQuickView(self.proto, self)
        self.search_results_view.setModel(self.search_results_model)
        self.search_results_view.horizontalHeader().setSortIndicatorShown(True)


        self.search_results_view.verticalHeader().hide()
        self.search_results_view.verticalHeader().setResizeMode(QHeaderView.ResizeToContents)
        self.search_results_view.doubleClicked.connect(self._supply_order_double_clicked)
        self.search_results_view.activated.connect(self._supply_order_double_clicked)
        self.search_results_view.horizontalHeader().sectionClicked.connect(self.section_clicked)

        top_layout = QVBoxLayout(self)


        navigation = NavBar( self,
                             [ (self.filter_widget.get_filters_combo(), None),
                               (_("Edit filter"),self._toggle_edit_filters)
                             ] )

        self.title_widget = TitleWidget(title, self, navigation) # navigation)

        hlayout_results = QHBoxLayout()
        # w = SubFrame(_("Supply order parts"),self.search_results_view,None)
        hlayout_results.addWidget( self.search_results_view)

        w = SubFrame(_("Supply order detail"),self._make_supply_order_detail_view(),None)
        hlayout_results.addWidget(w)

        hlayout_results.setStretch(0,2)
        hlayout_results.setStretch(0,1)

        top_layout.addWidget(self.title_widget)
        top_layout.addWidget(self.filter_widget)
        top_layout.addLayout(hlayout_results)
        top_layout.setStretch(3,100)
        self.setLayout(top_layout)

        self.search_results_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.search_results_view.setSelectionMode(QAbstractItemView.SingleSelection)

        # self.search_results_view.activated.connect(self.row_activated)
        self.search_results_view.selectionModel().currentRowChanged.connect(self.row_selected)
        # self.detail_view.doubleClicked.connect(self._supply_order_double_clicked)

        # pub.subscribe(self.refresh_panel, 'supply_order.changed')
        # pub.subscribe(self.refresh_panel, 'supply_order.deleted')
        # self.filter_widget.select_default_filter()
        self.filter_widget.load_last_filter( configuration)


    supply_order_selected = Signal(object)

    @Slot(QModelIndex)
    def _supply_order_double_clicked(self, cur_ndx):
        mainlog.debug("_supply_order_double_clicked")
        supply_order = cur_ndx.model().object_at( cur_ndx.row())
        if supply_order:
            self.supply_order_selected.emit(supply_order)


    def _fill_order_part_detail(self, supply_order_part):
        if supply_order_part:
            supply_order_part_id = supply_order_part.supply_order_id
            supply_order, parts = supply_order_service.find_by_id(supply_order_part.supply_order_id)
            self.detail_description.setText(supply_order.description)
            self.delivery_date_widget.setText(date_to_s(supply_order.expected_delivery_date) or "-")
            self.supplier_reference_widget.setText(supply_order.supplier_reference or "-")
            self.creation_date_widget.setText(date_to_s(supply_order.creation_date) or "-")
        else:
            self.detail_description.setText("-")
            self.delivery_date_widget.setText("-")
            self.supplier_reference_widget.setText("-")
            self.creation_date_widget.setText("-")


    @Slot(QModelIndex,QModelIndex)
    def row_selected(self,cur_ndx,prev_ndx):
        if cur_ndx.model():
            supply_order_part = cur_ndx.model().object_at( cur_ndx.row())
            self._fill_order_part_detail(supply_order_part)





if __name__ == "__main__":

    from PySide.QtGui import QApplication, QMainWindow

    app = QApplication(sys.argv)
    mw = QMainWindow()
    mw.setMinimumSize(1024,768)

    widget = SupplyOrderOverview(mw)
    widget.refresh_action()

    # widget.edit_new_order(dao.customer_dao.all()[1])
    mw.setCentralWidget(widget)
    mw.show()

    app.exec_()
