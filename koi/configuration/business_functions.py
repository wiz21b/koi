from decimal import Decimal
import math
from datetime import datetime,date

from koi.base_logging import mainlog
from koi.db_mapping import TaskOnOrder,TaskOnOperation,TaskOnNonBillable, Order
from koi.db_mapping import OrderStatusType, OrderPartStateType, OrderPart
from koi.datalayer.gapless_sequence import gaplessseq
from koi.datalayer.data_exception import DataException
from koi.datalayer.quality import QualityEventType

from koi.datalayer.database_session import session
from koi.datalayer.RollbackDecorator import RollbackDecorator
from koi.datalayer.audit_trail_service import audit_trail_service
from koi.gui.dialog_utils import confirmationBox
from koi.central_clock import central_clock

class BusinessComputationsService:

    def __init__(self):
        pass

    def set_dao(self, dao):
        self.dao = dao


    @RollbackDecorator
    def mark_as_non_conform(self, quality_event_dto, commit=True):
        part = self.dao.order_part_dao.find_by_id( quality_event_dto.order_part_id)

        # Create a non conformity event
        # self.dao.quality_dao.make(non_confomity_type, part.order_part_id, commit = False)

        self.dao.quality_dao.save_or_update(quality_event_dto)

        # Change the state of the order part
        self.transition_part_state(part, OrderPartStateType.non_conform)

        order_part = self.dao.order_part_dao.find_by_id( quality_event_dto.order_part_id)

        # will commit
        audit_trail_service.record("UPDATE_ORDER_PART", "Non conformity : {} for {}:{}".format(quality_event_dto.kind.description, order_part.label, order_part.description),
                                   quality_event_dto.order_part_id)


    # @RollbackDecorator
    # def mark_as_non_conform(self, order_part_id, non_confomity_type, commit=True):
    #     part = self.dao.order_part_dao.find_by_id(order_part_id)
    #
    #     # Create a non conformity event
    #     self.dao.quality_dao.make(non_confomity_type, part.order_part_id, commit = False)
    #
    #     # Change the state of the order part
    #     self.transition_state(part, OrderPartStateType.non_conform)
    #
    #     order_part = self.dao.order_part_dao.find_by_id(order_part_id)
    #
    #     # will commit
    #     audit_trail_service.record("UPDATE_ORDER_PART", "Non conformity : {} for {}:{}".format(non_confomity_type.description, order_part.label, order_part.description),order_part_id)

    def check_order_state_transition(self, order : Order, new_state : OrderStatusType):

        if new_state not in OrderStatusType:
            # This will catch None state as well
            raise Exception("The state {} is unknown".format(new_state))
        elif new_state == order.state:
            # It is always to allowed to go from one state to the same state.
            return True

        if new_state in (OrderStatusType.order_ready_for_production) \
            and not order.preorder_label:
            return confirmationBox( _("No estimate ?"),
                _("You want to put the order in the state {}. "
                  "However this order was not a estimate before. "
                  "This means that this order will be without a estimate. "
                  "Continue anyway ?").format(new_state.description), "confirm_estimate")

        elif new_state in (OrderStatusType.order_ready_for_production) \
            and order.preorder_label \
            and not order.sent_as_preorder:
            return confirmationBox( _("No estimate sent ?"),
                _("You want to put the order in the state {}. "
                  "However it seems you didn't send any estimate to the customer. "
                  "Continue anyway ?").format(new_state.description), "confirm_estimate_sent")

        else:
            return True


    def compute_order_state_from_parts(self, order : Order):
        """ Look at all the parts of an order and deduce
        the state of the order from it.

        We actually look at the parts which have quantities
        planned for them. Parts without quantities may be
        left overs or comments.
        """

        mainlog.debug("compute_order_state_from_parts")

        # We count how many times a given state appears
        # in all order parts.
        state_count = dict()
        parts_with_quantities = 0

        for part in order.parts:
            # Avoid "comment" parts
            if part.qty > 0:
                parts_with_quantities += 1
                mainlog.debug("part {} - qex {}".format(part.description, part.tex2))
                if part.state not in state_count:
                    state_count[part.state] = 0
                state_count[part.state] = state_count[part.state] + 1

        mainlog.debug("compute_order_state_from_part_states : State count : {}".format(state_count))

        if len(state_count) == 1:
            # All the order parts have the same state, so the
            # order will have a corresponding state

            part_state = list(state_count.keys())[0]

            # End states
            if part_state == OrderPartStateType.completed:
                state = OrderStatusType.order_completed
            elif part_state == OrderPartStateType.aborted:
                state = OrderStatusType.order_aborted
            # Start state
            elif part_state == OrderPartStateType.preorder:
                state = OrderStatusType.preorder_definition
            # Everything in between
            elif part_state == OrderPartStateType.ready_for_production:
                state = OrderStatusType.order_ready_for_production
            elif part_state == OrderPartStateType.production_paused:
                state = OrderStatusType.order_production_paused
            else:
                raise Exception("Unrecognized state {}".format(part_state))

        elif parts_with_quantities >= 1:
            # The order parts have different statuses but some of them
            # have quantities
            state = OrderStatusType.order_ready_for_production

        else:
            mainlog.debug("compute_order_state_from_parts : at least one part in the order, but none of them with quantities")
            # There are more than one order part state in the order
            # AND None of the part have quantities
            state = OrderStatusType.preorder_definition

        self._set_order_state( order, state)


    def _set_order_state(self, order : Order, state):

        if state not in OrderStatusType:
            # This will catch None state as well
            raise Exception("The state {} is unknown".format(state))

        if state == OrderStatusType.preorder_sent and order.sent_as_preorder is None:
            # Arriving to OrderStatusType.preorder_sent state
            order.sent_as_preorder = central_clock.today()

        elif order.state == OrderStatusType.preorder_sent and state == OrderStatusType.preorder_definition:
            # The user probably wants to clear an error
            order.sent_as_preorder = None

        if state in (OrderStatusType.order_completed, OrderStatusType.order_aborted):
            order.completed_date = central_clock.today()
        else:
            order.completed_date = None

        # Pay attention, the following assignments are not as simple
        # as they seem. That is, they'll trigger an update (of course).
        # Since there are constraints tying preorder_label, accounting_label
        # and state, one must be careful that they are updated all at once
        # in a single update statement. The following assignment on
        # accounting label is constructed so that SQLAlchemy produces
        # one sql update statement. See the doc at file:///C:/PORT-STC/opt/python/Doc/sqlalchemy/orm/session.html#embedding-sql-insert-update-expressions-into-a-flush
        # order.preorder_label = None

        if (state in (OrderStatusType.preorder_definition, OrderStatusType.preorder_sent)) and order.preorder_label is None:
            order.preorder_label = gaplessseq('preorder_id')
            mainlog.debug("_set_order_state() setting order.preorder_label to {} 'cos sate is {}".format(order.preorder_label,order.state))

        elif (state not in (OrderStatusType.preorder_definition, OrderStatusType.preorder_sent, OrderStatusType.order_aborted)) and order.accounting_label is None:
            order.accounting_label = gaplessseq('order_id')
            mainlog.debug("_set_labels_for_state() setting order.accouting_label {} 'cos sate is {}".format(order.accounting_label, state))

        order.state = state
        audit_trail_service.record("ORDER_STATE_CHANGED","State transition to {}".format(state), order.order_id, commit=False)



    def transition_order_state(self, order : Order, state : OrderStatusType):
        """ Transition order's state from order.state to state
         Possibly transition the states of the order's parts.
         Note that this is a transition, not a "set". A transition
         is more business oriented and thus, ther are more
         control on the validity of the transition.

        :param order:
        :param state:
        :return:
        """

        # mainlog.debug("-" * 50 + "transition_order_state from '{}' to '{}'".format(order.state, state))

        self._set_order_state( order, state)

        part_state = self.order_part_state_from_order_state(state)
        for part in order.parts:
            self.transition_part_state(part, part_state)



    def change_several_order_parts_state(self, order : Order, order_parts_states_map : dict):
        """ Set the state of one or more order parts to the give state.
        All the parts *must* belong to the given order.

        Once this is done the state of the given order is adapted
        to match the states of the parts.
        """

        if not order_parts_states_map:
            mainlog.debug("change_several_order_parts_state : nothing to do")
            return

        for state in order_parts_states_map.values():
            if state not in OrderPartStateType:
                raise DataException("Improper target state {}".format(state),
                                    DataException.IMPROPER_STATE_TRANSITION)

        mainlog.debug("change_several_order_parts_state {}".format(order_parts_states_map))

        for order_part in order.parts:
            if order_part in order_parts_states_map:
                # order_part.transition_state(state)
                business_computations_service.transition_part_state(order_part, order_parts_states_map[order_part])

        # Adapt the order's state to its parts' states

        business_computations_service.compute_order_state_from_parts(order)


    # def infer_part_state(self, order_part : OrderPart):
    #     assert isinstance(order_part, OrderPart)
    #
    #     if order_part.tex2 < order_part.qty and order_part.state == OrderPartStateType.completed:
    #         # "downgrade from completed to in production"
    #         return OrderPartStateType.ready_for_production
    #     else:
    #         return order_part.state

    def transition_part_state(self, order_part : OrderPart, state):
        """ Transition an order part state, and apply all business decisions
        accordingly.

        :param order_part: An OrderPart (will usually be part of a sqla session)
        :param state: The new state.
        :return:
        """

        assert isinstance(order_part, OrderPart)
        from koi.datalayer.DeclEnumP3 import EnumSymbol
        assert isinstance(state, EnumSymbol)

        if state != order_part.state:

            mainlog.debug("transition_part_state : {} --> {}".format(order_part, state))
            if order_part.state and state not in self.order_part_possible_next_states( order_part.state):
                raise DataException("Improper transition from state '{}' to state '{}'".format(order_part.state, state), DataException.IMPROPER_STATE_TRANSITION)

            mainlog.debug(u"Order part {} : transiion from {} -> {}".format(order_part.order_part_id,order_part.state,state))
            order_part.state = state

            # So that means that if the user changes a past part (say january)
            # from completed to aborted, then the changed part "moves" to
            # today (and thus may move from on GUI view to another)

            if order_part.state in (OrderPartStateType.completed, OrderPartStateType.aborted):
                order_part.completed_date = central_clock.today()
            else:
                order_part.completed_date = None

            audit_trail_service.record("UPDATE_ORDER_PART", "Transition to {} for {}:{}".format(state.description, order_part.label, order_part.description),order_part.order_part_id,commit=False)
        else:
            mainlog.debug("transition_part_state : nothing to do")

    def tar_time_horizon(self, at_time):
        security = 2 # hours

        if not at_time:
            at_time = central_clock.now()

        time_limit = datetime( at_time.year, at_time.month, at_time.day)

        # Daytime job
        time_limit = time_limit.replace(hour=6 - security)

        return time_limit

        # Work in shift
        # if 6 < at_time.hour < 14:
        #     time_limit = time_limit.replace(hour=6 - security)
        # elif 14 < at_time.hour < 22:
        #     time_limit = time_limit.replace(hour=14 - security)
        # else:
        #     time_limit = time_limit.replace(day=time_limit.day - 1, hour=22 - security)


    def encours_on_params(self, qty_produced, qty_ordered,
                          hours_consumed, hours_planned,
                          unit_price : Decimal, material_price : Decimal, order_part_id, ref_date):
        """ Compute the commercial value of work and material engaged in production
        on final goods. So, this is not related to the production cost.
        """

        # hours planned = hours planned for the whole order part (thus sum(hours planned ofr each operation) * qty_ordered

        # mainlog.debug("encours_on_params: qty_produced={},qty_ordered={},hours_consumed={},hours_planned={},unit_price={},material_price={}".format(qty_produced,qty_ordered,hours_consumed,hours_planned,unit_price,material_price))

        if unit_price > 0:
            return float(material_price) + float(qty_produced) * float(unit_price)
        else:
            # We assume the part we're looking at is not complete ('cos if it
            # wasn't then it wouldn't belong to the valuation)

            return self.dao.order_part_dao.value_work_on_order_part_up_to_date(
                order_part_id, ref_date)


    def order_possible_next_states(self, state):
        # The rationale is that we can go to ready_for_production
        # almost any time

        cls = OrderStatusType # shortcut

        if state == cls.preorder_definition:
            return (cls.order_definition, cls.order_ready_for_production, cls.preorder_sent)

        elif state == cls.order_definition:
            return (cls.order_definition, cls.order_ready_for_production, cls.order_aborted, cls.order_completed)

        elif state == cls.preorder_sent:
            return (cls.preorder_definition, cls.order_definition, cls.order_ready_for_production, cls.order_aborted,
                    cls.order_completed)

        elif state == cls.order_ready_for_production:
            return (cls.order_aborted, cls.order_completed, cls.order_production_paused, cls.order_definition)

        elif state == cls.order_production_paused:
            return (cls.order_ready_for_production, cls.order_aborted, cls.order_completed, cls.order_definition)

        elif state == cls.order_completed:
            return (cls.order_ready_for_production, cls.order_aborted)

        elif state == cls.order_aborted:
            return (cls.order_ready_for_production, cls.order_completed)

        else:
            raise Exception("Unknown source state")


    def order_part_possible_next_states(self, state):
        # The rationale is that we can go to ready_for_production
        # almost any time

        cls = OrderPartStateType

        if state == cls.preorder:
            return (cls.ready_for_production, cls.aborted, cls.completed, cls.production_paused)

        elif state == cls.ready_for_production:
            return (cls.aborted, cls.completed, cls.production_paused, cls.preorder, cls.non_conform)

        elif state == cls.production_paused:
            return (cls.ready_for_production, cls.aborted, cls.completed, cls.preorder, cls.non_conform)

        elif state == cls.non_conform:
            return (cls.ready_for_production, cls.aborted, cls.completed, cls.preorder)

        elif state == cls.completed:
            return (cls.ready_for_production, cls.aborted, cls.non_conform)

        elif state == cls.aborted:
            return (cls.ready_for_production, cls.completed)

        else:
            raise Exception("Unknown source state : {}".format(state))


    def order_part_state_from_order_state(cls, order_state):
        """ Derive a part state from its parent order state.
        That's usefull when one adds a new part to an existing
        order which has an arbitrary state.
        """

        d = {OrderStatusType.preorder_definition: OrderPartStateType.preorder,
             OrderStatusType.preorder_sent: OrderPartStateType.preorder,
             OrderStatusType.order_definition: OrderPartStateType.production_paused,
             OrderStatusType.order_ready_for_production: OrderPartStateType.ready_for_production,
             OrderStatusType.order_production_paused: OrderPartStateType.production_paused,
             OrderStatusType.order_completed: OrderPartStateType.completed,
             OrderStatusType.order_aborted: OrderPartStateType.aborted}

        return d[order_state]


    # Used when displayed
    def order_states_precedence(cls):
        return [OrderPartStateType.ready_for_production,
                OrderPartStateType.production_paused,
                OrderPartStateType.preorder,
                OrderPartStateType.completed,
                OrderPartStateType.aborted,
                OrderPartStateType.non_conform]

def zero(n):
    if n is None:
        return 0
    else:
        return n


def operation_unit_cost(fixed_cost, duration, hourly_cost):
    """ Cost of an operation performed during a given duration.
    This basically an "operation" from the data model and compute its
    unit cost.

    fixed cost : for example, cost of the material needed for the operation.
    duration : duration of the operation (in hours)
    hourly_cost : hourly cost for the work of that operation
    """

    return (fixed_cost * 1.25 + duration* float(hourly_cost) ) * 1.15






def is_task_imputable_for_employee(task,employee):
    # Currently employee is not used but that should cahnge in the
    # future

    assert task is not None

    if isinstance(task,TaskOnOperation):
        return task.active and task.operation.operation_model and \
            task.operation.operation_model.imputable and \
            task.operation.operation_model.on_operation and \
            task.operation.production_file.order_part.order.imputable

    elif isinstance(task,TaskOnNonBillable):
        return task.active and task.operation_definition.imputable

    elif isinstance(task,TaskOnOrder):
        return task.active and \
            task.operation_definition.imputable and \
            task.operation_definition.on_order and \
            task.order.imputable

    else:
        raise Exception("Unknown task type {}".format(type(task)))


def is_task_imputable_for_admin(task):
    """ So basically admin can put time on any task, provided
    its associated operation is indeed imputable. In particular,
    admin can put time on orders which are not imputable for
    regulare employees. That's because admin should be able to fix
    time recording issues at any time (provided it actually makes
    sense, that's why there are some conditions checked here)
    """

    assert task is not None

    if isinstance(task,TaskOnOperation):
        return task.active and task.operation.operation_model and \
            task.operation.operation_model.imputable and \
            task.operation.operation_model.on_operation

    elif isinstance(task,TaskOnNonBillable):
        return task.active and task.operation_definition.imputable

    elif isinstance(task,TaskOnOrder):
        return task.active and \
            task.operation_definition.imputable and \
            task.operation_definition.on_order

    else:
        raise Exception("Unknown task type {}".format(type(task)))




# Init won't be complete, still needs the global dao !
business_computations_service = BusinessComputationsService()
