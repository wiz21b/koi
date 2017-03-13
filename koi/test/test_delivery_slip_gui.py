import unittest

from PySide.QtCore import Qt
from PySide.QtGui import QApplication
from PySide.QtTest import QTest

from koi.delivery_slips.EditDeliverySlipDialog import EditDeliverySlipDialog
from koi.dao import *
from koi.test.test_base import TestBase

class TestDeliverySlipGUI(TestBase):

    @classmethod
    def setUpClass(cls):
        super(TestDeliverySlipGUI,cls).setUpClass()
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        cls.app = app

    @classmethod
    def tearDownClass(cls):
        cls.app.processEvents()
        # cls.app.exit()

    def setUp(self):
        super(TestDeliverySlipGUI,self).setUp()

        self.widget = EditDeliverySlipDialog(None)

        self._order = self._make_order()
        mainlog.debug("Accounting label {}".format(self._order.accounting_label))
        self.dao.order_dao.recompute_position_labels(self._order)
        session().commit()

        self.widget.show()
        QTest.qWaitForWindowShown(self.widget)

    def tearDown(self):
        super(TestDeliverySlipGUI,self).tearDown()

        # Those two lines avoid crash
        self.widget.close()
        # self.widget.deleteLater()
        self.widget = None


    def _encode_imputable_operation(self,nb_hours = 2):
        widget = self.widget
        app = self.app

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_1) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_0) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_1) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_A) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter)
        app.processEvents()

        # Choose the first operation
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter)
        app.processEvents()

        k = [Qt.Key_0,Qt.Key_1,Qt.Key_2,Qt.Key_3,Qt.Key_4,Qt.Key_5,Qt.Key_6,Qt.Key_7,Qt.Key_8,Qt.Key_9][nb_hours]

        # Work 2 hours on it.
        QTest.keyEvent(QTest.Click, app.focusWidget(), k)
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter)
        app.processEvents()


    def _encode_part(self,order_part_human_identifier, nb_hours = 2):
        widget = self.widget
        app = self.app

        k = [Qt.Key_0,Qt.Key_1,Qt.Key_2,Qt.Key_3,Qt.Key_4,Qt.Key_5,Qt.Key_6,Qt.Key_7,Qt.Key_8,Qt.Key_9,
             Qt.Key_A,Qt.Key_B,Qt.Key_C,Qt.Key_D,Qt.Key_E,Qt.Key_F,Qt.Key_G,Qt.Key_H,Qt.Key_I,Qt.Key_J,
             Qt.Key_K,Qt.Key_L,Qt.Key_M,Qt.Key_N,Qt.Key_O,Qt.Key_P,Qt.Key_Q,Qt.Key_R,Qt.Key_S,Qt.Key_T,
             Qt.Key_U,Qt.Key_V,Qt.Key_W,Qt.Key_X,Qt.Key_Y,Qt.Key_Z]

        k = dict(list(zip(["z{}".format(c) for c in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"],k)))

        for digit in order_part_human_identifier:
            kdigit = "z{}".format(digit)
            QTest.keyEvent(QTest.Click, app.focusWidget(), k[kdigit]) # modifier, delay
            app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter)
        app.processEvents()



    def test_encode_normal_delivery_slip(self):
        self._pg_locks("on start")
        app = self.app
        widget = self.widget

        order = self._make_order()
        order.parts[0].qty = 10
        order.parts[0].sell_price = 10

        self.order_dao.change_order_parts_state(order.order_id, [order.parts[0].order_part_id], OrderPartStateType.ready_for_production)

        self.show_order(order)

        widget.set_data(order.order_id)
        widget.show()
        widget._start_edit()
        app.processEvents()

        self._encode_part("5")

        self._pg_locks()

        for i in range(10000):
            # print(i)
            app.processEvents()

        self.prepare_to_click_dialog("confirmDSCreation")

        # from dialog_utils import confirmationBox
        # confirmationBox("uytyutyutyutyu","iyiuyuiyiuyuiy","teststetstetsets")
        # confirmationBox("uytyutyutyutyu","iyiuyuiyiuyuiy","teststetstetsets")

        mainlog.debug( "submit form")
        for i in range(10000):
            # print(i)
            app.processEvents()
        # Submit form
        print((app.focusWidget()))
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter)

        last_slip_id = self.delivery_slip_dao.find_last_slip_id()
        ds = self.delivery_slip_dao.find_by_id(last_slip_id)

        assert ds.delivery_slip_parts[0].quantity_out == 5
        assert ds.delivery_slip_parts[0].order_part_id == order.parts[0].order_part_id


    def test_encode_delivery_slip_with_too_big_quantity(self):
        self._pg_locks("on start")
        app = self.app
        widget = self.widget

        order = self._make_order()
        order.parts[0].qty = 10
        order.parts[0].sell_price = 10

        self.order_dao.change_order_parts_state(order.order_id, [order.parts[0].order_part_id], OrderPartStateType.ready_for_production)

        self.show_order(order)

        widget.set_data(order.order_id)
        widget.show()
        widget._start_edit()
        app.processEvents()

        # So we say we deliver 99 unit.
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_9)
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_9)
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter)
        app.processEvents()

        self._pg_locks()

        self.prepare_to_click_dialog("quantityTooBig")

        # Submit form
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter)

        assert not session().query(DeliverySlip.delivery_slip_id).all()


    def test_encode_delivery_slip_without_quantity(self):
        self._pg_locks("on start")
        app = self.app
        widget = self.widget

        order = self._make_order()
        order.parts[0].qty = 10
        order.parts[0].sell_price = 10

        self.order_dao.change_order_parts_state(order.order_id, [order.parts[0].order_part_id], OrderPartStateType.ready_for_production)

        widget.set_data(order.order_id)
        widget.show()
        widget._start_edit()
        app.processEvents()

        self._pg_locks()


        # Finish editing
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter)

        self.prepare_to_click_dialog("quantity_missing")

        # Submit form
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter)

        assert self.dialog_test_result
        assert not session().query(DeliverySlip.delivery_slip_id).all()



    def test_encode_delivery_slip_with_unpriced_part(self):
        self._pg_locks("on start")
        app = self.app
        widget = self.widget

        order = self._make_order()
        order.parts[0].qty = 10
        order.parts[0].sell_price = 0 # unpriced part

        self.order_dao.change_order_parts_state(order.order_id, [order.parts[0].order_part_id], OrderPartStateType.ready_for_production)

        self.show_order(order)

        widget.set_data(order.order_id)
        widget.show()
        widget._start_edit()
        app.processEvents()

        # At this point the cursor is on the first order part,
        # in the column for quantities to deliver.

        # So we say we deliver 1 unit.
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_1)
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter)
        app.processEvents()

        self._pg_locks()

        # Two errors must show up

        self.prepare_to_click_dialog("unpriced_part")
        self.prepare_to_click_dialog("confirmDSCreation")
        # Submit form
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter)


        self.wait_until_dialog_clicked()
        self.wait_until_dialog_clicked()

        # The slip was saved
        assert session().query(DeliverySlip.delivery_slip_id).all()



if __name__ == "__main__":
    unittest.main()
