import unittest

from PySide.QtCore import QObject
from PySide.QtGui import QApplication, QPushButton
from PySide.QtTest import QTest

from koi.test.test_base import TestBase
from koi.EditCustomerDialog import EditEmployeeDialog
from koi.dao import *

class TestEmployeeDialog(TestBase):

    @classmethod
    def setUpClass(cls):
        super(TestEmployeeDialog,cls).setUpClass()
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        cls.app = app

    @classmethod
    def tearDownClass(cls):
        cls.app.processEvents()
        # cls.app.exit()

    def setUp(self):
        super(TestEmployeeDialog,self).setUp()

        self.widget = EditEmployeeDialog( None, self.dao)
        self.widget.show()
        QTest.qWaitForWindowShown(self.widget)

    def tearDown(self):
        super(TestEmployeeDialog,self).tearDown()

        # Those two lines avoid crash
        self.widget.close()
        # self.widget.deleteLater()
        self.widget = None

    def test_add(self):
        nb_employees = self.widget.list_view.model().rowCount()

        b = self.widget.findChild( QPushButton, "newButton")
        save = self.widget.findChild( QPushButton, "saveButton")
        delete = self.widget.findChild( QPushButton, "deleteButton")

        name_field = self.widget.findChild(QObject, "form_fullname")
        password_field = self.widget.findChild(QObject, "form_password")
        login_field = self.widget.findChild(QObject, "form_login")

        b.click()
        name_field.setText("AAAGongo")

        # Normally, the error box says "must give login", "must give password"
        self.prepare_to_click_dialog("errorBox")
        save.click()

        login_field.setText("gng")
        password_field.setText("password")
        save.click()

        # I go deep in the object tree to get my value...
        m = self.widget.list_view.model()
        self.assertEqual( "AAAGongo", m.data( m.index(0,0)))

        # self.app.exec_()

        # I do the delete here to make sure I restore the database content.
        # delete.click()

        m = self.widget.list_view.model()
        self.assertEqual( nb_employees+1, m.rowCount())

        self.widget.line_in.setText("Gongo")

        self.assertEqual( "AAAGongo", m.data( m.index(0,0)))
        self.assertEqual( 1, m.rowCount())
        delete.click()

        # Since the filter doesn't choose anything else than Gongo, the list
        # view is empty. In that specific case, we clear the form
        self.assertEqual( '', name_field.text())
        self.assertEqual( '', login_field.text())
        self.assertEqual( '', password_field.text())

        self.widget.line_in.setText("")
        self.assertEqual( 4, m.rowCount())

        # self.app.exec_()

if __name__ == "__main__":
    unittest.main()
