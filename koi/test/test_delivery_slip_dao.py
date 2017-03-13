import unittest
from unittest import skip

import datetime
from datetime import date
import hashlib
import logging
from collections import OrderedDict

from sqlalchemy.sql.expression import desc

from koi.test.test_base import TestBase
from koi.db_mapping import *
from koi.dao import *
from koi.Configurator import mainlog
from koi.datalayer.data_exception import DataException

class TestDeliverySlipDao(TestBase):

    def setUp(self):
        self._clear_database_content()


    def test_delivery_slip_blank_creation(self):
        order = self._make_order()
        session().commit()

        try:
            self.delivery_slip_dao.make_delivery_slip_for_order(order.order_id, {}, date.today(), False)
            self.fail()
        except DataException as ex:
            pass


    def test_delivery_slip_creation_invalid_qty(self):

        order = self._make_order()
        order.parts[0].qty = 10
        session().commit()

        try:
            self.delivery_slip_dao.make_delivery_slip_for_order(order.order_id, {order.parts[0].order_part_id : 0}, datetime.now(), False)

            self.fail()
        except DataException as ex:
            pass


    def test_delivery_slip_creation_wrong_part(self):

        # Completely wrong part

        order = self._make_order()
        order.parts[0].qty = 10
        session().commit()

        try:
            self.delivery_slip_dao.make_delivery_slip_for_order(order.order_id, {1321654 : 5}, datetime.now(), False)
            self.fail()
        except DataException as ex:
            pass


        # Mixing two orders

        order2 = self._make_order()
        order2.parts[0].qty = 10
        session().commit()

        try:
            self.delivery_slip_dao.make_delivery_slip_for_order(order.order_id, {order2.parts[0].order_part_id : 5}, datetime.now(), False)
            self.fail()
        except DataException as ex:
            pass


    def test_delivery_slip_creation_too_much_done(self):
        order = self._make_order()
        order.parts[0].qty = 10
        order.parts[0].sell_price = 23
        session().commit()

        self.delivery_slip_dao.make_delivery_slip_for_order(order.order_id, {order.parts[0].order_part_id : 5}, datetime.now(), False)

        assert order.parts[0].tex2 == 5

        try:
            self.delivery_slip_dao.make_delivery_slip_for_order(order.order_id, {order.parts[0].order_part_id : 6}, datetime.now(), False)
            self.fail()
        except DataException as ex:
            pass


    def test_delivery_slip_creation(self):
        order = self._make_order()
        order.parts[0].qty = 10
        order.parts[0].sell_price = 35
        session().commit()

        self.delivery_slip_dao.make_delivery_slip_for_order(order.order_id, {order.parts[0].order_part_id : 5}, datetime.now(), False)

        assert order.parts[0].tex2 == 5

        self.delivery_slip_dao.make_delivery_slip_for_order(order.order_id, {order.parts[0].order_part_id : 3}, datetime.now(), False)
        assert order.parts[0].tex2 == 8

        self.delivery_slip_dao.make_delivery_slip_for_order(order.order_id, {order.parts[0].order_part_id : 2}, datetime.now(), False)
        assert order.parts[0].tex2 == 10

        self.assertEqual(OrderPartStateType.completed, order.parts[0].state)

        # Orders are automatically set to completed whenn all their quantities
        # are complete

        assert order.state == OrderStatusType.order_completed


    def test_delivery_slip_creation_state_as_preorder(self):
        order = self._make_order()

        # Without quantities everything is considered a preorder

        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 2" + chr(233)
        order_part.position = 2
        self._order_part_dao.save(order_part)

        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 3" + chr(233)
        order_part.position = 3
        self._order_part_dao.save(order_part)

        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 4" + chr(233)
        order_part.position = 4
        self._order_part_dao.save(order_part)

        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 5" + chr(233)
        order_part.position = 5
        self._order_part_dao.save(order_part)

        order = self.order_dao.find_by_id(order.order_id)

        self.order_dao.change_order_parts_state(order.order_id, [order.parts[0].order_part_id], OrderPartStateType.production_paused)
        self.order_dao.change_order_parts_state(order.order_id, [order.parts[2].order_part_id], OrderPartStateType.ready_for_production)
        self.order_dao.change_order_parts_state(order.order_id, [order.parts[3].order_part_id], OrderPartStateType.aborted)
        self.order_dao.change_order_parts_state(order.order_id, [order.parts[4].order_part_id], OrderPartStateType.completed)

        assert order.state == OrderStatusType.preorder_definition


    def test_delivery_slip_creation_state(self):
        order = self._make_order()

        # Without quantities everything is considered a preorder

        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 2" + chr(233)
        order_part.position = 2
        order_part.qty = 2
        self._order_part_dao.save(order_part)

        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 3" + chr(233)
        order_part.position = 3
        self._order_part_dao.save(order_part)

        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 4" + chr(233)
        order_part.position = 4
        self._order_part_dao.save(order_part)

        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 5" + chr(233)
        order_part.position = 5
        self._order_part_dao.save(order_part)

        order = self.order_dao.find_by_id(order.order_id)

        self.order_dao.change_order_parts_state(order.order_id, [order.parts[0].order_part_id], OrderPartStateType.production_paused)
        self.order_dao.change_order_parts_state(order.order_id, [order.parts[2].order_part_id], OrderPartStateType.ready_for_production)
        self.order_dao.change_order_parts_state(order.order_id, [order.parts[3].order_part_id], OrderPartStateType.aborted)
        self.order_dao.change_order_parts_state(order.order_id, [order.parts[4].order_part_id], OrderPartStateType.completed)

        self.show_order(order)

        assert order.parts[0].state == OrderPartStateType.production_paused
        assert order.parts[2].state == OrderPartStateType.ready_for_production
        assert order.parts[3].state == OrderPartStateType.aborted
        assert order.parts[4].state == OrderPartStateType.completed

        # All quantities are 0 in the order, so it remains a preorder
        self.assertEqual(OrderStatusType.preorder_definition, order.state)


    def test_part_state_transitions_preorder_to_aborted(self):
        order = self._order_dao.make(u"Test order"+chr(233),self.customer)
        self._order_dao.save(order)
        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 1" + chr(233)
        order_part.position = 1
        self._order_part_dao.save(order_part)

        order.parts[0].qty = 10
        session().commit()

        self.assertEqual(OrderStatusType.preorder_definition, order.state)
        assert order.accounting_label == None
        assert order.preorder_label > 0  # Exact value depends on the test execution order
        assert order.parts[0].state == OrderPartStateType.preorder

        # preorder_definition --> Aborted

        part_ids = [order.parts[0].order_part_id]
        self.order_dao.change_order_parts_state(order.order_id, part_ids, OrderPartStateType.aborted)

        self.assertEqual(OrderStatusType.order_aborted, order.state)
        assert order.accounting_label > 0
        assert order.preorder_label > 0  # Exact value depends on the test execution order
        assert order.parts[0].state == OrderPartStateType.aborted


    def test_part_state_transitions_preorder_to_in_production(self):
        order = self._order_dao.make(u"Test order"+chr(233),self.customer)
        self._order_dao.save(order)
        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 1" + chr(233)
        order_part.position = 1
        self._order_part_dao.save(order_part)
        order.parts[0].qty = 10
        session().commit()

        assert order.preorder_label > 0  # Label didn't change
        assert order.completed_date is None
        preorder_label = order.preorder_label

        # preorder_definition --> in_production

        part_ids = [order.parts[0].order_part_id]
        self.order_dao.change_order_parts_state(order.order_id, part_ids, OrderPartStateType.ready_for_production)
        assert order.accounting_label > 0
        accounting_label = order.accounting_label
        assert order.preorder_label == preorder_label # Label didn't change
        assert order.completed_date is None
        self.assertEqual(OrderStatusType.order_ready_for_production, order.state)

        # in_production --> completed

        self.order_dao.change_order_parts_state(order.order_id, part_ids, OrderPartStateType.completed)
        assert order.preorder_label == preorder_label
        assert order.accounting_label == accounting_label # Label didn't change
        assert order.completed_date == date.today()
        self.assertEqual(OrderStatusType.order_completed, order.state)

        #  completed --> in_production

        self.order_dao.change_order_parts_state(order.order_id, part_ids, OrderPartStateType.ready_for_production)
        assert order.preorder_label == preorder_label
        assert order.accounting_label == accounting_label # Label didn't change
        assert order.completed_date == None
        self.assertEqual(OrderStatusType.order_ready_for_production, order.state)

        # in_production --> preorder

        self.order_dao.change_order_parts_state(order.order_id, part_ids, OrderPartStateType.preorder)

        assert order.preorder_label == preorder_label
        assert order.accounting_label == accounting_label # Label didn't change
        self.assertEqual(OrderStatusType.preorder_definition, order.state)
        assert order.completed_date == None


    def test_part_state_transitions_preorder_to_aborted(self):
        order = self._order_dao.make(u"Test order"+chr(233),self.customer)
        self._order_dao.save(order)
        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 1" + chr(233)
        order_part.position = 1
        self._order_part_dao.save(order_part)
        order.parts[0].qty = 10
        session().commit()

        assert order.preorder_label > 0  # Label didn't change
        assert order.completed_date is None
        preorder_label = order.preorder_label

        # preorder_definition --> aborted (without going in production first)

        part_ids = [order.parts[0].order_part_id]
        self.order_dao.change_order_parts_state(order.order_id, part_ids, OrderPartStateType.aborted)
        self.assertEqual(None,order.accounting_label)
        assert order.preorder_label == preorder_label # Label didn't change
        assert order.completed_date == date.today()
        self.assertEqual(OrderStatusType.order_aborted, order.state)



    def test_part_state_transitions_preorder_back_to_preorder(self):

        order = self._order_dao.make(u"Test order"+chr(233),self.customer)
        self._order_dao.save(order)
        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 1" + chr(233)
        order_part.position = 1
        self._order_part_dao.save(order_part)
        order.parts[0].qty = 10
        session().commit()

        assert order.preorder_label > 0  # Label was set
        assert order.completed_date is None
        assert order_part.state == OrderPartStateType.preorder
        preorder_label = order.preorder_label

        part_ids = [order.parts[0].order_part_id]
        self.order_dao.change_order_parts_state(order.order_id, part_ids, OrderPartStateType.production_paused)

        assert order.preorder_label == preorder_label # Label didn't change
        assert order.completed_date == None
        assert order.state == OrderStatusType.order_production_paused
        assert order_part.state == OrderPartStateType.production_paused
        assert order_part.completed_date == None



    def test_part_state_transitions_preorder_back_to_preorder_via_production(self):

        order = self._order_dao.make(u"Test order"+chr(233),self.customer)
        self._order_dao.save(order)
        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 1" + chr(233)
        order_part.position = 1
        self._order_part_dao.save(order_part)
        order.parts[0].qty = 10
        session().commit()

        assert order.preorder_label > 0  # Label was set
        assert order.completed_date is None
        assert order_part.state == OrderPartStateType.preorder
        preorder_label = order.preorder_label

        part_ids = [order.parts[0].order_part_id]
        self.order_dao.change_order_parts_state(order.order_id, part_ids, OrderPartStateType.ready_for_production)
        assert order.preorder_label == preorder_label # Label didn't change
        assert order.completed_date == None
        assert order.state == OrderStatusType.order_ready_for_production
        assert order_part.state == OrderPartStateType.ready_for_production
        assert order_part.completed_date == None



    def test_part_state_transitions_preorder_back_to_preorder_via_aborted(self):

        order = self._order_dao.make(u"Test order"+chr(233),self.customer)
        self._order_dao.save(order)
        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 1" + chr(233)
        order_part.position = 1
        self._order_part_dao.save(order_part)
        order.parts[0].qty = 10
        session().commit()

        assert order.preorder_label > 0  # Label was set
        assert order.completed_date is None
        assert order_part.state == OrderPartStateType.preorder
        preorder_label = order.preorder_label

        part_ids = [order.parts[0].order_part_id]
        self.order_dao.change_order_parts_state(order.order_id, part_ids, OrderPartStateType.aborted)
        assert order.preorder_label == preorder_label # Label didn't change
        assert order.completed_date == date.today()
        assert order.state == OrderStatusType.order_aborted
        assert order_part.state == OrderPartStateType.aborted
        assert order_part.completed_date == date.today()


    @skip("We don't use the sell price of delivery slip anymore")
    def test_sell_price_unmodifiable(self):
        order = self._make_order()
        order.parts[0].qty = 10
        order.parts[0].sell_price = 23
        session().commit()

        now = datetime.now()
        delivery_slip_id = self.delivery_slip_dao.make_delivery_slip_for_order(order.order_id, {order.parts[0].order_part_id : 5}, now, False)

        to_bill, encours_this_month, encours_previous_month, turnover = dao.order_dao.compute_turnover_on(now)

        ds = dao.delivery_slip_part_dao.find_by_id(delivery_slip_id)

        assert order.parts[0].tex2 == 5
        assert ds.delivery_slip_parts[0].sell_price == 5 * order.parts[0].sell_price

        # Now we change the order part price

        order.parts[0].sell_price = 12
        session().commit()

        # And check the the price associated to the delivery slip
        # didn't change

        ds = dao.delivery_slip_part_dao.find_by_id(delivery_slip_id)
        assert ds.delivery_slip_parts[0].sell_price == 5 * 23 # the price before the change
        to_bill2, encours_this_month2, encours_previous_month2, turnover2 = dao.order_dao.compute_turnover_on(now)

        # to_bill must not change because the sell price is
        # rememebered in the delivery slip
        assert to_bill == to_bill2

        # no work was done so encours stays 0
        assert encours_this_month == 0
        assert encours_previous_month == 0
        assert turnover == to_bill2


    def test_parts_for_view(self):
        order = self._make_order()
        order.parts[0].description = "ABC"
        order.parts[0].qty = 10
        order.parts[0].sell_price = 23
        session().commit()

        now = datetime.now()
        delivery_slip_id = self.delivery_slip_dao.make_delivery_slip_for_order(order.order_id, {order.parts[0].order_part_id : 5}, now, False)

        res = dao.delivery_slip_part_dao.load_slip_parts_frozen(delivery_slip_id)
        assert len(res) == 1
        assert res[0].quantity_out == 5
        assert res[0].description == "ABC"

    def test_one_word_filtered_queries(self):
        res = dao.delivery_slip_part_dao.load_slip_parts_on_filter("124A")

    def test_filtered_queries(self):
        # python -m koi.test.test_delivery_slip_dao TestDeliverySlipDao.test_filtered_queries

        tests = [ "CreationDate In MonthBefore AND customer = \"TAC\"",
                  "CreationDate In (1/1/2013,1/1/2014)",
                  "CreationDate IN CURRENTMONTH",
                  "(CreationDate AFTER 1/1/2014) AND (CreationDate  AFTER 1/2/2014)",
                  "CreationDate AFTER 23/11/2014",
                  "customer = betrand",
                  "customer in betrand, kondor",
                  "DESCRIPTION = \"4000\"",
                  "DESCRIPTION ~ \"4000\"",
                  "SlipActive = false",
                  "SlipActive is true",
                  "SlipActive = false and SlipActive is true" ]

        for test in tests:
            res = dao.delivery_slip_part_dao.load_slip_parts_on_filter(test)


        try:
            dao.delivery_slip_part_dao.load_slip_parts_on_filter("1234567890"*100)
        except DataException as ex:
            assert ex.code == DataException.CRITERIA_IS_TOO_LONG

if __name__ == '__main__':
    unittest.main()
