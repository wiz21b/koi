import unittest
from unittest import skip
import logging

import datetime
from datetime import date
import hashlib
from collections import OrderedDict
from sqlalchemy.sql.expression import desc

from koi.test.test_base import TestBase
from koi.Configurator import mainlog
from koi.db_mapping import *
from koi.dao import *
from koi.datalayer.types import DBObjectActionTypes

from koi.junkyard.sqla_dict_bridge import InstrumentedRelation


class TestIndexes(TestBase):
    def test_order_parts(self):
        order = self._make_order()
        order.parts[0].description = 'test desc'
        dao.order_dao.save(order)

        p = dao.order_part_dao.find_by_id_frozen(order.parts[0].order_part_id)

        self.assertEqual('testdesc',p.indexed_description)
        p.description = 'AzE 123'

        actions = [ (DBObjectActionTypes.TO_UPDATE, p,0, InstrumentedRelation()) ]

        dao.order_part_dao._update_order_parts(actions, order)

        order = dao.order_dao.find_by_id(order.order_id)
        self.assertEqual('aze123',order.parts[0].indexed_description)



if __name__ == '__main__':
    unittest.main()
