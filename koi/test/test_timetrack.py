import unittest
import datetime
from datetime import date
import hashlib

from koi.test.test_base import TestBase

from koi.db_mapping import *
from koi.dao import *
from koi.PotentialTasksCache import PotentialTasksCache
from koi.EditTimeTracksDialog import ImputableProxy,TaskOnOrderProxy,TaskOnOperationProxy
from koi.Configurator import mainlog

class TestTimetrackBuild(TestBase):

    @classmethod
    def setUpClass(cls):
        super(TestTimetrackBuild,cls).setUpClass()

    # def setUp(self):
    #     session().query(TaskActionReport).delete()
    #     session().query(TimeTrack).delete()
    #     session().query(TaskOnNonBillable).delete()
    #     session().query(TaskOnOperation).delete()
    #     session().query(TaskOnOrder).delete()
    #     # db_mapping.session().query(Task).delete()

    #     self.opdef = session().query(OperationDefinition).filter(OperationDefinition.short_id == "Unbi").one()
    #     self.opdef2 = session().query(OperationDefinition).filter(OperationDefinition.short_id == "Unbi2").one()

    #     self.nb_task = self.task_dao.create_non_billable_task(self.opdef.operation_definition_id)
    #     self.nb_task2 = self.task_dao.create_non_billable_task(self.opdef2.operation_definition_id)
    #     session().commit()

    #     self.presence_task = session().query(TaskForPresence).filter(TaskForPresence.kind == TaskForPresenceType.regular_time).one()
    #     self.unemployment_task = session().query(TaskForPresence).filter(TaskForPresence.kind == TaskForPresenceType.unemployment_time).one()


    def test_potential_imputable_tasks_for_order_part(self):
        order = self._make_order()

        opdef_op = dao.operation_definition_dao.make()
        opdef_op.short_id = "DI"
        opdef_op.description = u"Disabled" + chr(233)
        opdef_op.imputable = True
        opdef_op.on_order = False
        opdef_op.on_operation = True
        dao.operation_definition_dao.save(opdef_op)

        operation = self._operation_dao.make()
        operation.production_file = order.parts[0].production_file[0]
        operation.description = u"second operation desc" + chr(233)
        operation.operation_model = opdef_op
        session().add(operation)
        session().commit()

        d = date(2010,12,31)
        proxy = ImputableProxy(d)
        order.state = OrderStatusType.order_ready_for_production
        dao.order_dao.save(order)
        session().flush()

        self.opdef_op.imputable = False
        session().commit()

        tasks = proxy.potential_imputable_task_for_order_part( order.parts[0].order_part_id)

        self.assertEqual( 2, len(tasks))
        self.assertTrue( isinstance(tasks[0],TaskOnOperationProxy))
        self.assertEqual( None, tasks[0].task_id)
        self.assertEqual( order.parts[0].production_file[0].operations[0].operation_id, tasks[0].operation_id)

        for task in tasks:
            mainlog.debug(task)

    @unittest.skip("I don't use the potential task anymore I think")
    def test_potential_imputable_tasks_for_order_part(self):
        order = self._make_order()

        opdef_op = dao.operation_definition_dao.make()
        opdef_op.short_id = "DI"
        opdef_op.description = u"Disabled" + chr(233)
        opdef_op.imputable = True
        opdef_op.on_order = False
        opdef_op.on_operation = True
        period = OperationDefinitionPeriod()
        period.start_date, period.end_date = date(2010,1,1), None
        opdef_op.periods.append(period)
        dao.operation_definition_dao.save(opdef_op)

        operation = self._operation_dao.make()
        operation.production_file = order.parts[0].production_file[0]
        operation.description = u"second operation desc" + chr(233)
        operation.operation_model = opdef_op
        session().add(operation)
        session().commit()

        d = date(2010,12,31)
        proxy = ImputableProxy(d)
        order.state = OrderStatusType.order_ready_for_production
        dao.order_dao.save(order)
        session().flush()

        session().commit()

        tasks = proxy.potential_imputable_task_for_order_part( order.parts[0].order_part_id)

        for task in tasks:
            mainlog.debug(task)
            op = dao.operation_dao.find_by_id(task.operation_id)
            mainlog.debug(op.operation_model.imputable)
            mainlog.debug(op.operation_model.on_operation)

        self.assertEqual( 2, len(tasks))
        self.assertTrue( isinstance(tasks[0],TaskOnOperationProxy))
        self.assertEqual( None, tasks[0].task_id)
        self.assertEqual( order.parts[0].production_file[0].operations[0].operation_id, tasks[0].operation_id)

        # Now we disable a task

        opdef_op.imputable = False
        dao.operation_definition_dao.save(opdef_op)

        tasks = proxy.potential_imputable_task_for_order_part( order.parts[0].order_part_id)

        for task in tasks:
            mainlog.debug(task)

        self.assertEqual( 1, len(tasks))



    def test_potential_imputable_tasks(self):

        # First we work with task which are already in the database


        d = date(2010,12,31)
        tasks = self.task_dao.potential_imputable_tasks_for(None,d)

        a = None
        for t in tasks:
            if t.operation_definition == self.opdef:
                a = t
                break
        self.assertTrue(a != None)


        tasks = self.task_dao.potential_imputable_tasks_for(None,d)

        b = None
        for t in tasks:
            if t.operation_definition == self.opdef:
                b = t
                break
        self.assertTrue(b != None)

        self.assertEqual(a.operation_definition,b.operation_definition) # Just to be sure :-)
        self.assertEqual(a,b)

        # Second, we test for task that do not exist yet in the database

        opdef = self._operation_definition_dao.make()
        opdef.short_id = "Unbi3"
        opdef.description = "Unbi3"
        opdef.imputable = True
        opdef.on_order = False
        opdef.on_operation = False

        period = OperationDefinitionPeriod()
        period.start_date, period.end_date = date(2010,1,1), None
        opdef.periods.append(period)

        self._operation_definition_dao.save(opdef)


        tasks = self.task_dao.potential_imputable_tasks_for(None,d)

        a = None
        for t in tasks:
            if t.operation_definition == opdef:
                a = t
                break
        self.assertTrue(a != None)


        tasks = self.task_dao.potential_imputable_tasks_for(None,d)

        b = None
        for t in tasks:
            if t.operation_definition == opdef:
                b = t
                break
        self.assertTrue(b != None)

        self.assertEqual(a.operation_definition,b.operation_definition) # Just to be sure :-)
        self.assertNotEqual(a,b)



    def potential_task_cache(self):
        d = date(2010,12,31)
        cache = PotentialTasksCache(self.task_dao,d)
        tasks = cache.tasks_for_identifier(None)

        a = None
        for t in tasks:
            if t.operation_definition == self.opdef:
                a = t
                break
        self.assertTrue(a != None)

        tasks = cache.tasks_for_identifier(None)

        for t in tasks:
            if t.operation_definition == self.opdef:
                b = t
                break
        self.assertTrue(b != None)

        self.assertEqual(a.operation_definition,b.operation_definition) # Just to be sure :-)
        self.assertEqual(a,b) # that's the difference with calling task_dao.potential_imputable_tasks_for

    def _standard_tar(self,kind,thetime):
        tar2 = TaskActionReport()
        tar2.kind = kind
        tar2.time = thetime
        tar2.origin_location = "OFFICE"
        tar2.editor = "Admin"
        tar2.reporter_id = self.employee.employee_id
        tar2.task = a
        tar2.report_time = datetime.today()
        tar2.status = TaskActionReport.CREATED_STATUS
        tar2.processed = False
        return tar2

    def _standard_timetrack(self,task_id,start_time,duration):
        tt = TimeTrack()
        tt.task_id = task_id
        tt.employee_id = self.employee.employee_id
        tt.duration = duration
        tt.start_time = start_time
        tt.encoding_date = date.today()
        tt.managed_by_code = False
        return tt


    def test_update_tar(self):
        d = date(2010,12,31)
        cache = PotentialTasksCache(self.task_dao,d)
        tasks = cache.tasks_for_identifier(None)
        a = None
        for t in tasks:
            if t.operation_definition.short_id == "Unbi":
                a = t
                break
        self.assertNotEqual(a, None)

        tar = TaskActionReport()
        tar.kind = TaskActionReportType.start_task
        tar.time = datetime.now() - timedelta(0,1111111)
        tar.origin_location = "OFFICE"
        tar.editor = "Admin"
        tar.reporter_id = self.employee.employee_id
        tar.task = a
        tar.report_time = datetime.today()
        tar.status = TaskActionReport.CREATED_STATUS
        tar.processed = False

        tasks = cache.tasks_for_identifier(None)
        a = None
        for t in tasks:
            if t.operation_definition.short_id == "Unbi":
                a = t
                break
        self.assertNotEqual(a, None)

        tar2 = TaskActionReport()
        tar2.kind = TaskActionReportType.stop_task
        tar2.time = datetime.now() - timedelta(0,3333333)
        tar2.origin_location = "OFFICE"
        tar2.editor = "Admin"
        tar2.reporter_id = self.employee.employee_id
        tar2.task = a
        tar2.report_time = datetime.today() # must be >= time
        tar2.status = TaskActionReport.CREATED_STATUS
        tar2.processed = False

        employee = session().query(Employee).all()[0]
        self.tar_dao.update_tars(employee, d, [tar,tar2], [])
        session().commit()

        employee = session().query(Employee).all()[0]
        cache = PotentialTasksCache(self.task_dao,d)
        tasks = cache.tasks_for_identifier(None)

        a = None
        for t in tasks:
            if t.operation_definition.short_id == "Unbi":
                a = t
                break

        tar = TaskActionReport()
        tar.kind = TaskActionReportType.start_task
        tar.time = datetime.now() - timedelta(0,3333333)
        tar.origin_location = "OFFICE"
        tar.editor = "Admin"
        tar.reporter_id = employee.employee_id
        tar.task = a
        tar.report_time = datetime.today()
        tar.status = TaskActionReport.CREATED_STATUS
        tar.processed = False

        tar2 = TaskActionReport()
        tar2.kind = TaskActionReportType.stop_task
        tar2.time = datetime.now() - timedelta(0,2222222)
        tar2.origin_location = "OFFICE"
        tar2.editor = "Admin"
        tar2.reporter_id = employee.employee_id
        tar2.task = a
        tar2.report_time = datetime.today()
        tar2.status = TaskActionReport.CREATED_STATUS
        tar2.processed = False

        self.tar_dao.update_tars(employee, d, [tar,tar2], [])
        session().commit()

    def _make_tar(self, kind, time, employee, task):
        tar = TaskActionReport()
        tar.kind = kind
        tar.time = time
        tar.origin_location = "OFFICE"
        tar.editor = "Admin"
        tar.reporter_id = employee.employee_id
        tar.task = task
        tar.report_time = datetime.today()
        tar.status = TaskActionReport.CREATED_STATUS
        tar.processed = False
        return tar

    def test_update_tar_insert(self):
        # Create a new^opdef to make sure there's no task associated
        # to it

        opdef = self._operation_definition_dao.make()
        opdef.short_id = "Unbi3"
        opdef.description = "Unbi3"
        opdef.imputable = True
        opdef.on_order = False
        opdef.on_operation = False
        period = OperationDefinitionPeriod()
        period.start_date, period.end_date = date(2010,1,1), None
        opdef.periods.append(period)
        self._operation_definition_dao.save(opdef)

        d = date(2012,10,10)
        employee = session().query(Employee).all()[0]
        cache = PotentialTasksCache(self.task_dao,d)
        tasks = cache.tasks_for_identifier(None)

        a = None
        for t in tasks:
            if t.operation_definition.short_id == "Unbi3":
                a = t
                break

        tar1 = self._make_tar(TaskActionReportType.start_task, datetime(2012,10,10,10) , employee, a)
        tar2 = self._make_tar(TaskActionReportType.stop_task,  datetime(2012,10,10,11) , employee, a)
        tar3 = self._make_tar(TaskActionReportType.start_task, datetime(2012,10,10,16) , employee, a)
        tar4 = self._make_tar(TaskActionReportType.stop_task,  datetime(2012,10,10,17) , employee, a)

        self.tar_dao.update_tars(employee, d, [tar1,tar2,tar3,tar4], [])
        session().commit()

        for tt in session().query(TimeTrack).all():
            mainlog.debug(u"CHECK: {}".format(tt))
        for tt in session().query(TaskActionReport).all():
            mainlog.debug(u"CHECK: {}".format(tt))

        session().close()

        employee = session().query(Employee).all()[0]
        cache = PotentialTasksCache(self.task_dao,d)
        tasks = cache.tasks_for_identifier(None)

        mainlog.debug("///////////////////////////////////////")

        tars = session().query(TaskActionReport).all()
        self.assertEqual(4,len(tars))
        for tar in tars:
            mainlog.debug(u"Reloaded: {}".format(tar))


        a = None
        for t in tasks:
            if t.operation_definition.short_id == "Unbi3":
                a = t
                break
        task_a_id = a.task_id
        tar5 = self._make_tar(TaskActionReportType.day_out, datetime(2012,10,10,12) , employee, dao.task_action_report_dao.presence_task())
        tars.append(tar5)
        self.tar_dao.update_tars(employee, d, tars, [])

        session().commit()
        session().close()

        for tt in session().query(TimeTrack).all():
            mainlog.debug(u"CHECK: {}".format(tt))

        tars = session().query(TaskActionReport).all()
        self.assertEqual(5,len(tars))

        self.assertEqual(4, session().query(TimeTrack).count())
        self.assertEqual(2, session().query(TimeTrack).filter(TimeTrack.task_id == task_a_id).count())
        self.assertEqual(2, session().query(TimeTrack).filter(TimeTrack.task == self.tar_dao.presence_task()).count())


    def set_situation( self, kind_time_pairs):
        tars = []
        session().query(TaskActionReport).delete()
        for kind, time in kind_time_pairs:

            if kind in (TaskActionReportType.start_task, TaskActionReportType.stop_task):
                tar = self._make_tar(kind, time, self.employee, self.base_task)
            else:
                tar = self._make_tar(kind, time, self.employee, dao.task_action_report_dao.presence_task())

            session().add(tar)
            tars.append(tar)
        session().commit()
        return tars

    def test_find_reports_to_reconciliate(self):
        d = date(2012,10,23)
        cache = PotentialTasksCache(self.task_dao,d)
        tasks = cache.tasks_for_identifier(None)

        self.base_task = tasks[0] # for set_situation function

        # Regular situation ---------------------------------------------------

        tars = self.set_situation( [(TaskActionReportType.start_task, datetime(2012,10,23,13)),
                                    (TaskActionReportType.stop_task, datetime(2012,10,24,5))] )

        reports = dao.task_action_report_dao._find_reports_to_reconciliate( tars[0])
        assert len(reports) == 2

        reports = dao.task_action_report_dao._find_reports_to_reconciliate( tars[1])
        assert len(reports) == 2

        # Two TARs very far apart ---------------------------------------------

        tars = self.set_situation( [(TaskActionReportType.start_task, datetime(2012,10,23,13)),
                                    (TaskActionReportType.stop_task, datetime(2012,11,24,5))] )

        reports = dao.task_action_report_dao._find_reports_to_reconciliate( tars[0])
        assert not reports

        reports = dao.task_action_report_dao._find_reports_to_reconciliate( tars[1])
        assert not reports

        # A shadowed start TAR ------------------------------------------------

        tars = self.set_situation( [(TaskActionReportType.start_task, datetime(2012,10,23,10)),
                                    (TaskActionReportType.start_task, datetime(2012,10,23,11)),
                                    (TaskActionReportType.stop_task,  datetime(2012,10,23,12))] )

        # This one is shadowed by the previous one => it'll have no effect
        reports = dao.task_action_report_dao._find_reports_to_reconciliate( tars[1])
        assert not reports

        # The zero-th one shadows the next one
        reports = dao.task_action_report_dao._find_reports_to_reconciliate( tars[0])
        assert len(reports) == 3

        # Final check. The stop will want the earliest TAR
        reports = dao.task_action_report_dao._find_reports_to_reconciliate( tars[2])
        assert len(reports) == 3

        # A shadowed stop TAR -------------------------------------------------

        tars = self.set_situation( [(TaskActionReportType.start_task, datetime(2012,10,23,10)),
                                    (TaskActionReportType.stop_task,  datetime(2012,10,23,11)),
                                    (TaskActionReportType.stop_task,  datetime(2012,10,23,12))] )

        reports = dao.task_action_report_dao._find_reports_to_reconciliate( tars[0])
        assert len(reports) == 2

        reports = dao.task_action_report_dao._find_reports_to_reconciliate( tars[1])
        assert len(reports) == 2

        reports = dao.task_action_report_dao._find_reports_to_reconciliate( tars[2])
        assert not reports


        # dao.task_action_report_dao.compute_activity_timetracks_from_task_action_reports(reports,self.employee)




    @unittest.skip("Not necesary any more, left here for test fodder")
    def test_multi_days(self):
        d = date(2012,10,23)
        cache = PotentialTasksCache(self.task_dao,d)
        tasks = cache.tasks_for_identifier(None)

        # Add a timetrack long after tar1,2
        tar3 = self._make_tar(TaskActionReportType.start_task, datetime(2012,11,23,13), self.employee, tasks[0])
        tar4 = self._make_tar(TaskActionReportType.stop_task, datetime(2012,11,24,5), self.employee, tasks[0])
        session().add(tar3)
        session().add(tar4)
        session().commit()

        def _join_tars(tar1, tar2):
            assert tar1.reporter_id == tar2.reporter_id
            assert tar1.task_id is not None and tar1.task_id == tar2.task_id
            assert tar1.time and tar2.time

            tt = TimeTrack()
            tt.task_id = tar1.task_id
            tt.employee_id = tar1.reporter_id

            d = (tar2.time - tar1.time)
            tt.duration = d.days * 24 + float(d.seconds) / 3600.0
            tt.start_time = tar1.time
            tt.encoding_date = date.today()
            tt.managed_by_code = True

            session().add(tt)
            tar1.timetrack = tt
            tar2.timetrack = tt

            return tt

        tt34 = _join_tars(tar3, tar4)
        session().commit()

        tars = self.tar_dao._find_reports_to_reconciliate( tasks[0].task_id, self.employee.employee_id)
        assert len(tars) == 2
        assert tar1 in tars
        assert tar2 in tars

        # Add a timetrack long before tar1,2
        tar5 = self._make_tar(TaskActionReportType.start_task, datetime(2012,9,23,13), self.employee, tasks[0])
        tar6 = self._make_tar(TaskActionReportType.stop_task, datetime(2012,9,24,5), self.employee, tasks[0])
        session().add(tar5)
        session().add(tar6)
        session().commit()
        tt56 = _join_tars(tar5, tar6)
        session().commit()

        tars = self.tar_dao._find_reports_to_reconciliate( tasks[0].task_id, self.employee.employee_id)
        assert len(tars) == 2
        assert tar1 in tars
        assert tar2 in tars

        # Add a timetrack inside tar1,2
        tar7 = self._make_tar(TaskActionReportType.start_task, datetime(2012,10,23,20), self.employee, tasks[0])
        tar8 = self._make_tar(TaskActionReportType.stop_task, datetime(2012,10,24,1), self.employee, tasks[0])
        session().add(tar7)
        session().add(tar8)
        session().commit()
        tt78 = _join_tars(tar7, tar8)
        session().commit()

        from sqlalchemy.sql.expression import cast
        from datetime import timedelta
        from sqlalchemy.types import Interval,Integer

        for tt,the_duration in session().query(TimeTrack.start_time,
                                               (TimeTrack.duration * cast('1 hour', Interval)).label('the_duration')).all():
            mainlog.debug(tt)
            mainlog.debug(the_duration)

        tars = self.tar_dao._find_reports_to_reconciliate( tasks[0].task_id, self.employee.employee_id)
        for tar in tars:
            mainlog.debug(tar)
        assert len(tars) == 4
        assert tar1 in tars
        assert tar2 in tars
        assert tar7 in tars
        assert tar8 in tars

        self.tar_dao.compute_activity_timetracks_from_task_action_reports(tars, self.employee)

        assert dao.operation_dao._find_next_action_for_task(tasks[0].task_id, self.employee.employee_id) == TaskActionReportType.start_task

        tts = session().query(TimeTrack.start_time,TimeTrack.duration).order_by(TimeTrack.start_time).all()

        assert tts[0].start_time == tt56.start_time

        assert tts[1].start_time == tar7.time
        assert tts[1].duration == 5 # We counted the last start and the first stop FIXME I don't like that, what about first start and last stop ?

        assert tts[2].start_time == tt34.start_time


        assert 3 == session().query(TimeTrack).count()


    def test_interval_tracker_task(self):
        """ Test the interval tracker class on various configurations of
        task action reports
        """

        d = date(2012,10,23)
        cache = PotentialTasksCache(self.task_dao,d)
        tasks = cache.tasks_for_identifier(None)

        self.base_task = tasks[0] # for set_situation function


        tars = self.set_situation( [(TaskActionReportType.start_task, datetime(2012,10,23,10)),
                                    (TaskActionReportType.stop_task,  datetime(2012,10,23,11)),
                                    (TaskActionReportType.stop_task,  datetime(2012,10,23,12))] )

        itracker = IntervalTracker(self.base_task.task_id, self.employee.employee_id)
        for tar in tars:
            itracker.handle_report(tar)

        assert len(itracker.timetracks) == 1
        tt, reports = itracker.timetracks[0]
        assert len(reports) == 3



        tars = self.set_situation( [ (TaskActionReportType.start_task,  datetime(2012,10,23,11))] )

        itracker = IntervalTracker(self.base_task.task_id, self.employee.employee_id)
        for tar in tars:
            itracker.handle_report(tar)

        assert len(itracker.timetracks) == 0



        tars = self.set_situation( [ (TaskActionReportType.stop_task,  datetime(2012,10,23,11))] )

        itracker = IntervalTracker(self.base_task.task_id, self.employee.employee_id)
        for tar in tars:
            itracker.handle_report(tar)

        assert len(itracker.timetracks) == 0



        tars = self.set_situation( [ (TaskActionReportType.stop_task,  datetime(2012,10,23,11)),
                                     (TaskActionReportType.stop_task,  datetime(2012,10,23,12)),
                                     (TaskActionReportType.start_task, datetime(2012,10,23,10)),] )

        itracker = IntervalTracker(self.base_task.task_id, self.employee.employee_id)
        for tar in tars:
            itracker.handle_report(tar)

        assert len(itracker.timetracks) == 0



        tars = self.set_situation( [ (TaskActionReportType.start_task, datetime(2012,10,23,10)),
                                     (TaskActionReportType.stop_task,  datetime(2012,10,23,11)),
                                     (TaskActionReportType.stop_task,  datetime(2012,10,23,12)),
                                     (TaskActionReportType.start_task, datetime(2012,10,23,13)),
                                     (TaskActionReportType.start_task, datetime(2012,10,23,14)),
                                     (TaskActionReportType.stop_task,  datetime(2012,10,23,15)),] )

        itracker = IntervalTracker(self.base_task.task_id, self.employee.employee_id)
        for tar in tars:
            itracker.handle_report(tar)

        assert len(itracker.timetracks) == 2

    def test_multi_update(self):

        d = date(2012,10,23)
        cache = PotentialTasksCache(self.task_dao,d)
        tasks = cache.tasks_for_identifier(None)
        tt1 = self._standard_timetrack(tasks[0].task_id, datetime.now(), 1)
        tt1.employee = self.employee
        tt2 = self._standard_timetrack(tasks[0].task_id, datetime.now(), 2)
        tt2.employee = self.employee

        session().close()

        mainlog.debug(tt1)
        mainlog.debug(tt1.employee)
        mainlog.debug(tt1.task)

        self.timetrack_dao.multi_update(tt1.employee,d,[],[tt1],[])
        for tt in session().query(TimeTrack).all():
            mainlog.debug(u"CHECK: {}".format(tt))
        session().close()

        tt1 = session().query(TimeTrack).one()
        self.timetrack_dao.multi_update(tt1.employee,d,[tt1],[tt2],[])

        for tt in session().query(TimeTrack).all():
            mainlog.debug(u"CHECK: {}".format(tt))


    def _recompute_work_periods( self, d):
        tars = dao.task_action_report_dao.get_reports_for_employee_id_on_date( self.employee.employee_id, d)

        return dao.task_action_report_dao._compute_man_work_time_on_tars(
            self.employee.employee_id, d, tars)


    def test_tar_and_presence(self):
        cache = PotentialTasksCache(self.task_dao,datetime(2012,10,23))
        tasks = cache.tasks_for_identifier(None)
        self.base_task = tasks[0] # for set_situation function

        res = self._recompute_work_periods( datetime(2012,10,23))
        self.assertEqual( 0, len(res))


        tars = self.set_situation( [ (TaskActionReportType.start_task, datetime(2012,10,23,10)),
                                     (TaskActionReportType.stop_task,  datetime(2012,10,23,11)),
                                     (TaskActionReportType.stop_task,  datetime(2012,10,23,12)),
                                     (TaskActionReportType.start_task, datetime(2012,10,23,13)),
                                     (TaskActionReportType.start_task, datetime(2012,10,23,14)),
                                     (TaskActionReportType.stop_task,  datetime(2012,10,23,15)),] )

        res = self._recompute_work_periods( datetime(2012,10,23))

        self.assertEqual( 1, len(res))
        self.assertEqual( res[0].duration().total_seconds() / 3600.0, 5)

        #  Double start
        tars = self.set_situation( [ (TaskActionReportType.start_task, datetime(2012,10,23,10)),
                                     (TaskActionReportType.start_task, datetime(2012,10,23,13))] )

        res = self._recompute_work_periods( datetime(2012,10,23))
        self.assertEqual( 1, len(res))
        self.assertEqual( res[0].duration().total_seconds() / 3600.0, 3)

        # Just one TAR
        tars = self.set_situation( [ (TaskActionReportType.start_task, datetime(2012,10,23,10))] )

        res = self._recompute_work_periods( datetime(2012,10,23))
        self.assertEqual( 0, len(res))


    def test_tar_and_presence_interuption(self):
        cache = PotentialTasksCache(self.task_dao,datetime(2012,10,23))
        tasks = cache.tasks_for_identifier(None)
        self.base_task = tasks[0] # for set_situation function



        tars = self.set_situation( [ (TaskActionReportType.start_task,  datetime(2012,10,23,10)),
                                     (TaskActionReportType.start_pause, datetime(2012,10,23,11)),
                                     (TaskActionReportType.stop_task,   datetime(2012,10,23,12)),
                                     (TaskActionReportType.day_out,     datetime(2012,10,23,14)) ])

        res = self._recompute_work_periods( datetime(2012,10,23))
        self.assertEqual( 2, len(res))
        self.assertEqual( res[0].duration().total_seconds() / 3600.0, 1)
        self.assertEqual( res[1].duration().total_seconds() / 3600.0, 2)


    def test_tar_and_presence_interuption_edge_cases(self):
        cache = PotentialTasksCache(self.task_dao,datetime(2012,10,23))
        tasks = cache.tasks_for_identifier(None)
        self.base_task = tasks[0] # for set_situation function

        tars = self.set_situation( [ (TaskActionReportType.start_task, datetime(2012,10,23,10)),
                                     (TaskActionReportType.day_out,    datetime(2012,10,23,11)),
                                     (TaskActionReportType.day_out,    datetime(2012,10,23,12)) ])

        res = self._recompute_work_periods( datetime(2012,10,23))
        self.assertEqual( 1, len(res))
        self.assertEqual( res[0].duration().total_seconds() / 3600.0, 1)


        tars = self.set_situation( [ (TaskActionReportType.start_task, datetime(2012,10,23,10)),
                                     (TaskActionReportType.day_out,    datetime(2012,10,23,11)) ])

        res = self._recompute_work_periods( datetime(2012,10,23))
        self.assertEqual( 1, len(res))
        self.assertEqual( res[0].duration().total_seconds() / 3600.0, 1)



    def test_timetrack_faster_create(self):

        cache = PotentialTasksCache(self.task_dao,datetime(2012,10,23))
        tasks = cache.tasks_for_identifier(None)
        self.base_task = tasks[0] # for set_situation function

        dao.task_action_report_dao.fast_create_after(self.base_task.task_id,
                                                     self.employee.employee_id,
                                                     datetime(2012,10,23,10),
                                                     TaskActionReportType.start_task,
                                                     "The grid")

        dao.task_action_report_dao.fast_create_after(self.base_task.task_id,
                                                     self.employee.employee_id,
                                                     datetime(2012,10,23,11),
                                                     TaskActionReportType.stop_task,
                                                     "The grid")


        assert 2 == session().query(TaskActionReport).count()
        assert 2 == session().query(TimeTrack).count()


        dao.task_action_report_dao.fast_create_after(self.base_task.task_id,
                                                     self.employee.employee_id,
                                                     datetime(2012,10,23,12),
                                                     TaskActionReportType.start_task,
                                                     "The grid")

        dao.task_action_report_dao.fast_create_after(self.base_task.task_id,
                                                     self.employee.employee_id,
                                                     datetime(2012,10,23,13),
                                                     TaskActionReportType.stop_task,
                                                     "The grid")

        assert 4 == session().query(TaskActionReport).count()
        assert 3 == session().query(TimeTrack).count()

if __name__ == '__main__':
    unittest.main()
