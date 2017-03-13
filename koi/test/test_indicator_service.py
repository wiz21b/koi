import unittest
from datetime import timedelta

from koi.base_logging import mainlog
from koi.charts.indicators_service import indicators_service, _standard_period2
from koi.configuration.business_functions import business_computations_service
from koi.dao import dao
from koi.datalayer.database_session import session
from koi.db_mapping import OrderStatusType
from koi.test.test_base import TestBase


class TestOrderOverview(TestBase):

    def test_encours(self):
        begin,end,duration = _standard_period2()
        duration_in_days = 90

        d = begin + timedelta(days=10)
        order = self._make_order()
        order.parts[0].sell_price = 123
        order.parts[0].qty = 12

        part = self._add_part_to_order(order)
        part.sell_price = 123
        part.qty = 12
        session().commit()

        part = self._add_part_to_order(order)
        part.sell_price = 123
        part.qty = 12
        session().commit()

        business_computations_service.transition_order_state( order, OrderStatusType.order_ready_for_production)

        for i in range(1):
            d = begin + timedelta(days=i*3)
            self.add_work_on_order_part( order.parts[i], d)
            self.add_work_on_order_part( order.parts[i], d + timedelta(days=1), duration = 2)
            self.add_work_on_order_part( order.parts[i], d + timedelta(days=32), duration = 5)

            dao.delivery_slip_part_dao.make_delivery_slip_for_order(order.order_id, { order.parts[i].order_part_id : 3 },
                                                                    creation_time=d + timedelta(10), complete_order=False)

        session().commit()



        d = begin
        # d = date(2016,11,1)

        for i in range(32):
            indicators_service.clear_caches()
            # failure 2/12/2016 17:34
            mainlog.debug(" *** {} *** {}".format(i, d))
            data = indicators_service.valution_production_chart(d, d) # graph data
            amount = data.data[-1][-1]

            v2 = indicators_service.valuation_this_month_indicator( d, d) # this month's valuation
            mainlog.debug(v2)

            self.assertEqual(amount, v2)

            d = d + timedelta(days=1)

if __name__ == "__main__":
    unittest.main()
