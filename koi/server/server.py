from datetime import datetime, timedelta

import sys
if sys.version[0] == '3':
    from xmlrpc.server import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler
    import xmlrpc.client as xmlrpclib
else:
    from SimpleXMLRPCServer import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler
    import xmlrpclib

from sqlalchemy.orm import lazyload
from sqlalchemy.sql.expression import desc
from sqlalchemy import and_
from sqlalchemy.exc import OperationalError

if __name__ == "__main__":
    from Configurator import load_configuration,init_i18n
    load_configuration("server.cfg","server_config_check.cfg")
    init_i18n()

from koi.BarCodeBase import BarCodeIdentifier

from koi.User import User
from koi.Task import TaskPointage
from koi.server import rpctools

from koi.tools.chrono import *

from koi.db_mapping import TaskOnNonBillable, TaskOnOrder,Task,TaskActionReport,TaskOnOperation, Operation, Order, OperationDefinition,TaskActionReportType, OrderPart, ProductionFile, Customer, OrderStatusType

from koi.datalayer.database_session import session
from koi.dao import DAO


# Restrict to a particular path.
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)


class ServerException(Exception):
    messages = {1000 : u"The task {} is not imputable",
                1001 : u"Unknown operation definition {} for non billable task",
                1002 : u"Operation definition {} is not imputable",
                1003 : u"The task {} for operation definition {} is not active",
                1004 : u"Unknown operation {} for on-operation task or operation is not imputable",
                1005 : u"Operation {} is not imputable *or* order part {} is not in production",
                1006 : u"Combination of operation definition {} for order {} doesn't exist",
                1007 : u"Combination of operation definition {} for order {} is not imputable",
                1008 : u"The task for operation definition {} on order {} is not active",
                1009 : u"There's no employee with id= {}",
                1010 : u"The barcode syntax is valid but I can't make sense of it : {}",
                1011 : u"Unable to record presence for employee_id : {}",
                1012 : u"The barcode syntax is incorrect {}",
                2000 : u"Operational error {}"}

    def __init__(self, code, *args):
        # *args is used to get a list of the parameters passed in
        self.code = code
        msg = self.messages[code]
        scode = "[{}] ".format(code)

        if msg.count('{}') > len(args):
            self.msg = msg
        else:
            self.msg = msg.format(*args)

        super(ServerException,self).__init__(scode + msg)



class ClockServer(object):
    def __init__(self,dao):
        self.dao = dao

    def getLastActionReport(self,task_id,employee_id):
        mainlog.info("getLastActionReport task:{} employee:{}".format(task_id,employee_id))
        try:
            reports = self.dao.task_action_report_dao.get_reports_for_task_employee(task_id, employee_id)
            if reports:
                return rpctools.sqla_to_hash(reports[-1])
            else:
                mainlog.debug("getLastActionReport : return None")
                return None

        except Exception as e:
            mainlog.exception(e)
            return None

    def _recordTaskOnNonBillable(self,operation_definition_id):
        mainlog.debug("_recordTaskOnNonBillable {}".format(operation_definition_id))

        q = session().query(OperationDefinition.operation_definition_id,
                            OperationDefinition.description,
                            OperationDefinition.imputable == True,
                            TaskOnNonBillable.active,
                            TaskOnNonBillable.task_id).outerjoin(TaskOnNonBillable).filter(OperationDefinition.operation_definition_id == operation_definition_id).options(lazyload('*'))

        row = q.first()

        if row is None:
            raise ServerException(1001,operation_definition_id)

        h = dict()
        h['task_type'] = 'TaskOnNonBillable'
        h['operation_definition_id'], h['description'], imputable, task_active, task_id = row

        if not imputable:
            raise ServerException(1002,operation_definition_id)

        if task_id is None:
            t = self.dao.task_dao.create_non_billable_task(operation_definition_id)
            task_id = t.task_id
        elif not task_active:
            raise ServerException(1003,task_id, operation_definition_id)

        return task_id, h


    def _recordTaskOnOrder(self,order_id,opdef_id):
        mainlog.debug("_recordTaskOnOrder {}".format(order_id))

        # Pay attention, this code is a double if you compare it
        # with the one from the DAO. I had to duplicate for
        # perforamnce reasons (SQLA loads too many things
        # when I sometimes just need an id)

        q = session().query(OperationDefinition.description,
                            and_( OperationDefinition.imputable == True, OperationDefinition.on_order == True, Order.state == OrderStatusType.order_ready_for_production),
                            TaskOnOrder.active,
                            TaskOnOrder.task_id).outerjoin(TaskOnOrder,
                                                           and_(TaskOnOrder.order_id == order_id, TaskOnOrder.operation_definition_id == opdef_id)).filter(and_(OperationDefinition.operation_definition_id == opdef_id, Order.order_id == order_id))

        row = q.first()
        mainlog.debug("query results {}".format(row))

        mainlog.debug("_recordTaskOnOrder")

        for o in session().query(OperationDefinition).all():
            mainlog.debug(o.operation_definition_id)
            mainlog.debug(o)

        for o in session().query(Order).all():
            mainlog.debug(o)

        if row is None:
            raise ServerException(1006,opdef_id,order_id)

        h = dict()
        h['order_id'] = order_id # FIXME Should be account/preorder rather than that
        h['description'], imputable, task_active, task_id = row
        h['task_type'] = 'TaskOnOrder'

        if not imputable:
            raise ServerException(1007,opdef_id,order_id)

        if task_id is None:
            t = self.dao.task_dao.create_task_on_order(order_id,opdef_id)
            task_id = t.task_id
        elif not task_active:
            raise ServerException(1008,opdef_id,order_id)

        return task_id, h


    def _recordTaskOnOperation(self,operation_id):
        mainlog.debug("_recordTaskOnOperation operation_id={}".format(operation_id))

        q = session().query(Operation.operation_id,
                            Order.accounting_label,
                            OrderPart.label,
                            OrderPart.description,
                            Customer.fullname,
                            OperationDefinition.short_id,
                            TaskOnOperation.task_id,
                            and_(OperationDefinition.imputable == True,
                                 OperationDefinition.on_operation == True,
                                 Order.state == OrderStatusType.order_ready_for_production),
                            TaskOnOperation.active,
                            Operation.description,
                            Operation.position)\
                     .join(ProductionFile).join(OrderPart).join(Order).outerjoin(TaskOnOperation,TaskOnOperation.operation_id == Operation.operation_id).join(OperationDefinition, OperationDefinition.operation_definition_id == Operation.operation_definition_id).join(Customer,Order.customer_id == Customer.customer_id).options(lazyload('*')).filter(Operation.operation_id == operation_id)

        row = q.first()

        if row is None:
            raise ServerException(1004,operation_id)

        mainlog.debug("_recordTaskOnOperation: query results {}".format(row))
        h = dict()
        h['task_type'] = 'TaskOnOperation'
        h['order_part_label'] = str(row[1]) + (row[2] or "-")
        h['order_part_description'] = row[3]
        h['customer_name'] = row[4]
        h['operation_definition'] = row[5]
        task_id = row[6]
        imputable = row[7]
        task_active = row[8]
        h['operation_description'] = row[9]
        h['operation_position'] = row[10]

        if imputable:
            if task_id is None:
                task_id = self.dao.task_dao.create_task_on_operation(operation_id).task_id

            elif not task_active:
                raise ServerException(1000,task_id)

            return task_id, h
        else:
            raise ServerException(1005,
                                  u"'{} {}'".format( (h['operation_definition'] or ""), (h['operation_description'] or "")),
                                  h['order_part_label'])


    def _barcodeToTask(self,barcode):
        data = None
        try:
            data = BarCodeIdentifier.barcode_to_id(barcode)
        except Exception as ex:
            raise ServerException(1012,barcode)

        if data[0] == Operation:
            operation_id = data[1]
            task_id, h = self._recordTaskOnOperation(operation_id)
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

            task_id = self.dao.task_action_report_dao.presence_task().task_id
            h = dict()
            h['task_type'] = 'TaskForPresence'
            h['action_kind'] = data[0]

            return task_id,h

        else:
            raise ServerException(1010,barcode)

    def _recordDayInAction(self,employee,action_time,location):
        t = self.dao.task_action_report_dao.presence_task()
        self.dao.task_action_report_dao.fast_create(t.task_id,employee,action_time,TaskActionReportType.day_in,location)

    def _recordDayOutAction(self,employee,action_time,location):
        t = self.dao.task_action_report_dao.presence_task()
        self.dao.task_action_report_dao.fast_create(t.task_id,employee,action_time,TaskActionReportType.day_out,location)

    def _recordActionOnWorkTask(self,task_id,employee,action_time,location):
            # We're going to use the last action report on the same task we're
            # working now to determine if the pointage is a task start or task stop

            # BUG For some reason if I only ask the action kind
            # the query returns no row at all...

            q = self.dao.session.query(TaskActionReport.task_action_report_id, TaskActionReport.kind).\
                filter(and_(TaskActionReport.task_id == task_id,
                            TaskActionReport.reporter == employee)).order_by(desc(TaskActionReport.time),desc(TaskActionReport.task_action_report_id))

            last_action_report = q.first()
            last_action_report_kind = None
            if last_action_report:
                # There is a last action report
                last_action_report_kind = last_action_report[1]

            # Who else works on the task ?
            # q = self.dao.session.query(TaskActionReport.task_action_report_id, TaskActionReport.reporter_id).filter(and_(TaskActionReport.task_id == task_id,TaskActionReport.reporter_id != employee_id)).order_by(desc(TaskActionReport.time),desc(TaskActionReport.task_action_report_id))

            # When pointage is on started task, then we *guess*
            # the intention of the user is to stop the task.
            # and vice versa...

            action_kind = TaskActionReportType.start_task

            if last_action_report_kind == TaskActionReportType.start_task:
                action_kind = TaskActionReportType.stop_task
            elif last_action_report_kind == TaskActionReportType.stop_task:
                action_kind = TaskActionReportType.start_task

            mainlog.debug("Constructing task action report on task {}".format(task_id))

            self.dao.task_action_report_dao.fast_create(task_id, employee,
                                                        action_time,
                                                        action_kind,location) # No commit

            session().commit()

            task_action_reports = self.dao.task_action_report_dao.get_reports_for_employee_on_date(employee,action_time.date())

            # if len(task_action_reports) > 0:
            #     mainlog.debug(u"_recordActionOnWorkTask : {}".format(task_action_reports[-1]))

            return action_kind



    def recordPointage(self,barcode,employee_id,action_time,location):
        mainlog.debug("Record pointage")

        try:
            action_time = datetime.strptime(str(action_time), "%Y%m%dT%H:%M:%S")

            # chrono_start()

            # Figure out the task information
            # Attention ! This will create a new tak if necessary

            task_id,h = self._barcodeToTask(barcode)

            mainlog.debug("Task id is {}".format(task_id))

            # chrono_click("_barcodeToTask")

            if not task_id:
                return None

            # FIXME That's sub optimal, we could use only the employee_id
            # however, this would change the dao layer in a way that we'd
            # use the id instead of the entity, which is less nice.

            employee = self.dao.employee_dao.find_by_id(employee_id)
            self.dao.session.commit()

            if h['task_type'] == 'TaskForPresence':
                if h['action_kind'] == TaskActionReportType.day_in:
                    self._recordDayInAction(employee,action_time,location)
                elif h['action_kind'] == TaskActionReportType.day_out:
                    self._recordDayOutAction(employee,action_time,location)
            else:
                h['action_kind'] =  self._recordActionOnWorkTask(task_id,employee,action_time,location)

            return h

        except ServerException as e:
            self.dao.session.rollback()
            mainlog.trace()
            raise xmlrpclib.Fault(e.code,e.msg)

        except Exception as e:
            self.dao.session.rollback()
            mainlog.trace()
            mainlog.exception(e)
            # msg = u"Problem while recording pointage : {}".format(e)
            msg = ""
            raise xmlrpclib.Fault(1000,msg)

    def usersInformation(self):
        users = []
        for employee in self.dao.employee_dao.all():
            print(employee.employee_id)
            u = User(employee.employee_id,employee.fullname)
            u.set_picture_bytes(employee.picture_bytes())
            users.append( u)

        # users = [ User(10,"Theo Champailler"), User(11,"Eva Champailler") ]
        return users

    def getTaskInformation(self,task_id):
        try:
            mainlog.debug("getTaskInformation, task id = {}".format(task_id))

            data = BarCodeIdentifier.barcode_to_id(task_id)


            if data[0] == Operation:
                operation_id = data[1]
                t = self.dao.task_dao.task_for_operation(operation_id)
            else:
                e = "Can't get that object, I don't recognize it"
                raise xmlrpclib.Fault(1000,e)

            return rpctools.sqla_to_hash(t)

        except Exception as e:
            mainlog.exception(e)
            e = "Task {} not found".format(task_id)
            mainlog.error(e)
            raise xmlrpclib.Fault(1000,e)

    def getTheStuff(self,employee_id):
        self.dao.session.query(Employee).join(TaskActionReport,TaskActionReport.employee_id == employee_id).join(Task, TaskActionReport.task_action_report_id == Task.task_id).filter(Employee.employee_id == employee_id)


    def getMoreTaskInformation(self,task_id):
        try:
            mainlog.debug("getMoreTaskInformation, task id = {}".format(task_id))
            t = self.dao.task_dao.find_by_id(task_id)

            if isinstance(t,TaskOnOperation):
                operation = t.operation

                employees_on_task = self.dao.task_dao.employees_on_task(t)

                h =  { 'task_type' : 'TaskOnOperation',
                       'description' :            operation.description,
                       'operation_definition' :   operation.operation_model.description,
                       'operation_definition_short' :   operation.operation_model.short_id,
                       'order_part_description' : operation.production_file.order_part.description,
                       'order_description' :      operation.production_file.order_part.order.description,
                       'order_part_id' :          operation.production_file.order_part.label,
                       'order_id' :               operation.production_file.order_part.order.label,
                       'customer_name' :          operation.production_file.order_part.order.customer.fullname,
                       'employees_on_task' :      map(lambda emp:emp.employee_id, employees_on_task)}
                mainlog.debug("getMoreTaskInformation, returning {}".format(h))
                session().commit()
                return h
            elif isinstance(t,TaskOnNonBillable):
                h =  { 'task_type' : 'TaskOnNonBillable',
                       'description' : t.operation_definition.description }
                session().commit()
                return h
            else:
                raise Exception("Unsupported task type")

        except Exception as e:
            mainlog.exception(e)
            return None


    def getOngoingTasksInformation(self,employee_id):
        try:
            mainlog.debug("getOngoingTasksInformation, employee id = {}".format(employee_id))

            employee = self.dao.employee_dao.find_by_id(employee_id)
            task_list = self.dao.task_dao.ongoing_tasks_for_employee(employee)
            r = rpctools.sqla_to_hash(task_list)
            mainlog.debug("getOngoingTasksInformation, about to return with : {}".format(r))
            self.dao.session.commit()

            return r
        except Exception as e:
            mainlog.exception(e)
            return None


    def recordPresence(self,employee_id,t,location):
        try:

            employee = self.dao.employee_dao.find_by_id(employee_id)
            self.dao.task_action_report_dao.create_presence_if_necessary( employee, t, location)
            return

        except OperationalError as e:
            raise ServerException(2000,employee_id,str(e))

        except Exception as e:
            raise ServerException(1011,employee_id)

    def get_employee_information(self, employee_id, location, start_date, end_date):
        try:
            u = self.dao.employee_dao.find_by_id_frozen(employee_id)
            acti = self.dao.employee_dao.find_activity(employee_id, start_date, end_date)
            return (u,acti)
        except OperationalError as e:
            raise ServerException(2000,user_id,str(e))

        except Exception as e:
            raise ServerException(1009,user_id)

    def getEmployeeInformation(self,user_id,location,ref_day):
        mainlog.info("getEmployeeInformation user_id = {}".format(user_id))

        try:
            chrono_click("getEmployeeInformation 1")
            u = self.dao.employee_dao.find_by_id(user_id)
            chrono_click("getEmployeeInformation 2")
            h = rpctools.sqla_to_hash(u)

            h['presence_day'],h['presence_begin'],h['presence_end'],h['presence_total'] = [],[],[],[]

            chrono_click("getEmployeeInformation 3")
            for i in range(4):
                d = ref_day + timedelta(-i)
                # Thus, most recent first...
                begin,end,total = self.dao.employee_dao.presence(user_id, d)
                h['presence_day'].append(d)
                h['presence_begin'].append(begin)
                h['presence_end'].append(end)
                h['presence_total'].append(total)

            self.dao.session.commit()
            chrono_click("getEmployeeInformation 4")
            return h

        except OperationalError as e:
            raise ServerException(2000,user_id,str(e))

        except Exception as e:
            raise ServerException(1009,user_id)


    def getTaskActionReports(self,task_id):
        mainlog.info("getTaskActionReports {}".format(task_id))
        r = self.dao.task_action_report_dao.get_reports_for_task(task_id)
        try:
            return rpctools.sqla_to_hash(r)
        except Exception as e:
            mainlog.exception(e)


    def tasksInformation(self):
        tasks = self.dao.task_dao.all_workable_tasks()
        server_tasks = []
        for t in tasks:
            # FIXME Potentially dangerous joins
            cust = t.operation.production_file.order_part.order.customer
            fullname = "NO CUSTOMER"
            if cust:
                fullname = cust.fullname

            server_tasks.append( TaskPointage(t.task_id,t.operation.description,fullname,t.operation.production_file.order_part.order.order_id,t.employee_id))

        #tasks = [ Task(20,"Verifier planeite","ALSTOM",10), Task(21,"Cubage 10x12","REGATA",11) ]
        return server_tasks


def all_systems_go():
    dao = DAO(session())
    instance = ClockServer(dao)

    server = SimpleXMLRPCServer(("localhost", 8080),
                            requestHandler=RequestHandler,logRequests=False,allow_none=True)
    server.register_introspection_functions()
    server.register_instance(instance)

    mainlog.info("The server is running")
    server.serve_forever()


if __name__ == "__main__":
    all_systems_go()
