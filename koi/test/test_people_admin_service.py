import unittest
from unittest import skip
# from PySide.QtGui import QApplication,QMainWindow
# from PySide.QtTest import QTest

from datetime import date

from koi.test.test_base import TestBase, mainlog

# from koi.chrono import *
# from PySide.QtGui import QApplication
# app = QApplication(sys.argv)


from koi.datalayer.database_session import session
from koi.server.json_decorator import ServerException,JsonCallWrapper, ServerErrors
from datetime import datetime, timedelta
from koi.dao import dao
from koi.date_utils import ts_to_date

from koi.people_admin.people_admin_mapping import DayEvent,DayEventType
from koi.people_admin.people_admin_service import DayEventService


class TestPeopleAdminService(TestBase):

    @classmethod
    def setUpClass(cls):
        super(TestPeopleAdminService,cls).setUpClass()
        cls.server = JsonCallWrapper( DayEventService(), JsonCallWrapper.IN_PROCESS_MODE)


    def test_set_day_event(self):
        event = DayEvent()
        event.employee_id = self.employee_id
        event.event_type = DayEventType.holidays

        mainlog.debug("Type {}".format(type(event)))

        self.server.set_event_on_days(event, [ (date(2012,12,15), 7.5) ] )

        r = self.server.events_for_month(date(2012,12,1))
        mainlog.debug(r)
        assert len(r) == 1
        assert r[0].duration == 7.5
        assert r[0].date == date(2012,12,15)
        assert r[0].event_type == DayEventType.holidays
        assert r[0].employee_id == self.employee_id


    def test_two_days_event_same_type_same_day(self):
        event = DayEvent()
        event.employee_id = self.employee_id
        event.event_type = DayEventType.holidays

        self.server.set_event_on_days(event, [ (date(2012,12,15), 0.5) ] )

        event2 = DayEvent()
        event2.employee_id = self.employee_id
        event2.event_type = DayEventType.holidays

        self.server.set_event_on_days(event2, [ (date(2012,12,15), 0.6) ] )

        r = self.server.events_for_month(date(2012,12,1))
        assert len(r) == 1
        assert r[0].duration == 0.6
        assert r[0].date == date(2012,12,15)


    def test_two_days_event_different_type_same_day(self):
        event = DayEvent()
        event.employee_id = self.employee_id
        event.event_type = DayEventType.holidays

        self.server.set_event_on_days(event, [ (date(2012,12,15), 0.5) ] )

        event2 = DayEvent()
        event2.employee_id = self.employee_id
        event2.event_type = DayEventType.sick_leave

        self.server.set_event_on_days(event2, [ (date(2012,12,15), 0.5) ] )

        r = self.server.events_for_month(date(2012,12,1))
        assert len(r) == 2


    def test_two_days_event_different_type_same_day_and_overflow(self):
        event = DayEvent()
        event.employee_id = self.employee_id
        event.event_type = DayEventType.holidays

        self.server.set_event_on_days(event, [ (date(2012,12,15), 0.5) ] )

        event2 = DayEvent()
        event2.employee_id = self.employee_id
        event2.event_type = DayEventType.sick_leave

        try:
            self.server.set_event_on_days(event2, [ (date(2012,12,15), 0.6) ] )
        except ServerException as ex:
            assert ex.code == ServerErrors.too_much_off_time_on_a_day.value


    def test_remove_day_event(self):
        event = DayEvent()
        event.employee_id = self.employee_id
        event.event_type = DayEventType.holidays
        self.server.set_event_on_days(event, [ (date(2012,12,15), 7.5) ] )

        r = self.server.events_for_month(date(2012,12,1))

        self.server.remove_events( [de.day_event_id for de in r])

        r = self.server.events_for_month(date(2012,12,1))
        assert len(r) == 0


if __name__ == "__main__":
    unittest.main()
