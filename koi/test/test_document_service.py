import unittest
from unittest import skip
from koi.test.test_base import TestBase

from koi.doc_manager.documents_service import DocumentsService

class TestDocumentService(TestBase):

    def setUp(self):
        self._clear_database_content()
        self.ds = DocumentsService()


    def test_find(self):

        order = self._make_order()
        order_id = order.order_id

        import io

        t = io.BytesIO( "Zulu".encode())
        doc_id = self.ds.save( 0, t, "Caracas", "The description")

        doc = self.ds.find_by_id(doc_id)

        assert not doc.order_id

        self.ds.associate_to_order(order_id, [doc_id])

        doc = self.ds.find_by_id(doc_id)
        assert doc.order_id == order_id

if __name__ == '__main__':
    unittest.main()
