import unittest
from unittest import skip

import datetime
from datetime import date
import hashlib
import logging
from collections import OrderedDict

from sqlalchemy.sql.expression import desc

from koi.test.test_base import TestBase
from koi.stock.stock_mapping import StockItem

from koi.dao import *
from koi.Configurator import mainlog
from koi.datalayer.data_exception import DataException

from decimal import Decimal

class TestStock(TestBase):
    #
    # def setUp(self):
    #     self._clear_database_content()


    def test_delivery_slip_blank_creation(self):

        stock_item = StockItem()
        stock_item.initial_quantity = 24.5
        stock_item.quantity_left = 24.5
        stock_item.buy_price = 1.3
        session().add(stock_item)

        stock_item = StockItem()
        stock_item.initial_quantity = 12.3
        stock_item.quantity_left = 12.3
        stock_item.buy_price = 1.1
        session().add(stock_item)

        session().commit()

        self.assertEqual( Decimal("1.1"), stock_item.buy_price)

        s = session().query(func.sum(StockItem.buy_price)).scalar()

        self.assertEqual( Decimal("2.4"), s)



if __name__ == '__main__':
    unittest.main()
