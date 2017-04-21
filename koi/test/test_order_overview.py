import unittest

from PySide.QtGui import QApplication,QMainWindow,QTabWidget,QContextMenuEvent
from PySide.QtTest import QTest
from PySide.QtCore import Qt,QTimer,Slot,QPoint

from koi.test.test_base import TestBase
from koi.db_mapping import *
from koi.dao import *

from koi.server.server import ClockServer,ServerException
from koi.OrderOverview import OrderOverviewWidget
from koi.OperationDefinitionsCache import operation_definition_cache



class TestOrderOverview(TestBase):

    @classmethod
    def setUpClass(cls):
        super(TestOrderOverview,cls).setUpClass()
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        # Fix issues with combo box that gets cleared too fast
        app.setEffectEnabled(Qt.UI_AnimateCombo, False)
        cls.app = app

        cls.mw = QMainWindow()
        cls.mw.setMinimumSize(1024,768)
        cls.order_overview_widget = OrderOverviewWidget(None,None,
                                                        None,
                                                        True)
        cls.mw.setCentralWidget(cls.order_overview_widget)
        cls.mw.show()

        # This is a big hack to select the "in production" order parts filter
        # on the overview. Without that, the "completed" order parts filter
        # is applied and no order parts gets shown :-(

        cls.order_overview_widget.persistent_filter.get_filters_combo().setCurrentIndex(1)
        QTest.qWaitForWindowShown(cls.mw)
        cls.app.processEvents()

    @classmethod
    def tearDownClass(cls):

        # cls.mw.setCentralWidget(None)
        cls.mw.close()
        cls.order_overview_widget.close()
        cls.app.processEvents()

        # cls.order_overview_widget.deleteLater()
        # cls.mw.deleteLater()
        cls.app.processEvents()
        cls.app.closeAllWindows()
        cls.app = None

    def setUp(self):
        super(TestOrderOverview,self).setUp()
        self._clear_database_content()
        operation_definition_cache.refresh()

    @Slot()
    def _click_context_menu(self):
        mainlog.debug("hello " * 100)

        active_widget = self.app.activePopupWidget()
        mainlog.debug(active_widget)
        # active_widget = self.app.focusWidget()
        mainlog.debug(active_widget)
        active_widget.setFocus()

        #QApplication.
        for i in range(10):
            self.app.processEvents()

        QTest.keyEvent(QTest.Click, active_widget, Qt.Key_Down) # enter menu
        for i in range(10):
            self.app.processEvents()
        QTest.keyEvent(QTest.Click, active_widget, Qt.Key_Down) # skip modify command
        self.app.processEvents()
        QTest.keyEvent(QTest.Click, active_widget, Qt.Key_Down) # Skip priority
        self.app.processEvents()

        import time
        for i in range(50):
            # time.sleep(0.1)
            self.app.processEvents()

        QTest.keyEvent(QTest.Click, active_widget, Qt.Key_Enter) # At this point we're on "order part -> aborted"
        self.app.processEvents()
        mainlog.debug("_click_context_menu : done")

    def test_change_order_part_state(self):
        order = self._make_order()

        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 2"
        order_part.position = 2
        self._order_part_dao.save(order_part)

        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 3"
        order_part.position = 3
        self._order_part_dao.save(order_part)

        self._order_dao.change_order_state(order.order_id,OrderStatusType.order_ready_for_production)

        # self.order_overview_widget.month_today()
        self.order_overview_widget.refresh_action()
        self.order_overview_widget.retake_focus()
        # self.app.exec_()

        # Select the first order part (we assume they are properly ordered)
        v = self.order_overview_widget.current_orders_overview.table_view
        v.setCurrentIndex( v.model().index(0,0))
        QTest.mouseMove(v)

        # QTest.mouseClick(self.order_overview_widget.current_orders_overview.table_view,
        #                  Qt.RightButton, delay=500)

        # self.order_overview_widget.current_orders_overview.popup_parts()


        timer = QTimer()
        timer.timeout.connect(self._click_context_menu)
        timer.setSingleShot(True)
        timer.start(1000)

        # I can't have the menu to popup using museClicks, so I
        # do it this way. FIXME Taht's not right because nothing prooves
        # that my context menu is shown on mouse clicks...
        self.app.sendEvent(self.order_overview_widget.current_orders_overview.table_view,
                           QContextMenuEvent(QContextMenuEvent.Keyboard, QPoint(10,10)))


        # self.app.exec_()


        order = self.order_dao.find_by_id(order.order_id)
        self.assertEqual(OrderPartStateType.aborted,              order.parts[0].state)
        self.assertEqual(OrderPartStateType.ready_for_production, order.parts[1].state)
        self.assertEqual(OrderPartStateType.ready_for_production, order.parts[2].state)


    def test_filter(self):
        order = self._make_order()
        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 2"
        order_part.position = 2
        self._order_part_dao.save(order_part)
        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 3"
        order_part.position = 3
        self._order_part_dao.save(order_part)

        self.order_overview_widget.persistent_filter.super_filter_entry.setText(u"Si"+ chr(233) + u"mens")
        QTest.keyEvent(QTest.Click, self.order_overview_widget.persistent_filter.super_filter_entry, Qt.Key_Enter)
        self.app.processEvents()

        self.assertEqual(3,self.order_overview_widget.current_orders_overview.table_view.model().rowCount())


        self.order_overview_widget.persistent_filter.super_filter_entry.setText("XXXXZZZZ")
        QTest.keyEvent(QTest.Click, self.order_overview_widget.persistent_filter.super_filter_entry, Qt.Key_Enter)
        self.app.processEvents()

        self.assertEqual(0,self.order_overview_widget.current_orders_overview.table_view.model().rowCount())


        self.order_overview_widget.persistent_filter.super_filter_entry.setText("")
        self.prepare_to_click_dialog("filter_is_empty")
        QTest.keyEvent(QTest.Click, self.order_overview_widget.persistent_filter.super_filter_entry, Qt.Key_Enter)
        self.wait_until_dialog_clicked()

        self.order_overview_widget.persistent_filter.super_filter_entry.setText("Z")
        self.prepare_to_click_dialog("filter_is_too_short")
        QTest.keyEvent(QTest.Click, self.order_overview_widget.persistent_filter.super_filter_entry, Qt.Key_Enter)
        self.wait_until_dialog_clicked()

        self.order_overview_widget.persistent_filter.super_filter_entry.setText("cli = zulu")
        self.prepare_to_click_dialog("filter_is_wrong")
        QTest.keyEvent(QTest.Click, self.order_overview_widget.persistent_filter.super_filter_entry, Qt.Key_Enter)
        self.wait_until_dialog_clicked()

if __name__ == "__main__":
    unittest.main()
