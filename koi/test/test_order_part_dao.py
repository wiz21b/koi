import unittest
from unittest import skip

import datetime
from datetime import date
import hashlib
import logging

from sqlalchemy.sql.expression import desc

from koi.test.test_base import TestBase
from koi.db_mapping import *
from koi.dao import *
from koi.PotentialTasksCache import PotentialTasksCache
from koi.Configurator import mainlog

class TestOrderPartDao(TestBase):

    def setUp(self):
        self._clear_database_content()

    def test_find_by_ids(self):
        order3 = self._make_order()
        order3.parts[0].description = "Tango"
        order2 = self._make_order()
        order2.parts[0].description = "Zulu"
        session().commit()

        oid = order3.parts[0].order_part_id
        self.assertEqual([],dao.order_part_dao.find_by_ids(None))
        self.assertEqual([],dao.order_part_dao.find_by_ids([]))
        self.assertEqual(1,len(dao.order_part_dao.find_by_ids([oid])))
        self.assertEqual("101A",dao.order_part_dao.find_by_ids([oid])[0].full_part_id)
        self.assertEqual(order3.parts[0].description,dao.order_part_dao.find_by_ids([oid])[0].description)

    def test_find_by_full_id(self):

        order = self._make_order()
        mainlog.debug("Part id = {}".format(order.parts[0].label))

        self.assertEqual( [order.parts[0].order_part_id], dao.order_part_dao.find_by_full_id(order.parts[0].human_identifier))
        self.assertEqual( [], dao.order_part_dao.find_by_full_id(None))
        self.assertEqual( [], dao.order_part_dao.find_by_full_id('E'))
        self.assertEqual( [], dao.order_part_dao.find_by_full_id('1'))
        self.assertEqual( [], dao.order_part_dao.find_by_full_id('1EA'))


    def test_find_by_text(self):
        order = self._make_order()
        order.customer_order_name = "XPKZ"

        order2 = self._make_order()
        order2.customer_order_name = "ABCDE"
        order2.parts[0].description = "Part_Two"

        # An order part which has the same name as its customer...
        # verrrry bad trap for the search (this will make
        # sure the same order doesn't appear twice)

        order3 = self._make_order()
        order3.parts[0].description = self.customer.fullname
        session().commit()

        try:
            dao.order_part_dao.find_ids_by_text(None)
            self.fail()
        except DataException as ex:
            self.assertEqual(DataException.CRITERIA_IS_EMPTY,ex.code)

        try:
            dao.order_part_dao.find_ids_by_text("A")
            self.fail()
        except DataException as ex:
            self.assertEqual(DataException.CRITERIA_IS_TOO_SHORT,ex.code)

        try:
            dao.order_part_dao.find_ids_by_text("A"*100)
            self.fail()
        except DataException as ex:
            self.assertEqual(DataException.CRITERIA_IS_TOO_LONG,ex.code)

        try:
            dao.order_part_dao.find_ids_by_text("123"*10 + "AB")
            self.fail()
        except DataException as ex:
            self.assertEqual(DataException.CRITERIA_IS_TOO_LONG,ex.code)

        try:
            dao.order_part_dao.find_ids_by_text("123" + "AB"*10)
            self.fail()
        except DataException as ex:
            self.assertEqual(DataException.CRITERIA_IS_TOO_LONG,ex.code)

        # By very small id, but id nonetheless
        self.assertEqual( (False, []),
                           dao.order_part_dao.find_ids_by_text("1"))


        # By part id
        self.assertEqual( (False, [order.parts[0].order_part_id]),
                           dao.order_part_dao.find_ids_by_text(order.parts[0].human_identifier))

        # By order preorder/accounting label
        self.assertEqual( (False,[order.parts[0].order_part_id]),
                           dao.order_part_dao.find_ids_by_text("101"))
        self.assertEqual( (False,[]),
                           dao.order_part_dao.find_ids_by_text("303"))

        # By customer name
        self.assertEqual( (False, [order3.parts[0].order_part_id,
                            order2.parts[0].order_part_id,
                            order.parts[0].order_part_id ]), # Most recent first !
                           dao.order_part_dao.find_ids_by_text("mens"))
        self.assertEqual( (False,[]),
                           dao.order_part_dao.find_ids_by_text("ZZZZ"))

        # By customer order name
        self.assertEqual( (False, [order.parts[0].order_part_id]),
                           dao.order_part_dao.find_ids_by_text("xPkZ"))

        # By order part description
        self.assertEqual( (False, [order.parts[0].order_part_id]),
                           dao.order_part_dao.find_ids_by_text("Part 1"))

        self.assertEqual( (False, [order2.parts[0].order_part_id,
                            order.parts[0].order_part_id]),
                           dao.order_part_dao.find_ids_by_text("Part"))

        self.assertEqual( (False,[]),
                           dao.order_part_dao.find_ids_by_text("Part Z"))


        # Make sure we can reach the order part with their id's

        self.assertEqual( [],
                           dao.order_part_dao.find_by_ids([]))

        r = dao.order_part_dao.find_ids_by_text("Part")
        self.assertEqual(2, len(r))

if __name__ == '__main__':
    unittest.main()
