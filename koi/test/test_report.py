import unittest
import os
from datetime import datetime

from koi.test.test_base import TestBase
from koi.Configurator import mainlog
from koi.dao import dao,session
from koi.reporting.utils import make_pdf_filename
from koi.reporting.preorder_report import _make_preorder_report
from koi.reporting.delivery_slip_report import _make_delivery_slip
from koi.reporting.order_activity_report import _print_iso_status # print_order_report,
from koi.db_mapping import DeliverySlipPart
from koi.reporting.rlab import _print_employees_badges, _print_non_billable_tasks

class TestReport(TestBase):

    def test_preorder_report(self):
        order = self._make_order()
        session().commit()

        n = make_pdf_filename("test")
        _make_preorder_report(order,n)
        mainlog.debug("Analyzing {}".format(n))
        mainlog.debug(os.path.getsize(n))

        # The report contains one part, valued at zero.
        assert os.path.getsize(n) > 25971, "bad size for {} : {}".format( n, os.path.getsize(n))
        os.remove(n)

    def test_print_iso_status(self):
        order = self._make_order()
        n = make_pdf_filename("test")
        _print_iso_status(dao,order.order_id,n)
        mainlog.debug(n)
        mainlog.debug(os.path.getsize(n))
        assert os.path.getsize(n) > 8000
        os.remove(n)


    def test_print_delivery_slip_report(self):
        order = self._make_order()
        order.parts[0].qty = 10
        order.parts[0].sell_price = 1
        session().commit()
        slip_id = self.delivery_slip_dao.make_delivery_slip_for_order(order.order_id, {order.parts[0].order_part_id : 5}, datetime.now(), False)

        n = make_pdf_filename("test")
        mainlog.debug(n)
        _make_delivery_slip(dao,slip_id,n)
        assert os.path.getsize(n) > 5000
        os.remove(n)

    def test_badges(self):
        n = make_pdf_filename("test")
        _print_employees_badges(dao, n)
        mainlog.debug( "Test badges. Filename {} = {} bytes".format(n, os.path.getsize(n)))
        assert os.path.getsize(n) > 8000
        os.remove(n)

    def test_non_billable_tasks(self):
        n = make_pdf_filename("test")
        _print_non_billable_tasks(dao, n)
        mainlog.debug( "Test non billable tasks. Filename {} = {} bytes".format(n, os.path.getsize(n)))
        assert os.path.getsize(n) > 8000
        os.remove(n)



if __name__ == '__main__':
    unittest.main()
