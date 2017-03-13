import unittest
import datetime

from PySide.QtGui import QApplication,QMainWindow, QDialogButtonBox
from PySide.QtTest import QTest
from PySide.QtCore import Qt

from koi.test.test_base import TestBase
from koi.db_mapping import *
from koi.dao import *
from koi.FindOrder import FindOrderDialog

class TestFindOrderGUI(TestBase):

    @classmethod
    def setUpClass(cls):
        super(TestFindOrderGUI,cls).setUpClass()
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        cls.app = app

    @classmethod
    def tearDownClass(cls):
        cls.app.processEvents()
        # cls.app.exit()

    def setUp(self):
        super(TestFindOrderGUI,self).setUp()

        self.widget = FindOrderDialog(None)

        self._order = self._make_order()
        self.dao.order_dao.recompute_position_labels(self._order)
        session().commit()

        self.widget.show()
        QTest.qWaitForWindowShown(self.widget)

    def tearDown(self):
        super(TestFindOrderGUI,self).tearDown()

        # Those two lines avoid crash
        self.widget.close()
        # self.widget.deleteLater()
        self.widget = None

    def test_find_happy(self):
        order = self._make_order()
        dao.order_dao.save(order)
        session().commit()

        self.show_order(order)
        b = self.widget.buttons.button(QDialogButtonBox.Ok)

        mainlog.debug(str(order.preorder_label))

        self.widget.search_criteria.setText(str(order.accounting_label))

        
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_Enter)

        self.app.processEvents()
        self.assertEqual(1,self.widget.search_results_model.rowCount())


    def test_find_fails(self):
        self._make_order()
        session().commit()
        self._make_order()
        session().commit()

        self.widget.search_criteria.setText("A")
        self.prepare_to_click_dialog("filter_is_too_short")
        print("1"*10)
        self._fix_focus(self.widget, self.widget.search_criteria)
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_Enter)

        print("2"*10)
        self.widget.search_criteria.setText("")
        self.prepare_to_click_dialog("filter_is_empty")
        self._fix_focus(self.widget, self.widget.search_criteria)
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_Enter)

        print("3"*10)
        
        # Monkey patching !
        old_max = dao.order_part_dao.MAX_RESULTS
        dao.order_part_dao.MAX_RESULTS = 1
        self.widget.search_criteria.setText(self.customer.fullname)
        self.prepare_to_click_dialog("too_many_results")
        self._fix_focus(self.widget, self.widget.search_criteria)
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_Enter)
        self.assertEqual(1,self.widget.search_results_model.rowCount())

        dao.order_part_dao.MAX_RESULTS = old_max


if __name__ == "__main__":
    unittest.main()
