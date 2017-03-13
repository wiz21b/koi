import re
from datetime import timedelta,date

from sqlalchemy.sql.expression import asc
from sqlalchemy.sql import and_

from koi.base_logging import mainlog
from koi.datalayer.database_session import session
from koi.db_mapping import TimeTrack, TaskOnOrder,TaskOnOperation,TaskOnNonBillable, Order, OrderPart, ProductionFile, Operation, OperationDefinition
from koi.dao import dao,RollbackDecorator
from koi.datalayer.types import DBObjectActionTypes
from koi.gui.dialog_utils import showWarningBox
from koi.gui.ProxyModel import TrackingProxyModel


class TaskOnOrderProxy(object):
    def __init__(self,task_id,description,order_id,operation_definition_id):
        self.task_id = task_id
        self.description = description
        self.order_id = order_id
        self.operation_definition_id = operation_definition_id

    def __repr__(self):
        return u"{} on order {}, operation:{}".format(self.description,self.order_id,self.operation_definition_id)

class TaskOnOperationProxy(object):
    def __init__(self,description,operation_id,opdef_id):
        # no, no task_id (that's because the machines...)
        self.description = description
        self.operation_id = operation_id
        self.operation_definition_id = opdef_id

    def __repr__(self):
        return u"{} on operation:{}".format(self.description,self.operation_id)


class TaskOnNonBillableProxy(object):
    def __init__(self,task_id,description,operation_definition_id):
        self.task_id = task_id
        self.description = description
        self.operation_definition_id = operation_definition_id

    def __repr__(self):
        return u"{} on operation:{}".format(self.description,self.operation_definition_id)


class TimetrackProxy(object):
    def __init__(self,timetrack = None):
        # timetrack is a timetrack

        if timetrack:
            self.timetrack_id = timetrack.timetrack_id
            self.duration = timetrack.duration
            self.managed_by_code = timetrack.managed_by_code
            self.start_time = timetrack.start_time

            if isinstance(timetrack.task,TaskOnOperation):
                self.task = TaskOnOperationProxy(timetrack.task.description,timetrack.task.operation_id, timetrack.task.operation.operation_definition_id)
                self.machine_id = timetrack.task.machine_id
            elif isinstance(timetrack.task,TaskOnNonBillable):
                self.task = TaskOnNonBillableProxy(timetrack.task.task_id,timetrack.task.description,timetrack.task.operation_definition_id)
                self.machine_id = None
            elif isinstance(timetrack.task,TaskOnOrder):
                self.task = TaskOnOrderProxy(timetrack.task.task_id,timetrack.task.description,timetrack.task.order_id,timetrack.task.operation_definition_id)
                self.machine_id = None
            else:
                self.task = None
                self.machine_id = None

        else:
            self.timetrack_id = None
            self.duration = None
            self.managed_by_code = None
            self.task = None
            self.start_time = None
            self.machine_id = None


    def __repr__(self):
        return u"id: {} mged_by_code: {} task: {}, machine_id: {}".format(self.timetrack_id, self.managed_by_code, self.task, self.machine_id)


class ImputableProxy(object):
    """ Provides a set of "imputable" stuff (operations ususally) provided
    an "idenitifer" which determines the parent of that stuff (e.g. an order
    part id : 1235BC)
    """

    def __init__(self,date):
        self.imputable_tasks = []
        self._date = date
        self._identifier = None

    @property
    def identifier(self):
        return self._identifier

    @RollbackDecorator
    def potential_imputable_task_for_order(self,order_accounting_label):
        mainlog.debug("potential_imputable_task_for_order : accouting label = {}".format(order_accounting_label))

        tasks = []

        order_id = session().query(Order.order_id).filter(Order.accounting_label == order_accounting_label).scalar()

        if order_id:
            mainlog.debug("order id = {}".format(order_id))
            q = session().query(OperationDefinition.operation_definition_id, OperationDefinition.description, TaskOnOrder.task_on_order_id).\
                outerjoin(TaskOnOrder,and_(TaskOnOrder.order_id == order_id,
                                           TaskOnOrder.operation_definition_id == OperationDefinition.operation_definition_id)).\
                filter( and_(OperationDefinition.on_order == True,
                             OperationDefinition.imputable == True)).\
                order_by(OperationDefinition.description)

            for opdef_id, opdef_desc, task_id in q.all():
                task = TaskOnOrderProxy(task_id, opdef_desc, order_id, opdef_id)
                tasks.append( task)
                mainlog.debug(task)

            return tasks
        else:
            return []


    @RollbackDecorator
    def potential_imputable_task_for_operation_definition(self):
        tasks = []
        for opdef_id, opdef_desc, task_id in session().query(OperationDefinition.operation_definition_id, OperationDefinition.description, TaskOnNonBillable.task_on_operation_definition_id).\
            outerjoin(TaskOnNonBillable).\
            filter( and_( OperationDefinition.imputable == True,
                          OperationDefinition.on_order == False,
                          OperationDefinition.on_operation == False)):

            task = TaskOnNonBillableProxy(task_id,opdef_desc,opdef_id)
            tasks.append( task)

        return tasks


    @RollbackDecorator
    def potential_imputable_operations_for_order_part(self, order_part_id):
        # This is a bit tricky. When we reach this point, we know we
        # want to record time on an operation of an order part. So we'll look for
        # the operations to actually report time.
        # But, in the case of operations, we record time on task
        # which are defined by an operation or an operation and a
        # machine id. In case there's a machine involved, then
        # we'll know which *task* to look for only when the
        # machine is known. And at this point, we don't.
        # So here, we don't look for task but simply for operation.



        # Grab all imputable operations for a given order part.

        q = session().query(Operation.operation_id,
                            Operation.position,
                            OperationDefinition.short_id,
                            OperationDefinition.operation_definition_id,
                            Operation.description).\
            join(ProductionFile).\
            join(OperationDefinition).\
            filter(and_(ProductionFile.order_part_id == order_part_id,
                        OperationDefinition.imputable == True,
                        OperationDefinition.on_operation == True)).\
            order_by(asc(Operation.position)).all()

        session().commit()

        # printquery(q)

        proxies = []
        for op_id, op_position, opdef_desc, opdef_id, op_desc in q:

            # FIXME Pay attention, an operation not always have an operation
            # model. I'll be able to have that once I have a much better
            # import code (one that merges double lines operations)

            # mainlog.debug("potential_imputable_task_for_order_part")

            proxies.append( TaskOnOperationProxy( "[{}-{}] {}".format(op_position, opdef_desc,  op_desc or ""), op_id, opdef_id))


        return proxies



    def set_on_identifier(self,identifier):

        order_re = re.compile("^([0-9]+)$") # FIXME use common regex
        orde_part_re = re.compile("^([0-9]+)([A-Za-z]+)$")

        m2 = order_re.match(identifier.upper())
        m = orde_part_re.match(identifier.upper())

        if m:
            order_label = int(m.groups()[0])
            part_label = m.groups()[1]
            order_part_id = session().query(OrderPart.order_part_id).join(Order).filter(Order.accounting_label == order_label).filter(OrderPart.label == part_label).scalar()

            if order_part_id:
                self.imputable_tasks = self.potential_imputable_operations_for_order_part(order_part_id)
                self._identifier = identifier.upper()
            else:
                # FIXME Or the order is not in production... Message not 100% clear
                showWarningBox(_("The order part {} does not exist !").format(identifier),"", None, "order_doesnt_exist")

        elif m2:
            order_label = int(m2.groups()[0])
            mainlog.debug("set_on_identifier, given accounting label : {}".format(order_label))
            order_id = session().query(Order.order_id).filter(Order.accounting_label == order_label).scalar()

            if order_id:
                self.imputable_tasks = self.potential_imputable_task_for_order(order_label)
                self._identifier = identifier.upper()
            else:
                # FIXME Or the order is not in production... Message not 100% clear
                showWarningBox(_("The order {} does not exist !").format(identifier),"", None, "order_doesnt_exist")


        elif identifier.strip() == "":

            self.imputable_tasks = self.potential_imputable_task_for_operation_definition()
            self._identifier = ""

        session().commit()



    def set_on_timetrack(self,timetrack):
        task = timetrack.task
        res = None

        if not task:
            res = None
            self._identifier = None

        elif isinstance(task,TaskOnOperation):

            # Locate TimeTrack imputation target data

            task_id, order_label, part_label, order_part_id = session().\
                                                              query(TaskOnOperation.task_id,
                                                                    Order.accounting_label,
                                                                    OrderPart.label,
                                                                    OrderPart.order_part_id).\
                                                              join(Operation).join(ProductionFile).join(OrderPart).join(Order).\
                                                              filter(TaskOnOperation.task_on_operation_id == timetrack.task_id).one()

            # Locate imputable tasks for that target

            tasks = self.potential_imputable_operations_for_order_part(order_part_id)

            if len(tasks) > 0:
                self._identifier = str(order_label) + part_label
                self.imputable_tasks = tasks

            return

        elif isinstance(task,TaskOnOrder):
            task_id,order_label = session().query(TaskOnOrder.task_id,Order.accounting_label).join(Order).filter(TaskOnOrder.task_on_order_id == timetrack.task_id).one()

            tasks = self.potential_imputable_task_for_order(order_label)

            if len(tasks) > 0:
                self._identifier = str(order_label)
                self.imputable_tasks = tasks

            return

        elif isinstance(task,TaskOnNonBillable):
            tasks =  self.potential_imputable_task_for_operation_definition()
            if len(tasks) > 0:
                self._identifier = ""
                self.imputable_tasks = tasks

        else:
            raise Exception("Unsupported type {} ".format(type(task)))


def make_task_on_proxy_timetrack(tt_proxy):

    if isinstance(tt_proxy.task, TaskOnOperationProxy):

        # The user wants an operation or operation-machine task.
        # We figure out which one.

        # The operation_id comes from the task because it is determined
        # with the ImputableProxy. The machine_id comes from the timetrack
        # proxy because it comes itself from the table (and each row of the
        # table is converted into a timetrack proxy)
        return dao.task_dao._get_task_for_operation_and_machine(tt_proxy.task.operation_id, tt_proxy.machine_id)

    elif isinstance(tt_proxy.task, TaskOnNonBillableProxy):

        return dao.task_dao._get_task_for_non_billable(tt_proxy.task.operation_definition_id)

    elif isinstance(tt_proxy.task, TaskOnOrderProxy):

        return dao.task_dao._get_task_for_order(tt_proxy.task.order_id, tt_proxy.task.operation_definition_id)

    else:
        raise Exception("Unsupported porxy in make_task_on_proxy")



@RollbackDecorator
def save_proxy_timetracks(original_proxy_tts, tt_start_time, employee_id, record_date = None):
    """ original_proxy_tts : a collection of ImputableProxy
    tt_time : the datetime where the timetracks happens
    employee_id : the employee to which the timetracks belong
    record_date : moment on which the timetracks are recorderd
    """

    record_date = record_date or date.today()

    # First we recompute the start time of all timetracks
    # to make sure they are all contiguous on the time
    # axis. We do this to produce a side effect. That side
    # effect is that if the user encodes 2 tasks with only
    # the duration in mind (he only has the duration in mind
    # because that's all he sees in the gui) then the
    # presence time must be the sum of the 2 durations
    # (that's what looks natural to the user). But because
    # of the way we compute the presence, all the timetracks
    # must be contiguous in time to have this "side" effect.
    # It's a side effect because we alter the information
    # of the timetracks periods to make sure the presence time
    # looks natural to the user. Normally these two things
    # should be independent.

    proxy_tts = [] # original_proxy_tts is immutable so I need to build a copy

    start_time = tt_start_time
    for i in range(len(original_proxy_tts)):
        action,proxy_tt,ndx = original_proxy_tts[i]
        if proxy_tt.start_time != start_time:
            proxy_tt.start_time = start_time
            # If we modify the time then the TT must be updated
            if action not in (DBObjectActionTypes.UNCHANGED,DBObjectActionTypes.TO_DELETE):
                action = DBObjectActionTypes.TO_UPDATE

        proxy_tts.append( (action,proxy_tt,ndx) )
        start_time = start_time + timedelta(days=0,seconds=int(proxy_tt.duration*3600.0))

    to_delete,to_create,to_update = TrackingProxyModel.filter_db_updates(proxy_tts)

    # mainlog.debug("To delete : ")
    # for tt in to_delete:
    #     mainlog.debug(tt)

    # mainlog.debug("To create : ")
    # for tt in to_create:
    #     mainlog.debug(tt)

    # mainlog.debug("To update : ")
    # for tt in to_update:
    #     mainlog.debug(tt)

    tasks_on_operations = dict()
    tasks_on_orders = dict()
    tasks_on_operation_definitions = dict()

    for proxy in to_create + to_update:

        task_id = make_task_on_proxy_timetrack(proxy)

        tt = None
        if proxy.timetrack_id:
            mainlog.debug("Loading timetrack")
            tt = session().query(TimeTrack).filter(TimeTrack.timetrack_id == proxy.timetrack_id).one()
        else:
            mainlog.debug("Creating timetrack task_id={}, start_time={}, duration={}".format(task_id,proxy.start_time,proxy.duration))
            tt = TimeTrack()
            tt.employee_id = employee_id
            session().add(tt)

        tt.duration = proxy.duration
        tt.encoding_date = record_date
        tt.managed_by_code = False
        tt.start_time = proxy.start_time
        tt.task_id = task_id

    for proxy in to_delete:
        if proxy.timetrack_id:
            session().query(TimeTrack).filter(TimeTrack.timetrack_id == proxy.timetrack_id).delete()

    session().flush()


    day = date(tt_start_time.year,tt_start_time.month,tt_start_time.day)
    dao.timetrack_dao._recompute_presence_on_timetracks(employee_id,day,
                                                        dao.timetrack_dao.all_work_for_employee_date_manual(employee_id,day))

    session().commit()

    return True
