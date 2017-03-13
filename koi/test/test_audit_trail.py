import unittest
from unittest import skip
import logging

import datetime
from datetime import date
import hashlib
from collections import OrderedDict
from sqlalchemy.sql.expression import desc

from koi.test.test_base import TestBase
from koi.db_mapping import *
from koi.dao import *
from koi.Configurator import mainlog
from koi.datalayer.audit_trail_service import audit_trail_service

class TestAuditTrail(TestBase):

    def test_add(self):
        audit_trail_service.record("CUSTOMER_EDIT","name=Google", 123, self.employee_id)

    def test_save_order(self):
        order = self._make_order()
        dao.order_dao.save(order)

        # Right now, the operation above implies a CREATE_ORDER followed
        # by an UPDATE_ORDER...
        assert len(audit_trail_service.audit_trail_for_order(order.order_id)) == 2

    def test_who_touched_order(self):
        order = self._make_order()
        dao.order_dao.save(order)

        # We don't see our own updates
        self.assertEqual(0, len(audit_trail_service.who_touched_order(order.order_id)))

        # We see others updates (and there's only one of those)
        self.assertEqual(1, len(audit_trail_service.who_touched_order(order.order_id,123456)))


if __name__ == '__main__':
    unittest.main()
