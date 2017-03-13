import unittest
from unittest import skip

from koi.test.test_base import TestBase
from koi.dao import *
from koi.Configurator import mainlog
from koi.datalayer.data_exception import DataException

from koi.datalayer.quality import QualityEvent, QualityEventType
from koi.quality.quality_dao import QualityDao

class TestQuality(TestBase):
    #
    # def setUp(self):
    #     self._clear_database_content()


    def test_quality_event_labels(self):

        dao = self.dao.quality_dao

        order = self._make_order()
        qe = dao.make(QualityEventType.non_conform_customer, order.parts[0].order_part_id)

        assert "NC-101A-1" == qe.human_identifier

        qe = dao.make(QualityEventType.non_conform_customer, order.parts[0].order_part_id)

        assert "NC-101A-2" == qe.human_identifier




if __name__ == '__main__':
    unittest.main()

