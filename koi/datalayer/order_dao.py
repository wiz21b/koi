import logging
from datetime import date,timedelta

from sqlalchemy import String
from sqlalchemy import and_, or_, not_
from sqlalchemy.orm import contains_eager,lazyload,joinedload # ,noload,joinedload_all,subqueryload
from sqlalchemy.orm.session import make_transient
from sqlalchemy.sql.expression import asc,cast,func,desc

from koi.configuration.business_functions import business_computations_service
from koi.datalayer import generic_access
from koi.datalayer.RollbackDecorator import RollbackDecorator
from koi.datalayer.audit_trail_service import audit_trail_service
from koi.datalayer.data_exception import DataException
from koi.datalayer.database_session import session
from koi.datalayer.gapless_sequence import gaplessseq, current_gaplessseq_value
from koi.datalayer.letter_position import position_to_letters
from koi.datalayer.order_part_dao import OrderPartDAO
from koi.datalayer.quality import QualityEvent
from koi.datalayer.query_parser import parse_order_parts_query
from koi.datalayer.sqla_mapping_base import declarative_base
from koi.datalayer.types import DBObjectActionTypes
from koi.date_utils import _last_moment_of_previous_month,_last_moment_of_month,_first_moment_of_month
from koi.db_mapping import Order,OrderPart,OrderStatusType,OrderPartStateType, ProductionFile,Operation,TimeTrack,TaskOnOperation,TaskOnOrder,TaskActionReport,DeliverySlipPart,DeliverySlip,Customer,Task,Employee,OperationDefinition
from koi.db_mapping import freeze2
from koi.doc_manager.documents_mapping import Document
from koi.junkyard.sqla_dict_bridge import ChangeTracker,InstrumentedRelation
from koi.junkyard.sqla_dict_bridge import make_change_tracking_dto
from koi.tools.chrono import *
from koi.translators import text_search_normalize

change_tracker = ChangeTracker(declarative_base())

class OrderDAO(object):
    def __init__(self,session,order_part_dao):
        self.order_part_dao = order_part_dao
        self._table_model = None

    def make(self,description,customer):
        new_order = Order()
        new_order.description = description
        new_order.customer_id = customer.customer_id # This will avoid merge issue
        new_order.creation_date = date.today()
        return new_order


    def indirects(self,order):
        """ Time spent by employees on indirect tasks of order.
        """
        pass


    def _set_labels_for_state(self,order):

        # Pay attention, the following assignments are not as simple
        # as they seem. That is, they'll trigger an update (of course).
        # Since there are constraints tying preorder_label, accounting_label
        # and state, one must be careful that they are updated all at once
        # in a single update statement. The following assignment on
        # accouting label is constructed so that SQLAlchemy produces
        # one sql update statement. See the doc at file:///C:/PORT-STC/opt/python/Doc/sqlalchemy/orm/session.html#embedding-sql-insert-update-expressions-into-a-flush
        # order.preorder_label = None

        if (order.state in (OrderStatusType.preorder_definition, OrderStatusType.preorder_sent)) \
                and order.preorder_label is None:
            order.preorder_label = gaplessseq('preorder_id')
            # mainlog.debug(u"_set_labels_for_state() setting order.preorder_label to {} 'cos sate is {}".format(order.preorder_label,order.state))

        elif (order.state not in (OrderStatusType.preorder_definition, OrderStatusType.preorder_sent, OrderStatusType.order_aborted)) \
                and order.accounting_label is None:
            # mainlog.debug(u"_set_labels_for_state() setting order.accouting_label 'cos sate is {}".format(order.state))
            order.accounting_label = gaplessseq('order_id')



    def _set_order_parts_state(self, order, part_state):
        """ Sets the state of each and every part of a given
        order.
        """

        # Since this function is a building block for more
        # sophisticated stuff, NO COMMIT down here plz.

        if part_state not in OrderPartStateType:
            # Will catch None as well
            raise Exception("The state {} is unknown".format(part_state))


        for part in order.parts:
            if part.state != part_state:
                business_computations_service.transition_part_state(part, part_state)
                #part.transition_state(part_state)





    # def _set_dates_from_state(self, order):
    #     if order.state == OrderStatusType.preorder_definition:
    #         order.completed_date = None
    #
    #     elif order.state == OrderStatusType.order_definition:
    #         order.completed_date = None
    #
    #     elif order.state == OrderStatusType.order_ready_for_production:
    #         order.completed_date = None
    #
    #     elif order.state == OrderStatusType.order_production_paused:
    #         order.completed_date = None
    #
    #     elif order.state == OrderStatusType.order_completed:
    #         order.completed_date = date.today()
    #
    #     elif order.state == OrderStatusType.order_aborted:
    #         order.completed_date = date.today()


    # def _transition_state(self, order, state):
    #     """ Transition the state of a given order to the given state.
    #     Possibly transition the states of the order's parts.
    #     Note that this is a transition, not a "set". A transition
    #     is more business oriented and thus, ther are more
    #     control on the validity of the transition.
    #     """
    #
    #     # Since this function is a building block for more
    #     # sophisticated stuff, NO COMMIT down here plz.
    #
    #     if state not in OrderStatusType:
    #         # This will catch None state as well
    #         raise Exception("The state {} is unknown".format(state))
    #
    #     if state == order.state:
    #         return
    #
    #     # mainlog.debug("_transition_state : Transition requested from state {} to state {}".format(order.state, state))
    #     if state not in OrderStatusType.next_states(order.state):
    #         raise Exception("The state transition {} -> {} is not allowed".format(state,order.state))
    #
    #     order.state = state
    #     audit_trail_service.record("ORDER_STATE_CHANGED","State transition to {}".format(state), order.order_id, commit=False)
    #
    #     self._set_dates_from_state(order)
    #     self._set_order_parts_state(order, OrderPartStateType.state_from_order_state(state))
    #     self._set_labels_for_state(order)




    # def _set_order_state(self, order, state):
    #     """ Set the state of an order and update its dates and labels
    #     appropriately, *without* touching its parts.
    #     """
    #
    #     if state not in OrderStatusType:
    #         # This will catch None state as well
    #         raise Exception("The state {} is unknown".format(state))
    #
    #     order.state = state
    #     self._set_dates_from_state(order)
    #     self._set_labels_for_state(order)


    @RollbackDecorator
    def change_order_state(self, order_id, state, commit=True):
        """ Change the state of the order. Doing so will possibly
        change the states of the order's parts as well.
        """

        order = self.find_by_id(order_id)
        business_computations_service.transition_order_state( order, state)
        # self._transition_state(order, state)
        if commit:
            session().commit()


    # def _set_state_from_parts(self,order):
    #     """ Look at all the parts of an order and deduce
    #     the state of the order from it.
    #
    #     We actually look at the parts which have quantities
    #     planned for them. Parts without quantities may be
    #     left overs or comments.
    #     """
    #
    #     # We count how many times a given state appears
    #     # in all order parts.
    #     state_count = dict()
    #     parts_with_quantities = 0
    #
    #     for part in order.parts:
    #         # Avoid "comment" parts
    #         if part.qty > 0:
    #             parts_with_quantities += 1
    #             mainlog.debug("part {} - qex {}".format(part.description, part.tex2))
    #             if part.state not in state_count:
    #                 state_count[part.state] = 0
    #             state_count[part.state] = state_count[part.state] + 1
    #
    #     mainlog.debug("_set_state_from_parts : State count : {}".format(state_count))
    #
    #     if len(state_count) == 1:
    #         # All the order parts have the same state, so the
    #         # order will have a corresponding state
    #
    #         part_state = list(state_count.keys())[0]
    #
    #         # End states
    #         if part_state == OrderPartStateType.completed:
    #             state = OrderStatusType.order_completed
    #         elif part_state == OrderPartStateType.aborted:
    #             state = OrderStatusType.order_aborted
    #         # Start state
    #         elif part_state == OrderPartStateType.preorder:
    #             state = OrderStatusType.preorder_definition
    #         # Everything in between
    #         elif part_state == OrderPartStateType.ready_for_production:
    #             state = OrderStatusType.order_ready_for_production
    #         elif part_state == OrderPartStateType.production_paused:
    #             state = OrderStatusType.order_production_paused
    #         else:
    #             raise Exception("Unrecognized state {}".format(part_state))
    #
    #     elif parts_with_quantities >= 1:
    #         # The order parts have different statuses but some of them
    #         # have quantities
    #         state = OrderStatusType.order_ready_for_production
    #
    #     else:
    #         # There are more than one order part state in the order
    #         # AND None of the part have quantities
    #         state = OrderStatusType.preorder_definition
    #
    #     #mainlog.debug("_set_state_from_parts : new order state : {}".format(state))
    #
    #     # FIXME Not clean. If the order state doesn't change
    #     # it's quite possible that its dates change.
    #     # So if the intention is just to alter dates and
    #     # not state, we will report an audit for no
    #     # change
    #     audit_trail_service.record("ORDER_STATE_CHANGED","to {}".format(state), order.order_id, commit=False)
    #
    #     order.state = state
    #     self._set_dates_from_state(order)
    #     self._set_labels_for_state(order)
    #     return



    @RollbackDecorator
    def change_order_parts_state(self, order_id, order_parts_ids, state, commit=True):
        """ Set the state of one or more order parts to the give state.
        All the parts *must* belong to the given order.

        Once this is done the state of the given order is adapted
        to match the states of the parts.
        """

        bmap = dict()

        # convert id's to session object
        order = self.find_by_id(order_id)
        for part in order.parts:
            if part.order_part_id in order_parts_ids:
                bmap[part] = state

        mainlog.debug("change_order_parts_state : {}".format( ["{} -> {} ".format(k,v) for k,v in bmap.items()]))
        business_computations_service.change_several_order_parts_state( order, bmap)

        if commit:
            session().commit()


    @RollbackDecorator
    def change_several_order_parts_state(self, order_id, order_parts_ids_state_map : dict, commit=True):
        """ Set the state of one or more order parts to the give state.
        All the parts *must* belong to the given order.

        Once this is done the state of the given order is adapted
        to match the states of the parts.
        """


        # convert id's to session object
        order = self.find_by_id(order_id)

        bmap = dict()
        for part in order.parts:
            if part.order_part_id in order_parts_ids_state_map:
                bmap[part] = order_parts_ids_state_map[part.order_part_id]

        business_computations_service.change_several_order_parts_state( order, bmap)

        if commit:
            session().commit()


    @RollbackDecorator
    def update_preorder_notes(self,order_id,note,footer):
        preorder = session().query(Order).filter(Order.order_id == order_id).options(lazyload(Order.parts), lazyload(Order.customer)).first()

        if preorder:
            preorder.preorder_print_note,preorder.preorder_print_note_footer = note,footer
            session().commit()
        else:
            raise DataException("Preorder id not found",INVALID_PK)



    @RollbackDecorator
    def save(self,order,commit=True):
        """ DEPRECATED

        Save the order. This will *only* save the order instance,
        not its parts. So for example, you can't use this method to
        change the state of the order ('cos if you do so, the order
        of the parts may not be updated accordingly).
        """



        # FIXME This is not safe regarding to the customer
        # If order is added, then I think SQLA tries to
        # add order.customr to the session too. But if the
        # customer is already in the session, then that fails :
        # AssertionError: A conflicting state is already present in the identity map for key (<class 'db_mapping.Customer'>, (1002,))

        # mainlog.debug(u"order_dao.save():{}".format(order.preorder_print_note))
        audit_action = "UPDATE_ORDER"

        if order not in session():
            if not order.order_id:
                session().add(order)
                audit_action = "CREATE_ORDER"
            else:
                # mainlog.debug("order_dao.save : merge")
                order = session().merge(order)
        else:
            pass
            # mainlog.debug("order_dao.save : order already in session {}".format(type(order)))

        self._set_labels_for_state(order)

        session().flush()

        audit_trail_service.record(audit_action,None, order.order_id, commit=False)


        if commit:
            session().commit()

        return order


    @RollbackDecorator
    def update_order(self,order_id,current_customer_id,customer_order_name,customer_preorder_name, order_state,
                     comments,
                     estimate_sent_date,
                     parts_results=dict()):
        """ Updates the order with number order_id. If order_id is None, then
        a new order id created.
        Return the SQLAlchemy's order data (session bound !!!)

        parts_results is a dict. Its keys are part actions. The value assocaited to
        each part action is a list of operations (of the part) actions.
        """

        audit_changes = ""

        # Parts result is a dict of dict

        # if not isinstance(parts_results,OrderedDict):
        #     # Ordered because the key orders must reflect the
        #     # order of the parts...
        #     raise Exception("I'm expecting an OrderedDict")

        # mainlog.debug("update_order() : start")


        order = None

        # Preload all we need.
        # The next step is to merge whatever is needed to the result
        # of this load.



        if order_id:
            new_order = False
            self.load_all_ops_lazily(order_id)

            # We're modifying an existing order
            # BUG We've lost the version by using only id's...
            order = self.find_by_id(order_id)
        else:
            new_order = True
            mainlog.debug("Brand new order; not loading any order parts")
            order = Order() # The state is expected to be preorder

            session().add(order)
            # self._set_order_state(order, order_state) # no commit
            # order.state = None
            # business_computations_service.transition_order_state(order, order_state)


        mainlog.debug("Order state is {}. Is it a new order ? {}.".format(order.state, new_order))
        # mainlog.debug("Done with session loading of the order")

        # Save the order (so we can link the order parts to it)
        # Think about errors here : if the order can't be saved
        # then the orders shouldn't be saved neither

        if order.customer_id != current_customer_id:
            audit_changes += "Change customer id to {}".format(current_customer_id)

        if order.customer_order_name != customer_order_name:
            audit_changes += "Change customer order id to {}".format(customer_order_name)

        if order.customer_preorder_name != customer_preorder_name:
            audit_changes += "Change customer preorder id to {}".format(customer_preorder_name)

        if order.description != comments:
            audit_changes += "Change comments to {}".format(comments)

        order.customer_id = current_customer_id
        order.customer_order_name = customer_order_name
        order.customer_preorder_name = customer_preorder_name
        order.description = comments
        order.sent_as_preorder = estimate_sent_date

        mainlog.debug("Order state is {}".format(order.state))

        # Transform our parts so that we can later update
        # the merged order_parts in our lists (with a dict, that's
        # not possible)

        parts_actions = []
        operations_actions = []
        for pa,oa in parts_results: # See parts_results definition to understand this :-)
            parts_actions.append( pa)
            operations_actions.append( oa)
            # mainlog.debug(u"Appended {} {} {} -=> {} ".format(k[0],k[1],k[2], v))
            # mainlog.debug(u"   in session ? {}".format(k[1] in session()))

        #mainlog.debug("At this point, there are {} parts in the order. We're now updating the parts accoridng to what we have received.".format(len(order.parts)))

        # The parts will inherit the state of the order as it is

        parts_actions = self.order_part_dao._update_order_parts(parts_actions,order,commit=False) # no commit but a flush
        mainlog.debug("Order state is {}".format(order.state))

        # At this point the order_part in the parts_actions are
        # in SQLA's session

        #mainlog.debug("Parts have been updated. At this point, there are {} parts in the order".format(len(order.parts)))

        # Fix the state if necessary.
        # That is, if the user doesn't change the state
        # then we might change the state ourselves. We'll change
        # it if the user has added a part and the state is
        # currently completed. We do it becuase in that case
        # it means the order *was* completed but can't be anymore
        # because one adds a new part which is by definition,
        # not completed.

        if order_state == order.state and order.state == OrderStatusType.order_completed:
            # Thus if order_state != order.state, it means the user wants
            # to force a given state (included "completed").
            # If order.start != completed, then the state needs not
            # to be changed (only the completed state requires the change
            # we're interested in)

            for i in range(len(parts_actions)):

                action_type,order_part,op_ndx,quality_events = parts_actions[i]
                if action_type == DBObjectActionTypes.TO_CREATE:

                    for part in order.parts:
                        # mainlog.debug( "qty={} tex2={}".format(part.qty,part.tex2))
                        if part.qty > part.tex2:
                            order_state = OrderStatusType.order_ready_for_production
                            break

                    break

        # Set the state of the order and possibly the state
        # of its parts. Note that we expect the function below
        # to do nothing if the order state is not changed.
        # Note that we don't deduce the order's state from
        # its parts. It's the other way around.

        # self._transition_state(order, order_state) # no commit
        mainlog.debug("Order state is {}".format(order.state))

        # FIXME This is a hack
        # This allows to run the transition_order_state as if the order was brand new
        # Problem is, when order is created, its state defaults to something
        # Moreover one cannot store a order in the database without having a state
        # So If create an order and force its state to None I can't save it.
        # Problem is : it's not me who wants to save it, it's SQLAlchemy. Indieed
        # it will save as soon as it needs to flush. And that comes much faster
        # than I need. For exemple, right at the end od the transition, I write
        # in the audit trail. For that, I need the order_id => I need to flush...
        # So, I basically let SQLA flush with a default state and, in the case
        # it was an order creation, I reset the state to have the transition code
        # working properly. But that's a hack because it makes the state transition
        # code a bit less independant of this update_order function.
        # I thought about lifting the not null ocsntraint on the state, but I think
        # it's too risky to leave it out (data quality issues will arise from
        # that I guess).

        if new_order:
            order.state = None
            mainlog.debug("update_order() : hack for transition, order.state is now {}".format(order.state))
        business_computations_service.transition_order_state(order, order_state)


        # mainlog.debug("There are {} part results".format(len(parts_results)))
        # for action_type, order_part, op_ndx in parts_results:
        #     mainlog.debug("Part is : {} {} {}".format(action_type,order_part.order_part_id,op_ndx))

        # progress = QProgressDialog(_("Saving order..."), None, 0, 2 + len(parts_results), self)
        # progress.setWindowModality(Qt.WindowModal)
        # progress.setWindowTitle(_("Saving..."))
        # progress.setValue(1)

        # Pay attention. All the submodels might not be linked to
        # a part anymore. This is because the user might have
        # cleared some rows in the order parts side. If he did
        # so, then those rows won't appear in the parts_results.

        #mainlog.debug("At this point, there are {} parts in the order".format(len(order.parts)))
        for i in range(len(parts_actions)):

            action_type,order_part,op_ndx,quality_events = parts_actions[i]
            operations_for_part = operations_actions[i]

            # mainlog.debug(u"Setting operations on part {} state {}".format(order_part,order_part.state))
            if order_part not in order.parts:
                # mainlog.error("oooops")
                pass

            if operations_for_part:
                # All operations can be unchanged but their sort order
                # *can* be changed.

                # mainlog.debug("There are {} operation  results".format(len(operations_for_part)))
                # for action_type, op, op_ndx in operations_for_part:
                #     mainlog.debug("   Operation : {} {} {}".format(action_type,op.operation_id,op_ndx))
                # mainlog.debug("save operations for order_part_id={} at index {}".format(order_part.order_part_id,op_ndx))

                self.order_part_dao.update_operations( operations_for_part, order_part, commit=False) # still no commit


            # mainlog.debug(u"-- after -- Part {} state {}".format(order_part,order_part.state))

        # Recompute the "human positions" of each order parts
        # We do this here because it is quite heavy to compute

        self.recompute_position_labels(order)

        audit_trail_service.record("UPDATE_ORDER", audit_changes, order.order_id, who_id=None,who_else=None,commit=False)

        session().commit()

        # We return the order because it may have been created here
        return order





    def _order_parts_worked_hours(self, date_end):
        """ Compute the hours reported order parts up to a given date,
        provided there are hours reported.
        """

        # FIXME Since the quantities determined here also determines the orders
        # we have to look into, we have a recursive issue. That is, if we
        # want to not not look at every order parts, then we need to know
        # which orders are not interesting. But to know what orders are
        # not interesting, we need to read the read the order parts first...
        # A solution would be to know if *and* when an order was completed.
        # For that we have Order.completed_date but we must make sure
        # it is updated correctly (when a delivery is created/removed or
        # when order part.qty is changed, etc.)

        # "greatest" is a trick that allows us to transform NULL into zero.
        # FIXME coalesce should be better
        # FIXME The outer joins are strange, we return more order_part_id than necessary
        #       moreover, the queries which this this subquery seem to outer join on it.
        #       So it is most definitely useless.

        subq = session().query(OrderPart.order_part_id.label("order_part_id"),
                               (func.greatest(func.sum(TimeTrack.duration),0)).label("part_worked_hours")).\
            join(ProductionFile).join(Operation).join(TaskOnOperation).join(TimeTrack).\
            filter(TimeTrack.start_time <= date_end).\
            group_by(OrderPart.order_part_id).subquery()

        # print(subq)
        return subq


    def _order_parts_quantity_done(self, date_end):
        """ Compute the quantities done on an order part up to a given date,
        by *only* looking at delivery slips.
        Also gives the date of the last delivery that happened before or on
        that date.

        We don't use the tex_ migrated field. That's because this query
        reflects the quantities produced so far but for which we have delivery
        slips, that is those on which there were some activity recorded.
        tex_ represent a starting point but it does not represent any kind
        of activity => it does not belong here, semantically speaking.

        Therefore, this *DOES NOT* compute the total quantity produced for a
        given order part if the tex_ field is set !
        """

        # FIXME Optimize this to take advantage of order.completed_date

        ds_sum_subq = session().query(OrderPart.order_part_id,
                                      (func.coalesce(func.sum(DeliverySlipPart.quantity_out),0)).label("part_qty_out"),
                                      (func.max(DeliverySlip.creation).label("last_delivery_before_date"))).\
            join(Order).\
            join(DeliverySlipPart).\
            join(DeliverySlip).\
            filter(and_(DeliverySlip.active,
                        or_(DeliverySlip.creation == None, # FIXME If a DS is active, can it really have a null creation date ?
                            DeliverySlip.creation <= date_end))).\
            group_by(OrderPart.order_part_id).subquery()

        return ds_sum_subq


    def __order_parts_finished_on_month_subquery(self,state,month_date):
        if state not in (OrderPartStateType.completed,OrderPartStateType.aborted):
            # Only the states for which the completed date makes sense
            raise Exception("Unsupported state {}".format(state))

        date_begin = _first_moment_of_month(month_date)
        date_end = _last_moment_of_month(month_date)

        order_parts = session().query(OrderPart.order_part_id.label("order_part_id")).\
                      filter( and_(OrderPart.state == state,
                                   OrderPart.completed_date.between(date_begin, date_end))).\
                      order_by(OrderPart.order_part_id).subquery()

        return order_parts


    @RollbackDecorator
    def _order_parts_finished_this_month_subquery(self,month_date):
        # FIXME move to order part dao
        return self.__order_parts_finished_on_month_subquery(OrderPartStateType.completed,month_date)


    @RollbackDecorator
    def _order_parts_aborted_this_month_subquery(self,month_date):
        # FIXME move to order part dao
        return self.__order_parts_finished_on_month_subquery(OrderPartStateType.aborted,month_date)


    def _active_orders_in_month_subquery(self, month_date):
        date_begin = _first_moment_of_month(month_date)
        date_end = _last_moment_of_month(month_date)

        mainlog.debug("_active_orders_in_month_subquery from {} to {}".format(date_begin, date_end))

        # Work done on each part up to date_end
        hsubq = self._order_parts_worked_hours(date_end)

        # Quantities out on each part up to date_end
        qsubq = self._order_parts_quantity_done(date_end)

        # qsubq_res = session().query(qsubq).order_by("order_part_id").all()
        # print(qsubq_res)

        # print("/// "*10)
        # print( session().query(OrderPart.order_id.label("active_order_id"),
        #                        OrderPart.state == OrderPartStateType.completed,
        #                        OrderPart.completed_date,
        #                        not_( and_( OrderPart.state == OrderPartStateType.completed,
        #                             OrderPart.completed_date < date_begin))).\
        #                     outerjoin(hsubq, hsubq.c.order_part_id == OrderPart.order_part_id).\
        #                     outerjoin(qsubq, qsubq.c.order_part_id == OrderPart.order_part_id).\
        #        filter(OrderPart.order_id == 5896).all())
        # print("/// "*10)


        aggsubq = session().query(OrderPart.order_id.label("active_order_id")).\
                            outerjoin(hsubq, hsubq.c.order_part_id == OrderPart.order_part_id).\
                            outerjoin(qsubq, qsubq.c.order_part_id == OrderPart.order_part_id).\
                            join(Order).\
                        filter( \
            and_(
                # Avoid orders which are in the future
                Order.creation_date <= date_end,
                # An order is removed from the valuation if it was completed.
                # It is removed *as soon as* the user has completed it.
                # But only before the begin of the month. This is
                # to account for delivery slips (thus amounts to bill)
                # issued during the month (IIRC if an orer is completed
                # during the month, then it may still not be billed to the
                # customer, therefore it stays in the WIP valuation; it will
                # disappear from the valuation the next month. So this
                # is a rather coarse approximation : we should have
                # a 'order part delivered' state)
                # Also, this serves has an optimisation since we can
                # remove a great number of parts by just looking
                # at their state and completed_date without going
                # along the joins.
                not_( and_( OrderPart.state == OrderPartStateType.completed,
                            OrderPart.completed_date < date_begin,

                            # Keep in mind that it's possible to have an order part completed
                            # before its last delivery slip. It happens if the user change
                            # the state of the part before and fills a delivery slips a while after.
                            # So I do this. FIXME Maybe it'd be better to make sure
                            # the complete date is set on the last delivery slip at least...
                            not_(qsubq.c.last_delivery_before_date.between(date_begin,date_end)))),

                # An order is removed from the valuation if it was aborted.
                # It is removed *as soon as* the user has aborted it.
                not_( and_( OrderPart.state == OrderPartStateType.aborted,
                            OrderPart.completed_date < date_end)),
                or_(
                    # Work has started, thus there may be a valuation
                    # (done hours are the basis for valuation).
                    # This also covers the case where somebeody
                    # worked this month on the order and so we'd
                    # like to see that in our report.
                    func.coalesce(hsubq.c.part_worked_hours,0) > 0,

                    # Some quantities were delivered this month. Therefore
                        # there will be amount to bill. This is also part
                    # of the valuation (because we count what's left to produce)
                    # FIXME Is this correct ? Shouldn't we take all the delivery slips
                    # FIXME before date_end (and not restrict to "after date_begin")
                    qsubq.c.last_delivery_before_date.between(date_begin,date_end)))).\
            distinct().subquery()

        return aggsubq



    # @RollbackDecorator
    # def xx_active_orders_in_month_subquery(self, month_date):
    #     """ Gives all the orders active for a given month.
    #     """

    #     date_begin = _first_moment_of_month(month_date)
    #     date_end = _last_moment_of_month(month_date)

    #     mainlog.debug("_active_orders_in_month : date_end = {}".format(date_end))

    #     tsubq = self._order_parts_worked_hours(date_end)
    #     qsubq = self._order_parts_quantity_done(date_end)


    #     # check = 4814
    #     # for t in session().query(OrderPart,tsubq).join(tsubq, OrderPart.order_part_id == tsubq.c.order_part_id).filter(OrderPart.order_id == check).all():
    #     #     print "time : " + t

    #     # for t in session().query(OrderPart,qsubq.c.part_qty_out).join(qsubq, OrderPart.order_part_id == qsubq.c.order_part_id).filter(OrderPart.order_id == check).all():
    #     #     print "qty : " + str(t)

    #     aggsubq = session().query(Order.order_id.label("order_id"),
    #                               func.greatest(0,func.sum(tsubq.c.part_worked_hours)).label("worked_hours"),
    #                               func.greatest(0,func.sum(qsubq.c.part_qty_out)).label("qty_out"),
    #                               func.sum(OrderPart.qty).label("qty_ordered"),
    #                               func.sum(OrderPart.estimated_time_per_unit * OrderPart.qty).label("estimated_time"),
    #                               func.max(DeliverySlip.creation).label("last_delivery")).\
    #                         join(OrderPart).\
    #                         outerjoin(tsubq, tsubq.c.order_part_id == OrderPart.order_part_id).\
    #                         outerjoin(qsubq, qsubq.c.order_part_id == OrderPart.order_part_id).\
    #                         outerjoin(DeliverySlipPart).\
    #                         outerjoin(DeliverySlip).\
    #                         group_by(Order.order_id).subquery()


    #     active_orders = session().query(Order.order_id.label("active_order_id")).\
    #                     join(aggsubq,Order.order_id == aggsubq.c.order_id).\
    #                     filter( \
    #         # If an order was completed in the past we ignore it, although its quantities may be
    #         # incomplete. This is done to avoid to have garbage orders from the past.
    #         and_( not_( and_( Order.state == OrderStatusType.order_completed, Order.completed_date < date_begin)),
    #               # An order that is ready_for_production is active
    #               or_(Order.state == OrderStatusType.order_ready_for_production,
    #                   # The user specified that the order is still active
    #                   Order.state == OrderStatusType.order_production_paused,
    #                   # An order that was completed during the month is active (so it's
    #                   # possible to complete an order even if all its quantities
    #                   # have not been actually produced
    #                   # FIXME Warn the user if he forcefully completes an order
    #                   and_( Order.state == OrderStatusType.order_completed,
    #                         Order.completed_date.between(date_begin,date_end)),
    #                   # For other states
    #                   and_(or_( aggsubq.c.worked_hours > 0, # Work on the order has begun
    #                             aggsubq.c.qty_out > 0),
    #                        or_( aggsubq.c.qty_out < aggsubq.c.qty_ordered,
    #                             and_( aggsubq.c.qty_out == aggsubq.c.qty_ordered, # or work is finished (and consequently order is completed), and it was finished this very month
    #                                   aggsubq.c.last_delivery.between(date_begin,date_end))))))).\
    #             order_by(Order.order_id).subquery()

    #     return active_orders


    @RollbackDecorator
    def order_parts_for_monthly_report(self, month_date = None):
        """ Order parts data to show in the monthly financial report.
        """

        if month_date == None:
            month_date = date.today()

        date_end = _last_moment_of_month(month_date)
        last_mo = _last_moment_of_previous_month(month_date)

        mainlog.debug("order_parts_for_monthly_report : date_end = {}".format(date_end))

        # The number of hours worked on an order part until date_end
        tsubq = self._order_parts_worked_hours(date_end)

        # The quantities delivered on an order part until date_end (deliver slips)
        qsubq = self._order_parts_quantity_done(date_end)

        # The quantities delivered on an order part until date_mo (deliver slips)
        # quantity delivered between date_end and last_mo
        qsubq_last_month = self._order_parts_quantity_done(last_mo)

        active_orders = self._active_orders_in_month_subquery(month_date)

        list_active_orders = session().query(active_orders).all()
        # print( sorted([o.active_order_id for o in list_active_orders]))


        # # The price of the quantities delivered on an order part *this* month
        # ds_subq = session().query(DeliverySlipPart.order_part_id,
        #                           func.coalesce(func.sum(func.coalesce(DeliverySlipPart.sell_price,0))).label("total_sell_price")).\
        #     select_from(DeliverySlipPart).\
        #     join(DeliverySlip,DeliverySlip.delivery_slip_id == DeliverySlipPart.delivery_slip_id).\
        #     filter(and_(DeliverySlip.active,
        #                 DeliverySlip.creation.between(last_mo,date_end))).\
        #     group_by(DeliverySlipPart.order_part_id).subquery()

        # Note we introduce _tex here because it is to be used as
        # a correction on the delivery slip computation. The delivery
        # slip is, from this program point of view, the onyl way
        # to report and follow the quantity produced. The tex_ field
        # should not be taken into account because it doesn't have
        # a dynamic concept behind it. It merely represents a starting
        # poitn for the quantity produced. In the report we're building
        # we're interested in what was produced and *when*.

        # ( qty_out:10, worked_hours:183.75, 0, 1041, 11, 237.6, 1, Decimal('7509.4913'), Decimal('82604.4043'), Decimal('0'), '2A', 'Cobalt', "Buy'n'Large Corporation", Decimal('75094.9130'))
        query = session().query((OrderPart._tex + func.coalesce(qsubq.c.part_qty_out,0)).label("part_qty_out"),
                                func.coalesce(tsubq.c.part_worked_hours,0).label("part_worked_hours"),
                                (OrderPart._tex + func.coalesce(qsubq_last_month.c.part_qty_out,0)).label("q_out_last_month"),
                                OrderPart.order_part_id,
                                OrderPart.qty,
                                func.coalesce(OrderPart.total_estimated_time,0).label("total_estimated_time"),
                                OrderPart.order_id,
                                func.coalesce(OrderPart.sell_price,0).label("unit_sell_price"),
                                (OrderPart.qty * OrderPart.sell_price).label("total_sell_price"),
                                func.coalesce(OrderPart.material_value,0).label("material_value"),
                                OrderPart.human_identifier,
                                OrderPart.description,
                                Customer.fullname.label("customer_name"),
                                # func.coalesce(ds_subq.c.total_sell_price,0).label("bill_this_month")).\
                                ((func.coalesce(qsubq.c.part_qty_out,0) - func.coalesce(qsubq_last_month.c.part_qty_out,0)) * OrderPart.sell_price).label("bill_this_month")).\
            select_from(OrderPart).\
            join(active_orders, active_orders.c.active_order_id == OrderPart.order_id).\
            outerjoin(tsubq, tsubq.c.order_part_id == OrderPart.order_part_id).\
            outerjoin(qsubq, qsubq.c.order_part_id == OrderPart.order_part_id).\
            outerjoin(qsubq_last_month, qsubq_last_month.c.order_part_id == OrderPart.order_part_id).\
            join(Order).join(Customer).\
            order_by(OrderPart.order_id,OrderPart.position)

        res = query.all()
        session().commit()

        if res:
            # We extend the tuple returned by SQLAlchemy with
            # our own stuff.
            from collections import namedtuple
            nt = namedtuple('MonthlyReportTuple', res[0]._fields + ('encours',))

            wip_valuation = []
            for r in res:
                # if r.order_part_id == 25268:
                #     mainlog.debug( "old {}".format( ( r.part_qty_out, r.qty, r.part_worked_hours,
                #                      r.total_estimated_time,
                #                      r.unit_sell_price, r.material_value,
                #                      r.order_part_id, date_end)))

                v = business_computations_service.encours_on_params(r.part_qty_out, r.qty, r.part_worked_hours,
                                                                             r.total_estimated_time,
                                                                             r.unit_sell_price, r.material_value,
                                                                             r.order_part_id, date_end)
                # if r.order_part_id == 25268:
                #     mainlog.debug( "   --> {}".format( v))

                wip_valuation.append(
                    nt._make( tuple(r) + \
                             ( v,)))

            # mainlog.debug("encours computation")
            # for r in wip_valuation:
            #     mainlog.debug( "{}, {}".format(r.order_part_id, r.encours))
            #     if r.order_part_id == 25268:
            #         mainlog.debug( ( r.order_part_id, r.part_qty_out, r.qty, r.part_worked_hours,
            #                       r.total_estimated_time,
            #                       r.unit_sell_price,r.material_value, r.encours))

            return wip_valuation
        else:
            return []





    @RollbackDecorator
    def compute_encours_for_month(self,month_date = None):
        """ Compute the encours till the last instant of the month month_date.
        So this works in two scenarios :
        * Knowing the encours of a past month
        * knowing an encours of the ongoing/current month because
          there's nothing past today (so the interval begin of month,
          today is equivalent to begin of month, end of month)

        The encours is computed for a set of order parts.
        An order part is taken into account if it is part of an
        order that is :
        * not completed (i.e. not all of its quantities
          were produced by the end of the month).
        * started (some work done or some quantities out)
        """

        parts = self.order_parts_for_monthly_report(month_date)

        # mainlog.debug( [ (p.order_part_id, p.encours) for p in parts])
        mainlog.debug("compute_encours_for_month month_date {}".format(month_date))

        if parts:
            return sum( [p.encours for p in parts or []] )
        else:
            return 0




    @RollbackDecorator
    def compute_turnover_on(self,month_date):
        """ Turnover for a given month. The turnover is made
        of three parts : turnover = realised value + current encours - past month's encours.

        * realised value = value of quantities delivered (i.e. for which there
          are delivery slips) this month
        * current encours = encours of this month
        * past month's encours = encours at the very end of the previous month

        So the first part depends exclusively on the deliver slips
        written during the month, and nothing else.
        """

        month_before = month_date - timedelta(month_date.day)

        ts_begin = _first_moment_of_month(month_date)
        ts_end = _last_moment_of_month(month_date)

        mainlog.debug("Turnover from {} to {} ----------------------------------------- ".format(ts_begin, ts_end))

        # for order_part,q_out, sell_price  in session().query(OrderPart, DeliverySlipPart.quantity_out, OrderPart.sell_price).\
        #     select_from(DeliverySlipPart).\
        #     join(DeliverySlip,DeliverySlip.delivery_slip_id == DeliverySlipPart.delivery_slip_id).\
        #     join(OrderPart,OrderPart.order_part_id == DeliverySlipPart.order_part_id).\
        #     join(Order,Order.order_id==OrderPart.order_id).\
        #     filter(and_(DeliverySlip.active,
        #                 DeliverySlip.creation.between(ts_begin, ts_end))).order_by(Order.accounting_label,OrderPart.label):
        #
        #     mainlog.debug(u"{} {} {}".format(order_part.human_identifier, q_out, sell_price))

        # mainlog.debug("//Turnover from {} to {} ----------------------------------------- ".format(ts_begin, ts_end))

        # Coalesce works because slip_part.sell_price is never null
        v = session().query(func.coalesce(func.sum(DeliverySlipPart.quantity_out * OrderPart.sell_price))).\
            select_from(DeliverySlipPart).\
            join(DeliverySlip,DeliverySlip.delivery_slip_id == DeliverySlipPart.delivery_slip_id).\
            join(OrderPart,OrderPart.order_part_id == DeliverySlipPart.order_part_id).\
            filter(and_(DeliverySlip.active,
                        DeliverySlip.creation.between(ts_begin, ts_end))).scalar()

        to_bill = 0
        if v:
            to_bill = float(v)

        encours_this_month = float(self.compute_encours_for_month(month_date))
        encours_previous_month = float(self.compute_encours_for_month(month_before))
        turnover = to_bill + encours_this_month - encours_previous_month

        return to_bill, encours_this_month, encours_previous_month, turnover


    # @RollbackDecorator
    # def compute_finished_orders_value_on(self,month_date):
    #     """ Compute the value of the completely finished order. The
    #     value is the product of the quantities out by the sell price.
    #     It is computed for orders which were completed on the given
    #     month (so for which the last quantity was produced during
    #     the month, regardless of the status of the order)
    #     """

    #     orders = self._orders_finished_this_month_subquery(month_date)

    #     res = session().query(func.sum(DeliverySlipPart.quantity_out * OrderPart.sell_price)).\
    #           select_from(DeliverySlipPart).\
    #           join(OrderPart,OrderPart.order_part_id == DeliverySlipPart.order_part_id).\
    #           join(orders, orders.c.order_id == OrderPart.order_id).scalar()

    #     return res or 0



    @RollbackDecorator
    def load_order_parts_on_filter(self,f):
        filter_expression = parse_order_parts_query(f)

        chrono_start()

        # I use the subquery to ensure all the query is done
        # at the postgres level. Before that, I was using
        # select orderpartid in (...) but this was slower.

        ids_subquery = session().query(OrderPart.order_part_id).join(Order).join(Customer).filter(filter_expression).subquery()

        parts_query = session().query(Customer.fullname,
                                      OrderPart.position,
                                      (cast(Order.user_label,String) + OrderPart.label).label('full_part_id'), # human identifier
                                      (cast(Order.preorder_label,String) + OrderPart.label).label('preorder_part_label'), # human identifier
                                      (cast(Order.accounting_label,String) + OrderPart.label).label('accounting_part_label'), # human identifier
                                      OrderPart.description,
                                      OrderPart.deadline,
                                      OrderPart.estimated_time_per_unit,
                                      OrderPart.total_estimated_time,
                                      OrderPart.total_hours,
                                      OrderPart.qty,
                                      OrderPart.tex2,
                                      Order.state,
                                      OrderPart.material_value,
                                      OrderPart.sell_price,
                                      OrderPart.order_part_id,
                                      Order.order_id,
                                      OrderPart.flags,
                                      OrderPart.notes,
                                      OrderPart.priority).\
            select_from(OrderPart).\
            join(Order).\
            join(Customer)

        res = parts_query.join(ids_subquery,ids_subquery.c.order_part_id == OrderPart.order_part_id).all()

        res2 =  self._reinject_human_time(res)
        session().commit()

        chrono_click("query done")
        return res2


    def _reinject_human_time(self, res):

        from koi.Interval import Interval, IntervalCollection
        from datetime import timedelta
        from koi.datalayer.generic_access import DictAsObj

        if not res:
            return []
        
        order_part_ids = [ p.order_part_id for p in res]

        tts = session().query(OrderPart.order_part_id, TimeTrack).select_from(TimeTrack).\
            join(TaskOnOperation).join(Operation).join(ProductionFile).join(OrderPart).\
            filter(OrderPart.order_part_id.in_(order_part_ids)).order_by(TimeTrack.start_time).all()

        intervals = dict()

        for k, tt in tts:
            # k is order part id
            if k not in intervals:
                intervals[k] = [tt]
            else:
                intervals[k].append(tt)


        for k in intervals.keys():

            tt_per_employee = dict()

            # Dispatch TT per employee
            for tt in intervals[k]:
                if tt.employee_id not in tt_per_employee:
                    tt_per_employee[tt.employee_id] = []
                tt_per_employee[tt.employee_id].append(tt)

            # for employee_id, tts in tt_per_employee.items():
            #     mainlog.debug("Employee {}".format(employee_id))

            #     for tt in tts:
            #         mainlog.debug(tt)

            # Fusion/Sum per employee
            total_sum = 0
            for tts_per_employee in tt_per_employee.values():

                d = sum( [ i.duration().total_seconds() / 3600.0
                           for i in IntervalCollection(
                                   *[ Interval( tt.start_time,
                                                tt.start_time + timedelta(hours=tt.duration))
                                      for tt in tts_per_employee ]).intervals ] )
                # mainlog.debug("Sum = {}".format(d))
                total_sum += d

            intervals[k] = total_sum

        new_res = []
        for r in res:
            d = r._asdict()
            if r.order_part_id in intervals:
                d['human_time'] = intervals[r.order_part_id]
            else:
                d['human_time'] = 0
            new_res.append( DictAsObj(d)) # FIXME Use keyed tuples

        return new_res



    @RollbackDecorator
    def load_order_parts_overview(self,month_date, criteria):

        # mainlog.debug("load_order_parts_overview {}".format(month_date))

        parts_query = session().query(Customer.fullname,
                                      OrderPart.position,
                                      (cast(Order.user_label,String) + OrderPart.label).label('full_part_id'), # human identifier
                                      (cast(Order.preorder_label,String) + func.coalesce(OrderPart.label,"-")).label('preorder_part_label'), # human identifier
                                      (cast(Order.accounting_label,String) + func.coalesce(OrderPart.label,"-")).label('accounting_part_label'), # human identifier
                                      OrderPart.description,
                                      OrderPart.deadline,
                                      OrderPart.estimated_time_per_unit,
                                      OrderPart.total_estimated_time,
                                      OrderPart.total_hours,
                                      OrderPart.qty,
                                      OrderPart.tex2,
                                      Order.state,
                                      OrderPart.material_value,
                                      OrderPart.sell_price,
                                      OrderPart.order_part_id,
                                      Order.order_id,
                                      OrderPart.flags,
                                      OrderPart.notes,
                                      OrderPart.priority).\
            select_from(OrderPart).\
            join(Order).\
            join(Customer)



        order_subq = None


        if criteria == OrderPartDAO.ORDER_PART_SELECTION_ACTIVE_ORDERS:

            # order_subq = self._active_orders_suquery(month_date)
            # filter = and_(~Order.state.in_([OrderStatusType.preorder_definition,
            #                                 OrderStatusType.order_production_paused]),
            #               order_subq.c.order_id == OrderPart.order_id)
            # res = parts_query.filter(filter).all()

            # res = parts_query.filter(Order.state == OrderStatusType.order_ready_for_production)
            res = parts_query.filter(OrderPart.state == OrderPartStateType.ready_for_production,
                                     Order.creation_date <= month_date)

        elif criteria == OrderPartDAO.ORDER_PART_SELECTION_PREORDERS:

            # Preorder

            res = parts_query.filter(OrderPart.state == OrderPartStateType.preorder,
                                     Order.creation_date <= month_date)

        elif criteria == OrderPartDAO.ORDER_PART_SELECTION_ON_HOLD:

            # Dormant

            # date_end = _last_moment_of_month(month_date)
            # tsubq = self._order_parts_worked_hours(date_end)
            # tsubq2 = self._order_parts_quantity_done(date_end)

            # qsubq = session().query(Order.order_id.label("order_id"),
            #                     func.greatest(0,func.sum(tsubq.c.part_worked_hours)).label("worked_hours"),
            #                     func.greatest(0,func.sum(tsubq2.c.part_qty_out)).label("qty_out")).\
            #     join(OrderPart).\
            #     outerjoin(tsubq, tsubq.c.order_part_id == OrderPart.order_part_id).\
            #     outerjoin(tsubq2, tsubq2.c.order_part_id == OrderPart.order_part_id).\
            #     group_by(Order.order_id).subquery()

            # res = parts_query.filter(
            #     or_(Order.state == OrderStatusType.order_production_paused,
            #         Order.state == OrderStatusType.order_definition))

            res = parts_query.filter( OrderPart.state == OrderPartStateType.production_paused,
                                      Order.creation_date <= month_date)

        elif criteria == OrderPartDAO.ORDER_PART_SELECTION_COMPLETED_THIS_MONTH:

            # Finished this month ___

            # orders = self._orders_finished_this_month_subquery(month_date)
            # res = parts_query.join(orders)

            parts_finished = self._order_parts_finished_this_month_subquery(month_date)
            res = parts_query.join(parts_finished,
                                   OrderPart.order_part_id == parts_finished.c.order_part_id)

        elif criteria == OrderPartDAO.ORDER_PART_SELECTION_ABORTED_THIS_MONTH:

            # Aborted this month

            # orders = self._orders_aborted_this_month_subquery(month_date)
            # res = parts_query.join(orders)

            # res = parts_query.filter(OrderPart.state == OrderPartStateType.aborted)

            parts_aborted = self._order_parts_aborted_this_month_subquery(month_date)
            res = parts_query.join(parts_aborted,
                                   OrderPart.order_part_id == parts_aborted.c.order_part_id)
        else:
            return []


        # res = res.filter(OrderPart.order_id == 5485)

        res = res.all()

        res2 = self._reinject_human_time(res)
        session().commit()
        return res2

        # return res




        # # Sort everything into specific orders

        # h = dict()
        # h['order_id'] = part.order_id
        # h['flags'] = part.flags
        # h['state'] = part.state
        # res = type("FrozenOrder", (object,), h)()

        # orders = dict()
        # old_order_id = None
        # for part in res.order_by('full_part_id').all():
        #     if part.order_id != old_order_id:
        #         old_order_id = part.order_id
        #         orders[old_order_id] = []
        #     orders[old_order_id].append(part)

        # session().commit()
        # return orders



    @RollbackDecorator
    def load_order_overview(self,date_begin,date_end):
        ret = session().query(Order).join(Customer).\
              filter( or_( ~Order.state.in_([OrderStatusType.preorder_definition, OrderStatusType.preorder_sent,
                                             OrderStatusType.order_definition, OrderStatusType.order_completed]),
                           and_( Order.state == OrderStatusType.order_completed,\
                                 Order.completed_date.between(date_begin,date_end)))).\
              options(joinedload_all(Order.parts, OrderPart.production_file,ProductionFile.operations),contains_eager(Order.customer)).\
              order_by(Customer.fullname,Order.order_id).all()

        # FIXME BUG without that I can't access the part.order field outside of
        # the session

        for order in ret:
            for part in order.parts:
                z = part.order

        session().close()
        return ret


    @RollbackDecorator
    def load_order_overview_past(self,date_begin,date_end):

        ret = session().query(Order).join(Customer).\
              filter( and_( Order.state == OrderStatusType.order_completed,\
                               Order.completed_date.between(date_begin,date_end))).\
              options(joinedload_all(Order.parts, OrderPart.production_file,ProductionFile.operations),contains_eager(Order.customer)).\
              order_by(Customer.fullname,Order.order_id).all()

        # FIXME BUG without that I can't access the part.order field outside of
        # the session

        for order in ret:
            for part in order.parts:
                z = part.order

        session().close()
        return ret

    @RollbackDecorator
    def load_all_ops_lazily(self,order_id):
        """ Preloads all active orders with their parts and their operations.
        The goal of this function is to get all these informations in one
        database query so we optimise speed """

        # The contains_eager statement refer to elements of the query() tuple.
        # outerjoin make sure we actually loads orders that have no operation
        # attached to them.

        # FIXME without the order_by on OrderPArt.ordering, the contains
        # eager loads the parts of an order OK, but in the wrong order
        # (which is strange because in the Order mapper, I clearly specify
        # to load in a specific order)

        return session().query(Order,OrderPart,ProductionFile).join(OrderPart).outerjoin(ProductionFile).outerjoin(Operation).filter(Order.order_id == order_id).options(contains_eager(Order.parts),contains_eager(OrderPart.production_file),contains_eager(ProductionFile.operations)).all()


    @RollbackDecorator
    def load_all_ops2(self):
        """ Preloads all active orders with their parts and their operations.
        The goal of this function is to get all these informations in one
        database query so we optimise speed """

        # The contains_eager statement refer to elements of the query() tuple.
        # outerjoin make sure we actually loads orders that have no operation
        # attached to them.

        # FIXME without the order_by on OrderPArt.ordering, the contains
        # eager loads the parts of an order OK, but in the wrong order
        # (which is strange because in the Order mapper, I clearly specify
        # to load in a specific order)

        return session().query(Order,OrderPart,ProductionFile).join(OrderPart).outerjoin(ProductionFile).outerjoin(Operation).join(Customer).filter(Order.state == OrderStatusType.order_ready_for_production).options(contains_eager(Order.parts),contains_eager(OrderPart.production_file),contains_eager(ProductionFile.operations)).order_by(Customer.fullname,Order.order_id,OrderPart.position).all()




    @RollbackDecorator
    def load_week_overview(self,start_date,end_date):
        # mainlog.debug(u"load_all_ops3() : between {} and {}".format(start_date,end_date))
        r = session().query(OrderPart,Order,Customer.fullname).join(Order).join(Customer).options(contains_eager(Order.parts)).filter(OrderPart.deadline.between(start_date,end_date)).order_by(OrderPart.deadline,Customer.fullname,Order.order_id).all()

        # r = map(lambda r: r + (r[0].deadline.isocalendar()[0],r[0].deadline.isocalendar()[1]), r)

        # for t in r:
        #     part,order,customer_name,year,week = t

        #     if year in (2013,) and week in (23,24,25):
        #         print part,order,customer_name,year,week

        session().close()
        return r


    @RollbackDecorator
    def load_quick_view(self,order_id):
        r = session().query(OrderPart).filter(OrderPart.order_id == order_id).all()
        ret = []
        for part in r:
            ret.append([part.human_identifier,part.description])
        session().commit()
        return ret

    @RollbackDecorator
    def customer_order_before(self,base_order_id,customer_id):

        order_id = session().query(Order.order_id).filter(and_(Order.customer_id == customer_id, Order.order_id < base_order_id)).order_by(desc(Order.order_id)).first()

        if order_id is None:
            order_id = session().query(Order.order_id).filter(and_(Order.customer_id == customer_id,Order.order_id > base_order_id)).order_by(desc(Order.order_id)).first()

        # Get the scalar
        if order_id:
            order_id = order_id[0]

        session().commit()
        return order_id



    @RollbackDecorator
    def customer_order_after(self,base_order_id,customer_id):
        order_id = session().query(Order.order_id).filter(and_(Order.customer_id == customer_id, Order.order_id > base_order_id)).order_by(asc(Order.order_id)).first()

        if not order_id:
            order_id = session().query(Order.order_id).filter(and_(Order.customer_id == customer_id, Order.order_id < base_order_id)).order_by(asc(Order.order_id)).first()

        # Get the scalar
        if order_id:
            order_id = order_id[0]

        session().commit()
        return order_id



    @RollbackDecorator
    def last_customer_order(self,customer_id):
        return session().query(Order).filter(Order.customer_id == customer_id).order_by(desc(Order.order_id)).first()



    @RollbackDecorator
    def order_before(self,base_order_id):
        order_id = session().query(Order.order_id).filter(Order.order_id < base_order_id).order_by(desc(Order.order_id)).first()
        if not order_id:
            order_id = session().query(Order.order_id).filter(Order.order_id > base_order_id).order_by(desc(Order.order_id)).first()

        # Get the scalar
        if order_id:
            order_id = order_id[0]

        session().commit()

        return order_id


    @RollbackDecorator
    def order_after(self,base_order_id):
        order_id = session().query(Order.order_id).filter(Order.order_id > base_order_id).order_by(asc(Order.order_id)).first()
        if not order_id:
            order_id = session().query(Order.order_id).filter(Order.order_id < base_order_id).order_by(asc(Order.order_id)).first()

        # Get the scalar
        if order_id:
            order_id = order_id[0]

        session().commit()

        return order_id


    @RollbackDecorator
    def active_order_before(self,base_order_id):
        """ The id of the active (in production) order right before
        (in order_id order, thus not accounting label because there's
        no specific order there) the one given in parameter.
        If none is found, then we take the latest active order (i.e. we loop).
        But still we may end up with no order at all...
        """

        order_id = session().query(Order.order_id).filter(and_(Order.state == OrderStatusType.order_ready_for_production,Order.order_id < base_order_id)).order_by(desc(Order.order_id)).first()

        if order_id is None: # 0 is OK though
            order_id = session().query(Order.order_id).filter(and_(Order.state == OrderStatusType.order_ready_for_production,Order.order_id > base_order_id)).order_by(desc(Order.order_id)).first()

        # Get the scalar
        if order_id:
            order_id = order_id[0]

        session().commit()

        return order_id


    @RollbackDecorator
    def active_order_after(self,base_order_id):
        """ Select the active order right after (in order_id order) the one
        given in parameter.
        If none is found, then we take the first active order (i.e. we loop).
        But still we may end up with no order at all...
        """

        order_id = session().query(Order.order_id).filter(and_(Order.state == OrderStatusType.order_ready_for_production,Order.order_id > base_order_id)).order_by(asc(Order.order_id)).first()

        if order_id == None:
            order_id = session().query(Order.order_id).filter(and_(Order.state == OrderStatusType.order_ready_for_production,Order.order_id < base_order_id)).order_by(asc(Order.order_id)).first()

        # Get the scalar
        if order_id:
            order_id = order_id[0]

        session().commit()

        return order_id

    @RollbackDecorator
    def active_orders(self):
        # I do this rather complicated select_fom because without that
        # (that is, with session.query(Order).join(Customer), SQLAlchemy
        # builds 2 join on the Customer table. That is rather strange.

        return session().query(Order).select_from(join(Order,Customer)).filter(Order.state == OrderStatusType.order_ready_for_production).order_by(Order.order_id).all()

    @RollbackDecorator
    def all(self):
        return session().query(Order).all()

    @RollbackDecorator
    def all_for_customer(self,customer):
        return session().query(Order).filter(Order.customer == customer).all()

    @RollbackDecorator
    def all_for_customer_as_dropdown(self,customer):
        return session().query(Order).filter(Order.customer == customer).values('order_id','description')

    @RollbackDecorator
    def id_exists(self, identifier):
        return len(session().query(Order).filter(Order.order_id == identifier).all()) > 0

    @RollbackDecorator
    def find_by_customer_name(self,customer_name):
        if not customer_name:
            return []

        return session().query(Order.order_id, Order.preorder_label, Order.accounting_label, Order.customer_order_name, Customer.fullname,Order.creation_date).filter(Order.customer_id == Customer.customer_id).filter(Customer.indexed_fullname.like(u"%{}%".format(text_search_normalize(customer_name)))).order_by(Customer.fullname,Order.order_id)[0:100]

    @RollbackDecorator
    def find_by_customer_order_name(self,order_number):
        if not order_number:
            return []

        return session().query(Order.order_id, Order.preorder_label, Order.accounting_label, Order.customer_order_name, Customer.fullname,Order.creation_date).filter(Order.customer_id == Customer.customer_id).filter(Order.indexed_customer_order_name.like(u"%{}%".format(text_search_normalize(order_number)))).order_by(Customer.fullname,Order.order_id)[0:100]

    @RollbackDecorator
    def find_by_id(self,identifier,resilient=False):
        q = session().query(Order).filter(Order.order_id == identifier)
        if not resilient:
            return q.one()
        else:
            return q.first()


    @RollbackDecorator
    def find_by_id_full_frozen(self, identifier):
        # join(documents_order_parts_table, documents_order_parts_table.c.order_part_id == OrderPart.order_part_id ).\
        # join(Document, documents_order_parts_table.c.document_id == Document.document_id).\
        # join(Customer).join(OrderPart).

        chrono_click("find_by_id_full_frozen-1")
        q = session().query(Order).\
            filter(Order.order_id == identifier).\
            options( joinedload(Order.parts, innerjoin=False),
                     joinedload(Order.parts, innerjoin=False).joinedload(OrderPart.documents, innerjoin=False),
                     joinedload(Order.customer) ).one()

        chrono_click("find_by_id_full_frozen-2")
        order = generic_access.freeze(q,commit=False,additional_fields=['parts','customer','customer_name'])
        chrono_click("find_by_id_full_frozen-3")
        order.parts = generic_access.freeze(q.parts,commit=False, additional_fields=['documents','quality_events'])
        chrono_click("find_by_id_full_frozen-4")
        order.customer = generic_access.freeze(q.customer,commit=False)
        chrono_click("find_by_id_full_frozen-5")

        order.customer_name = q.customer.fullname
        chrono_click("find_by_id_full_frozen-6")

        # Quick fix for documents. Ideally we'd like a recursive
        # freeze
        for i in range(len(q.parts)):
            # order.parts[i].documents = generic_access.freeze(q.parts[i].documents,commit=False)

            order.parts[i].documents = q.parts[i].documents
            for d in q.parts[i].documents:
                make_transient(d)
            # order.parts[i].documents = generic_access.freeze(q.parts[i].documents,commit=False)
            # mainlog.debug("find_by_id_full_frozen: frozen documents {}".format(len(order.parts[i].documents)))


            order.parts[i].quality_events = InstrumentedRelation()
            for qe in q.parts[i].quality_events:
                detached_qe = make_change_tracking_dto(QualityEvent, qe, recursive= {Document})
                # make_transient(qe)
                order.parts[i].quality_events.append(detached_qe)
            order.parts[i].quality_events.clear_changes()

        chrono_click("find_by_id_full_frozen-7")

        session().commit()
        chrono_click("find_by_id_full_frozen-8")

        return order




    @RollbackDecorator
    def find_by_id_frozen(self,identifier,resilient=False):
        # mainlog.debug("order_dao : find_by_id_frozen {}".format(identifier))

        # Since I freeze, I don't need the order parts => lazy load them
        q = session().query(Order,Customer.fullname).join(Customer).filter(Order.order_id == identifier).options(lazyload(Order.parts), lazyload(Order.customer))

        res = None
        if not resilient:
            res = q.one()
        else:
            res = q.first()

        if not res:
            return None
        else:
            res2 = freeze2(res[0])
            setattr(res2,"customer_name",res[1])
            return res2

    @RollbackDecorator
    def find_by_accounting_label(self,identifier,resilient=False):
        q = session().query(Order).filter(Order.accounting_label == identifier)
        if not resilient:
            return q.one()
        else:
            return q.first()

    @RollbackDecorator
    def find_by_preorder_label(self,identifier,resilient=False):
        q = session().query(Order).filter(Order.preorder_label == identifier)
        if not resilient:
            return q.one()
        else:
            return q.first()

    @RollbackDecorator
    def find_by_labels(self,identifier):
        # FIXME is the join on customer really necessary ? Maybe the relationship is automatically loaded
        q = session().query(Order.order_id, Order.preorder_label,Order.accounting_label,Order.customer_order_name,Customer.fullname,Order.creation_date).join(Customer).filter(or_(Order.preorder_label == identifier,Order.accounting_label == identifier))
        return q.all()


    @RollbackDecorator
    def recompute_position_labels(self,order):
        """ Recompute parts labels (A,B,...) on basis
        of parts positions.
        """

        ndx = 0
        for p in sorted(order.parts,key=lambda part:part.position):
            # mainlog.debug(p)
            # mainlog.debug("Has operation ? {}".format(p.has_operations()))

            if p.has_operations():
                p.label = position_to_letters(ndx)
                ndx += 1
            else:
                p.label = "-"

        # mainlog.debug("dao.recompute_position_labels -- done")

    CANNOT_DELETE_BECAUSE_ORDER_HAS_TIMETRACKS = 11 # Attention, more than one so we can compare to True !
    CANNOT_DELETE_BECAUSE_ORDER_IS_NOT_LAST = 12

    @RollbackDecorator
    def check_delete(self,order_id):
        result = None

        order = session().query(Order).filter(Order.order_id == order_id).one()
        # label = None

        if not order.accounting_label:
            # If it's not an accounting label then it's a preorder.
            result = True
            # label = order.preorder_label
        else:
            # label = order.accounting_label
            last_order_id = current_gaplessseq_value('order_id')
            if order.accounting_label == current_gaplessseq_value('order_id'):

                #mainlog.debug("Checking task action reports")

                # Count timetracks on that order
                nb_tars = session().query(TimeTrack).join(TaskOnOrder).filter(TaskOnOrder.order_id == order_id).count()
                nb_tars = nb_tars + session().query(TaskActionReport.task_action_report_id).join(TaskOnOrder).filter(TaskOnOrder.order_id == order_id).count()

                # Count task action reports on the operations of the order
                nb_tars = nb_tars + session().query(TimeTrack).join(TaskOnOperation).join(Operation).join(ProductionFile).join(OrderPart).join(Order).filter(Order.order_id == order_id).count()

                nb_tars = nb_tars + session().query(TaskActionReport.task_action_report_id).join(TaskOnOperation).join(Operation).join(ProductionFile).join(OrderPart).join(Order).filter(Order.order_id == order_id).count()


                if nb_tars > 0:
                    #mainlog.debug(nb_tars)
                    result = self.CANNOT_DELETE_BECAUSE_ORDER_HAS_TIMETRACKS
                else:
                    result = True
            else:
                result = self.CANNOT_DELETE_BECAUSE_ORDER_IS_NOT_LAST

        session().commit()
        return result


    CANNOT_DELETE_NONE_ORDER = 20

    @RollbackDecorator
    def delete(self,order_id):
        if order_id is None:
            raise Exception(CANNOT_DELETE_NONE_ORDER)
        else:
            #mainlog.debug(u"OrderDAO.delete : Deleting order id:{}".format(order_id))
            pass

            order = session().query(Order).filter(Order.order_id == order_id).one()
            session().delete(order)
            session().commit()


    @RollbackDecorator
    def find_last_one(self):
        return session().query(Order).order_by(desc(Order.order_id)).first()


    def clone(self,identifier):
        old = self.find_by_id(identifier)

        new_order = Order()
        new_order.description = old.description
        new_order.customer = old.customer

        new_parts = []
        for old_part in old.parts:
            new_part = OrderPart()
            new_part.num_part = old_part.num_part
            new_part.position = old_part.position
            new_part.description = old_part.description
            new_part.order = new_order
            new_parts.append(new_part)

        new_order.parts = new_parts

        session().add(new_order)
        return new_order




    @RollbackDecorator
    def load_order_timetracks(self,order_id):
        # Pay attention ! Since this query is quite big, I got correlation
        # issues. These were solved by disabling correlation on Operation.description

        # I was doing this query with the following joins and eager loading
        #    outerjoin(OrderPart).outerjoin(ProductionFile).outerjoin(Operation).outerjoin(Operation.task.of_type(TaskOnOperation)).outerjoin(TimeTrack).join(Customer).
        # eager loading :
        #    Operation.task.of_type(TaskOnOperation),\
        # But somehow, the query generated by SQLAlchemy is not friendly at all for postgres
        # Basically, it produces a join such as (see the JOIN "in" the left join ?) :
        # LEFT OUTER JOIN horse.operations ON horse.production_files.production_file_id = horse.operations.production_file_id
        # LEFT OUTER JOIN
        #        (horse.tasks JOIN horse.tasks_operations ON horse.tasks.task_id = horse.tasks_operations.task_id)
        #      ON horse.operations.operation_id = horse.tasks_operations.operation_id
        # LEFT OUTER JOIN horse.timetracks ON horse.tasks.task_id = horse.timetracks.task_id
        # That "in" join blinds the Postgres analyzer a bit and because of that
        # that join is done outside the other, resulting in full table scans...
        # So I've made things more explicit in the query below.

        timetracks = session().query(Employee.fullname,
                                     OrderPart.order_part_id,
                                     OperationDefinition.short_id,
                                     TimeTrack.start_time,
                                     TimeTrack.duration).\
            select_from(Order).\
            join(OrderPart).\
            join(ProductionFile).\
            join(Operation).\
            join(OperationDefinition).\
            join(TaskOnOperation).\
            join(Task).\
            join(TimeTrack).\
            join(Employee).\
            filter(Order.order_id == order_id).\
            order_by(OrderPart.position, Operation.position, Employee.fullname, OperationDefinition.short_id).\
            all()

        from collections import OrderedDict

        # 1 Part -> 1 Employee -> N Timetracks
        parts = OrderedDict()

        for tt in timetracks:

            if tt.order_part_id not in parts:
                parts[tt.order_part_id] = OrderedDict()

            employee_timetracks = parts[tt.order_part_id]

            if tt.fullname not in employee_timetracks:
                employee_timetracks[tt.fullname] = []

            employee_timetracks[tt.fullname].append( (tt.short_id, tt.start_time, tt.duration) )


        order = session().query(Order).filter(Order.order_id == order_id).one()

        res = []
        for part in order.parts:

            #res.append([part.human_identifier, part.description, part.state, part.completed_date, employee_timetracks])

            if part.order_part_id in parts:
                res.append([part.human_identifier, part.description, part.state, part.completed_date, parts[part.order_part_id], part.order_part_id ])
            else:
                res.append([part.human_identifier, part.description, part.state, part.completed_date, dict(),                    part.order_part_id ])



        # res = []
        # for part in order.parts:
        #     employee_timetracks = OrderedDict()

        #     for tt in order:

        #     for operation in part.operations:
        #         if operation.task:
        #             # mainlog.debug(operation)
        #             for timetrack in operation.task.timetracks:
        #                 if timetrack.employee.fullname not in employee_timetracks:
        #                     employee_timetracks[timetrack.employee.fullname] = []
        #                 employee_timetracks[timetrack.employee.fullname].append((operation.operation_model.short_id, timetrack.start_time))

        #     res.append([part.human_identifier, part.description, part.state, part.completed_date, employee_timetracks])

        obj = dict()
        obj['accounting_label'] = order.accounting_label
        obj['horse_order_id'] = order.order_id
        obj['preorder_label'] = order.preorder_label
        obj['creation_date'] = order.creation_date
        obj['completed_date'] = order.completed_date
        obj['customer_order_name'] = order.customer_order_name
        obj['customer_name'] = order.customer.fullname
        obj['state'] = order.state
        session().commit()

        return obj, res


    @RollbackDecorator
    def nb_operations_on_order(self, order_id):
        res = session().query(OrderPart.order_part_id).\
            join(ProductionFile).join(Operation).filter(OrderPart.order_id == order_id).count()
        session().commit()
        return res

    @RollbackDecorator
    def get_oldest_order_creation_date(self):
        return session().query( func.least( date.today(), func.min(Order.creation_date))).scalar()