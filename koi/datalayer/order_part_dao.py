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
        # mainlog.debug("value_work_on_order_part_up_to_date: {}".format(d))
        # for tt in session().query(TimeTrack.start_time,TimeTrack.duration,OperationDefinition.description,OperationDefinitionPeriod.start_date,OperationDefinitionPeriod.end_date,OperationDefinitionPeriod.cost).join(TaskOnOperation).\
        #     join(Operation).\
        #     join(OperationDefinition).\
        #     join(OperationDefinitionPeriod, OperationDefinitionPeriod.operation_definition_id == OperationDefinition.operation_definition_id).\
        #     join(ProductionFile).\
        #     join(OrderPart).filter(and_(OrderPart.order_part_id == order_part_id,
        #                                 TimeTrack.start_time <= d,
        #                                 TimeTrack.start_time >= OperationDefinitionPeriod.start_date,
        #                                 or_(OperationDefinitionPeriod.end_date == None,
        #                                     TimeTrack.start_time <= OperationDefinitionPeriod.end_date))).all():
        #     mainlog.debug(tt)


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
