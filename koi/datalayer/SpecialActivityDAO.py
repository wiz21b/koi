from datetime import timedelta
from sqlalchemy.sql import and_
from koi.Configurator import mainlog
from koi.datalayer.database_session import session
from koi.db_mapping import SpecialActivity
from koi.datalayer.RollbackDecorator import RollbackDecorator
from koi.datalayer.tools import last_moment_of_month,first_moment_of_month,day_span
from koi.datalayer.generic_access import all_non_relation_columns

class SpecialActivityDAO(object):

    def __init__(self):
        pass

    @RollbackDecorator
    def save(self,sa):
        mainlog.debug("SpecialActivityDAO.save()")
        if not sa.special_activity_id:
            session().add(sa)
        elif sa not in session():
            session().merge(sa)
        session().commit()

    @RollbackDecorator
    def delete(self,sa,commit=True):
        session().delete(sa)

        if commit:
            session().commit()

    @RollbackDecorator
    def find_by_id(self,sa_id):
        r = session().query(SpecialActivities).filter(SpecialActivities.special_activity_is == sa_id).one()
        session().commit()
        return r

    @RollbackDecorator
    def find_by_employee(self, employee, month_date):
        start_month = first_moment_of_month(month_date)
        end_month = last_moment_of_month(month_date)

        r = session().query(SpecialActivity).\
            filter(and_( SpecialActivity.employee == employee,
                         SpecialActivity.end_time >= start_month,
                         SpecialActivity.start_time <= end_month)).all()
        session().commit()
        return r


    @RollbackDecorator
    def delete_by_employee_and_date(self, employee_id, day):
        """ Delete all the s.a. intersecting the period
        of the given day.
        """

        day_start,day_end = day_span(day)

        r = session().query(SpecialActivity).\
            filter(and_( SpecialActivity.employee_id == employee_id,
                         SpecialActivity.end_time >= day_start,
                         SpecialActivity.start_time <= day_end)).delete()
        session().commit()

        return r > 0


    @RollbackDecorator
    def find_on_day(self, employee_id, ref_date):
        """ Find special activities which periods covers
        the given day, at least partially.
        """

        columns = all_non_relation_columns(SpecialActivity)

        day_start,day_end = day_span(ref_date)

        r = session().query(*columns).\
            filter(and_( SpecialActivity.employee_id == employee_id,
                         SpecialActivity.end_time >= day_start,
                         SpecialActivity.start_time <= day_end)).all()
        session().commit()

        return r


    @RollbackDecorator
    def find_on_month(self, month_date):
        start_month = first_moment_of_month(month_date)
        end_month = last_moment_of_month(month_date)

        # mainlog.debug("{}-{}".format(start_month,end_month))
        res = session().query(SpecialActivity).\
            filter(and_( SpecialActivity.end_time >= start_month,
                         SpecialActivity.start_time <= end_month)).all()

        m = dict()
        for sa in res:
            if sa.employee.employee_id not in m:
                m[sa.employee.employee_id] = []

            mainlog.debug(" - {}".format(sa))
            m[sa.employee.employee_id].append(sa)

        mainlog.debug("activities={}".format(len(m)))
        session().commit()
        return m
