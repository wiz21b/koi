import unittest
from time import sleep

from unittest import skip
from PySide.QtGui import QApplication,QMainWindow,QFontDatabase
from PySide.QtTest import QTest

from koi.test.test_base import TestBase


from koi.db_mapping import *
from koi.dao import *
from koi.server.MemoryLogger import MemLogger
from koi.server.clock_client import MainWindow, ClockErrors
from koi.BarCodeBase import BarCodeIdentifier,BarCode

from koi.server.json_decorator import ServerException,ServerErrors,JsonCallWrapper


class TestClockClient(TestBase):
    @classmethod
    def setUpClass(cls):
        super(TestClockClient,cls).setUpClass()

        mainlog.setLevel(logging.WARNING) # logging.WARNING)
        cls.mem_logger = MemLogger()

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        font_database = QFontDatabase()

        cls.app = app
        cls.window = MainWindow("TEST_CLOCK",cls.mem_logger,dao, font_database, call_mode=JsonCallWrapper.DIRECT_MODE) # IN_PROCESS_MODE
        cls.window.show()

    @classmethod
    def tearDownClass(cls):
        cls.window.close()
        # cls.app.exit()


    def setUp(self):
        super(TestClockClient,self).setUp()

        self.window._reset_clock()
        self.mem_logger.clear_errors()
        app = self.app
        self.window.setFocus(Qt.OtherFocusReason)



    def _scan(self,barcode):
        """ Simulate a real barcode scan.
        """

        bc = str(barcode) + str(BarCode(barcode)._checksum())

        mainlog.debug("Sending a scan : {}".format(bc))

        QTest.keyClicks(self.app.focusWidget(), bc) # modifier, delay
        self.app.processEvents()
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_Enter) # modifier, delay
        self.app.processEvents()


    def _on_screen(self, screen_name):
        mainlog.debug("Current screen is {}".format(self.window.current_screen))
        return self.window.current_screen == screen_name

    def test_employee_select(self):
        app = self.app
        self.window.setFocus(Qt.OtherFocusReason)

        employee = dao.employee_dao.find_by_id(self.employee_id)
        bc = BarCodeIdentifier.code_for(employee)

        self._scan(bc)
        assert not self.mem_logger.last_error()



    @skip("Report on order not yet completed")
    def test_order(self):
        order = self._order_dao.make("Test order",self.customer)
        order.state = OrderStatusType.order_ready_for_production
        self._order_dao.save(order)
        bc_order = BarCodeIdentifier.code_for(order,self.opdef_order)
        session().close()

        app = self.app
        self.window.setFocus(Qt.OtherFocusReason)

        employee = dao.employee_dao.find_by_id(self.employee_id)
        bc = BarCodeIdentifier.code_for(employee)
        self._scan(bc)

        self._scan(bc_order)

        # self.app.exec_()


    def test_operation(self):
        order = self._order_dao.make(u"Test order"+chr(233),self.customer)
        order.state = OrderStatusType.order_definition # OrderStatusType.order_ready_for_production
        self._order_dao.save(order)

        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 1" + chr(233)
        order_part.position = 1
        self._order_part_dao.save(order_part)

        pf = self._production_file_dao.make()
        pf.order_part = order_part
        order_part.production_file = [pf]
        session().add(pf)
        session().flush()

        operation = self._operation_dao.make()
        operation.production_file = pf
        operation.description = u"operation desc" + chr(233)
        operation.operation_model = self.opdef_op
        session().add(operation)
        session().commit()

        bc_operation = BarCodeIdentifier.code_for(operation)
        order_id = order.order_id
        session().close()

        app = self.app
        self.window.setFocus(Qt.OtherFocusReason)

        # Scan employee; this hsould result in a presence task.
        employee = dao.employee_dao.find_by_id(self.employee_id)
        bc = BarCodeIdentifier.code_for(employee)
        self._scan(bc)

        # At this point, the operation exists but is not imputable
        # because the order is not in production.
        # Therefore scanning it shll produce no effect.

        self._scan(bc_operation)

        self.assertEqual( ServerErrors.order_part_not_in_production_unknown.value,
                          self.mem_logger.last_error().code)
        self.assertEqual(0, session().query(TaskActionReport).filter(TaskActionReport.kind == TaskActionReportType.start_task).count())

        order = dao.order_dao.find_by_id(order_id)
        order.state = OrderStatusType.order_ready_for_production
        self._order_dao.save(order)
        session().close()

        self.mem_logger.clear_errors()

        # Start task
        self._scan(bc_operation)

        # app.exec_()
        mainlog.debug(" *** !!! "*10)
        assert not self.mem_logger.last_error()
        self.assertEqual(1, session().query(TaskActionReport).filter(TaskActionReport.kind == TaskActionReportType.start_task).count())

        # FIXME missing asserts

        # End task
        self._scan(bc_operation)
        assert not self.mem_logger.last_error()

        self.assertEqual(1, session().query(TaskActionReport).filter(TaskActionReport.kind == TaskActionReportType.start_task).count())
        self.assertEqual(1, session().query(TaskActionReport).filter(TaskActionReport.kind == TaskActionReportType.stop_task).count())
        assert session().query(TaskActionReport).count() == 3 # 2 + presence
        session().commit()

        # self.app.exec_()



    def test_two_operations_without_machine(self):
        order = self._make_order()
        dao.order_dao.change_order_state(order.order_id, OrderStatusType.order_ready_for_production)
        operation = order.parts[0].operations[0]

        operation2 = self._operation_dao.make()
        operation2.production_file_id = order.parts[0].production_file[0].production_file_id
        operation2.description = u"lorem ipsum dolor amet lorem ipsum dolor amet sic transit gloria mundi" + chr(233)
        operation2.operation_model = self.opdef_op
        session().add(operation2)
        session().commit()

        employee = dao.employee_dao.find_by_id(self.employee_id)
        bc_employee = BarCodeIdentifier.code_for(employee)
        self._scan(bc_employee)

        bc_operation = BarCodeIdentifier.code_for(operation)
        self._scan(bc_operation)
        self.assertEqual(1, session().query(TaskActionReport).filter(TaskActionReport.kind == TaskActionReportType.start_task).count())

        bc_operation2 = BarCodeIdentifier.code_for(operation2)
        self._scan(bc_operation2)
        self.assertEqual(2, session().query(TaskActionReport).filter(TaskActionReport.kind == TaskActionReportType.start_task).count())

        self._scan(bc_employee)
        self._scan(bc_employee)

        self._scan(bc_operation)
        self.assertEqual(1, session().query(TaskActionReport).filter(TaskActionReport.kind == TaskActionReportType.stop_task).count())

        self._scan(bc_operation2)
        self.assertEqual(2, session().query(TaskActionReport).filter(TaskActionReport.kind == TaskActionReportType.stop_task).count())





    def test_operation_with_machine(self):
        order = self._make_order()
        dao.order_dao.change_order_state(order.order_id, OrderStatusType.order_ready_for_production)
        operation = order.parts[0].operations[0]

        machine = self._make_machine("Jones & shipman 1307 zala yop", operation.operation_definition_id)

        app = self.app
        self.window.setFocus(Qt.OtherFocusReason)

        # Employee badge

        employee = dao.employee_dao.find_by_id(self.employee_id)
        bc_employee = BarCodeIdentifier.code_for(employee)
        self._scan(bc_employee)
        assert not self.mem_logger.last_error()

        # Operation selection

        bc_operation = BarCodeIdentifier.code_for(operation)
        self._scan(bc_operation)


        # The operation is tied to a machine => machine selection

        bc_machine = BarCodeIdentifier.code_for(machine)
        self._scan(bc_machine)


        # self._scan(bc_employee)
        # self._scan(bc_employee)


        # The task is started

        self.assertEqual(1, session().query(TaskActionReport).filter(TaskActionReport.kind == TaskActionReportType.start_task).count())
        session().commit()


        # Now we start the scenario over to stop the task

        # self._scan(bc_employee)
        self._scan(bc_operation)
        # self.app.exec_()

        self._scan(bc_machine)

        self.assertEqual(1, session().query(TaskActionReport).filter(TaskActionReport.kind == TaskActionReportType.stop_task).count())
        session().commit()


        # self.app.exec_()



    def test_operation_with_2_machines(self):
        order = self._make_order()
        dao.order_dao.change_order_state(order.order_id, OrderStatusType.order_ready_for_production)
        operation = order.parts[0].operations[0]
        operation.description = "lorem ipsum dolor amet lorem ipsum dolor amet sic transit gloria mundi"

        machine1 = self._make_machine("Test1 Zimmer Johnson", operation.operation_definition_id)
        machine2 = self._make_machine("Machine2 12457", operation.operation_definition_id)

        app = self.app
        self.window.setFocus(Qt.OtherFocusReason)

        # Employee badge

        employee = dao.employee_dao.find_by_id(self.employee_id)
        bc_employee = BarCodeIdentifier.code_for(employee)
        self._scan(bc_employee)
        assert not self.mem_logger.last_error()

        # Operation selection

        bc_operation = BarCodeIdentifier.code_for(operation)
        self._scan(bc_operation)

        # The operation is tied to a machine => machine selection

        bc_machine1 = BarCodeIdentifier.code_for(machine1)
        mainlog.debug("*** --- " * 40)
        self._scan(bc_machine1)


        self.assertEqual(1, session().query(TaskActionReport).filter(TaskActionReport.kind == TaskActionReportType.start_task).count())
        session().commit()

        # Start the scenario again for a second task on a second machine

        self._scan(bc_employee)
        mainlog.debug(bc_employee)
        mainlog.debug("testtt : {} / {}".format(self.employee_id,bc_employee))


        self._scan(bc_operation)
        # app.exec_()


        mainlog.debug("Active Operation")
        for op in session().query(Operation).all():
            mainlog.debug(op)

        mainlog.debug("Active Operation + join")
        for op, task_id in session().query(Operation,TaskOnOperation.task_id).outerjoin(TaskOnOperation, TaskOnOperation.machine_id == machine2.machine_id).all():
            mainlog.debug(op)
            mainlog.debug(task_id)


        bc_machine2 = BarCodeIdentifier.code_for(machine2)


        mainlog.debug("Active TaskOnOperation")
        for task in session().query(TaskOnOperation).all():
            mainlog.debug("Task id:{} operation:{} machine:{}".format(task.task_id, task.operation_id, task.machine_id))
        for tar in session().query(TaskActionReport).all():
            mainlog.debug(tar)
        session().commit()


        mainlog.debug("*** --- " * 40)
        self._scan(bc_machine2)



        mainlog.debug("Active TaskOnOperation")
        for task in session().query(TaskOnOperation).all():
            mainlog.debug("Task id:{} operation:{} machine:{}".format(task.task_id, task.operation_id, task.machine_id))
        for tar in session().query(TaskActionReport).all():
            mainlog.debug(tar)
        session().commit()



        self.assertEqual(2, session().query(TaskOnOperation).count())

        self.assertEqual(2, session().query(TaskActionReport).filter(TaskActionReport.kind == TaskActionReportType.start_task).count())
        session().commit()

        # app.exec_()


        # Now we start the scenario over to stop one of the task

        # self._scan(bc_employee)
        self._scan(bc_operation)

        # self.app.exec_()

        self._scan(bc_machine1)

        self.assertEqual(1, session().query(TaskActionReport).filter(TaskActionReport.kind == TaskActionReportType.stop_task).count())
        session().commit()



    def test_employee_out(self):

        self._scan(BarCodeIdentifier.code_for(TaskActionReportType.day_out))
        self.assertEqual( ClockErrors.identify_first.value,
                          self.mem_logger.last_error().code)

        # Employee badge

        employee = dao.employee_dao.find_by_id(self.employee_id)
        bc_employee = BarCodeIdentifier.code_for(employee)
        self._scan(bc_employee)
        assert not self.mem_logger.last_error()

        self._scan(BarCodeIdentifier.code_for(TaskActionReportType.day_out))



        assert self._on_screen( MainWindow.PresenceActionScreen)

        self._scan(bc_employee)

        assert self._on_screen( MainWindow.UserInformationScreen)

        # See if employee out cuts the current activities

        order = self._make_order()
        dao.order_dao.change_order_state(order.order_id, OrderStatusType.order_ready_for_production)
        operation = order.parts[0].operations[0]

        bc_operation = BarCodeIdentifier.code_for(operation)
        self._scan(bc_operation)


        # Scan out...
        self._scan(bc_employee)
        self.app.processEvents()
        sleep(3) # Need this so that the interval is big enough (if too small it will be ignored)
        self.app.processEvents()
        self._scan(BarCodeIdentifier.code_for(TaskActionReportType.day_out))


        # session().query(TaskOnOperation).filter(TaskOnOperation.operation_id == operation.operation_id)

        mainlog.debug("Operation id = {}".format(operation.operation_id))
        self.show_timetracking()

        self.assertEqual(1, session().query(TimeTrack).join(Task).join(TaskOnOperation).filter(TaskOnOperation.operation_id == operation.operation_id).count())

        # self.app.exec_()


    def test_employee_in_and_out(self):

        self._scan(BarCodeIdentifier.code_for(TaskActionReportType.day_out))
        self.assertEqual( ClockErrors.identify_first.value,
                          self.mem_logger.last_error().code)

        # Employee badge

        employee = dao.employee_dao.find_by_id(self.employee_id)
        bc_employee = BarCodeIdentifier.code_for(employee)
        self._scan(bc_employee)
        assert not self.mem_logger.last_error()

        self._scan(BarCodeIdentifier.code_for(TaskActionReportType.day_in))

        assert self._on_screen( MainWindow.PresenceActionScreen)

        sleep(3)

        self._scan(bc_employee)

        assert self._on_screen( MainWindow.UserInformationScreen)


        self._scan(BarCodeIdentifier.code_for(TaskActionReportType.day_out))

        assert self._on_screen( MainWindow.PresenceActionScreen)

        self._scan(bc_employee)

        assert self._on_screen( MainWindow.UserInformationScreen)

        self.assertEqual(1, session().query(TimeTrack).join(Task).join(TaskForPresence).count())



    def test_bad_bar_codes(self):
        order = self._make_order()
        dao.order_dao.change_order_state(order.order_id, OrderStatusType.order_ready_for_production)
        operation = order.parts[0].operations[0]
        machine = self._make_machine("Test1", operation.operation_definition_id)
        employee = dao.employee_dao.find_by_id(self.employee_id)


        app = self.app
        self.window.setFocus(Qt.OtherFocusReason)

        #### Employee bad badge

        bad_employee = Employee()
        bad_employee.employee_id = 999
        bc_employee = BarCodeIdentifier.code_for(bad_employee)
        self._scan(bc_employee)

        assert self.mem_logger.last_error().code == ServerErrors.unknown_employee_id.value


        #### Operation bad badge

        employee = dao.employee_dao.find_by_id(self.employee_id)
        bc_employee = BarCodeIdentifier.code_for(employee)
        self._scan(bc_employee)

        # Operation selection

        bad_operation = Operation()
        bad_operation.operation_id = 9999
        bc_operation = BarCodeIdentifier.code_for(bad_operation)
        self._scan(bc_operation)

        assert self.mem_logger.last_error().code == ServerErrors.operation_unknown.value

        # Try again, with the good one
        bc_operation = BarCodeIdentifier.code_for(operation)
        self._scan(bc_operation)


        #### Machine bad badge

        bad_machine = Machine()
        bad_machine.resource_id = 999
        bc_machine = BarCodeIdentifier.code_for(bad_machine)
        self._scan(bc_machine)

        assert self.mem_logger.last_error().code == ServerErrors.unknown_machine.value

        # Try again
        bc_machine = BarCodeIdentifier.code_for(machine)
        self._scan(bc_machine)

        assert self._on_screen( MainWindow.OperationStartedScreen)


    def test_bad_bar_codes_unbillable(self):

        employee = dao.employee_dao.find_by_id(self.employee_id)
        bc_employee = BarCodeIdentifier.code_for(employee)
        self._scan(bc_employee)

        #### Unbillable operation bad badge

        bad_unbillable = OperationDefinition()
        bad_unbillable.operation_definition_id = 999
        bad_unbillable.imputable = True
        bad_unbillable.on_order = False
        bad_unbillable.on_operation = False

        bc_unbillable = BarCodeIdentifier.code_for(bad_unbillable)


        self._scan(bc_unbillable)
        assert self.mem_logger.last_error().code == ServerErrors.operation_definition_unknown.value


    def test_inactive_unbillable(self):

        employee = dao.employee_dao.find_by_id(self.employee_id)
        bc_employee = BarCodeIdentifier.code_for(employee)
        self._scan(bc_employee)


        bad_unbillable = OperationDefinition()
        bad_unbillable.short_id = "ZZ"
        bad_unbillable.description = "Zulu"
        bad_unbillable.imputable = False
        bad_unbillable.on_order = False
        bad_unbillable.on_operation = False
        period = OperationDefinitionPeriod()
        period.start_date, period.end_date = date(2010,1,1), None
        bad_unbillable.periods.append(period)

        self._operation_definition_dao.save(bad_unbillable)

        bc_unbillable = BarCodeIdentifier.code_for(bad_unbillable)
        self._scan(bc_unbillable)

        assert self._on_screen( MainWindow.UserInformationScreen)


    def test_unbillable(self):

        nonbillable_op = self._operation_definition_dao.find_by_id(self.nonbillable_op_id)
        bc_unbillable = BarCodeIdentifier.code_for(nonbillable_op)

        employee = dao.employee_dao.find_by_id(self.employee_id)
        bc_employee = BarCodeIdentifier.code_for(employee)

        # Starting the work

        self._scan(bc_employee)
        self._scan(bc_unbillable)

        assert self._on_screen( MainWindow.UnbillableOperationStartedScreen)

        sleep(3) # Need this so that the interval is big enough (if too small it will be ignored)

        # Finishing the work

        self._scan(bc_employee)
        self._scan(bc_unbillable)

        assert self._on_screen( MainWindow.UnbillableOperationFinishedScreen)

        # self.app.exec_()

if __name__ == "__main__":
    unittest.main()
