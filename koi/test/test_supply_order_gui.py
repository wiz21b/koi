import unittest
import datetime

from PySide.QtGui import QApplication,QMainWindow, QDialogButtonBox
from PySide.QtTest import QTest
from PySide.QtCore import Qt

from koi.test.test_base import TestBase

from koi.db_mapping import *
from koi.dao import *

from koi.datalayer.supplier_mapping import Supplier
from koi.supply.EditSupplyOrderPanel import EditSupplyOrderPanel
from koi.datalayer.supplier_service import supplier_service
from koi.datalayer.generic_access import blank_dto

class TestSupplyOrderSlipGUI(TestBase):

    @classmethod
    def setUpClass(cls):
        super(TestSupplyOrderSlipGUI,cls).setUpClass()
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        cls.app = app

    @classmethod
    def tearDownClass(cls):
        super(TestSupplyOrderSlipGUI,cls).tearDownClass()
        cls.app.processEvents()
        # cls.app.exit()

    def setUp(self):
        super(TestSupplyOrderSlipGUI,self).setUp()

        self.widget = EditSupplyOrderPanel(None)

        self._order = self._make_order()
        mainlog.debug("Accounting label {}".format(self._order.accounting_label))
        self.dao.order_dao.recompute_position_labels(self._order)
        session().commit()

        self.widget.show()
        QTest.qWaitForWindowShown(self.widget)

    def tearDown(self):
        super(TestSupplyOrderSlipGUI,self).tearDown()

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


    def encode_text(self, text):
        k = [Qt.Key_0,Qt.Key_1,Qt.Key_2,Qt.Key_3,Qt.Key_4,Qt.Key_5,Qt.Key_6,Qt.Key_7,Qt.Key_8,Qt.Key_9,
             Qt.Key_A,Qt.Key_B,Qt.Key_C,Qt.Key_D,Qt.Key_E,Qt.Key_F,Qt.Key_G,Qt.Key_H,Qt.Key_I,Qt.Key_J,
             Qt.Key_K,Qt.Key_L,Qt.Key_M,Qt.Key_N,Qt.Key_O,Qt.Key_P,Qt.Key_Q,Qt.Key_R,Qt.Key_S,Qt.Key_T,
             Qt.Key_U,Qt.Key_V,Qt.Key_W,Qt.Key_X,Qt.Key_Y,Qt.Key_Z]

        k = dict(list(zip(["z{}".format(c) for c in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"],k)))
        app = self.app

        for digit in text:
            kdigit = "z{}".format(digit)
            QTest.keyEvent(QTest.Click, app.focusWidget(), k[kdigit]) # modifier, delay
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



    def test_encode_supply_order(self):
        supplier = blank_dto(Supplier)
        supplier.fullname = "Tessier-Ashpool"
        supplier_id = supplier_service.save(supplier)
        supplier = supplier_service.find_by_id(supplier_id)

        self._pg_locks("on start")
        app = self.app
        widget = self.widget
        widget.edit_new(supplier)

        self.encode_text("PARTONE")
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter)
        app.processEvents()

        self.encode_text("11")
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter)
        app.processEvents()

        self.encode_text("22")
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter)
        app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()

        # app.exec_()




if __name__ == "__main__":
    unittest.main()
