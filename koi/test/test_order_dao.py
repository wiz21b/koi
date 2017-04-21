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
from koi.EditTimeTracksDialog import ImputableProxy,TaskOnOrderProxy,TaskOnOperationProxy
from koi.datalayer.order_part_dao import OrderPartDAO
from koi.Configurator import mainlog

class TestOrderDao(TestBase):

    def setUp(self):
        self._clear_database_content()


    def test_previous_active_order(self):
        active_order_id = self.order_dao.active_order_before(100)
        self.assertEqual(None, active_order_id)

        order = self._make_order()

        active_order_id = self.order_dao.active_order_before(100)
        self.assertEqual(None, active_order_id)

        active_order_id = self.order_dao.active_order_before(order.order_id)
        self.assertEqual(None, active_order_id)

        order.state = OrderStatusType.order_ready_for_production
        session().commit()

        active_order_id = self.order_dao.active_order_before(order.order_id)
        self.assertEqual(None, active_order_id)

        order2 = self._make_order()
        order2.state = OrderStatusType.order_ready_for_production
        session().commit()

        # We'll check the locks so avoid reopening locks on
        # accessing orders' id fields

        order_id = order.order_id
        order2_id = order2.order_id

        active_order_id = self.order_dao.active_order_before(order_id)
        self.assertEqual(order2_id, active_order_id)

        active_order_id = self.order_dao.active_order_before(order2_id)
        self.assertEqual(order_id, active_order_id)

        self.assertTrue( self._pg_locks() < 3)

        # Check multiple rows

        order3 = self._make_order()
        order3.state = OrderStatusType.order_ready_for_production
        session().commit()

        self.assertEqual(order3.order_id, self.order_dao.active_order_before(order_id))
        self.assertEqual(order.order_id,  self.order_dao.active_order_before(order2_id))
        self.assertEqual(order2.order_id, self.order_dao.active_order_before(order3.order_id))

    def test_next_active_order(self):
        active_order_id = self.order_dao.active_order_after(100)
        self.assertEqual(None, active_order_id)

        order = self._make_order()

        active_order_id = self.order_dao.active_order_after(100)
        self.assertEqual(None, active_order_id)

        active_order_id = self.order_dao.active_order_after(order.order_id)
        self.assertEqual(None, active_order_id)

        order.state = OrderStatusType.order_ready_for_production
        session().commit()

        active_order_id = self.order_dao.active_order_after(order.order_id)
        self.assertEqual(None, active_order_id)

        order2 = self._make_order()
        order2.state = OrderStatusType.order_ready_for_production
        session().commit()

        # We'll check the locks so avoid reopening locks on
        # accessing orders' id fields

        order_id = order.order_id
        order2_id = order2.order_id

        active_order_id = self.order_dao.active_order_after(order_id)
        self.assertEqual(order2_id, active_order_id)

        active_order_id = self.order_dao.active_order_after(order2_id)
        self.assertEqual(order_id, active_order_id)

        self.assertTrue( self._pg_locks() < 3)

        # Check multiple rows

        order3 = self._make_order()
        order3.state = OrderStatusType.order_ready_for_production
        session().commit()

        self.assertEqual(order2_id, self.order_dao.active_order_after(order_id))
        self.assertEqual(order3.order_id, self.order_dao.active_order_after(order2_id))
        self.assertEqual(order_id, self.order_dao.active_order_after(order3.order_id))


    def test_customer_order_before(self):
        customer_id = self.customer.customer_id

        active_order_id = self.order_dao.customer_order_before(100,customer_id)
        self.assertEqual(None, active_order_id)

        order = self._make_order()

        active_order_id = self.order_dao.customer_order_before(100,customer_id)
        self.assertEqual(order.order_id, active_order_id)

        active_order_id = self.order_dao.customer_order_before(order.order_id,customer_id)
        self.assertEqual(None, active_order_id)

        order.state = OrderStatusType.order_ready_for_production
        session().commit()

        active_order_id = self.order_dao.customer_order_before(order.order_id,customer_id)
        self.assertEqual(None, active_order_id)

        order2 = self._make_order()
        order2.state = OrderStatusType.order_ready_for_production
        session().commit()

        # We'll check the locks so avoid reopening locks on
        # accessing orders' id fields

        order_id = order.order_id
        order2_id = order2.order_id

        active_order_id = self.order_dao.customer_order_before(order_id,customer_id)
        self.assertEqual(order2_id, active_order_id)

        active_order_id = self.order_dao.customer_order_before(order2_id,customer_id)
        self.assertEqual(order_id, active_order_id)

        self.assertTrue( self._pg_locks() < 3)

        # Check multiple rows

        order3 = self._make_order()
        order3.state = OrderStatusType.order_ready_for_production
        session().commit()

        self.assertEqual(order3.order_id, self.order_dao.customer_order_before(order_id,customer_id))
        self.assertEqual(order.order_id, self.order_dao.customer_order_before(order2_id,customer_id))
        self.assertEqual(order2.order_id, self.order_dao.customer_order_before(order3.order_id,customer_id))



    def test_customer_order_after(self):
        customer_id = self.customer.customer_id

        active_order_id = self.order_dao.customer_order_after(100,customer_id)
        self.assertEqual(None, active_order_id)

        order = self._make_order()

        active_order_id = self.order_dao.customer_order_after(100,customer_id)
        self.assertEqual(order.order_id, active_order_id)

        active_order_id = self.order_dao.customer_order_after(order.order_id,customer_id)
        self.assertEqual(None, active_order_id)

        order.state = OrderStatusType.order_ready_for_production
        session().commit()

        active_order_id = self.order_dao.customer_order_after(order.order_id,customer_id)
        self.assertEqual(None, active_order_id)

        order2 = self._make_order()
        order2.state = OrderStatusType.order_ready_for_production
        session().commit()

        # We'll check the locks so avoid reopening locks on
        # accessing orders' id fields

        order_id = order.order_id
        order2_id = order2.order_id

        active_order_id = self.order_dao.customer_order_after(order_id,customer_id)
        self.assertEqual(order2_id, active_order_id)

        active_order_id = self.order_dao.customer_order_after(order2_id,customer_id)
        self.assertEqual(order_id, active_order_id)

        self.assertTrue( self._pg_locks() < 3)

        # Check multiple rows

        order3 = self._make_order()
        order3.state = OrderStatusType.order_ready_for_production
        session().commit()

        self.assertEqual(order2_id, self.order_dao.customer_order_after(order_id,customer_id))
        self.assertEqual(order3.order_id, self.order_dao.customer_order_after(order2_id,customer_id))
        self.assertEqual(order_id, self.order_dao.customer_order_after(order3.order_id,customer_id))


    def test_order_parts_for_monthly_report(self):
        d = date.today()
        now = datetime( d.year-1, d.month, 1)

        order = self._make_order()
        order.creation_date = now.date()
        order.parts[0].qty = 16
        order.parts[0].sell_price = 23
        session().commit()


        dao.order_dao.change_order_state(order.order_id, OrderStatusType.order_ready_for_production)


        self.add_work_on_order_part(order.parts[0],now)
        session().commit()

        delivery_slip_id = self.delivery_slip_dao.make_delivery_slip_for_order(order.order_id, {order.parts[0].order_part_id : 1}, now, False)
        delivery_slip_id = self.delivery_slip_dao.make_delivery_slip_for_order(order.order_id, {order.parts[0].order_part_id : 2}, now + timedelta(2), False)
        delivery_slip_id = self.delivery_slip_dao.make_delivery_slip_for_order(order.order_id, {order.parts[0].order_part_id : 4}, now + timedelta(33), False)

        mainlog.debug(now + timedelta(33))

        delivery_slip_id = self.delivery_slip_dao.make_delivery_slip_for_order(order.order_id, {order.parts[0].order_part_id : 8}, now + timedelta(64), False)

        result = dao.order_dao.order_parts_for_monthly_report(now + timedelta(65))

        mainlog.debug(result)

        self.assertEqual( 8 * order.parts[0].sell_price, result[0].bill_this_month)
        self.assertEqual( 16 * order.parts[0].sell_price, result[0].total_sell_price)
        assert result[0].part_qty_out == 15

        old_unit_price = order.parts[0].sell_price
        order.parts[0].sell_price = 44
        session().commit()

        # Changing the price *DOES* affect the past computations
        result = dao.order_dao.order_parts_for_monthly_report(now + timedelta(65))
        self.assertEqual( 8 * 44, result[0].bill_this_month)
        self.assertEqual( 16 * 44, result[0].total_sell_price)
        assert result[0].part_qty_out == 15

        # Create a new slip, it will use the new price as well
        delivery_slip_id = self.delivery_slip_dao.make_delivery_slip_for_order(order.order_id,
                                                                               {order.parts[0].order_part_id : 1},
                                                                               now + timedelta(seconds=1), False)

        self.show_order(order)
        result = dao.order_dao.order_parts_for_monthly_report(now+timedelta(65))
        self.assertEqual(16, result[0].part_qty_out)
        self.assertEqual(8*44, result[0].bill_this_month)


    def test_load_order_parts_overview(self):

        d = date(2014,1,1)

        assert [] == dao.order_dao.load_order_parts_overview(d, OrderPartDAO.ORDER_PART_SELECTION_ACTIVE_ORDERS)

        # FIXME should use asserts :-)

        dao.order_dao.load_order_parts_overview(d, OrderPartDAO.ORDER_PART_SELECTION_ACTIVE_ORDERS)
        dao.order_dao.load_order_parts_overview(d, OrderPartDAO.ORDER_PART_SELECTION_PREORDERS)
        dao.order_dao.load_order_parts_overview(d, OrderPartDAO.ORDER_PART_SELECTION_ON_HOLD)
        dao.order_dao.load_order_parts_overview(d, OrderPartDAO.ORDER_PART_SELECTION_COMPLETED_THIS_MONTH)
        dao.order_dao.load_order_parts_overview(d, OrderPartDAO.ORDER_PART_SELECTION_ABORTED_THIS_MONTH)


    def test_load_order_parts_on_filter(self):
        assert [] == dao.order_dao.load_order_parts_on_filter("CLIENT = TAC")


    def test_find_by_customer_order_name(self):
        assert [] == dao.order_dao.find_by_customer_order_name("")

    def test_find_by_customer_name(self):

        assert [] == dao.order_dao.find_by_customer_name("")

        order = self._make_order()
        session().commit()

        self.assertEqual( [], dao.order_dao.find_by_customer_name(""))
        assert [] == dao.order_dao.find_by_customer_name("ZZZ")
        assert order.order_id == dao.order_dao.find_by_customer_name(self.customer.fullname)[0].order_id


    def test_encours_and_migrate_qty(self):
        order = self._make_order()
        order.creation_date = date(2000,1,1)
        order.parts[0]._tex = 123
        order.parts[0].qty = 24+order.parts[0]._tex
        order.parts[0].sell_price = 10
        session().commit()

        delivery_slip_id = self.delivery_slip_dao.make_delivery_slip_for_order(order.order_id, {order.parts[0].order_part_id : 3}, datetime(2014,3,3), False)

        delivery_slip_id = self.delivery_slip_dao.make_delivery_slip_for_order(order.order_id, {order.parts[0].order_part_id : 2}, datetime(2014,2,26), False)

        delivery_slip_id = self.delivery_slip_dao.make_delivery_slip_for_order(order.order_id, {order.parts[0].order_part_id : 7}, datetime(2014,1,31), False)

        delivery_slip_id = self.delivery_slip_dao.make_delivery_slip_for_order(order.order_id, {order.parts[0].order_part_id : 6}, datetime(2013,11,29), False)

        delivery_slip_id = self.delivery_slip_dao.make_delivery_slip_for_order(order.order_id, {order.parts[0].order_part_id : 6}, datetime(2013,11,21), False)

        sq = dao.order_dao._order_parts_quantity_done(date(2014,2,3))
        print((session().query(sq.c.order_part_id,sq.c.part_qty_out).select_from().all()))

        result = dao.order_dao.order_parts_for_monthly_report(date(2014,3,3))
        self.assertEqual( 3 * 10, result[0].bill_this_month)

        self.assertEqual( 3, result[0].part_qty_out - result[0].q_out_last_month)
        self.assertEqual( 123+24, result[0].part_qty_out)

        result = dao.order_dao.order_parts_for_monthly_report(date(2014,2,3))
        self.assertEqual( 2 * 10, result[0].bill_this_month)
        self.assertEqual( 2, result[0].part_qty_out - result[0].q_out_last_month)
        self.assertEqual( 123+21, result[0].part_qty_out)

        result = dao.order_dao.order_parts_for_monthly_report(date(2014,1,3))
        self.assertEqual( 7 * 10, result[0].bill_this_month)
        self.assertEqual( 7, result[0].part_qty_out - result[0].q_out_last_month)
        self.assertEqual( 123+19, result[0].part_qty_out)

        result = dao.order_dao.order_parts_for_monthly_report(date(2013,12,3))
        self.assertEqual( [], result)


        result = dao.order_dao.order_parts_for_monthly_report(date(2013,11,3))

        self.assertEqual( 123+12, result[0].part_qty_out)
        self.assertEqual( 123, result[0].q_out_last_month)
        self.assertEqual( 12 * 10, result[0].bill_this_month)
        self.assertEqual( 12, result[0].part_qty_out - result[0].q_out_last_month)
        self.assertEqual( 123+12, result[0].part_qty_out)


        # 4716
        # Bordereau de livraison n 1102 cree le 3/3/2014
        # A : 3 unites
        # Bordereau de livraison n 1080 cre le 26/2/2014
        # A : 2 unites
        # Bordereau de livraison n 993 cree le 31/1/2014
        # A : 7 unites
        # Bordereau de livraison n 847 cree le 29/11/2013
        # A : 6 unites
        # Bordereau de livraison n 815 cree le 21/11/2013
        # A : 6 unites


if __name__ == '__main__':
    unittest.main()
