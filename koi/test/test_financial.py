import math
import datetime
import unittest

from PySide.QtGui import QApplication

from koi.Configurator import mainlog, init_i18n

init_i18n()

from koi.PotentialTasksCache import PotentialTasksCache
from koi.business_charts import ToFacturePerMonthChart
from koi.configuration.business_functions import business_computations_service
from koi.dao import *
from koi.db_mapping import *
from koi.test.test_base import TestBase



class TestFinancial(TestBase):

    @classmethod
    def _make_operation(cls,order_part,opdef,planned_hours=10):
        operation = cls._operation_dao.make()

        pf = None
        if order_part.production_file and len(order_part.production_file) == 1:
            pf = order_part.production_file[0]
        else:
            pf = cls._production_file_dao.make()
            pf.order_part = order_part
            order_part.production_file = [pf]
            session().add(pf)
            session().flush()

        operation.production_file = pf
        operation.description = u"operation desc-" + str(len(pf.operations)) + chr(233)
        operation.operation_model = opdef
        operation.planned_hours = planned_hours
        session().add(operation)


    @classmethod
    def createOrderWithoutWork(cls):
        order = cls._order_dao.make(u"Test order without work "+chr(233),cls.customer)
        order.state = OrderStatusType.order_ready_for_production
        cls._order_dao.save(order)

        order_part = cls._order_part_dao.make(order)
        order_part.description = u"Part 1 with work"
        order_part.position = 1
        order_part.sell_price = 100
        order_part.qty = 7
        cls._order_part_dao.save(order_part)

        cls._make_operation(order_part, cls.opdef_op)
        cls._make_operation(order_part, cls.opdef_op)

        order_part = cls._order_part_dao.make(order)
        order_part.description = u"Part 2" + chr(233)
        order_part.position = 2
        order_part.sell_price = 111
        order_part.qty = 19
        cls._order_part_dao.save(order_part)

        cls._make_operation(order_part, cls.opdef_op)
        cls._make_operation(order_part, cls.opdef_op)

        session().refresh(order)

        order_part = cls._order_part_dao.make(order)
        order_part.description = u"Part 3" + chr(233)
        order_part.position = 3
        order_part.sell_price = 23
        order_part.qty = 3
        cls._order_part_dao.save(order_part)

        session().commit()
        return order


    @classmethod
    def createOrderWithHours(cls,base_month=3):
        order = cls.createOrderWithoutWork()
        order.description = "Order with hours"

        d = date(2012,10,21)
        cache = PotentialTasksCache(cls.task_dao,d)

        task = cache.tasks_for_identifier(order.parts[0].operations[0])[0]
        session().add(task)
        session().flush()
        mainlog.debug(task)
        tt = cls._make_timetrack(task.task_id,datetime(2012,base_month,1),11)
        session().add(tt)
        session().flush()
        tt = cls._make_timetrack(task.task_id,datetime(2012,base_month,2),13)
        session().add(tt)
        session().flush()

        task = cache.tasks_for_identifier(order.parts[0].operations[1])[0]
        session().add(task)
        session().flush()
        mainlog.debug(task)
        tt = cls._make_timetrack(task.task_id,datetime(2012,base_month+1,15),23)
        session().add(tt)
        session().flush()

        task = cache.tasks_for_identifier(order.parts[1].operations[0])[0]
        session().add(task)
        session().flush()
        mainlog.debug(task)
        tt = cls._make_timetrack(task.task_id,datetime(2012,base_month+1,15),23)
        session().add(tt)
        session().flush()

        return order


    @classmethod
    def createOrderWithWork(cls):
        order = cls.createOrderWithHours(base_month=4)
        order.description = "Order with hours and work done"

        # First delivery

        # ds1 = DeliverySlipPart()
        # ds1.order_part = order.parts[0]
        # ds1.quantity_out = 2

        # ds2 = DeliverySlipPart()
        # ds2.order_part = order.parts[1]
        # ds2.quantity_out = 3

        # cls.delivery_slip1 = dao.delivery_slip_part_dao.save([ds1,ds2], date(2012,3,20))

        # I use time because no two delivey slips can be issues
        # simultaneously
        n = datetime.now()
        cls.delivery_slip1 = dao.delivery_slip_part_dao.make_delivery_slip_for_order(order.order_id, {order.parts[0].order_part_id : 2, order.parts[1].order_part_id : 3}, datetime(2012,3,20,n.hour,n.minute,n.second,n.microsecond), False)




        # Second delivery

        # ds3 = DeliverySlipPart()
        # ds3.order_part = order.parts[0]
        # ds3.quantity_out = 5
        # dao.delivery_slip_part_dao.save([ds3], date(2012,4,21))

        dao.delivery_slip_part_dao.make_delivery_slip_for_order(order.order_id, {order.parts[0].order_part_id : 5}, datetime(2012,4,21), False)


        # Third

        # ds4 = DeliverySlipPart()
        # ds4.order_part = order.parts[1]
        # ds4.quantity_out = 7
        # dao.delivery_slip_part_dao.save([ds4], date(2012,5,22))

        dao.delivery_slip_part_dao.make_delivery_slip_for_order(order.order_id, {order.parts[1].order_part_id : 7}, datetime(2012,5,22), False)

        return order

    # @classmethod
    # def _clear_database_content(cls):
    #     session().query(MonthTimeSynthesis).delete()
    #     session().query(TaskActionReport).delete()
    #     session().query(TaskActionReport).delete()
    #     session().query(TimeTrack).delete()
    #     session().query(TaskOnNonBillable).delete()
    #     session().query(TaskOnOperation).delete()
    #     session().query(TaskOnOrder).delete()
    #     session().query(TaskForPresence).delete()
    #     session().query(DayTimeSynthesis).delete()
    #     session().query(DeliverySlipPart).delete()

    #     for ds in session().query(DeliverySlip).order_by(desc(DeliverySlip.delivery_slip_id)):
    #         session().delete(ds)
    #     # session().query(DeliverySlip).delete()
    #     session().query(Operation).delete()
    #     session().query(ProductionFile).delete()
    #     session().query(OrderPart).delete()

    #     for order in session().query(Order).order_by(desc(Order.accounting_label)).all():
    #         session().delete(order)

    #     # db_mapping.session().query(Task).delete()
    #     session().commit()

    # @classmethod
    # def _clear_database_basic_content(cls):
    #     session().query(OperationDefinitionPeriod).delete()
    #     session().query(OperationDefinition).delete()
    #     session().query(Operation).delete()
    #     session().query(Employee).delete()
    #     session().query(Customer).delete()

    @classmethod
    def tearDownClass(cls):
        pass
        # cls._clear_database_content()
        # cls._clear_database_basic_content()

    @classmethod
    def setUpClass(cls):
        super(TestFinancial,cls).setUpClass()
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        cls.app = app


    def setUp(self):
        # mainlog.setLevel(logging.DEBUG)

        # super(TestFinancial,self).setUp()
        self.order_without_work = self.createOrderWithoutWork()
        self.order_with_hours = self.createOrderWithHours()
        self.order_with_work = self.createOrderWithWork()
        self.order_in_the_future = self.createOrderWithHours(base_month=11)
        self.order_in_the_future.description = "Order in the future"
        session().commit()

    def tearDown(self):
        self._clear_database_content()




    # def test_direct_hours(self):
    #     self.assertEqual(0,self.dao.order_dao.compute_worked_direct_hours_on(date(2012,2,21)))
    #     self.assertEqual(24.0,self.dao.order_dao.compute_worked_direct_hours_on(date(2012,3,21)))
    #     self.assertEqual(70.0,self.dao.order_dao.compute_worked_direct_hours_on(date(2012,4,21)))
    #     self.assertEqual(46.0,self.dao.order_dao.compute_worked_direct_hours_on(date(2012,5,21)))
    #     self.assertEqual(0,self.dao.order_dao.compute_worked_direct_hours_on(date(2012,6,21)))


    # def test_compute_estimated_hours_for_unfinished_orders_on(self):
    #     mainlog.setLevel(logging.DEBUG)

    #     mainlog.debug("-"*80)
    #     self.show_order(self.order_with_hours) # 7 x (10h+10h) + 19 x (10h+10h) = 26x20 = 520h
    #     mainlog.debug("-"*80)
    #     self.show_order(self.order_with_work) # 19 - (3+7) = 10 x (10h+10h) = 200h

    #     for tt in session().query(TimeTrack).all():
    #         mainlog.debug(tt)

    #     self.assertEqual(0,self.dao.order_dao.compute_estimated_hours_for_unfinished_orders_on(date(2012,2,21)))
    #     self.assertEqual(520,self.dao.order_dao.compute_estimated_hours_for_unfinished_orders_on(date(2012,3,21)))
    #     self.assertEqual(520,self.dao.order_dao.compute_estimated_hours_for_unfinished_orders_on(date(2012,4,21)))
    #     self.assertEqual(1040,self.dao.order_dao.compute_estimated_hours_for_unfinished_orders_on(date(2012,5,21)))
    #     self.assertEqual(1040,self.dao.order_dao.compute_estimated_hours_for_unfinished_orders_on(date(2012,6,21)))
    #     self.assertEqual(1040,self.dao.order_dao.compute_estimated_hours_for_unfinished_orders_on(date(2012,7,21)))
    #     self.assertEqual(1560,self.dao.order_dao.compute_estimated_hours_for_unfinished_orders_on(date(2012,11,21)))

    # def test_compute_finished_orders_value_on(self):
    #     self.show_order(self.order_with_work) # 19 - (3+7) = 10 x (10h+10h) = 200h

    #     self.assertEqual(0,self.dao.order_dao.compute_finished_orders_value_on(date(2012,2,21)))
    #     self.assertEqual(0,self.dao.order_dao.compute_finished_orders_value_on(date(2012,3,21)))
    #     self.assertEqual(100*7+111*10,self.dao.order_dao.compute_finished_orders_value_on(date(2012,4,21)))
    #     self.assertEqual(0,self.dao.order_dao.compute_finished_orders_value_on(date(2012,5,21)))
    #     self.assertEqual(0,self.dao.order_dao.compute_finished_orders_value_on(date(2012,6,21)))

    # def test_encours2(self):
    #     month_date = datetime(2012,5,28)
    #     date_end = datetime(2012,5,28)

    #     tsubq = dao.order_dao._order_parts_worked_hours(date_end)
    #     qsubq = dao.order_dao._order_parts_quantity_done(date_end)
    #     active_orders = dao.order_dao._started_but_unfinished_orders_subquery(date_end)

    #     # Pay attention, although orders selected above are started and unfinished,
    #     # it is quite possible that some of their order parts are not started
    #     # or finished. Because of that, we have to filter out those parts.
    #     # Note that this  filter out is already, in some way, done in the
    #     # qsubq subquery. Note also that this filtering is not 100% necessary
    #     # as the encours function will take care of those special cases.
    #     # So I add the filter with the goal of being more accurate in the
    #     # query (it doesn't make it more correct)

    #     query = session().query(OrderPart.order_part_id,
    #                             OrderPart.qty,
    #                             qsubq.c.part_qty_out,
    #                             tsubq.c.part_worked_hours,
    #                             OrderPart.sell_price,
    #                             OrderPart.total_estimated_time.label("a_estimated_time"),
    #                             OrderPart.material_value.label("a_material_value"),
    #                             OrderPart.order_id,
    #                             OrderPart.label).\
    #         select_from(OrderPart).\
    #         join(tsubq, tsubq.c.order_part_id == OrderPart.order_part_id).\
    #         join(qsubq, qsubq.c.order_part_id == OrderPart.order_part_id).\
    #         join(active_orders, active_orders.c.order_id == OrderPart.order_id).\
    #         filter( and_(tsubq.c.part_worked_hours > 0,
    #                      qsubq.c.part_qty_out < OrderPart.qty))

    #     mainlog.debug("tsubq "*8)
    #     for x in session().query(tsubq).all():
    #         mainlog.debug(x)
    #     mainlog.debug("."*80)

    #     mainlog.debug("qsubq "*8)
    #     for x in session().query(qsubq).all():
    #         mainlog.debug(x)
    #     mainlog.debug("."*80)

    #     mainlog.debug("#"*8)
    #     for x in session().query(self.dao.order_dao._aggregated_orders_data_up_to(date_end)).all():
    #         mainlog.debug(x)
    #     mainlog.debug("#"*8)

    #     mainlog.debug("/"*8)
    #     for x in session().query(active_orders).all():
    #         mainlog.debug(x)
    #     mainlog.debug("/"*8)

    #     mainlog.debug("!!!"*8)
    #     for x in query.all():
    #         mainlog.debug(x)
    #     mainlog.debug("!!!"*8)


    def test_turnover_computations(self):

        self.show_order(self.order_with_hours) # 7 x (10h+10h) + 19 x (10h+10h) = 26x20 = 520h
        self.show_order(self.order_with_work) # 19 - (3+7) = 10 x (10h+10h) = 200h

        # for tt in session().query(TimeTrack).all():
        #     mainlog.debug(tt)

        # to_facture, encours_this_month, encours_previous_month, turnover
        assert (0,0,0,0) == dao.order_dao.compute_turnover_on(date(2012,2,28))
        self.assertEqual( (2*100+3*111,120,0,2*100+3*111 + 120 - 0),
                          dao.order_dao.compute_turnover_on(date(2012,3,28)))
        self.assertEqual( (100*5,362.65,120,500 + 362.65 - 120), dao.order_dao.compute_turnover_on(date(2012,4,28)))
        self.assertEqualEpsilon( (111*7,423.1157,362.65, 111*7 + 423.1157 - 362.65), dao.order_dao.compute_turnover_on(date(2012,5,28)))
        self.assertEqualEpsilon( (0,423.1157,423.1157, 0), dao.order_dao.compute_turnover_on(date(2012,6,28)))




    def test_deactivate_delivery_slip(self):
        """ Make sure deactivated slips change to bill amounts.
        """

        # return to_facture, encours_this_month, encours_previous_month, turnover

        # Test active slip

        slip = dao.delivery_slip_part_dao.find_by_id(self.delivery_slip1)
        assert slip.active == True
        self.assertEqual(7, self.order_with_work.parts[0].tex2)
        self.assertEqual(10, self.order_with_work.parts[1].tex2)

        self.assertEqualEpsilon( (2*self.order_with_work.parts[0].sell_price + 3*self.order_with_work.parts[1].sell_price, 120, 0, 653),
                                 dao.order_dao.compute_turnover_on(date(2012,3,28)))

        # Test deactivated slip

        dao.delivery_slip_part_dao.deactivate(self.delivery_slip1)

        slip = dao.delivery_slip_part_dao.find_by_id(self.delivery_slip1)

        assert slip.active == False
        self.assertEqual(5, self.order_with_work.parts[0].tex2)
        self.assertEqual(7, self.order_with_work.parts[1].tex2)

        # to_bill, encours_this_month, encours_previous_month, turnover

        # Check to bill amount and encours are modified

        self.assertEqualEpsilon( (0*(2*100+3*111), 120, 0, 0*(2*100+3*111) + 120 - 0),
                                 dao.order_dao.compute_turnover_on(date(2012,3,28)))



    def test_deactivate_delivery_slip_charts(self):
        """ Make sure deactivated slips change to bill amounts.
        """

        # python test_financial.py TestFinancial.test_deactivate_delivery_slip_charts

        slip = dao.delivery_slip_part_dao.find_by_id(self.delivery_slip1)
        assert slip.active == True

        chart = ToFacturePerMonthChart(None, self.remote_indicators_service)
        chart._gather_data(date(2012,1,1),date(2012,12,31))

        self.assertEqual([[0,
                           0,
                           float(2*self.order_with_work.parts[0].sell_price + 3*self.order_with_work.parts[1].sell_price),
                           500,
                           777,0,0,0,0,0,0,0],
                          [0,0,4431.0, 2975.1, 1455.9,0,0,0,0,0,0,0],
                          [0,0,0.0, 0.0, 0.0,0,0,0,0,0,0,0]],
                         chart.chart.data)

        # Deactivate the delivery slip now
        dao.delivery_slip_part_dao.deactivate(self.delivery_slip1)
        slip = dao.delivery_slip_part_dao.find_by_id(self.delivery_slip1)
        assert slip.active == False
        self.remote_indicators_service.clear_caches()

        chart._gather_data(date(2012,1,1),date(2012,12,31))


        mainlog.debug("- "*80)
        mainlog.debug(slip)
        # We in fact cleared the first month of the query by deactivating the first slip
        # To bill"),_("Actual cost"),_("Planned cost
        self.assertEqual([[0, 0, 0, 5*self.order_with_work.parts[0].sell_price, 777, 0, 0, 0, 0, 0, 0, 0],
                          [0, 0, 0, 2975.1, 1455.9, 0, 0, 0, 0, 0, 0, 0],
                          [0.0, 0.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]],
                         chart.chart.data)



    def test_compute_encours(self):
        n = date(2012,2,28)
        assert 0 == dao.order_dao.compute_encours_for_month(n)

        n = date(2012,4,28)
        self.assertEqual( 362.65, dao.order_dao.compute_encours_for_month(n))


    def test_encours_function(self):

        enc = business_computations_service.encours_on_params # shortcut
        o = self.order_with_work.parts[0]
        d = date.today()

        # zero hours done = zero valuation
        self.assertEqual( 0, enc(0,10,hours_consumed=0,hours_planned=10,unit_price=1,material_price=1,order_part_id=o.order_part_id,ref_date=d))
        self.assertEqual( 0, enc(3,10,hours_consumed=0,hours_planned=10,unit_price=1,material_price=1,order_part_id=o.order_part_id,ref_date=d))

        # nothing produced but all hours or more consumed
        self.assertEqual( 9, enc(0,10,hours_consumed=10,hours_planned=10,unit_price=1,material_price=1,order_part_id=o.order_part_id,ref_date=d))
        self.assertEqual( 9, enc(0,10,hours_consumed=20,hours_planned=10,unit_price=1,material_price=1,order_part_id=o.order_part_id,ref_date=d))

        # all was produced => zero valuation
        self.assertEqual( 0, enc(10,10,hours_consumed=10,hours_planned=10,unit_price=1,material_price=1,order_part_id=o.order_part_id,ref_date=d))

        # hours done but unit price is zero => we estimate based on operations
        self.assertEqual( (11+13+23) * 63.3, enc(0,10,hours_consumed=5,hours_planned=10,unit_price=0,material_price=1,order_part_id=o.order_part_id,ref_date=d))

        self.assertEqual( (11) * 63.3, enc(0,10,hours_consumed=5,hours_planned=10,unit_price=0,material_price=1,order_part_id=o.order_part_id,ref_date=date(2012,4,1)))


    def test_value_work_on_order_part_up_to_date(self):
        d = date(2011,2,28)
        v = dao.order_part_dao.value_work_on_order_part_up_to_date(self.order_with_work.parts[0].order_part_id, d)
        assert v == 0

        d = date(2012,4,28)
        v = dao.order_part_dao.value_work_on_order_part_up_to_date(self.order_with_work.parts[0].order_part_id, d)
        self.assertEqualEpsilon( 24 * 63.3, v)

    def test_value_work_on_order_part_up_to_date_with_operation_cost_change(self):
        period = OperationDefinitionPeriod()
        period.start_date = date(2012,4,2)
        period.cost = 10
        dao.operation_definition_dao.add_period(period, self.opdef_op)
        session().commit()

        d = date(2012,4,28)
        v = dao.order_part_dao.value_work_on_order_part_up_to_date(self.order_with_work.parts[0].order_part_id, d)
        self.assertEqual( 11 * 63.3 + 13 * 10, v)


    def test_encours_coherence(self):

        self.show_order( self.order_with_work)
        self.show_order( self.order_without_work)
        self.show_order( self.order_with_hours)

        # Right before the first work was done
        n = date(2012,2,28)
        encours = dao.order_dao.compute_encours_for_month(n)
        assert 0 == encours
        r = self.remote_indicators_service.valution_production_chart(None, n)
        mainlog.debug(r.data)
        assert encours == r.data[0][-1]

        n = date(2012, 3, 31)
        encours = dao.order_dao.compute_encours_for_month(n)
        mainlog.debug(encours)
        assert 120 == encours
        r = self.remote_indicators_service.valution_production_chart(None, n)
        mainlog.debug(r.data)
        assert encours == r.data[0][-1]

        n = date(2012,4,30)
        encours = dao.order_dao.compute_encours_for_month(n)
        assert 362.65 == encours
        r = self.remote_indicators_service.valution_production_chart(None, n)
        mainlog.debug(r.data)
        assert encours == r.data[0][-1]


        n = date(2012, 5, 31)
        encours = dao.order_dao.compute_encours_for_month(n)
        r = self.remote_indicators_service.valution_production_chart(None, n)
        mainlog.debug(encours)
        mainlog.debug(r.data)
        assert math.fabs(423.11 -encours) < 0.01
        assert encours == r.data[0][-1]

        # Make sure the valuation computation is stable when date changes
        old_valuation = None
        for i in range(30*12):
            n = date(2012, 1, 1) + timedelta(days=i)
            r = self.remote_indicators_service.valution_production_chart(
                    date(2012, 1, 1),
                    n)
            if old_valuation is not None:
                # mainlog.debug(r.data[0])
                # mainlog.debug("{} =? {}".format(old_valuation, r.data[0][-2]))
                assert r.data[0][-2] == old_valuation
            old_valuation = r.data[0][-1]

            # Last day of month ?
            if (n + timedelta(days=1)).day == 1:
                # Yep, so check other valuation functions
                valuation = dao.order_dao.compute_encours_for_month(n)
                assert valuation == r.data[0][-1]

                to_bill, encours_this_month, encours_previous_month, turnover = dao.order_dao.compute_turnover_on( n)
                assert encours_this_month == r.data[0][-1]

if __name__ == '__main__':
    unittest.main()
