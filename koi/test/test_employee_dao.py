import unittest
from unittest import skip
import logging

from datetime import date, datetime, timedelta
import hashlib
from collections import OrderedDict
from sqlalchemy.sql.expression import desc

from koi.test.test_base import TestBase
from koi.db_mapping import *
from koi.dao import *
from koi.Configurator import mainlog
from koi.datalayer.audit_trail_service import audit_trail_service

class TestEmployeeDao(TestBase):

    def test_find_activity(self):
        # Time reporting must always occur in the past (else you're predicting future :-))

        n = datetime.now()
        start_date = datetime( n.year, n.month, n.day,1,0,0) - timedelta(days=365)
        end_date = start_date + timedelta(days=1)

        assert len( dao.employee_dao.find_activity(self.employee_id, start_date, end_date)) == 2

        order = self._make_order()
        operation = order.parts[0].operations[0]

        self.add_work_on_operation(operation, start_date, duration=1)
        self.add_work_on_operation(operation, start_date, duration=2)
        self.add_work_on_operation(operation, end_date, duration=4)

        r = dao.employee_dao.find_activity(self.employee_id, start_date, end_date)
        assert r[0].duration == 1+2
        assert r[1].duration == 4

        machine = self._make_machine("The machine", operation.operation_definition_id)
        task_id = dao.task_dao._get_task_for_operation_and_machine(operation.operation_id, machine.machine_id, commit=True)

        dao.task_action_report_dao.fast_create_after( task_id, self.employee_id, start_date,                      TaskActionReportType.start_task, "Nautilus")
        dao.task_action_report_dao.fast_create_after( task_id, self.employee_id, start_date + timedelta(hours=8), TaskActionReportType.stop_task,  "Nautilus")


        r = dao.employee_dao.find_activity(self.employee_id, start_date, end_date)

        assert r[0].duration == 1+2+8
        assert r[1].duration == 4



if __name__ == '__main__':
    unittest.main()
