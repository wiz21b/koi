import re
import sys
import traceback
from datetime import date, datetime, timedelta

from sqlalchemy import Table, Column, Integer, String, Float, MetaData, ForeignKey, Date, DateTime, Sequence, Boolean, LargeBinary, Binary, Index, Numeric
from sqlalchemy.orm import mapper, relationship, column_property, backref, deferred
from sqlalchemy.sql import select,func,and_,join
from sqlalchemy.schema import CreateTable,DropTable,CheckConstraint,UniqueConstraint
from sqlalchemy.orm.session import object_session
from sqlalchemy import event
from sqlalchemy.orm.properties import ColumnProperty
import sqlalchemy.types
from sqlalchemy.dialects.postgresql import TIMESTAMP,ARRAY
from sqlalchemy.sql.expression import desc,asc,func,between,case,text
from sqlalchemy.orm.collections import InstrumentedList

from koi.Configurator import configuration,mainlog
from koi.translators import text_search_normalize
from koi.datalayer.SQLAEnum import DeclEnum

from koi.datalayer.database_session import session
from koi.datalayer.letter_position import position_to_letters
from koi.datalayer.sqla_mapping_base import metadata,Base,DATABASE_SCHEMA,MoneyType
from koi.datalayer.gapless_sequence import gaplessseq
from koi.datalayer.employee_mapping import Employee
from koi.machine.machine_mapping import Machine


# sqlhandler = logging.FileHandler("sql.log",mode="w")
# sqllogger = logging.getLogger('sqlalchemy.engine')
# sqllogger.setLevel(logging.INFO)
# sqllogger.addHandler(sqlhandler)



id_generator = Sequence('id_generator', start=1000, metadata=metadata)
operation_definition_id_generator = Sequence('operation_definition_id_generator',start=10000, metadata=metadata)
order_id_generator = Sequence('order_id_generator',start=1, metadata=metadata)
order_accounting_id_generator = Sequence('order_accounting_id_generator',start=1, metadata=metadata)
preorder_id_generator = Sequence('preorder_id_generator',start=10000, metadata=metadata)



class OrderPartStateType(DeclEnum):
    # Start state
    preorder = 'preorder', _('Preorder')

    # Production states
    ready_for_production = 'in_production', _('In production')

    # Production stopped
    production_paused = 'on_hold', _('On hold')

    # Not conform = a fault has been detected in the process or in the result.
    # It may mean the part was returned from the delivery_slips and thus is marked as "failed". The order part
    # will stay in that state forever.
    # It may also mean that the part is internally marked as "failed". In that case, efforts
    # will be accomplished to bring the part in conformity. So, the part may go back
    # to a normal procution or completed state.

    non_conform = 'non_conform', _('Non conform')

    # End states
    completed = 'completed', _('Completed')
    aborted = 'aborted', _('Aborted')


class OrderStatusType(DeclEnum):

    preorder_definition = 'preorder_definition',_("Preorder definition")
    """ The preorder is being written. It is still studied and has not
    been sent to the customer for approval.
    """

    preorder_sent = 'preorder_sent',_("Preorder sent")
    """ The preorder has been written and was sent to the customer.
    We're now waiting for its approval.

    This state plays a role in the "preorders sent per month"
    (preorder_parts_value_chart) indicator.
    """

    order_definition = 'order_definition', _('Order definition')
    """ The preorder has been approved by the customer. Now
    we are transforming the preorder data into a proper order
    definition (an order definition that can be sent on the workfloor)
    """

    order_ready_for_production = 'order_ready_for_production', _('Order in production')
    """ The order writing is complete. The order production can start anytime
    now.
    """

    order_production_paused = 'order_production_paused',_('Order production on hold')

    order_completed = 'order_completed',_('Order completed')
    """ Order completed : the order is finished and was successfully delivered
    to the customer. A completed order doesn't mean that all work has
    been realized or all planned quantities have been delivered. It just
    means that the user has decided that no more work should be done
    on that order because it was successfuly processed.
    """

    order_aborted = 'order_aborted',_('Order aborted')
    """ An order is aborted when its processing is stopped before completion.
    That can occur for various reasons. For example, the customer
    doesn't want it anymore.
    """


class SpecialActivityType(DeclEnum):
    holidays = 'holidays', _('Holidays')
    partial_activity = 'partial_activity', _('Partial activity')
    unemployment = 'unemployment', _('Unemployment')
    sick_leave = 'sick_leave', _('Sick leave')
    other = 'other', _('Other')




class FilterQuery(Base):
    __tablename__ = 'filter_queries'

    ORDER_PARTS_OVERVIEW_FAMILY = "order_parts_overview"
    DELIVERY_SLIPS_FAMILY = 'delivery_slips'
    SUPPLIER_ORDER_SLIPS_FAMILY = 'supply_orders_overview'

    filter_query_id = Column('filter_query_id',Integer,autoincrement=True,nullable=False,primary_key=True)

    # Family of the query. Most of the time, all the filters related
    # to the same screen or set of data are in the same family
    family = Column(String,nullable=False)

    # Name of the query
    name = Column(String,nullable=False)

    # Code of the query, must be parsable
    query = Column(String,nullable=False)

    # When a filter is shared, every users can see it
    shared = Column(Boolean,nullable=False,default=False)

    # The employee who owns the query. An employee
    # can own several queries.
    owner_id = Column('owner_id', Integer, ForeignKey('employees.employee_id'),nullable=False)
    owner = relationship('Employee', backref=backref('filter_queries'), lazy='joined')

    # Each filters of a given owner must have a unique name
    __table_args__ = (UniqueConstraint(name, owner_id, family, name='fq_by_name'),)



class OperationDefinitionPeriod(Base):
    __tablename__ = 'operation_definition_periods'

    # We use a sepcific sequence generator to keep the ID's as low
    # as possible. This will help us with thte construction of the
    # operation definitions

    operation_definition_period_id = Column('operation_definition_period_id',Integer,operation_definition_id_generator,nullable=False,primary_key=True)


    def __eq__(self,p):
        return self.start_date == p.start_date and self.end_date == p.end_date and self.cost == p.cost
    def __ne__(self,p):
        return not self.__eq__(p)

    def __hash__(self):
        # I added the hash because I've added the __eq__. If I don't SQL
        # complain that this class is not hashable. That makes sense
        # when you read the doc of Python about __hash__. However
        # since the object of this class are mutable, python's doc advises
        # agains redefining the hash (for reasons that are not 100% clear to me)

        return hash(self.start_date) ^ hash(self.end_date) ^ hash(self.cost)

    start_date = Column('start_date',Date,nullable=False)
    """ start time is inclusive """

    end_date = Column('end_date',Date,nullable=True)
    """ end time is inclusive. A NULL end date means
    a period without an end """

    cost = Column('hourly_cost',MoneyType,nullable=False,default=0)
    """ Hourly cost for the parent operation during this period.
     The cost is a *cost*, it's not the value of the operation
     on the delivery_slips side, it's the cost of the operation for
     the company. This is important for the valuation of work. """


    operation_definition_id = Column('operation_definition_id', Integer,
                                     ForeignKey('operation_definitions.operation_definition_id'),nullable=False)

    # Pay attention, the order by is important because
    # in some parts of the program we rely on it.
    # Explicitely states "cascade delete" so that when one deletes
    # an operation, he also deletes all the attached periods.

    operation_definition = relationship('OperationDefinition',
                                        backref=backref('periods', cascade="all, delete, delete-orphan", order_by='OperationDefinitionPeriod.start_date',lazy='joined'))

    # FIXME Also need a no-overlap constraint (rather a
    # pre-insert trigger)

    # FIXME Also need a contraint saying that each opdef
    # has at least on period

    # Periods are either open (no end date) or at least a day long
    __table_args__ = (CheckConstraint( 'end_date is null or start_date < end_date',
                                       name='opdef_period_valid'),)
    # There are no 2 periods which start the same date
    # for a given operationdefinition
    UniqueConstraint(operation_definition_id, start_date, name='opdef_unique_start_date')


    def __repr__(self):
        return "OperationDefinitionPeriod on {} from {} to {}. Cost={}.".format(
            self.operation_definition_id, self.start_date, self.end_date, self.cost)

class OperationDefinition(Base):
    """ We define some standard operations that will be completed
    by the employees. Standard operations are canonical, they'll
    be used as shortcut for the definition of the actual operations.


    I decide this :

    - each order (and all the parts that define it) will be said
    to be given at a given point in time. This point in time
    corresponds to the moment the order was created.
    Any modification brought to that order will be evaluated
    at that point in time. So for example, if I change an
    OperationDefinition, I'll choose from an operation definition
    that was valid at the moment of the order creation
    (not the moment of the update)

    Corollary : it is not possible to have, in a single order,
    infporamtion that come from different period of time.
    (That simplifies the thing quite a bit ut I think it
    makes sense from the business point of view too)

    Corollary : there is not such thing as an history
    of modifications on an order (since everything is
    brought back to the creation time).

    Corollary : the creation time *must* be stored
    at the order level and that's the only place
    where it will stand.
    """

    __tablename__ = 'operation_definitions'

    # operation_definition_id = Column(Integer, autoincrement=True, primary_key=True,index=True)
    operation_definition_id = Column('operation_definition_id',Integer,id_generator,nullable=False,primary_key=True)

    short_id = Column(String,nullable=False)
    """ The short ID is used to identify an operation by people who
    are accustomed to the system. Instead of "Tournage", people
    sometimes prefer to use the "TO" abbreviation.

    Short id's are also a mean to identify a given operation definition.
    Therefore it must be unique. Consequently, renaming it can be
    tedious (we need to preserve the unique nature...). However, since
    the same operation definition can have several versions that are all
    stored here, then the uniqueness must be on (short_id,start_date) """


    # and some additional constraints
    # 1. start_date < end_date
    # 2. There's no two periods which overlaps

    description = Column('description', String)

    # Deprecated
    XXXcost = Column('hourly_cost',Float,nullable=False,default=0)
    """ Hourly cost for this operation """

    imputable=Column(Boolean(create_constraint=False),nullable=False)
    """ An operation definition denotes an operation that can
    be imputed or not (that is, active or not in the time
    recording). If its neither on_order or on_operation then
    it is indirect and non-billable; that is, one cannot send a bill to a
    customer for the work accomplished on it. It's a loss.
    """

    on_order=Column(Boolean(create_constraint=False),nullable=False)
    """ Defines if the operation can be applied at the order level.
    For example, "cleaning desk" is a taks that is not especially
    related to a precise operation but can be related to an
    order. It's a kind of "indirect" operation. """

    on_operation=Column(Boolean(create_constraint=False),nullable=False)
    """ Defines if the task can be associated to a specific
    operation in an order. For example, the "fraisage" operation.
    This is also called a "direct" operation. """

    @property
    def specification(self):
        return imputable, on_order, on_operation

    @specification.setter
    def specification(self,imputable, on_order, on_operation):
        self.imputable, self.on_order, self.on_operation = imputable, on_order, on_operation

    def cost(self,d):

        for p in self.periods:
            if (not p.end_date and d >= p.start_date) or \
                    (p.end_date and p.start_date <= d and d <= p.end_date):
                return p.cost

        return 0

        err = "The cost was requested on a date ({}) for which there's no valid period.".format(d)
        if len(self.periods) == 0:
            err += " And it appears there are no periods at all which is definitely wrong (id={}).".format(self.operation_definition_id)
        raise Exception(err)

    def __str__(self):
        if self.description:
            return self.description
        else:
            return u""

    def is_used(self):
        """ Tell if this operation definition is in use.
        This function can be used to check if one can delete an operation
        definition (before actually sending the SQL to do so, 'cos
        it might end up violating integrity contraints)
        """

        on_orders = object_session(self).query(TimeTrack).join(TaskOnOrder).filter(TaskOnOrder.operation_definition_id == self.operation_definition_id).count()
        if on_orders:
            return True

        # Pay attention, on_op also covers the case of timetracks on given
        # operations.
        on_op = object_session(self).query(Operation).filter(Operation.operation_definition_id == self.operation_definition_id).count()
        return on_op > 0

    def all_timetracks(self):
        q = select([func.sum(TimeTrack.__table__.c.duration)],
                   from_obj=Operation.__table__.join(tasks_operations).join(Task.__table__).join(TimeTrack.__table__)).\
                   where(self.operation_definition_id == Operation.operation_definition_id)
        # FIXME no return value ?

    def all_times(self):
        q = select([func.sum(TimeTrack.__table__.c.duration)],
                   from_obj=Operation.__table__.join(TaskOnOperation.__table__).join(Task.__table__).join(TimeTrack.__table__)).\
                   where(self.operation_definition_id == Operation.operation_definition_id)

        t = object_session(self).execute(q).fetchone()[0]
        if t:
            return float(t)
        else:
            return 0




class SpecialActivity(Base):
    __tablename__ = 'special_activities'

    special_activity_id = Column('special_activity_id',Integer,id_generator,primary_key=True)

    employee_id = Column('employee_id',Integer,ForeignKey('employees.employee_id'),nullable=False,index=True)
    reporter_id = Column('reporter_id',Integer,ForeignKey('employees.employee_id'),nullable=False,index=True)

    start_time = Column('start_time',TIMESTAMP,index=True,nullable=False)
    """ The moment on which the perdio starts. It will last for 'duration' hours """

    end_time = Column('end_time',TIMESTAMP,index=True,nullable=False)
    """ The moment on which the period ends. """

    encoding_date = Column('encoding_date',Date,nullable=False)

    activity_type = Column(SpecialActivityType.db_type(),default=SpecialActivityType.other,nullable=False)

    employee = relationship(Employee, primaryjoin=Employee.employee_id == employee_id)
    reporter = relationship(Employee, primaryjoin=Employee.employee_id == reporter_id)

    __table_args__ = (CheckConstraint( 'start_time < end_time',
                                       name='period_not_empty'),)

    def __repr__(self):
        return "employee_id:{}, from {} to {}".format(self.employee_id, self.start_time, self.end_time)


class TimeTrack(Base):
    """ Tracks how much time was spent on a given task and by whom.
    TimeTracks are either automatically generated from the
    TaskActionreports (managed_by_code) or directly entered by a user.
    The rule is that Koi always generates what it can. The user
    then enters additional TimeTracks to fix the hours of an
    employee. A managed_by_code TimeTrack cannot be removed/edited
    by the user.

    Since a fix can be to remove hours done, we'd allow negative
    duration in non-managed_by_code TimeTracks.
    """

    __tablename__ = 'timetracks'

    # timetrack_id = Column('timetrack_id',Integer,autoincrement=True,primary_key=True)
    timetrack_id = Column('timetrack_id',Integer,id_generator,primary_key=True)

    task_id = Column('task_id',Integer,ForeignKey('tasks.task_id'),nullable=False,index=True)
    employee_id = Column('employee_id',Integer,ForeignKey('employees.employee_id'),nullable=False,index=True)

    # machine_id = Column(Integer,ForeignKey('machines.resource_id'),nullable=True)
    # machine = relationship(Machine,lazy='select')
    """ A time track can be tied to a machine.
    We could use inheritance to make machine-timetracks and human-timetracks
    But that would imply we choose to say that a timetrack refer to a human only or
    to a machine only. Right now, we can refer to both simultaneously.
    """

    start_time = Column('start_time',TIMESTAMP,index=True)
    """ The moment on which the period starts. It will last for 'duration' hours """

    duration = Column('duration',Float,nullable=False,default=0)
    """ Duration of the work on the task, in hours """

    encoding_date = Column('encoding_date',Date)


    # ineffective = Column(Boolean(create_constraint=False),default=False,nullable=False)
    # """ Marked as ineffective means that Horse shall not
    # recreate this timetrack if it ever has to.
    # The user has decided that this timetrack (i.e. a work on a given
    # task for a given period, has no reason to exist)
    # """

    managed_by_code = Column('managed_by_code',Boolean(create_constraint=False),nullable=False,default=False) # FIXME Rename
    """ Indicates if this is managed by Horse or by the user.
    When managed by Horse, a timetrack is expected to be
    created/deleted/recreated by Horse only. """

    task = relationship('Task')
    employee = relationship(Employee)
    task_action_reports = relationship("TaskActionReport")


    def end_time(self):
        return self.start_time + timedelta(days=0,seconds=self.duration*3600.0)

    def __unicode__(self):
        return u"<TimeTrack {} taskid:{} employee_id:{} {}h, {} recorded:{} mged:{}>".format(self.timetrack_id, self.task_id, self.employee_id, self.duration, self.start_time, self.encoding_date, self.managed_by_code)

    def __repr__(self):     # must be unambiguous
        return self.__unicode__()



class Task(Base):
    """ A task is used by the pointage to know what the tracked
    time is about. If such a task exist, then it means : an ''employee'' may
    report time spent on a given ''operation''.

    Tasks are here to bridge between the time reporting world and the production
    planning world. In the time reporting world, one only knows
    about the time spent on tasks. But in the production world,
    each task is actually linked to an operation that is part
    of a production order.

    The bridge is realized in the inherited classes.

    Task allows us to handle the action reports of the users and
    the times they define (TimeTracks) independently of what is
    tracked.
    """


    __tablename__ = 'tasks'

    # We guard against race conditions (optimistic locking)
    # This is because tasks are exposed to employees and can
    # be modified while they're looking at them (for example
    # if the timeclock gets disconnected from the server for
    # a long time).

    version_id = Column(Integer) # See mapper configuration to understand this


    task_type = Column('task_type',String,nullable=False)

    __mapper_args__ = {'polymorphic_on': task_type,
                       'polymorphic_identity': 'task',
                       'version_id_col': version_id} # FIXME not a very good name

    # Autoincrment is effectless if the primary key is referenced by
    # a foreign key

    task_id = Column('task_id',Integer,id_generator,index=True,primary_key=True)

    # operation_id = Column('operation_id',ForeignKey('operations.operation_id'),unique=True)
    # employee_id = Column('employee_id',ForeignKey('employees.employee_id'))

    # description = Column('description',String)
    description = "This task's description must be redefined in concrete class"

    # True : one can report time on the task
    # False : one cannot
    # Defaults to True

    active = Column(Boolean(create_constraint=False),default=True,index=True,nullable=False)

    timetracks = relationship('TimeTrack',lazy='select')
    # never, ever with a cascade ('cos you could potentially bring back
    # thousands of row, e.g. for the "presence" task)
    # => 'select' as lazy loading strategy


    def __init__(self):
        self.active = True

    def __repr__(self):
        return self.description

    def total_time(self):
        d = 0
        for t in self.timetracks:
            d += t.duration
        return d


    @property
    def imputable(self):
        # FIXME Should be called "active"
        raise Exception("Must be defined in child class")



class TaskOnOperation(Task):
    __tablename__ = 'tasks_operations'
    __mapper_args__ = {'polymorphic_identity': 'task_on_operation'}

    task_on_operation_id = Column( 'task_id', Integer, ForeignKey('tasks.task_id'),nullable=False,primary_key=True)


    machine_id = Column(Integer,ForeignKey('machines.resource_id'),nullable=True)
    machine = relationship(Machine,lazy='select')

    # When a task is defined for an operation, then
    # this task must be reused => unique=True below
    operation_id = Column('operation_id',ForeignKey('operations.operation_id'),nullable=False)
    operation = relationship('Operation', lazy='joined',uselist=False)

    __table_args__ = (UniqueConstraint(operation_id, machine_id, name='unique_task_on_machine_and_operation'),)


    @property
    def imputable(self):
        return self.active and self.operation.operation_model and \
            self.operation.operation_model.imputable and \
            self.operation.operation_model.on_operation and \
            self.operation.production_file.order_part.order.imputable


    def __repr__(self):
        return u"TaskOnOperation: #{} {} on operation {}".format(self.task_on_operation_id, str(self.description),self.operation_id)


class Operation(Base):
    __tablename__ = 'operations'
    __table_args__ = (CheckConstraint( 'position > 0', name='position_one_based'),)

    operation_id = Column('operation_id',Integer,id_generator,primary_key=True,index=True)

    description = Column('description',String)
    value = Column('value',MoneyType,nullable=False,default=0)

    # Planned hours for that operation for *one* unit produced
    planned_hours = Column('planned_hours',Float,nullable=False,default=0) # in hours

    # FIXME Change this to extra hours, useful for fixing issues in production
    migrated_t_reel = Column('t_reel',Float,nullable=False,default=0) # Old stuff, result of migration ! in hours

    # operations are ordered : one must be completed after the
    # other (FIXME This is rather primitive)
    # The first operation must always have a position 1; then second 2;
    # the third 3; etc. (so 1-based, gapless sequence)

    position = Column('position',Integer,nullable=False,default=1)

    # Each operation is linked to a production_file
    production_file_id = Column('production_file_id', Integer, ForeignKey('production_files.production_file_id'),nullable=False,index=True)
    production_file = relationship('ProductionFile', lazy='joined')

    # An operation can be defined in terms of a model.
    # This is the link to such a model

    operation_definition_id = Column('operation_definition_id', Integer, ForeignKey('operation_definitions.operation_definition_id'),nullable=True)
    operation_model = relationship('OperationDefinition', lazy='joined')



    # task_id = Column('task_id', Integer, ForeignKey('tasks.task_id'))
    # task = relationship('Task',backref=backref('operation',uselist=False), lazy='joined') # each task can have one operation tied to it at most.

    # Pay attentiont to uselist, this assumes one to one relationship
    # between tasks and operations

    # task = relationship('Task',secondary='tasks_operations',
    #                     #backref=backref('operation',uselist=False),
    #                     lazy='select',uselist=False)

    # There are only tasks on operations tied to operations
    tasks = relationship('TaskOnOperation',
                        lazy='select',cascade="delete, delete-orphan")

    # description = operations_table.c.description

    # The assignee is the person expected to complete an operation.
    # It is not necessarily the one who'll complete/do it.
    # So this is rather an advice from the manager.
    assignee_id = Column('employee_id',ForeignKey('employees.employee_id'),nullable=True)
    assignee = relationship('Employee', uselist=False)


    # This one works... But doesn't mention the joins explicitely
    # total_hours = column_property(
    #     select( [func.sum(TimeTrack.duration)]).where(and_(TimeTrack.task_id == Task.task_id, Task.task_id == tasks_operations.c.task_id, tasks_operations.c.operation_id == operation_id)) )

    def cost(self):
        return self.value

    def __unicode__(self):
        d = self.planned_hours
        if not d:
            d = 0

        return u"<Operation [{}] #{} {} planned_hours:{} done hours:{} model:{}>".format(self.operation_id,self.position,self.description,float(d),float(self.done_hours or 0),self.operation_model) # .encode(sys.getdefaultencoding(),'ignore')














class ProductionFile(Base):
    # A production file defines the operations needed to complete
    # a part of an order (these at the operations that actually be
    # done by the employees)

    # As the operations really do track the work, they're the right
    # place to record times spent and other production indicators
    # (therefore we don't store that at the order level...)

    # FIXME So files are linked to orders

    __tablename__ = 'production_files'

    production_file_id = Column('production_file_id',Integer,autoincrement=True,primary_key=True)
    description = Column('description',String)
    date = Column('date',Date)
    order_part_id = Column('order_part_id',ForeignKey('order_parts.order_part_id'),nullable=False,index=True)

    quantity = Column(Integer)
    note = Column(String)

    operations = relationship('Operation',order_by='Operation.position',cascade="all, delete, delete-orphan, merge")
    order_part = relationship('OrderPart')



    def __repr__(self):
        return "<ProductionFile [{}] '{}' date='{}' {}>".format(self.production_file_id, self.description, self.date, self.operations)











# class OrderPartFlags(DeclEnum):
#     month_goal = 'month_goal',_("Month goal")

class OrderPart(Base):

    re_order_part_identifier = re.compile("^([0-9]{1,6})([A-Z]{1,4})$")
    re_label_identifier = re.compile("^[0-9]{1,6}$")

    __tablename__ = 'order_parts'

    order_part_id = Column('order_part_id',Integer,id_generator,primary_key=True)
    description = Column(String)
    indexed_description = Column(String)

    priority = Column(Integer, default=1, nullable = False)
    """ Priority for production. This is indicative. 1 means low
    priority, 5 means top priority.
    """

    qty = Column('quantity',Integer,default=0,nullable=False)
    """ Planned quantity to do """

    deadline  = Column('deadline',Date)

    # I want this to be the quantities done this month
    _dev = Column('dev',Float,default=0,nullable=False) # Hours planned
    _qex = Column('qex',Integer,default=0,nullable=False) # FIXME Can be removed
    _tex = Column('tex',Integer,default=0,nullable=False) # FIXME Move this to a special DeliverySlip
    _eff = Column("eff",Float,default=0,nullable=False) # Hours done

    label = Column('label',String,nullable=True)
    """ The label of this order part : A,B,C,..,AA,AB,...
    """

    position = Column('position',Integer,nullable=False)
    """ Position of this part relative to the other.
    There must not be two positions the same for a given
    Order. """

    UniqueConstraint('order_id','position',name='positions_are_strictly_ordered')

    notes = Column('notes',String,default="")
    """ Some notes about the order part, for the user's comfort. """

    # True = goal for month
    # Flags are set (True) or not set (False), there's no other possibility.
    flags = Column('flags',Boolean,default = False,server_default=text("false"), nullable = False)

    # Sell price for *one* unit
    sell_price = Column('sell_price', MoneyType,default=0,nullable=False)

    state = Column('state',OrderPartStateType.db_type(),default=OrderPartStateType.preorder,nullable=False,index=True)
    completed_date = Column('completed_date',Date,unique=False,nullable=True)

    order_id = Column('order_id',Integer,ForeignKey('orders.order_id'),nullable=False)

    # order = relationship('Order')
    # order = relationship('Order',backref=backref('parts',order_by='OrderPart.position',lazy="joined"))

    production_file = relationship('ProductionFile',cascade="delete,delete-orphan,merge")

    # I use a set because each document is associated only once to the order
    # part
    #documents = relationship(Document, secondary=documents_order_parts_table, collection_class=set, cascade="delete")

    # Periods are either open (no end date) or at least a day long
    __table_args__ = (CheckConstraint( 'priority in (1,2,3,4,5) ',
                                       name='valid_priority'),)

    @property
    def operations(self):
        if not self.production_file  or len(self.production_file) == 0:
            return []
        else:
            # For some reason, SQLAlchemy forgets about the order FIXME Maybe
            # there's an option in the mapper to sort ?
            return sorted(self.production_file[0].operations, key=lambda x:x.position)

    def has_operations(self):
        # mainlog.debug("has_operation prod file {}".format(id(self.production_file[0])))
        return self.production_file is not None and len(self.production_file) > 0 and self.production_file[0].operations is not None and len(self.production_file[0].operations) > 0

    @property
    def human_position(self):
        # FIXME This function should be deprecated and replaced by "label"

        ndx = 0
        for p in self.order.parts:

            has_operations = p.has_operations() # This variable to cache results

            if p == self and has_operations:
                return position_to_letters(ndx)
            elif p == self:
                return "-"
            elif has_operations:
                ndx += 1
        return "-"

    def __repr__(self):
        # return "{}".format(self.sell_price)
        return u"OrderPart #{} [{}] {} qty_ordrd={}(tex:{})  deadline:{} sell:{} completed:{} state:{} label:{}".format(
            self.position, self.order_part_id,self.description,self.qty, self._tex, self.deadline or '/',self.sell_price,self.completed_date or '/',self.state, self.label or '/')





TaskOnOperation.description = column_property(
    select([ "[" + OperationDefinition.__table__.c.short_id.concat( "] ").concat( func.coalesce(Operation.__table__.c.description,"")) ],\
           from_obj=Operation.__table__.join(OperationDefinition.__table__)).\
    where(TaskOnOperation.__table__.c.operation_id == Operation.__table__.c.operation_id).as_scalar())


class Order(Base):
    re_order_identifier = re.compile("^([0-9]{1,6})$")

    __tablename__ = 'orders'

    # The number given to this order by the customer
    customer_order_name = Column(String)
    indexed_customer_order_name = Column(String)

    customer_preorder_name = Column(String,default="")
    indexed_customer_preorder_name = Column(String)

    # Accounting label. Must be a gapless sequence !
    accounting_label = Column('accounting_label',Integer,nullable=True,unique=True)
    # Preorder label. Must be a gapless sequence !
    preorder_label = Column('preorder_label',Integer,nullable=True,unique=True)

    # __table_args__ = (CheckConstraint( '(accounting_label is not null and preorder_label is null and state != \'preorder_definition\') or (accounting_label is null and preorder_label is not null and state = \'preorder_definition\')',
    #                                    name='labels_properly_set'),) # the other must be null

    # The order number, given by the company
    # order_id = Column('order_id',Integer,autoincrement=True,primary_key=True)
    order_id = Column('order_id',Integer,order_id_generator,nullable=False,primary_key=True)


    description = Column(String)

    # A Note that appears on top of the last printed preorder.
    preorder_print_note = Column(String,default="")

    # A note that appears at the bottom of the last printed preorder.
    preorder_print_note_footer = Column(String, default="")

    customer_id = Column('customer_id',Integer,ForeignKey('customers.customer_id'),nullable=False)
    state = Column(OrderStatusType.db_type(), nullable=False)
    # XactiveX = Column('active',Boolean(create_constraint=False),default=False)


    @property
    def imputable(self):
        return self.state == OrderStatusType.order_ready_for_production

    creation_date = Column('creation_date',Date,unique=False,nullable=False) # FIXME Not a datetime but a date
    """ When the preorder was created. This defines which operations
    can be done in this order (and ultimately, the prices of those operations).
    """

    completed_date = Column('completed_date',Date,unique=False,nullable=True) # FIXME Not a datetime but a date
    """ When the order was closed (status = order_completed or order_aborted).
    Pay attention, although each OrderPart has its own deadline, there's a
    global completion date.
    """

    sent_as_preorder = Column('was_preorder_on', Date, nullable=True)
    """ If the order was sent as a preorder, then the date of the sending is set.
    This happens when transtionning to state "preorder_sent. But this can
    be cleared by a human (for example if the order was marked as preorder_sent
    erroneously.
    """

    # Be super careful here, there are automatic update mechanisms
    # at play here (esp. when we add parts to orders)

    parts = relationship('OrderPart',backref=backref('order',lazy="joined"),order_by='OrderPart.position', cascade="delete, delete-orphan")
    # parts = relationship('OrderPart',backref=backref('order',lazy="joined"),order_by='OrderPart.position', cascade="delete, delete-orphan")

    customer = relationship('Customer', lazy='joined')

    tasks = relationship('Task', secondary=DATABASE_SCHEMA + '.tasks_order_operation_definitions')
    """ The indirect tasks tied to this order"""


    @property
    def delivery_slip_parts(self):
        """ All the delivery slip lines of all the delivery slips
        related to this order """
        return object_session(self).query(DeliverySlipPart).\
            join(OrderPart).\
            join(Order).\
            filter(Order.order_id == self.order_id).order_by(OrderPart.label).all()

    def delivery_slips(self):
        return object_session(self).query(DeliverySlip).join(DeliverySlipPart).join(OrderPart).join(Order).filter(Order.order_id == self.order_id).order_by(DeliverySlip.creation).all()


    def __init__(self):
        self.description = ""
        self.state = OrderStatusType.preorder_definition
        self.creation_date = date.today()

    def __repr__(self):
        c = None
        if self.customer:
            c = self.customer.fullname
        return "<Order %s %s %s>" % (self.order_id,self.description,c)


    def total_sell_price(self):
        sell_price = 0
        for part in self.parts:
            sell_price += part.total_sell_price
        return sell_price

    @property
    def label(self):
        if self.accounting_label:
            return self.accounting_label
        else:
            return self.preorder_label


class TaskOnNonBillable(Task):
    __tablename__ = 'tasks_operation_definitions'
    __mapper_args__ = {'polymorphic_identity': 'task_on_non_billable'}

    task_on_operation_definition_id = Column( 'task_id', Integer, ForeignKey('tasks.task_id'),primary_key=True)

    # When a task is defined for an operation_defintion, then
    # this task must be reused => unique=True below

    operation_definition_id = Column( 'operation_definition_id', Integer, ForeignKey('operation_definitions.operation_definition_id'),unique=True,nullable=False)


    operation_definition = relationship('OperationDefinition', lazy='select',uselist=False)

    @property
    def description(self):
        return u"{}".format(self.operation_definition.description)

    @property
    def imputable(self):
        return  self.active and self.operation_definition.imputable


class TaskForPresenceType(DeclEnum):
    regular_time = 'regular_time',_("Regular time")
    unemployment_time = 'unemployment_time', _('Unemployment time')



class TaskForPresence(Task):
    """ There are :
    - regular time
    - unemployment time

    when regular time is a "stop", then all other tasks stop (for ex. the worker leaves the building and goes home)
    when unemployment time is a "start", then all othe tasks stop (but
    this should not happen, one muste first be sure he has finished
    all of his work before starting to be unemployed)

    Since the types are rather constraint, this table won't probably
    never be updated by the user.

    We count unemployment time here rather than in a non billable task
    because unemployment has no duration, no validity period.
    It is possible at any time. Morevoer, when one starts unemployment,
    one should close all the ongoing task. Since we'd like to do that
    automatically, we need a way to recognize that kind of task
    easily.
    """

    __tablename__ = 'presence_task'
    __mapper_args__ = {'polymorphic_identity': 'task_for_presence'}

    presence_task_id = Column( 'presence_task_id', Integer, ForeignKey('tasks.task_id'),primary_key=True)
    kind = Column(TaskForPresenceType.db_type(),default=TaskForPresenceType.regular_time,nullable=False,unique=True)

    @property
    def imputable(self):
        return True

    @property
    def description(self):
        return _("Presence")

    def __repr__(self):
        return "Generic TaskForPresence of type {} ".format(self.kind)




class TaskOnOrder(Task):
    __tablename__ = 'tasks_order_operation_definitions'
    __mapper_args__ = {'polymorphic_identity': 'task_on_order'}

    task_on_order_id = Column( 'task_id', Integer, ForeignKey('tasks.task_id'),primary_key=True)
    order_id = Column( 'order_id', Integer, ForeignKey('orders.order_id'))

    order = relationship('Order', lazy='select',uselist=False)

    operation_definition_id = Column('operation_definition_id', Integer, ForeignKey('operation_definitions.operation_definition_id'),nullable=False)
    operation_definition = relationship('OperationDefinition', lazy='select',uselist=False)

    # When a task is defined for an order and operation_defintion, then
    # this task must be reused

    UniqueConstraint('order_id','operation_definition_id',name='one_task_per_def')

    @property
    def description(self):
        return u"{} {}".format(self.order.accounting_label,self.operation_definition.description)

    @property
    def imputable(self):
        # BUG Should take a date into account ?

        # mainlog.debug("Imputable ?")
        # mainlog.debug("self.active {}".format(self.active))
        # mainlog.debug("self.operation_definition.imputable {}".format(self.operation_definition.imputable))
        # mainlog.debug("self.operation_definition.on_order {}".format(self.operation_definition.on_order))
        # mainlog.debug("self.order.imputable {}".format(self.order.imputable))

        return self.active and \
            self.operation_definition.imputable and \
            self.operation_definition.on_order and \
            self.order.imputable







class OfferPart(Base):
    __tablename__ = 'offer_parts'

    offer_part_id = Column('offer_part_id',Integer,autoincrement=True,primary_key=True)
    description = Column('description',String)
    price = Column('price',String)
    quantity = Column('quantity',String)
    offer_id = Column('offer_id', ForeignKey('offers.offer_id'))




class Offer(Base):

    """ An offer is an informal proposal made to a customer for various
    services """

    __tablename__ = 'offers'

    offer_id = Column('offer_id',Integer,autoincrement=True,primary_key=True)
    date = Column('date',Date)
    customer_id = Column('customer_id', ForeignKey('customers.customer_id'))

    parts = relationship(OfferPart)


class Customer(Base):
    __tablename__ = 'customers'

    # customer_id = Column(Integer,autoincrement=True,primary_key=True)
    customer_id = Column('customer_id',Integer,id_generator,nullable=False,primary_key=True)

    fullname = Column(String)

    indexed_fullname = Column(String)

    address1 = Column(String)
    address2 = Column(String)
    phone = Column(String)
    phone2 = Column(String)
    email = Column(String)
    country = Column(String)
    notes =  Column(String)
    fax = Column(String)

    orders = relationship(Order)
    offers = relationship(Offer)

    def __init__(self,fullname=None):
        self.fullname = fullname

    def __eq__(self,c):
        if not c:
            return False

        if self.customer_id and c.customer_id:
            return self.customer_id == c.customer_id
        else:
            return self.fullname == c.fullname

    def __neq__(self,c):
        return not (self == c)

    def __repr__(self):
        return self.fullname or "" # This because of strange coercion error in __repr__ and unicode and NoneType


class TaskActionReportType(DeclEnum):
    start_task = 'start_task',_("Task start ")
    stop_task = 'stop_task', _("Task stop")
    presence = 'presence', _("Presence")
    day_in = 'day_in', _("Day in")
    day_out = 'day_out', _("Day out")
    start_pause = 'start_pause', _("Pause start")
    start_unemployment = 'start_unemployment', _("Unemployment start")


class DayTimeSynthesis(Base):
    """ This gives a synthesis of various things for a given employee
    on a given day. For example, his total presence time.

    This table is a sort of a cache. It exists because computing the
    value it gives (for ex. the presence time) is a rather expensive
    operation (because we need to compute the intersection of several
    TimeTracks.
    """

    __tablename__ = 'day_time_synthesis'

    day_time_synthesis_id = Column('day_time_synthesis_id',Integer,id_generator,primary_key=True)

    employee_id = Column(Integer,ForeignKey('employees.employee_id'))
    employee = relationship(Employee)

    day = Column('day',Date,nullable=False)
    """ Day of the synthesis (a day, not a timestamp)"""

    presence_time = Column('presence_time',Float,nullable=False,default=0)
    """ Duration of the presence (we assume solid presence period), in hours """

    off_time = Column('off_time',Float,nullable=False,default=0)
    """ time spent outside presence time (for ex. in lunch), in hours """


    UniqueConstraint(employee_id, day, name='one_synthesis_per_day_per_employee')







class MonthTimeSynthesis(Base):
    __tablename__ = "month_time_report"

    month_time_report_id = Column('month_time_report_id',Integer,id_generator,primary_key=True)
    employee_id = Column(Integer,ForeignKey('employees.employee_id'))
    employee = relationship(Employee)

    month = Column('month',Integer,nullable=False,default=0)
    """ From 1 to 12 """

    year = Column('year',Integer,nullable=False,default=0)

    correction_time = Column('correction_time',Float,nullable=False,default=0)




class TaskActionReport(Base):
    """ A task action report represents an action reported
    on a task by somebody. It is part of the tracking system.
    It has three parts :

    - a kind : the kind of report. For example "task started", "task stopped"
    - the task : which describes what was achieved (for ex. a piece of metal was folded); usually tasks are described in the production file. The tasks are described in another table but we don't refer to the production file directly.
    - the :py:attr:`reporter` : the one (normally, an employee) who did the report.

    A rather advanced aggregatin of TaskActionReports defines one or more TimeTrack.
    Consequently, a TaskActionReport can be tied to zero or one timetrack.

    """

    __tablename__ = 'task_action_reports'

    # One must always report time after the event has happened
    # (event, just on that moment), but never after.

    __table_args__ = (CheckConstraint( "report_time >= time",
                                       name='cant_report_in_the_future'),)

    task_action_report_id = Column('task_action_report_id',Integer,id_generator,primary_key=True)

    reporter_id = Column(Integer,ForeignKey('employees.employee_id'),nullable=False)
    reporter = relationship(Employee) # I don't join because it makes it too heavy on TAR access (esp. during timetracks reconsicliation)
    """ The person who reported the timetrack, the one that the
    report belongs to (the one who said "I started on task X on Y").
    So for example, a worker (and not the adminstrator who fixed
    the time reporting of that worker) """

    origin_location = Column(String,nullable=False)
    """ The tracking system on which the time was reported. """

    task_id            = Column(Integer,ForeignKey('tasks.task_id'),nullable=False)
    task = relationship(Task,lazy='joined')
    """ The task associated to this task action report. All action report are
    linked to a task. Presence reports are tied to the presence task.  """

    # ForeignKeyConstraint(['timetrack_id', 'reporter_id'], ['timetracks.timetrack_id','timetracks.employee_id'])

    timetrack_id = Column(Integer,ForeignKey('timetracks.timetrack_id'),nullable=True)
    timetrack = relationship(TimeTrack,lazy='joined')
    """ TAR are tied to timetracks. If a TAR doesn't belong to a timetrack
    then
    """

    machine_id = Column(Integer,ForeignKey('machines.resource_id'),nullable=True)
    machine = relationship(Machine,lazy='select')
    """ A TAR can be tied to one machine. But not necessarily. Wen envision
    a situation where soemtimes an employee reports a given action on a given
    machine and sometimes, it just isn't necessary. We could enforce the tie
    to a machine in some cases, but there will always be task which are not
    tied to no machine at all.

    We tie to only one machine because an action, we think, can only be achieved
    with one machine. This is arbitrary. We can aswell imagine actions that
    involve two machines in parallel. But doing so will probably make time
    tracking harder (esp. TimeTrack hours accounting).

    FIXME The question of knowing if we allow a *stop* TAR to be tied to a specific
    machine is left out right now. That's because if we allow that then we allow
    indirectly the possibility of having timetracks for a given task AND machine.
    That is a tough question.

    """

    kind            = Column(TaskActionReportType.db_type(),nullable=False)
    """ The kind of report  """

    time            = Column(TIMESTAMP,nullable=False,index=True)
    """ The time at which this report is valid """

    report_time     = Column(TIMESTAMP,nullable=False)
    """ The time at wich the report was done. For example : on 12h12 (report_time)
    I report that  I have started a task on 10h00 (time) -- this happens when one
    forgets to report and fixes the situation afterwards.
    Report time is always >= the time reported (because I think that
    reporting time in the future is rather strange. See the constraint. """

    CREATED_STATUS = 1 # FIXME Change to enum
    DELETED_STATUS = 2

    # is_last         = Column(Boolean(create_constraint=False))
    # If true, then this report is the last one for the given task and reporter.

    status          = Column(Integer,nullable=False) # 1 = created, 2 = deleted (once deleted, forever deleted)
    """ The edit status of this report : created or modified.
    That's an embryo of modification mainlog.
    """

    processed       = Column(Boolean(create_constraint=False)) # Create constraint is here to tune SQLA for Postgresql
    """ True = this report has been processed (transformed into real work
    hours). False = it has not.
    """

    editor          = Column(String,nullable=True) # from uuid import getnode , getnode() FIXME Link to employee please
    """ In case somebody modified the report *after* it was reported,
    then this represents its identity.
    That's an embryo of modification log.
    """


    def validate(self):
        errors = []

        if self.editor is None or len(self.editor.strip()) == 0:
            errors.append(_("Editor can't be empty"))
        if len(errors) > 0:
            return errors

    # @validates('editor')
    # def validate_editor(self,key,editor):
    #     if editor is None or len(editor.strip()) == 0:
    #         raise Exception(_("The editor cannot be empty"))
    #     else:
    #         return editor

    def __repr__(self):
        return u"TaskActionReport #{} reporter:{} task_id:{} timetrack_id:{} kind:{} at {}; status={}".format(self.task_action_report_id, self.reporter,self.task_id,self.timetrack_id,self.kind,self.time,self.status)


class AccountingPeriodStart(Base):
    __tablename__ = 'accounting_period_start'
    accountin_period_start_id = Column('accounting_period_start_id',Integer, primary_key=True)

    start = Column('start', TIMESTAMP, nullable=False,unique=True,index=True)

class DeliverySlip(Base):
    __tablename__ = 'delivery_slip'

    # Pay attention, the slip numbers must be gapless
    # This is an accounting rule => extreme care !

    delivery_slip_id = Column('delivery_slip_id',Integer, default=gaplessseq('delivery_slip_id'), primary_key=True)

    # If inactive a delivery slip is counted nowhere

    active = Column(Boolean,nullable=False,default=True)

    # The creation time is the time when a user decided
    # to create a deliveryslip. The creation time is
    # super accurate in the context of monthly accounting.
    # That is, if the delivery slip is inside a given
    # month, then it will participate to the KPI
    # of that month, for example the turnover.

    # Pay attention, since the id's are ordered,
    # so must be the creation times. So timestamp accuracy
    # is necessary.

    # Actually it's more than that. id's and creation times must
    # have the same order.

    # FIXME find a DB constraint to enforce that (the current
    # unique constraint just ensure unicity but not ordering)
    # what we need is "A_id > B_id <=> A_creation > B_creation"

    creation = Column('creation', TIMESTAMP, nullable=False,unique=True,index=True)


    def __repr__(self):
        return "Active {}, creation:{}".format(self.active, self.creation)


class DeliverySlipPart(Base):
    """
    Delivery slip parts have no price information on them
    """
    __tablename__ = 'delivery_slip_parts'

    # There is no such thing as a delivery slip for a null/zero quantity.
    __table_args__ = (CheckConstraint( 'quantity_out > 0',name='delivery_slip_for_something'),)

    # frozen = Column(Boolean(create_constraint=False),nullable=False,default=False)

    delivery_slip_part_id = Column('delivery_slip_part_id',Integer,id_generator,nullable=False,primary_key=True)
    delivery_slip_id = Column('delivery_slip_id',Integer,ForeignKey('delivery_slip.delivery_slip_id'),nullable=False)

    order_part_id = Column('order_part_id',Integer,ForeignKey('order_parts.order_part_id'),nullable=False)
    quantity_out = Column('quantity_out',Integer,nullable=False)

    # Be careful with the delivery_slip_parts and the fact that we turn
    # off the cascading...  According to the documentation of SQL :
    # (in file:///C:/PORT-STC/opt/python/Doc/sqlalchemy/orm/session.html#unitofwork-cascades) :
    #    delete - This cascade indicates that when the parent object is marked for deletion, the related objects should also be marked for deletion.
    #    !!! Without this cascade present, SQLAlchemy will set the foreign key
    #    on a one-to-many relationship to NULL when the parent object is deleted. !!!
    #    When enabled, the row is instead deleted.

    # So in our case, if one destroys an order_part, then
    # the order_part_id field in this object will be set to NULL.
    # In practice, it's not much of a problemn since
    # we prevent DELETE of an order part if it has some delivery
    # slip connected to it. However, during the test, it might be
    # an issue because we clean up the database sometimes.

    order_part = relationship('OrderPart',backref=backref('delivery_slip_parts',cascade_backrefs=False),cascade_backrefs=False)
    delivery_slip = relationship('DeliverySlip',backref=backref('delivery_slip_parts',cascade="delete,delete-orphan"))

    def __repr__(self):
        return u"Quantity:{} for order_part_id:{}".format(self.quantity_out, self.order_part_id)


# Total material value
OrderPart.material_value = column_property(
    select([func.greatest(0,func.sum(Operation.__table__.c.value))],
           from_obj=ProductionFile.__table__.join(Operation.__table__)).\
        where(ProductionFile.__table__.c.order_part_id == OrderPart.__table__.c.order_part_id).as_scalar())

# All the hours done/worked on an order part
OrderPart.total_hours = column_property(
    select([func.greatest(0,func.sum(TimeTrack.__table__.c.duration))],
           from_obj=ProductionFile.__table__.join(Operation.__table__).join(TaskOnOperation.__table__).join(Task.__table__).join(TimeTrack.__table__)).\
        where(ProductionFile.__table__.c.order_part_id == OrderPart.__table__.c.order_part_id).as_scalar())


OrderPart.estimated_time_per_unit = column_property(
    select([func.greatest(0,func.sum(Operation.__table__.c.planned_hours))],
           from_obj=ProductionFile.__table__.join(Operation.__table__)).\
        where(ProductionFile.__table__.c.order_part_id == OrderPart.__table__.c.order_part_id).as_scalar())

OrderPart.total_estimated_time = column_property(
    select([OrderPart.qty * func.greatest(0,func.sum(Operation.__table__.c.planned_hours))],
           from_obj=ProductionFile.__table__.join(Operation.__table__)).\
        where(ProductionFile.__table__.c.order_part_id == OrderPart.__table__.c.order_part_id).as_scalar())


""" Total quantity delivered for a given order part so far. The delivered
quantity is computed on the sole basis of the delivery slips.
That is, independently of time -- for the whole order's history. """

OrderPart.tex2= column_property( # FIXME Rename total_delivered_quantity
    select([OrderPart._tex + func.greatest(0,func.sum(DeliverySlipPart.quantity_out))],
           from_obj=DeliverySlipPart.__table__.join(DeliverySlip.__table__)).\
        where(and_(DeliverySlip.active,
                   DeliverySlipPart.order_part_id == OrderPart.__table__.c.order_part_id)).correlate_except(DeliverySlipPart).as_scalar())


OrderPart.total_sell_price = column_property( OrderPart.sell_price * OrderPart.qty)

# No idea why i need to correalte_except... should read SQLA doc again
# The human idenitfier here has a meaning only if the OrderPart
# is part of the session... So when one edits a new (unsaved) order part,
# this will be None...

# Also, sorting on human_identifier is not easy because
# alphanumerical comparison in PostgreSQL is not applicable.

OrderPart.human_identifier = column_property(
    select([case([(Order.__table__.c.state == OrderStatusType.preorder_definition,
                   Order.__table__.c.preorder_label)],
                 else_=Order.__table__.c.accounting_label).\
            concat(func.coalesce(OrderPart.__table__.c.label,"-"))],
           from_obj=Order.__table__).\
    where(Order.__table__.c.order_id == OrderPart.__table__.c.order_id).\
    correlate_except(Order).\
    as_scalar())



# Double coalesce to account for :
#   1/ where there are NULL in the join,
#   2/ when the query brings no row back

Operation.done_hours = column_property(
    select([func.coalesce(func.sum(func.coalesce(TimeTrack.__table__.c.duration,0)),0)],
           from_obj=TaskOnOperation.__table__.join(Task.__table__).join(TimeTrack.__table__)).\
    where(Operation.operation_id == TaskOnOperation.__table__.c.operation_id))


# The following works only when selecting existing
# orders...

Order.user_label = column_property(case([(Order.__table__.c.state == OrderStatusType.preorder_definition,
                                          Order.__table__.c.preorder_label)],
                                        else_=Order.__table__.c.accounting_label))


def set_customer_indexed_fullname(target, value, oldvalue, initiator):
    if value:
        target.indexed_fullname = text_search_normalize(str(value))

event.listen(Customer.fullname, 'set', set_customer_indexed_fullname)

def set_indexed_customer_order_name(target, value, oldvalue, initiator):
    if value:
        target.indexed_customer_order_name = text_search_normalize(str(value))

event.listen(Order.customer_order_name, 'set', set_indexed_customer_order_name)

def set_indexed_customer_preorder_name(target, value, oldvalue, initiator):
    if value:
        target.indexed_customer_preorder_name = text_search_normalize(str(value))

event.listen(Order.customer_preorder_name, 'set', set_indexed_customer_preorder_name)

def set_indexed_description(target, value, oldvalue, initiator):
    if value:
        target.indexed_description = text_search_normalize(str(value))

event.listen(OrderPart.description, 'set', set_indexed_description)



Index('idx_col34', TaskOnOperation.__table__.c.task_id, TaskOnOperation.__table__.c.operation_id)
Index('ndx_employee_day',DayTimeSynthesis.employee_id,DayTimeSynthesis.day)
Index('idx_tar', TaskActionReport.reporter_id, TaskActionReport.task_id)
Index('idx_order_parts_order_id', OrderPart.__table__.c.order_id)



from sqlalchemy.inspection import inspect

def dto(klass):
    """ Builds a DTO based on a SQLA mapped class.
    """

    d = dict()
    # We pick the attributes, but not the SQLA relationships
    for attr_name in inspect(klass).column_attrs.keys():
        d[attr_name] = None
    return type("Frozen"+klass.__name__, (object,), d)()

def dto_to_mapped(dto,mapped):
    for attr_name in inspect(type(mapped)).column_attrs.keys():
        setattr(mapped, attr_name, getattr(dto, attr_name))


def freeze(session,obj):
    """ Creates a shallow copy of an SQLAlchemy object
    or a collection of SQLA objects. Shallow means
    we don't go into relationships.

    A commit is done at the end of the copy to end
    open transactions.

    The goal is to have an object that can be safely
    used outside the SQLAl. session. That is an object
    that will not trigger a session access when we
    access its attributes.
    """

    if not obj:
        return obj

    if type(obj) == list:
        lres = []

        for o in obj:

            #mainlog.debug("^^"*80)
            d = dict()
            # mainlog.debug(dir(obj))
            for a in filter(lambda s: s[0:2] != '__', dir(o)):
                v = getattr(o,a)
                if type(v) != InstrumentedList:
                    d[a] = v

            res = type("Frozen"+type(o).__name__, (object,), d)()
            lres.append(res)

        session.commit()
        return lres

    d = dict()
    # mainlog.debug(dir(obj))
    for a in filter(lambda s: s[0:2] != '__', dir(obj)):
        v = getattr(obj,a)
        if type(v) != InstrumentedList:
            d[a] = v

    res = type("Frozen"+type(obj).__name__, (object,), d)()

    session.commit() # FIXME That's too heavy no ? Release Postgres locks. Taht's the only way I've found so far

    return res



def _freeze(obj):
    if not obj:
        return obj

    d = dict()

    # Make sure I copy only attributes which are
    # visible to me and which are not relationships
    # FIXME What about hybrids ?

    for k,t in inspect(obj).mapper.attrs.items():
        if isinstance(t,ColumnProperty):
            d[k] = getattr(obj,k)

    # Problem with expunge is that it expunges the
    # object but maybe not its dependencies...
    # mainlog.debug(u"Expunging {}".format(obj))
    session().expunge(obj)

    frozen_obj = type("Frozen"+type(obj).__name__, (object,), d)()

    return frozen_obj


def freeze2(obj,commit = True):
    """ Creates a shallow copy of an SQLAlchemy object
    or a collection of SQLA objects. Shallow means
    we don't go into relationships.

    A commit can be done at the end of the copy to end
    an open transaction.

    FIXME The commit can be an issue with remotely called stuff.
    For example, findById(xxx). This will usually do
    a commit at the end of execution to close the session.
    But, if the result of the function is to be sent remotely, one might
    call freeze on it, which will reopen the session, evenually
    re-read the the object, then commit again when freeze() is done.
    That's basically 2 reads...

    The goal is to have an object that can be safely
    used outside the SQLAlchemy. session. That is an object
    that will not trigger a session access when we
    access its attributes.
    """

    frozen = None

    # The instrumented list part is to allow us to easily freeze
    # a relationship of an object : freeze(parent.children)

    if type(obj) == list or type(obj) == sqlalchemy.orm.collections.InstrumentedList:
        frozen = list(map(_freeze,obj))
    else:
        frozen = _freeze(obj)

    if commit:
        session().commit()

    return frozen


def defrost_into(obj, sqlaobj, fields_out = []):
    """ Shallowly copy some attributes of obj into
    the columns of sqlaobj. We try all the columns.
    We don't follow the relationships.
    """

    assert obj
    assert sqlaobj

    from sqlalchemy.orm import class_mapper,ColumnProperty
    fnames = [prop.key for prop in class_mapper(type(sqlaobj)).iterate_properties
              if isinstance(prop, ColumnProperty)]

    for f in fnames:
        if f not in fields_out:
            # mainlog.debug(u"defrost: setattr {} to {} {}".format(f,str(getattr(obj,f)), type(getattr(obj,f))))
            setattr(sqlaobj,f,getattr(obj,f))




def copy_fields_to_object(fields, obj):
    assert obj is not None, "copy_fields_to_object() : Can't work on empty object"
    assert fields is not None, "copy_fields_to_object() : Can't work on empty parameters"

    for field_name,new_attr in fields.items():
        try:
            # The following piece of code is rather tricky
            # and may still be riddled with bugs. It is
            # there to allow to set attributes which are
            # collections/SQLA relationships. The whole thing
            # is to transform the source data represented as
            # a python list into an InstrumentedList.
            # This is the culmination of an effort to handle
            # the fact that once SQLA has given you access
            # to an object, then all collections of that
            # object are represented as InstrumentedList
            # (no matter what you do : reset with a regular
            # list, with [], expunge, etc.). Therefore, if one tries
            # to update that InstrumentedList, SQLA automatically
            # tries to reload session objects tied to that
            # list. And I can't figure out how to prevent that.
            # This results in various synchronisation issues
            # between the states of objects of the old collection
            # and the new one.

            if type(getattr(obj,field_name)) == InstrumentedList:
                coll = getattr(c,field_name)
                for i in range(len(coll)):
                    coll[i] = session().merge(coll[i])

                for i in range(len(new_attr)):
                    new_attr[i] = session().merge(new_attr[i])

            # mainlog.debug("About to set {}".format(p.field))
            setattr(obj,field_name,new_attr)

        except Exception as e:
            session().rollback()
            mainlog.error("I can't set attribute '{}' of type {} with value : '{}' of type '{}'. The reason is :".format(field_name,type(getattr(obj,field_name)),new_attr,type(new_attr)))
            for l in traceback.format_tb(sys.exc_info()[2]):
                mainlog.error(l)

            mainlog.exception(e)
            raise e
