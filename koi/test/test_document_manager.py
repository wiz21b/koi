import unittest
import os
import tempfile
from datetime import datetime

from sqlalchemy.orm.exc import NoResultFound

from koi.test.test_base import TestBase
from koi.db_mapping import *
from koi.dao import *
from koi.doc_manager.documents_service import documents_service

from koi.Configurator import configuration


class TestDocumentManager(TestBase):

    @classmethod
    def setUpClass(cls):
        super(TestDocumentManager,cls).setUpClass()
        cls.temp_dir = tempfile.TemporaryDirectory("doc_mgr")

        configuration.set("DocumentsDatabase","documents_root",cls.temp_dir.name)

    def _make_tmp_file(self):
        tmpfile,tmpfile_path = tempfile.mkstemp(prefix='KoiTest_', suffix='.dat')
        tmpfile = os.fdopen(tmpfile,"w")
        tmpfile.write("TestData")
        tmpfile.close()
        tmpfile = open(tmpfile_path,"rb")
        return tmpfile,tmpfile_path

    def _clear_tmp_file(self, tmpfile, tmpfile_path):
        tmpfile.close()
        os.unlink(tmpfile_path)


    def test_names(self):
        tmp = self._make_tmp_file()

        import sys

        fn = str(os.sep) + chr(8364) + u'zulu.pdf'

        doc_id = documents_service.save(None, tmp[0], fn, 'description')

        p = documents_service._make_path_to_document(doc_id, fn)
        assert os.path.exists(p)

        documents_service.delete(doc_id)
        assert not os.path.exists(p)

        self._clear_tmp_file(*tmp)


    def test_add_delete(self):
        tmp = self._make_tmp_file()
        doc_id = documents_service.save(None, tmp[0], 'zulu', 'description')
        documents_service.delete(doc_id)
        self._clear_tmp_file(*tmp)

        tmp = self._make_tmp_file()
        doc_id = documents_service.save(None, tmp[0], 'zulu.txt', 'description')

        d = documents_service.find_by_id(doc_id)
        assert d.filename == "zulu.txt"
        assert "koimes_{}_{}".format(doc_id,"zulu.txt") in d.server_location
        assert d.file_size == 8
        assert d.upload_date.year == datetime.today().year
        assert d.upload_date.month == datetime.today().month
        assert d.upload_date.day == datetime.today().day


        tmp2 = self._make_tmp_file()
        doc_id2 = documents_service.save(None, tmp2[0], 'zulu.txt', 'description')
        documents_service.delete(doc_id)
        documents_service.delete(doc_id2)

        self._clear_tmp_file(*tmp)
        self._clear_tmp_file(*tmp2)


    def test_add_delete_template(self):
        t = documents_service.all_templates()
        assert len(t) == 0

        tmp = self._make_tmp_file()
        tpl_id = documents_service.save_template(tmp[0], 'zulu.tpl')
        self._clear_tmp_file(*tmp)

        t = documents_service.all_templates()
        assert len(t) == 1

        d = documents_service.find_by_id(tpl_id)
        assert d.filename == "zulu.tpl"
        assert "koimes_{}_{}".format(tpl_id,"zulu.tpl") in d.server_location
        assert d.file_size == 8
        assert d.upload_date.year == datetime.today().year
        assert d.upload_date.month == datetime.today().month
        assert d.upload_date.day == datetime.today().day


        documents_service.delete(tpl_id)

        t = documents_service.all_templates()
        assert len(t) == 0

    def test_copy_template(self):

        tmp = self._make_tmp_file()
        tpl_id = documents_service.save_template(tmp[0], 'zulu')
        self._clear_tmp_file(*tmp)

        doc_id = documents_service.copy_template_to_document(tpl_id)

        assert documents_service.find_by_id(doc_id)
        assert documents_service.find_by_id(tpl_id)


    def test_order_association(self):
        order = self._make_order()
        tmp = self._make_tmp_file()
        doc_id = documents_service.save(None, tmp[0], 'zulu', 'description')
        self._clear_tmp_file(*tmp)

        documents_service.associate_to_order(order.order_id, doc_id)

        assert len(order.documents) == 1
        assert list(order.documents)[0].document_id == doc_id

        documents_service.delete(doc_id)

        assert len(order.documents) == 0


    def test_order_association2(self):
        order = self._make_order()

        tmp = self._make_tmp_file()
        doc_id = documents_service.save(None, tmp[0], 'zulu', 'description')
        self._clear_tmp_file(*tmp)

        tmp = self._make_tmp_file()
        doc_id2 = documents_service.save(None, tmp[0], 'zulu', 'description')
        self._clear_tmp_file(*tmp)

        documents_service.associate_to_order(order.order_id, [doc_id, doc_id2])
        assert len(documents_service.find_by_order_id(order.order_id)) == 2

        assert len(order.documents) == 2

        session().delete(order)
        session().commit()

        # Make sure all the docs of the part were removed
        try:
            documents_service.find_by_id(doc_id)
            self.fail()
        except NoResultFound as ex:
            pass

        assert len(documents_service.find_by_order_id(order.order_id)) == 0

if __name__ == "__main__":
    unittest.main()
