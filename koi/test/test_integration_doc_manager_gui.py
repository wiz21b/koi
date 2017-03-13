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

def make_document_drop( drop_target, pos, mime_data):
    drag_enter_event = QDragEnterEvent( pos, Qt.CopyAction, mime_data, Qt.LeftButton, Qt.NoModifier)
    drop_target.dragEnterEvent(drag_enter_event)

    drop_event = QDropEvent( pos, Qt.CopyAction, mime_data, Qt.LeftButton, Qt.NoModifier)
    drop_target.dropEvent(drop_event)


class TestEditOrderPartsDocManager(TestBase):

    @classmethod
    def setUpClass(cls):
        super(TestEditOrderPartsDocManager,cls).setUpClass()

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        # Fix issues with combo box that gets cleared too fast
        app.setEffectEnabled(Qt.UI_AnimateCombo, False)
        cls.app = app

        operation_definition_cache.reload()
        cls.mw = QMainWindow()
        cls.mw.setMinimumSize(1024,768)
        cls.widget = EditOrderPartsWidget(None, None, False, cls.remote_documents_service)
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
        super(TestEditOrderPartsDocManager,self).setUp()
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

    def test_edit_order_documents(self):

        app = self.app
        widget = self.widget
        mw = self.mw

        # order = self._make_order()
        # order_id = order.order_id
        # widget.reset_order(order.order_id)

        widget.edit_new_order(self.customer_id)

        widget.controller_part.view.setFocus(Qt.OtherFocusReason)

        # QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Escape) # modifier, delay
        # QTest.keyEvent(QTest.Click, widget.controller_part.view, Qt.Key_F5, Qt.ShiftModifier) # modifier, delay
        # app.processEvents()

        self._fill_order_part("Order part two")

        # Put the cursor back on the first line so the next document drop is tied to it.
        QTest.keyEvent(QTest.Click, widget.controller_part.view, Qt.Key_Up)
        app.processEvents()
        # app.exec_()

        tmp_file, tmp_path = self._make_tmp_file()
        mime_data = QMimeData()
        url = "file:///{}".format(os.path.abspath(tmp_path).replace('\\','/'))
        mainlog.debug("Dropping at {}".format(QUrl(url).toString()))
        mime_data.setUrls( [ QUrl(url) ])
        make_document_drop( widget.documents_widget.view, QPoint(10,10), mime_data)



        self._clear_tmp_file(tmp_file, tmp_path)

        # That's fine, but I'll need to pilot the file chooser dialog, and that's hard :-(
        # But even if I find my way around that, I'll have to mock the file server... :-(
        # b.click()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()

        order = dao.order_dao.find_by_id(widget._current_order.order_id)

        #app.exec_()
        self.assertEqual(1, len(order.parts[0].documents), "One document was added on the first part")



    def test_edit_order_add_rename_documents(self):

        app = self.app
        widget = self.widget
        mw = self.mw

        widget.edit_new_order(self.customer_id)

        widget.controller_part.view.setFocus(Qt.OtherFocusReason)

        self._fill_order_part("Order part one")

        # Put the cursor back on the first line so the next document drop is tied to it.
        QTest.keyEvent(QTest.Click, widget.controller_part.view, Qt.Key_Up)
        app.processEvents()
        # app.exec_()

        # Drop a document
        tmp_file, tmp_path = self._make_tmp_file()
        mime_data = QMimeData()
        url = "file:///{}".format(os.path.abspath(tmp_path).replace('\\','/'))
        mainlog.debug("Dropping at {}".format(QUrl(url).toString()))
        mime_data.setUrls( [ QUrl(url) ])

        make_document_drop( widget.documents_widget.view, QPoint(10,10), mime_data)

        self._clear_tmp_file(tmp_file, tmp_path)

        # Now it has been dropped, rename it
        # (this tests things like non-delayed create, delayed rename)

        model = widget.documents_widget.model
        fn_ndx = model.prototype.index_of("filename")
        ndx = model.index(0,fn_ndx)
        model.setData( ndx, "New name", Qt.UserRole)

        #app.exec_()

        # Now save the whole order
        widget.setFocus()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()

        order = dao.order_dao.find_by_id(widget._current_order.order_id)

        #app.exec_()
        self.assertEqual(1, len(order.parts[0].documents), "One document was added on the first part")

        documents = [d for d in order.parts[0].documents] # Set to array
        self.assertEqual("New name", documents[0].filename, "Rename should've been applied")



if __name__ == "__main__":
    unittest.main()
