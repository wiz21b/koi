""" The DAO object is the mandatory crossroad of all database accesses.

The DAO object is exported through the dao variable. Please use
this as the only entry point to the stuff here.

Please keep this database only. So only allowed dependecies are
SQLAlchemy and basic python stuff. So, no Qt down here please.
"""

"""
import logging logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)
logging.getLogger('sqlalchemy.orm').setLevel(logging.DEBUG)
"""

import calendar
import os
from datetime import date,datetime,timedelta

from sqlalchemy import and_,or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import join
from sqlalchemy.orm import joinedload,lazyload,noload
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql.expression import FromClause
from sqlalchemy.sql.expression import desc,asc,func, literal,label
from sqlalchemy.util._collections import KeyedTuple

from koi.Interval import IntervalCollection,Interval
from koi.configuration.business_functions import is_task_imputable_for_admin, business_computations_service
from koi.datalayer.RollbackDecorator import RollbackDecorator
from koi.datalayer.SpecialActivityDAO import SpecialActivityDAO
from koi.datalayer.audit_trail_service import audit_trail_service
from koi.datalayer.customer_dao import CustomerDAO
from koi.datalayer.database_session import session
from koi.datalayer.delivery_slip_query_parser import parse_delivery_slip_parts_query
from koi.datalayer.filters_dao import FilterQueryDAO
from koi.datalayer.generic_access import all_non_relation_columns # FIXME not here...
from koi.datalayer.operation_definition_dao import OperationDefinitionDAO
from koi.datalayer.order_dao import OrderDAO
from koi.datalayer.order_part_dao import OrderPartDAO
from koi.datalayer.tools import day_span
from koi.date_utils import _last_moment_of_month,_first_moment_of_month, day_period, ts_to_date
from koi.db_mapping import DayTimeSynthesis,MonthTimeSynthesis
from koi.db_mapping import DeliverySlip,DeliverySlipPart,TaskOnOrder
from koi.db_mapping import Employee,Customer, TaskActionReport
from koi.db_mapping import Operation,ProductionFile,TimeTrack,Task,OperationDefinition,Order,OrderPart,TaskOnOperation,TaskOnNonBillable
from koi.db_mapping import OrderStatusType,OrderPartStateType
from koi.db_mapping import TaskActionReportType
from koi.db_mapping import TaskForPresence,TaskForPresenceType
from koi.db_mapping import freeze,freeze2
from koi.machine.machine_service import machine_service
from koi.quality.quality_dao import QualityDao
from koi.server.json_decorator import ServerErrors,ServerException
from koi.tools.chrono import *
from koi.translators import text_search_normalize


class values(FromClause):
    named_with_column = True

    def __init__(self, columns, *args, **kw):

        self._column_args = columns
        self.list = args
        self.alias_name = self.name = kw.pop('alias_name', None)

    def _populate_column_collection(self):
        for c in self._column_args:
            c._make_proxy(self)


@compiles(values)
def compile_values(element, compiler, asfrom=False, **kw):
    columns = element.columns
    v = "VALUES %s" % ", ".join(
        "(%s)" % ", ".join(
                compiler.render_literal_value(elem, column.type)
                for elem, column in zip(tup, columns))
        for tup in element.list
    )
    if asfrom:
        if element.alias_name:
            v = "(%s) AS %s (%s)" % (v, element.alias_name, (", ".join(c.name for c in element.columns)))
        else:
            v = "(%s)" % v
    return v


def printquery(statement, bind=None):
    """
    print a query, with values filled in
    for debugging purposes *only*
    for security, you should always separate queries from their values
    please also note that this function is quite slow
    """
    import sqlalchemy.orm
    if isinstance(statement, sqlalchemy.orm.Query):
        if bind is None:
            bind = statement.session.get_bind(
                    statement._mapper_zero_or_none()
            )
        statement = statement.statement
    elif bind is None:
        bind = statement.bind

    dialect = bind.dialect
    compiler = statement._compiler(dialect)
    class LiteralCompiler(compiler.__class__):
        def visit_bindparam(
                self, bindparam, within_columns_clause=False,
                literal_binds=False, **kwargs
        ):

            # Sometimes this crash with
            # https://bitbucket.org/zzzeek/alembic/issue/57/support-rendering-of-dates-datetimes-for
            # and i can't figure how to fix it

            return super(LiteralCompiler, self).render_literal_bindparam(
                    bindparam, within_columns_clause=within_columns_clause,
                    literal_binds=literal_binds, **kwargs
            )

    compiler = LiteralCompiler(dialect, statement)
    # print( compiler.process(statement))

# def decallmethods(decorator, prefix='test_'):
#     def dectheclass(cls):
#       for name, m in inspect.getmembers(cls, inspect.ismethod):
#         if name.startswith(prefix):
#           setattr(cls, name, decorator(m))
#       return cls
#     return dectheclass







from koi.datalayer.data_exception import DataException



MAX_BACK_IN_TIME_FOR_TARS = timedelta(hours=48)

# Maximum time
MAXIMUM_HUMAN_WORK_PERIOD = timedelta(hours=12)


class ProductionFileDAO(object):
    """ Productionfile DAO
    """
    def __init__(self,session,order_part_dao):
        """ Init
        """
        self._table_model = None
        self._model_operations = None
        self.order_part_dao = order_part_dao

    def make(self):
        pf = ProductionFile()
        return pf

    @RollbackDecorator
    def save(self,pf):
        if pf not in session():
            session().add(pf)
        session().commit()

    def clone(self,identifier):
        """ Clone
        """
        old = self.find_by_identifier(identifier)
        new = ProductionFile()
        new.description = old.description
        new.date = old.date
        new.order_part = old.order_part
        return new

    def find_by_identifier(self,identifier):
        return session().query(ProductionFile).filter(ProductionFile.identifier == identifier).one()

    # def find_by_order_part(self,order_part):
    #     #print order_part.__class__

    #     if isinstance(order_part, OrderPart):
    #         return session().query(ProductionFile).filter(ProductionFile.order_part == order_part).one()
    #     elif isinstance(order_part, basestring):
    #         return self.find_by_order_part(self.order_part_dao.find_by_full_id(order_part))
    #     elif order_part is None:
    #         return None
    #     else:
    #         raise TypeError('Unsupported type ')





class TimeTrackDAO(object):
    def __init__(self,session):
        pass

    def create(self,task,employee,duration,start_time,encoding_date):
        t = TimeTrack()
        t.task = task
        t.employee = employee
        t.duration = duration
        t.start_time = start_time
        t.encoding_date = encoding_date
        session().add(t)
        return t


    @RollbackDecorator
    def all_work_for_employee_date_manual(self,employee_id,date):

        begin,end = day_span(date)

        mainlog.debug(u"all_work_for_employee_date_manual {} from {} to {}".format(employee_id,begin,end))

        q = session().query(TimeTrack).join(Task).filter(
            and_( Task.task_type != TaskForPresence.__mapper_args__['polymorphic_identity'],
                  TimeTrack.employee_id == employee_id,
                  TimeTrack.managed_by_code != True, # None or False (FIXME should never be None ?)
                  TimeTrack.start_time.between(begin,end))).order_by(TimeTrack.start_time)

        return q.all()




    @RollbackDecorator
    def all_work_for_employee_date(self,employee_id,date):
        """ Returns all the timetracks of real work performed by an employee
        on day date or an empty list.

        The timetracks are ordered based on the fact they are managed by
        Horse or manually entered and based on start time. The presentation
        layer relies on that order.

        That is, the timetracks for absence,unemployment,... are not taken
        into account here.
        """

        begin, end = day_period(date)
        # Two ways to achieve the same thing

        # printquery(session().query(TimeTrack).join(TimeTrack.task.of_type(TaskOnOrder))) => but this eager loads a lot of information
        # printquery(session().query(TimeTrack).join(Task).filter(Task.task_type == TaskOnOrder.__mapper_args__['polymorphic_identity']))
        return session().query(TimeTrack).join(Task).filter(
            and_( Task.task_type != TaskForPresence.__mapper_args__['polymorphic_identity'],
                  TimeTrack.employee_id == employee_id,
                  TimeTrack.start_time.between(begin,end))).order_by(TimeTrack.managed_by_code,TimeTrack.start_time).all()


    @RollbackDecorator
    def load_order_overview_total_unbillable(self,month_date):

        ts_begin = _first_moment_of_month(month_date)
        ts_end = _last_moment_of_month(month_date)

        return session().query(func.sum(TimeTrack.duration)).join(Task).filter(
            and_( Task.task_type == TaskOnNonBillable.__mapper_args__['polymorphic_identity'],
                  TimeTrack.start_time.between(ts_begin,ts_end))).scalar() or 0

    @RollbackDecorator
    def load_unbillable_for_month(self,date_begin,date_end):
        return session().query(OperationDefinition.description, func.sum(TimeTrack.duration)).join(TaskOnNonBillable).join(TimeTrack).filter(TimeTrack.start_time.between(date.today(),date.today())).group_by(OperationDefinition).all()

    @RollbackDecorator
    def all_presence_for_employee_date(self,employee,date):
        begin, end = day_period(date)

        return session().query(TimeTrack).join(Task).filter(
            and_( Task.task_type == TaskForPresence.__mapper_args__['polymorphic_identity'],
                  TimeTrack.employee == employee,
                  TimeTrack.start_time.between(begin,end))).order_by(TimeTrack.managed_by_code,TimeTrack.start_time).all()

    @RollbackDecorator
    def all_presence_for_employee_date_managed_by_code_full(self,employee_id,date):
        begin, end = day_period(date)

        return session().query(TimeTrack).join(Task).filter(
            and_( Task.task_type == TaskForPresence.__mapper_args__['polymorphic_identity'],
                  TimeTrack.employee_id == employee_id,
                  TimeTrack.managed_by_code == True,
                  TimeTrack.start_time.between(begin,end))).order_by(TimeTrack.start_time).all()

    @RollbackDecorator
    def all_manual_presence_timetracks(self,employee,date):
        # This returns presence AND unemployment tasks

        begin, end = day_period(date)

        return session().query(TimeTrack).join(Task).filter(
            and_( Task.task_type == TaskForPresence.__mapper_args__['polymorphic_identity'],
                  TimeTrack.employee == employee,
                  TimeTrack.managed_by_code != True,
                  TimeTrack.start_time.between(begin,end))).order_by(TimeTrack.start_time).all()

    @RollbackDecorator
    def all_presence_for_employee_date_managed_by_code(self,employee,date):
        # This ONLY returns the presence task (not the unemployment task)
        # FIXME II have the impression that is not correct

        begin, end = day_period(date)

        presence = dao.task_action_report_dao.presence_task()

        return session().query(TimeTrack.timetrack_id).filter(
            and_( TimeTrack.task_id == presence.task_id,
                  TimeTrack.employee == employee,
                  TimeTrack.managed_by_code == True,
                  TimeTrack.start_time.between(begin,end))).order_by(TimeTrack.start_time).all()


    @RollbackDecorator
    def all_for_employee_date(self,employee,date):
        """ Returns all the timetracks of real work performed by an employee
        on day date or an empty list.

        The timetracks are ordered based on the fact they are managed by
        Horse or manually entered and based on start time. The presentation
        layer relies on that order.

        """

        begin, end = day_period(date)

        return session().query(TimeTrack).join(Task).filter(
            and_( TimeTrack.employee == employee,
                  TimeTrack.start_time.between(begin,end))).order_by(TimeTrack.managed_by_code,TimeTrack.start_time).all()



    @RollbackDecorator
    def delete(self,timetrack):
        session().delete(timetrack)
        session().commit()



    @RollbackDecorator
    def multi_update(self,employee,day,to_delete,to_create,to_update):
        """ Save several timetracks which are *not* tied to task action
        reports """

        if type(day) != date:
            raise Exception("Expecting a date, got a {}".format(day))

        mainlog.debug("TimetrackDAO.multi_update")

        # for o in to_update + to_create:

        # Pay attention, there's a lot going on right here.
        # Beside the attribute merge, don't forget that a timetrack
        # is also tied to an employee, a task and some TaskActionReports
        # through a back ref. The standard operation though is that
        # the employee should already be in the database. The TAR
        # should not exist (when we create a timetrack from scratch
        # it's precisely because we don't have TAR that generates it)
        # The only remaining thing is the task. However, the task is
        # itself tied to orders, operation, inherited TaskOn... entities
        # etc. Here we rely a lot on SQLA's merge to handle all
        # the cases.

        # session().merge(o)

        employee = session().merge(employee) # FIXME should pass employee_id and make a find here instead

        # Merging the tasks. Pay attention, this is tricky.
        # Normally I should rely on SQLA's merge bring the
        # tasks in the session. Unfortunately, the task
        # primary key doesn't contain the operation_id.
        # Therefore, when I merge, since SLA only considers
        # primary key, SQLA believes all the tasks are
        # different. So if I happen to have 2 tasks connected
        # to the same operation SQLA will not see that they are
        # actually the same. It will therefore try to create
        # two different rows in the TaskOnOperation table
        # with the same operation_id. But since operation_id
        # is unique, this fails. So, I have to detect the tasks
        # that are the same. Then I group them under one
        # task.

        # Also note that I don't pick the id directly but from
        # the relationship. That is, I use task.order.order_id
        # instead of task.order_id. I do that because the
        # task might not be persisted when we use them here.
        # But the task must be "filled" with its relationships.

        d = dict()
        for tt in to_update + to_create:
            if isinstance(tt.task,TaskOnOperation):
                if tt.task.operation_id not in d:
                    d[tt.task.operation_id] = session().merge(tt.task)

                tt.task = d[tt.task.operation_id]


        d = dict()
        for tt in to_update + to_create:
            if isinstance(tt.task,TaskOnNonBillable):
                opdef_id = tt.task.operation_definition.operation_definition_id
                if not opdef_id:
                    raise Exception("Can't work on non persisted task")
                elif opdef_id not in d:
                    d[opdef_id] = session().merge(tt.task)

                tt.task = d[opdef_id]

        d = dict()
        for tt in to_update + to_create:
            if isinstance(tt.task,TaskOnOrder):
                k = str(tt.task.operation_definition.operation_definition_id) + str(tt.task.order.order_id)
                if not tt.task.operation_definition.operation_definition_id or not tt.task.order.order_id:
                    raise Exception("Can't work on non complete task opdef:{} order:{}".format(tt.task.operation_definition.operation_definition_id, tt.task.order.order_id))
                elif k not in d:
                    d[k] = session().merge(tt.task)

                tt.task = d[k]

        # Now we merge the timetracks in SQLA's session

        to_update = list(map(session().merge, to_update))
        to_create = list(map(session().merge, to_create))

        # Apply the deletes

        to_delete = list(filter( lambda e:e is not None, map(lambda tt:tt.timetrack_id, to_delete)))
        if len(to_delete) > 0:
            session().query(TimeTrack).filter(TimeTrack.timetrack_id.in_(to_delete)).delete('fetch')

        session().flush()

        # Shortcut to reload all the timetracks
        timetracks = self.all_work_for_employee_date_manual(employee.employee_id,day)

        if len(timetracks) > 0:
            start = datetime( day.year, day.month, day.day, 6, 0, 0)
            for tt in timetracks:
                tt.start_time = start
                start = start + timedelta(days=0,seconds=int(tt.duration*3600.0))
                mainlog.debug("Retimed the timetrack : {}".format(start))

            # self._recompute_presence_on_timetracks(employee.employee_id,day,timetracks)
            self._compute_and_store_presence(employee_id, date_ref, timetracks = timetracks, commit=False)


        session().commit()




    def _recompute_presence_on_timetracks(self,employee_id,day,timetracks):

        if type(day) != date:
            raise Exception("Expecting a date, got a {}".format(day))


        employee = session().query(Employee).filter(Employee.employee_id == employee_id).one()
        # mainlog.debug(u"_recompute_presence_on_timetracks: for {} ".format(employee))

        timetracks_to_delete = dao.timetrack_dao.all_presence_for_employee_date_managed_by_code(employee,day)

        if len(timetracks_to_delete) > 0:
            timetracks_to_delete = list(map(lambda t:t[0],timetracks_to_delete))
            # mainlog.debug("_recompute_presence_on_timetracks: Clearing existing presence with id's : ")
            # mainlog.debug(timetracks_to_delete)
            session().query(TimeTrack).filter(TimeTrack.timetrack_id.in_(timetracks_to_delete)).delete('fetch')

            # timetracks_to_delete = dao.timetrack_dao.all_presence_for_employee_date_managed_by_code(employee,day)
            # mainlog.debug(len(timetracks_to_delete))


        if len(timetracks) > 0:
            timetracks = sorted(timetracks, key=lambda x:x.start_time)

            # The rule is, the presence is based on the beginning
            # of the first timetrack and the end of the last one.
            # That's rough. But that's enough because the uesr is
            # not allowed to build non consecutive timetracks.
            # (when he actually build timetracks; rememeber he's
            # expected to only build task action reports)

            start = timetracks[0].start_time
            end = timetracks[-1].end_time()
            duration = float((end - start).seconds ) / 3600.0

            tt = TimeTrack()
            tt.managed_by_code = True
            tt.task = dao.task_action_report_dao.presence_task()
            tt.task_id = tt.task.task_id
            tt.employee = employee
            tt.start_time = start
            tt.duration = duration
            tt.encoding_date = date.today()
            session().add(tt)
            mainlog.debug(u"_recompute_presence_on_timetracks: Creating presence {}".format(tt))

            dao.day_time_synthesis_dao.save(employee_id,day,duration,0)
        else:
            dao.day_time_synthesis_dao.save(employee_id,day,0,0)





class IntervalTracker(object):
    """ Helper class for the timetracks reconciliation
    """

    MINIMUM_INTERVAL_SIZE = 1.0/3600.0 # in hours, any interval smaller than this won't exist

    def __init__(self,task_id,employee_id):
        assert task_id >= 0
        assert employee_id >= 0

        self.task_id = task_id
        self.employee_id = employee_id
        # Array of tuple (timetrack, task action report_s_ )
        self.timetracks = []
        self._reset()

    def _reset(self):
        self.in_interval = False
        self.reports = []
        self.interval_start = None
        self.interval_end = None

    def _build_timetrack(self):
        d = (self.interval_end - self.interval_start)
        duration = d.days * 24 + float(d.seconds) / 3600.0 # Hours

        # We don't store intervals less than one second

        if duration >= self.MINIMUM_INTERVAL_SIZE:
            tt = TimeTrack()
            tt.managed_by_code = True
            tt.task_id = self.task_id
            tt.employee_id = self.employee_id
            tt.start_time = self.interval_start
            tt.encoding_date = date.today()
            tt.duration = duration
            mainlog.debug(u"IntervalTracker [{}]: creating timetrack on task: {} :: {}".format(id(self), self.task_id, tt))

            # # Relink each counted report to the timetrack
            # # mainlog.debug(u"reconciliate_timetracks : linking {} reports to that timetrack".format(len(interval[2])))
            # for tar in self.reports:
            #     tar.timetrack = tt

            self.timetracks.append( (tt,self.reports) )
            self.reports = []
        else:
            mainlog.debug("Not creating an *empty* timetrack (duration was {} / d:{})".format(duration, d))
            pass

    def close_interval_on(self,tar):
        # Closing a non existing (or already closed interval) has
        # no effect (this avoids to have to check for open interval
        # before calling this method)

        if self.in_interval:
            mainlog.debug(u"[TRACKER: {} on {}] Close interval on {} {}, started on {}".format(id(self),self.task_id, tar.time,tar.kind,self.interval_start))

            # Add the last information we need to create
            # a timetrack
            self.interval_end = tar.time

            # Now we create a timetrack
            self._build_timetrack()

            # We prepare the tracker for the next interval
            self._reset()
        else:
            mainlog.debug(u"[TRACKER: {} on {}] Skipping close interval on {} {}".format(id(self), self.task_id, tar.time,tar.kind))
            pass


    def open_interval_on(self,tar):
        if self.in_interval:
            # mainlog.debug(u"[TRACKER: {} on {}] Skip open interval on {} {}".format(id(self),self.task, tar.time,tar.kind))
            # If an interval is started again before being closed
            # then the second opening is ignored
            pass
        else:
            # mainlog.debug(u"[TRACKER: {} on {}] Open interval on {} {}".format(id(self),self.task,tar.time,tar.kind))
            self.in_interval = True
            self.interval_start = tar.time


    def handle_report(self,tar):
        """ this function must be called in the chronological order of the
        TARS.
        """

        # Either there's not known TAR so far, or the new
        # TAR is after the last from the reports array

        assert (not self.reports) or (tar.time > self.reports[0].time)

        if tar.kind not in (TaskActionReportType.start_task,TaskActionReportType.stop_task):
            raise Exception("This works only for regular tasks")

        # Make sure the task action reports will be linked
        # to their timetrack (the reports array will
        # be used later in the execution flow).

        # Interpret the begin/end of periods

        if tar.kind == TaskActionReportType.start_task:
            # We associate the TAR to whatever interval
            # is open => all the start tars are associated
            # to the interval (and hence, if a stop is encountered, to
            # the timetrack) => maximum packing

            self.reports.append(tar)

            self.open_interval_on(tar)

        elif tar.kind == TaskActionReportType.stop_task:
            # We pack a maximum of start/stop TARs toegether.
            # So if we have :
            #    --Start--Start--Start--Stop--Stop--Stop-->
            # Then all the TARS will be tied to the same timetrack.

            if not self.in_interval and self.timetracks:
                tt, reports = self.timetracks[-1]
                reports.append(tar)
            elif self.in_interval:
                self.reports.append(tar)


            self.close_interval_on(tar)


class AbsenceIntervalTracker(IntervalTracker):
    """ Helper class for the timetracks reconciliation
    """

    def __init__(self,task_id,employee_id):
        super(AbsenceIntervalTracker,self).__init__(task_id,employee_id)

    def open_interval_on(self,tar):
        if not self.in_interval:
            # If an interval is started again before being closed,
            # the reopening is ignored. Only the first open counts.
            self.in_interval = True
            self.interval_start = tar.time


class PresenceIntervalTracker(IntervalTracker):
    """ Helper class for the timetracks reconciliation
    """

    def __init__(self,task_id,employee_id):
        super(PresenceIntervalTracker,self).__init__(task_id,employee_id)
        self.intervals = IntervalCollection()

    def _build_timetrack(self):
        # mainlog.debug("Extending timetrack with start: {}".format(self.interval_start))
        # mainlog.debug("                         end: {}".format(self.interval_end))
        self.intervals.add_and_merge( Interval(self.interval_start,self.interval_end) )
        # mainlog.debug("Extended timetrack to {}".format(self.intervals))

    def make_timetracks(self):
        for i in self.intervals.intervals:
            d = i.length()
            duration = d.days * 24 + float(d.seconds) / 3600.0

            if duration > 0:
                tt = TimeTrack()
                tt.managed_by_code = True
                tt.task_id = self.task_id
                tt.employee_id = self.employee_id
                tt.start_time = i.start
                tt.duration = duration
                tt.encoding_date = date.today()
                # mainlog.debug(u"PresenceIntervalTracker : creating presence timetrack on task: {} :: {}".format(self.task.task_id,tt))

                self.timetracks.append( (tt,None) )

        return self.timetracks

    def merge_timetracks(self,timetracks):
        """ Add the intervals of the given timetracks to the intervals
        tracked here.
        """

        for tt in timetracks:
            days = int(tt.duration / 24.0)
            seconds = (tt.duration - 24*days) * 3600.0
            i = Interval(tt.start_time, tt.start_time + timedelta(days, seconds ))
            self.intervals.add_and_merge(i)

    def open_interval_on(self,tar):
        if not self.in_interval:
            # If an interval is started again before being closed,
            # the reopening is ignored. Only the first open counts.
            self.in_interval = True
            self.interval_start = tar.time



class TaskActionReportDAO(object):

    def __init__(self,session,timetrack_dao,day_time_synthesis_dao):
        self.timetrack_dao = timetrack_dao
        self.day_time_synthesis_dao = day_time_synthesis_dao
        self._cached_presence_task_id_regular_time = None

    def presence_task_id_regular_time(self):
        if not self._cached_presence_task_id_regular_time:
            self._cached_presence_task_id_regular_time = session().query(TaskForPresence.task_id).filter(TaskForPresence.kind == TaskForPresenceType.regular_time).one()[0]
        return self._cached_presence_task_id_regular_time

    def presence_task(self,kind = TaskForPresenceType.regular_time):
        return session().query(TaskForPresence).filter(TaskForPresence.kind == TaskForPresenceType.regular_time).one()

    def unemployment_task(self):
        return session().query(TaskForPresence).filter(TaskForPresence.kind == TaskForPresenceType.unemployment_time).one()

    @RollbackDecorator
    def find_by_task_employee(self,task_id,employee_id):
        # Pay attention, the ordering is absolutely crucial.
        # It is used in the "reconcialite" functions.

         return session().query(TaskActionReport).\
            filter(and_(TaskActionReport.status != TaskActionReport.DELETED_STATUS, TaskActionReport.reporter_id == employee_id, TaskActionReport.task_id == task_id)).\
            order_by(asc(TaskActionReport.time),asc(TaskActionReport.task_action_report_id)).all()

    @RollbackDecorator
    def get_reports_for_task(self, task_id):
        # Gives the last action report for the given task and reporter.
        return session().query(TaskActionReport).filter(TaskActionReport.task_id == task_id).order_by(asc(TaskActionReport.time)).all()

    @RollbackDecorator
    def get_reports_for_employee(self, employee):
        return session().query(TaskActionReport).\
            filter(and_(TaskActionReport.status != TaskActionReport.DELETED_STATUS, \
                        TaskActionReport.reporter == employee)).\
            order_by(asc(TaskActionReport.time)).all()

    @RollbackDecorator
    def get_reports_for_task_employee(self, task_id, employee_id):
        return session().query(TaskActionReport).filter(and_(TaskActionReport.status != TaskActionReport.DELETED_STATUS, TaskActionReport.task_id == task_id,TaskActionReport.reporter_id == employee_id)).order_by(asc(TaskActionReport.time)).all()


    @RollbackDecorator
    def get_reports_for_employee_on_date(self, employee,d):
        return self.get_reports_for_employee_id_on_date( employee.employee_id, d)


    @RollbackDecorator
    def get_reports_for_employee_id_on_date(self, employee_id, d):
        assert employee_id >= 0
        assert d

        begin, end = day_period(d)

        # Pay attention ! The ordering is crucial !!! Because some functions
        # rely on it !

        # entity = with_polymorphic(Task,[TaskOnOperation,TaskOnNonBillable,TaskForPresence,TaskOnOrder])

        chrono_click("get_reports_for_employee_id_on_date-1 ZULU ")

        # The join condition on timetrack's employee_id is necessary because task are not tied
        # to a specific person. So if one joins from task to timetracks,
        # then it'll load all timetracks linked to the task, for *any*
        # employee. So, that can potentially returns a lot of timetracks
        # (for exemple, for the "presence" one, which is shared amongst
        # all employees)

        # The outer join is necessary because a TAR may not have a timetrack
        # associated to it (for example, the "start" ones)

        # FIXME Nonetheless we will have a performance issue when an employee
        # will record many timetracks on a given task (such as the presence
        # task...)

        q = session().query(TaskActionReport).\
            join(Task, TaskActionReport.task_id == Task.task_id).\
            outerjoin(TimeTrack, and_(TimeTrack.task_id == TaskActionReport.task_id, TimeTrack.employee_id == TaskActionReport.reporter_id)).\
            filter(TaskActionReport.reporter_id == employee_id).\
            filter(TaskActionReport.time.between(begin,end)).\
            filter(TaskActionReport.status != TaskActionReport.DELETED_STATUS).\
            options( joinedload('reporter').defer('picture_data')).\
            order_by(asc(TaskActionReport.time))

        # Comment left for historical reasons The noload is here to force the timetracks out of the query
        # if I don't to that, tiemtracks get loaded and worst, they
        # are loaded for the task => all timetracks of every employee
        # on the task, for nothing. This results in a good performance
        # improvement. Now, I wonder why SQLA loads those that
        # because in the mapping, I explicitely state "lazyload" for
        # Task.timetracks...
        # options( noload('task'), noload('timetrack')).\

        # options( joinedload('reporter')). \
        # , \
        # subqueryload('task').lazyload('timetracks')).\

        res = q.all()

        mainlog.debug("get_reports_for_employee_id_on_date : returning {} results".format(len(res)))

        chrono_click("get_reports_for_employee_id_on_date-2")

        return res



    @RollbackDecorator
    def _find_reports_to_reconciliate(self, new_tar):
        """

        FIXME the pause are not taken into account

        The new_tar is expected to be already in the database (or at least
        in the session). The new tar is expected to be fully populated.

        Find reports that needs to be evaluated to rebuild tyhe timetracks
        timeline for a given teask.

        Several principles :
        1/ there are no two timetracks for a given task that overlap.
        2/ there are never two TAR's on the same time (for a person/task).
        3/ We work incrementally : once a TAR has been added, all the TT
           are correct.

        We need to be very accurate in the TAR selection because the reconciliation
        process, might build wrong timetracks if it is not properly fed.

        Consider this degenerated case :

            1                                 2
        ----|---[____]---[______]----[____]---|----
            |Start                            | Stop

        We could say that we need to look at TAR 1 and TAR 2
        (and everythig between) because they are not attached to a timetrack.
        But that's not realistic. First, if TAR 1 is where it is, then, each time
        one calls this function, the one has to recheck the whole TAR history
        (and for presence task, this might amount to thousands of TARs).
        Second, considering that there are already a timetrack that
        follow TAR1, then it is useless to recompute so much in the past.

        Before going further we need to choose if timetrack creation
        is greedy or not :

         ----|---[____]----|--- Eager

         ----[___|____|____]--- Greedy

        But in fact, the IntervalTracker is like this

         ---[____|____]----|--- First of starts, first of stops

        So, when one add a start TAR on the timeline, one has to figure :

        1/ If that TAR is the first of a series of start TAR (base case :
           it is always the start of the serie made of itself). If it's not
           then adding that tar won't change anything.
           To know if it is the first, it's enough to look at the previous
           TAR. If the previous TAR is a start TAR, then the TAR is not the
           first of the serie, else it is.
        2/ If that TAR is followed by a stop tar (with some start tar in between if any).
           If so then a timetrack might be built. If not, then it is either followed
           by nothing or followed by another start TAR. In any case, we know there won't
           be any timetrack to build.

        Conversely, if we add a stop TAR, then on has to figure:

        1/ If it is the first of a serie of stop TARs. If so, then we might finish
           a timetrack (or shorten an exisiting one). If not, adding that TAR won't
           change anything to the timetracks.
        2/ If that TAR is preceded by a start TAR (with some stops between, if any).

        At this point, we have yet not taken the day_in day_out TARs into account.

        """

        # Make sure the TAR is fully populated
        assert new_tar.reporter_id
        assert new_tar.task_id
        assert new_tar.kind
        assert new_tar.time

        employee_id = new_tar.reporter_id
        task_id = new_tar.task_id
        presence_task_id = self.presence_task().task_id

        # The queries below can degenerate, for example, if we have 1 million
        # of start TARs. So we bound the time to avoid bringing back all of them.
        # This might also help the database query engine.

        timelimit_begin = new_tar.time - MAX_BACK_IN_TIME_FOR_TARS
        timelimit_end = new_tar.time + MAX_BACK_IN_TIME_FOR_TARS

        if new_tar.kind == TaskActionReportType.start_task:

            # We look the immediate previous TAR
            prev_tar = session().query(TaskActionReport).\
                       filter( and_( TaskActionReport.task_id.in_( [presence_task_id, task_id] ),
                                     TaskActionReport.reporter_id == employee_id,
                                     TaskActionReport.status != TaskActionReport.DELETED_STATUS,
                                     TaskActionReport.time < new_tar.time, # can't use between operator because I mix "<" and ">="
                                     TaskActionReport.time >= timelimit_begin)).\
                       order_by( desc( TaskActionReport.time)).first() # Have to order desc then use first() because there's no last()

            if prev_tar and prev_tar.kind == TaskActionReportType.start_task:
                # The previous TAR cancels the effect of the new one
                return
            else:
                begin = new_tar.time

            # At this point, we know the new TAR may have an effect, but
            # that'll depend on the following TARs.

            next_tar = session().query(TaskActionReport).\
                       filter( and_( or_( and_( TaskActionReport.task_id == task_id,
                                                TaskActionReport.kind == TaskActionReportType.stop_task),
                                          and_( TaskActionReport.task_id == presence_task_id,
                                                TaskActionReport.kind == TaskActionReportType.day_out)),
                                     TaskActionReport.reporter_id == employee_id,
                                     TaskActionReport.status != TaskActionReport.DELETED_STATUS,
                                     TaskActionReport.time > new_tar.time,
                                     TaskActionReport.time <= timelimit_end)).\
                       order_by( asc( TaskActionReport.time)).first()

            if not next_tar:
                # No stop after the start => no timetrack will be altered
                return
            else:
                # We have at least a stop after the start and the query
                # actually took the first of those
                end = next_tar.time


        elif new_tar.kind in (TaskActionReportType.stop_task, TaskActionReportType.day_out):

            # We go up the previous TAR chain, until we find the end of the
            # chain or a stop TAR.

            # We're interested in TAR which stops a started TAR (that can cut
            # a timetrack). Those are stop_task, of course, but also the day_out
            # ones.

            # I live by the timelimit_begin here... It'd be very hard to build a
            # query that looks for what I need without that limit (basically
            # the for loop below should be put in a SQL query which doesn't look
            # easy at all)

            task_ids = [presence_task_id]
            if task_id:
                task_ids.append(task_id)

            prev_tars = session().query(TaskActionReport).\
                        filter( and_( TaskActionReport.task_id.in_( task_ids),
                                      TaskActionReport.reporter_id == employee_id,
                                      TaskActionReport.status != TaskActionReport.DELETED_STATUS,
                                      TaskActionReport.time < new_tar.time,
                                      TaskActionReport.time >= timelimit_begin)).\
                        order_by( desc( TaskActionReport.time)).all()

            # The following loop takes presence task into account
            first_start_tar = None
            for prev_tar in prev_tars: # prev tars are in reverse chronological order !
                if prev_tar.kind == TaskActionReportType.start_task:
                    first_start_tar = prev_tar
                elif prev_tar.kind in (TaskActionReportType.stop_task, TaskActionReportType.day_out):
                    # a stop task before the new TAR means that the new TAR
                    # is "shadowed" (if there were no start_task in between)
                    # We can abort the loop.
                    break
                else:
                    raise Exception("Unsupported type {}".format(prev_tar.kind))

            if first_start_tar:
                begin = first_start_tar.time
            else:
                return

            end = new_tar.time

        mainlog.debug("_find_reports_to_reconciliate {} {}".format(begin, end))
        tars = session().query(TaskActionReport).\
               filter( and_( TaskActionReport.task_id == task_id,
                             TaskActionReport.reporter_id == employee_id,
                             TaskActionReport.status != TaskActionReport.DELETED_STATUS,
                             TaskActionReport.time.between(begin, end))).all()

        return tars




        # Now we look for the timetracks which overlaps the start/stop period

        # from sqlalchemy.dialects.postgresql import INTERVAL
        from sqlalchemy.types import Interval

        from sqlalchemy.sql.expression import cast

        q = session().query(TaskActionReport).\
            join(Task, TaskActionReport.task_id == Task.task_id).\
            outerjoin(TimeTrack, TimeTrack.timetrack_id == TaskActionReport.timetrack_id).\
            filter(
                and_(
                    TaskActionReport.reporter_id == employee_id,
                    TaskActionReport.status != TaskActionReport.DELETED_STATUS,
                    or_(
                        # Task action reports that may stop work on a task before an actual stop task
                        TaskActionReport.kind.in_([TaskActionReportType.start_pause,
                                                   TaskActionReportType.day_out,
                                                   TaskActionReportType.start_unemployment]),
                        # Task action reports tied to the task, but not tied to a timetrack
                        and_( TaskActionReport.task_id == task_id,
                              TaskActionReport.timetrack_id == None),
                        # Task action reports tied to the task (by way of the outerjoin)
                        # and to a timetrack which period overlaps the [begin,end] period.
                        and_( TaskActionReport.task_id == task_id,
                              TimeTrack.task_id == task_id,
                              TimeTrack.start_time < end,
                              TimeTrack.start_time + TimeTrack.duration * cast('1 hour', Interval) > begin,
                              TimeTrack.managed_by_code == True))))


        # q = session().query(TaskActionReport).\
        #     join(Task, TaskActionReport.task_id == Task.task_id).\
        #     outerjoin(TimeTrack, and_(TimeTrack.task_id == TaskActionReport.task_id, TimeTrack.employee_id == TaskActionReport.reporter_id)).\
        #     filter(TaskActionReport.reporter_id == employee_id).\
        #     filter(TaskActionReport.time.between(begin,end)).\
        #     filter(TaskActionReport.status != TaskActionReport.DELETED_STATUS).\
        #     options( joinedload('reporter').defer('picture_data')).\
        #     order_by(asc(TaskActionReport.time))

        return q.all()



    @RollbackDecorator
    def presence_time(self, employee, day):
        """ Total day presence time based on timetracks.
        WARNING ! You should get the daytime synthesis instead
        """

        tt = self.timetrack_dao.all_presence_for_employee_date(employee,day)
        if len(tt) > 0:
            return sum( [timetrack.duration for timetrack in tt or []])
        else:
            return 0

    # @RollbackDecorator
    # def presence_time(self,employee_id,day):
    #     """ Return the presence time of an employee on a given date.
    #     The time is given in hours, float.
    #     """

    #     begin_day = datetime(day.year,day.month,day.day,0,0,0)
    #     end_day = datetime(day.year,day.month,day.day,23,59,59,999999) # FIXME If the DB gives more than microseconds, then we have a problem

    #     # The odering in the query below is super crucial for the rest
    #     # of this function to work
    #     tars = session().query(TaskActionReport).\
    #         filter(and_(TaskActionReport.reporter_id == employee_id, TaskActionReport.time.between(begin_day, end_day))).\
    #         order_by(asc(TaskActionReport.time)).all()

    #     in_off_period = False
    #     off_periods = []

    #     for tar in tars:
    #         # If the following is True, it means an "off time"
    #         # period starts
    #         start_off_time = tar.kind == TaskActionReportType.pause_in

    #         # If the following is True, it means an "off time"
    #         # period ends.

    #         # So the only way to start an off period is to actually
    #         # begin some meaningful work or start reporting time on
    #         # unemployment
    #         stop_off_time = tar.kind in (TaskActionReportType.start_task, TaskActionReportType.start_unemployment)

    #         if not in_off_period and start_off_time:
    #             in_off_period = True
    #             off_period_start = tar.time

    #         if in_off_period and stop_off_time:
    #             off_periods.append( Interval(off_period_start, tar.time) )
    #             in_off_period = False
    #             off_period_start = None

    #     # In case the loop does not finish in a clean way
    #     if in_off_period:
    #         off_periods.append(Interval(off_period_start,None))

    #     presence_time = timedelta(0)
    #     for interval in off_periods:
    #         if interval.is_finite():
    #             presence_time += interval.length()

    #     if len(tars) > 1:
    #         in_period =  tars[-1].time - tars[0].time
    #         return float((max(presence_time,in_period)).seconds) / 3600.0
    #     else:
    #         return float(presence_time.seconds) / 3600.0


    # def _recompute_time_on_operation_without_machine( self, employee_id):

    #     timetracks = session().query(TimeTrack).filter(and_( TimeTrack.task != self.presence_task(),
    #                                                          TimeTrack.employee_id == employee_id,
    #                                                          TimeTrack.start_time.between(begin,end))).all()

    #     operations_interval_collections = dict()

    #     for tt in timetracks:
    #         if isinstance(tt.task, TaskOnOperation):
    #             if tt.task.operation_id not in operations_interval_collections:
    #                 operations_interval_collections[tt.task.operation_id] = IntervalCollection()
    #             operations_interval_collections[tt.task.operation_id].add_and_merge(Interval(tt.start_time, tt.duration))


    # def _compute_and_store_presence(self, date_ref, employee_id, tars = None, timetracks = None, commit=True):
    #     """ The presence is stored in two places :
    #     * timetracks which represent actual presences period. Note that
    #       those timetracks are *NOT* tied to task action report in the
    #       database
    #     * the day time synthesis, which is a precomputed presence array

    #     Storing the presence overwrites the previous presence data.
    #     """

    #     intervals = self.compute_man_presence_periods(employee_id, date_ref, tars, timetracks, commit=False)
    #     tts = self.convert_intervals_to_presence_timetracks(intervals)

    #     # Rememeber, the presence timetracks are *not* tied to any TAR.
    #     # So deleting them is safe.
    #     session().query(TimeTrack).filter(and_( TimeTrack.task == self.presence_task(),
    #                                             TimeTrack.employee_id == employee_id,
    #                                             TimeTrack.start_time.between(begin,end))).delete()


    #     total_presence = 0
    #     for tt in tts:
    #         total_presence += tt.duration
    #         session.add(tt)

    #     dao.day_time_synthesis_dao.save(employee_id, date_ref, total_presence, 0, commit=commit)

    #     if commit:
    #         session().commit()



    def _recompute_and_store_all_timetracks(self, employee_id, date_ref):
        begin, end = day_period(date_ref)

        timetracks = session().query(TimeTrack).filter(and_( TimeTrack.employee_id == employee_id,
                                                             TimeTrack.start_time.between(begin,end))).all()

        task_action_reports = self.get_reports_for_employee_id_on_date(employee_id, date_ref)

        total_presence, tts_to_create = self._recompute_all_timetracks(employee_id, timetracks, task_action_reports)

        # Now we write our changes

        # Purge existing tt's

        for tar in task_action_reports:
            if tar.timetrack_id:
                tar.timetrack_id = None
                tar.timetrack = None

        session().flush()

        session().query(TimeTrack).\
            filter( TimeTrack.timetrack_id.in_([tt.timetrack_id for tt in timetracks])).delete()

        dao.day_time_synthesis_dao.save(employee_id, date_ref, total_presence, 0, commit=False)

        # Save all the new timetracks

        total_presence = 0
        for tt in tts:
            total_presence += tt.duration
            session.add(tt)



    def _recompute_all_timetracks(self, employee_id, timetracks, task_action_reports):

        assert employee_id
        assert timetracks or task_action_reports

        effective_timetracks = []
        ineffective_timetracks = []

        for tt in timetracks:
            if tt.ineffective:
                ineffective_timetracks.append(tt)
            elif True:
                effective_timetracks.append(tt)


        activity_timetracks = self.compute_activity_timetracks_from_task_action_reports( task_action_reports)

        presence_intervals = self.compute_man_presence_periods(employee_id, date_ref, task_action_reports, effective_timetracks, commit=False)

        presence_timetracks = self.convert_intervals_to_presence_timetracks(presence_intervals)


        # Purge ineffective timetracks
        # (be they presence, activity or whatever tasks)

        def hash_tt(tt):
            return tt.start_time.toordinal() + tt.task_id + tt.duration

        ineffective_hashes = set()
        for tt in ineffective_timetracks:
            ineffective_hashes.add( hash_tt( tt))

        tts_to_create = []
        for tt in presence_timetracks + activity_timetracks:
            if hash_tt(tt) not in ineffective_hashes:
                tts_to_create.append(tt)

        # Compute the whole day presence (after having removed the ineffective TT's !)

        presence_task_id = self.presence_task()
        total_presence = 0
        for tt in tts_to_create:
            if tt.task_id == presence_task_id:
                # A presence task (so not an unemployment one)
                total_presence += tt.duration

        return total_presence, tts_to_create



    def convert_intervals_to_presence_timetracks(self, intervals, employee_id):
        if not intervals.intervals:
            return []

        presence_task_id = dao.task_action_report_dao.presence_task_id_regular_time()

        tts= []
        for interval in intervals.intervals:

            d = (interval.end - interval.start)
            duration = d.days * 24 + float(d.seconds) / 3600.0

            tt = TimeTrack()
            tt.managed_by_code = True
            tt.task_id = presence_task_id
            tt.employee_id = employee_id
            tt.start_time = interval.start
            tt.encoding_date = date.today()
            tt.duration = duration
            tts.append(tt)

        return tts


    @RollbackDecorator
    def compute_man_presence_periods(self, employee_id, date_ref, tars = None, timetracks = None, commit=False):
        """ Returns the presences of an employee based on TARs and timetracks.
        The result is returned as an array of DISJOINT intervals.

        Note that we can mix the presences on TARS and TimeTracks because:
        - we exclude any timetracks which is managed_by_code (in other words
          which was built on top of TARs -- that would double the computation
          of presence on top on TARs). So, to tell it another way, the
          TT's we're looking at are never tied to TARs.
        - we exclude "ineffective" TTs because they'll be applied after
          presence computations (to remember user's decision to disable
          this or that timetrack)

        Warning! It probably makes no sense to call this function outside
        of TAR's reconciliations because hten it'd be difficult to manade
        the creation/destruction of TT's
        """

        # presence_task_id = dao.task_action_report_dao.presence_task().task_id
        if timetracks:
            for tt in timetracks:
                assert not tt.ineffective
                assert not tt.managed_by_code

        begin, end = day_period(date_ref)

        # Compute presence on TARs
        res_tars = self._compute_man_work_time_on_tars(employee_id, date_ref, tars)

        # Compute presence on TT's
        # if timetracks == None:
        #     timetracks = session().query(TimeTrack).filter(and_( TimeTrack.managed_by_code == False,
        #                                                          TimeTrack.ineffective == False,
        #                                                          TimeTrack.employee_id == employee_id,
        #                                                          TimeTrack.start_time.between(begin,end))).all()

        res_timetracks = self._compute_man_work_time_on_timetracks( employee_id, date_ref, timetracks)

        # Now we merge all the presence intervals

        res = IntervalCollection()
        res.add_and_merge(res_tars)
        res.add_and_merge(res_timetracks)

        mainlog.debug("compute_man_presence_periods {}".format(res.intervals))

        if commit:
            session().commit()

        return res


    def _compute_man_work_time_on_timetracks( self, employee_id, date_ref, timetracks):
        # Here we work on two kinds of TT's
        #  - The presence TT's that were given by the user
        #  - The work TT's that were given the user
        # We don't work with TT's that were generated by the code (presence or activity) because we
        # are genertaing them right now. Those which are generated by code
        # come from the TAR computations, and that's taken into accoun in the TAR
        # presence computation.
        # We also don't work with ineffective TT's.

        # When handling the TT's of the user we assume that each of them
        # begins on the RIGHT time. So if somebody puts three intervals
        # of 2 hours beginning at the same time, then the overall presence
        # will be two hours and the user WILL BE RESPONSIBLE for that.
        # Without that hypothesis, things become too heuristic or too
        # complicated.

        # The net result of all of this is that the presence is the union
        # of all the intervals delimited by the given TT's


        if len(timetracks) > 0:
            # There's a fusion interval algorithm beneath
            icol = IntervalCollection([ Interval(tt.start, tt.start + timedelta(hours=tt.duration)) for tt in timetracks])

            return icol.intervals
        else:
            return []


    def _compute_man_work_time_on_tars( self, employee_id, date_ref, tars):
        """ Work time (as opposed to non-presence or pause time)  is returned
        as an array of intervals.
        """

        if len(tars) >= 2:
            # FIXME Basically, day_in and day_out are useless as they are
            # represented by mere clock'in (in particular the "presence" TAR).

            # Think about this : one starts 2 operations and then go for pause
            # [___OP1_____________]
            #     [____OP2______________]
            #           |Lunch|
            # We choose to avoid that because then it means the pause can restart
            # stopped stuff...

            # The way we work guarantees that we don't have to bother with
            # timetracks overlaps.

            class SmallIntervals:
                def __init__(self):
                    self.intervals = []
                    self.interval_start = None

                def count_in(self, time):
                    if not self.interval_start:
                        self.interval_start = time
                    else:
                        self.interval_end = time

                def count_out(self, time):
                    # We dont't handle the scenario where steps :
                    # 1. report regular start task
                    # 2. regular start_pause
                    # 3. regular day_out --> what to do ? forget the pause of enforce the pause ?
                    # We choose to enforce the pause, and forget the day_out

                    if self.interval_start:
                        self.intervals.append( Interval(self.interval_start, time))
                        self.interval_start = None

                def finish(self):
                    if self.interval_start and self.interval_end:
                        self.intervals.append( Interval(self.interval_start, self.interval_stop))

            intervals = SmallIntervals()

            # We build the presence interval. It can be defined like this :
            #  - It ranges from the first TAR to the last TAR, whatever those TAR's are.
            #  - Inside that range, there may be pause, which are delimite by start_pause
            #    or day_out actions.

            # The last TAR always checks in
            intervals.count_in(tars[0].time)

            for tar in tars[1:-1]:
                if tar.kind in (TaskActionReportType.start_pause, TaskActionReportType.day_out):
                    intervals.count_out(tar.time)
                else:
                    intervals.count_in(tar.time)

            # The last TAR always checks out
            intervals.count_out(tars[-1].time)

            mainlog.debug("_compute_man_work_time_on_tars  :returning {}".format(intervals.intervals))

            # Returns an array of intervals
            return intervals.intervals
        else:
            mainlog.debug("Not enough TARs to deduce presence")
            return []



    def _recompute_presence(self, employee_id, date_ref):

        mainlog.debug(u"_recompute_presence")

        begin, end = day_period(date_ref)

        times = session().query(TaskActionReport).\
                filter( and_( TaskActionReport.status != TaskActionReport.DELETED_STATUS,
                              TaskActionReport.reporter_id == employee_id,
                              TaskActionReport.time.between(begin,end))).\
                order_by(TaskActionReport.time).all()

        # First clear any left over
        # Technical note, SQLA says it can't evaluate in Python. So I
        # provide False as an argument to delete.

        nb_del = session().query(TimeTrack).filter(and_( TimeTrack.managed_by_code == True,
                                                         TimeTrack.task == self.presence_task(),
                                                         TimeTrack.employee_id == employee_id,
                                                         TimeTrack.start_time.between(begin,end))).delete(False) # Normally one or zero

        if nb_del not in (0,):
            mainlog.error("Critical situation while recomputing presence for employee_id: {}, date: {}. There were more than one timetrack !".format(employee_id, date_ref))

        if len(times) == 0:
            return
        elif len(times) == 1:
            # when there is only one time, a duration doesn't make sense
            return
        else:

            mainlog.debug(u"_recompute_presence TAR are : {}".format(times))

            first = times[0].time
            last = times[-1].time
            total_hours = (last - first).seconds / 3600.0

            tt = TimeTrack()
            tt.managed_by_code = True
            tt.task = self.presence_task()
            tt.employee_id = employee_id
            tt.start_time = first
            tt.encoding_date = date.today()
            tt.duration = total_hours

            session().add(tt)



    def compute_activity_timetracks_from_task_action_reports(self,reports,employee_id):
        """ Important, don't modify any existing entity here. That's because
        most of the object we manipulate here can be in a SQLA session.
        Since this method is also used in drawing algorithms and other
        things which goal is not to update the database, we have to be careful
        not to change anything """

        if not reports:
            return []

        mainlog.debug("reconciliate_timetracks3 " * 20)
        for tar in reports:
            mainlog.debug(u"TAR > {} / task={}".format(tar, tar.task))

        tt_to_delete = []
        interval_trackers = dict()

        unemployment_task = self.unemployment_task()

        unemployment_tracker = AbsenceIntervalTracker(unemployment_task.task_id,employee_id)
        pause_tracker = AbsenceIntervalTracker(unemployment_task.task_id,employee_id)
        # presence_tracker = PresenceIntervalTracker(self.presence_task(),employee)

        # mainlog.debug(u"Reconciliating timetracks3")

        sorted_reports = sorted(reports,key=lambda x:x.time)
        for tar in sorted_reports:

            # mainlog.debug(u"")
            mainlog.debug(u"Reconciliating TAR : {}".format(tar))

            # Set up our tracker if necessary

            if tar.task_id not in interval_trackers:
                # mainlog.debug(u"Task of the TAR (task_id:{}, task={}) is unknown => making a new tracker".format(tar.task_id,tar.task))
                interval_trackers[tar.task_id] = IntervalTracker(tar.task_id,employee_id)
            tracker = interval_trackers[tar.task_id]

            # mainlog.debug(u"Task is {}, Tracker is {}".format(tar.task, id(tracker)))

            # Interpret the action report as a presence information

            # if tar.kind != TaskActionReportType.day_out:
            #     mainlog.debug(u"presence tracking open {}".format(tar))
            #     presence_tracker.open_interval_on(tar)
            # else:
            #     presence_tracker.close_interval_on(tar)

            # Interpret the action report as a work information

            if tar.kind == TaskActionReportType.start_pause:

                unemployment_tracker.close_interval_on(tar)
                for t in interval_trackers.values():
                    t.close_interval_on(tar)

                pause_tracker.open_interval_on(tar)

            elif tar.kind == TaskActionReportType.day_out:
                mainlog.debug("Day out, will close interval on unemployment")

                unemployment_tracker.close_interval_on(tar)
                mainlog.debug("Day out, will close interval on pause")
                pause_tracker.close_interval_on(tar)

                mainlog.debug("Day out, will close interval on regular intervals")

                for t in interval_trackers.values():
                    t.close_interval_on(tar)

                mainlog.debug("Day out, I'm done")

            elif tar.kind == TaskActionReportType.start_unemployment:

                # count the unemployment time
                unemployment_tracker.open_interval_on(tar)

                # Starting an unemployment phase autoamtically stops
                # all ongoing tasks (that's arbitrary)

                pause_tracker.close_interval_on(tar)
                for t in interval_trackers.values():
                    t.close_interval_on(tar)

            elif tar.kind in (TaskActionReportType.start_task, TaskActionReportType.stop_task):
                if tar.kind == TaskActionReportType.start_task:
                    # Starting a task automatically ends any ongoing
                    # unemployement
                    unemployment_tracker.close_interval_on(tar)
                    pause_tracker.close_interval_on(tar)

                tracker.handle_report(tar)
            else:
                pass
                # mainlog.debug(u"TAR is presence TAR => skipping {}".format(tar))

        # if len(sorted_reports) > 1:
        #     presence_tracker.close_interval_on(sorted_reports[-1])

        # Bring all the timetracks and their associated reports
        # together.

        all_tracks = []
        for tracker in interval_trackers.values():
            all_tracks += tracker.timetracks

        all_tracks += unemployment_tracker.timetracks

        # presence_tracker.merge_timetracks(map(lambda tupl:tupl[0], all_tracks)) # have to reextract info from tuples
        # presence_tracker.make_timetracks() # FIXME Dirty, bad abstraction level

        all_tracks += pause_tracker.timetracks
        # all_tracks += presence_tracker.timetracks

        # mainlog.debug("Done recocnilation")
        return all_tracks

        # Recompute overall presence
        # self._recompute_presence(employee.employee_id, day)


    def _detach_tars_from_timetracks(self,task_action_reports):

        timetracks_to_detach = set()

        for tar in task_action_reports:

            ttid = tar.timetrack_id
            if not ttid and tar.timetrack:
                tid = tar.timetrack.timetrack_id

            if ttid:
                # Detach old time tracks and after that set the new one

                # We don't delete here because there may be other TAR
                # linked to the timetrack as well (and I'm not too sure
                # about the cascading thing of SQLA)

                timetracks_to_detach.add(ttid)
                tar.timetrack = None # poor man's cascade :-)
                tar.timetrack_id = None # poor man's cascade :-)

                # mainlog.debug(u"Detaching timetrack : {} from tar {}".format(ttid,tar.task_action_report_id))

        return timetracks_to_detach


    def _update_presence_on_tars(self, employee, day, tars):

        # Destroy current presence timetracks

        chrono_click("_update_presence_on_tars 1")
        timetracks_to_delete = self.timetrack_dao.all_presence_for_employee_date_managed_by_code(employee,day)

        chrono_click("_update_presence_on_tars 2")
        presence_time, off_time, presence_timetracks = self.recompute_presence_on_tars(employee, tars)

        # Store everything in DB

        chrono_click("_update_presence_on_tars 3 : {}".format(timetracks_to_delete))

        if len(timetracks_to_delete) > 0:
            session().query(TimeTrack).filter(TimeTrack.timetrack_id.in_(timetracks_to_delete)).delete('fetch')

        chrono_click("_update_presence_on_tars 4")

        for pt in presence_timetracks:
            session().add(pt)
            session().flush()
            mainlog.debug(pt)

        chrono_click("_update_presence_on_tars 5")

        self.day_time_synthesis_dao.save(employee.employee_id,day,presence_time,off_time)

        chrono_click("_update_presence_on_tars 6")


    def _recompute_daily_synthesis(self,presence_timetracks):

        if presence_timetracks == None or len(presence_timetracks) == 0:
            return 0,0

        # Recompute the daily "in" time

        presence_time = 0
        for tt in presence_timetracks:
            presence_time += tt.duration

        # Compute the off time (as the holes between "in" periods)

        off_time = 0
        if len(presence_timetracks) >= 2: # you need at least 2 tt to have a hole between them
            for i in range(len(presence_timetracks) - 1):
                tt = presence_timetracks[i]
                tt_next = presence_timetracks[i+1]

                end_tt = tt.start_time + timedelta(seconds=tt.duration*3600.0)
                off_time += float( (tt_next.start_time - end_tt).seconds) / 3600.0

        return presence_time, off_time


    def recompute_presence_on_tars(self, employee, tars):
        """ Recompute the set of presence time tracks based on the
        task action reports.

        The task action reports given *must* be sorted.

        This function doesn't write anything to the database session.
        """

        if tars is None or len(tars) == 0:
            return 0,0,[]

        mainlog.debug(u"recompute_presence_on_tars")

        # Now we recompute the TT's based on the TAR's

        presence_tracker = PresenceIntervalTracker(self.presence_task().task_id,employee.employee_id)

        # This is where the rules for computing what presence
        # times are.

        tars = sorted(tars,key=lambda x:x.time)

        for tar in tars:
            if tar.kind == TaskActionReportType.day_out:
                presence_tracker.close_interval_on(tar)
            elif tar.kind in (TaskActionReportType.start_task,TaskActionReportType.day_in,TaskActionReportType.presence,TaskActionReportType.start_unemployment): # any other action is a "in" record
                presence_tracker.open_interval_on(tar)

        # The last reports always count for the day out (but only
        # if there are more than one report)

        if len(tars) > 1:
            presence_tracker.close_interval_on(tars[-1])


        presence_tracker.make_timetracks() # FIXME Dirty, bad abstraction level
        presence_timetracks = list(map(lambda tupl: tupl[0], presence_tracker.timetracks)) # TT's not TAR's

        presence_time, off_time = self._recompute_daily_synthesis(presence_timetracks)

        mainlog.debug(u"recompute_presence_on_tars. Results are :")
        for tar in tars:
            mainlog.debug(u"{} {}".format( (tar.task is None) or (tar.task.task_id), tar))

        for tt in presence_timetracks:
            mainlog.debug(tt)


        return presence_time, off_time, presence_timetracks


    @RollbackDecorator
    def create(self,task_or_task_id,reporter,action_time,action_kind,location,commit=True):

        # Pay attention, this function doesn't protect one to create
        # TAR's for non imputable task ! However, it does some
        # minimal testing by way of  is_task_imputable_for_admin.

        if not task_or_task_id:
            raise Exception("TaskActionReport requires a task")

        if isinstance(task_or_task_id,Task):
            task_id = task_or_task_id.task_id
        else:
            raise Exception("Bad parameter {}".format(task_or_task_id))

        if not is_task_imputable_for_admin(task_or_task_id):
            raise Exception("Can't record actions on task_id {} because it's not imputable".format(task_or_task_id.task_id))

        t = TaskActionReport()
        t.task = task_or_task_id
        t.task_id = task_id
        t.reporter = reporter
        t.time = action_time
        t.kind = action_kind
        t.origin_location = location

        t.status = TaskActionReport.CREATED_STATUS
        t.processed = False
        t.editor = None
        t.report_time = datetime.now()

        task_action_reports = dao.task_action_report_dao.get_reports_for_employee_on_date(reporter,action_time.date())
        task_action_reports.append(t)
        self.update_tars(reporter, action_time.date(), task_action_reports, [])

        return t



    @RollbackDecorator
    def fast_create_after(self,task_id,reporter_id,action_time,action_kind,location):
        """ This is an optimized, full blown TAR creation.
        It is optimized because it only allows the creation
        of a TAR after all the other TAR's on a given day
        (which is the regular timetracking situation in fact).

        Pay attention ! This will consider the TAR on the same day as action_time day.
        """

        assert task_id is not None
        assert reporter_id is not None
        assert action_time is not None
        assert action_kind is not None

        presence_task_id = dao.task_action_report_dao.presence_task_id_regular_time()

        task_action_reports = dao.task_action_report_dao.get_reports_for_employee_id_on_date(reporter_id,action_time.date())

        # Make sure we are in the conditions to apply our
        # optimizations.

        for tar in task_action_reports:
            if tar.time >= action_time:
                raise Exception("You must record in chronological order")


        # Now let's see how the new TAR affects the current ones

        if action_kind in (TaskActionReportType.day_out, TaskActionReportType.stop_task) :

            last_action_on_task_id = dict()

            # Stopping stuff

            if action_kind == TaskActionReportType.day_out :
                assert task_id == presence_task_id

                for tar in sorted(task_action_reports, key=lambda tar:tar.time, reverse=True):
                    if tar.task_id not in tasks:
                        last_action_on_task_id[tar.task_id] = tar

            elif TaskActionReportType.stop_task :

                assert task_action_reports

                for tar in sorted(task_action_reports, key=lambda tar:tar.time, reverse=True):
                    if tar.task_id == task_id and tar.task_id not in last_action_on_task_id:
                        last_action_on_task_id[task_id] = tar
                        break

            else:
                raise Exception("bad state")

            # if one chooses to stop something then there *must* be something
            # to stop.
            # Here are gathered presence task as well as work task. Therefore
            # there must be something to stop.

            assert last_action_on_task_id
            # mainlog.debug(u"fast_create_after : last actions are : {}".format(last_action_on_task_id))

            # Now we do stop things, and since they were started, it means
            # TimeTracks creation !
            for task_id, tar in last_action_on_task_id.items():
                if tar.kind == TaskActionReportType.start_task:
                    tt = TimeTrack()
                    tt.task_id = task_id
                    tt.employee_id = reporter_id
                    tt.duration = (action_time - tar.time).total_seconds() / 3600
                    tt.start_time = tar.time
                    tt.encoding_date = date.today()
                    session().add(tt)

                    mainlog.debug("fast_create_after : creating a TT : {}".format(tt))

                    # session().flush() # Get the timetrack id
                    # tar.timetrack_id = t.timetrack_id
                    # new_tar.timetrack_id = t.timetrack_id


        new_tar = TaskActionReport()

        new_tar.reporter_id = reporter_id
        new_tar.task_id = task_id
        new_tar.time = action_time
        new_tar.kind = action_kind
        new_tar.origin_location = location

        new_tar.status = TaskActionReport.CREATED_STATUS
        new_tar.processed = False
        new_tar.editor = None
        new_tar.report_time = datetime.now()

        session().add(new_tar)

        try:
            session().flush()
        except IntegrityError as ex:
            session().rollback()

            if not dao.employee_dao.id_exists(reporter_id):
                raise ServerException(ServerErrors.unknown_employee_id, reporter_id)
            else:
                raise(ex)

        task_action_reports.append(new_tar)

        presence_intervals = self.compute_man_presence_periods(reporter_id, action_time, task_action_reports, timetracks=[], commit=False)
        presence_timetracks = self.convert_intervals_to_presence_timetracks(presence_intervals, reporter_id)

        mainlog.debug(" presence_timetracks = {}".format(presence_timetracks))

        begin, end = day_period(action_time)

        # We're going to replace presence TT's. That's because updating
        # them seems a bit complex to me right now.

        # Technical note, SQLA says it can't evaluate in Python. So I
        # provide False as an argument to delete.

        session().query(TimeTrack).filter(
            and_( TimeTrack.task_id == presence_task_id,
                  TimeTrack.employee_id == reporter_id,
                  TimeTrack.start_time.between(begin,end))).delete(False)

        # Save all the new timetracks

        total_presence = 0
        for tt in presence_timetracks:
            session().add(tt)
            total_presence += tt.duration

        dao.day_time_synthesis_dao.save(reporter_id, ts_to_date(action_time), total_presence, 0, commit=False)

        session().commit()


    @RollbackDecorator
    def fast_create(self,task_id,reporter_id,action_time,action_kind,location):

        assert task_id is not None
        assert reporter_id is not None
        assert action_time is not None
        assert action_kind is not None

        t = TaskActionReport()
        t.task_id = task_id
        t.reporter_id = reporter_id

        t.time = action_time
        t.report_time = datetime.now()

        t.kind = action_kind
        t.origin_location = location

        t.status = TaskActionReport.CREATED_STATUS
        t.processed = False
        t.editor = None

        session().add(t)

        mainlog.debug(u"Fast create : {}".format(t))

        # t above will be in the result of the query below !!!
        task_action_reports = dao.task_action_report_dao.get_reports_for_employee_id_on_date(reporter_id,action_time.date())

        reporter = session().query(Employee).filter(Employee.employee_id == reporter_id).one()

        self.update_tars(reporter, action_time.date(), task_action_reports, [])

        # mainlog.debug(u"Fast create : {}".format(t))



    @RollbackDecorator
    def create_presence_if_necessary(self,employee_id,action_time,location):
        assert employee_id >= 0
        assert action_time
        assert location

        chrono_click("create_presence_if_necessary : emp_id:{} time:{} location:{}".format(employee_id,action_time,location))
        # task_action_reports = self.get_reports_for_employee_on_date(reporter,action_time.date())
        task_action_reports = self.get_reports_for_employee_id_on_date( employee_id, action_time.date())


        presence_tars = list(filter(lambda tar:tar.kind == TaskActionReportType.presence, task_action_reports))

        chrono_click("create_presence_if_necessary : {} presence tars out of {} tars".format(len(presence_tars), len(task_action_reports)))

        # Presences define a range. The first TAR gives the beginning of the period,
        # the second TAR (if any), the end of the period. If there are already
        # two TARS, we reuse one of them to extend the presence period.
        # Note that the period always expands, it never shrinks.

        t = None
        if len(presence_tars) < 2:
            t = TaskActionReport()
        elif action_time < task_action_reports[0].time and len(presence_tars) > 0:
            t = presence_tars[0]
        elif action_time > task_action_reports[-1].time and len(presence_tars) > 0:
            t = presence_tars[-1]
        else:
            return

        chrono_click("create_presence_if_necessary : 2")

        mainlog.debug("create_presence_if_necessary: {} {}".format(t.time,t.report_time))

        self.fast_create_after(self.presence_task_id_regular_time(),
                               employee_id,
                               action_time,
                               TaskActionReportType.presence,
                               location)


        # t.kind = TaskActionReportType.presence
        # t.time = action_time
        # t.report_time = datetime.now()
        # t.origin_location = location
        # t.reporter_id = employee_id

        # t.task = dao.task_action_report_dao.presence_task()
        # t.task_id = t.task.task_id

        # chrono_click("create_presence_if_necessary : 2b")

        # t.status = TaskActionReport.CREATED_STATUS
        # t.processed = False
        # t.editor = None

        # if t not in session():
        #     session().add(t)
        #     session().flush()
        #     task_action_reports.append(t)
        # else:
        #     mainlog.debug("Out of session")

        # chrono_click("create_presence_if_necessary : 3")

        # # self.update_tars(reporter, action_time.date(), task_action_reports, [])
        # self._update_presence_on_tars(t.reporter, action_time.date(), task_action_reports)

        # chrono_click("create_presence_if_necessary : 4")
        # session().commit()

        mainlog.debug("create_presence_if_necessary: done")


    @RollbackDecorator
    def start_unemployment(self,reporter,action_time,location):

        t = TaskActionReport()

        t.kind = TaskActionReportType.start_unemployment
        t.time = action_time
        t.origin_location = location
        t.reporter = reporter

        t.task = self.unemployment_task()
        t.report_time = datetime.now()
        t.status = TaskActionReport.CREATED_STATUS
        t.processed = False
        t.editor = None

        task_action_reports = dao.task_action_report_dao.get_reports_for_employee_on_date(reporter,action_time.date())
        task_action_reports.append(t)
        self.update_tars(reporter, action_time.date(), task_action_reports, [])
        return t

    @RollbackDecorator
    def _delete_all_logically(self,tars):
        mainlog.debug(u"--------------------------------------- deleting")
        for tar in tars:
            if tar.task_action_report_id:
                # We made sure we just delete TAR which actually were in
                # the database. Not those which were added by the user
                # while he was editing and edited right after.

                z = session().merge(tar) # merge returns an object :-)
                z.status = TaskActionReport.DELETED_STATUS



    @RollbackDecorator
    def multi_update(self,to_delete,to_create,to_update,current_employee):

        mainlog.debug(u"multi_update. To update = {}".format(to_update))

        # Updates are automatically handled by SQL Alchemy
        # (for objects which are already in the session of course)

        origin = os.environ['COMPUTERNAME']
        if not origin:
            origin = "ADMIN"

        for o in to_create + to_update:
            o.report_time = datetime.now()
            o.origin_location = origin
            o.processed = False
            o.editor = "ADMIN" # FIXME
            o.reporter = current_employee

            if o.task and not o.task.task_id:
                session().add(o.task)

        for o in to_create:
            o.status = TaskActionReport.CREATED_STATUS
            session().add(o)

        for o in to_delete:
            session().delete(o)

        for o in to_create + to_update + to_delete:
            o.processed = False

        # FIXME Was changed in a refactoring; not thoroughly tested
        for tars in to_create + to_update + to_delete:
            self.compute_activity_timetracks_from_task_action_reports(o,employee)

        session().commit()



    @RollbackDecorator
    def load_task_action_reports_for_edit(self,employee, d):
        task_action_reports = dao.task_action_report_dao.get_reports_for_employee_on_date(employee,d)

        for tar in task_action_reports:
            if isinstance(tar.task,TaskForPresence):
                d = tar.task.kind

        return task_action_reports

    @RollbackDecorator
    def update_tars(self, employee, base_date, task_action_reports, all_tars_to_delete):
        """ Save or update a set of task action reports. It is
        expected that those are all the current task action reports
        for the employee on a given date; or at least that those
        form a coherent set in time. This is because we'll rebuild all
        the timetracks associated to them. Also, it is expected
        that all the task action reports are for only one employee. """

        session().flush()

        employee = session().merge(employee)

        # At this point, since we optimise the task creation process
        # it is possible that some tasks are still not in the session
        # (or in the database)

        tasks = dict()
        for tar in task_action_reports:
            if tar.task: # Dayin/dayout have no task
                if not tar.task in tasks:
                    # mainlog.debug(u"Premerge task {}".format(tar.task))
                    tasks[tar.task] = session().merge(tar.task)
                tar.task = tasks[tar.task]
                mainlog.debug(u"Premerged task {} in {}".format(tar.task,tar))


        # We merge the TAR into the session (it's a merge because
        # we update the database with new or changed tars)

        all_tars = []
        for tar in task_action_reports:
            all_tars.append(session().merge(tar))

        tars_to_delete = []
        for tar in all_tars_to_delete:
            if tar.task_action_report_id:
                tars_to_delete.append(session().merge(tar))

            # if tar.task_action_report_id:
            #     all_tars.append(session().merge(tar))
            # else:
            #     session().add(tar)
            #     all_tars.append(tar)

            # session().flush()

        # Many of the operation we'll do later one rely on that
        # sort order. It's absolutely crucial to maintain it.
        all_tars = sorted(all_tars, key=lambda x:x.time)

        mainlog.debug(u"update tars ************************************************ ")

        for tar in all_tars:
            zid = "None"
            if tar.task:
                zid = id(tar.task)
            mainlog.debug(u"TAR : {} {} {} timetrack:{} task:{} / id():{}".format(tar.task_action_report_id, tar.time,tar.kind,tar.timetrack_id,tar.task_id,zid))
        mainlog.debug(u"")

        # mainlog.debug(u"tars to delete")
        # for tar in tars_to_delete:
        #     mainlog.debug(u"TAR : {} {} {} timetrack:{} task:{} / id(){}".format(tar.task_action_report_id, tar.time,tar.kind,tar.timetrack_id,tar.task_id,zid))
        # mainlog.debug(u"")


        # Detaching the TT's of the TARs. We have a specific phase for that
        # because it's very hard to track which TAR will get their TT
        # replaced or cleared. By separating the job, we make it easier.

        timetracks_to_delete = self._detach_tars_from_timetracks(all_tars)
        timetracks_to_delete |= self._detach_tars_from_timetracks(tars_to_delete)

        all_timetracks = dao.timetrack_dao.all_for_employee_date(employee,base_date)
        timetracks_to_delete = [tt.timetrack_id for tt in all_timetracks]

        # Now the presence time track, which are not tied to any TAR.

        # BUG this is date based but the TAR selection is not,
        # so there's a possible bug here (the TAR could span a period
        # extending outside the given base_date)

        # mainlog.debug(session().query(TimeTrack).all())

        # mainlog.debug(u"Presence TTs to delete for {} on {}".format(employee,base_date))
        # for i in self.timetrack_dao.all_presence_for_employee_date_managed_by_code(employee,base_date):
        #     mainlog.debug("presence TT to delete : {}".format(i[0]))
        #     timetracks_to_delete.add(i[0])

        # session().flush() # Fluh the detach before deleteing (otherwise SQLA gets mad)

        # note that SQLA seems to opitmize the following deletes
        # by gathering them in one SQL query
        # for tt in timetracks_to_delete:
        #     session().delete(tt)

        if len(timetracks_to_delete) > 0:
            mainlog.debug("Deleting timetracks ids : {}".format(timetracks_to_delete))
            session().query(TimeTrack).filter(TimeTrack.timetrack_id.in_(timetracks_to_delete)).delete('fetch')
        else:
            mainlog.debug("No timetracks to delete")

        session().flush()

        # Rebuild timetracks based on tars. The timetracks returned
        # are all brand new. That's not optimal but that's easier
        # to code (ie. we could reuse existing, unchanged timetracks).

        timetracks_tars = self.compute_activity_timetracks_from_task_action_reports(all_tars, employee.employee_id)

        # Add the timetrack on the session and reconnect to their TARs.
        # Since the timetrack are linked to employees, we merge them
        # into the session rather than adding them
        # Note that not all tars end up
        # being reconnected; some just stay orphan.
        # For example, you canhave two TARs on two different task
        # which are not linked to a timetrack bu, those 2 TARs
        # trigger the creation of a presence timetrack (which
        # is not connected to the TARs).

        if timetracks_tars:
            for timetrack,tars in timetracks_tars:
                mainlog.debug("update_tars : adding to session timetrack : {}".format(timetrack))
                session().add(timetrack)

                if tars:
                    for tar in tars:
                        mainlog.debug(u"Reattach... {} on {}".format(timetrack, tar))
                        tar.timetrack = timetrack

        # Make sure the references to timetracks (in the TARS) are
        # cleaned before deleting the timetracks.

        session().flush()

        # Logically delete to-be-deleted tars

        self._delete_all_logically(tars_to_delete)

        # Recompute the presence related stuff

        self._update_presence_on_tars(employee, base_date, all_tars)

        session().commit()













class TaskDAO(object):
    def __init__(self,session,task_action_report_dao):
        self.task_action_report_dao = task_action_report_dao

    @RollbackDecorator
    def create(self,description):
        task = Task()
        task.description = description
        session().add(task)
        session().commit()
        return task

    @RollbackDecorator
    def all_workable_tasks(self):
        return session().query(Task).filter(Task.imputable == True).all()

    @RollbackDecorator
    def tasks_count(self):
        c = session().query(Task).count()
        session().commit()
        return c

    @RollbackDecorator
    def all_tasks(self):
        return session().query(Task).all()

    @RollbackDecorator
    def find_by_id(self,identifier):
        # Don't forget inheritnace is at play here. So we won't
        # give a task back but a TaskOnOperation or some other inherited
        # class...

        return session().query(Task).filter(Task.task_id == identifier).one()


    def _flatten_task(self, task):
        # task is a "Task" instance.

        from koi.datalayer.generic_access import DictAsObj
        from koi.machine.machine_service import machine_service

        d = { "type" : type(task),
              "task_id" : task.task_id,
        }

        if isinstance(task,TaskForPresence):
            d['description'] = _("Presence")

        elif isinstance(task,TaskOnOperation):

            m = ""
            d['machine_id'] = task.machine_id
            if task.machine_id:
                m = machine_service.find_machine_by_id(task.machine_id).fullname
                d['machine_label'] = str(m)
            else:
                d['machine_label'] = None

            d['description'] = u"{}: {} on {}, {}".format(task.operation.production_file.order_part.human_identifier,
                                                          task.operation.operation_model.short_id,
                                                          m,
                                                          task.operation.description )
            d['order_part_id'] = task.operation.production_file.order_part.order_part_id
            d['order_part_label'] = task.operation.production_file.order_part.human_identifier
            d['operation_id'] = task.operation_id
            d['operation_definition_id'] = task.operation.operation_definition_id
            d['operation_definition_short_id'] = task.operation.operation_model.short_id
            d['operation_description'] = task.operation.description

            mainlog.debug(u"Flattened {}".format(d))

        elif isinstance(task,TaskOnNonBillable):

            d['description'] = u"{}: {}".format(task.operation_definition.short_id,
                                                task.operation_definition.description)
            d['operation_definition_id'] = task.operation_definition_id
            d['operation_definition_short_id'] = task.operation_definition.short_id
            d['operation_description'] = task.operation_definition.description

        elif isinstance(task,TaskOnOrder):
            d['description'] = "On order {} {}".format(task.order.label, task.order.customer_order_name)
        else:
            raise Exception("I can not flatten an object of type {}".format(type(task)))

        return DictAsObj(d)
        return KeyedTuple( d.keys(), labels=d.values())


    def potential_imputable_tasks_flattened(self,obj_type,obj_id,on_date):

        if obj_type == Operation:
            op = dao.operation_dao.find_by_id(obj_id)
            tasks = self.potential_imputable_tasks_for(op,on_date)
        else:
            tasks = []


        # FIXME Relaod old constraint on admin :
        # filter(is_task_imputable_for_admin,
        #       self.task_dao.potential_imputable_tasks_for(obj, self.base_d

        r = [self._flatten_task(t) for t in tasks]
        session().commit()
        return r


    @RollbackDecorator
    def find_by_ids_frozen(self, task_ids):
        """ This is specially tailored for some views.
        This will flatten the task data
        """

        tasks = []

        for task in session().query(Task).filter(Task.task_id.in_(task_ids)).all():

            tasks.append( self._flatten_task(task))

        session().commit()
        return tasks


    @RollbackDecorator
    def last_employees_on_task(self,task_ids):
        """ Return a list of pair (employee, time spent by employee on some tasks)
        """

        # I check both the TaskActionReports and the TimeTracks
        # because both can be populated independently
        # (that is, with TaskActionReport automatically implying
        # a TimeTrack)

        tar = session().query(Employee.employee_id.label("employee_id"),
                              TaskActionReport.time.label('time'),
                              literal(0).label('Duration')).\
            select_from(
                join(TaskActionReport,Employee)).\
            filter(TaskActionReport.task_id.in_(task_ids)).\
            filter(Employee.employee_id == TaskActionReport.reporter_id)

        tt = session().query(Employee.employee_id.label("employee_id"),
                             TimeTrack.start_time.label('time'),
                             TimeTrack.duration.label('Duration')).\
            select_from(join(TimeTrack,Employee)).\
            filter(TimeTrack.task_id.in_(task_ids)).\
            filter(Employee.employee_id == TimeTrack.employee_id)

        subq = tar.union(tt).order_by("time").subquery()

        return session().query(Employee,
                               func.sum(subq.c.Duration))\
                        .join(subq, subq.c.employee_id == Employee.employee_id).group_by(Employee).all()


    @RollbackDecorator
    def employees_on_task(self,task):
        # This on is subtle. You can have a single TAR for an employee
        # and without a second TAR, it's not possible to have a proper
        # Timetrack. Moreover, it's quit epossible to have Timetracks
        # without TARs...

        r = session().query(Employee).select_from(join(TaskActionReport,Employee)).filter(TaskActionReport.task_id == task.task_id).filter(Employee.employee_id == TaskActionReport.reporter_id).distinct()

        r2 = session().query(Employee).select_from(join(TimeTrack,Employee)).filter(TimeTrack.task_id == task.task_id).filter(Employee.employee_id == TimeTrack.employee_id).distinct()

        return set(r.all()) | set(r2.all())

    @RollbackDecorator
    def task_for_employee(self,employee):
        return session().query(Task).filter(Task.employee == employee).all()




    @RollbackDecorator
    def ongoing_tasks_for_employee(self,employee_id, at_time=None):
        """ List of ongoing tasks for an employee.
        A task is ongoing if it was started but not finished
        Or even restarted and still not finished.
        Task here are expected to be productive tasks (not presence ones).
        """

        # TaskActionReports are always associated to a task.
        # If a TaskActionReport is "start_task" and is *not* associated to a TimeTrack
        # it means the related task is started. It does not mean it is ongoing.
        # To have an ongoing task, it means that the last TARs associated to the
        # task are all "start" and not "stop".

        # The goal of this query is to avoid to read all of TARS to determine which
        # starts or ends a timetrack

        # We use the following invariant here :
        # if there are start TARs not associated to TT, then they are always after
        # the last stop TAR on the timeline OR there is no stop TAR
        # on the timeline at all.
        # Therefore, if a start TAR is followed (immediately or not) by
        # a stop TAR, then that start TAR will be endorsed by a timetrack
        # (tar.timetrack_id won't be null).

        # The big problem with the query is to know how much to look at.
        # That is, if a task has hundreds of TARs, then it might difficult
        # to know if the task is actually stopped or started. For example :
        # Start, start, start, ..., start, stop.

        # Imagine a situation where there's a start task followed
        # by a year of valid timetracks. While perfectly valid, there's
        # this problem that we'll always think the task is started
        # if we only look at it alone. That is, without looking at stop
        # task after, one cannot know the start is inactive...

        # Another way to look at this is when somebody forgets
        # to stop a task. If he was allowed to stop it, for example,
        # the day after, then, we'd have a record tracking activity
        # on the task that goes from the past day to the present
        # one, which is not correct...

        time_limit = business_computations_service.tar_time_horizon(at_time)


        mainlog.debug('ongoing_tasks_for_employee ' + '----' * 50)
        mainlog.debug("From {} to {}".format(time_limit, at_time))


        # A task is ongoing if the last TAR is a start one.
        # So we can look at each of the last TARs of all the task.
        # But htat's a difficult query to write... It involves all the
        # task and all the TARS of a given person.

        # I still have no clue on how to do it efficiently (using timetrack
        # info is not right because timetracks cannot be interpreted in
        # the past). So the only solution is to limit the query in
        # a time interval.

        # We include presence TAR's because they can stop progress on a task too

        tars = session().query(TaskActionReport.task_id, TaskActionReport.kind).\
               filter(and_(TaskActionReport.status != TaskActionReport.DELETED_STATUS,
                           TaskActionReport.reporter_id == employee_id,
                           TaskActionReport.time.between(time_limit,at_time))).\
               order_by(desc(TaskActionReport.time)).all()

        # mainlog.debug("Located TARS : {}".format(tars))

        tasks = dict()

        for task_id, kind in tars:
            # This is more clever than you think. Remember the TARS were sorted
            # by decreasing report time. So we basically take the last
            # of the TAR for each task.

            if kind == TaskActionReportType.day_out:
                # because of the desc order on time, as soon as we encounter
                # the day out it means we can't have anything "ongoing"
                # anymore
                break

            elif task_id not in tasks:
                tasks[task_id] = kind


        # mainlog.debug("Extracted tasks : {}".format(tasks))

        task_ids = []
        for task_id, kind in tasks.items():
            # If the last of the TARs for a task is a "start_task", then
            # we consider that task as "ongoing".
            if kind == TaskActionReportType.start_task:
                task_ids.append(task_id)

        if task_ids:
            c = all_non_relation_columns(Task)
            tasks = session().query(*c).filter(Task.task_id.in_(task_ids)).all()
            return tasks
        else:
            return []


        # # Because of the order_by, the TAR.time is added to the select
        # # (and anyway, Postgres requires it for ordering too)
        # # consequently, I can't use distinct to the effect of selecting
        # # distinct tasks... I do it by hand.
        # # I have investigated the use of a subquery, but then how could
        # # I knwo the name of the SQL alis for TAR.time so that I could
        # # exlucde it from a select distinct...

        # task_ids = set()
        # ret = []

        # for task in tasks:
        #     if task.task_id not in task_ids:
        #         mainlog.debug("ongoing_tasks_for_employee : {}".format(task))
        #         task_ids.add(task.task_id)
        #         ret.append(task)



        # session().commit()

        # # The user can use "task_type" to know what kind of task we returned.

        # return ret

        # # reports = self.task_action_report_dao.get_reports_for_employee(employee)

        # # mainlog.debug("ongoing_tasks_for_employee : {} task action reports".format(len(reports)))

        # # for r in reports:
        # #     mainlog.debug(r)
        # #     if r.kind == TaskActionReportType.start_task and r.task not in t:
        # #         t.append(r.task)
        # #     elif r.kind == TaskActionReportType.stop_task and r.task in t:
        # #         t.remove(r.task)

        # # return t


    @RollbackDecorator
    def tasks_for_order_part(self,order_part):
        tasks = []
        if order_part.has_operations():
            for op in order_part.production_file[0].operations:
                if op.task is not None:
                    tasks.append(op.task)
        return tasks


    @RollbackDecorator
    def task_for_operation(self,operation_id):
        q = session().query(TaskOnOperation).filter(TaskOnOperation.operation_id == operation_id)
        return q.first()

    @RollbackDecorator
    def task_for_non_billable(self,operation_definition_id):
        q = session().query(TaskOnNonBillable).filter(TaskOnNonBillable.operation_definition_id == operation_definition_id)
        # printquery(q)
        return q.first()

    @RollbackDecorator
    def task_for_order(self,order_id,operation_definition_id):
        return session().query(TaskOnOrder).filter( and_( TaskOnOrder.order_id == order_id,
                                                             TaskOnOrder.operation_definition_id == operation_definition_id)).first()

    @RollbackDecorator
    def select_for_operations(self,operations):

        operations_ids = []
        for o in operations:
            operations_ids.append(o.operation_id)

        # This is not very nice (we use identifiers directly). Howver SQL Alchemy
        # doesn't provide any other way (I've tried with Task.operation.in_(operations)
        # but I get operations_ids "not implemented" exception

        return session().query(Task).filter(Task.operation_id.in_(operations_ids))


    @RollbackDecorator
    def create_non_billable_task(self,operation_definition_id):
        mainlog.debug(u"create_non_billable_task {}".format(operation_definition_id))
        t = TaskOnNonBillable()
        t.operation_definition_id = operation_definition_id
        session().add(t)
        session().flush() # Without that the id doesn't get turned into a related object
        mainlog.debug(u"create_non_billable_task {}".format(t))
        return t

    @RollbackDecorator
    def create_task_on_order(self,order_id, operation_definition_id):
        t = TaskOnOrder()
        t.order_id = order_id
        t.operation_definition_id = operation_definition_id
        session().add(t)
        session().flush() # Without that the id doesn't get turned into a related object
        return t

    @RollbackDecorator
    def create_task_on_operation(self,operation_id, machine_id):
        assert operation_id # That's the minimum, we tolerate a blank machine

        t = TaskOnOperation()
        t.operation_id = operation_id
        t.machine_id = machine_id
        session().add(t)
        session().flush() # Without that the id doesn't get turned into a related object
        mainlog.debug("Created task_on_operation(operation_id = {}, machine_id={}) : task_id={}".format(t.operation_id, t.machine_id, t.task_id))
        return t




    @RollbackDecorator
    def potential_imputable_tasks_for(self,o,on_date):
        """ Pay attention, the task returned by the function may or may not
        be in the session, mays or may not be in the database !!! Therefore
        if you use some of them, make sure you handle persistence
        appropriately.

        """

        tasks = []

        if o == None:

            """ A task for none is a task for non billable stuff.
            Non billable stuff is never associated to anything. """

            tasks_opdef = set()
            for d in session().query(TaskOnNonBillable).all():
                if d.operation_definition not in tasks_opdef:
                    tasks.append(d)
                    tasks_opdef.add(d.operation_definition)

            for d in dao.operation_definition_dao.all_imputable_unbillable(on_date):
                if d not in tasks_opdef:
                    t = TaskOnNonBillable()
                    t.operation_definition = d
                    tasks.append(t)

        elif isinstance(o,Operation):

            mainlog.debug(u"potential_imputable_tasks_for.on operation {}".format(o))
            current_tasks = session().query(TaskOnOperation).filter(TaskOnOperation.operation == o).all()

            if len(current_tasks) > 0:
                tasks.append(current_tasks[0])
            else:
                t = TaskOnOperation()
                t.operation = o
                tasks.append(t)

        elif isinstance(o,OperationDefinition):

            q = session().query(OperationDefinition.operation_definition_id, OperationDefinition.description, TaskOnNonBillable).\
                outerjoin(TaskOnNonBillable).options(noload('timetracks')).\
                filter( and_( OperationDefinition.imputable == True,
                              OperationDefinition.on_order == False,
                              OperationDefinition.on_operation == False,
                              OperationDefinition.operation_definition_id == o.operation_definition_id))

            op_id, op_desc, task_on_opdef = q.one()
            if not task_on_opdef:
                t = TaskOnNonBillable()
                t.operation_definition_id = op_id
                t.description = op_desc or ""
                tasks.append(t)
            else:
                tasks.append(task_on_opdef)

        elif isinstance(o,Operation):

            # For operations, there is 0 or 1 task, but not more.
            # That's because operations are tied to one and only one
            # operation definition

            current_tasks = session().query(TaskOnOperation).filter(TaskOnOperation.operation_id == Operation.operation_id).all()

            if len(current_tasks) > 0:
                tasks.append(current_tasks[0])
            else:
                t = TaskOnOperation()
                t.operation = o
                tasks.append(t)

        elif isinstance(o,OrderPart):

            mainlog.debug("Looking for tasks on order part {}".format(o.order_part_id))

            # On a given order part, there are several operations
            # Some of these operations are tied to TaskOperation. The
            # others are tied to nothing.

            # Here we ensure that each is tied to a TakOperation,
            # in memory (we leave it to the caller to save them
            # or not)

            for op,tasks_on_op in session().query(Operation,TaskOnOperation).outerjoin(TaskOnOperation).join(ProductionFile).filter(ProductionFile.order_part_id == o.order_part_id).order_by(asc(Operation.position)).all():


                # FIXME Pay attention, an operation not always have an operation
                # model. I'll be able to have that once I have a much better
                # import code (one that merges double lines operations)

                if tasks_on_op is None and op.operation_model:
                    t = TaskOnOperation()
                    t.operation = op

                    # FIXME Dirty. I set the dscription because normally, in
                    # TaskOnOperation the description is an SQLA Column Property.
                    # Therefore it is init'ed only when one reads the
                    # TaskOnOperation, not when it is created.

                    t.description = op.description

                    tasks.append(t)
                elif tasks_on_op is not None:
                    tasks.append(tasks_on_op)

        elif isinstance(o, Order):

            mainlog.debug("potential_imputable_tasks_for : look for task on order")

            # First we gather the TaskOnOrders that are currently tied to
            # the order we're interested in.

            tasks_opdef = set()
            for d in session().query(TaskOnOrder).filter(TaskOnOrder.order == o).all():
                if d.operation_definition not in tasks_opdef:
                    tasks.append(d)
                    tasks_opdef.add(d.operation_definition)
                mainlog.debug(u"skip list += {} ({})".format(d.operation_definition,type(d.operation_definition)))

            # Now we *generate* the TaskOnOrder that could be (depending on
            # what the user do) tied to the order.
            for d in dao.operation_definition_dao.all_on_order(): # BUG Date not takne into account !!!
                # Make sure we reuse existing TaskOnOrder if possible.
                if d not in tasks_opdef:
                    t = TaskOnOrder()
                    t.order = o
                    t.operation_definition = d
                    tasks.append(t)

                    mainlog.debug("potential_imputable_tasks_for : buildinng a new task, imputable ? {}".format(t.imputable))

                    # Pay attention, none of the TaskOnOrder is attached
                    # to a DB session !!! Don't forget to do it
                    # if necessary

                else:
                    mainlog.debug(u"Skipping {}".format(d))
        else:
            raise Exception("Unrecognized object type : {}".format(type(o)))

        return tasks

        # Only present imputable stuff to the user
        # return filter(lambda t:t.imputable == True, tasks)



    @RollbackDecorator
    def potential_imputable_tasks_for_BACKUP(self,o,on_date):
        """ Pay attention, the task returned by the function may or may not
        be in the session, may or may not be in the database !!! Therefore
        if you use some of them, make sure you handle persistence
        appropriately.

        """

        mainlog.debug("potential_imputable_tasks_for")

        tasks = []

        if o == None:

            """ A task for none is a task for non billable stuff.
            Non billable stuff is never associated to anything. """

            q = session().query(OperationDefinition.operation_definition_id, OperationDefinition.description, TaskOnNonBillable).\
                outerjoin(TaskOnNonBillable).options(noload('timetracks')).\
                order_by(asc(Operation.position)).\
                filter( and_( OperationDefinition.imputable == True,
                              OperationDefinition.on_order == False,
                              OperationDefinition.on_operation == False))

            for op_id, op_desc, task_on_opdef in q.all():
                if not task_on_opdef:
                    t = TaskOnNonBillable()
                    t.operation_definition_id = op_id
                    t.description = op_desc or ""
                    tasks.append(t)
                else:
                    tasks.append(task_on_opdef)

        elif isinstance(o,OrderPart):

            mainlog.debug("Looking for tasks on order part {}".format(o.order_part_id))
            mainlog.debug("*"*1000)

            # On a given order part, there are several operations
            # Some of these operations are tied to TaskOperation. The
            # others are tied to nothing.

            # Here we ensure that each is tied to a TaskOnOperation,
            # in memory (we leave it to the caller to save them
            # or not). We do that by creating the appropriate TaskOnOperation
            # and linking it to an Operation

            for op_id, op_desc, tasks_on_op in session().query(Operation.operation_id,Operation.description,TaskOnOperation).outerjoin(TaskOnOperation).join(ProductionFile).filter(ProductionFile.order_part_id == o.order_part_id).filter(Operation.operation_definition_id > 0).options(noload('operation'),noload('timetracks')).order_by(asc(Operation.position)).all():

                # FIXME Pay attention, an operation not always have an operation
                # model. I'll be able to have that once I have a much better
                # import code (one that merges double lines operations)

                if tasks_on_op is None and op_id:
                    mainlog.debug("building potential task")

                    t = TaskOnOperation()
                    t.operation_id = op_id

                    # FIXME Dirty. I set the dscription because normally, in
                    # TaskOnOperation the description is an SQLA Column Property.
                    # Therefore it is init'ed only when one reads the
                    # TaskOnOperation, not when it is created.

                    t.description = op_desc

                    tasks.append(t)

                elif tasks_on_op is not None:
                    mainlog.debug("reusing task")
                    mainlog.debug(tasks_on_op)

                    a = tasks_on_op.description
                    session().expunge(tasks_on_op)
                    mainlog.debug("task expunged")

                    tasks.append(tasks_on_op)

            mainlog.debug("Done loading tasks on order part {}".format(o.order_part_id))
            mainlog.debug("*"*1000)

        elif isinstance(o, Order):

            mainlog.debug("potential_imputable_tasks_for : look for task on order")

            # First we gather the TaskOnOrders that are currently tied to
            # the order we're interested in.

            tasks_opdef = set()
            for d in session().query(TaskOnOrder).filter(TaskOnOrder.order == o).all():
                if d.operation_definition not in tasks_opdef:
                    tasks.append(d)
                    tasks_opdef.add(d.operation_definition)
                mainlog.debug(u"skip list += {} ({})".format(d.operation_definition,type(d.operation_definition)))

            # Now we *generate* the TaskOnOrder that could be (depending on
            # what the user do) tied to the order.
            for d in dao.operation_definition_dao.all_on_order(): # BUG Date not takne into account !!!
                # Make sure we reuse existing TaskOnOrder if possible.
                if d not in tasks_opdef:
                    t = TaskOnOrder()
                    t.order = o
                    t.operation_definition = d
                    tasks.append(t)

                    mainlog.debug("potential_imputable_tasks_for : buildinng a new task, imputable ? {}".format(t.imputable))

                    # Pay attention, none of the TaskOnOrder is attached
                    # to a DB session !!! Don't forget to do it
                    # if necessary

                else:
                    mainlog.debug(u"Skipping {}".format(d))


        return tasks

        # Only present imputable stuff to the user
        # return filter(lambda t:t.imputable == True, tasks)

    def _get_task_for_order(self, order_id, operation_definition_id):

        tasks = session().query(TaskOnOrder).filter(
            and_( TaskOnOrder.order_id == order_id,
                  TaskOnOrder.operation_definition_id == operation_definition_id)).all()

        if len(tasks) == 1:
            return tasks[0].task_on_order_id

        elif len(tasks) == 0:
            task = TaskOnOrder()
            task.order_id = order_id
            task.operation_definition_id = operation_definition_id
            session().add(task)
            session().flush() # get a task id

            return task.task_id

        else:
            raise Exception("There are more than one task for an order operation ???")

    def _get_task_for_non_billable(self, operation_definition_id):
        """ Read or create a task on a non billable operation
        """

        tasks = session().query(TaskOnNonBillable).filter(TaskOnNonBillable.operation_definition_id == operation_definition_id).all()

        if len(tasks) == 1:
            return tasks[0].task_on_operation_definition_id
        elif len(tasks) == 0:
            task = TaskOnNonBillable()
            task.operation_definition_id = operation_definition_id
            session().add(task)
            session().flush() # get the task_id
            return task.task_on_operation_definition_id
        else:
            raise Exception("There are more than one task for an unbillable operation ???")


    def _get_task_for_operation_and_machine(self, operation_id, machine_id, commit=False):
        """ Will either find or create a task for the given pair operation/machine.
        The operation is expected to exist and being imputable.
        If the task already exists, we ensure that it is active.
        In any case, we validate that the machine can be used for the operation.

        So, if you get a task out of here, then you're 100% sure you can
        record time on it (provided you stay in the same transaction).
        """
        assert operation_id > 0
        assert not machine_id or machine_id > 0

        if not machine_id:
            machine_id = None


        from koi.machine.machine_service import machine_service

        # The way we filter in the outer join clause is very important.

        q = session().query(Operation.operation_id,
                            Order.accounting_label.label("order_accounting_label"),
                            OrderPart.label.label("order_part_label"),
                            OperationDefinition.operation_definition_id,
                            OperationDefinition.short_id.label("operation_definition_short_id"),
                            Operation.description.label("operation_description"),
                            and_(OperationDefinition.imputable == True,
                                 OperationDefinition.on_operation == True,
                                 or_(True,
                                     Order.state == OrderStatusType.order_ready_for_production)).label("imputable"),
                            TaskOnOperation.task_id,
                            Order.state.label("order_state"),
                            TaskOnOperation.active.label("task_active")).\
            join(ProductionFile).\
            join(OrderPart).join(Order).\
            join(OperationDefinition, OperationDefinition.operation_definition_id == Operation.operation_definition_id).\
            join(Customer, Order.customer_id == Customer.customer_id).\
            outerjoin(TaskOnOperation,
                      and_(
                          TaskOnOperation.operation_id == Operation.operation_id,
                          TaskOnOperation.machine_id == machine_id)).\
            options(lazyload('*')).\
            filter( Operation.operation_id == operation_id)


        operation = q.all()

        if len(operation) > 1:
            raise Exception("_get_task_for_operation_and_machine : Too many results")

        elif not operation:

            c = session().query(Operation.operation_id).filter(Operation.operation_id == operation_id).count()

            if c == 0:
                raise ServerException(ServerErrors.operation_unknown,operation_id)
            else:
                mainlog.error("_get_task_for_operation_and_machine : The operation exists but it is not imputable")
                raise ServerException(ServerErrors.operation_non_imputable,operation_id,None)

        operation = operation[0]

        task_id = operation.task_id

        # Check if the pointage has to be recorded on a machine too.

        machine_ids = [m.machine_id for m in machine_service.find_machines_for_operation_definition(operation.operation_definition_id)]

        mainlog.debug("Authorized machine id's are : {}; you gave {}".format(machine_ids, machine_id))

        if machine_id: # BUG Tolerate null machines. Decide if it must be so

            if not machine_id and machine_ids:
                raise ServerException( ServerErrors.machine_not_compatible_with_operation, machine_id, str(machine_ids))
            elif machine_id and machine_id not in machine_ids:
                raise ServerException( ServerErrors.machine_not_compatible_with_operation, machine_id, str(machine_ids))


        if operation.imputable:

            # Make sure a taks is tied to the operation/machine

            if operation.task_id is None:

                mainlog.debug("_make_task_for_operation_and_machine : create_task_on_operation")
                task_id = dao.task_dao.create_task_on_operation(operation_id, machine_id).task_id

            elif not operation.task_active:
                raise ServerException(ServerErrors.task_not_imputable, task_id)
        else:
            opdef = session().query(OperationDefinition).filter(OperationDefinition.operation_definition_id == operation.operation_definition_id).one()

            mainlog.error("Operation definition for operation is ")
            mainlog.error(opdef)
            mainlog.error(" ... is imputable ? {}, is on operation ? {}".format(
                opdef.imputable,
                opdef.on_operation))
            mainlog.error("Order state is {}".format(operation.order_state))

            raise ServerException(ServerErrors.operation_non_imputable,
                                  u"'{} {}'".format( (operation.operation_definition_short_id or ""), (operation.operation_description or "")),
                                  str(operation.order_accounting_label) + (operation.order_part_label or '-'))

        if commit:
            session().commit()
        return task_id




class EmployeeDAO(object):
    def __init__(self,session):
        self._table_model = None
        # self._reload_cache()

    @RollbackDecorator
    def authenticate(self, identifier, password):
        q = session().query(Employee).filter(and_(Employee.login == identifier,
                                                  Employee.password == password,
                                                  Employee.is_active == True)).first()

        session().commit()
        # mainlog.debug(u"Authenticate : password {}".format(password))
        if q:
            return q
        else:
            return False

    @RollbackDecorator
    def save(self,employee):
        if not employee in session():
            session().add(employee)
        session().commit()

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
    def find_by_id(self,identifier):
        # FIXME replace by cache access
        try:
            return session().query(Employee).filter(Employee.employee_id == identifier).one()
        except NoResultFound as ex:
            mainlog.error("EmployeeDAO.find_by_id: Failed to find with id {} of type {}".format(identifier,type(identifier)))
            raise ex

    @RollbackDecorator
    def find_by_login(self,login):
        return session().query(Employee).filter(Employee.login == login).first()


    @RollbackDecorator
    def find_by_ids(self,identifiers):
        # return session().query(Employee).filter(in_Employee.employee_id.in_(identifiers)).one()
        if identifiers == None:
            raise "I can't find None"
        else:
            return list(map( lambda a:self._cache[a], identifiers))

    @RollbackDecorator
    def any(self):
        # FIXME replace by cache access
        return session().query(Employee).order_by(Employee.fullname).first()

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
            raise DataException(_("Cannot delete this employee because there are orders for him. Remove the orders first."))
        except Exception as e:
            mainlog.exception(e)
            session().rollback()
            raise e

    @RollbackDecorator
    def save(self,employee):
        session().add(employee)
        session().commit()
        self._reload_cache()

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


    @RollbackDecorator
    def find_activity(self, employee_id, start_date, end_date):
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


    # Never used

    # def working_on_operation(self,target_operation):
    #     # FIXME operation=_id comparisons are not nice...
    #     return current_session.query(Employee).join(TimeTrack.employee).join(TimeTrack.task).join(Task.operation).filter(Operation.operation_id == target_operation.operation_id).all()


    # def list_model(self):
    #     if self._table_model != None:
    #         return self._table_model

    #     self._table_model = QStandardItemModel(2, 1, None)

    #     allc = session().query(Employee).order_by(Employee.fullname).all()
    #     self._table_model.setRowCount( len(allc))

    #     i = 0
    #     for c in allc:
    #         item = QStandardItem(c.fullname)
    #         item.setData(c,Qt.UserRole)
    #         self._table_model.setItem(i,0,item)
    #         i = i + 1

    #     return self._table_model


class OperationDAO(object):
    def __init__(self,session):
        pass

    def make(self):
        op = Operation()
        return op

    @RollbackDecorator
    def find_by_id(self,operation_id):
        return session().query(Operation).filter(Operation.operation_id == operation_id).one()


    @RollbackDecorator
    def find_next_action_for_employee_operation_machine(self, employee_id, operation_id, machine_id):
        # Rememeber that we're interested in Task, first and foremost.
        # We allow this to be called with necessary parameters to find
        # a task (rather than the task_id iteself) to ease the implementation
        # at the delivery_slips level.

        # Here we expect one and only one row because the pair operation/machine
        # should fully discrimante one or zero TaskOnOperation (on machine)

        task_id = session().query(TaskOnOperation.task_id).\
                  filter(and_(TaskOnOperation.operation_id == operation_id,
                              TaskOnOperation.machine_id == machine_id)).scalar()

        if not task_id:
            # If the task doesn't exist, it means no TAR has ever been
            # recorded => so the first TAR to come will be a start.
            return TaskActionReportType.start_task
        else:
            return self.find_next_action_for_task(task_id, employee_id)


    @RollbackDecorator
    def find_next_action_for_employee_operation(self, employee_id, operation_id, commit=True):
        # Rememeber that we're interested in Task, first and foremost.
        # We allow this to be called with necessary parameters to find
        # a task (rather than the task_id iteself) to ease the implementation
        # at the delivery_slips level.

        # Here we expect one and only one row because the operation
        # should fully discriminate one or zero TaskOnOperation (*not* on machine)

        task_id = session().query(TaskOnOperation.task_id).\
                  filter( and_(TaskOnOperation.operation_id == operation_id,
                               TaskOnOperation.machine_id == None)).scalar()
        return self.find_next_action_for_task(task_id, employee_id, commit)


    @RollbackDecorator
    def find_next_action_for_task(self, task_id, employee_id, commit=True, at_time=None):
        assert employee_id
        # task_id can be null

        # Basic principle is to the last of all the TAR's of the task

        q = session().query(TaskActionReport.task_action_report_id, TaskActionReport.kind).\
            filter(and_(TaskActionReport.timetrack_id == None,
                        TaskActionReport.task_id == task_id,
                        TaskActionReport.reporter_id == employee_id)).\
            order_by(desc(TaskActionReport.time),desc(TaskActionReport.task_action_report_id))

        # ... but all the TAR's can be too many. So we put a limit in
        # time. Moreover, if we say that TAR are local to a working day
        # it makes no sense to load too-old TAR's

        if not at_time:
            at_time = datetime.now()

        time_limit = business_computations_service.tar_time_horizon(at_time)
        q = q.filter( TaskActionReport.time.between(time_limit, at_time))

        # So we pick the last (that's where the filter makes sense; without
        # it we might go to a full table scan)

        last_action_report = q.first()

        last_action_report_kind = None
        if last_action_report:
            # There is a last action report
            last_action_report_kind = last_action_report.kind

        # Who else works on the task ?
        # q = self.dao.session.query(TaskActionReport.task_action_report_id, TaskActionReport.reporter_id).filter(and_(TaskActionReport.task_id == task_id,TaskActionReport.reporter_id != employee_id)).order_by(desc(TaskActionReport.time),desc(TaskActionReport.task_action_report_id))

        # When pointage is on started task, then we *guess*
        # the intention of the user is to stop the task.
        # and vice versa...

        next_action_kind = TaskActionReportType.start_task

        if last_action_report_kind == TaskActionReportType.start_task:
            next_action_kind = TaskActionReportType.stop_task
        elif last_action_report_kind == TaskActionReportType.stop_task:
            next_action_kind = TaskActionReportType.start_task

        if commit:
            session().commit()

        return next_action_kind


    @RollbackDecorator
    def find_by_operation_id_frozen(self, employee_id, operation_id, commit=True):
        """ Find a lot of information about an operation.
        The employee is necessary to determine what the next
        action is possible on that operation.
        The operation must be ready for timetracking (active, etc.)
        """

        assert operation_id
        assert employee_id

        mainlog.debug("find_by_operation_id_frozen")

        # For some reason, I had to give a join condition on OpDef. Without that it joins
        # on *all* op def's :-( FIXME

        operation = session().query(Operation.operation_id,
                                    Operation.description,
                                    Operation.position,
                                    OperationDefinition.operation_definition_id,
                                    OperationDefinition.description.label("operation_definition_description"),
                                    OperationDefinition.short_id.label("operation_definition_short"),
                                    and_( OperationDefinition.imputable == True,
                                          OperationDefinition.on_operation == True).label("operation_imputable"),
                                    Order.state.label("order_state"), # == OrderStatusType.order_ready_for_production,
                                    and_(OperationDefinition.imputable == True,
                                         OperationDefinition.on_operation == True,
                                         Order.state == OrderStatusType.order_ready_for_production).label("imputable"),
                                    OrderPart.human_identifier.label("order_part_identifier"),
                                    OrderPart.description.label("order_part_description"),
                                    Customer.fullname.label("customer_name")).\
            join(ProductionFile).\
            join(OrderPart).join(Order).\
            join(Customer).\
            join(OperationDefinition, OperationDefinition.operation_definition_id == Operation.operation_definition_id).\
            filter(Operation.operation_id == operation_id).one()

        colleagues = self.find_who_is_on_operation(operation_id)

        machines = machine_service.find_machines_for_operation_definition(operation.operation_definition_id)

        if not machines:
            mainlog.debug("No machine for current operation")

            # This is an optimisation to avoid a second call to determine
            # the next action. The need for this optimisation comes from the
            # way the delivery_slips work (scanning an operation instantly decides
            # if one has to stop/start the associated task)

            next_action_kind = self.find_next_action_for_employee_operation(employee_id, operation_id, commit=False)
        else:
            # When there are several machines, it's not always possible to know
            # what will be the next action. If we know which machine
            # is concerned, then we can know, but not here.

            # For example, the employee may have started work on two
            # machines A,B and stopped on one of them A. Therefore he can stop
            # the work on B or start on A. So both possibilities are there.
            # To be able to convey that information I should create a new
            # "next_actionkind" type ( FIXME )

            next_action_kind = None



        session().commit()
        return operation, machines, next_action_kind, colleagues

    @RollbackDecorator
    def find_by_order_part_id_frozen(self,order_part_id):
        from koi.datalayer.generic_access import all_non_relation_columns

        entities = session().query(*all_non_relation_columns(Operation)).join(ProductionFile).filter(ProductionFile.order_part_id == order_part_id).order_by(Operation.position).all()
        f = freeze(session(),entities)
        session().commit()
        return f


    @RollbackDecorator
    def save(self,operation):
        if operation not in session():
            session().add(operation)
        session().commit()


    @RollbackDecorator
    def find_who_is_on_operation(self, operation_id):
        """ Find the employees who are working or have worked on the
        operation. Also gives what their last action was (start or stop,
        on which machine).
        """

        # mainlog.debug(u"find_who_is_on_operation: operation_id {}".format(operation_id))

        tars = session().query(TaskActionReport.reporter_id,
                               TaskActionReport.kind,
                               Employee.fullname,
                               TaskOnOperation.machine_id).\
               join(Task).\
               join(TaskOnOperation).\
               join(Employee).\
               filter(TaskOnOperation.operation_id == operation_id).\
               order_by( desc( TaskActionReport.time))

        # We pick the last action of each employee and
        # discard everything else

        colleagues = dict()
        for tar in tars:
            # mainlog.debug(u"find_who_is_on_operation {}".format(tar))
            if tar.reporter_id not in colleagues:
                colleagues[tar.reporter_id] = tar

        return [x for x in colleagues.values()]




    @RollbackDecorator
    def last_employees_on_operation(self,operation_id):
        """ Return a list of pair (employee, time spent by employee on operation)
        """

        ret = []
        task_ids = session().query(TaskOnOperation.task_id).filter(TaskOnOperation.operation_id == operation_id).all()

        if task_ids:

            task_ids = [tid.task_id for tid in task_ids]

            employees_hours = dao.task_dao.last_employees_on_task(task_ids)
            for employee, hours in employees_hours:
                ret.append( (freeze(session(),employee), hours) )

        session().commit()
        return ret


    @RollbackDecorator
    def operations_for_order_parts_frozen(self,order_parts_id):

        if not order_parts_id:
            return order_parts_id

        if type(order_parts_id) != list:
            order_parts_id = list(order_parts_id)

        operations = session().query(ProductionFile.order_part_id, Operation).\
                     filter(and_(ProductionFile.production_file_id == Operation.production_file_id,
                                 ProductionFile.order_part_id.in_(order_parts_id))).\
                     order_by(Operation.position).all()

        mainlog.debug(operations)

        d = dict()
        for part_id, op in operations:
            if part_id not in d:
                d[part_id] = []
            d[part_id].append(freeze(session(),op))

        return d

    # @RollbackDecorator
    # def operation_for_task(self,task):
    #     return session().query(Operation).filter(Operation.task == task).one()



    @RollbackDecorator
    def load_all_operations_ready_for_production(self):
        # The tricky thing is that one can have the same operation
        # appearing several times in one order part.

        all_operations = session().query(Operation.planned_hours,
                                         Operation.done_hours,
                                         Operation.description,
                                         OrderPart.description.label("order_part_description"),
                                         label("order_part_human_identifier", OrderPart.human_identifier),
                                         OperationDefinition.operation_definition_id,
                                         OrderPart.qty,
                                         OrderPart.deadline).\
                         join(ProductionFile).\
                         join(OrderPart).\
                         join(Order).\
                         join(OperationDefinition).\
                         filter(OrderPart.state == OrderPartStateType.ready_for_production).\
                         order_by(Order.accounting_label,OrderPart.position).\
                         all()

        session().commit()

        return all_operations



# class SuppliersDAO(object):
#     def __init__(self,session):
#         session() = session
#         self._table_model = None

#     def list_model(self):
#         if self._table_model != None:
#             return self._table_model

#         self._table_model = QStandardItemModel(1, 1, None)

#         allc = session().query(Supplier).order_by(Supplier.fullname).all()
#         self._table_model.setRowCount( len(allc))

#         i = 0
#         for c in allc:
#             item = QStandardItem(c.fullname)
#             item.setData(c,Qt.UserRole)
#             self._table_model.setItem(i,0,item)

#             i = i + 1

#         return self._table_model

from koi.central_clock import central_clock

class DeliverySlipDAO(object):
    def __init__(self,session,order_dao):
        self.order_dao = order_dao

    @RollbackDecorator
    def id_exists(self, identifier):
        r = len(session().query(DeliverySlip).filter(DeliverySlip.delivery_slip_id == identifier).all()) > 0
        session().close()
        return r

    @RollbackDecorator
    def find_recent2(self, count=100):
        q = session().query(DeliverySlip.delivery_slip_id,
                            DeliverySlip.creation,
                            DeliverySlip.active,
                            Customer.fullname,
                            Order.user_label).\
            join(DeliverySlipPart).join(OrderPart).join(Order).join(Customer).order_by(desc(DeliverySlip.creation)).distinct(DeliverySlip.delivery_slip_id,
                            DeliverySlip.creation,
                            DeliverySlip.active,
                            Customer.fullname,
                            Order.user_label).limit(count).all()
        session().commit()
        return q

    @RollbackDecorator
    def find_recent(self, count=100):
        q = session().query(DeliverySlip).options(joinedload('delivery_slip_parts')).order_by(desc(DeliverySlip.creation)).limit(count).all()
        slips = []
        for slip in q:
            slips.append( [slip.delivery_slip_id,
                           slip.creation,
                           slip.delivery_slip_parts[0].order_part.order.customer.fullname,
                           str(slip.delivery_slip_parts[0].order_part.order.user_label)])
        session().close()
        return slips

    @RollbackDecorator
    def slips_for_order_part(self, order_part_id):
        parts = session().query(DeliverySlipPart.quantity_out,
                                DeliverySlip.delivery_slip_id,
                                DeliverySlip.creation).join(DeliverySlip).\
            filter( and_( DeliverySlip.active == True, DeliverySlipPart.order_part_id == order_part_id) ).order_by( desc(DeliverySlip.creation))
        session().commit()
        return parts

    @RollbackDecorator
    def load_slip_parts_frozen(self, slip_id):
        """ Parts covered by a delivery slip.
        :param slip_id:
        :return:
        """
        parts = session().query(DeliverySlipPart.quantity_out,
                                OrderPart.description,
                                Order.accounting_label.concat(func.coalesce(OrderPart.label,"-")).label("part_label")).\
            select_from(DeliverySlipPart).join(OrderPart).join(Order).filter(DeliverySlipPart.delivery_slip_id == slip_id).order_by(OrderPart.position).all()
        session().commit()
        return parts

        parts = session().query(DeliverySlipPart).join(OrderPart).filter(DeliverySlipPart.delivery_slip_id == slip_id).order_by(OrderPart.position).all()

        res = []
        for part in parts:
            fopart = freeze2(part.order_part)
            fpart = type("FrozenDeliverySlipPart", (object,), { 'quantity_out' : part.quantity_out, 'order_part' : fopart })
            res.append(fpart)

        session().commit()
        return res


    @RollbackDecorator
    def find_by_id(self,slip_id):
        if not slip_id:
            raise Exception("None id won't be found")

        return session().query(DeliverySlip).filter(DeliverySlip.delivery_slip_id == slip_id).one()



    @RollbackDecorator
    def find_last_slip_id(self):
        slip_id = session().query(DeliverySlip.delivery_slip_id).order_by(desc(DeliverySlip.delivery_slip_id)).first()
        session().commit()
        if slip_id:
            return slip_id[0]
        else:
            return None

    @RollbackDecorator
    def delete_last(self,slip_id):
        """ I give the id because when one says he wants to delete the last
        slip we show it to him first. So the user sees a particular slip.
        By passing the id here we ensure the last slip is the one the user
        has really seen.

        The idea is that if one tries to delete a slip which is not the last
        one, the *database* will raise an exception.
        """

        try:
            session().query(DeliverySlipPart).filter(DeliverySlipPart.delivery_slip_id == slip_id).delete()
            session().query(DeliverySlip).filter(DeliverySlip.delivery_slip_id == slip_id).delete()
            session().commit()
        except IntegrityError as ex:
            session().rollback()
            mainlog.exception(ex)
            raise DataException(_("I can't delete the delivery slip {} because it is not the last one.").format(slip_id))



    @RollbackDecorator
    def make_delivery_slip_for_order( self, order_id, parts_ids_quantities, creation_time, complete_order):
        """ parts_ids_quantities : a dict linking orderpartids to their quantities
        Returns the delivery slip id.
        """

        if not parts_ids_quantities:
            raise DataException("One can't create empty delivery slips")

        if not isinstance(creation_time, datetime):
            raise Exception("Expecting datetime, not {}".format(creation_time))

        if not creation_time:
            creation_time = central_clock.now()

        # Make several checks before going on

        # If one gives an order_part then there must be quantity for it

        for order_part_id,qty in parts_ids_quantities.items():
            assert order_part_id
            if qty <= 0:
                raise DataException("Invalid qty {} for order part id {}".format(qty,order_part_id))

        # Make sure all the quantities are compatible with the planned
        # quantities

        # mainlog.debug("make_delivery_slip_for_order: order_id = {}".format(order_id))

        data = session().query(OrderPart.order_part_id, OrderPart.state, OrderPart.tex2, OrderPart.qty,
                               OrderPart.sell_price)\
                        .filter(OrderPart.order_id == order_id).all()

        prices = dict()

        for order_part_id, state, qty_done, qty_planned,sell_price in data:
            if order_part_id in parts_ids_quantities:
                if qty_done + parts_ids_quantities[order_part_id] > qty_planned:
                    raise DataException("On order_part {}, qty currely done ({}) + new qty ({}) > qty planned {}".format(
                        order_part_id, qty_done, parts_ids_quantities[order_part_id], qty_planned))
                else:
                    prices[order_part_id] = sell_price

        # Make sure all order parts given to us do belong to the same order.

        db_orders_parts_id = list(map( lambda tupl:tupl[0], data))
        for k in parts_ids_quantities.keys():
            if k not in db_orders_parts_id:
                raise DataException("The order part id {} doesn't belong to order {}".format(k, order_id))

        # Everything is OK, so now we can create the delivery slip

        slip = DeliverySlip()
        session().add(slip)

        slip.creation = creation_time

        for order_part_id,qty in parts_ids_quantities.items():

            p = DeliverySlipPart()
            p.delivery_slip = slip
            p.quantity_out = qty
            p.sell_price = prices[order_part_id] * qty
            p.order_part_id = order_part_id

            session().add(p)

        mainlog.debug("Delivery slip created on {}".format(slip.creation))
        order_parts_ids = parts_ids_quantities.keys()

        # Now we change the states of all the parts that are
        # completed

        order = session().query(Order).filter( Order.order_id == order_id).one()

        if complete_order:
            # In this case, the user wants us to mark the order as fully completed
            # regardless of the completion of each parts.

            # dao.order_dao.change_order_state(order_id, OrderStatusType.order_completed,commit=False)
            business_computations_service.transition_order_state(
                order,
                OrderStatusType.order_completed)
        else:
            # For the query to work, the tex2 must have been updated
            # correctly... SQLA seems to do that (by flushin the delivery slip
            # above before doing the query below, I suppose, didin't verify)

            data = session().query(OrderPart)\
                            .filter( and_( OrderPart.state != OrderPartStateType.completed, # only completes something if it's not already completed
                                           OrderPart.qty > 0,
                                           OrderPart.tex2 >= OrderPart.qty,
                                           OrderPart.order_part_id.in_(order_parts_ids))).all()

            changes = dict( map( lambda tupl: (tupl,OrderPartStateType.completed),data))

            data = session().query(OrderPart)\
                            .filter( and_( OrderPart.state == OrderPartStateType.preorder,
                                           OrderPart.tex2 > 0,
                                           OrderPart.tex2 < OrderPart.qty, # this will work even if qty == 0
                                           OrderPart.order_part_id.in_(order_parts_ids))).all()

            changes.update( dict( map( lambda tupl: (tupl,OrderPartStateType.ready_for_production),data)))

            mainlog.debug("make_delivery_slip_for_order : not complete_order : {}".format(changes or "no state changes triggered "))

            # self.order_dao.change_several_order_parts_state(order_id, changes, False)
            business_computations_service.change_several_order_parts_state( order, changes)

        session().commit()

        return slip.delivery_slip_id



    @RollbackDecorator
    def deactivate(self,slip_id):
        session().query(DeliverySlip).filter(DeliverySlip.delivery_slip_id == slip_id).update({'active':False})
        audit_trail_service.record("DELIVERY_SLIP_DEACTIVATED",None, slip_id, commit=False)
        session().commit()

    @RollbackDecorator
    def activate(self,slip_id):
        session().query(DeliverySlip).filter(DeliverySlip.delivery_slip_id == slip_id).update({'active':True})
        audit_trail_service.record("DELIVERY_SLIP_DEACTIVATED",None, slip_id, commit=False)
        session().commit()

    @RollbackDecorator
    def save(self,parts,date_ds = None):
        # FIXME Deprecated ! Use make_delivery_slip_for_order instead


        """ Create a delivery slip out of its parts and save it in DB.
        You give a collection of parts, already connected connected to
        their order part.

        The slip is create on the date_ds. Thi is very important for
        accounting (delivery slips are, for example, tied to a monthly
        accounting). If date_ds is not given, then "now" is assumed.
        (the date_ds was added in the context of testing so one may not
        need to use it in regular use) """

        assert len(parts) >= 1 # No empty delivery slip

        # Pay attention, the slip numbers must be gapless
        # This is an accounting rule and it's enforced at the
        # database level (see DB mapping)

        slip = DeliverySlip()

        if date_ds:
            slip.creation = date_ds
        else:
            slip.creation = datetime.now()

        # Pay attention ! As we have already created some slip parts
        # and linked those parts to some order parts, SQLAlchemy
        # will try to persist the slip parts (because of the backref
        # relationship with the order parts). To prevent that, we had
        # to change the definition of the backref with cascade_backrefs=False

        session().add(slip)

        for p in parts:
            # The order_part relationship is already set up
            p.delivery_slip = slip
            session().add(p)

        session().commit()


        return slip

    MINIMUM_QUERY_LENGTH = 3
    MAXIMUM_QUERY_LENGTH = 200
    MAX_RESULTS = 200

    @RollbackDecorator
    def load_slip_parts_on_filter(self, query_string):

        columns= [DeliverySlip.delivery_slip_id,
                  DeliverySlip.creation,
                  DeliverySlip.active,
                  Customer.fullname,
                  Order.user_label]
        base_query = session().query(*columns).select_from(DeliverySlip).join(DeliverySlipPart).join(OrderPart).join(Order).join(Customer)

        res = []

        query_string = query_string.strip()

        if len(query_string) > DeliverySlipDAO.MAXIMUM_QUERY_LENGTH:
            raise DataException(DataException.CRITERIA_IS_TOO_LONG)

        chrono_start()

        if " " not in query_string.upper():
            # One word query

            query_string = query_string.upper()
            if OrderPart.re_order_part_identifier.match(query_string):
                order_part_id = dao.order_part_dao.find_by_full_id(query_string, commit=False)
                if order_part_id:
                    res = base_query.filter(OrderPart.order_part_id == order_part_id[0])

            elif OrderPart.re_label_identifier.match(query_string):
                res = base_query.filter(or_(Order.accounting_label == query_string, DeliverySlip.delivery_slip_id == int(query_string)))
            else:
                if len(query_string) < DeliverySlipDAO.MINIMUM_QUERY_LENGTH:
                    raise DataException(DataException.CRITERIA_IS_TOO_SHORT)

                # maybe a customer's name
                res = base_query.filter(Customer.indexed_fullname.like(u"%{}%".format(text_search_normalize(query_string))))

        else:
            res = base_query.filter(parse_delivery_slip_parts_query(query_string))

        # For info, given a simple filter (customer indexed name LIKE 'tac') this
        # query takes around 90ms in python (with db on localhost).
        # The actual SQL query run into PGAdmin takes around 40ms

        if res:
            res = res.distinct().limit(DeliverySlipDAO.MAX_RESULTS).all()
        session().commit()
        chrono_click("load_slip_parts_on_filter : query done")
        return res

    @RollbackDecorator
    def compute_billable_amount(self, ts_begin : datetime, ts_end : datetime):
        # Coalesce works because slip_part.sell_price is never null
        v = session().query(func.coalesce(func.sum(DeliverySlipPart.quantity_out * OrderPart.sell_price))).\
            select_from(DeliverySlipPart).\
            join(DeliverySlip,DeliverySlip.delivery_slip_id == DeliverySlipPart.delivery_slip_id).\
            join(OrderPart,OrderPart.order_part_id == DeliverySlipPart.order_part_id).\
            filter(and_(DeliverySlip.active,
                        DeliverySlip.creation.between(ts_begin, ts_end))).scalar()

        return float(v or 0)

    # @RollbackDecorator
    # def parts_for_activity_report(self, delivery_slip_id):
    #     res = session().query(DeliverySlipPart).join(OrderPart).filter(DeliverySlipPart.delivery_slip_id == delivery_slip_id).order_by(OrderPart.label).all()
    #
    #     from sqlalchemy.orm.session import make_transient
    #     for r in res:
    #         make_transient(r)
    #     session().commit()
    #     return res

# class UserDAO(object):
#     def __init__(self,session):
#         session() = session

#     @RollbackDecorator
#     def all(self):
#         return session().query(User).order_by(User.user_id).all()

#     @RollbackDecorator
#     def delete(self,user_id):
#         user = self.find_by_id(user_id)

#         if user is None:
#             raise ValueError("Missing a user")

#         session().delete(user)
#         session().commit()

#     @RollbackDecorator
#     def save(self,user):
#         if user not in session():
#             session().add(user)
#         session().commit()

#     @RollbackDecorator
#     def authenticate(self, identifier, password):
#         return len(session().query(User).filter(and_(User.user_id == identifier,User.password == password)).all()) == 1

#     @RollbackDecorator
#     def id_exists(self, identifier):
#         return len(session().query(User).filter(User.user_id == identifier).all()) > 0

#     @RollbackDecorator
#     def find_by_id(self,identifier):
#         return session().query(User).filter(User.user_id == identifier).one()


class DayTimeSynthesisDAO(object):
    def __init__(self,session):
        pass

    def presence(self, employee_id, d = None):
        if not d:
            d = date.today()

        t = session().query(func.sum(DayTimeSynthesis.presence_time)).\
            filter(and_(DayTimeSynthesis.employee_id == employee_id,
                        DayTimeSynthesis.day == d)).scalar() or 0

        session().commit()
        return t

    def monthly_presence(self,employee,year,month):
        """ Returns total number of presence hours on a given month for
        a given employee. Returns 0 if there's no presence at all.
        """

        day_max = calendar.monthrange(year,month)[1]
        d_start = date(year,month,1)
        d_end = date(year,month,day_max)

        return session().query(func.sum(DayTimeSynthesis.presence_time)).\
            filter(and_(DayTimeSynthesis.employee == employee,
                        DayTimeSynthesis.day.between(d_start,d_end))).scalar() or 0

    def save(self,employee_id,day,presence_time,off_time, commit=True):
        """ Store a presence in the database.

        If there's already a presence then it'll be replaced. """

        if type(day) != date:
            raise Exception("Expecting a date, got a {}".format(day))

        p = session().query(DayTimeSynthesis).filter(and_(DayTimeSynthesis.employee_id == employee_id,
                                                          DayTimeSynthesis.day == day)).all()

        if len(p) == 0:
            mainlog.debug("DayTimeSynthesisDAO.save() : creating a new day time synthesis")

            p = DayTimeSynthesis()
            p.employee_id = employee_id
            p.day = day
            p.presence_time = presence_time
            p.off_time = off_time
            session().add(p) # dependecy on employee !
        else:
            p = p[0]
            p.presence_time = presence_time
            p.off_time = off_time

            mainlog.debug("DayTimeSynthesisDAO.save() : updating day time synthesis duration={}, date={}".format(p.presence_time, p.day))

        if commit:
            session().commit()



class MonthTimeSynthesisDAO(object):
    def __init__(self,session):
        pass

    def load_all_synthesis(self,year,month):
        r = session().query(MonthTimeSynthesis).\
            options(joinedload(MonthTimeSynthesis.employee)).filter(and_(MonthTimeSynthesis.month == month,
                                                                         MonthTimeSynthesis.year == year)).all()
        session().commit()
        return r

    def load_correction_time(self,employee_id,year,month):
        r = session().query(MonthTimeSynthesis.correction_time).\
            filter(and_(MonthTimeSynthesis.employee_id == employee_id,
                        MonthTimeSynthesis.month == month,
                        MonthTimeSynthesis.year == year)).scalar()
        session().commit()
        return r or 0

    def save(self,employee_id,year,month,correction):
        p = session().query(MonthTimeSynthesis).filter(and_(MonthTimeSynthesis.employee_id == employee_id,
                                                            MonthTimeSynthesis.month == month,
                                                            MonthTimeSynthesis.year == year)).all()

        if len(p) == 0:
            p = MonthTimeSynthesis()
            session().add(p)
        else:
            mainlog.debug(u"MonthTimeSynthesisDAO.save() : Merging")
            p = p[0]

        p.employee_id = employee_id
        p.year = year
        p.month = month
        p.correction_time = correction
        mainlog.debug(u"MonthTimeSynthesisDAO.save() : storing {}".format(correction))
        session().commit()




class DAO(object):

    def __init__(self):
        pass

    @property
    def order_part_dao(self):
        return self._order_part_dao

    def set_session(self, scoped_session):
        """ session is function, when called it gives an actual
        session """

        self.customer_dao = CustomerDAO(scoped_session)
        self.employee_dao = EmployeeDAO(scoped_session)
        # self.user_dao = UserDAO(session)


        self._order_part_dao = OrderPartDAO(scoped_session)
        self.order_dao = OrderDAO(scoped_session,self._order_part_dao)
        self.delivery_slip_part_dao = DeliverySlipDAO(scoped_session, self.order_dao) # FIXME rename to delivery_slip_dao

        self._order_part_dao.set_delivery_slip_dao(self.delivery_slip_part_dao)

        self.production_file_dao = ProductionFileDAO(scoped_session,self._order_part_dao)

        self.day_time_synthesis_dao = DayTimeSynthesisDAO(scoped_session)
        self.month_time_synthesis_dao = MonthTimeSynthesisDAO(scoped_session)

        self.timetrack_dao = TimeTrackDAO(scoped_session)
        self.task_action_report_dao = TaskActionReportDAO(scoped_session,self.timetrack_dao,self.day_time_synthesis_dao)
        self.task_dao = TaskDAO(scoped_session,self.task_action_report_dao)

        # self.suppliers_dao = SuppliersDAO(session)
        self.operation_dao = OperationDAO(scoped_session)
        self.operation_definition_dao = OperationDefinitionDAO(self.operation_dao)


        self.special_activity_dao = SpecialActivityDAO()
        self.filters_dao = FilterQueryDAO()
        self.quality_dao = QualityDao()


    def close(self):
        session().close()

    def set_callback_operational_error(self,f):
        RollbackDecorator.callback_operational_error = [f]



#mainlog.info("Making dao")
dao = DAO()
# dao.set_session(session())

business_computations_service.set_dao(dao)
