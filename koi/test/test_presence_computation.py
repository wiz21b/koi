import unittest

from koi.test.test_base import TestBase
from koi.db_mapping import *
from koi.dao import *


class TestPresenceComputation(TestBase):

    @classmethod
    def setUpClass(cls):
        super(TestPresenceComputation,cls).setUpClass()

    def setUp(self):
        super(TestPresenceComputation,self).setUp()

    def test_recompute_presence_on_tars(self):

        order = self._make_order()
        order.state = OrderStatusType.order_ready_for_production

        task = dao.task_dao.potential_imputable_tasks_for(order, date(2012,10,10))[0]

        tar1 = self._make_tar(TaskActionReportType.presence,   datetime(2012,10,10,10), self._employee(), dao.task_action_report_dao.presence_task())
        tar2 = self._make_tar(TaskActionReportType.day_out,    datetime(2012,10,10,11), self._employee(), dao.task_action_report_dao.presence_task())
        tar3 = self._make_tar(TaskActionReportType.stop_task, datetime(2012,10,10,16), self._employee(), task)

        all_tars = [tar1,tar2,tar3]
        presence_time, off_time, presence_timetracks = dao.task_action_report_dao.recompute_presence_on_tars(self._employee(), all_tars)

        mainlog.debug(presence_time)
        mainlog.debug(off_time)

        for t in presence_timetracks:
            mainlog.debug(t)

        self.assertEqual(1,presence_time)
        self.assertEqual(0,off_time)
        self.assertEqual(1,len(presence_timetracks))
        self.assertEqual(1,presence_timetracks[0].duration)


if __name__ == "__main__":
    unittest.main()
