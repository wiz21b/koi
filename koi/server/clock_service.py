from datetime import date,timedelta, datetime

from sqlalchemy.exc import OperationalError
from sqlalchemy import and_
from sqlalchemy.orm import lazyload

from koi.dao import dao
from koi.server.json_decorator import wrap_keyed_tuples, ServerErrors,ServerException, JsonCallable
from koi.tools.chrono import *
from koi.BarCodeBase import BarCodeIdentifier
from koi.db_mapping import Operation,Order,OrderPart,Customer,OperationDefinition,TaskOnOperation,TaskOnNonBillable,TaskOnOrder,OrderStatusType,ProductionFile, TaskActionReportType
from koi.machine.machine_service import machine_service
from koi.datalayer.database_session import session
from koi.datalayer.generic_access import DictAsObj


def person_data_encoder(person):

    person.roles = person._roles and person._roles.split(',')
    person.presence = wrap_keyed_tuples(person.presence_hours) # [h._asdict() for h in hours]

    # The following is a bit of a hack. For some reason I don't understand, on Python 2.7
    # picture data are seen as a 'str'. Therefore, when using the JSON encoder, it
    # tries to convert the 'str' to unicode, which fails (because there a rearbitrary bytes in it).
    # So I cheat the encoder a bit by wrapping the str in a memoryview. this way, the encoder
    # will see the memoryview and revert to the "default" encoder (the one we provide).
    # There we'll handle the bytes appropriately.

    if sys.version[0] == "2" and person.picture_data:
        # mainlog.debug("Python27 hack {}".format(type(d['picture_data'])))
        person.picture_data = memoryview(person.picture_data) # Python 2.7

    # mainlog.debug("person_data_encoder : type of picture_data = {}".format(type(d['picture_data'])))

    # I remove that because it's exposing security related stuff
    # that must remain private.
    person.password = None

    # Well, not needed anymore bacause we've made the roles entry
    person._roles = None

    # We return a keyedtuple so that it's deserialized as a.. keyedtuple !
    # (that is, as an objet with attributes instead of a regular dict.
    return person # {'__keyed_tuple__' : d}


class ClockService(object):
    def __init__(self):
        pass

    # @JSonServer([int])
    # def get_person_activity(self, employee_id):
    #     start_date = date.today() + timedelta(-365)
    #     end_date = start_date + timedelta(3)

    #     # 120 calls
    #     # JSON account for 1% of the performance
    #     # Interstingly, a blank call (with JSON serialize of a simple integer) takes 3.8 millisecs ! That's a lot for barely nothing.

    #     # empty 0.46s
    #     # query 6.17s
    #     # query+json 6.29s

    #     hours = dao.employee_dao.find_activity(employee_id,start_date, end_date)
    #     return 123


    # @JSonServer([int, date], person_data_encoder)

    @JsonCallable([int, date], person_data_encoder)
    def get_person_data(self, employee_id : int, start_date : date):
        """ Get a lot of information about a person :
        * person data (totally independent of the start_date)
        * presence hours per day (on a period of 4 days, sorted from the oldest
          to th emost recent)

        The data are given on a specific date. The data are collected
        over a period of 3 days before the given start date.

        WARNING : To make sure the presence information is correct,
        a presence TAR may have to be recorded before calling this.
        """

        # FIXME I think about adding the activity hours instead of the presence hours


        if not start_date:
            raise ServerException(ServerErrors.invalid_parameter, 'start_date')

        mainlog.debug("get_person_data {}".format(employee_id))
        # 120 calls
        # query+json 6.70s => 0.055s per call

        # start_date = date.today() + timedelta(-360)

        end_date = start_date
        start_date = end_date - timedelta(days=3)

        from koi.junkyard.services import services

        try:
            chrono_start()
            person = dao.employee_dao.find_by_id_frozen2(employee_id)
            # person = services.employees.find_by_id(employee_id)

            d = DictAsObj(person._asdict())
            d.password = None # Don't give the password away !

            chrono_click("clock_service : get_person_data - 1")

            activity_hours = dao.employee_dao.find_activity(employee_id, start_date, end_date)
            presence_hours = dao.employee_dao.find_person_presence_for_period(employee_id, start_date, end_date)
            # activity_hours = services.employees.find_activity(employee_id, start_date, end_date)
            # presence_hours = services.employees.find_person_presence_for_period(employee_id, start_date, end_date)

            chrono_click("clock_service : get_person_data - 2")
            mainlog.debug("get_person_data Done")

            d.activity_hours = activity_hours
            d.presence_hours = presence_hours

            return d

        except OperationalError as e:
            mainlog.debug("Raising Server exception")
            raise ServerException(ServerErrors.db_error, str(e))

        except Exception as e:
            mainlog.debug("Raising Server exception-2")
            mainlog.exception(e)
            raise ServerException(ServerErrors.unknown_employee_id, employee_id)


    #@JSonServer([int])
    @JsonCallable([int])
    def get_machine_data(self, machine_id : int):
        return machine_service.find_machine_by_id(machine_id)


    #@JSonServer([int, datetime])
    @JsonCallable([int, datetime])
    def get_ongoing_tasks(self,employee_id : int, time : datetime):
        """ Gives a "light" list of ongoing tasks on a moment 'time'
        for a given employee.

        Light means : without all the task details (i.e; the inheritied part)
        Obviously, only production task are returned, not presence tasks.
        """

        # If one wants the detail, then he'll call get_task_data
        # We assume that there are not many tasks, so this multi-call
        # approach is fine. FIXME That a "so so" argument, with JSON I
        # could easily mix tasks of various types (but I'd probably
        # stay with a SQL query per task type)

        try:
            mainlog.debug("get_ongoing_tasks, employee id = {}, time={}".format(employee_id,time))

            tasks_list = dao.task_dao.ongoing_tasks_for_employee(employee_id, time)

            return tasks_list
        except Exception as e:
            mainlog.exception(e)
            return None

    @JsonCallable([list])
    def get_multiple_tasks_data(self, task_id_list : list):

        tasks_data = dict()

        for task_id in task_id_list:

            t = dao.task_dao.find_by_id(task_id)

            # t can be anything, so I have to check its type to knwo whic fields
            # to use...

            if isinstance(t,TaskOnOperation):
                operation = t.operation

                employees_on_task = dao.task_dao.employees_on_task(t)

                h =  { 'task_type' :              'TaskOnOperation',
                       'description' :            operation.description,
                       'operation_id' :           operation.operation_id,
                       'operation_definition' :   operation.operation_model.description,
                       'operation_definition_short' :   operation.operation_model.short_id,
                       'order_part_description' : operation.production_file.order_part.description,
                       'order_description' :      operation.production_file.order_part.order.description,
                       'order_part_id' :          operation.production_file.order_part.label,
                       'order_id' :               operation.production_file.order_part.order.label,
                       'customer_name' :          operation.production_file.order_part.order.customer.fullname,
                       'employees_on_task' :      [emp.employee_id for emp in employees_on_task]}

            elif isinstance(t,TaskOnNonBillable):
                h =  { 'task_type' : 'TaskOnNonBillable',
                       'description' : t.operation_definition.description }

            elif isinstance(t,TaskOnOrder):
                h =  { 'task_type' : 'TaskOnOrder',
                       'order_id' : t.order_id,
                       'operation_definition_id' : t.operation_definition_id }

            else:
                raise Exception("getMoreTaskInformation : Unsupported task type {}".format(type(t)))

            # FIXME Move this into a specific encoder to have
            # a clean object

            tasks_data[task_id] = {'__keyed_tuple__' : h}

        session().commit()
        return tasks_data

    @JsonCallable([int])
    def get_task_data(self,task_id : int):
        try:
            # FIXME use _flatten in TaskDAO

            mainlog.debug("get_task_data, task id = {}".format(task_id))
            t = dao.task_dao.find_by_id(task_id)

            # t can be anything, so I have to check its type to knwo whic fields
            # to use...

            if isinstance(t,TaskOnOperation):
                operation = t.operation

                employees_on_task = dao.task_dao.employees_on_task(t)

                h =  { 'task_type' : 'TaskOnOperation',
                       'description' :            operation.description,
                       'position' :               operation.position,
                       'operation_id' :           operation.operation_id,
                       'operation_definition' :   operation.operation_model.description,
                       'operation_definition_short' :   operation.operation_model.short_id,
                       'order_part_description' : operation.production_file.order_part.description,
                       'order_description' :      operation.production_file.order_part.order.description,
                       'order_part_id' :          operation.production_file.order_part.label,
                       'order_id' :               operation.production_file.order_part.order.label,
                       'customer_name' :          operation.production_file.order_part.order.customer.fullname,
                       'employees_on_task' :      [emp.employee_id for emp in employees_on_task]
                }

                h['machine_id'] = t.machine_id
                if t.machine_id:
                    m = machine_service.find_machine_by_id(t.machine_id).fullname
                    h['machine_label'] = str(m)
                else:
                    h['machine_label'] = None

                mainlog.debug("get_task_data, returning {}".format(h))
                session().commit()
                return h

            elif isinstance(t,TaskOnNonBillable):
                h =  { 'task_type' : 'TaskOnNonBillable',
                       'description' : t.operation_definition.description }
                session().commit()
                return h
            else:
                raise Exception("getMoreTaskInformation : Unsupported task type")

        except Exception as e:
            mainlog.exception(e)
            return None


    # @JSonServer([int, datetime, str, TaskActionReportType])
    @JsonCallable([int, datetime, str, TaskActionReportType])
    def record_presence(self, employee_id :int , time : datetime, location : str, action : TaskActionReportType):

        if action in (TaskActionReportType.day_in, TaskActionReportType.day_out):

            presence_task_id = dao.task_action_report_dao.presence_task().task_id
            dao.task_action_report_dao.fast_create(presence_task_id, employee_id,
                                                   time, action, location) # No commit
            session().commit()

        elif action == TaskActionReportType.presence or not action:

            dao.task_action_report_dao.create_presence_if_necessary( employee_id, time, location)

        else:

            raise Exception("Invalid action type for presence, you gave '{}'.".format(action))



    @JsonCallable([int,int,datetime,str,TaskActionReportType,int])
    def record_pointage_on_operation(self,operation_id : int, employee_id : int,
                                     action_time : datetime, location : str,
                                     action_kind : TaskActionReportType,
                                     machine_id : int):

        # First, load the operation and figure out if a task is associated to the operation/machine.
        # self._figure_task_for_operation_and_machine(operation_id, machine_id)

        task_id = dao.task_dao._get_task_for_operation_and_machine(operation_id, machine_id)
        # Report time on the task
        self._recordActionOnWorkTask(task_id, employee_id, action_time, location, action_kind)


    @JsonCallable([int,int,int,datetime,str,TaskActionReportType])
    def record_pointage_on_order(self, order_id : int, operation_definition_id : int, employee_id : int,
                                 action_time : datetime, location : str, action_kind : TaskActionReportType):

        task_id = dao.task_dao._get_task_for_order(order_id, operation_definition_id)
        self._recordActionOnWorkTask(task_id, employee_id, action_time, location, action_kind)


    @JsonCallable([int,int,datetime,str,TaskActionReportType])
    def record_pointage_on_unbillable(self, operation_definition_id : int , employee_id : int,
                                      action_time : datetime, location : str, action_kind : TaskActionReportType):

        mainlog.debug("record_pointage_on_unbillable ")

        opdef = dao.operation_definition_dao.find_by_id_frozen(operation_definition_id, commit=False, resilient = True)

        if not opdef:
            raise ServerException( ServerErrors.operation_definition_unknown, operation_definition_id)
        elif not opdef.imputable:
            raise ServerException( ServerErrors.operation_definition_not_imputable, opdef.short_id)

        task_id = dao.task_dao._get_task_for_non_billable(operation_definition_id)
        self._recordActionOnWorkTask(task_id, employee_id, action_time, location, action_kind)



    def _recordActionOnWorkTask(self,task_id,employee_id,action_time,location,action_kind):
        # We're going to use the last action report on the same task we're
        # working now to determine if the pointage is a task start or task stop

        # BUG For some reason if I only ask the action kind
        # the query returns no row at all...

        # q = session().query(TaskActionReport.task_action_report_id, TaskActionReport.kind).\
        #     filter(and_(TaskActionReport.task_id == task_id,
        #                 TaskActionReport.reporter_id == employee_id)).\
        #     order_by(desc(TaskActionReport.time),desc(TaskActionReport.task_action_report_id))

        # last_action_report = q.first()
        # last_action_report_kind = None
        # if last_action_report:
        #     # There is a last action report
        #     last_action_report_kind = last_action_report.kind

        # Who else works on the task ?
        # q = self.dao.session.query(TaskActionReport.task_action_report_id, TaskActionReport.reporter_id).filter(and_(TaskActionReport.task_id == task_id,TaskActionReport.reporter_id != employee_id)).order_by(desc(TaskActionReport.time),desc(TaskActionReport.task_action_report_id))

        # When pointage is on started task, then we *guess*
        # the intention of the user is to stop the task.
        # and vice versa...

        # action_kind = TaskActionReportType.start_task

        # if last_action_report_kind == TaskActionReportType.start_task:
        #     action_kind = TaskActionReportType.stop_task
        # elif last_action_report_kind == TaskActionReportType.stop_task:
        #     action_kind = TaskActionReportType.start_task

        mainlog.debug("Constructing task action report on task {}".format(task_id))

        # At this point we know exactly what to record in the database
        # so we go to the fast track...
        # 1182

        assert task_id
        assert employee_id
        assert action_kind
        assert location

        dao.task_action_report_dao.fast_create(task_id, employee_id,
                                               action_time,
                                               action_kind,
                                               location) # No commit

        session().commit()

        # task_action_reports = self.dao.task_action_report_dao.get_reports_for_employee_on_date(employee,action_time.date())
        # if len(task_action_reports) > 0:
        #     mainlog.debug(u"_recordActionOnWorkTask : {}".format(task_action_reports[-1]))

        return action_kind



    def _figure_task_for_operation_and_machine(self, operation_id, machine_id):
        # FIXME Same as TaskDAO.get_task_for_operation_and_machine

        operation = self._load_operation_and_task_data(operation_id, machine_id)
        task_id = operation.task_id

        # Check if the pointage has to be recorded on a machine too.

        machine_ids = [m.machine_id for m in machine_service.find_machines_for_operation_definition(operation.operation_definition_id)]

        mainlog.debug("Authorized machine id's are : {}; you gave {}".format(machine_ids, machine_id))
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
            raise ServerException(ServerErrors.operation_non_imputable,
                                  u"'{} {}'".format( (operation.operation_definition_short_id or ""), (operation.operation_description or "")),
                                  str(operation.order_accounting_label) + (operation.order_part_label or '-'))

        return task_id


    def _load_operation_and_task_data(self, operation_id, machine_id):
        """ Load an operation and all its associated task_data
        The task data may not be there.
        """

        mainlog.debug("_load_operation_and_task_data")

        # We outer join on the tasks to majke sure to read the operation
        # even if there's no task.

        q = session().query(Operation.operation_id,
                            Order.accounting_label.label("order_accounting_label"),
                            OrderPart.label.label("order_part_label"),
                            OrderPart.description.label('order_part_description'),
                            Customer.fullname.label('customer_name'),
                            OperationDefinition.operation_definition_id,
                            OperationDefinition.short_id.label("operation_definition_short_id"),
                            Operation.description.label("operation_description"),
                            Operation.position.label("operation_position"),
                            and_(OperationDefinition.imputable == True,
                                 OperationDefinition.on_operation == True,
                                 Order.state == OrderStatusType.order_ready_for_production).label("imputable"),
                            TaskOnOperation.task_id,
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
            filter( Operation.operation_id == operation_id) # None is for the outer join; "or" works, in [None, machine] doesn not.


        row = q.all()

        # We do a bit of result analysis to improve error reporting

        if len(row) > 1:
            raise Exception("_load_operation_and_task_data : Too many results")

        elif not row:

            c = session().query(Operation.operation_id,
                                OperationDefinition.imputable,
                                OperationDefinition.short_id.label("operation_definition_short_id"),
                                OperationDefinition.on_operation,
                                Order.accounting_label.label("order_accounting_label"),
                                OrderPart.label.label("order_part_label"),
                                OrderPart.state.label("order_part_state")).\
                join(ProductionFile).\
                join(OrderPart).\
                join(Order).\
                join(OperationDefinition, OperationDefinition.operation_definition_id == Operation.operation_definition_id).\
                filter(Operation.operation_id == operation_id).first()


            if not c:
                raise ServerException(ServerErrors.operation_unknown,operation_id)
            elif not c.imputable:
                raise ServerException(ServerErrors.operation_definition_not_imputable, c.operation_definition_short_id)
            elif c.order_part_state != OrderStatusType.order_ready_for_production:
                raise ServerException(ServerErrors.order_part_not_in_production_unknown, "{}{}".format(c.order_accounting_label,c.order_part_label))


        return row[0]


    def _analyse_operation_non_imputable(self, operation_id):
        c = session().query(Operation.operation_id,
                            OperationDefinition.imputable,
                            OperationDefinition.short_id.label("operation_definition_short_id"),
                            OperationDefinition.on_operation,
                            Order.accounting_label.label("order_accounting_label"),
                            OrderPart.label.label("order_part_label"),
                            OrderPart.state.label("order_part_state")).\
            join(ProductionFile).\
            join(OrderPart).\
            join(Order).\
            join(OperationDefinition, OperationDefinition.operation_definition_id == Operation.operation_definition_id).\
            filter(Operation.operation_id == operation_id).first()

        if not c:
            raise ServerException(ServerErrors.operation_unknown,operation_id)
        elif not c.imputable:
            raise ServerException(ServerErrors.operation_definition_not_imputable, c.operation_definition_short_id)
        elif c.order_part_state != OrderStatusType.order_ready_for_production:
            raise ServerException(ServerErrors.order_part_not_in_production_unknown, "{}{}".format(c.order_accounting_label,c.order_part_label or ""))
        else:
            raise ServerException(ServerErrors.general_failure, "This operation is imputable but I expectd it's not. Contact support !")


    @JsonCallable([int,int,datetime,str,TaskActionReportType])
    def record_pointage(self,barcode:int,employee_id:int,action_time:datetime,location:str,action_kind:TaskActionReportType):

        mainlog.debug("Record pointage {} {} {} {} {}".format(barcode,employee_id,action_time,location,action_kind))

        # action_time = datetime.strptime(str(action_time), "%Y%m%dT%H:%M:%S")

        # chrono_start()

        # Figure out the task information
        # Attention ! This will create a new task if necessary

        task_id,h = self._barcodeToTask(barcode)

        mainlog.debug("Task id is {}".format(task_id))

        # chrono_click("_barcodeToTask")

        if not task_id:
            return None

        # FIXME That's sub optimal, we could use only the employee_id
        # however, this would change the dao layer in a way that we'd
        # use the id instead of the entity, which is less nice.

        employee = dao.employee_dao.find_by_id(employee_id)

        if h['task_type'] == 'TaskForPresence':
            if h['action_kind'] == TaskActionReportType.day_in:
                self._recordDayInAction(employee,action_time,location)
            elif h['action_kind'] == TaskActionReportType.day_out:
                self._recordDayOutAction(employee,action_time,location)
        else:
            h['action_kind'] =  self._recordActionOnWorkTask(task_id,employee,action_time,location)

        return h


    @JsonCallable([int,int,int])
    def get_next_action_for_employee_operation_machine(self, employee_id : int, operation_id : int, machine_id : int):
        return dao.operation_dao.find_next_action_for_employee_operation_machine(employee_id, operation_id, machine_id)


    @JsonCallable([int, int])
    def get_operation_information(self, employee_id : int, operation_id : int):
        """ Retrieve information about an operation.
        The operation is meant to be imputable.

        Returns a tuple :
        * operation
        * machines : machines available for the operation
        * next_action (if it was computable)
        * colleagues : a list of person working on the operation

        FIXME That is a problem : if the operation is not imputable, one
        should still be able to report an "end of task" (but no "start task")
        """

        try:
            o,m,next_action_kind,colleagues = dao.operation_dao.find_by_operation_id_frozen(employee_id, operation_id)
        except Exception as ex:
            mainlog.exception(ex)
            raise ServerException( ServerErrors.operation_unknown, operation_id)

        if o.imputable:
            # Ouch! I have to convert the colleagues to an array of tuple
            # because the colleagues are represented in a dict with keys which
            # are integers. Unfortunately, json converts those key to strings...

            return o,m,next_action_kind,colleagues

        else:
            self._analyse_operation_non_imputable(operation_id)
            raise ServerException( ServerErrors.operation_non_imputable, operation_id, o.order_part_identifier)




    @JsonCallable([int, int])
    def get_operation_definition_information(self, employee_id : int, operation_definition_id : int):
        """ Retrieve information about an operation.
        The operation is meant to be imputable.

        FIXME That is a problem : if the operation is not imputable, one
        should still be able to report an "end of task" (bu not "start task")
        """

        opdef = dao.operation_definition_dao.find_by_id_frozen(operation_definition_id, commit=False, resilient = True)

        if not opdef:
            raise ServerException( ServerErrors.operation_definition_unknown, operation_definition_id)

        next_action_kind = dao.operation_definition_dao.find_next_action_for_employee_operation_definition(employee_id, operation_definition_id, at_time=datetime.now())
        session().commit()
        return opdef,next_action_kind


        # if not opdef.imputable
        # if opdef.imputable:
        #     return opdef,next_action_kind
        # else:
        #     self._analyse_operation_non_imputable(operation_id)
        #     raise ServerException( ServerErrors.operation_non_imputable, operation_id, o.order_part_identifier)





    def _barcodeToTask(self,barcode, additional_data):
        data = None
        try:
            data = BarCodeIdentifier.barcode_to_id(barcode)
        except Exception as ex:
            raise ServerException(ServerErrors.barcode_syntax_invalid, barcode)

        if data[0] == Operation:
            operation_id = data[1]
            machine_id = additional_data
            task_id, h = self._recordTaskOnOperation(operation_id, machine_id)
            return task_id, h

        elif data[0] == OperationDefinition:
            operation_definition_id = data[1]
            task_id, h = self._recordTaskOnNonBillable(operation_definition_id)
            return task_id, h

        elif data[0] == Order and data[1] == OperationDefinition:
            order_id = data[2]
            operation_definition_id = data[3]
            task_id, h = self._recordTaskOnOrder(order_id,operation_definition_id)
            # self.dao.task_dao.task_for_order(order_id,operation_definition_id)
            return task_id, h

        elif data[0] in (TaskActionReportType.day_in,TaskActionReportType.day_out):
            task_id = dao.task_action_report_dao.presence_task().task_id
            h = dict()
            h['task_type'] = 'TaskForPresence'
            h['action_kind'] = data[0]

            return task_id,h

        else:
            raise ServerException(ServerErrors.barcode_invalid, barcode)


    def _recordTaskOnOperation(self,operation_id, machine_id):
        """ Create a task for reporting time on a "task on operation"
        with machine_id and operation_id
        """

        mainlog.debug("*** "*100)
        mainlog.debug("_recordTaskOnOperation operation_id={}, machine_id={}".format(operation_id, machine_id))

        # First we locate the operation and check if one can record time on it.

        q = session().query(Operation.operation_id,
                            Order.accounting_label.label("order_accounting_label"),
                            OrderPart.label.label("order_part_label"),
                            OrderPart.description.label('order_part_description'),
                            Customer.fullname.label('customer_name'),
                            OperationDefinition.short_id.label("operation_definition_short_id"),
                            TaskOnOperation.task_id,
                            and_(OperationDefinition.imputable == True,
                                 OperationDefinition.on_operation == True,
                                 Order.state == OrderStatusType.order_ready_for_production).label("imputable"),
                            TaskOnOperation.active.label("task_active"),
                            Operation.description.label("operation_description"),
                            Operation.position.label("operation_position"))\
                     .join(ProductionFile).join(OrderPart).join(Order).outerjoin(TaskOnOperation,TaskOnOperation.operation_id == Operation.operation_id).join(OperationDefinition, OperationDefinition.operation_definition_id == Operation.operation_definition_id).join(Customer,Order.customer_id == Customer.customer_id).options(lazyload('*')).filter(Operation.operation_id == operation_id)

        row = q.first()

        if row is None:
            self._analyse_operation_non_imputable(operation_id)
            raise ServerException(ServerErrors.operation_non_imputable,operation_id)

        h = row._asdict() # SQLA KeyedTupe

        h['task_type'] = 'TaskOnOperation'
        h['order_part_label'] = str(row[1]) + (row[2] or "-")

        if row.imputable:
            task_id = row.task_id
            if task_id is None:
                task_id = dao.task_dao.create_task_on_operation(operation_id, machine_id).task_id

            elif not row.task_active:
                raise ServerException(ServerErrors.task_not_imputable,task_id)

            return task_id, h
        else:
            raise ServerException(ServerErrors.operation_non_imputable,
                                  u"'{} {}'".format( (row.operation_definition_short_id or ""), (row.operation_description or "")),
                                  str(row.order_accounting_label) + (row.order_part_label or '-'))
