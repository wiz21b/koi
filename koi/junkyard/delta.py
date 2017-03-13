__author__ = 'stc'

# python -m koi.junkyard.delta

from pprint import pprint
from koi.test.setup_test import init_test_database
init_test_database()
from koi.datalayer.database_session import session

from koi.db_mapping import Employee, FilterQuery, Order, OrderPart, Customer, ProductionFile, Operation, OrderPartStateType
from koi.datalayer.quality import QualityEvent,QualityEventType

from koi.junkyard.sqla_dict_bridge import ChangeTracker
from koi.datalayer.RollbackDecorator import RollbackDecorator
from koi.server.json_decorator import JsonCallable, ServerErrors, ServerException, JsonCallWrapper


class EmployeeService:
    def __init__(self, change_tracker : ChangeTracker):
        self._change_tracker = change_tracker

    @JsonCallable()
    @RollbackDecorator
    def load_all(self):
        employees = session().query(Employee).all()
        r = self._change_tracker.serialize_full(employees)
        session().commit()
        return r

class OrderService:
    def __init__(self, change_tracker : ChangeTracker):
        self._change_tracker = change_tracker

    @JsonCallable()
    @RollbackDecorator
    def load_all(self):
        orders = session().query(Order).all()
        r = self._change_tracker.serialize_full(orders)
        session().commit()
        return r

    @JsonCallable([dict])
    @RollbackDecorator
    def apply_updates(self,deltas):
        self._change_tracker.apply_delta_on_database_objects(deltas)
        session().commit()


def apply_changes(inst, change_tracker):
    """ Applies updates that were done on a change tracking DTO to the database.

    :param inst: Object that was modified
    :param change_tracker: Change tracker
    :return:
    """

    obj_track = dict()
    store = dict()

    # d = change_tracker.serialize_delta(inst, obj_track, obj_to_modify)
    change_tracker.delta_serialize(inst, store, obj_track)
    pprint("************************************************ Serialized delta")
    pprint(store)
    pprint("************************************************ / Serialized delta")


    change_tracker.apply_delta_on_database_objects(store.values())

    # change_tracker.apply_delta_on_database_objects(d)
    session().flush()
    # pprint("*** Applied delta")
    # pprint(d)
    key_track = change_tracker.update_delta_with_sqla_keys(store.values())
    # pprint("*** Delta with copied keys ")
    # pprint(d)

    # pprint("*** Updating object with keys from updated delta")
    # change_tracker.copy_delta_pk_in_dto(d, inst)
    pprint(key_track)
    change_tracker.merge_keys(obj_track, key_track)
    # We have finished the round trip. Now we can mark the
    # object as not changed
    change_tracker.clear_changes_recursively(inst)
    # return d


if __name__ == '__main__':

    from datetime import datetime

    from koi.datalayer.sqla_mapping_base import metadata,Base

    change_tracker = ChangeTracker(Base)


    employee = change_tracker.make_change_tracking_dto(Employee)
    employee.fullname = "Zorgo"

    fq = change_tracker.make_change_tracking_dto(FilterQuery)
    fq.name = "Test1"
    fq.query = "price > 123"
    fq.family = "test-family"
    employee.filter_queries.append(fq)

    fq = change_tracker.make_change_tracking_dto(FilterQuery)
    fq.name = "Test2"
    fq.query = "price > 123"
    fq.family = "test-family"
    employee.filter_queries.append(fq)


    d=apply_changes(employee, change_tracker)
    #exit()


    # Adding a new fq
    fq = change_tracker.make_change_tracking_dto(FilterQuery)
    fq.name = "Test3"
    fq.query = "price > 123"
    fq.family = "test-family2"
    employee.filter_queries.append(fq)

    d=apply_changes(employee, change_tracker)
    #exit()


    # e = session().query(Employee).filter(Employee.employee_id == d['employee_id']).one()
    # pprint(change_tracker.serialize_full(e,[]))

    customer = change_tracker.make_change_tracking_dto(Customer)
    customer.fullname = "Darth Vador"
    order = change_tracker.make_change_tracking_dto(Order)
    order_part = change_tracker.make_change_tracking_dto(OrderPart)
    order_part.description = "First part"
    order.parts.append(order_part)


    qe = change_tracker.make_change_tracking_dto(QualityEvent)
    qe.when = datetime.now()
    qe.kind = QualityEventType.non_conform_customer
    qe.who = employee
    order_part.quality_events.append(qe)

    order_part = change_tracker.make_change_tracking_dto(OrderPart)
    order_part.description = "Second part"
    order_part.completed_date = datetime.today()
    order.parts.append(order_part)

    production_file = change_tracker.make_change_tracking_dto(ProductionFile)
    order_part.production_file.append(production_file)

    operation = change_tracker.make_change_tracking_dto(Operation)
    operation.description = "First cut"
    production_file.operations.append(operation)

    order.customer = customer

    d = apply_changes(order, change_tracker)

    operation.description = "First cut - nix"
    d = apply_changes(order, change_tracker)


    order.parts.swap( 0,1)
    d = apply_changes(order, change_tracker)


    d = change_tracker.serialize_full(
        session().query(Order).filter(Order.order_id == order.order_id).one(),
    )

    pprint(d)

    change_tracker.unserialize_full(d)

    # from koi.server.json_decorator import horse_json_encoder
    # e = horse_json_encoder.encode(d)
    # print(e)


    # --------------------------------------------------------------------------------------
    # service = EmployeeService(change_tracker)
    service = OrderService(change_tracker)
    remote_service = JsonCallWrapper(service,JsonCallWrapper.DIRECT_MODE)

    d = remote_service.load_all()

    pprint(d)

    change_tracker.unserialize_full(d)

    exit()
    # --------------------------------------------------------------------------------------
