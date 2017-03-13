import datetime
from datetime import date
import unittest
from unittest import skip

import sys
if sys.version[0] == "2":
    from xmlrpclib import Fault
else:
    from xmlrpc.client import Fault

from sqlalchemy.exc import IntegrityError,InternalError
from sqlalchemy.sql.expression import func,select,join,and_,desc
from sqlalchemy.orm.session import Session

from koi.test.test_base import TestBase

from koi.db_mapping import *
from koi.dao import *

from koi.server.server import ClockServer,ServerException
from koi.PotentialTasksCache import PotentialTasksCache
from koi.BarCodeBase import BarCodeIdentifier




class TestTimeReportingServer(TestBase):

    def setUp(self):
        self.clock_server = ClockServer(dao)
        super(TestTimeReportingServer,self).setUp()


if __name__ == '__main__':
    unittest.main()
