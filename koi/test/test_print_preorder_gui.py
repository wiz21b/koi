import unittest
import datetime

from PySide.QtGui import QApplication,QMainWindow, QDialogButtonBox
from PySide.QtTest import QTest



from koi.test.test_base import TestBase
from db_mapping import *
from dao import *


from BarCodeBase import BarCodeIdentifier

from PrintPreorderDialog import PrintPreorderDialog

class TestPrintPreorderGUI(TestBase):

    @classmethod
    def setUpClass(cls):
        super(TestPrintPreorderGUI,cls).setUpClass()
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        cls.app = app

    @classmethod
    def tearDownClass(cls):
        cls.app.processEvents()
        # cls.app.exit()

    def setUp(self):
        super(TestPrintPreorderGUI,self).setUp()

        self.widget = PrintPreorderDialog(None)

        self._order = self._make_order()
        self.dao.order_dao.recompute_position_labels(self._order)
        session().commit()

        self.widget.show()
        QTest.qWaitForWindowShown(self.widget)

    def tearDown(self):
        super(TestPrintPreorderGUI,self).tearDown()

        # Those two lines avoid crash
        self.widget.close()
        # self.widget.deleteLater()
        self.widget = None
        
    def test_happy(self):
        order = self._make_order()
        dao.order_dao.save(order)
        session().commit()
        order_id = order.order_id
        session().close()

        b = self.widget.buttons.button(QDialogButtonBox.Ok)

        self.widget.set_preorder( order_id)
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_Enter)
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
