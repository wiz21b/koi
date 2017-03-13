import unittest
from datetime import date
from datetime import datetime, timedelta

from koi.configuration.business_functions import business_computations_service
from koi.dao import dao
from koi.datalayer.database_session import session
from koi.date_utils import ts_to_date
from koi.db_mapping import TaskActionReport,TaskActionReportType, OrderStatusType, TimeTrack
from koi.machine.machine_mapping import Machine
from koi.machine.machine_service import machine_service
from koi.server.clock_service import ClockService
from koi.server.json_decorator import ServerException,JsonCallWrapper, ServerErrors
from koi.test.test_base import TestBase, mainlog


class TestClockService(TestBase):

    @classmethod
    def setUpClass(cls):
        super(TestClockService,cls).setUpClass()
        cls.server = JsonCallWrapper( ClockService(), JsonCallWrapper.IN_PROCESS_MODE)

    def test_day_in_out(self):
        d1 = datetime(2012,12,31,8)
        d2 = datetime(2012,12,31,9)

        self.server.record_presence(self.employee_id,
                                    d1, "Nostromo", TaskActionReportType.day_in)

        self.server.record_presence(self.employee_id,
                                    d2, "Nostromo", TaskActionReportType.day_out)

        h = self.server.get_person_data( self.employee_id, d1.date())
        self.assertEqual(1, h.presence[3].presence_time)

    def test_record_on_order(self):

        order = self._make_order()
        dao.order_dao.change_order_state(order.order_id, OrderStatusType.order_ready_for_production)
        employee = self._employee()

        operation_id = order.parts[0].operations[0].operation_id

        d1 = datetime(2012,12,31,8)
        self.server.record_pointage_on_order(order.order_id, self.opdef.operation_definition_id, self.employee_id, d1, "Nostromo", TaskActionReportType.start_task, None)

        d2 = datetime(2012,12,31,9)
        self.server.record_pointage_on_order(order.order_id, self.opdef.operation_definition_id, self.employee_id, d2, "Nostromo", TaskActionReportType.stop_task, None)

        d3 = datetime(2012,12,31,10)
        self.server.record_pointage_on_order(order.order_id, self.opdef.operation_definition_id, self.employee_id, d3, "Nostromo", TaskActionReportType.start_task, None)

        d4 = datetime(2012,12,31,11)
        self.server.record_pointage_on_order(order.order_id, self.opdef.operation_definition_id, self.employee_id, d4, "Nostromo", TaskActionReportType.stop_task, None)

        h = self.server.get_person_data( self.employee_id, d1.date())
        mainlog.debug("/// "*50)
        mainlog.debug(h)

        self.assertEqual(3, h.presence[3].presence_time) # From 8 to 11 ==  3 hours


    def test_record_on_operation_no_machine(self):
        order = self._make_order()
        dao.order_dao.change_order_state(order.order_id, OrderStatusType.order_ready_for_production)
        employee = self._employee()

        operation_id = order.parts[0].operations[0].operation_id

        d1 = datetime(2012,12,31,8)
        self.server.record_pointage_on_operation(operation_id, self.employee_id, d1, "Nostromo", TaskActionReportType.start_task, None)

        d2 = datetime(2012,12,31,9)
        self.server.record_pointage_on_operation(operation_id, self.employee_id, d2, "Nostromo", TaskActionReportType.stop_task, None)

        d3 = datetime(2012,12,31,10)
        self.server.record_pointage_on_operation(operation_id, self.employee_id, d3, "Nostromo", TaskActionReportType.start_task, None)

        d4 = datetime(2012,12,31,11)
        self.server.record_pointage_on_operation(operation_id, self.employee_id, d4, "Nostromo", TaskActionReportType.stop_task, None)

        h = self.server.get_person_data( self.employee_id, d1.date())
        mainlog.debug("/// "*50)
        mainlog.debug(h)

        self.assertEqual(3, h.presence[3].presence_time) # From 8 to 11 ==  3 hours



    def test_record_on_operation_definition(self):
        d1 = datetime(2012,12,31,8)

        self.server.record_pointage_on_unbillable( self.opdef.operation_definition_id, self.employee_id,
                                                   d1, "Nostromo", TaskActionReportType.start_task)

        d2 = datetime(2012,12,31,9)
        self.server.record_pointage_on_unbillable( self.opdef.operation_definition_id, self.employee_id,
                                                   d2, "Nostromo", TaskActionReportType.stop_task)

        d3 = datetime(2012,12,31,10)
        self.server.record_pointage_on_unbillable( self.opdef.operation_definition_id, self.employee_id,
                                                   d3, "Nostromo", TaskActionReportType.start_task)

        d4 = datetime(2012,12,31,11)
        self.server.record_pointage_on_unbillable( self.opdef.operation_definition_id, self.employee_id,
                                                   d4, "Nostromo", TaskActionReportType.stop_task)

        ot = self.server.get_ongoing_tasks(self.employee_id, d1 + timedelta(minutes=5) )
        self.assertEqual( 1, len(ot))

        ot = self.server.get_ongoing_tasks(self.employee_id, d4 + timedelta(hours=5) )
        self.assertEqual( 0, len(ot))

        h = self.server.get_person_data(self.employee_id, ts_to_date(d1 - timedelta(days=1)))
        self.assertEqual( 4, len(h.presence))

        for x in h.presence:
            self.assertEqual(0, x.presence_time)

        h = self.server.get_person_data( self.employee_id, d1.date())
        mainlog.debug(h)
        # self.assertEqual([d1,None,None,None], h['presence_begin'])
        # self.assertEqual([d4,None,None,None], h['presence_end'])
        self.assertEqual(3.0, h.presence[3].presence_time) # From 8 to 11 ==  3 hours


    def test_ongoing_tasks_presence_and_task_recording2(self):
        order = self._order_dao.make("Test order",self.customer)
        order.state = OrderStatusType.order_ready_for_production
        self._order_dao.save(order)

        # First report -------------------------------------------

        d1 = datetime(2012,12,31,7)
        self.server.record_pointage_on_order(order.order_id, self.opdef_order.operation_definition_id, self.employee_id,
                                             d1, "Nostromo", TaskActionReportType.start_task)

        ot = self.server.get_ongoing_tasks(self.employee_id, d1 + timedelta(hours=3) )
        task_ids = [int(t.task_id) for t in ot] # FIXME This int sucks, but it hides a very complex bug
        ot = self.server.get_multiple_tasks_data(task_ids)

        # One TAR => one task (no presence here)
        assert len(ot) == 1
        self.assertEqual(self.opdef_order.operation_definition_id, ot[str(task_ids[0])].operation_definition_id)

        # Second report, same task -----------------------------------

        d2 = datetime(2012,12,31,8)
        self.server.record_pointage_on_order(order.order_id, self.opdef_order.operation_definition_id, self.employee_id,
                                             d2, "Nostromo", TaskActionReportType.start_task)

        ot = self.server.get_ongoing_tasks(self.employee_id, d2 + timedelta(hours=3) )
        task_ids = [int(t.task_id) for t in ot] # FIXME This int sucks, but it hides a very complex bug
        ot = self.server.get_multiple_tasks_data(task_ids)


        # One TAR => one task (no presence here)
        assert len(ot) == 1
        self.assertEqual(self.opdef_order.operation_definition_id, ot[str(task_ids[0])].operation_definition_id)

        # Third report -----------------------------------------------

        t1 = datetime(2012,12,31,7,30)

        self.assertEqual(2, len(self.tar_dao.get_reports_for_employee_id_on_date(self.employee_id,t1.date())))

        self.server.record_presence(self.employee_id,
                                    t1, "Nostromo", TaskActionReportType.day_out)

        self.assertEqual(3, len(self.tar_dao.get_reports_for_employee_id_on_date(self.employee_id,t1.date())))

        ot = self.server.get_ongoing_tasks(self.employee_id, t1 + timedelta(seconds=30) )
        assert len(ot) == 0



    def test_ongoing_task(self):

        # In the following the dates are reversed, it's too make
        # things a bit harder :-)

        # A first task (for an order)

        order = self._order_dao.make("Test order",self.customer)
        order.state = OrderStatusType.order_ready_for_production
        self._order_dao.save(order)

        d1 = datetime(2012,12,31,11)

        self.server.record_pointage_on_order(order.order_id, self.opdef_order.operation_definition_id, self.employee_id,
                                             d1, "Nostromo", TaskActionReportType.start_task)


        ot = self.server.get_ongoing_tasks(self.employee_id, d1 + timedelta(hours=3) )

        mainlog.debug("Task action reports")
        for tar in session().query(TaskActionReport).all():
            mainlog.debug(tar)

        self.assertEqual(1,len(ot))

        # A second task

        d2 = datetime(2012,12,31,10)
        # self.clock_server.recordPointage(bc,self.employee_id, datetime.strftime(d2, "%Y%m%dT%H:%M:%S"),"Nostromo")

        self.server.record_pointage_on_unbillable(self.opdef.operation_definition_id, self.employee_id,
                                                  d1, "Nostromo", TaskActionReportType.start_task)


        ot = self.server.get_ongoing_tasks(self.employee_id, d1 + timedelta(hours=3) )
        self.assertEqual(2,len(ot))

        # A third task

        order_part = self._order_part_dao.make(order)
        order_part.description = "Part 1"
        order_part.position = 1
        self._order_part_dao.save(order_part)

        pf = self._production_file_dao.make()
        pf.order_part = order_part
        order_part.production_file = [pf]
        session().add(pf)
        session().flush()

        operation = self._operation_dao.make()
        operation.production_file = pf
        operation.description = "operation desc"
        operation.operation_model = self.opdef_op
        session().add(operation)
        session().commit()
        machine = self._make_machine("Tarazer", operation.operation_definition_id)

        d3 = datetime(2012,12,31,9)
        self.server.record_pointage_on_operation(operation.operation_id, self.employee_id, d3, "Nostromo", TaskActionReportType.start_task, machine.machine_id)

        # bc = BarCodeIdentifier.code_for(operation)
        # self.clock_server.recordPointage(bc,self.employee_id, datetime.strftime(d1, "%Y%m%dT%H:%M:%S"),"Nostromo")

        ot = self.server.get_ongoing_tasks(self.employee_id, d1 + timedelta(hours=3) )
        self.assertEqual(3,len(ot))

        # Day in day out must not affect the number of ongoing tasks

        d4 = datetime(2012,12,31,8)

        self.server.record_presence(self.employee_id, d4, "Nostromo", TaskActionReportType.day_in)
        ot = self.server.get_ongoing_tasks(self.employee_id, d1 + timedelta(hours=3) )
        self.assertEqual(3,len(ot))





    def test_presence_recording(self):

        # TestClockService.test_presence_recording
        t1 = datetime(2012,12,31,8,0)
        self.assertEqual(0, len(self.tar_dao.get_reports_for_employee_id_on_date(self.employee_id,t1.date())))

        self.server.record_presence(self.employee_id, t1,"Nostromo",TaskActionReportType.presence)
        self.assertEqual(1, len(self.tar_dao.get_reports_for_employee_id_on_date(self.employee_id,t1.date())))

        t2 = t1 + timedelta(seconds=30)
        self.server.record_presence(self.employee_id, t2,"Nostromo",TaskActionReportType.presence)
        self.assertEqual(2, len(self.tar_dao.get_reports_for_employee_id_on_date(self.employee_id,t2.date())))

        ot = self.server.get_ongoing_tasks(self.employee_id, t1 + timedelta(hours=3))
        self.assertEqual(0,len(ot))


        h = self.server.get_person_data(self.employee_id,t1.date())

        mainlog.debug("test : get_person_data")
        mainlog.debug(h)

        self.assertEqual( 30, round(3600*h.presence[3].presence_time)) # Duration is in hours
        self.assertEqual(date(2012,12,31), h.presence[3].day)

        # self.assertEqual([t2,None,None,None], h.presence['presence_end'])

        # New time between two exisiting times. It shouldn't be recorded because it's useless.
        t2 = t1 + timedelta(seconds=15)
        self.server.record_presence(self.employee_id, t2,"Nostromo",TaskActionReportType.presence)
        self.assertEqual(2, len(self.tar_dao.get_reports_for_employee_id_on_date(self.employee_id,t2.date())))



    def test_bad_machine_provided_on_pointage(self):
        order = self._make_order()
        dao.order_dao.change_order_state(order.order_id, OrderStatusType.order_ready_for_production)
        employee = self._employee()

        op = order.parts[0].operations[0]

        # Test 1 : Give a machine where none is needed (the operation is not
        # tied to an operation definition that doesn't require a machine)

        time = datetime(2012,10,23,10)
        try:
            self.server.record_pointage_on_operation(op.operation_id,
                                                     employee.employee_id,
                                                     time,
                                                     "location",
                                                     TaskActionReportType.start_task,
                                                     12)
            self.fail()
        except ServerException as ex:
            assert ex.code == ServerErrors.machine_not_compatible_with_operation.value

        # Test 1 : Give no machine where one is needed

        m = Machine()
        m.fullname = "Test"
        m.is_active = True
        m.operation_definition_id = op.operation_definition_id
        session().add(m)
        session().commit()
        machine_service._reset_cache()

        try:
            self.server.record_pointage_on_operation(op.operation_id,
                                                     employee.employee_id,
                                                     time,
                                                     "location",
                                                     TaskActionReportType.start_task,
                                                     None)
        except ServerException as ex:
            assert ex.code == ServerErrors.machine_not_compatible_with_operation.value


    def test_open_and_close_task_without_machine(self):
        order = self._make_order()

        dao.order_dao.change_order_state(order.order_id, OrderStatusType.order_ready_for_production)
        employee = self._employee()

        op = order.parts[0].operations[0]

        time = datetime(2012,10,23,10)
        self.server.record_pointage_on_operation(op.operation_id,
                                                 employee.employee_id,
                                                 time,
                                                 "location",
                                                 TaskActionReportType.start_task,
                                                 None)

        self.server.record_pointage_on_operation(op.operation_id,
                                                 employee.employee_id,
                                                 time + timedelta(hours=5),
                                                 "location",
                                                 TaskActionReportType.stop_task,
                                                 None)

        assert 2 == session().query(TimeTrack).count()

        pt = dao.task_action_report_dao.presence_task()
        assert 1 == session().query(TimeTrack).filter(TimeTrack.task_id == pt.task_id).count()



    def test_open_and_close_task_with_machine(self):
        order = self._make_order()

        dao.order_dao.change_order_state(order.order_id, OrderStatusType.order_ready_for_production)
        employee = self._employee()

        op = order.parts[0].operations[0]

        m = Machine()
        m.fullname = "Test"
        m.is_active = True
        m.operation_definition_id = op.operation_definition_id
        session().add(m)
        session().commit()
        machine_service._reset_cache()

        time = datetime(2012,10,23,10)
        self.server.record_pointage_on_operation(op.operation_id,
                                                 employee.employee_id,
                                                 time,
                                                 "location",
                                                 TaskActionReportType.start_task,
                                                 m.machine_id)

        self.server.record_pointage_on_operation(op.operation_id,
                                                 employee.employee_id,
                                                 time + timedelta(hours=5),
                                                 "location",
                                                 TaskActionReportType.stop_task,
                                                 m.machine_id)

        assert 2 == session().query(TimeTrack).count()

        pt = dao.task_action_report_dao.presence_task()
        assert 1 == session().query(TimeTrack).filter(TimeTrack.task_id == pt.task_id).count()



    def test_no_colleagues(self):
        order = self._make_order()

        dao.order_dao.change_order_state(order.order_id, OrderStatusType.order_ready_for_production)
        employee = self._employee()

        op = order.parts[0].operations[0]

        m = Machine()
        m.fullname = "Test"
        m.is_active = True
        m.operation_definition_id = op.operation_definition_id
        session().add(m)
        session().commit()
        machine_service._reset_cache()

        assert op.operation_definition_id

        operation,machines,next_action_kind,colleagues = self.server.get_operation_information(employee.employee_id, op.operation_id)

        assert not colleagues


    def test_one_colleague(self):
        order = self._make_order()

        dao.order_dao.change_order_state(order.order_id, OrderStatusType.order_ready_for_production)
        employee = self._employee()

        employee2 = self.dao_employee.create(u"Frankie Franky"+ chr(233))

        operation = order.parts[0].operations[0]

        m = Machine()
        m.fullname = "Test"
        m.is_active = True
        m.operation_definition_id = operation.operation_definition_id
        session().add(m)
        session().commit()
        machine_service._reset_cache()

        # A colleague

        d3 = datetime(2012,12,31,9)
        self.server.record_pointage_on_operation(operation.operation_id, employee2.employee_id, d3, "Nostromo", TaskActionReportType.start_task, m.machine_id)

        mainlog.debug("test_one_colleague-1")
        operation,machines,next_action_kind,colleagues = self.server.get_operation_information(employee.employee_id, operation.operation_id)
        mainlog.debug("test_one_colleague-2")

        assert len(colleagues) == 1
        assert colleagues[0].reporter_id == employee2.employee_id
        assert colleagues[0].kind == TaskActionReportType.start_task



    def test_self_colleague(self):
        order = self._make_order()

        dao.order_dao.change_order_state(order.order_id, OrderStatusType.order_ready_for_production)
        employee = self._employee()

        operation = order.parts[0].operations[0]

        m = Machine()
        m.fullname = "Test"
        m.is_active = True
        m.operation_definition_id = operation.operation_definition_id
        session().add(m)
        session().commit()
        machine_service._reset_cache()

        # The reporter himself

        d3 = datetime(2012,12,31,9)
        self.server.record_pointage_on_operation(operation.operation_id, employee.employee_id, d3, "Nostromo", TaskActionReportType.start_task, m.machine_id)

        operation,machines,next_action_kind,colleagues = self.server.get_operation_information(employee.employee_id, operation.operation_id)

        assert len(colleagues) == 1
        assert colleagues[0].reporter_id == employee.employee_id
        assert colleagues[0].kind == TaskActionReportType.start_task



    def test_first_record_on_opdef_task(self):

        # set PYTHONPATH=c:/port-stca2/pl-PRIVATE/horse
        # py.test test_clock_service.py -k test_first_record_on_task

        from koi.configuration.business_functions import business_computations_service

        operation_definition,next_action_kind = self.server.get_operation_definition_information(self.employee_id, self.opdef.operation_definition_id)

        assert next_action_kind == TaskActionReportType.start_task


        # Test one : Just outside TAR time horizon

        d1 = business_computations_service.tar_time_horizon(datetime.now()) - timedelta(hours=1)
        d2 = datetime.now() - timedelta(hours=1)

        self.server.record_pointage_on_unbillable( self.opdef.operation_definition_id, self.employee_id,
                                                   d1, "Nostromo", TaskActionReportType.start_task)


        ot = self.server.get_ongoing_tasks(self.employee_id, d2)
        assert len(ot) == 0

        operation_definition,next_action_kind = self.server.get_operation_definition_information(self.employee_id, self.opdef.operation_definition_id)
        assert next_action_kind == TaskActionReportType.start_task

        # Test two : Inside TAR time horizon

        d1 = datetime.now() - timedelta(hours=1)

        self.server.record_pointage_on_unbillable( self.opdef.operation_definition_id, self.employee_id,
                                                   d1, "Nostromo", TaskActionReportType.start_task)

        ot = self.server.get_ongoing_tasks(self.employee_id, datetime.now())
        assert len(ot) == 1

        operation_definition,next_action_kind = self.server.get_operation_definition_information(self.employee_id, self.opdef.operation_definition_id)
        assert next_action_kind == TaskActionReportType.stop_task



    def test_first_record_on_operation_task(self):

        d1 = business_computations_service.tar_time_horizon(datetime.now()) - timedelta(hours=1) # outside time horizon
        d2 = datetime.now() - timedelta(hours=1)

        # set PYTHONPATH=c:/port-stca2/pl-PRIVATE/horse
        # py.test test_clock_service.py -k test_first_record_on_task


        order = self._make_order()

        dao.order_dao.change_order_state(order.order_id, OrderStatusType.order_ready_for_production)
        employee = self._employee()
        operation = order.parts[0].operations[0]
        machine = self._make_machine("Tarazer", operation.operation_definition_id)
        session().commit()

        # Test zero  : no TAR at all

        ot = self.server.get_ongoing_tasks(self.employee_id, d2)
        assert len(ot) == 0
        operation, machines, next_action_kind, colleagues = self.server.get_operation_information(self.employee_id, operation.operation_id)

        # FIXME assert next_action_kind == TaskActionReportType.start_task

        assert TaskActionReportType.start_task == self.server.get_next_action_for_employee_operation_machine(self.employee_id, operation.operation_id, machine.machine_id)


        next_action_kind = self.server.get_next_action_for_employee_operation_machine(self.employee_id, operation.operation_id, machine.machine_id)

        assert TaskActionReportType.start_task == next_action_kind


        # Test one : Just outside TAR time horizon (so alike there's not TAR)

        self.server.record_pointage_on_operation( operation.operation_id, self.employee_id,
                                                  d1, "Nostromo", TaskActionReportType.start_task, machine.machine_id)


        operation, machines, next_action_kind, colleagues = self.server.get_operation_information(self.employee_id, operation.operation_id)
        assert next_action_kind == None

        next_action_kind = self.server.get_next_action_for_employee_operation_machine(self.employee_id, operation.operation_id, machine.machine_id)
        assert TaskActionReportType.start_task == next_action_kind

        ot = self.server.get_ongoing_tasks(self.employee_id, d2)
        assert len(ot) == 0


        # Test two : Inside TAR time horizon

        d1 = datetime.now() - timedelta(hours=1)

        self.server.record_pointage_on_operation( operation.operation_id, self.employee_id,
                                                  d1, "Nostromo", TaskActionReportType.start_task, machine.machine_id)

        operation, machines, next_action_kind, colleagues = self.server.get_operation_information(self.employee_id, operation.operation_id)
        assert next_action_kind == None

        next_action_kind = self.server.get_next_action_for_employee_operation_machine(self.employee_id, operation.operation_id, machine.machine_id)
        assert TaskActionReportType.stop_task == next_action_kind

        ot = self.server.get_ongoing_tasks(self.employee_id, datetime.now())
        assert len(ot) == 1


if __name__ == "__main__":
    unittest.main()
