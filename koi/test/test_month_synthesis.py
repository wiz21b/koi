import datetime
from datetime import date
import unittest
from unittest import skip
from sqlalchemy.exc import IntegrityError,InternalError
from sqlalchemy.sql.expression import func,select,join,and_,desc

from koi.test.test_base import TestBase

from koi.db_mapping import *
from koi.dao import *





class TestDaySynthesis(TestBase):

    def test_creation(self):
        self.month_time_synthesis_dao.save(self._employee().employee_id,2011,12,+3)
        session().close()

        dts = session().query(MonthTimeSynthesis).one()
        self.assertEqual(dts.year,2011)
        self.assertEqual(dts.month,12)
        self.assertEqual(dts.correction_time,+3)

        self.month_time_synthesis_dao.save(self._employee().employee_id,2011,12,+6)
        session().close()

        dts = session().query(MonthTimeSynthesis).one()
        self.assertEqual(dts.year,2011)
        self.assertEqual(dts.month,12)
        self.assertEqual(dts.correction_time,+6)

        session().close()
        self.assertEqual(+6,self.month_time_synthesis_dao.load_correction_time(self._employee().employee_id,2011,12))

if __name__ == "__main__":
    unittest.main()
