import unittest
import os
import tempfile
from datetime import datetime
import shutil

from sqlalchemy.orm.exc import NoResultFound

import sys
from PySide.QtTest import QTest
from PySide.QtGui import QApplication, QDropEvent, QDragEnterEvent
from PySide.QtCore import QMimeData, QUrl, Qt

from koi.test.test_base import TestBase
from koi.db_mapping import *
from koi.dao import *

from koi.Configurator import configuration


from koi.doc_manager.documents_service import documents_service
from koi.doc_manager.templates_collection_widget import TemplatesCollectionWidget, TemplatesCollectionWidgetDialog
from koi.server.json_decorator import JsonCallWrapper



class TestDocumentTemplateManagerGui(TestBase):

    @classmethod
    def setUpClass(cls):
        super(TestDocumentTemplateManagerGui,cls).setUpClass()
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
        super(TestDocumentTemplateManagerGui,self).setUp()
        self.dialog = TemplatesCollectionWidgetDialog(None,self.remote_documents_service)

        self.dialog.setMinimumSize(1024,768)
        self.dialog.open()

        QTest.qWaitForWindowShown(self.dialog)
        self.app.processEvents()

    def tearDown(self):
        self.dialog.close()
        self.dialog = None # GC

    def _make_tmp_file(self):
        tmpfile,tmpfile_path = tempfile.mkstemp(prefix='HorseTest_', suffix='.dat')
        tmpfile = os.fdopen(tmpfile,"w")
        tmpfile.write("TestData")
        tmpfile.close()
        tmpfile = open(tmpfile_path,"rb")
        return tmpfile,tmpfile_path

    def _clear_tmp_file(self, tmpfile, tmpfile_path):
        tmpfile.close()
        os.unlink(tmpfile_path)

    def test_replace_template_with_reference(self):
        tmp_file, tmp_path = self._make_tmp_file()

        # Reference must be unique (or NULL), that's what we test.

        # Simulate an add, the add is not delayed.
        self.dialog.widget._add_file(tmp_path)

        # Make it a Horse template (i.e. with a reference)
        docs = documents_service.all_templates()
        template = docs[0]
        mainlog.debug("docid:{},  tpl id:{}",template.document_id,template.template_document_id)
        documents_service.update_template_description(template.template_document_id, template.description, template.filename, "REF")
        self.dialog.widget.refresh_templates_list()

        # At this point there's only one line in the table



        drop_target = self.dialog.widget.view
        mime_data = QMimeData()
        url = "file:///{}".format(os.path.abspath(tmp_path).replace('\\','/'))
        mainlog.debug("Dropping at {}".format(QUrl(url).toString()))
        mime_data.setUrls( [ QUrl(url) ])
        pos = self.dialog.widget.view.pos() # in parent coordinate
        pos.setY(pos.y() + 5)

        drag_enter_event = QDragEnterEvent( pos, Qt.CopyAction, mime_data, Qt.LeftButton, Qt.NoModifier)
        drop_target.dragEnterEvent(drag_enter_event)

        drop_event = QDropEvent( pos, Qt.CopyAction, mime_data, Qt.LeftButton, Qt.NoModifier)
        drop_target.dropEvent(drop_event)


        self.prepare_to_click_dialog("confirmationBox")
        self.dialog.widget.view.dropEvent(drop_event)
        self.wait_until_dialog_clicked()
        assert self.dialog_test_result


        self._clear_tmp_file(tmp_file, tmp_path)


    # @unittest.skip("faster test")
    def test_change_description(self):
        tmp_file, tmp_path = self._make_tmp_file()

        # Simulate an add, the add is not delayed.
        self.dialog.widget._add_file(tmp_path)

        # Actually change the reference in DB (we can't do that in the GUI, it forbids it)
        docs = documents_service.all_templates()
        template = docs[0]
        documents_service.update_template_description(template.document_id, template.description, template.filename, "REF")

        # Update the content of the GUI
        self.dialog.widget.refresh_templates_list()

        # Make sure I can change the descrption

        description_ndx = self.dialog.widget.model.prototype.index_of("description")
        reference_ndx = self.dialog.widget.model.prototype.index_of("reference")

        self.dialog.widget.view.setCurrentIndex(self.dialog.widget.model.index(0,description_ndx))
        QTest.keyClicks(self.dialog.widget.view, "N") # triegger edit
        self.app.processEvents()
        QTest.keyClicks(self.app.focusWidget(), "ew") # finish edit
        self.app.processEvents()
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_Enter) # finish edit

        # Make sure I can not change the reference
        self.dialog.widget.view.setCurrentIndex(self.dialog.widget.model.index(0,reference_ndx))
        QTest.keyClicks(self.dialog.widget.view, "Z") # triegger edit
        self.app.processEvents()
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_Enter) # finish edit

        template = documents_service.find_by_id(template.document_id)


        mainlog.debug("*** Template id:{} desc:{} ref:{}".format(template.document_id, template.description, template.reference))
        self.dialog.widget.refresh_templates_list()
        mainlog.debug(template)
        mainlog.debug("*** Template id:{} desc:{} ref:{}".format(template.document_id, template.description, template.reference))
        #self.app.exec_()

        assert template.description == "New"
        self.assertEqual("REF", template.reference, "The refrenece should not have changed (because it is forbidden)")

        self._clear_tmp_file(tmp_file, tmp_path)

    # @unittest.skip("faster test")
    # def test_add_remove_rename_delayed(self):
    #     tmp_file, tmp_path = self._make_tmp_file()
    #
    #     docs = documents_service.all_documents()
    #     assert len(docs) == 0
    #
    #     # Simulate an add, the add is not delayed.
    #     self.dialog.widget._add_file(tmp_path)
    #
    #     docs = documents_service.all_documents()
    #     assert len(docs) == 1
    #     assert docs[0].filename == os.path.basename(tmp_path)
    #
    #     # simulate a rename, be aware the the rename is delayed
    #
    #     ndx = self.dialog.widget.model.index(0,0)
    #     self.dialog.widget.model.setData( ndx, "New name", Qt.UserRole)
    #
    #     docs = documents_service.all_documents()
    #     assert len(docs) == 1
    #     assert docs[0].filename == os.path.basename(tmp_path)
    #
    #     # simulate a delete, the delete must be delayed
    #
    #     actions = self.dialog.widget.model.export_objects_as_actions()
    #     assert len(actions) == 1
    #
    #     self.dialog.widget.model.removeRows( 0, 1)
    #     docs = documents_service.all_documents()
    #     assert len(docs) == 1 # Delete has not been actually performed
    #     assert docs[0].filename == os.path.basename(tmp_path)
    #
    #     # Since the added object has been deleted, there's nothing
    #     # to do
    #     actions = self.dialog.widget.model.export_objects_as_actions()
    #     assert len(actions) == 0
    #
    #     self._clear_tmp_file(tmp_file, tmp_path)
    #
    #
    # @unittest.skip("faster test")
    # def test_drop(self):
    #     tmp_file, tmp_path = self._make_tmp_file()
    #
    #     docs = documents_service.all_documents()
    #     assert len(docs) == 0
    #
    #
    #     mime_data = QMimeData()
    #     url = "file:///{}".format(os.path.abspath(tmp_path).replace('\\','/'))
    #     mainlog.debug("Dropping at {}".format(QUrl(url).toString()))
    #     mime_data.setUrls( [ QUrl(url) ])
    #     drop_event = QDropEvent( QPoint(10,10),  Qt.CopyAction, mime_data, Qt.LeftButton, Qt.NoModifier)
    #
    #     self.dialog.widget.dropEvent(drop_event)
    #
    #     docs = documents_service.all_documents()
    #     assert len(docs) == 1
    #     assert docs[0].filename == os.path.basename(tmp_path)
    #
    #     # self.dialog.exec_()
    #
    #     self._clear_tmp_file(tmp_file, tmp_path)
    #
    # @unittest.skip("faster test")
    # def test_multi_drop(self):
    #     tmp_file, tmp_path = self._make_tmp_file()
    #
    #     docs = documents_service.all_documents()
    #     assert len(docs) == 0
    #
    #
    #     mime_data = QMimeData()
    #     url = "file:///{}".format(os.path.abspath(tmp_path).replace('\\','/'))
    #     mainlog.debug("Dropping at {}".format(QUrl(url).toString()))
    #     mime_data.setUrls( [ QUrl(url), QUrl(url), QUrl(url) ])
    #     drop_event = QDropEvent( QPoint(10,10),  Qt.CopyAction, mime_data, Qt.LeftButton, Qt.NoModifier)
    #
    #     self.dialog.widget.dropEvent(drop_event)
    #
    #     docs = documents_service.all_documents()
    #     assert len(docs) == 3
    #     assert docs[0].filename == os.path.basename(tmp_path)
    #
    #     # self.dialog.exec_()
    #
    #     self._clear_tmp_file(tmp_file, tmp_path)
    #
    #
    # @unittest.skip("faster test")
    # def test_upload_download(self):
    #     mainlog.debug("test_upload_download")
    #     docs = documents_service.all_documents()
    #     assert len(docs) == 0
    #
    #     # Monkey patch the file dialog. Remember that the upload function itself is also patched
    #     import types
    #     def __open_file_dialog(zelf):
    #         return os.path.abspath(__file__)
    #     self.dialog.widget._open_file_dialog = types.MethodType(__open_file_dialog, self.dialog.widget)
    #     def __save_file_dialog(zelf, proposed_filename):
    #         return os.path.join('c:', os.sep, 'tmp','horse_dl')
    #     self.dialog.widget._save_file_dialog = types.MethodType(__save_file_dialog, self.dialog.widget)
    #
    #
    #     from PySide.QtGui import QToolButton
    #     b = self.dialog.widget.findChild(QToolButton, "upload_button")
    #     b.click()
    #
    #     docs = documents_service.all_documents()
    #     self.assertEqual(1, len(docs), "We just uploaded one file")
    #     self.assertEqual(1, self.dialog.widget.model.rowCount(), "We just uploaded one file so rowCount should be one")
    #
    #     doc = self.dialog.widget.model.object_at(0)
    #
    #     button_name = "download{}".format(doc.button_id)
    #     mainlog.debug(button_name)
    #     b = self.dialog.widget.findChild(QToolButton, button_name)
    #     b.click()


if __name__ == "__main__":
    unittest.main()
