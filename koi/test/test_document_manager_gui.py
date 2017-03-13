import unittest
import os
import tempfile
from datetime import datetime
import shutil

from sqlalchemy.orm.exc import NoResultFound

import sys
from PySide.QtTest import QTest
from PySide.QtGui import QApplication, QDropEvent, QDragEnterEvent
from PySide.QtCore import QPoint, QMimeData, QUrl, Slot, Qt

from koi.test.test_base import TestBase
from koi.db_mapping import *
from koi.dao import *

from koi.Configurator import configuration



from koi.doc_manager.documents_service import documents_service
from koi.doc_manager.docs_collection_widget import DocumentCollectionWidgetDialog,DocumentCollectionWidget
from koi.server.json_decorator import JsonCallWrapper



class TestDocumentManagerGui(TestBase):

    @classmethod
    def setUpClass(cls):
        super(TestDocumentManagerGui,cls).setUpClass()
        cls.temp_dir = tempfile.TemporaryDirectory("horse_doc_mgr")

        configuration.set("DocumentsDatabase","documents_root",cls.temp_dir.name)

        # In process so that the server is bypassed (or else
        # I have to run a server in parallel)
        cls.remote_documents_service = JsonCallWrapper(documents_service,JsonCallWrapper.IN_PROCESS_MODE)


        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        # Fix issues with combo box that gets cleared too fast
        app.setEffectEnabled(Qt.UI_AnimateCombo, False)
        cls.app = app


    def setUp(self):
        super(TestDocumentManagerGui,self).setUp()
        self.dialog = DocumentCollectionWidgetDialog(None,self.remote_documents_service)

        self.dialog.setMinimumSize(1024,768)
        self.dialog.open()

        QTest.qWaitForWindowShown(self.dialog)
        self.app.processEvents()

    def tearDown(self):
        self.dialog.close()
        self.dialog = None # GC

    def test_rename(self):
        tmp_file, tmp_path = self._make_tmp_file()

        docs = documents_service.all_documents()
        assert len(docs) == 0

        # Simulate an add, the add is not delayed.
        self.dialog.widget._add_file(tmp_path)

        docs = documents_service.all_documents()
        assert len(docs) == 1
        assert docs[0].filename == os.path.basename(tmp_path)

        # simulate a rename, be aware the the rename is delayed

        fn_ndx = self.dialog.widget.model.prototype.index_of("filename")
        ndx = self.dialog.widget.model.index(0,fn_ndx)
        self.dialog.widget.model.setData( ndx, "New name", Qt.UserRole)

        # Rename is delayed, so no change yet
        docs = documents_service.all_documents()
        assert len(docs) == 1
        assert docs[0].filename == os.path.basename(tmp_path)

        # Apply rename
        self.dialog.widget.model.apply_delayed_renames(self.remote_documents_service)

        # Check it was applied
        docs = documents_service.all_documents()
        assert docs[0].filename == "New name"

    #@unittest.skip("faster test")
    def test_add_remove_rename_delayed(self):
        tmp_file, tmp_path = self._make_tmp_file()

        docs = documents_service.all_documents()
        assert len(docs) == 0

        # Simulate an add, the add is not delayed.
        self.dialog.widget._add_file(tmp_path)

        docs = documents_service.all_documents()
        assert len(docs) == 1
        assert docs[0].filename == os.path.basename(tmp_path)

        # simulate a rename, be aware the the rename is delayed

        ndx = self.dialog.widget.model.index(0,0)
        self.dialog.widget.model.setData( ndx, "New name", Qt.UserRole)

        docs = documents_service.all_documents()
        assert len(docs) == 1
        assert docs[0].filename == os.path.basename(tmp_path)

        # simulate a delete, the delete must be delayed

        actions = self.dialog.widget.model.export_objects_as_actions()
        assert len(actions) == 1

        self.dialog.widget.model.removeRows( 0, 1)
        docs = documents_service.all_documents()
        assert len(docs) == 1 # Delete has not been actually performed
        assert docs[0].filename == os.path.basename(tmp_path)

        # Since the added object has been deleted, there's nothing
        # to do
        actions = self.dialog.widget.model.export_objects_as_actions()
        assert len(actions) == 0

        self._clear_tmp_file(tmp_file, tmp_path)


    #@unittest.skip("faster test")
    def test_drop(self):
        tmp_file, tmp_path = self._make_tmp_file()

        docs = documents_service.all_documents()
        assert len(docs) == 0


        drop_target = self.dialog.widget.view
        mime_data = QMimeData()
        url = "file:///{}".format(os.path.abspath(tmp_path).replace('\\','/'))
        mainlog.debug("Dropping at {}".format(QUrl(url).toString()))
        mime_data.setUrls( [ QUrl(url) ])
        pos = QPoint(10,10)

        drag_enter_event = QDragEnterEvent( pos, Qt.CopyAction, mime_data, Qt.LeftButton, Qt.NoModifier)
        drop_target.dragEnterEvent(drag_enter_event)

        drop_event = QDropEvent( pos, Qt.CopyAction, mime_data, Qt.LeftButton, Qt.NoModifier)
        drop_target.dropEvent(drop_event)

        docs = documents_service.all_documents()
        assert len(docs) == 1
        assert docs[0].filename == os.path.basename(tmp_path)

        # self.dialog.exec_()

        self._clear_tmp_file(tmp_file, tmp_path)

    #@unittest.skip("faster test")
    def test_multi_drop(self):
        tmp_file, tmp_path = self._make_tmp_file()

        docs = documents_service.all_documents()
        assert len(docs) == 0

        drop_target = self.dialog.widget.view
        mime_data = QMimeData()
        url = "file:///{}".format(os.path.abspath(tmp_path).replace('\\','/'))
        mainlog.debug("Dropping at {}".format(QUrl(url).toString()))
        mime_data.setUrls( [ QUrl(url), QUrl(url), QUrl(url) ])
        pos = QPoint(10,10)

        drag_enter_event = QDragEnterEvent( pos, Qt.CopyAction, mime_data, Qt.LeftButton, Qt.NoModifier)
        drop_target.dragEnterEvent(drag_enter_event)

        drop_event = QDropEvent( pos, Qt.CopyAction, mime_data, Qt.LeftButton, Qt.NoModifier)
        drop_target.dropEvent(drop_event)



        docs = documents_service.all_documents()
        assert len(docs) == 3
        assert docs[0].filename == os.path.basename(tmp_path)

        # self.dialog.exec_()

        self._clear_tmp_file(tmp_file, tmp_path)


    def test_upload_download(self):
        mainlog.debug("test_upload_download")
        docs = documents_service.all_documents()
        assert len(docs) == 0

        # Monkey patch the file dialog. Remember that the upload function itself is also patched
        import types
        def __open_file_dialog(zelf):
            return os.path.abspath(__file__)
        self.dialog.widget._open_file_dialog = types.MethodType(__open_file_dialog, self.dialog.widget)
        def __save_file_dialog(zelf, proposed_filename):
            return os.path.join('c:', os.sep, 'tmp','horse_dl')
        self.dialog.widget._save_file_dialog = types.MethodType(__save_file_dialog, self.dialog.widget)


        from PySide.QtGui import QToolButton
        b = self.dialog.widget.findChild(QToolButton, "upload_button")
        b.click()

        docs = documents_service.all_documents()
        self.assertEqual(1, len(docs), "We just uploaded one file")
        self.assertEqual(1, self.dialog.widget.model.rowCount(), "We just uploaded one file so rowCount should be one")

        doc = self.dialog.widget.model.object_at(0)

        # Pich the last one
        button_name = "download{}".format(self.dialog.widget.button_id_counter - 1)
        mainlog.debug(button_name)
        b = self.dialog.widget.findChild(QToolButton, button_name)
        b.click()





    #@skip("This is is super tough to do, see comments in the test")

if __name__ == "__main__":
    unittest.main()
