import unittest

from PySide.QtGui import QApplication, QPushButton
from PySide.QtTest import QTest

from koi.EditCustomerDialog import EditCustomerDialog
from koi.dao import *
from koi.test.test_base import TestBase

class TestCustomerDialog(TestBase):

    @classmethod
    def setUpClass(cls):
        super(TestCustomerDialog,cls).setUpClass()
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        cls.app = app

    @classmethod
    def tearDownClass(cls):
        cls.app.processEvents()
        # cls.app.exit()

    def setUp(self):
        super(TestCustomerDialog,self).setUp()

        self.widget = EditCustomerDialog(None)
        self.widget.show()
        QTest.qWaitForWindowShown(self.widget)

    def tearDown(self):
        super(TestCustomerDialog,self).tearDown()

        # Those two lines avoid crash
        self.widget.close()
        # self.widget.deleteLater()
        self.widget = None

    def test_add(self):

        b = self.widget.findChild( QPushButton, "newButton")
        print(b)
        # self.app.exec_()
        pass


if __name__ == "__main__":
    unittest.main()
