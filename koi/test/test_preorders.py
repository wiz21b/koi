import unittest
from unittest import skip

from PySide.QtGui import QApplication,QMainWindow
from PySide.QtTest import QTest
from PySide.QtCore import Qt


from koi.test.test_base import TestBase

from PySide.QtGui import QDropEvent
from PySide.QtCore import QPoint, QMimeData, QUrl
import tempfile

from koi.dao import *
from koi.EditOrderParts import EditOrderPartsWidget,operation_definition_cache
from koi.OrderOverview import OrderOverviewWidget

from PySide.QtGui import QDropEvent, QDragEnterEvent
from koi.charts.indicators_service import indicators_service


class EditOrderTestBase(TestBase):
    @classmethod
    def setUpClass(cls):
        super(EditOrderTestBase,cls).setUpClass()

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        # Fix issues with combo box that gets cleared too fast
        app.setEffectEnabled(Qt.UI_AnimateCombo, False)
        cls.app = app

        operation_definition_cache.reload()
        cls.mw = QMainWindow()
        cls.mw.setMinimumSize(1024,768)
        cls.widget = EditOrderPartsWidget(None, None, True, cls.remote_documents_service)
        cls.order_overview_widget = OrderOverviewWidget(None,None,
                                                        None,
                                                        True)

        cls.temp_dir = tempfile.TemporaryDirectory("horse_doc_mgr")
        configuration.set("DocumentsDatabase","documents_root",cls.temp_dir.name)


        cls.mw.setCentralWidget(cls.widget)
        cls.mw.show()
        QTest.qWaitForWindowShown(cls.mw)
        cls.app.processEvents()

    @classmethod
    def tearDownClass(cls):
        # cls.mw.setCentralWidget(None)
        cls.mw.close()
        cls.widget.close()
        cls.app.processEvents()
        # cls.widget.deleteLater()
        # cls.mw.deleteLater()
        cls.app.processEvents()
        cls.app.closeAllWindows()
        # cls.app.exit()
        cls.app = None

    def setUp(self):
        super(EditOrderTestBase,self).setUp()
        operation_definition_cache.reload()


    def _encode_imputable_operation(self,description="Description op 1, TOurnage", pause=False):
        widget = self.widget
        app = self.app

        widget.controller_operation.view.setFocus(Qt.OtherFocusReason)


        mainlog.debug("*** Activating operation selection")

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Down) # modifier, delay
        app.processEvents()

        # Operation defintion
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_T) # modifier, delay
        app.processEvents()
        ed = app.focusWidget()
        for i in range(10000):
            app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_O) # modifier, delay
        app.processEvents()

        if pause:
            app.exec_()

        mainlog.debug("*** Selecting operation selection")

        for i in range(10000):
            app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()
        for i in range(10000):
            app.processEvents()

        mainlog.debug("*** Entering description")
        mainlog.debug(app.focusWidget())
        # Operation's description
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_8) # modifier, delay
        app.processEvents()
        print(app.focusWidget())
        QTest.keyClicks(app.focusWidget(), description) # modifier, delay
        print(app.focusWidget())
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Uacute) # modifier, delay
        app.processEvents()

        mainlog.debug("*** hitting enter")
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()
        mainlog.debug(app.focusWidget())

        mainlog.debug("*** entering number of hours")

        # Value/price (skipped because TO is not a fixed price)

        # Number of hours
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_8) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()

        # Leave auto edit to give focus back to parent
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Escape) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Escape) # modifier, delay
        app.processEvents()
        app.processEvents()

    def _encode_not_imputable_operation(self):
        widget = self.widget
        app = self.app

        widget.controller_operation.view.setFocus(Qt.OtherFocusReason)
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Down) # modifier, delay

        # Operation defintion
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_M) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_A) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()

        # Operation's description
        QTest.keyClicks(app.focusWidget(), "Not imputable task") # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Uacute) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()

        # Value/price

        QTest.keyClicks(app.focusWidget(), "123.66") # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()

        # Number of hours (skipped because TO is not a fixed price)

        # Leave auto edit to give focus back to parent
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Escape) # modifier, delay
        app.processEvents()
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Escape) # modifier, delay
        app.processEvents()
        app.processEvents()


    def _make_basic_preorder(self):
        app = self.app
        widget = self.widget
        mw = self.mw

        widget.edit_new_order(self.customer.customer_id)


        widget.customer_order_name.setText(u"AKZO123"+ chr(233))

        QTest.keyEvent(QTest.Click, widget.controller_part.view, Qt.Key_Down) # modifier, delay
        app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_1) # modifier, delay
        app.processEvents()
        QTest.keyClicks(app.focusWidget(), "Order part one") # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Uacute) # modifier, delay
        app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_1) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_0) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()
        app.processEvents()

        # deadline
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Tab) # modifier, delay
        app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_1) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_1) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_1) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()

        self._encode_imputable_operation()

        # Leave auto edit to give focus back to parent
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Escape) # modifier, delay
        app.processEvents()
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Escape) # modifier, delay
        app.processEvents()
        app.processEvents()


    def _fill_order_part(self,description):
        app = self.app

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_0) # modifier, delay
        app.processEvents()
        QTest.keyClicks(app.focusWidget(), description) # modifier, delay

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_9) # modifier, delay
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()

        # deadline
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Tab) # modifier, delay
        app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_1) # modifier, delay
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()


    def edit_new_order(self, customer_id):
        """  Edit a new order, for a given customer
        :param customer_id:
        :return:
        """
        self.widget.edit_new_order(self.customer_id)
        self.widget.controller_part.view.setFocus(Qt.OtherFocusReason)

    def save(self):
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        self.app.processEvents()


    def pause(self):
        self.app.exec_()

class TestPreorders(EditOrderTestBase):

    def test_basic_preorder(self):

        app = self.app
        widget = self.widget
        mw = self.mw

        widget.edit_new_order(self.customer_id)
        self.save()
        order = dao.order_dao.find_by_id(widget._current_order.order_id)

        self.assertEqual(None, order.sent_as_preorder, "Estimate was not sent, so no date")
        self.assertEqual(OrderStatusType.preorder_definition, order.state, "Defaut state should be preoder_definition")


    def test_preorder_sent(self):

        self.widget.edit_new_order(self.customer_id)
        self.widget._set_state(OrderStatusType.preorder_sent)
        self.save()
        order = dao.order_dao.find_by_id(self.widget._current_order.order_id)

        self.assertEqual(date.today(), order.sent_as_preorder)
        self.assertEqual(OrderStatusType.preorder_sent, order.state)


    def test_preorder_then_preorder_sent(self):

        self.widget.edit_new_order(self.customer_id)
        self.save()

        self.widget._set_state(OrderStatusType.preorder_sent)
        self.save()
        order = dao.order_dao.find_by_id(self.widget._current_order.order_id)

        self.assertEqual(date.today(), order.sent_as_preorder)
        self.assertEqual(OrderStatusType.preorder_sent, order.state)

    def test_preorder_then_preorder_sent(self):

        self.widget.edit_new_order(self.customer_id)
        self.widget._set_state(OrderStatusType.order_ready_for_production)
        self.prepare_to_click_dialog("confirm_estimate")
        self.save()

        order = dao.order_dao.find_by_id(self.widget._current_order.order_id)

        self.assertEqual(None, order.sent_as_preorder)
        self.assertEqual(OrderStatusType.order_ready_for_production, order.state)


    def test_preorder_then_preorder_not_sent(self):

        self.widget.edit_new_order(self.customer_id)
        self.save()

        self.widget._set_state(OrderStatusType.order_ready_for_production)
        self.prepare_to_click_dialog("confirm_estimate_sent")
        self.save()

        order = dao.order_dao.find_by_id(self.widget._current_order.order_id)

        self.assertEqual(None, order.sent_as_preorder)
        self.assertEqual(OrderStatusType.order_ready_for_production, order.state)

    def test_indicator(self):
        self._make_basic_preorder()
        self.save()
        # self.pause()
        ret = indicators_service.preorder_parts_value_chart()

        self.assertEqual([[0.0,0.0,0.0]], ret.data, "Preorder definition is not sent to the custmoer, so it is not to be reported")

        self.widget._set_state(OrderStatusType.preorder_sent)
        self.save()
        # self.pause()

        # Disable the cache while testing
        indicators_service.clear_caches()

        ret = indicators_service.preorder_parts_value_chart()
        self.assertEqual([[0.0,0.0,1110.0]], ret.data)


if __name__ == "__main__":
    unittest.main()
