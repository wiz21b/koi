import calendar
import calendar
from datetime import date,datetime,timedelta

import sqlalchemy
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql.expression import func

from koi.base_logging import mainlog
from koi.date_utils import day_period

from koi.datalayer.RollbackDecorator import RollbackDecorator
from koi.datalayer.database_session import session
from koi.db_mapping import DayTimeSynthesis,TimeTrack
from koi.db_mapping import Employee, TaskActionReport

#from koi.server.json_decorator import ServerErrors, ServerException
#from koi.dao import dao
from koi.junkyard.dto_maker import JsonCallable, Sequence, KeyedTuplesSequence


# print(JsonCallable.__module__)

class EmployeeService:

    @JsonCallable()
    @RollbackDecorator
    def authenticate(self, identifier : str, password : str) -> Employee:
        q = session().query(Employee).filter(and_(Employee.login == identifier,
                                                  Employee.password == password,
                                                  Employee.is_active == True)).first()

        session().commit()
        # mainlog.debug(u"Authenticate : password {}".format(password))
        if q:
            return q
        else:
            return None


    @JsonCallable()
    @RollbackDecorator
    def save(self, employee : Employee) -> Employee:
        session().commit() # It may be an INSERT, so I need to commit to get the PK's back
        return employee


    @JsonCallable()
    @RollbackDecorator
    def find_by_id(self,employee_id : int) -> Employee:
        try:
            return session().query(Employee).filter(Employee.employee_id == employee_id).one()
        except NoResultFound as ex:
            mainlog.error("EmployeeDAO.find_by_id: Failed to find with id {} of type {}".format(identifier,type(identifier)))
            raise ServerException(ServerErrors.unknown_employee_id, employee_id)


    #@JsonCallable() # Used in test only => remote call not necessary
    @RollbackDecorator
    def any(self):
        # FIXME replace by cache access
        return session().query(Employee).order_by(Employee.fullname).first()


    @RollbackDecorator
    def _reload_cache(self):
        self._cache = dict()
        for e in session().query(Employee).all():
            self._cache[e.employee_id] = e

    @RollbackDecorator
    def find_by_id_frozen2(self, employee_id):

        c = all_non_relation_columns(Employee)
        r = session().query( *c).filter(Employee.employee_id == employee_id).all()
        session().commit()

        if len(r) == 1:
            return r[0]
        elif len(r) == 0:
            raise ServerException(ServerErrors.unknown_employee_id, employee_id)
        else:
            raise ServerException("Constraint violation")

        return r

    @RollbackDecorator
    def find_by_id_frozen(self,identifier):
        # FIXME replace by cache access
        try:
            mainlog.debug("find_by_id_frozen-1")
            emp = session().query(Employee).filter(Employee.employee_id == identifier).one()
            mainlog.debug("find_by_id_frozen-3")
            f = freeze(session(), emp)
            mainlog.debug("find_by_id_frozen-2")
            session().commit()
            return f
        except NoResultFound as ex:
            mainlog.error("EmployeeDAO.find_by_id: Failed to find with id {} of type {}".format(identifier,type(identifier)))
            raise ex

    @RollbackDecorator
    def id_exists(self,identifier):
        c = session().query(Employee).filter(Employee.employee_id == identifier).count()
        session().commit()
        return c > 0



    @RollbackDecorator
    def find_by_ids(self,identifiers):
        # return session().query(Employee).filter(in_Employee.employee_id.in_(identifiers)).one()
        if identifiers == None:
            raise "I can't find None"
        else:
            return list(map( lambda a:self._cache[a], identifiers))


    @RollbackDecorator
    def all(self):
        res = session().query(Employee).order_by(Employee.fullname).all()
        session().commit()
        return res


    @RollbackDecorator
    def all_active(self):
        res = session().query(Employee).filter(Employee.is_active == True).order_by(Employee.fullname).all()
        session().commit()
        return res




    def delete(self,employee_id):
        employee = self.find_by_id(employee_id)
        try:
            session().delete(employee)
            session().commit()
            self._reload_cache()
        except IntegrityError:
            session().rollback()
            raise ServerException( ServerErrors.cannot_delete_employee_because_orders)
        except Exception as e:
            mainlog.exception(e)
            session().rollback()
            raise e

    # @RollbackDecorator
    # def save(self,employee):
    #     session().add(employee)
    #     session().commit()
    #     self._reload_cache()

    def make(self,name):
        # FIXME Double with create method
        employee = Employee()
        employee.fullname = name
        return employee

    @RollbackDecorator
    def create(self,fullname):
        employee = Employee()
        employee.fullname = fullname
        session().add(employee)
        session().commit()
        self._reload_cache()
        return employee


    @RollbackDecorator
    def list_overview(self):
        res = session().query(Employee.fullname,
                              Employee.employee_id,
                              Employee.is_active).order_by(Employee.fullname).all()
        session().commit()
        return res

    @RollbackDecorator
    def presence_overview_for_month(self,base_date):
        """ Presence overview for employees during a month
        """

        day_max = calendar.monthrange(base_date.year,base_date.month)[1]

        t_start = datetime( base_date.year,  base_date.month, 1)
        t_end = datetime( base_date.year,  base_date.month, day_max, 23, 59, 59, 9999 )
        # So this won't select employees without timetracking

        presences = session().query(DayTimeSynthesis.employee_id,
                                    DayTimeSynthesis.presence_time,
                                    DayTimeSynthesis.day).\
                    filter( DayTimeSynthesis.day.between(t_start.date(),t_end.date())).all()

        # Make a 'map' of presence time

        r = dict()

        for p in presences:
            if p.employee_id not in r:
                r[p.employee_id] = [0] * day_max
            r[p.employee_id][p.day.day - 1] += p.presence_time

        session().commit()

        return r



    @RollbackDecorator
    def find_person_presence_for_period(self, employee_id, start_date, end_date):
        """ A list of tuples. Each tuple represents the total presence of a person
        on a given day (day as a day, presence_time in hours).
        """

        begin = datetime(start_date.year,start_date.month,start_date.day,0,0,0)
        end =   datetime(end_date.year,  end_date.month,  end_date.day,23,59,59,999999)

        presences = session().query(DayTimeSynthesis.day,
                                    DayTimeSynthesis.presence_time).\
                    filter( and_( DayTimeSynthesis.employee_id == employee_id,
                                  DayTimeSynthesis.day.between(begin.date(),end.date()))).\
                    order_by(DayTimeSynthesis.day).all()

        days = dict()

        d = start_date
        while d <= end_date:
            days[d] = None
            d += timedelta(days=1)

        for p in presences:
            days[p.day] = p

        r = []


        for day in sorted( days.keys()):
            if days[day]:
                r.append(days[day])
            else:
                r.append(KeyedTuple( [day,0], labels=['day','presence_time'] ))

        session().commit()

        return r


    @JsonCallable()
    @RollbackDecorator
    def find_activity(self, employee_id : int, start_date : date, end_date : date) -> KeyedTuplesSequence([date, float],['day','duration']):
        """ Actiivity (work done, not presence) between two dates, as a list of tuples.
        Each tuple represents a day.
        * tuple.day = the day
        * tuple.first_time : the time of the first time record
        * tuple.duration : the duration of the activity
        """

        mainlog.debug("find_activity from {} to {}".format(start_date, end_date))

        begin = datetime(start_date.year,start_date.month,start_date.day,0,0,0)
        end =   datetime(end_date.year,  end_date.month,  end_date.day,23,59,59,999999)

        presence_task = dao.task_action_report_dao.presence_task()

        t = session().query(func.DATE(TimeTrack.start_time).label('day'),
                            func.min(TimeTrack.start_time).label('first_time'),
                            func.sum(TimeTrack.duration).label('duration')).\
            filter(
                and_ ( TimeTrack.task_id != presence_task.task_id,
                       TimeTrack.employee_id == employee_id,
                       TimeTrack.start_time.between(begin,end))).\
            group_by('day').order_by("day").subquery()


        vdays = session().query( (date(begin.year,begin.month,begin.day)
                                  + func.generate_series(0, (end - begin).days)).label("day")).subquery()

        t = session().query(vdays.c.day, t.c.duration).select_from(vdays).outerjoin(t, vdays.c.day == t.c.day).order_by(vdays.c.day).all()

        session().commit()

        return t



    @RollbackDecorator
    def presence(self,employee_id,date_ref = None):
        """ Find a person's presence on a given day
        """

        today = date_ref
        if not today:
            today = date.today() # because param default are evaluated at copile time !

        begin, end = day_period(today)

        times = session().query(TaskActionReport).\
                filter(and_(TaskActionReport.status != TaskActionReport.DELETED_STATUS,
                            TaskActionReport.reporter_id == employee_id,
                            TaskActionReport.time.between(begin,end))).order_by(TaskActionReport.time).all()

        if len(times) == 0:
            return None, None, None
        elif len(times) == 1:
            # returned total_hours is None becaue when there are
            # only on time, a duration doesn't make sense (and thus
            # it's not zero)
            return times[0].time, None, None
        else:

            first = times[0].time
            last = times[-1].time

            total_hours = (last - first).seconds / 3600.0

            return first, last, total_hours


    """ All the employees who have worked (got timetmetracks) or will work on a given task.
    """

    def working_on_task(self,task):
        return self.any()

    @RollbackDecorator
    def find_by_login(self,login : str) -> Employee:
        return session().query(Employee).filter(Employee.login == login).first()

