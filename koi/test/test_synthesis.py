import datetime
from datetime import date
import unittest
from unittest import skip

from sqlalchemy.exc import IntegrityError,InternalError
from sqlalchemy.sql.expression import func,select,join,and_,desc
from sqlalchemy.orm.session import Session


from koi.test.test_base import TestBase
from koi.db_mapping import *
from koi.dao import *

from koi.PotentialTasksCache import PotentialTasksCache




class TestDaySynthesis(TestBase):


    def test_creation(self):
        # check the insert
        d = date(2010,12,31)
        self.day_time_synthesis_dao.save(self._employee().employee_id,d,5.5,0)
        dts = session().query(DayTimeSynthesis).one()
        self.assertEqual(dts.day,d)
        self.assertEqual(dts.presence_time,5.5)
        session().close()

        t = self.day_time_synthesis_dao.monthly_presence(self._employee(),d.year,d.month)
        self.assertEqual(5.5,t)

        # Check the update
        self.day_time_synthesis_dao.save(self._employee().employee_id,d,2.5,0)
        dts = session().query(DayTimeSynthesis).one()
        self.assertEqual(dts.day,d)
        self.assertEqual(dts.presence_time,2.5)

        t = self.day_time_synthesis_dao.monthly_presence(self._employee(),d.year,d.month)
        self.assertEqual(2.5,t)

    def test_monthly_presence(self):

        self.day_time_synthesis_dao.save(self._employee().employee_id,date(2012,1,31),1,0)
        self.day_time_synthesis_dao.save(self._employee().employee_id,date(2012,2,10),2,0)
        self.day_time_synthesis_dao.save(self._employee().employee_id,date(2012,2,12),4,0)
        self.day_time_synthesis_dao.save(self._employee().employee_id,date(2012,3, 1),8,0)

        t = self.day_time_synthesis_dao.monthly_presence(self._employee(),2012,2)
        self.assertEqual(6,t)

    def test_daily_presence_update_on_tars(self):

        d = date(2012,10,10)
        cache = PotentialTasksCache(self.task_dao,d)
        tasks = cache.tasks_for_identifier(None)

        a = None
        for t in tasks:
            if t.operation_definition.short_id == "Unbi2":
                a = t
                break

        tar1 = self._make_tar(TaskActionReportType.start_task, datetime(2012,10,10,10) , self._employee(), a)
        tar2 = self._make_tar(TaskActionReportType.stop_task,  datetime(2012,10,10,11) , self._employee(), a)
        tar3 = self._make_tar(TaskActionReportType.start_task, datetime(2012,10,10,16) , self._employee(), a)
        tar4 = self._make_tar(TaskActionReportType.stop_task,  datetime(2012,10,10,17) , self._employee(), a)

        self.tar_dao.update_tars(self._employee(), d, [tar1,tar2,tar3,tar4], [])
        session().commit()

        t = self.day_time_synthesis_dao.monthly_presence(self._employee(),2012,10)
        self.assertEqual(7,t)


    def test_daily_presence_update_on_tars2(self):

        d = date(2012,10,10)
        cache = PotentialTasksCache(self.task_dao,d)
        tasks = cache.tasks_for_identifier(None)

        a = None
        for t in tasks:
            if t.operation_definition.short_id == "Unbi2":
                a = t
                break

        tar1 = self._make_tar(TaskActionReportType.start_task, datetime(2012,10,10,10) , self._employee(), a)
        tar2 = self._make_tar(TaskActionReportType.start_task,  datetime(2012,10,10,11,45) , self._employee(), a)

        self.tar_dao.update_tars(self._employee(), d, [tar1,tar2], [])
        session().commit()

        t = self.day_time_synthesis_dao.monthly_presence(self._employee(),2012,10)
        self.assertEqual(1.75,t)

    def test_daily_presence_update_on_tar_limits(self):

        d = date(2012,10,10)
        cache = PotentialTasksCache(self.task_dao,d)
        tasks = cache.tasks_for_identifier(None)

        # No TaskActionReport atall

        t = self.day_time_synthesis_dao.monthly_presence(self._employee(),2012,10)
        self.assertEqual(0,t)

        # A single TaskActionReport

        a = None
        for t in tasks:
            if t.operation_definition.short_id == "Unbi2":
                a = t
                break

        tar1 = self._make_tar(TaskActionReportType.start_task, datetime(2012,10,10,10) , self._employee(), a)
        self.tar_dao.update_tars(self._employee(), d, [tar1], [])

        t = self.day_time_synthesis_dao.monthly_presence(self._employee(),2012,10)
        self.assertEqual(0,t)

    def test_recompute_presence(self):

        d = date(2012,10,10)
        cache = PotentialTasksCache(self.task_dao,d)
        tasks = cache.tasks_for_identifier(None)

        a = None
        for t in tasks:
            if t.operation_definition.short_id == "Unbi2":
                a = t
                break

        tar1 = self._make_tar(TaskActionReportType.start_task, datetime(2012,10,10,10) , self._employee(), a)
        tar2 = self._make_tar(TaskActionReportType.stop_task,  datetime(2012,10,10,11,45) , self._employee(), a)

        tar_out = self._make_tar(TaskActionReportType.day_out,  datetime(2012,10,10,12) , self._employee(), a)

        tar3 = self._make_tar(TaskActionReportType.start_task, datetime(2012,10,10,13) , self._employee(), a)
        tar4 = self._make_tar(TaskActionReportType.stop_task,  datetime(2012,10,10,13,45) , self._employee(), a)

        self.tar_dao.update_tars(self._employee(), d, [tar1,tar2,tar_out,tar3,tar4], [])
        t = self.day_time_synthesis_dao.monthly_presence(self._employee(),2012,10)
        self.assertEqual(2.75,t)

        # Make sure it is safe on updates

        session().close()
        mainlog.debug(Session.object_session(tar1))

        tars = dao.task_action_report_dao.get_reports_for_employee( self._employee())

        for tar in tars:
            mainlog.debug(u"TEST >>> TAR : {} {} {} timetrack:{} task:{} / id():/".format(tar.task_action_report_id, tar.time,tar.kind,tar.timetrack_id,tar.task_id))


        self.tar_dao.update_tars(self._employee(), d, tars, [])
        t = self.day_time_synthesis_dao.monthly_presence(self._employee(),2012,10)
        self.assertEqual(2.75,t)



if __name__ == "__main__":
    unittest.main()
