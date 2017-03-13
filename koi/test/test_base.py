import gc
import hashlib
import unittest

from PySide.QtTest import QTest
from PySide.QtCore import QTimer,Slot, Qt

import sys

from koi.test.setup_test import init_test_database
import tempfile

# init_test_database()


# Monkey patch -- Done here to make sure it happens soon enough. Else, the import
# behaviour in pytest will prevail and we're screwed
import shutil
def upload_document_mock(path, progress_tracker=None, file_id = 0, post_url = ""):
    mainlog.debug("upload_document_mock : {}".format(post_url))
    uploaded_file = open(path,"rb")
    file_id = documents_service.save(int(file_id), uploaded_file, os.path.basename(path), "")
    uploaded_file.close()
    return file_id


def upload_template_document_mock(path, progress_tracker=None, file_id = 0, post_url = ""):
    mainlog.debug("upload_template_document_mock : {}".format(post_url))
    uploaded_file = open(path,"rb")

    if file_id:
        documents_service.replace_template(file_id, uploaded_file, os.path.basename(path))
    else:
        file_id = documents_service.save_template(uploaded_file, os.path.basename(path))

    uploaded_file.close()
    return file_id

def download_document_mock(doc_id, progress_tracker = None, destination = None):
    mainlog.debug("download_document_mock {}".format(destination))
    path = documents_service.path_to_file(doc_id)
    shutil.copy(path, destination)
    return

import koi.doc_manager.client_utils
koi.doc_manager.client_utils.upload_document = upload_document_mock
koi.doc_manager.client_utils.upload_template = upload_template_document_mock
koi.doc_manager.client_utils.download_document = download_document_mock
from koi.doc_manager.documents_service import documents_service
from koi.server.json_decorator import JsonCallWrapper


from koi.db_mapping import *
from koi.datalayer.audit_trail_mapping import AuditTrail
from koi.people_admin.people_admin_mapping import DayEvent

from koi.PotentialTasksCache import PotentialTasksCache
from koi.session.UserSession import user_session
from koi.charts.indicators_service import IndicatorsService

from koi.dao import *


class TestBase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        # In process so that the server is bypassed (or else
        # I have to run a server in parallel)
        cls.remote_documents_service = JsonCallWrapper(documents_service,JsonCallWrapper.IN_PROCESS_MODE)
        cls.remote_indicators_service = IndicatorsService()

        configuration.set('Programs','pdf_viewer',None)

        mainlog.debug("TestBase.setUpClass : init database")


        from koi.dao import dao, DAO
        init_test_database()

        cls.open_locks_on_startup = cls._count_open_locks()

        mainlog.debug("TestBase.setUpClass")
        cls.dao = DAO()
        cls.dao.set_session(session)
        dao.set_session(session)

        cls._operation_definition_dao = cls.dao.operation_definition_dao

        cls.dao_employee = cls.dao.employee_dao
        cls.tar_dao = cls.dao.task_action_report_dao
        cls.task_dao = cls.dao.task_dao
        cls.timetrack_dao = cls.dao.timetrack_dao
        cls.delivery_slip_dao = cls.dao.delivery_slip_part_dao
        cls.order_dao = cls.dao.order_dao
        cls.day_time_synthesis_dao = cls.dao.day_time_synthesis_dao
        cls.month_time_synthesis_dao = cls.dao.month_time_synthesis_dao
        cls._production_file_dao = cls.dao.production_file_dao
        cls.employee_dao = cls.dao.employee_dao


        cls._order_dao = cls.dao.order_dao
        cls._order_part_dao = cls.dao.order_part_dao
        cls._operation_dao = cls.dao.operation_dao
        cls._customer_dao = cls.dao.customer_dao

        cls.customer = cls._customer_dao.make(u"Si"+ chr(233) + u"mens")
        cls.customer.address1 = u"Square Niklaus Wirth"+ chr(233)
        cls.customer.country = u"Pakistan"+ chr(233)
        cls.customer.phone = u"+494 0412 32 32 6654"
        cls.customer.email = u"kernighan@google.com"

        cls._customer_dao.save(cls.customer)
        cls.customer_id = cls.customer.customer_id

        cls.opdef = cls._operation_definition_dao.make()
        cls.opdef.short_id = "Unbi"
        cls.opdef.description = u"Unbi" + chr(233)
        cls.opdef.imputable = True
        cls.opdef.on_order = False
        cls.opdef.on_operation = False

        period = OperationDefinitionPeriod()
        period.start_date, period.end_date = date(2010,1,1), None
        cls.opdef.periods.append(period)

        cls._operation_definition_dao.save(cls.opdef)

        cls.nonbillable_op = cls.opdef
        cls.nonbillable_op_id = cls.opdef.operation_definition_id


        cls.opdef2 = cls._operation_definition_dao.make()
        cls.opdef2.short_id = "Unbi2"
        cls.opdef2.description = u"Unbi2"+ chr(233)
        cls.opdef2.imputable = True
        cls.opdef2.on_order = False
        cls.opdef2.on_operation = False

        period = OperationDefinitionPeriod()
        period.start_date, period.end_date = date(2010,1,1), None
        cls.opdef2.periods.append(period)

        cls._operation_definition_dao.save(cls.opdef2)


        cls.not_imputable_opdef_on_order = cls._operation_definition_dao.make()
        cls.not_imputable_opdef_on_order.short_id = "OnOrder"
        cls.not_imputable_opdef_on_order.description = u"OnOrder (not imputable)" + chr(233)
        cls.not_imputable_opdef_on_order.imputable = False
        cls.not_imputable_opdef_on_order.on_order = True
        cls.not_imputable_opdef_on_order.on_operation = False

        period = OperationDefinitionPeriod()
        period.start_date, period.end_date = date(2010,1,1), None
        cls.not_imputable_opdef_on_order.periods.append(period)

        cls._operation_definition_dao.save(cls.not_imputable_opdef_on_order)

        cls.not_imputable_opdef_on_operation = cls._operation_definition_dao.make()
        cls.not_imputable_opdef_on_operation.short_id = "MA"
        cls.not_imputable_opdef_on_operation.description = u"OnOperation (not imputable)" + chr(233)
        cls.not_imputable_opdef_on_operation.imputable = False
        cls.not_imputable_opdef_on_operation.on_operation = True
        cls.not_imputable_opdef_on_operation.on_order = False
        period = OperationDefinitionPeriod()
        period.start_date = date(2010,1,1)
        period.cost = 63.3 # BUG Cost makes no sense for non imputable task or does it ?
        cls.not_imputable_opdef_on_operation.periods.append(period)

        cls._operation_definition_dao.save(cls.not_imputable_opdef_on_operation)

        session().flush()

        # A regular operation

        cls.opdef_op = cls._operation_definition_dao.make()
        cls.opdef_op.short_id = "TO"
        cls.opdef_op.description = u"Tournag" + chr(233)
        cls.opdef_op.imputable = True
        cls.opdef_op.on_order = False
        cls.opdef_op.on_operation = True

        period = OperationDefinitionPeriod()
        period.start_date = date(2010,1,1)
        period.cost = 63.3

        cls.dao.operation_definition_dao.add_period(period, cls.opdef_op)
        session().flush()

        cls.opdef_order = cls._operation_definition_dao.make()
        cls.opdef_order.short_id = "ZO"
        cls.opdef_order.description = u"Analyse order " + chr(233)
        cls.opdef_order.imputable = True
        cls.opdef_order.on_order = True
        cls.opdef_order.on_operation = False

        period = OperationDefinitionPeriod()
        period.start_date, period.end_date = date(2010,1,1), None
        cls.opdef_order.periods.append(period)

        cls._operation_definition_dao.save(cls.opdef_order)

        cls.employee = cls.dao_employee.create(u"Don d. Knuth"+ chr(233))
        cls.employee.login = "dk"

        h = hashlib.md5()
        h.update('kk'.encode('utf-8'))

        cls.employee.password = h.hexdigest()
        cls.employee_id = cls.employee.employee_id

        user_session.open(cls.employee)

        cls.reporter = cls.dao_employee.create(u"George Orwell")
        cls.reporter.login = "go"
        cls.reporter.password = h.hexdigest()
        cls.reporter_id = cls.reporter.employee_id

        # It's already in the basic database
        # fq = FilterQuery()
        # fq.family = "order_parts_overview"
        # fq.query = "CreationDate > 1/1/2016"
        # fq.owner_id = cls.employee_id
        # fq.name = "production"
        # f = cls.dao.filters_dao.save(fq)

        session().commit()

        mainlog.debug("***************************************************** CLASS INIT completed")
        cls.timer = QTimer()
        cls.timer_connected = False
        cls.dialog_to_click = []

    def fail_hook(self,type_ex,ex,tback):
        mainlog.exception(ex)
        mainlog.error(str(type(ex)))
        for l in traceback.format_tb(tback):
            mainlog.error(l)

        self.fail("Qt's exception trigger !")

    def setUp(self):
        from koi.machine.machine_service import machine_service
        from koi.doc_manager.documents_mapping import TemplateDocument,Document,documents_order_parts_table

        sys.excepthook = self.fail_hook

        # For some reasons I don't undersant, delteing Document is not
        # applied polymorphically, that is, applied to TemplateDocument as well...
        documents_order_parts_table.delete().execute() # FIXME That should work polymorphically
        session().query(TemplateDocument).delete()
        session().query(Document).delete()

        session().query(DayEvent).delete()
        session().query(TaskActionReport).delete()
        session().query(TimeTrack).delete()
        session().query(TaskOnNonBillable).delete()
        session().query(TaskOnOperation).delete()
        session().query(TaskOnOrder).delete()
        # session().query(TaskForPresence).delete()
        session().query(DayTimeSynthesis).delete()
        # db_mapping.session().query(Task).delete()
        session().query(DeliverySlipPart).delete()
        for ds in session().query(DeliverySlip).order_by(desc(DeliverySlip.delivery_slip_id)):
            session().delete(ds)

        session().query(Machine).delete()
        machine_service._reset_cache()


        self.customer = session().query(Customer).filter(Customer.customer_id == self.customer_id).one()
        self.opdef = session().query(OperationDefinition).filter(OperationDefinition.short_id == "Unbi").one()
        self.opdef_op = session().query(OperationDefinition).filter(OperationDefinition.short_id == "TO").one()
        self.opdef2 = session().query(OperationDefinition).filter(OperationDefinition.short_id == "Unbi2").one()

        self.not_imputable_opdef_on_operation = session().query(OperationDefinition).filter(OperationDefinition.short_id == "MA").one()

        self.nb_task = self.task_dao.create_non_billable_task(self.opdef.operation_definition_id)
        self.nb_task2 = self.task_dao.create_non_billable_task(self.opdef2.operation_definition_id)
        session().commit()

        self.presence_task = session().query(TaskForPresence).filter(TaskForPresence.kind == TaskForPresenceType.regular_time).one()
        self.unemployment_task = session().query(TaskForPresence).filter(TaskForPresence.kind == TaskForPresenceType.unemployment_time).one()

        self.timer.stop()
        self.dialog_to_click = []

        from koi.datalayer.query_parser import initialize_customer_cache
        initialize_customer_cache()

        mainlog.debug("***************************************************** TEST INIT completed")

    @classmethod
    def _clear_database_content(cls):
        """ Will clear everything but the 'constant' stuff like
        operation definitions.

        That's a rather atomic bomb.
        """

        session().query(DayEvent).delete()
        session().query(AuditTrail).delete()
        session().query(FilterQuery).delete()
        session().query(MonthTimeSynthesis).delete()
        session().query(TaskActionReport).delete()
        session().query(TimeTrack).delete()
        session().query(TaskOnNonBillable).delete()
        session().query(TaskOnOperation).delete()
        session().query(TaskOnOrder).delete()

        session().query(TaskForPresence).filter(TaskForPresence.kind != TaskForPresenceType.regular_time).filter(TaskForPresence.kind != TaskForPresenceType.unemployment_time).delete()

        session().query(DayTimeSynthesis).delete()
        session().query(DeliverySlipPart).delete()
        for ds in session().query(DeliverySlip).order_by(desc(DeliverySlip.delivery_slip_id)):
            session().delete(ds)
        # session().query(DeliverySlip).delete()
        session().query(Operation).delete()
        session().query(ProductionFile).delete()
        session().query(OrderPart).delete()

        for order in session().query(Order).order_by(desc(Order.accounting_label)).all():
            session().delete(order)

        session().query(Customer).filter(Customer.customer_id != cls.customer.customer_id).delete()

        # db_mapping.session().query(Task).delete()
        session().commit()


    def _employee(self):
        return session().query(Employee).filter(Employee.employee_id == self.employee_id).one()

    def _make_tar(self, kind, time, employee, task):
        tar = TaskActionReport()
        tar.kind = kind
        tar.time = time
        tar.origin_location = u"OFFICE"+ chr(233)
        tar.editor = u"Admin"+ chr(233)
        tar.reporter_id = employee.employee_id
        tar.task = task
        tar.report_time = datetime.today()
        tar.status = TaskActionReport.CREATED_STATUS
        tar.processed = False
        return tar

    @classmethod
    def _make_order_cls(cls):
        order = cls._order_dao.make(u"Test order"+chr(233),cls.customer)
        order.state = OrderStatusType.order_definition # OrderStatusType.order_ready_for_production
        cls._order_dao.save(order)

        order_part = cls._order_part_dao.make(order)
        order_part.description = u"Part 1" + chr(233)
        order_part.position = 1
        cls._order_part_dao.save(order_part)

        pf = cls._production_file_dao.make()
        pf.order_part = order_part
        order_part.production_file = [pf]
        session().add(pf)
        session().flush()

        operation = cls._operation_dao.make()
        operation.production_file = pf
        operation.description = u"operation desc" + chr(233)
        operation.operation_model = cls.opdef_op
        operation.planned_hours = 7
        session().add(operation)
        session().commit()

        return order

    @classmethod
    def _make_timetrack(cls,task_id,start_time,duration):
        tt = TimeTrack()
        tt.task_id = task_id
        tt.employee_id = cls.employee.employee_id
        tt.duration = duration
        tt.start_time = start_time
        tt.encoding_date = date.today()
        tt.managed_by_code = False
        return tt

    def _add_part_to_order(self, order):
        order_part = self._order_part_dao.make(order)
        order_part.description = "standard part description"
        order_part.position = len(order.parts) + 1
        self._order_part_dao.save(order_part)

        pf = self._production_file_dao.make()
        pf.order_part = order_part
        order_part.production_file = [pf]
        session().add(pf)
        session().flush()

        operation = self._operation_dao.make()
        operation.production_file = pf
        operation.description = u"operation desc" + chr(233)
        operation.operation_model = self.opdef_op
        operation.planned_hours = 7
        session().add(operation)

        self._order_dao.recompute_position_labels(order)

        session().commit()

        return order_part

    def _make_order(self):
        order = self._order_dao.make(u"Test order"+chr(233),self.customer)
        order.state = OrderStatusType.order_definition # OrderStatusType.order_ready_for_production
        self._order_dao.save(order)

        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 1" + chr(233)
        order_part.position = 1
        self._order_part_dao.save(order_part)

        pf = self._production_file_dao.make()
        pf.order_part = order_part
        order_part.production_file = [pf]
        session().add(pf)
        session().flush()

        operation = self._operation_dao.make()
        operation.production_file = pf
        operation.description = u"operation desc" + chr(233)
        operation.operation_model = self.opdef_op
        operation.planned_hours = 7
        session().add(operation)

        self._order_dao.recompute_position_labels(order)

        session().commit()

        return order

    @classmethod
    def _make_machine(cls, name, operation_definition_id):
        """ Make a machine and tie it to the given operation defintion (which
        can be None)
        """

        from koi.machine.machine_service import machine_service

        m = Machine()
        m.fullname = name
        m.is_active = True
        m.operation_definition_id = operation_definition_id
        session().add(m)
        session().commit()
        machine_service._reset_cache()
        return m


    @classmethod
    def _count_open_locks(self):
        q = "select count(*) from pg_locks"
        return session().connection().execute(q).scalar()


    def _pg_locks(self,txt = ""):

        gc.collect()
        gc.collect()
        gc.collect()

        new_locks = self._count_open_locks() - self.open_locks_on_startup

        s = ""
        if new_locks > 2:
            # mainlog.debug("!!!" * 150)
            s = "!!! {} !!! {} at startup".format(new_locks,self.open_locks_on_startup)

            q = "select pg_locks.pid,pg_locks.relation,pg_class.relname from pg_locks join pg_class on pg_class.oid = pg_locks.relation;"
            for line in session().connection().execute(q):
                print(line)

        else:
            # mainlog.debug("....." * 150)
            s = str(new_locks)

        if txt:
            s += " at " + txt

        mainlog.debug("PG_LOCKS  : " + s)
        return new_locks

    def assertEqualEpsilon(self,a,b,eps=0.0001):
        if type(a) == tuple:
            for aa,bb in zip(a,b):
                self.assertEqualEpsilon(aa,bb,eps)
        else:
            # Casting to float because we can receive decimals...
            delta = float(a) - float(b)
            if delta*delta > eps*eps:
                self.fail("{} ~!= {}".format(a,b))

    @classmethod
    def show_timetracking(cls):

        mainlog.debug(u"TimeTrack on Operations:")
        for tt in session().query(TimeTrack).join(TaskOnOperation).all():
            mainlog.debug(u"  > {}".format(tt))

        mainlog.debug(u"TimeTrack on presence :")
        for tt in session().query(TimeTrack).join(TaskForPresence).all():
            mainlog.debug(u"  > {}".format(tt))

    @classmethod
    def show_order(cls,order):
        mainlog.debug(u"Order [{}]: {} accounting label:{} state:{}".format(order.order_id, order.description, order.accounting_label,order.state))
        for part in order.parts:
            mainlog.debug(u"{} {} {}".format(str(part), part.state.description, part.human_identifier))

            for operation in part.operations:
                mainlog.debug(u"         op: " + str(operation))
                for tt in session().query(TimeTrack).join(TaskOnOperation).filter(TaskOnOperation.operation == operation).all():
                    mainlog.debug(u"             tt:{}".format(tt))
            for slip in session().query(DeliverySlipPart).join(DeliverySlip).filter(DeliverySlipPart.order_part == part).all():
                mainlog.debug(u"       slip: {} - {}".format(slip.delivery_slip.creation,slip))



    @Slot()
    def _accept_open_dialog(self):
        if self.timer_has_run_once:
            return
        else:
            self.timer_has_run_once = True

        self.timer.stop()

        dialog_object_name = self.dialog_to_click[0]
        self.dialog_to_click = self.dialog_to_click[1:len(self.dialog_to_click)]

        trail = ""
        o = self.app.activeModalWidget()
        mainlog.debug("Looking for {}. Currently focused widget is {} (name = {})".format(dialog_object_name, o, o.objectName()))

        while o and o.objectName() != dialog_object_name:
            trail += str(o.objectName()) + ","
            o = o.parent()

        if o:
            mainlog.debug("timer triggered the expected click on {}".format(dialog_object_name))
            self.dialog_test_result = True
            QTest.keyEvent(QTest.Click, self.app.activeModalWidget(), Qt.Key_Enter)
            mainlog.debug("Clicked on {} !".format(dialog_object_name))

            if len(self.dialog_to_click) > 0:
                mainlog.debug("timer triggered again on {}".format(self.dialog_to_click[0]))
                self.timer_has_run_once = False
                self.timer.start(1000)

        else:
            # You must assert on dialog_test_result otherwise the failure
            # won't be seen (even igf you do self.fail() down here...)
            # I think it's because PySide still catches exceptions even
            # after self.app.exit()
            self.dialog_test_result = False
            # self.app.exit()
            mainlog.error("Didn't find the expected widget {}. The trail was {}".format(dialog_object_name, trail))

    def wait_until_dialog_clicked(self):
        assert self.app

        while self.timer.isActive():
            self.app.processEvents()


    def prepare_to_click_dialog(self,object_name, wait_time=1):
        # app must be set so we know where to look for widgets
        assert self.app

        self.timer_has_run_once = False

        if self.timer_connected:
            self.timer.timeout.disconnect()
        self.timer_connected = True
        self.timer.timeout.connect(self._accept_open_dialog)

        self.timer.setSingleShot(True)
        self.dialog_to_click.append(object_name)
        self.timer.start(1000 * wait_time)
        mainlog.debug("timer started for clicking on dialog {}".format(object_name))


    # was add_work_on_order, _part
    def add_work_on_order_part(self, order_part, work_date, duration=11, operation_ndx=0):

        cache = PotentialTasksCache(self.task_dao, work_date)

        task = cache.tasks_for_identifier(order_part.operations[operation_ndx])[0]
        session().add(task)
        session().flush()

        tt = self._make_timetrack(task.task_id,work_date,duration)
        mainlog.debug("Timetrack added on {}, with {} hours".format(work_date,duration))
        session().add(tt)
        session().flush()


    def add_work_on_operation(self, operation, work_date, duration=4):

        cache = PotentialTasksCache(self.task_dao, work_date)

        task = cache.tasks_for_identifier(operation)[0]
        session().add(task)
        session().flush()

        tt = self._make_timetrack(task.task_id,work_date,duration)
        session().add(tt)
        session().flush()


    def _fix_focus(self, parent, widget):
        """ Force the focus. This is needed under X 'cose for some reason
        I ignore, the focus gets frequently lost.

        None of this looks quite necessary, bit without that, well, it
        doesn't work.
        """

        parent.show()
        widget.show()

        # I do it twice because, well , someitmes it seemed necessary
        self.app.setActiveWindow(parent)
        widget.setFocus(Qt.OtherFocusReason)
        self.app.processEvents()

        self.app.setActiveWindow(parent)
        widget.setFocus(Qt.OtherFocusReason)
        self.app.processEvents()


    def _make_tmp_file(self):
        tmpfile,tmpfile_path = tempfile.mkstemp(prefix='HorseTest_', suffix='.dat')
        tmpfile = os.fdopen(tmpfile,"w")
        tmpfile.write("TestData")
        tmpfile.close()
        tmpfile = open(tmpfile_path,"rb")
        return tmpfile,tmpfile_path

    def _clear_tmp_file(self, tmpfile, tmpfile_path):
        tmpfile.close()
        os.unlink(tmpfile_path)


