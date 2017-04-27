from datetime import date
from sqlalchemy import and_
from sqlalchemy.sql.expression import func

from koi.Configurator import mainlog
from koi.server.json_decorator import JsonCallable, ServerErrors, ServerException

from koi.date_utils import month_period_as_date
from koi.translators import date_to_dmy
from koi.datalayer.database_session import session
from koi.datalayer.RollbackDecorator import RollbackDecorator
from koi.datalayer.audit_trail_mapping import AuditTrail
from koi.people_admin.people_admin_mapping import DayEvent, DayEventType



class DayEventService(object):

    @JsonCallable([date])
    def events_for_month(self, base_date : date):
        begin, end = month_period_as_date(base_date)

        db_events = session().query(DayEvent.day_event_id,
                                    DayEvent.employee_id,
                                    DayEvent.event_type,
                                    DayEvent.date,
                                    DayEvent.duration).filter( DayEvent.date.between(begin, end)).all()
        session().commit()

        return db_events


    @JsonCallable([int])
    def events_for_year(self, year : int):

        begin_date = date(year,1,1)
        end_date = date(year,12,31)

        db_events = session().query(DayEvent.employee_id,
                                    DayEvent.event_type,
                                    func.sum(DayEvent.duration)).\
            filter(DayEvent.date.between(begin_date, end_date)).\
            group_by(DayEvent.employee_id,
                     DayEvent.event_type).all()

        emp = dict()

        for employee_id, event_type, total_duration in db_events:
            if employee_id not in emp:
                emp[employee_id] = dict()

            if event_type not in emp[employee_id]:
                emp[employee_id][event_type] = total_duration

        session().commit()

        return emp


    # FIXME In Python 3.6 one can use List[int]
    @JsonCallable([list])
    def remove_events( self, event_ids : list):
        if event_ids:
            session().query(DayEvent).filter( DayEvent.day_event_id.in_(event_ids)).delete(synchronize_session=False)
            session().commit()


    @JsonCallable([DayEvent, list])
    def set_event_on_days( self, day_event : DayEvent, days_duration : list):
        """ Set an event on several days each time with a specific duration.

        :param day_event:
        :param days_duration: An array of pairs. Each pair is (date, duration). Each date
         must be unique.
        :return:
        """

        day_max = date(1980,1,1)
        day_min = date(2050,12,31)

        mainlog.debug("set_event_on_days")
        mainlog.debug(days_duration)

        for day, duration in days_duration:
            day_min = min( day_min, day)
            day_max = max( day_max, day)

        db_events = session().query(DayEvent).filter( and_( DayEvent.employee_id == day_event.employee_id,
                                                            DayEvent.event_type == day_event.event_type,
                                                            DayEvent.date.between(day_min, day_max))).all()

        db_events_dates = dict( zip( [ e.date for e in db_events ], db_events))

        other_db_events = session().query(DayEvent.date,
                                          func.sum(DayEvent.duration).label("duration_sum")).\
            filter( and_( DayEvent.employee_id == day_event.employee_id,
                          DayEvent.event_type != day_event.event_type,
                          DayEvent.date.between(day_min, day_max))).\
            group_by(DayEvent.date).all()

        other_db_events_dates = dict( [ (e.date,e.duration_sum) for e in other_db_events ])

        for day, duration in days_duration:
            if day in other_db_events_dates and other_db_events_dates[day] + duration > 1:
                raise ServerException( ServerErrors.too_much_off_time_on_a_day, date_to_dmy(day))

            if day in db_events_dates:
                # Replace the old duration
                db_event = db_events_dates[day]
                db_event.duration = duration
            else:
                nu_event = DayEvent()
                nu_event.date = day
                nu_event.duration = duration
                nu_event.event_type = day_event.event_type
                nu_event.employee_id = day_event.employee_id
                session().add(nu_event)

        session().commit()



people_admin_service = DayEventService()
