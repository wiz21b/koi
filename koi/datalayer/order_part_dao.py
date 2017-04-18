from datetime import date, timedelta
import logging
import re
from collections import OrderedDict
from functools import cmp_to_key

from sqlalchemy import and_, or_, String
from sqlalchemy.sql.expression import desc,cast,func

import koi.datalayer.generic_access as generic_access
from koi.Configurator import mainlog
from koi.configuration.business_functions import business_computations_service
from koi.datalayer.RollbackDecorator import RollbackDecorator
from koi.datalayer.audit_trail_service import audit_trail_service
from koi.datalayer.data_exception import DataException
from koi.datalayer.database_session import session
from koi.datalayer.quality import QualityEvent
from koi.datalayer.types import DBObjectActionTypes
from koi.db_mapping import Order,OrderPart,Customer,ProductionFile
from koi.db_mapping import OrderPartStateType,TimeTrack
from koi.db_mapping import TaskOnOperation, Operation, OperationDefinition, OperationDefinitionPeriod, Employee
from koi.db_mapping import defrost_into
from koi.doc_manager.documents_mapping import Document
from koi.translators import text_search_normalize
from koi.date_utils import day_period_to_ts, timestamp_to_pg, _last_moment_of_month,_first_moment_of_month, compute_overlap


def _freeze_order_part( sqla_part):
    p = generic_access.freeze(sqla_part,commit=False,additional_fields=['documents','quality_events','customer'])
    p.documents = generic_access.freeze(sqla_part.documents,commit=False,additional_fields=['category'])
    return p

def _freeze_order_parts(parts):
    new_parts = []
    for p in parts:
        new_parts.append( _freeze_order_part( p))
    return new_parts

class OrderPartDAO(object):

    ORDER_PART_SELECTION_ACTIVE_ORDERS = 1
    ORDER_PART_SELECTION_PREORDERS = 2
    ORDER_PART_SELECTION_ON_HOLD = 4
    ORDER_PART_SELECTION_COMPLETED_THIS_MONTH = 8
    ORDER_PART_SELECTION_ABORTED_THIS_MONTH = 16


    def __init__(self,session):
        pass

    def set_delivery_slip_dao(self, ds_dao):
        assert ds_dao
        self._delivery_slip_part_dao = ds_dao

    def make(self,order):
        part = OrderPart()
        part.order = order
        return part

    @RollbackDecorator
    def save(self,order_part):
        if order_part not in session():
            mainlog.debug(u"OrderPartDAO.save() order_part not in session")
            session().add(order_part)
        session().commit()

    @RollbackDecorator
    def find_youngest(self):
        max_id = session().query(func.max(OrderPart.order_part_id)).scalar()
        return self.find_by_id_frozen(max_id)

    @RollbackDecorator
    def find_by_id(self, identifier : int):
        assert identifier
        return session().query(OrderPart).filter(OrderPart.order_part_id == identifier).one()

    @RollbackDecorator
    def find_by_id_frozen(self,identifier):
        p = _freeze_order_part(self.find_by_id(identifier))
        session().commit()
        return p

    @RollbackDecorator
    def find_by_ids_frozen(self,identifiers):
        op = session().query(OrderPart).filter(OrderPart.order_part_id.in_(identifiers)).all()
        fp = _freeze_order_parts(op)
        session().commit()
        return fp

    @RollbackDecorator
    def find_by_order_id_frozen(self,order_id):
        op = session().query(OrderPart).filter(OrderPart.order_id == order_id).order_by(OrderPart.position).all()
        fp = _freeze_order_parts(op)
        session().commit()
        return fp

    @RollbackDecorator
    def find_by_order_id(self,order_id):
        """ Return tuples representing of the order parts corresponding to order_id
        """
        r = session().query(OrderPart.order_part_id).filter(OrderPart.order_id == order_id).order_by(OrderPart.position).all()
        session().commit()

        if r:
            return self.find_by_ids(map(lambda t:t[0],r))
        else:
            return []

    @RollbackDecorator
    def find_by_description(self,description):
        # calias = aliased(Customer)

        return session().query(Order.order_id, Order.preorder_label, Order.accounting_label, Order.customer_order_name, Customer.fullname, OrderPart.description, OrderPart.order_part_id, Order.creation_date, OrderPart.label).filter(OrderPart.order_id == Order.order_id).filter(Order.customer_id == Customer.customer_id).filter(OrderPart.indexed_description.ilike(u"%{}%".format(text_search_normalize(description)))).order_by(Customer.fullname,OrderPart.description)[0:100]



    @RollbackDecorator
    def find_by_full_id(self,identifier, commit=True):
        """ identifier such as 2769A where 2769 is the number of an order
        and A is the number of the order part.

        Will return up to 2 part id's (one part from an order, one from a
        preorder)
        """

        # FIXME Should rather throw an exception in this

        if not identifier:
            return []

        re_order_part_identifier = re.compile("^ *([0-9]+)([A-Z]+) *$")

        m = re_order_part_identifier.match(identifier)
        if not m:
            return []

        order_id = m.group(1)
        label = m.group(2)

        res = session().query(OrderPart.order_part_id, Order.preorder_label, Order.accounting_label, Order.order_id).join(Order).\
              filter(and_(or_(Order.preorder_label == order_id,
                              Order.accounting_label == order_id),
                          OrderPart.label == label)).all()

        # Give priority to orders over preorders

        def key_sort(p):
            k = 1000000000
            if p.accounting_label:
                k = 0
            return k + p.order_id

        if res:
            res = [t.order_part_id for t in sorted(res, key=key_sort)]

        if commit: session().commit()
        return res



    @RollbackDecorator
    def find_by_ids(self,ids):

        if not ids:
            return []

        res = session().query(Customer.fullname,
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
                              OrderPart.label,
                              OrderPart.state.label("part_state"),
                              Order.customer_order_name,
                              OrderPart.priority).\
            select_from(OrderPart).\
            join(Order).\
            join(Customer).filter(OrderPart.order_part_id.in_(ids)).all()


        # Avoid doubles in the given ids

        d = OrderedDict( map(lambda part_id: (part_id,None), ids))
        for part in res:
            d[part.order_part_id] = part

        # mainlog.debug(",".join(map(lambda part:str(part.order_part_id), d.values())))

        from koi.dao import dao
        res2 = dao.order_dao._reinject_human_time(list(d.values()))
        session().commit()
        return res2

        session().commit()
        return list(d.values())





    MINIMUM_QUERY_LENGTH = 3
    MAXIMUM_QUERY_LENGTH = 20
    MAX_RESULTS = 200

    @RollbackDecorator
    def find_ids_by_text(self,text):
        """ Return a tuple (boolean, array of order_part_id's)
        if the boolean is False it means that all the results of the
        search are in the array. If True, it means the search
        has brought too many results back and those are truncated.
        """

        if not text:
            raise DataException(DataException.CRITERIA_IS_EMPTY)

        text = text.strip().upper()

        if not text:
            raise DataException(DataException.CRITERIA_IS_EMPTY)

        if len(text) > OrderPartDAO.MAXIMUM_QUERY_LENGTH:
            raise DataException(DataException.CRITERIA_IS_TOO_LONG)

        import re

        # Label identifier will be cast to int so they must not be
        # too long ! So we limit the length of each part.
        re_order_part_identifier = re.compile("^([0-9]{1,6})([A-Z]{1,4})$")
        re_label_identifier = re.compile("^[0-9]{1,6}$")


        if len(text) < OrderPartDAO.MINIMUM_QUERY_LENGTH and not re_order_part_identifier.match(text) and not re_label_identifier.match(text):
            raise DataException(DataException.CRITERIA_IS_TOO_SHORT)

        order_part_match = []
        matches = []
        super_matches = []


        if re_order_part_identifier.match(text):

            # Look for an exact (and unique) match on the order part full identifier
            p = self.find_by_full_id(text)
            order_part_match = p

        if re_label_identifier.match(text):

            # 5050B
            # find by order's preorder/accounting label

            q = session().query(OrderPart.order_part_id,Order.preorder_label,Order.accounting_label,Order.order_id).join(Order).filter(or_(Order.preorder_label == text,Order.accounting_label == text)).order_by(Order.order_id,OrderPart.position)

            def key_sort(p):
                k = 1000000000
                if p.accounting_label:
                    k = 0
                return k + p.order_id

            # def part_sort(a,b):
            #     rank_a = +1
            #     if a.accounting_label:
            #         rank_a = -1

            #     rank_b = +1
            #     if b.accounting_label:
            #         rank_b = -1

            #     return cmp(rank_a,rank_b) or (- cmp(a.order_id,b.order_id))


            for r in sorted(q.all(), key=key_sort):
                super_matches.append( r.order_part_id ) # map(lambda t:t[0],r)

        if len(text) >= OrderPartDAO.MINIMUM_QUERY_LENGTH:
            seen_order_part_ids = set()

            # Find by customer name

            q = session().query(OrderPart.state,OrderPart.order_part_id,Order.order_id).join(Order).join(Customer).filter(Customer.indexed_fullname.like(u"%{}%".format(text_search_normalize(text)))).order_by(Customer.fullname,desc(Order.order_id),OrderPart.position)

            for r in q:
                if r.order_part_id not in seen_order_part_ids:
                    matches.append(r)
                    seen_order_part_ids.add(r.order_part_id)


            # Find by customer order ID

            q = session().query(OrderPart.state,OrderPart.order_part_id,Order.order_id).join(Order).join(Customer).filter(Order.indexed_customer_order_name.like(u"%{}%".format(text_search_normalize(text)))).order_by(Customer.fullname,desc(Order.order_id),OrderPart.position)

            for r in q:
                if r.order_part_id not in seen_order_part_ids:
                    matches.append(r)
                    seen_order_part_ids.add(r.order_part_id)


            mainlog.debug(u"search criteria : {}".format(text_search_normalize(text)))

            # Find by order part description

            q = session().query(OrderPart.state,OrderPart.order_part_id,Order.order_id).join(Order).join(Customer).filter(OrderPart.indexed_description.ilike(u"%{}%".format(text_search_normalize(text)))).order_by(Customer.fullname,desc(Order.order_id))

            for r in q:
                if r.order_part_id not in seen_order_part_ids:
                    matches.append(r)
                    seen_order_part_ids.add(r.order_part_id)

        # Finally we order the matches to bring the most relevant
        # first. The "most relevant" is really a business order.

        states_precendence = business_computations_service.order_states_precedence()
        def part_sort(a,b):
            return cmp(states_precendence.index(a.state), states_precendence.index(b.state)) \
                   or (- cmp(a.order_id,b.order_id))

        # def part_sort(a,b):
        #     return - cmp(a.order_id,b.order_id)

        res = order_part_match + super_matches + \
            [t.order_part_id for t in sorted(matches, key=cmp_to_key(part_sort))]

        session().commit()

        if len(res) > self.MAX_RESULTS:
            return True, res[0:self.MAX_RESULTS]
        else:
            # False = there are not too many results
            return False, res




    @RollbackDecorator
    def change_priority(self, order_parts_ids, priority):
        parts = session().query(OrderPart)\
                         .filter( OrderPart.order_part_id.in_(order_parts_ids)).all()

        for part in parts:
            part.priority = priority

        session().commit()


    # @RollbackDecorator
    # def change_order_part_state(self,order_id,order_part_id,state):
    #     self.change_order_parts_state(order_id,[order_part_id], state)


    @RollbackDecorator
    def order_parts_quantities_completed(self,order_id, order_parts_ids):
        """ Check if  the planned quantities of some of the parts of the order
        are actually done. Returns a sub set of order part's ids. Each
        member of the subset is a completed order part id. The subset is represented
        as a set of tuples. Each tuples combines the order part id and its
        human identifier.
        """

        # the check on order_id is actually there to make sure all
        # the order_parts belong to the same order

        data = session().query(OrderPart)\
                        .filter( and_( OrderPart.order_id == order_id,
                                       OrderPart.order_part_id.in_(order_parts_ids))).all()

        if len(data) != len(order_parts_ids):
            raise Exception("Some of order parts ({}) don't belong to order {}".format(order_parts_ids,order_id))

        # The check on the state is just defensive

        completed_ids = []
        completed_labels = []

        for order_part_id, qty, tex2, state in data:
            if order_part.state != OrderPartStateType.completed and order_part.tex2 >= order_part.qty:
                completed_ids.append( order_part.order_part_id )
                completed_labels.append( order_part.human_identifier )

        session().commit()
        return completed_ids,completed_labels



    @RollbackDecorator
    def _update_order_parts(self,actions,order,commit=True):
        """ Pay attention ! This will update the action array to reflect the
        order part that were merged

        The object in the actions don't necessarily have to be
        SQLA mapped object, they can be frozen as well.
        """

        new_pos = 10000

        mainlog.debug("Reloading order parts into SQLA's session")

        def merge_quality_events_full( quality_event_dtos, part_db):
            assert part_db in session()

            # Create and update
            for qe in quality_event_dtos:
                mainlog.debug(dir(qe))

                # Was it modified or created ?
                if qe.has_changed() or not qe.quality_event_id:
                    qe_session = generic_access.defrost_to_session(qe, QualityEvent)
                    qe_session.order_part_id = part_db.order_part_id
                    if not qe_session.quality_event_id:
                        part_db.quality_events.append(qe_session)
                else:
                    qe_session = session().query(QualityEvent).filter(QualityEvent.quality_event_id == qe.quality_event_id).one()
                    mainlog.debug("Quality event not, updated not created, so nothing to save, proceeding to documents")

                # Now merge in each document of the quality event
                for doc in qe.documents:
                    md = session().query(Document).filter(Document.document_id == doc.document_id).one()
                    # Set the category
                    mainlog.debug("Merging: category = {}".format(doc.document_category_id))
                    md.document_category_id = doc.document_category_id

                    if md not in qe_session.documents:
                        # But it is not associated to any order part
                        qe_session.documents.add(md)
                        mainlog.debug("Merged one document, now I have {} documents".format([str(d) for d in qe_session.documents]))
                        # FIXME Finish this for proper audit trail construction merged_docs.append(doc) # doc is not in the session, I prefer that (but not mandatory)

                # Delete documents
                deleted_ids = [doc.document_id for doc in qe.documents._deleted]
                if deleted_ids:
                    for doc in session().query(Document).filter( Document.document_id.in_(deleted_ids)).all():
                        # I do this to allow SQLAclhemy to update relationships.
                        # useing a  query(...).delete() won't work (see caveats in SQLAlchemy's doc)
                        session().delete(doc)


            # Delete
            deleted_ids = [qe.quality_event_id for qe in quality_event_dtos._deleted]
            if deleted_ids: # Avoid an SQLAlchemy warning on applying "in_" to an empty list
                mainlog.debug("********************************************** deleting {} ".format( deleted_ids ))
                for qe in session().query(QualityEvent).filter( QualityEvent.quality_event_id.in_(deleted_ids)).all():
                    # I do this to allow SQLAclhemy to update relationships.
                    # useing a  query(...).delete() won't work (see caveats in SQLAlchemy's doc)
                    session().delete(qe)


        def merge_documents( documents, part_db):
            """ Merge document into SQLA session.

            The following hypothesis is made. Any document that is
            associated to an order part is *first* uploaded and therefore,
            is present in the database as a Document entity before
            we do the association...

            part_in : order_part that comes from the GUI (not in SQLA session). It is usually a frozen object.
            part_db : the order_part which is in session
            """

            merged_docs = []
            # For all of this to work, the various cascade
            # must work...
            for doc in documents:

                assert doc.document_id, "A document without id ? That should never happen."

                # The document exist in our document database
                md = session().query(Document).filter(Document.document_id == doc.document_id).one()

                # Set the category
                mainlog.debug("MErging: category = {}".format(doc.document_category_id))
                md.document_category_id = doc.document_category_id

                if md not in part_db.documents:
                    # But it is not associated to any order part
                    part_db.documents.add(md)
                    merged_docs.append(doc) # doc is not in the session, I prefer that (but not mandatory)


            mainlog.debug("merge_documents : {} doc to check, {} doc after merge".\
                          format(len(documents), len(part_db.documents)))

            return merged_docs


        # Will be used for reporting. Associate parts to their "merged" documents
        merged_documents = [None] * len(actions)

        for i in range(len(actions)):
            action_type,op,op_ndx, quality_events_of_part = actions[i]

            if action_type == DBObjectActionTypes.TO_UPDATE:
                # quality_events = [qe for qe in op.quality_events]
                mainlog.debug("Reload ndx={} for update, order_part_id={}".format(i,op.order_part_id))
                dbop = session().query(OrderPart).filter(OrderPart.order_part_id == op.order_part_id).one()

                defrost_into(op,dbop,['indexed_description'])
                # We merge documents explicitely because defrost doesn't
                # work on relationships
                merged_documents[i] = merge_documents(op.documents, dbop)
                # merge_quality_events( quality_events_of_part, dbop)
                # delete_quality_events( quality_events_of_part._deleted)

                merge_quality_events_full( quality_events_of_part, dbop)
                op = dbop

            elif action_type == DBObjectActionTypes.UNCHANGED:

                # I don't use merge because merge will trigger
                # a copy of the attributes. Which will in
                # turn result in an UPDATE being performed.
                # And that is useless (since it is unchanged).
                # Moreover it makes testing a bit harder because
                # I have to think about the session to make
                # test cases.

                op = session().query(OrderPart).filter(OrderPart.order_part_id == op.order_part_id).one()
                merge_quality_events_full( quality_events_of_part, op)

            elif action_type == DBObjectActionTypes.TO_CREATE:
                op.position = new_pos

                # I merge docs because they are all already stored in the database
                # We just need to wire them to the order parts
                # SQLA doesn't properly merge the documents itself...

                # For some reason, if a handle a copy of oducments, when I set
                # op.documents to set(), then that copy is cleared as well. I bet
                # it's becuse that collection is instrumented by SQLA.
                # To avoid that, I make "deep copy".
                documents = [d for d in op.documents]

                op.documents = set()

                session().add(op) # The part will be automatically wired to the order
                op.order = order # after session.add or else SQLA complains

                merge_documents(documents, op)

                # merge_quality_events( quality_events_of_part, op)
                merge_quality_events_full( quality_events_of_part, op)

                # order.parts.append(op) # This won't work because parts relationship has not "save-update" cascade
                new_pos += 1

                merged_documents[i] = op.documents

            elif action_type == DBObjectActionTypes.TO_DELETE:
                # Yes, we do need to merge the "TO_DELETE" ones. Because
                # SQLA will check against what it has in session.
                # SO if the part we want to destroy is already
                # in session and op is the same part but is not in
                # session, then SQLA will complain
                # op = session().merge(op)
                op = session().query(OrderPart).filter(OrderPart.order_part_id == op.order_part_id).one()
                order.parts.remove(op) # We need the delete to cascade !
                # session().delete(op)

            actions[i] = (action_type,op,op_ndx,quality_events_of_part)

        mainlog.debug("At this point, there are {} parts in the order".format(len(order.parts)))

        # Align order_part states *if necessary*.
        # We say "if necessary" because there are in fact a bit more
        # to it. That is, if the order is simply modified by the
        # user, he might want to leave the current parts' states
        # as they are (in fact, our GUI forces that). OTOH, when
        # a user adds new parts to an already ongoing order
        # then we have to initialize their state.

        for action_type,op,op_ndx,quality_events_of_part in actions:
            mainlog.debug("Looking state of op #{} : {}".format(op_ndx,op.state))
            if action_type == DBObjectActionTypes.TO_UPDATE:
                # when we create, there's no state transition, the part is created.
                if not op.state: # only set unset state; leave set states as they are
                    # op.transition_state(OrderPartStateType.state_from_order_state(order.state))
                    assert op.order_part_id, "There was a failure in session handling"
                    business_computations_service.transition_part_state(op,
                                                                        business_computations_service.order_part_state_from_order_state(order.state))
                    mainlog.debug("Changed it to {}".format(op.state))

                # elif op.state == OrderPartStateType.completed:
                #     op.state = business_computations_service.infer_part_state( op)

        # Remember that when doing flush, nothing guarantees
        # that the DB statements will be sent to the DB
        # in the order there were done in Python. SQLA
        # may reorder them at will.

        # Handles positions : order far away

        pos = 100000
        for action_type,op,op_ndx,quality_events_of_part  in actions:
            if action_type != DBObjectActionTypes.TO_DELETE:
                op.position = pos
                pos += 1

        session().flush()

        # Handles positions : bring back in place

        pos = 1
        for action_type,op,op_ndx,quality_events_of_part in actions:
            if action_type != DBObjectActionTypes.TO_DELETE:
                # mainlog.debug(u"reposition {} {}".format(pos,op.description))
                op.position = pos
                pos += 1

        if commit:
            session().commit()
        else:
            session().flush()

        for i in range(len(actions)):
            action_type,op,op_ndx,quality_events_of_part  = actions[i]

            assert op.order_part_id, "audit trail must have a target" # if this is triggered, then something is wrong in object persisence
            if action_type == DBObjectActionTypes.TO_CREATE:
                audit_trail_service.record("CREATE_ORDER_PART",str(op), op.order_part_id)
            if action_type == DBObjectActionTypes.TO_UPDATE:
                doc_msg = ""
                if merged_documents[i]:
                    doc_msg = " - File added : " + ",".join( [doc.filename for doc in merged_documents[i]])
                audit_trail_service.record("UPDATE_ORDER_PART",str(op) + doc_msg, op.order_part_id)
            elif action_type == DBObjectActionTypes.TO_DELETE:
                # !!! Order id ! because order part id doesn't make sense after a delete :-)
                audit_trail_service.record("DELETE_ORDER_PART",str(op), order.order_id)


        mainlog.debug(u"update_order_parts -- done")

        return actions




    @RollbackDecorator
    def update_operations(self,actions,order_part,commit=True):
        # Each actions may contain an Operation-like (we heavily
        # rely on duck typing here) object


        # for k,v in session().identity_map.items():
        #     mainlog.debug("{} \t {}".format(k,type(v)))

        # session().flush()
        # session().expunge_all()
        # order_part = session().merge(order_part)

        mainlog.debug("update_operations : part = {}".format(order_part))

        if order_part.production_file is None:
            # FIXME Dirty fix
            pf = ProductionFile()
            session().add(pf)
            # order_part.production_file = [pf]

        elif len(order_part.production_file) == 0:
            pf = ProductionFile()
            session().add(pf)
            order_part.production_file.append(pf)

        elif len(order_part.production_file) > 0:
            # FIXME This is necessary for clone to work (this merges
            # a production file and the operations attached to it)
            # FIXME Dirty fix
            order_part.production_file[0] = session().merge(order_part.production_file[0])
        else:
            raise Exception("Ooops "*10)

        # mainlog.debug("update_operations : part = {}".format(order_part))

        # mainlog.debug(u"update_operations() : order_part is [{}] ".format(order_part))
        # mainlog.debug(u"actions are : {}".format(actions))

        # Pay attention, the update_operations is meant to
        # work on detached objects. However, SQLA likes to
        # get in when I access realtionships (for ex. op.task below).
        # Because of that I have to put back some stuff in the session
        # before handling it.


        # Apply delete operations. I do it first to reduce the risk
        # of having duplicate positions.

        for action_type,op,op_ndx in actions:
            if action_type == DBObjectActionTypes.TO_DELETE:
                if op.operation_id:

                    op = session().query(Operation).filter(Operation.operation_id == op.operation_id).one()

                    nb_tts = 0
                    for t in op.tasks:
                        nb_tts += len(t.timetracks)

                    if nb_tts == 0:
                        mainlog.debug("Deleting operation {} == {}".format(op.operation_id, op))
                        for o in order_part.production_file[0].operations:
                            mainlog.debug(u"   out of {}".format(o))

                        ops = order_part.production_file[0].operations

                        # session().delete(op) # Will cascade to the task
                        ops.remove(op) # Should trigger delete
                    else:
                        # Normally this error should be caught in the GUI
                        # before arriving here, but you never know...
                        raise DataException("One cannot delete an operation for which there is some work reported",
                                            DataException.CANNOT_DELETE_WHEN_OPERATIONS_PRESENT)
                else:
                    mainlog.warning("The operation you want to delete must exist in database (else the delete makes no sense)")


        session().flush() # Apply delete


        mainlog.debug("update operations : {} actions".format(len(actions)))

        position = 10000

        for i in range(len(actions)):

            action_type,op,op_ndx = actions[i]

            mainlog.debug("{}th operation : {}".format(i,op.description))

            # mainlog.debug("AGO Reloading {} [id:{}] {}".format(type(op.operation_model), op.operation_model or id(op.operation_model), op.operation_definition_id))

            # FIXME Not sure but I think that when I merge, SQLA reload
            # the operation_model based on the relationship (and not on the
            # operation_model_id). So I do some tricks here to force
            # the operation_model / operation_model_id to the proper
            # value (that is the one coming from the "actions")

            # opdef_id = op.operation_definition_id

            # if op not in session() and op.operation_id:
            #     mainlog.debug("Merging")
            #     op = session().merge(op)

            #     # we expect SQLA to merge the operation_definixtion as well (FIXME : why ?),
            #     # erasing the freshly set opdef id...
            #     # Force SQLA to update the operation model (merge can have changed it)
            #     op.operation_definition_id = opdef_id


            if action_type == DBObjectActionTypes.TO_CREATE:
                op = generic_access.defrost_to_session(op, Operation)
                op.production_file_id = order_part.production_file[0].production_file_id
                op.position = position
                position += 1
                mainlog.debug("Created  operation")
                actions[i] = (action_type,op,op_ndx)

            elif action_type == DBObjectActionTypes.TO_UPDATE:
                dbop = session().query(Operation).filter(Operation.operation_id == op.operation_id).one()
                defrost_into(op,dbop)
                op = dbop
                op.position = position
                position += 1
                mainlog.debug("Reloaded operation {} for update".format(op.operation_id))
                actions[i] = (action_type,op,op_ndx)

            elif action_type == DBObjectActionTypes.UNCHANGED:
                # I reload everything because I may need to update
                # the position field. I may also need to access
                # relationships.
                dbop = session().query(Operation).filter(Operation.operation_id == op.operation_id).one()

                op = dbop
                op.position = position
                position += 1
                mainlog.debug("Reloaded operation {} for delete".format(op.operation_id))
                actions[i] = (action_type,op,op_ndx)

            elif action_type == DBObjectActionTypes.TO_DELETE:
                pass # Already handled

            else:
                raise Exception("Unsupported action type : {}".format(action_type))

            # mainlog.debug("{} {} {}".format(action_type,op,op_ndx))

        session().flush() # Apply updates and creations, with offset positions


        # operations = order_part.production_file[0].operations
        # for action_type,op,op_ndx in actions:
        #     if action_type == DBObjectActionTypes.TO_UPDATE:
        #         for current_op in operations:
        #             if current_op.operation_id == op.operation_id:
        #                 current_op.position = op_ndx
        #     elif action_type == DBObjectActionTypes.TO_CREATE:
        #         op.production_file_id = order_part.production_file[0].production_file_id # each operation belongs to a ProductioFile (and it shouldn't FIXME)
        #         op.position = op_ndx
        #         session().add(op)
        #
        #         operations.insert()


        # pos = 10000
        # for action_type,op,op_ndx in actions:
        #     mainlog.debug("reorder operation positin {}".format(op_ndx))
        #     if action_type == DBObjectActionTypes.TO_CREATE:
        #         op.position = pos
        #         session().add(op)
        #         # This has sometimes triggered a flush which in turn
        #         # triggered "violates check constraint "position_one_based""
        #         order_part.production_file[0].operations.append(op)
        #
        #     if action_type != DBObjectActionTypes.TO_DELETE:
        #         pos += 1

        session().flush()

        # Now we reorder the operations
        # The following operations are efficient only if the
        # operations are all in the SQLA session. If not this will
        # result in lots of objects loads.

        # pos = 100000 # Make sure this doesn't collide with previously added
        # # operations' positions
        # for action_type,operation,op_ndx in actions:
        #     if action_type != DBObjectActionTypes.TO_DELETE:
        #         operation.position = pos
        #         pos += 1
        #
        # session().flush()

        # Operations were reordered, now we bring them into
        # place

        pos = 1
        for action_type,operation,op_ndx in actions:
            if action_type != DBObjectActionTypes.TO_DELETE:
                operation.position = pos
                pos += 1

        session().flush()

        if commit:
            session().commit()






    @RollbackDecorator
    def bulk_change_flags(self,bulk_changes):
        for order_part_id,month_goal in bulk_changes.iteritems():
            mainlog.debug("Bulk change order part : {} with {}".format(order_part_id,month_goal))
            part = self.find_by_id(order_part_id)
            part.flags = month_goal
        session().commit()
        return


    @RollbackDecorator
    def next_states_for_parts(self, order_parts_ids):
        all_states = map(lambda a:a[0],
                         session().query(OrderPart.state).filter(OrderPart.order_part_id.in_(order_parts_ids)).distinct().all())

        # We work backwards by starting with all possible states
        # and removing those which are not valid for some order part.

        authorized_states = OrderPartStateType.symbols()
        for state in all_states:

            next_states = business_computations_service.order_part_possible_next_states( state)

            for s in OrderPartStateType.symbols():
                if s not in next_states and s in authorized_states:
                    authorized_states.remove(s)

        session().commit()
        return authorized_states


    @RollbackDecorator
    def sort_part_id_on_order(self,order_parts_ids):
        res = session().query(OrderPart.order_id, OrderPart.order_part_id).filter(OrderPart.order_part_id.in_(order_parts_ids)).all()

        d = dict()
        for order_id,order_part_id in res:
            if order_id not in d:
                d[order_id] = []

            d[order_id].append(order_part_id)

        session().commit()
        return d



    def value_work_on_order_part_up_to_date(self,order_part_id,d):

        if order_part_id == 25268:
            mainlog.debug("value_work_on_order_part_up_to_date: {}".format(d))
            for tt in session().query(TimeTrack.start_time,TimeTrack.duration,OperationDefinition.description,OperationDefinitionPeriod.start_date,OperationDefinitionPeriod.end_date,OperationDefinitionPeriod.cost).\
                join(TaskOnOperation).\
                join(Operation).\
                join(ProductionFile).\
                join(OperationDefinition).\
                join(OperationDefinitionPeriod, OperationDefinitionPeriod.operation_definition_id == OperationDefinition.operation_definition_id).\
                join(OrderPart).\
                filter(and_(OrderPart.order_part_id == order_part_id,
                            TimeTrack.start_time <= d,
                            TimeTrack.start_time >= OperationDefinitionPeriod.start_date,
                            or_(OperationDefinitionPeriod.end_date == None,
                                TimeTrack.start_time <= OperationDefinitionPeriod.end_date))).all():
                mainlog.debug(tt)


        r = session().query(func.sum(TimeTrack.duration * OperationDefinitionPeriod.cost)).\
            join(TaskOnOperation).\
            join(Operation).\
            join(ProductionFile).\
            join(OrderPart).\
            join(OperationDefinition).\
            join(OperationDefinitionPeriod, OperationDefinitionPeriod.operation_definition_id == OperationDefinition.operation_definition_id).\
            filter(and_( OrderPart.order_part_id == order_part_id,
                         TimeTrack.start_time <= d,
                         TimeTrack.start_time >= OperationDefinitionPeriod.start_date,
                         or_(OperationDefinitionPeriod.end_date == None,
                             TimeTrack.start_time <= OperationDefinitionPeriod.end_date))).scalar()

        session().commit()
        # mainlog.debug(r)
        return r or 0


    @RollbackDecorator
    def work_done_on_part(self, order_part_id):

        res = session().query(Employee.fullname,
                              TimeTrack.duration,
                              TimeTrack.start_time,
                              OperationDefinition.short_id,
                              Operation.description). \
            select_from(TimeTrack).\
            join(TaskOnOperation). \
            join(Operation). \
            join(ProductionFile). \
            join(OrderPart).\
            join(OperationDefinition).\
            join(Employee, TimeTrack.employee_id == Employee.employee_id).\
            filter(OrderPart.order_part_id == order_part_id). \
            order_by(desc(TimeTrack.start_time)).all()

        session().commit()
        return res


    @RollbackDecorator
    def wip_valuation_over_time(self, begin, end) -> OrderedDict:
        """
        Compute WIP valuation over time for a given (begin, end) period.

        The computation is made day by day.
        The whole database history is taken into account because the computation
        is cumulative. SO, for example, to have the value on the first day,
        we must have all the data preceding that day.

        The computation is based on the states of the order part only. The
        fact that the parts are grouped in orders is not taken into account.

        Order parts which are aborted or completed are removed from the valuation
        as soon as they are aborted/completed. Parts which are in another state
        (notably 'paused') remain in the WIP valuation as long as their state
        allows it (<> completed/aborted). Therefore, if the user "forgets" an
        order part in state production pausd, this is valued indefintely
        (this can produce surprising result if the part stay for years
        in the valuation).

        Note that the valuation on a given day is completely independant of the
        computation period.

        :return: An OrderedDict mapping days to valuation. If no valuations, then an
        empty dict is returned.
        """

        debugged_part = 208184
        debugged_date = date(2017,2,28)
        self.debug_part_dates = []

        valuations = OrderedDict()
        begin,end = day_period_to_ts( begin, end)
        mainlog.debug("wip_valuation_over_time: From {} to {}".format(begin, end))


        # The goal of the following query is
        # 1. Gather all data about order part necessary for the computation
        #    formula (quantities, time spent, etc)
        # 2. Sum these quantities over time
        # 3. Select only order parts which participate in the valuation

        # The query is optimized with speed in mind. So it tries to
        # minimize th quantity of information returned by :
        # 1. Only retaining days where the *total* valuation of the parts
        #    will change (so if that valuation doessn't change on a given
        #    day, then this day is not returned.
        # 2. Remove data which are after the period of interest.
        # 3. Compress (by accumulation) the data before the period of interest.


        sql = """
        with
        events_q_out as (
        	select
        	   cast( date_trunc('day',s.creation) as date) as day,
        	   sp.order_part_id,
        	   sp.quantity_out
        	from delivery_slip_parts sp
        	join delivery_slip as s on s.delivery_slip_id = sp.delivery_slip_id
        	where s.active = true
        ),
        events_work as (
        	select
        	    cast( date_trunc('day', timetracks.start_time ) as date) as day,
        	    pf.order_part_id,
        	    timetracks.duration,
        	    timetracks.duration * coalesce(op_def_per.hourly_cost,0) as cost
        	from production_files pf
        	join operations op on op.production_file_id = pf.production_file_id
        	join tasks_operations on tasks_operations.operation_id = op.operation_id
        	join timetracks on timetracks.task_id = tasks_operations.task_id and timetracks.duration > 0
        	join operation_definitions opdef on opdef.operation_definition_id = op.operation_definition_id
        	left outer join operation_definition_periods op_def_per on
        	      op_def_per.operation_definition_id = opdef.operation_definition_id
        	      and timetracks.start_time >= op_def_per.start_date
        		  and (op_def_per.end_date is null or timetracks.start_time <= op_def_per.end_date)
        ),
        exceptional_quantities as (
            select orders.creation_date as day, order_parts.order_part_id, order_parts.tex as quantity_out
            from order_parts
            join orders on orders.order_id = order_parts.order_id
            where order_parts.tex > 0
        ),
        all_events_untranslated as (
             -- we're interested in what happens for a given part on a given day.
             -- for that, we collapse all data on each days (so if we have 1 qty out
             -- and one done hour on the same day, then they both must appear on the
             -- same row). That's why we sum over grouped dates.
        	select day, order_part_id, sum(quantity_out) as quantity_out, sum(duration) as done_hours, sum(cost) as done_hours_cost
        	from (
        		select day, order_part_id, quantity_out, 0 as duration, 0 as cost
        		from events_q_out
        		union all
        		select day, order_part_id, 0, duration, cost
        		from events_work
        		union all
        		select day, order_part_id, quantity_out, 0 as duration, 0 as cost
        		from exceptional_quantities
        	) merged_data
        	-- filter out useless events. Do that early to remove as much computations
        	-- as possible. Attention, this optimisation works *only* if the
        	-- completed part is greater than the max(timetracks/slip dates).
        	-- see note below
        	-- where day <= date '{}'
        	group by order_part_id, day
        ),
        all_events as (
            -- select greatest( day, date '{}') as day, order_part_id, quantity_out, done_hours, done_hours_cost
            select day, order_part_id, quantity_out, done_hours, done_hours_cost
            from all_events_untranslated
        ),
        active_parts as (
            -- determine which parts must participate in the computation of the valuation
            -- this is based on events as well as statuses of the parts.
            -- here we only take into account the parts which have either
            -- delivered quantities or time spent on them.
            select order_parts.order_part_id, periods.finish, periods.start
            from (
                -- We figure out the moment on which an order part is out of the valuation
                -- This is what we call the finish date
                -- there are problems here
                -- imagine this : completed_date = 10 january, and with have 2 events 5 january and 15 january
                -- if we look for WIP on period 1 -> 15 january, then the last day is max(completed, 15/1) => 15 january
                -- if we look for WIP on period 1 -> 14 january, then the last day is max(completed, 5/1) => 10 january
                --    which is wrong because we forget 5 days (from 11 to 15 january)...
                -- but the problem is that the completed date doesn't correspond to the timetracks.
                -- completed date should be greater than the latest timetrack/slip and it seems
                -- it's not alwyas the case (data quality issue :-( )...
                -- so filtering out events that are beyond the end of the computed WIP period
                -- is quite difficult because we have the risk of forgetting a period betwwen the last
                -- event in the wip period and the first event after the wip period.
                select all_events.order_part_id,
                       least( orders.creation_date, min(day)) as start, -- !!! the first day *should* be after the creation_date but somestimes data quality says the opposite
                       case order_parts.state
                          when 'aborted' then order_parts.completed_date
                          when 'completed' then greatest( order_parts.completed_date, max(day))
                          else date '{}'
                          end as finish
                from all_events
                join order_parts on order_parts.order_part_id =  all_events.order_part_id
                join orders on orders.order_id = order_parts.order_id
                group by all_events.order_part_id, orders.creation_date, order_parts.completed_date, order_parts.state
                order by all_events.order_part_id) periods
            join order_parts on order_parts.order_part_id = periods.order_part_id
            where      periods.start <= date '{}' -- doesn't start after the end of the period
                  and (periods.finish is null or periods.finish  >= date '{}') -- doesn't end before the end of the period
        ),
        extended_events as (
        	  select day, order_part_id, sum(quantity_out) as quantity_out, sum(done_hours) as done_hours, sum(done_hours_cost) as done_hours_cost
        	  from (
	            -- Keep in mind that it must *not* be necessary to have work/delivery slips
	            -- to take the part into account in the valuation. That's because at this
	            -- point it's better not to make any assumptions on how the absence of
	            -- work/delivery is taken into account in the valuation formula (the formula
	            -- might count something for those parts, even if they have no work/slips).
	            select          day,  order_part_id, quantity_out, done_hours, done_hours_cost
	            from all_events
	            union
	            select start as day,  order_part_id, 0 as quantity_out, 0 as done_hours, 0 as done_hours_cost
	            from active_parts
	            union
	            select finish as day, order_part_id, 0 as quantity_out, 0 as done_hours, 0 as done_hours_cost
	            from active_parts) data
    	      group by day, order_part_id
        )
        select
            extended_events.order_part_id,
            day,
            -- We use the fact that this specific partition will accumulate values in its series.
            -- See postgresql doc about those partitions.
            sum( extended_events.quantity_out)    over (partition by extended_events.order_part_id  order by extended_events.day) quantity_out,
            sum( extended_events.done_hours)      over (partition by extended_events.order_part_id  order by extended_events.day) done_hours,
            sum( extended_events.done_hours_cost) over (partition by extended_events.order_part_id  order by extended_events.day) done_hours_cost
        from extended_events
        join active_parts on active_parts.order_part_id = extended_events.order_part_id
        order by order_part_id, day asc -- This ordering is crucial for the python part.
                """.format(timestamp_to_pg(end),
                           timestamp_to_pg(begin - timedelta(days=1)),
                           timestamp_to_pg(end),
                           timestamp_to_pg(end), timestamp_to_pg(begin),
                           timestamp_to_pg(end))

        mainlog.debug(sql)

        r = session().connection().execute(sql).fetchall()


        if len(r) == 0:
            i = date(begin.year, begin.month, begin.day)
            end = date(end.year, end.month, end.day)
            while i <= end:
                valuations[i] = 0
                i = i + timedelta(days=1)

        elif len(r) > 0:

            # We build a vlauation smap. It maps a day to
            # the sum of valuations for that day

            first_date = date(begin.year, begin.month, begin.day)
            # Preinitialise the mapping so that we don't have to check
            # for the existence of a given date before adding items.
            # first_date = min([row.day for row in r])
            i = first_date
            end = date(end.year, end.month, end.day)
            while i <= end:
                valuations[i] = 0
                i = i + timedelta(days=1)

            # i = date(end.year, end.month, end.day)
            # while i >= first_date:
            #     valuations[i] = 0
            #     i = i + timedelta(days=-1)

            # We'll need quick access to parts
            parts = dict()

            all_ids = list(set([row.order_part_id for row in r]))  # list/set to compress the array

            # We preload all the parts that participate in the valuation of WIP

            # We use a step because the IN clause doesn't accept as many integer as we want.
            step = 100
            ndx = 0
            while ndx < len(all_ids):
                parts_ids = set(all_ids[ndx:ndx + step])
                for part in session().query(OrderPart).filter(OrderPart.order_part_id.in_(parts_ids)).all():
                    parts[part.order_part_id] = part
                    # mainlog.debug("Part {} completed_date = {}".format(part.order_part_id, part.completed_date))
                ndx += step

            # Now we compute the sum of valuations on each day

            last_date = None
            last_valuation = 0
            last_order_part_id = None

            if mainlog.level == logging.DEBUG:
                mainlog.debug("valution_production_chart: query complete {} rows must be computed".format(len(r)))
                # mainlog.debug( sorted(list(set([row.order_part_id for row in r]))))
                self._debug_active_orders = sorted(set([part.order_id for part in parts.values()]))
                self._debug_active_order_parts = sorted(set([part.order_part_id for part in parts.values()]))

            stats = 0

            global_row_ndx = 0

            while global_row_ndx < len( r):

                # We consume all the rows belonging to the same order part
                # We make the assumption that there are always at least
                # 2 rows per order part.

                part_rows = [ r[ global_row_ndx] ]
                global_row_ndx += 1

                # assert part_rows
                # if global_row_ndx > len(r) - 1 or global_row_ndx not in r:
                #     mainlog.debug("{}/{}".format(global_row_ndx, len(r)))

                while global_row_ndx < len(r) and part_rows[0].order_part_id == r[global_row_ndx].order_part_id:
                    part_rows.append( r[global_row_ndx])
                    global_row_ndx += 1

                # we have now consumed all the rows for the order_part_id

                part = parts[ part_rows[ 0].order_part_id]

                if part.order_part_id == debugged_part:
                    for x in part_rows:
                        mainlog.debug("in stock : {}".format(x))

                for row_ndx in range( len( part_rows) - 1): # Thus will stop at len(r) - 2

                    row = part_rows[row_ndx]
                    row_next = part_rows[row_ndx + 1]

                    if part.sell_price > 0:
                        valuation = business_computations_service.encours_on_params(
                            int(row.quantity_out), part.qty, row.done_hours, part.total_estimated_time,
                            float(part.sell_price), part.material_value, row.order_part_id, row.day
                        )
                    else:
                        valuation = row.done_hours_cost

                    p_end = row_next.day - timedelta(days=1)

                    # if not compute_overlap( row.day, p_end, first_date, end):
                    #     mainlog.debug("{} {} / {} {}".format(row.day, p_end, first_date, end))
                    #     for r in part_rows:
                    #         mainlog.debug(str(r))

                    o = compute_overlap( row.day, p_end, first_date, end)
                    if o:
                        i, end_o = o

                        if part.order_part_id == debugged_part:
                            # for x in part_rows:
                            mainlog.debug("deb part {} : {} {} --> {} {} --> {} {}, valuation {}".format(
                                part.order_part_id, row.day, row_next.day, row.day, p_end, i, end_o, valuation))

                        if row.day == date(2017,2,28):
                           self.debug_part_dates.append(row.order_part_id)

                        while i <= end_o:
                            valuations[i] += valuation
                            i += timedelta(days=1)

                # The last row is a special case.
                # Indeed, the last row is the last day on which there's an
                # event for the order part id in the period. We're sure of that
                # because when we construt events, we introduce an event for
                # the end of the period. In other word, there will alwyas
                # be an event on the last day of the period over which we
                # compute the WIP valuation.
                #
                # Since it's the last event, the valuation
                # must be computed at its point too. That's what we do here.

                row = part_rows[-1]
                if first_date <= row.day <= end:
                    if part.sell_price > 0:
                        valuation = business_computations_service.encours_on_params(
                            int(row.quantity_out), part.qty, row.done_hours, part.total_estimated_time,
                            float(part.sell_price), part.material_value, row.order_part_id, row.day
                        )
                    else:
                        valuation = row.done_hours_cost

                    valuations[row.day] += valuation
                    if row.day == date(2017, 2, 28) and row.order_part_id == debugged_part:
                        self.debug_part_dates.append( row.order_part_id )

                #
                # if row.day == debugged_date:
                #     mainlog.debug("Special date {}, {}".format(debugged_date, row.order_part_id))
                #
                # # if stats % 1000 == 0:
                # #     mainlog.debug("{} rows computed".format(stats))
                # # stats += 1
                #
                # # mainlog.debug("Row {}".format(row))
                #
                # # We go one order part at a time
                # if last_order_part_id != row.order_part_id:
                #     last_order_part_id = row.order_part_id
                #     last_date = None
                #     last_valuation = 0
                #
                # part = parts[row.order_part_id]
                #
                # if last_date:
                #
                #     # Copy the last valuation over several days because it's constant
                #     # on that period.
                #
                #     # We determine the range of dates given by the valuation points
                #     # and then we constrain it to the period we compute the valuation for
                #     i = max( first_date, last_date + timedelta(days=1))  # skip last date, it's already accounted for.
                #     i_end = min( end, row.day - timedelta(days=1))
                #
                #     if row.order_part_id == 113659:
                #         mainlog.debug("valuation on for {} from  {} to {}".format(
                #             last_order_part_id, i, i_end))
                #
                #     while i <= i_end:  # Don't go till new date, it will be accounted for afterwards.
                #         # if i == date(2018, 3, 31):
                #         # mainlog.debug("valuation on  {} for order part {} is {}".format(i, last_order_part_id, last_valuation))
                #         # mainlog.debug("{},{}".format(row.order_part_id, last_valuation))
                #         valuations[i] += last_valuation
                #
                #         if part.order_part_id == debugged_part:
                #             mainlog.debug("{} : + {} - {}".format(part.order_part_id, i, last_valuation))
                #
                #         i = i + timedelta(days=1)
                #
                # # mainlog.debug("Valuation step 1 unit price {}".format(part.sell_price))
                #
                #
                # if part.sell_price > 0:
                #     # if True or part.order_part_id == 115984:
                #     #     mainlog.debug( "new [{}] {}".format( row.day,
                #     #         (int(row.quantity_out), part.qty, row.done_hours, part.total_estimated_time, float(part.sell_price), part.material_value, row.order_part_id, row.day)))
                #
                #     last_valuation = business_computations_service.encours_on_params(
                #         int(row.quantity_out), part.qty, row.done_hours, part.total_estimated_time,
                #         float(part.sell_price), part.material_value, row.order_part_id, row.day
                #     )
                #
                #     # if True or part.order_part_id == 115984:
                #     #     mainlog.debug("new is --> {}".format(last_valuation))
                #
                # else:
                #     last_valuation = row.done_hours_cost
                #
                # # mainlog.debug("{}, {}".format(row.order_part_id,last_valuation))
                # # mainlog.debug("Valuation {}".format(last_valuation))
                #
                # if first_date <= row.day <= end: # This is not an optimisation, it's needed for the calculation
                #     if part.order_part_id == debugged_part:
                #         mainlog.debug("{} : {} - {}".format(part.order_part_id, row.day, last_valuation))
                #
                #     # if row.day == date(2018,3,31):
                #     #     # mainlog.debug("On basis of {}".format( (row.quantity_out, part.qty, row.done_hours, part.total_estimated_time, part.sell_price, part.material_value, row.order_part_id, row.day) ))
                #     #     # mainlog.debug("the valuation on {} for {} is {}".format(row.day, row.order_part_id, last_valuation))
                #     #     mainlog.debug("{},{}".format(row.order_part_id, last_valuation))
                #     valuations[row.day] += last_valuation
                #
                # last_date = row.day
                #
                # # for k in sorted(valuations.keys()):
                # #     mainlog.debug("{} {}".format(k,valuations[k]))
                #
                # # mainlog.debug("valution_production_chart - 2")

            return valuations


    @RollbackDecorator
    def compute_turnover_on( self, month_date : date):
        """ Turnover for a given month. The turnover is made
        of three parts :

            turnover = realised value + current WIP value - past month's WIP value

        with :
        * realised value = value of quantities delivered (i.e. for which there
          are delivery slips) this month
        * current WIP valuation = WIP value of this month
        * past month's WIP valuation = WIP value at the very end of the previous month

        Note that if no realised value was made, then the turnover depends
        on the WIP valuations delta. And that may be negative if the current
        WIP if smaller than the past one. That can happen if orders are cancelled
        in this month (so the WIP decreases, but to delivery slips are written).
        In that case, we bound the turnover to 0.
        """

        month_before = month_date - timedelta(month_date.day)

        ts_begin = _first_moment_of_month(month_date)
        ts_end = _last_moment_of_month(month_date)

        billable_amount_on_slips = self._delivery_slip_part_dao.compute_billable_amount(ts_begin, ts_end)

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

        # we're interested in the previous month so we extend the period by one day
        valuations = self.wip_valuation_over_time( ts_begin - timedelta(days=1), ts_end)

        encours_this_month = valuations[ts_end.date()]
        encours_previous_month = valuations[ month_before]
        turnover = billable_amount_on_slips + encours_this_month - encours_previous_month

        if turnover < 0:
            turnover = 0

        return billable_amount_on_slips, encours_this_month, encours_previous_month, turnover
