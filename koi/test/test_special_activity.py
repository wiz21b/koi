import unittest
from unittest import skip

import datetime
from datetime import date,timedelta
import hashlib

from sqlalchemy.sql.expression import desc

from koi.test.test_base import TestBase
from koi.db_mapping import *
from koi.dao import *

import logging


from koi.Configurator import mainlog

class TestSpecialActivity(TestBase):

    def setUp(self):
        mainlog.setLevel(logging.DEBUG)

    def tearDown(self):
        session().query(SpecialActivity).delete()
        session().commit()

    def test_basic(self):

        start_time = datetime(2012,12,31,7)

        sa = SpecialActivity()
        sa.employee = self.employee
        sa.reporter = self.reporter
        sa.start_time = start_time
        sa.end_time = sa.start_time + timedelta(hours=48)  # will span 2 months
        sa.encoding_date = date.today()
        dao.special_activity_dao.save(sa)

        sa = SpecialActivity()
        sa.employee = self.employee
        sa.reporter = self.reporter
        sa.start_time = start_time
        sa.end_time = sa.start_time + timedelta(hours=1)
        sa.encoding_date = date.today()
        dao.special_activity_dao.save(sa)

        sa = SpecialActivity()
        sa.employee = self.reporter
        sa.reporter = self.reporter
        sa.start_time = start_time
        sa.end_time = sa.start_time + timedelta(hours=1)
        sa.encoding_date = date.today()
        dao.special_activity_dao.save(sa)

        l = dao.special_activity_dao.find_by_employee(self.employee, date(2012,11,1))
        self.assertEqual(0,len(l))

        l = dao.special_activity_dao.find_by_employee(self.employee, date(2012,12,1))
        self.assertEqual(2,len(l))

        l = dao.special_activity_dao.find_by_employee(self.employee, date(2013,1,1))
        self.assertEqual(1,len(l))

        l = dao.special_activity_dao.find_by_employee(self.employee, date(2013,2,1))
        self.assertEqual(0,len(l))

if __name__ == '__main__':
    unittest.main()
