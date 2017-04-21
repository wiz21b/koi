import unittest

from PySide.QtCore import Qt
from PySide.QtGui import QApplication,QMainWindow,QHideEvent,QTableView
from PySide.QtTest import QTest



from koi.test.test_base import TestBase
from koi.db_mapping import *
from koi.dao import *


from koi.server.server import ClockServer,ServerException
from koi.BarCodeBase import BarCodeIdentifier
from koi.EditOrderParts import EditOrderPartsWidget,operation_definition_cache



class TestEditOrderPartsComputations(TestBase):

    @classmethod
    def setUpClass(cls):
        super(TestEditOrderPartsComputations,cls).setUpClass()
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        app.setEffectEnabled(Qt.UI_AnimateCombo, False)
        cls.app = app

        cls.mw = QMainWindow()
        cls.mw.setMinimumSize(1024,768)
        cls.widget = EditOrderPartsWidget(None,None,True,cls.remote_documents_service)
        cls.mw.setCentralWidget(cls.widget)
        cls.mw.show()
        QTest.qWaitForWindowShown(cls.mw)
        cls.app.processEvents()

    @classmethod
    def tearDownClass(cls):
        cls.mw.close()
        # cls.app.exit()

    def setUp(self):
        super(TestEditOrderPartsComputations,self).setUp()
        operation_definition_cache.refresh()


    def _encode_imputable_operation(self):
        widget = self.widget
        app = self.app

        widget.controller_operation.view.setFocus(Qt.OtherFocusReason)
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

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_O) # modifier, delay
        app.processEvents()


        ed = app.focusWidget()
        app.processEvents()
        app.processEvents()

        ed.hide()
        ed.close()
        ed.repaint()
        app.processEvents()


        app.processEvents()

        # app.exec_()

        for i in range(10000):
            app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()

        for i in range(10000):
            app.processEvents()


        # Operation's description
        QTest.keyClicks(app.focusWidget(), "Description op 1, TOurnage") # modifier, delay
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Uacute) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()

        # Valude/price (skipped because TO is not a fixed price)

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

        widget.controller_part.view.setFocus(Qt.OtherFocusReason)

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

        # Quantity
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_1) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_0) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()
        app.processEvents()

        # skip deadline
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Tab) # modifier, delay
        app.processEvents()

        # Price
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
        """ Fill an order part line and be ready to edit the next one.
        """

        mainlog.debug("_fill_order_part : {}".format(description))
        app = self.app

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_0) # modifier, delay
        app.processEvents()
        QTest.keyClicks(app.focusWidget(), description) # modifier, delay

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()

        # Qantity
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_9) # modifier, delay
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()

        # skip deadline
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Tab) # modifier, delay
        app.processEvents()

        # Price
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_1) # modifier, delay
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()

        mainlog.debug("_fill_order_part : DONE with {}".format(description))

    def _save(self):
        app = self.app
        # Save
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()


    def test_order_total_sell_price(self):

        app = self.app
        app.setEffectEnabled(Qt.UI_AnimateCombo, False)
        widget = self.widget
        mw = self.mw
        self._make_basic_preorder()

        # app.exec_()


        widget.controller_part.view.setFocus(Qt.OtherFocusReason)
        QTest.keyEvent(QTest.Click, widget.controller_part.view, Qt.Key_Up) # modifier, delay
        QTest.keyEvent(QTest.Click, widget.controller_part.view, Qt.Key_F5) # modifier, delay
        app.processEvents()

        self._fill_order_part("Order part new")


        app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Escape ) # Stop editing
        widget.controller_part.view.setFocus(Qt.OtherFocusReason)

        QTest.keyEvent(QTest.Click, widget.controller_part.view, Qt.Key_F5, Qt.ShiftModifier) # modifier, delay
        app.processEvents()

        self._fill_order_part("Order part new-new")

        # Save
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Escape ) # Stop editing
        widget.controller_part.view.setFocus(Qt.OtherFocusReason)

        # app.exec_()

        self.assertEqual(9*1+111*10+9*1,widget.total_selling_price_label.value)

        order = dao.order_dao.find_by_id(widget._current_order.order_id)
        self.assertEqual(order.total_sell_price(),widget.total_selling_price_label.value)








if __name__ == "__main__":
    unittest.main()
