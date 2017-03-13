import unittest
from unittest import skip
import logging

import datetime
from datetime import date
import hashlib
from collections import OrderedDict
from sqlalchemy.sql.expression import desc

from koi.test.test_base import TestBase
from koi.Configurator import mainlog
from koi.db_mapping import *
from koi.datalayer.filters_dao import FilterQueryDAO


"""
filter1 V | a > b AND c == SDFSDFS | Save | SaveAs

"""


class TestFiltersDao(TestBase):

    def setUp(self):
        self._clear_database_content()
        self.filters_dao = FilterQueryDAO()


    def test_names_must_be_different(self):
        fq = self.filters_dao.make()
        fq.name ="test"
        fq.query = "date > 12/2/3000"
        fq.owner_id = self.employee.employee_id
        fq.shared = False
        fq.family = "family"
        id1 = self.filters_dao.save(fq)

        try:
            id2 = self.filters_dao.save(fq)
            self.fail()
        except Exception as ex:
            pass

    def test_create(self):

        fq = self.filters_dao.make()
        fq.name ="test"
        fq.query = "date > 12/2/3000"
        fq.owner_id = self.employee.employee_id
        fq.shared = False
        fq.family = "family"
        id1 = self.filters_dao.save(fq)

        fq = self.filters_dao.make()
        fq.name ="test"
        fq.query = "date > 12/2/3000"
        fq.owner_id = self.reporter.employee_id
        fq.shared = False
        fq.family = "family"
        id2 = self.filters_dao.save(fq)


        l = self.filters_dao.usable_filters(self.employee.employee_id, "family")
        self.assertEqual( 1, len(l))
        self.assertEqual( self.employee.employee_id, l[0].owner_id)

        l = self.filters_dao.usable_filters(12346879, "family")
        self.assertEqual( 0, len(l))

        fq = self.filters_dao.find_by_id(id1)
        fq.shared = True
        self.filters_dao.save(fq)

        l = self.filters_dao.usable_filters(self.reporter.employee_id, "family")
        self.assertEqual( 2, len(l))

if __name__ == '__main__':
    unittest.main()
