import unittest
from unittest import skip
from sqlalchemy.exc import InternalError
from PySide.QtTest import QTest
from koi.test.test_base import TestBase

from koi.db_mapping import *
from koi.datalayer.gapless_sequence import current_gaplessseq_value
from koi.dao import *
from koi.server.server import ClockServer,ServerException
from koi.datalayer.types import DBObjectActionTypes
from koi.junkyard.sqla_dict_bridge import InstrumentedRelation



# import datetime
# from datetime import date
# import hashlib
# import unittest
# from unittest import skip

# """
# createdb.exe horse_test
# createuser.exe --no-superuser --no-createdb --no-createrole tester
# """

# # Make sure we work with an in memory database
# import Configurator
# # Configurator.configuration.in_test()


# import logging
# from koi.base_logging import init_logging
# init_logging("test.log")

# from Configurator import init_i18n,load_configuration
# init_i18n()
# load_configuration("test_config.cfg")
# from Configurator import mainlog,configuration

# def add_user(login,password,fullname,roles):
#     h = hashlib.md5()
#     h.update(password)
#     session().connection().execute("INSERT INTO users (user_id,fullname,roles,password) VALUES ('{}','{}','{}','{}')".format(login,fullname,roles,h.hexdigest()))


# from sqlalchemy.exc import IntegrityError,InternalError
# from sqlalchemy.sql.expression import func,select,join,and_,desc

# import db_mapping
# from db_mapping import Employee,Task, OperationDefinition, TaskActionReport,TimeTrack,DeliverySlipPart,Order, Customer,OrderPart,Operation,ProductionFile,TaskOnOperation,TaskActionReportType, TaskOnNonBillable
# from db_mapping import OrderStatusType

# from dao import *
# from server import ClockServer,ServerException




# def init_sequences(session):

#     # Always insert the number RIGHT BEFORE the one you expect to use next time...
#     session.connection().execute("BEGIN")
#     session.connection().execute("INSERT INTO gapless_seq VALUES('delivery_slip_id', '799')")
#     session.connection().execute("INSERT INTO gapless_seq VALUES('order_id','100')")
#     session.connection().execute("INSERT INTO gapless_seq VALUES('preorder_id','4999')")
#     session.connection().execute("COMMIT")




class TestOrderPart(TestBase):

    @classmethod
    def setUpClass(cls):
        super(TestOrderPart,cls).setUpClass()

        # cls.order_dao = OrderDAO(session())
        # cls._order_part_dao = OrderPartDAO(session())
        # cls.operation_dao = OperationDAO(session())
        # cls.customer_dao = CustomerDAO(session())
        # cls._operation_definition_dao = OperationDefinitionsDAO(session())
        # cls._production_file_dao = ProductionFileDAO(session(),cls._order_part_dao)
        # cls.dao_employee = EmployeeDAO(session())
        # cls.timetrack_dao = TimeTrackDAO(session())

        cls.opdef = cls._operation_definition_dao.make()
        cls.opdef.short_id = "MA"
        cls.opdef.description = "MA"
        cls.opdef.imputable = False
        cls.opdef.on_order = False
        cls.opdef.on_operation = True
        period = OperationDefinitionPeriod()
        period.start_date = date(2010,1,1)
        period.cost = 63.3 # BUG Cost makes no sense for non imputable task or does it ?
        cls.opdef.periods.append(period)
        cls._operation_definition_dao.save(cls.opdef)

        # cls.opdef_op = cls._operation_definition_dao.make()
        # cls.opdef_op.short_id = "TO"
        # cls.opdef_op.description = "TO"
        # cls.opdef_op.imputable = True
        # cls.opdef_op.on_order = False
        # cls.opdef_op.on_operation = True
        # cls._operation_definition_dao.save(cls.opdef_op)

        # cls.employee = cls.dao_employee.make("Edgar Dijkstra")
        # cls.dao_employee.save(cls.employee)

        # cls.customer = cls.customer_dao.make("Donald Knuth")
        # cls.customer_dao.save(cls.customer)


    def setUp(self):
        mainlog.debug("Entering setUp")
        for slip in session().query(DeliverySlip).all():
            session().delete(slip) # Delete like this so that the cascade works

        session().query(TaskActionReport).delete()
        session().query(TimeTrack).delete()
        session().query(TaskOnNonBillable).delete()
        session().query(TaskOnOperation).delete()
        session().query(TaskOnOrder).delete()
        session().query(DayTimeSynthesis).delete()

        mainlog.debug("Deleting orders")
        for order in session().query(Order).order_by(desc(Order.accounting_label)).all():
            mainlog.debug("setUp: deleting order {}".format(order.order_id))
            session().delete(order) # Delete like this so that the cascade works
        mainlog.debug("Deleting orders - done")

        session().commit()
        session().expire_all()

        order = self.order_dao.make("Test order",self.customer)
        order.state = OrderStatusType.preorder_definition
        self.order_dao.save(order)
        self._order_id = order.order_id

        order_part = self._order_part_dao.make(order)
        order_part.description = "Part 1"
        order_part.position = 1
        self._order_part_dao.save(order_part)

        order_part = self._order_part_dao.make(order)
        order_part.description = "Part 2"
        order_part.position = 2
        self._order_part_dao.save(order_part)
        print("setUp complete")


    def test_gapless(self):
        mainlog.debug("test_gapless, there are {} orders".format(session().query(Order).count()))
        order1 = self.order_dao.make("Test order gapless",self.customer)
        order1.state = OrderStatusType.order_definition
        self.order_dao.save(order1)

        order2 = self.order_dao.make("Test order gapless",self.customer)
        order2.state = OrderStatusType.order_definition
        self.order_dao.save(order2)

        self.assertEqual(101,order1.accounting_label)
        self.assertEqual(None,order1.preorder_label)
        self.assertEqual(102,order2.accounting_label)
        self.assertEqual(None,order2.preorder_label)

        self.assertEqual(102,current_gaplessseq_value('order_id'))

        mainlog.debug("Delete one, there are {} orders".format(session().query(Order).count()))

        self.assertEqual(self.order_dao.CANNOT_DELETE_BECAUSE_ORDER_IS_NOT_LAST,
                         self.order_dao.check_delete(order1.order_id))

        try:
            self.order_dao.delete(order1.order_id) # one can only delete the last order
            self.fail()
        except InternalError as ex:
            mainlog.debug("one can only delete the last order caught, fine !")
            pass

        mainlog.debug("Next delete, orders are :")
        mainlog.debug("Session is {}".format(session()))
        # session().rollback()

        # session().rollback()
        # session().expire_all()

        for order in session().query(Order).order_by(desc(Order.accounting_label)).all():
            mainlog.debug("   id:{} preorder:{} account:{}".format(order.order_id,order.preorder_label, order.accounting_label))

        self.order_dao.delete(order2.order_id) # one can only delete the last order

        # and of course, after a delete everything should go on
        # with appropriate accounting_label number...

        mainlog.debug("Third delete")
        order3 = self.order_dao.make("Test order gapless",self.customer)
        order3.state = OrderStatusType.order_definition
        self.order_dao.save(order3)
        self.assertEqual(102,order3.accounting_label)

    def test_gapless2(self):
        mainlog.debug("test_gapless2")

        order1 = self.order_dao.make("Test order gapless",self.customer)
        order1.state = OrderStatusType.order_definition
        self.order_dao.save(order1)

        order2 = self.order_dao.make("Test order gapless",self.customer)
        order2.state = OrderStatusType.order_definition
        self.order_dao.save(order2)

        order3 = self.order_dao.make("Test order gapless",self.customer)
        order3.state = OrderStatusType.order_definition
        self.order_dao.save(order3)

        self.assertEqual(101,order1.accounting_label)
        self.assertEqual(None,order1.preorder_label)
        self.assertEqual(102,order2.accounting_label)
        self.assertEqual(None,order2.preorder_label)
        self.assertEqual(103,order3.accounting_label)
        self.assertEqual(None,order3.preorder_label)

        self.assertEqual(self.order_dao.CANNOT_DELETE_BECAUSE_ORDER_IS_NOT_LAST,
                         self.order_dao.check_delete(order1.order_id))
        try:
            self.order_dao.delete(order1.order_id)
            self.fail()
        except InternalError as ex:
            pass

        self.assertEqual(self.order_dao.CANNOT_DELETE_BECAUSE_ORDER_IS_NOT_LAST,
                         self.order_dao.check_delete(order2.order_id))
        try:
            self.order_dao.delete(order2.order_id)
            self.fail()
        except InternalError as ex:
            pass

        self.assertEqual(True, self.order_dao.check_delete(order3.order_id))
        self.order_dao.delete(order3.order_id)

    def test_gapless3(self):
        mainlog.debug("test_gapless3")
        order1 = self.order_dao.make("Test order gapless",self.customer)
        order1.state = OrderStatusType.order_definition
        self.order_dao.save(order1)

        order2 = self.order_dao.make("Test order gapless",self.customer)
        order2.state = OrderStatusType.order_definition
        self.order_dao.save(order2)

        self.assertEqual(101,order1.accounting_label)
        self.assertEqual(None,order1.preorder_label)
        self.assertEqual(102,order2.accounting_label)
        self.assertEqual(None,order2.preorder_label)

        self.order_dao.delete(order2.order_id) # one can only delete the last order
        self.order_dao.delete(order1.order_id) # one can only delete the last order

        # and of course, after a delete everything should go on
        # with appropriate accounting_label number...

        order3 = self.order_dao.make("Test order gapless",self.customer)
        order3.state = OrderStatusType.order_definition
        self.order_dao.save(order3)
        self.assertEqual(101,order3.accounting_label)


    def test_no_delete(self):

        # Delete order /order part

        order = self.order_dao.make("Test order no delete",self.customer)
        order.state = OrderStatusType.preorder_definition
        self.order_dao.save(order)

        order_part = self._order_part_dao.make(order)
        order_part.description = "Part 1"
        order_part.position = 1
        self._order_part_dao.save(order_part)

        self.order_dao.delete(order.order_id)
        self.assertEqual(1,session().query(Order).count())

        # -------------------------------------
        # Delete order /order part /production file / operation

        order = self.order_dao.make("Test order no delete",self.customer)
        order.state = OrderStatusType.preorder_definition

        self.order_dao.save(order)

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
        session().add(operation)

        session().commit()

        self.order_dao.delete(order.order_id)
        self.assertEqual(1,session().query(Order).count())

        # -------------------------------------
        # Delete order /order part /production file / operation / task

        order = self.order_dao.make("Test order no delete",self.customer)
        order.state = OrderStatusType.preorder_definition

        self.order_dao.save(order)

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
        session().add(operation)

        t = TaskOnOperation()
        t.operation = operation
        session().add(t)

        session().commit()

        self.order_dao.delete(order.order_id)
        self.assertEqual(1,session().query(Order).count())

        # -------------------------------------
        # Delete order /order part /production file / operation /task / timetrack : impossible !

        order = self.order_dao.make("Test order no delete",self.customer)
        order.state = OrderStatusType.order_ready_for_production

        self.order_dao.save(order)

        mainlog.debug("order_id = {}".format(order.order_id))

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
        session().add(operation)

        task = TaskOnOperation()
        task.operation = operation
        session().add(task)

        tt = TimeTrack()
        tt.task = task
        tt.employee = self.employee
        session().add(tt)
        session().commit()

        self.assertEqual(self.order_dao.CANNOT_DELETE_BECAUSE_ORDER_HAS_TIMETRACKS,
                         self.order_dao.check_delete(order.order_id))

        try:
            self.order_dao.delete(order.order_id)
            self.fail("should have failed")
        except IntegrityError as e:
            pass

        self.assertEqual(2,session().query(Order).count())

        # remove the timetrack and clean the test
        self.timetrack_dao.delete(tt)
        self.order_dao.delete(order.order_id)
        self.assertEqual(1,session().query(Order).count())


    def test_read(self):
        order = self.order_dao.find_by_id(self._order_id)

        np1 = self._order_part_dao.make(order)
        np1.description = "New part 1"

        np2 = self._order_part_dao.make(order)
        np2.description = "New part 2"


        actions = [ (DBObjectActionTypes.TO_CREATE, np1, 2, InstrumentedRelation()),\
                    (DBObjectActionTypes.UNCHANGED, order.parts[0], 3, InstrumentedRelation()),\
                    (DBObjectActionTypes.UNCHANGED, order.parts[1], 4, InstrumentedRelation()), \
                    (DBObjectActionTypes.TO_CREATE, np2, 5, InstrumentedRelation()) ]

        self._order_part_dao._update_order_parts(actions,order)

        order = self.order_dao.find_by_id(self._order_id)
        self.assertEqual(4,len(order.parts))

        self.assertEqual("New part 1",order.parts[0].description)
        self.assertEqual("Part 1",order.parts[1].description)
        self.assertEqual("Part 2",order.parts[2].description)
        self.assertEqual("New part 2",order.parts[3].description)

        self.assertEqual(1, order.parts[0].position)
        self.assertEqual(2, order.parts[1].position)
        self.assertEqual(3, order.parts[2].position)
        self.assertEqual(4, order.parts[3].position)

        self.assertEqual([], order.parts[0].production_file)
        self.assertEqual([], order.parts[1].production_file)
        self.assertEqual([], order.parts[2].production_file)
        self.assertEqual([], order.parts[3].production_file)

        # --------------------------------------------
        # We have updated order parts
        # Now we update operations

        op = self._operation_dao.make()
        op.description = "Op 1 - Added"
        op.operation_model = self.opdef_op

        op2 = self._operation_dao.make()
        op2.description = "Op 2 - Added"
        op.operation_model = None

        actions = [ (DBObjectActionTypes.TO_CREATE,op,1),
                    (DBObjectActionTypes.TO_CREATE,op2,2)]
        self._order_part_dao.update_operations(actions, order.parts[0])

        order = self.order_dao.find_by_id(self._order_id)
        self.assertEqual(op.description,  order.parts[0].production_file[0].operations[0].description)
        self.assertEqual(op2.description, order.parts[0].production_file[0].operations[1].description)
        self.assertEqual([], order.parts[1].production_file)
        self.assertEqual([], order.parts[2].production_file)
        self.assertEqual([], order.parts[3].production_file)

        # --------------------------------------------

        # We delete the first operation, so the second will take its place
        # I use the descrption to compare the operation because
        # update_operations never returns operations it has created => I can't
        # have the operation id's.

        actions = [ (DBObjectActionTypes.TO_DELETE,order.parts[0].production_file[0].operations[0],None)]

        mainlog.debug("second part of the test")

        self._order_part_dao.update_operations(actions, order.parts[0])
        self.assertEqual(op2.description, order.parts[0].production_file[0].operations[0].description)
        self.assertEqual(1, len(order.parts[0].production_file[0].operations))

        # --------------------------------------------

        mainlog.debug("Operations we'll use")
        mainlog.debug(self.opdef_op)
        mainlog.debug(self.not_imputable_opdef_on_operation)

        op3 = self._operation_dao.make()
        op3.description = "Op 3"
        op3.operation_definition_id = self.opdef_op.operation_definition_id
        op4 = self._operation_dao.make()
        op4.description = "Op 4"
        op4.operation_definition_id = self.not_imputable_opdef_on_operation.operation_definition_id

        actions = [ (DBObjectActionTypes.TO_CREATE,op3,0),
                    (DBObjectActionTypes.UNCHANGED,order.parts[0].production_file[0].operations[0],None),
                    (DBObjectActionTypes.TO_CREATE,op4,0) ]
        self._order_part_dao.update_operations(actions, order.parts[0])

        order = self.order_dao.find_by_id(self._order_id)
        self.assertEqual(op3.description, order.parts[0].production_file[0].operations[0].description)
        self.assertEqual(op2.description, order.parts[0].production_file[0].operations[1].description)
        self.assertEqual(op4.description, order.parts[0].production_file[0].operations[2].description)
        self.assertEqual(3, len(order.parts[0].production_file[0].operations))

        # Creating an order part must leave the task blank
        # The task will be created on demand when someone tries to record time
        # on it.

        self.assertEqual([], order.parts[0].production_file[0].operations[0].tasks)
        self.assertEqual([], order.parts[0].production_file[0].operations[1].tasks)
        self.assertEqual([], order.parts[0].production_file[0].operations[2].tasks)

        # Now we report some time on each operation. This must have
        # the effect of associating tasks to operations.

        dao.task_dao.create_task_on_operation(order.parts[0].production_file[0].operations[0].operation_id, None)
        dao.task_dao.create_task_on_operation(order.parts[0].production_file[0].operations[1].operation_id, None)
        dao.task_dao.create_task_on_operation(order.parts[0].production_file[0].operations[2].operation_id, None)

        # We pause the order

        #order.active = False
        order.state = OrderStatusType.order_production_paused
        self.order_dao.save(order)

        # Reload everything
        order = self.order_dao.find_by_id(self._order_id)
        self.assertEqual(3, len(order.parts[0].production_file[0].operations))

        mainlog.debug("Task")
        task = order.parts[0].production_file[0].operations[0].tasks[0]

        mainlog.debug( task.operation_id)
        mainlog.debug( task.machine_id)
        mainlog.debug( task.description)
        mainlog.debug( order.parts[0].production_file[0].operations[0].operation_definition_id)

        self.assertEqual("[TO] Op 3", task.description)

        self.assertFalse(task.imputable)
        self.assertIsNone(order.parts[0].production_file[0].operations[1].operation_model)
        self.assertFalse(order.parts[0].production_file[0].operations[1].tasks[0].imputable) # No operation definition => not active ??? BUG
        self.assertFalse(order.parts[0].production_file[0].operations[2].tasks[0].imputable) # Non-imputable op. def. => not active

        # If we reactivate an active order, then it must stay the same.

        order.state = OrderStatusType.order_ready_for_production # Activate !
        self.order_dao.save(order)

        order = self.order_dao.find_by_id(self._order_id)
        self.assertEqual(3, len(order.parts[0].production_file[0].operations))
        self.assertEqual("[TO] Op 3", order.parts[0].production_file[0].operations[0].tasks[0].description)
        self.assertEqual(3,session().query(TaskOnOperation).count()) # two successive actiavations don't recreate tasks...

        self.assertTrue(order.parts[0].production_file[0].operations[0].tasks[0].imputable) # On imputable op. defin.

        self.assertIsNone(order.parts[0].production_file[0].operations[1].operation_model)
        self.assertFalse(order.parts[0].production_file[0].operations[1].tasks[0].imputable) # No operation definition => not active ??? BUG

        self.assertFalse(order.parts[0].production_file[0].operations[2].tasks[0].imputable) # Non-imputable op. def. => not active

        # Now, we change the imputable nature of an operation.

        insp = inspect(self.opdef_op)
        imputable_state = insp.attrs.imputable
        print((imputable_state.history))

        self.opdef_op.imputable = False
        self._operation_definition_dao.save(self.opdef_op)

        self.assertFalse(order.parts[0].production_file[0].operations[0].tasks[0].imputable)
        self.assertFalse(order.parts[0].production_file[0].operations[2].tasks[0].imputable) # Non-imputable op. def. => not active

        # Now, we change again the nature of an operation.

        self.opdef_op.imputable = True
        self._operation_definition_dao.save(self.opdef_op)

        self.assertTrue(order.parts[0].production_file[0].operations[0].tasks[0].imputable) # On imputable op. defin.
        self.assertFalse(order.parts[0].production_file[0].operations[2].tasks[0].imputable) # Non-imputable op. def. => not active


        self.assertEqual(3,session().query(TaskOnOperation).count())





        # check task's activity which must be derived from tasop.operation.model AND task.operation.order_part.order

        """
        SELECT t1.ID
        FROM Table1 t1
        LEFT JOIN Table2 t2 ON t1.ID = t2.ID
        WHERE t2.ID IS NULL
        """

        # Operation that should get a new task





        # op = session().query(OrderPart).filter(OrderPart.order_part_id == 10001).one()
        # print op.total_hours2

        # print select([func.sum(TimeTrack.__table__.c.duration)],
        #              from_obj=ProductionFile.__table__.join(OrderPart.__table__).join(
        #         Operation.__table__).join(
        #         Task.__table__).join(
        #         TimeTrack.__table__)).where(OrderPart.__table__.c.order_part_id==123)

        # print join(TimeTrack,Operation,TimeTrack.__table__.c.task_id == Operation.task_id)

        # print select( [func.sum(TimeTrack.duration)],
        #               from_obj=join(TimeTrack,Operation,TimeTrack.task_id == Operation.task_id).select(TimeTrack.task_id == 123))

# @skip
class TestOperationsDefinitionDAO(TestBase):

    def test_create(self):
        opdef = OperationDefinition()
        opdef.description = "Summarize"
        opdef.short_id = "SUM"
        opdef.imputable = True
        opdef.on_order = False
        opdef.on_operation = False
        period = OperationDefinitionPeriod()
        period.start_date = date(2010,1,1)
        period.cost = 63.3 # BUG Cost makes no sense for non imputable task or does it ?
        opdef.periods.append(period)
        s = self._operation_definition_dao.save(opdef)
        session().commit()
        self.assertEqual(opdef,self._operation_definition_dao.find_by_id(opdef.operation_definition_id))

# @skip
class TestEmployeeDAO(TestBase):
    def setUp(self):
        session().query(TaskActionReport).delete()
        session().query(TimeTrack).delete()
        session().query(DayTimeSynthesis).delete()
        session().query(FilterQuery).delete()
        session().query(Employee).delete()

    def test_read_nothing(self):
        self.assertEqual([],self.employee_dao.all())

    def test_presence2(self):
        empl = Employee()
        empl.fullname = "D. Knuth"
        self.employee_dao.save(empl)
        employee_id = empl.employee_id

        begin,last,total_hours = self.employee_dao.presence(employee_id,date(2010,12,31))
        self.assertIsNone(begin)
        self.assertIsNone(total_hours)


        t1,t2 = datetime(2010,12,31,12,00), datetime(2010,12,31,13,15)

        empl = session().query(Employee).filter(Employee.employee_id == employee_id).one()

        self.tar_dao.create_presence_if_necessary(empl.employee_id,t1,"CLOCK 01")
        begin,last,total_hours = self.employee_dao.presence(employee_id,date(2010,12,31))
        self.assertEqual(begin,t1)
        self.assertIsNone(total_hours)


        empl = session().query(Employee).filter(Employee.employee_id == employee_id).one()
        self.tar_dao.create_presence_if_necessary(empl.employee_id,t2,"CLOCK 02")
        begin,last,total_hours = self.employee_dao.presence(employee_id,date(2010,12,31))
        self.assertEqual(begin,t1)

        self.assertEqual(total_hours,1.25)



# @skip("")
class TestTaskDAO(TestBase):
    def setUp(self):
        self.timetrack_dao = TimeTrackDAO(session())
        self.day_time_synthesis_dao = DayTimeSynthesisDAO(session())
        self.task_action_report_dao = TaskActionReportDAO(session(),self.timetrack_dao,self.day_time_synthesis_dao)
        self.dao = TaskDAO(session(), self.task_action_report_dao)

        session().query(TaskActionReport).delete()
        session().query(TimeTrack).delete()
        session().query(TaskOnNonBillable).delete()
        # session().query(Task).delete()
        session().commit()

    def test_create(self):
        task = self.dao.create("my task one")
        session().commit()

# @skip("")
class TestTaskActionReport(TestBase):
    def setUp(self):
        self.dao_timetrack = TimeTrackDAO(session())

        session().query(TaskActionReport).delete()
        session().query(TimeTrack).delete()
        session().query(TaskOnNonBillable).delete()
        session().query(TaskOnOperation).delete()
        session().query(TaskOnOrder).delete()
        # session().query(Task).delete()
        session().commit()

    def test_create_basis(self):

        self.task = self.task_dao.create_non_billable_task(self.opdef.operation_definition_id)
        # This should do nothing
        self.tar_dao.compute_activity_timetracks_from_task_action_reports([],self.employee)

        count_query = session().query(TimeTrack).filter(TimeTrack.employee == self.employee)
        self.assertEqual(0,count_query.count())

        d  = date(2010,12,1)
        d1 = datetime(2010,12,1,10)
        d2 = datetime(2010,12,1,11)
        d3 = datetime(2010,12,1,12)
        d4 = datetime(2010,12,1,13)
        d5 = datetime(2010,12,1,14)

        # Regular timetrack
        tar = self.tar_dao.create(self.task,self.employee,d1,TaskActionReportType.start_task,"Mars")
        tar = self.tar_dao.create(self.task,self.employee,d2,TaskActionReportType.start_task,"Mars")
        tar = self.tar_dao.create(self.task,self.employee,d3,TaskActionReportType.stop_task,"Mars")
        self.tar_dao.compute_activity_timetracks_from_task_action_reports(self.tar_dao.get_reports_for_employee_on_date(self._employee(), d),self.employee.employee_id)


        # Empty timetrack (which should ne be possible)
        tar = self.tar_dao.create(self.task,self.employee,d4,TaskActionReportType.start_task,"Mars")

        # # FIXME Fix emptiness issues if any !!!

        try:
            tar = self.tar_dao.create(self.task,self.employee,d4,TaskActionReportType.stop_task,"Mars")
            self.fail()
        except Exception as ex:
            pass

        session().commit()
        self.assertEqual(2,count_query.count())


    def test_nonbillable_task_imputable(self):
        opdef = self._operation_definition_dao.make()
        opdef.short_id = "TO"
        opdef.description = "Tour"
        opdef.imputable = True
        opdef.on_order = False
        opdef.on_operation = False
        session().add(opdef)
        session().flush() # Get the id for the opdef

        task = self.task_dao.create_non_billable_task(opdef.operation_definition_id)
        self.assertTrue(task.imputable)

        opdef.imputable = False
        task.active = False
        self.assertFalse(task.imputable)

        opdef.imputable = True
        task.active = False
        self.assertFalse(task.imputable)

        opdef.imputable = False
        task.active = True
        self.assertFalse(task.imputable)



    def test_on_order_task_imputable(self):
        opdef = self._operation_definition_dao.make()
        opdef.short_id = "TO"
        opdef.description = "Tour"
        opdef.imputable = True
        opdef.on_order = True
        opdef.on_operation = False
        session().add(opdef)
        session().flush() # Get the id for the opdef

        task = self.task_dao.create_non_billable_task(opdef.operation_definition_id)
        self.assertTrue(task.imputable)

        opdef.imputable = False
        task.active = False
        self.assertFalse(task.imputable)

        opdef.imputable = True
        task.active = False
        self.assertFalse(task.imputable)

        opdef.imputable = False
        task.active = True
        self.assertFalse(task.imputable)


@skip("out dated")
class TestPointageServer(TestBase):

    @classmethod
    def setUpClass(cls):
        super(TestPointageServer,cls).setUpClass()

        #     cls.opdef = cls._operation_definition_dao.make()
        #     cls.opdef.short_id = "ZZ"
        #     cls.opdef.description = "ZZ"
        #     cls.opdef.imputable = False
        #     cls.opdef.on_order = False
        #     cls.opdef.on_operation = False
        #     cls._operation_definition_dao.save(cls.opdef)
        #     cls.employee = cls.dao_employee.create("Don Knuth")


        cls.clock_server = ClockServer(DAO(session()))

    def setUp(self):
        session().query(TaskActionReport).delete()
        session().query(TimeTrack).delete()
        session().query(TaskOnNonBillable).delete()
        session().query(TaskOnOperation).delete()
        session().query(TaskOnOrder).delete()
        # session().query(Task).delete()
        session().commit()

    def test_report_on_operation(self):
        opdef = self._operation_definition_dao.make()
        opdef.short_id = "TO"
        opdef.description = "Tour"
        opdef.imputable = False
        opdef.on_order = False
        opdef.on_operation = False
        session().add(opdef)
        session().flush() # Get the id for the opdef

        try:
            r = self.clock_server._recordTaskOnOperation(-1)
        except ServerException as ex:
            self.assertEqual(ex.code,1004,"operation doesn't exist")

        customer = self.dao.customer_dao.make("AlphaCustomer")
        self.dao.customer_dao.save(customer)

        order = self.dao.order_dao.make("Test order no delete",customer)
        order.state = OrderStatusType.preorder_definition
        self.dao.order_dao.save(order)

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
        operation.operation_model = opdef
        session().add(operation)
        session().commit()

        try:
            r = self.clock_server._recordTaskOnOperation(operation.operation_id)
        except ServerException as ex:
            self.assertEqual(ex.code,1005,"order not in production")

        order.state = OrderStatusType.order_ready_for_production
        self.order_dao.save(order)
        session().flush()

        try:
            r = self.clock_server._recordTaskOnOperation(operation.operation_id)
        except ServerException as ex:
            self.assertEqual(ex.code,1005,"op def not imputable")

        opdef.imputable = True
        opdef.on_order = False
        opdef.on_operation = True
        session().flush()

        # This should create a brand new task on operation
        r = self.clock_server._recordTaskOnOperation(operation.operation_id)

        # We change the opdef so that it is not imputable anymore
        opdef.imputable = True
        opdef.on_order = True # trap !
        opdef.on_operation = False
        session().flush()

        try:
            r = self.clock_server._recordTaskOnOperation(operation.operation_id)
        except ServerException as ex:
            self.assertEqual(ex.code,1005,"op def not imputable")


    def test_report_on_non_billable(self):
        opdef = self._operation_definition_dao.make()
        opdef.short_id = "TO"
        opdef.description = "Tour"
        opdef.imputable = False
        opdef.on_order = False
        opdef.on_operation = False
        session().add(opdef)
        session().flush() # Get the id for the opdef

        try:
            r = self.clock_server._recordTaskOnNonBillable(-1)
        except ServerException as ex:
            self.assertEqual(ex.code,1001,"operation definition doesn't exist")

        try:
            r = self.clock_server._recordTaskOnNonBillable(opdef.operation_definition_id)
        except ServerException as ex:
            self.assertEqual(ex.code,1002, "op def is not imputable")

        opdef.imputable = True
        session().flush()

        r = self.clock_server._recordTaskOnNonBillable(opdef.operation_definition_id)
        task_id = r[0]
        self.assertIsNotNone(task_id,"A task is created")

        r = self.clock_server._recordTaskOnNonBillable(opdef.operation_definition_id)
        self.assertEqual(task_id, r[0], "Two reports on the same non billable shoudl report the same task")

        task = self.task_dao.find_by_id(task_id)
        task.active = False
        session().flush()

        try:
            r = self.clock_server._recordTaskOnNonBillable(opdef.operation_definition_id)
        except ServerException as ex:
            self.assertEqual(ex.code,1003, "task not active anymore")



    def _create_order(self):
        customer = self.dao.customer_dao.make("AlphaCustomer")
        self.dao.customer_dao.save(customer)

        order = self.dao.order_dao.make("Test order no delete",customer)
        order.state = OrderStatusType.preorder_definition
        self.dao.order_dao.save(order)

        order_part = self._order_part_dao.make(order)
        order_part.description = "Part 1"
        order_part.position = 1
        self._order_part_dao.save(order_part)

        pf = self.dao.production_file_dao.make()
        pf.order_part = order_part
        order_part.production_file = [pf]
        session().add(pf)
        session().flush()

        opdef = self._operation_definition_dao.make()
        opdef.short_id = "TO"
        opdef.description = "Tour"
        opdef.imputable = False
        opdef.on_order = False
        opdef.on_operation = False


        operation = self._operation_dao.make()
        operation.production_file = pf
        operation.description = "operation desc"
        operation.operation_model = opdef
        session().add(operation)
        session().commit()

        return customer,order,order_part,operation,opdef


    def test_report_on_order(self):
        try:
            r = self.clock_server._recordTaskOnOrder(-1,999999)
        except ServerException as ex:
            self.assertEqual(ex.code,1006,"operation doesn't exist")

        customer,order,order_part,operation,opdef = self._create_order()

        try:
            r = self.clock_server._recordTaskOnOrder(order.order_id,opdef.operation_definition_id)
        except ServerException as ex:
            self.assertEqual(ex.code,1007,"operation def/order not imputable")

        opdef.imputable = True
        opdef.on_order = True
        opdef.on_operation = False
        session().flush()

        try:
            r = self.clock_server._recordTaskOnOrder(order.order_id,opdef.operation_definition_id)
        except ServerException as ex:
            self.assertEqual(ex.code,1007,"operation def/order not imputable")

        order.state = OrderStatusType.order_ready_for_production # Activate !
        self.order_dao.save(order)

        r = self.clock_server._recordTaskOnOrder(order.order_id,opdef.operation_definition_id)



# @skip("")
class TestPresence(TestBase):

    def setUp(self):
        session().query(TaskActionReport).delete()
        session().query(TimeTrack).delete()
        session().query(TaskOnNonBillable).delete()
        session().query(TaskOnOperation).delete()
        session().query(TaskOnOrder).delete()
        session().query(DayTimeSynthesis).delete()

        # session().query(Task).delete()
        self.nb_task = self.task_dao.create_non_billable_task(self.opdef.operation_definition_id)
        self.nb_task_id = self.nb_task.task_id
        self.nb_task2 = self.task_dao.create_non_billable_task(self.opdef2.operation_definition_id)
        self.nb_task2_id = self.nb_task2.task_id
        session().commit()

        self.presence_task = session().query(TaskForPresence).filter(TaskForPresence.kind == TaskForPresenceType.regular_time).one()
        self.unemployment_task = session().query(TaskForPresence).filter(TaskForPresence.kind == TaskForPresenceType.unemployment_time).one()

    def _employee(self):
        return session().query(Employee).filter(Employee.employee_id == self.employee_id).one()

    def _nb_task(self):
        return session().query(TaskOnNonBillable).filter(TaskOnNonBillable.task_id == self.nb_task_id).one()

    def _nb_task2(self):
        return session().query(TaskOnNonBillable).filter(TaskOnNonBillable.task_id == self.nb_task2_id).one()

    def test_empty(self):
        d = date(2010,12,31)
        # self.tar_dao.reconciliate_timetracks2(d,self._employee())
        # self.tar_dao.reconciliate_timetracks(self.unemployment_task.task_id,self._employee().employee_id)
        self.tar_dao.compute_activity_timetracks_from_task_action_reports([],self._employee())

    def test_create_unemployment_time(self):
        self.tar_dao.start_unemployment(self._employee(),datetime(2010,12,31,13,00),'Nostromo')
        session().commit()

        self.tar_dao.start_unemployment(self._employee(),datetime(2010,12,31,13,20),'Nautilus')
        session().commit()


    def _task_efforts(self,employee,d):
        timetracks = self.timetrack_dao.all_for_employee_date(employee,d)

        mainlog.debug("Presence task : {}, unemployment task : {}".format(self.presence_task.task_id,self.unemployment_task.task_id))
        for tt in timetracks:
            mainlog.debug(u"_task_efforts() : {}".format(tt))
            if type(tt.task) == TaskForPresence:
                mainlog.debug("    presence : {}".format(tt.task.kind))

        totals = dict()
        for tt in timetracks:
            if tt.task not in totals:
                totals[tt.task] = 0
            totals[tt.task] += tt.duration

        return totals

    def test_unemployment_and_regular_task(self):
        d = date(2010,12,31)
        self.tar_dao.start_unemployment(self._employee(),datetime(2010,12,31,13,00),'Nostromo')
        session().commit()

        mainlog.debug("//////////////////////////////////////////////////// TAR")
        tar = self.tar_dao.create(self._nb_task(),self._employee(),datetime(2010,12,31,14,00),TaskActionReportType.start_task,"Mars")
        mainlog.debug("//////////////////////////////////////////////////// TAR")
        tar = self.tar_dao.create(self._nb_task(),self._employee(),datetime(2010,12,31,15,00),TaskActionReportType.stop_task,"Mars")
        mainlog.debug("//////////////////////////////////////////////////// TAR")
        tar = self.tar_dao.create(self._nb_task(),self._employee(),datetime(2010,12,31,16,00),TaskActionReportType.start_task,"Mars")
        mainlog.debug("//////////////////////////////////////////////////// TAR")
        tar = self.tar_dao.create(self._nb_task(),self._employee(),datetime(2010,12,31,17,00),TaskActionReportType.stop_task,"Mars")

        timetracks = self.timetrack_dao.all_work_for_employee_date(self._employee().employee_id,d)

        totals = self._task_efforts(self._employee(),d)
        self.assertEqual(2,totals[self._nb_task()])

        # Unemployment has no influence when it doesn't "cut" real work.
        self.tar_dao.start_unemployment(self._employee(),datetime(2010,12,31,13,20),'Nautilus')
        session().commit()

        totals = self._task_efforts(self._employee(),d)
        self.assertEqual(2,totals[self._nb_task()])
        self.assertEqual(4,totals[self.presence_task])

        # Unemployment start in the middle of the first task. Therefore
        # it "cuts" it.

        self.tar_dao.start_unemployment(self._employee(),datetime(2010,12,31,14,30),'Nautilus')
        session().commit()

        totals = self._task_efforts(self._employee(),d)
        self.assertEqual(1.5,totals[self._nb_task()])
        self.assertEqual(4,totals[self.presence_task])

        # What happens if there are two task

        tar = self.tar_dao.create(self._nb_task2(),self._employee(),datetime(2010,12,31,16,00),TaskActionReportType.start_task,"Mars")
        tar = self.tar_dao.create(self._nb_task2(),self._employee(),datetime(2010,12,31,17,00),TaskActionReportType.stop_task,"Mars")

        totals = self._task_efforts(self._employee(),d)
        self.assertEqual(1.5,totals[self._nb_task()])
        self.assertEqual(1,totals[self._nb_task2()])
        self.assertEqual(4,totals[self.presence_task])

        # And one of those task is create around the start of an
        # unemployment period ?

        tar = self.tar_dao.create(self._nb_task2(),self._employee(),datetime(2010,12,31,14,00),TaskActionReportType.start_task,"Mars")
        tar = self.tar_dao.create(self._nb_task2(),self._employee(),datetime(2010,12,31,15,00),TaskActionReportType.stop_task,"Mars")

        totals = self._task_efforts(self._employee(),d)
        self.assertEqual(1.5,totals[self._nb_task()])
        self.assertEqual(1 + 0.5,totals[self._nb_task2()]) # 1 is for the first timetrack (see above)
        self.assertEqual(4,totals[self.presence_task])



    def test_unemployement_after_task(self):
        d = date(2010,12,31)

        tar = self.tar_dao.create(self._nb_task(),self._employee(),datetime(2010,12,31,14,00),TaskActionReportType.start_task,"Mars")
        tar = self.tar_dao.create(self._nb_task(),self._employee(),datetime(2010,12,31,15,00),TaskActionReportType.stop_task,"Mars")

        tar = self.tar_dao.create(self._nb_task2(),self._employee(),datetime(2010,12,31,14,00),TaskActionReportType.start_task,"Mars")
        tar = self.tar_dao.create(self._nb_task2(),self._employee(),datetime(2010,12,31,16,00),TaskActionReportType.stop_task,"Mars")

        totals = self._task_efforts(self._employee(),d)
        self.assertEqual(1,totals[self._nb_task()])
        self.assertEqual(2,totals[self._nb_task2()])

        self.tar_dao.start_unemployment(self._employee(),datetime(2010,12,31,14,30),'Nostromo')

        totals = self._task_efforts(self._employee(),d)
        self.assertEqual(0.5,totals[self._nb_task()])
        self.assertEqual(0.5,totals[self._nb_task2()])
        self.assertTrue(self.unemployment_task not in totals)
        self.assertEqual(2,totals[self.presence_task])



    def test_unemployement_termination(self):
        d = date(2010,12,31)

        tar = self.tar_dao.create(self.nb_task,self._employee(),datetime(2010,12,31,14,00),TaskActionReportType.start_task,"Mars")
        tar = self.tar_dao.create(self.nb_task,self._employee(),datetime(2010,12,31,15,00),TaskActionReportType.stop_task,"Mars")

        tar = self.tar_dao.create(self.nb_task2,self._employee(),datetime(2010,12,31,14,00),TaskActionReportType.start_task,"Mars")
        tar = self.tar_dao.create(self.nb_task2,self._employee(),datetime(2010,12,31,16,00),TaskActionReportType.stop_task,"Mars")

        totals = self._task_efforts(self._employee(),d)
        self.assertEqual(1,totals[self.nb_task])
        self.assertEqual(2,totals[self.nb_task2])

        self.tar_dao.start_unemployment(self._employee(),datetime(2010,12,31,14,30),'Nostromo')

        mainlog.debug("--- --- ---")
        totals = self._task_efforts(self._employee(),d)
        self.assertTrue(self.unemployment_task not in totals)
        self.assertEqual(2,totals[self.presence_task])

        # Finishing a task later doesn't do anythin
        tar = self.tar_dao.create(self.nb_task,self._employee(),datetime(2010,12,31,17,00),TaskActionReportType.stop_task,"Mars")

        totals = self._task_efforts(self._employee(),d)
        self.assertTrue(self.unemployment_task not in totals)

        # But starting a new task automatically ends the current unemployment
        tar = self.tar_dao.create(self.nb_task,self._employee(),datetime(2010,12,31,14,45),TaskActionReportType.start_task,"Mars")

        totals = self.tar_dao.compute_activity_timetracks_from_task_action_reports(
            self.tar_dao.get_reports_for_employee_on_date(self._employee(), d),
            self._employee().employee_id)

        totals = self._task_efforts(self._employee(),d)

        self.assertTrue(self.unemployment_task in totals)
        self.assertEqual(0.25,totals[self.unemployment_task])
        self.assertEqual(3,totals[self.presence_task])


    def test_unemployment_and_presence(self):
        d = date(2010,12,31)

        self.tar_dao.start_unemployment(self._employee(),datetime(d.year,d.month,d.day,13,15),'Nostromo')
        session().commit()

        self.tar_dao.start_unemployment(self._employee(),datetime(d.year,d.month,d.day,13,00),'Nautilus')
        session().commit()

        self.assertEqual(0.25,dao.day_time_synthesis_dao.presence(self._employee().employee_id,d))


    def assert_presence(self, duration, d):

        assert abs(duration-self.tar_dao.presence_time( self._employee(), d)) < 0.000001

        assert abs(duration-dao.day_time_synthesis_dao.presence(self._employee().employee_id,d)) < 0.000001


    def test_presence(self):
        d = date(2010,12,31)

        mainlog.debug("------------------------------- // ---------------")
        mainlog.debug(session().query(DayTimeSynthesis).all())

        # 0 report means no presence
        self.assert_presence(0,d)

        # Only one report doesn't lead to a presence, we need 2
        self.tar_dao.create_presence_if_necessary(self._employee().employee_id, datetime(d.year,d.month,d.day,13,20), 'Nostromo')
        session().commit()

        self.assert_presence(0,d)

        # Two reports but on the same time, so 1 min presence
        self.tar_dao.create_presence_if_necessary(self._employee().employee_id, datetime(d.year,d.month,d.day,13,21), 'Nostromo')
        session().commit()
        self.assert_presence(1.0/60.0,d)

        # Three reports, but two of them gives a 15 min presence
        self.tar_dao.create_presence_if_necessary(self._employee().employee_id, datetime(d.year,d.month,d.day,13,35), 'Nostromo')
        session().commit()
        self.assert_presence(0.25,d)

        # is the computation done on the right day ?

        self.tar_dao.create_presence_if_necessary(self._employee().employee_id, datetime(d.year,d.month,29,13,5), 'Nostromo')
        self.assert_presence(0,date(2010,12,30))

        # Mixing presence and real work

        tar = self.tar_dao.create(self._nb_task(),self._employee(),datetime(d.year,d.month,d.day,14,00),TaskActionReportType.start_task,"Mars")

        mainlog.debug( dao.day_time_synthesis_dao.presence(self._employee().employee_id,d) )
        self.assertTrue((40.0/60.0 - dao.day_time_synthesis_dao.presence(self._employee().employee_id,d)) < 0.000001)

        tar = self.tar_dao.create(self._nb_task(),self._employee(),datetime(d.year,d.month,d.day,12,00),TaskActionReportType.start_task,"Mars")
        self.assert_presence(2,d)

        tar = self.tar_dao.create(self._nb_task(),self._employee(),datetime(d.year,d.month,d.day,10,00),TaskActionReportType.start_task,"Mars")

        tar = self.tar_dao.create(self._nb_task(),self._employee(),datetime(d.year,d.month,d.day,11,00),TaskActionReportType.start_task,"Mars")
        self.assert_presence(4,d)



    def test_pause(self):

        d = date(2010,12,31)


if __name__ == '__main__':
    # setup_test.init_test_database()
    # setup_test.add_user('dd','dd','Daniel Dumont','TimeTrackModify,ModifyParameters')
    # mainlog.setLevel(logging.ERROR)

    # Remember:
    # python -m unittest test_module.TestClass
    # python -m unittest test_module.TestClass.test_method

    # python -m unittest test.TestPointageServer

    unittest.main()
