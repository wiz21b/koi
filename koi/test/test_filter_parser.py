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
from koi.dao import *
from koi.datalayer.query_parser import find_suggestions, parse_order_parts_query, initialize_customer_cache


class TestFilterParser(TestBase):

    @classmethod
    def setUpClass(cls):
        super(TestFilterParser,cls).setUpClass()
        initialize_customer_cache()

    def test_queries(self):

        f = parse_order_parts_query("CreationDate In MonthBefore AND CLIENT = \"TAC\" AND STATUS = ABORTED")
        session().query(OrderPart).filter(f).all()

        f = parse_order_parts_query("CreationDate In (1/1/2013,1/1/2014)")
        session().query(OrderPart).filter(f).all()

        f = parse_order_parts_query("CreationDate AFTER DEADLINE")
        session().query(OrderPart).filter(f).all()

        f = parse_order_parts_query("CreationDate IN CURRENTMONTH")
        session().query(OrderPart).filter(f).all()

        f = parse_order_parts_query("(Deadline AFTER 1/1/2014) AND (CompletionDate  AFTER Deadline)")
        session().query(OrderPart).filter(f).all()

        f = parse_order_parts_query("delivery_slips = betrand")
        session().query(OrderPart).filter(f).all()


    def test_suggestions(self):

        self.assertEqual( (('rep', 9, 13), [u'Si\xe9mens'], True),
                           find_suggestions(u"delivery_slips = \"Si\xe9\"",11)) # cursor Inside Siemens

        self.assertEqual( (('rep', 19, 21), [u'AND', u'OR'], False),
                           find_suggestions('Client="ABMI sprl "  ',21))


        self.assertEqual( (('rep', 8, 9), [u'Si\xe9mens'], True),
                           find_suggestions("delivery_slips = ",9))

        self.assertEqual( (('rep', 16, 26), [u'MonthBefore'], False),
                           find_suggestions("CreationDate In MonthBefore",27))

        self.assertEqual( (('rep', 0, 2), ['Status'], False),
                           find_suggestions("sta",3))

        self.assertEqual( (('rep', 16, 16), ['Client', 'CompletionDate', 'CreationDate', 'Deadline', 'Description', 'DoneHours', 'NbNonConformities', 'PlannedHours', 'Price', 'Priority', 'Status', 'Total_Price'], False),
                           find_suggestions("CLIENT = TAC AND ",16))

        self.assertEqual( (('rep', 5, 5), [], False),
                           find_suggestions("zo zo ",5))

        mainlog.debug("TEST --------------------" + str(find_suggestions("CLIENT ",5)))

        mainlog.debug("TEST --------------------" + str(find_suggestions("CLIENT = A",8)))
        mainlog.debug("TEST --------------------" + str(find_suggestions("CLIENT = A",7)))
        mainlog.debug("TEST --------------------" + str(find_suggestions("CLIENT = TAC ",12)))
        mainlog.debug("TEST --------------------" + str(find_suggestions("CL",1)))

        mainlog.debug("TEST --------------------" + str(find_suggestions("CLIENT = A",10)))
        mainlog.debug("TEST --------------------" + str(find_suggestions("CLIENT = A )))",10)))
        mainlog.debug("TEST --------------------" + str(find_suggestions("CL",2)))


        mainlog.debug("TEST --------------------" + str(find_suggestions("status",6)))
        mainlog.debug("TEST --------------------" + str(find_suggestions("delivery_slips = ze",11)))

        mainlog.debug("TEST --------------------" + str(find_suggestions("delivery_slips = ",9)))



if __name__ == '__main__':
    unittest.main()
