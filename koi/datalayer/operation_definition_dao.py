from datetime import date,datetime,timedelta

from sqlalchemy.sql.expression import func,and_
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import subqueryload

from koi.datalayer.RollbackDecorator import RollbackDecorator
from koi.datalayer.database_session import session
from koi.datalayer.generic_access import freeze
from koi.db_mapping import OperationDefinition, Operation
from koi.tools.chrono import *
from koi.datalayer.generic_access import all_non_relation_columns
from koi.db_mapping import TaskOnNonBillable # FIXME Move to TaskDAO


class OperationDefinitionDAO:
    def __init__(self,operation_dao):
        self._table_model = None
        self._combo_model = None
        self.operation_dao = operation_dao

    def make(self):
        o = OperationDefinition()
        o.start_date = date(2000,1,1)
        return o

    @RollbackDecorator
    def add_period(self, p, opdef):
        """ Adds a new period on a given operation definition.
        The period is expected to be after all the others.
        """

        if opdef is None:
            raise ValueError("Missing an operation definition")

        if p.start_date is None:
            raise ValueError("Need a proper start date")

        if p.end_date is not None:
            # FIXME Translating exceptions is bad. Use error codes instead.
            raise ValueError(_("Can't add a new period after an operation definition period that was already terminated"))

        # In the rest of this function we assume the periods
        # are chronologically sorted

        if len(opdef.periods) > 0:
            if p.start_date <= opdef.periods[-1].start_date:
                raise ValueError("The new period must start after the beginning of the last one which started on {}".format(opdef.periods[-1].start_date))
            else:

                # Updating the last period.
                # FIXME Write database constraints to ensure
                # the periods don't cover each other.

                opdef.periods[-1].end_date = p.start_date - timedelta(1) # 1 day

        # ensure this update is done before the next one
        # We do that here to avoid constraints checks at the
        # database level (when they'll be written :-))
        session().flush()

        session().add(p)
        p.operation_definition = opdef
        session().commit()

        return p


    @RollbackDecorator
    def save(self,opdef):
        must_refresh_tasks_activity = False

        if opdef not in session():
            session().add(opdef)
        else:
            insp = inspect(opdef)
            imputable_state = insp.attrs.imputable

            must_refresh_tasks_activity = (imputable_state is not None) and imputable_state.history and len(imputable_state.history.unchanged) == 0


        session().flush()

        if len(opdef.periods) == 0:
            raise Exception("An operation definition must always have at least on period")

        if must_refresh_tasks_activity:
            mainlog.debug(u"must_refresh_tasks_activity on operation definition {}".format(opdef.operation_definition_id))

        #     q = """update tasks
        # set active = (orders.state = 'order_ready_for_production' and operation_definitions.imputable)
        # from tasks_operations
        # join operations on tasks_operations.operation_id = operations.operation_id
        # join production_files on production_files.production_file_id = operations.production_file_id
        # join order_parts on order_parts.order_part_id = production_files.order_part_id
        # join orders on orders.order_id = order_parts.order_id
        # join operation_definitions on operation_definitions.operation_definition_id = operations.operation_definition_id
        # where tasks_operations.task_id = tasks.task_id and operation_definitions.operation_definition_id = %s
        # and tasks.active != (orders.state = 'order_ready_for_production' and operation_definitions.imputable)"""
        #     session().connection().execute(q, opdef.operation_definition_id )
        #     session().expire_all() # FIXME Too hard, must select only the necessary instances

        session().commit()
        mainlog.debug("operation_definition_dao : commited")

        mainlog.debug("operation_definition_dao : save - done")

    @RollbackDecorator
    def delete(self,opdef_id):
        if opdef_id is None:
            raise ValueError("Missing an operation definition")

        # FIXME Need to verify there's nothing that depends on that
        # operation definition

        opdef = self.find_by_id(opdef_id)
        mainlog.debug("OperationDefinitionsDAO.delete {}".format(opdef_id))
        session().delete(opdef)
        session().commit()


    @RollbackDecorator
    def find_by_id(self,identifier):
        return session().query(OperationDefinition).filter(OperationDefinition.operation_definition_id == identifier).one()


    @RollbackDecorator
    def find_next_action_for_employee_operation_definition(self, employee_id, operation_definition_id, commit=True, at_time=None):

        # FIXME Move this function into the TaskDAO

        # Rememeber that we're interested in Task, first and foremost.
        # We allow this to be called with necessary parameters to find
        # a task (rather than the task_id iteself) to ease the implementation
        # at the client level.

        task_id = session().query(TaskOnNonBillable.task_id).\
                  filter(TaskOnNonBillable.operation_definition_id == operation_definition_id).scalar()

        return self.operation_dao.find_next_action_for_task(task_id, employee_id, commit=commit, at_time=at_time)



    @RollbackDecorator
    def find_by_id_frozen(self,identifier, commit=True, resilient=True):
        c = all_non_relation_columns(OperationDefinition)

        q = session().query(*c).filter(OperationDefinition.operation_definition_id == identifier)

        if resilient:
            opdef = q.first()
        else:
            opdef = q.one()

        if commit:
            session().commit()

        return opdef

    @RollbackDecorator
    def find_by_short_id(self,short_id):
        return session().query(OperationDefinition).filter(func.upper(OperationDefinition.short_id) == func.upper(short_id)).first()

    @RollbackDecorator
    def all(self):
        return session().query(OperationDefinition).order_by(OperationDefinition.description).all()

    @RollbackDecorator
    def all_frozen(self):
        r = session().query(OperationDefinition.operation_definition_id,
                            OperationDefinition.short_id,
                            OperationDefinition.description).order_by(OperationDefinition.description).all()
        session().commit()
        return r


    @RollbackDecorator
    def all_direct(self):
        return session().query(OperationDefinition).filter(OperationDefinition.on_operation == True).order_by(OperationDefinition.description).all()


    @RollbackDecorator
    def all_direct_frozen(self):
        r =  session().query(OperationDefinition.operation_definition_id,
                             OperationDefinition.description).filter(OperationDefinition.on_operation == True).order_by(OperationDefinition.description).all()
        session().commit()
        return r


    @RollbackDecorator
    def all_indirect(self, on_order = False):
        return session().query(OperationDefinition).filter(and_(OperationDefinition.on_operation == False, OperationDefinition.on_order == on_order)).order_by(OperationDefinition.description).all()

    @RollbackDecorator
    def all_on_date(self,d):
        return self.all()

    @RollbackDecorator
    def all_imputable_unbillable(self,d):
        d = datetime(d.year,d.month,d.day,0,0,0)

        r = session().query(OperationDefinition).\
            filter( and_( OperationDefinition.imputable == True,
                          OperationDefinition.on_order == False,
                          OperationDefinition.on_operation == False)).\
            order_by(OperationDefinition.description)

        return r


    @RollbackDecorator
    def all_on_order(self):
        """ All opdef that can be linked to an order (i.e.
        at the "order level") """

        return session().query(OperationDefinition).\
            filter( and_(OperationDefinition.on_order == True,
                         OperationDefinition.imputable == True)).\
            order_by(OperationDefinition.description).all()


    @RollbackDecorator
    def all_on_order_part(self, commit = True):
        """ All opdef that can be linked to an operation (i.e.
        at the "order part level") when defining a new order
        part. """

        chrono_click("all_on_order_part 1")
        # return session().query(OperationDefinition).\
        #     filter( OperationDefinition.on_operation == True).\
        #     order_by(OperationDefinition.description).all()


        opdefs = session().query(OperationDefinition).\
                 filter( OperationDefinition.on_operation == True).\
                 options(subqueryload(OperationDefinition.periods)).\
                 order_by(OperationDefinition.description).all()

        frozen_opdefs = []
        for opdef in opdefs:
            chrono_click("all_on_order_part 2 XXX ")
            frozen_periods = freeze(opdef.periods, commit=False)
            frozen_opdef = freeze(opdef, False, ['periods'] )
            frozen_opdef.periods = frozen_periods
            frozen_opdefs.append(frozen_opdef)

        if commit:
            session().commit()
        chrono_click("all_on_order_part 2")
        return frozen_opdefs


    @RollbackDecorator
    def is_used(self, op_def_id):
        """ Is an operation currently used ?
        This is useful to know before deleting.
        """
        c = session().query( Operation).filter( Operation.operation_definition_id == op_def_id).count()
        return c >= 1
