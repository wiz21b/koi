# from pubsub import pub
import datetime

from sqlalchemy.sql.expression import desc,and_
from sqlalchemy.sql import func

from koi.Configurator import mainlog

from koi.datalayer.RollbackDecorator import RollbackDecorator
from koi.datalayer.types import DBObjectActionTypes
from koi.datalayer.generic_access import blank_dto, recursive_defrost_into, defrost_to_session, freeze, all_non_relation_columns
from koi.datalayer.database_session import session
from koi.datalayer.data_exception import DataException
from koi.datalayer.letter_position import position_to_letters

from koi.datalayer.audit_trail_service import audit_trail_service
from koi.translators import text_search_normalize

from koi.datalayer.supply_order_mapping import SupplyOrder, SupplyOrderPart, Supplier

from koi.datalayer.gapless_sequence import gaplessseq
from koi.datalayer.supply_order_query_parser import parse_supply_order_parts_query

from koi.datalayer.utils import split_horse_identifier

class SupplyOrderService(object):
    def __init__(self):
        pass

    MINIMUM_QUERY_LENGTH = 3
    MAX_RESULTS = 200


    def _columns_for_parts(self):
        columns = all_non_relation_columns(SupplyOrderPart)
        columns.append(Supplier.fullname.label('supplier_fullname'))
        columns.append(Supplier.supplier_id.label('supplier_id'))
        columns.append(SupplyOrder.expected_delivery_date.label('expected_delivery_date'))
        columns.append(SupplyOrder.accounting_label)
        columns.append(SupplyOrder.creation_date.label('creation_date'))
        return columns


    @RollbackDecorator
    def find_recent_parts(self):
        c = self._columns_for_parts()
        r = session().query(*c ).select_from(SupplyOrderPart).join(SupplyOrder).join(Supplier).filter(SupplyOrder.active == True).order_by(desc(SupplyOrder.accounting_label),SupplyOrderPart.position).limit(self.MAX_RESULTS).all()
        session().commit()
        return r


    @RollbackDecorator
    def find_recent_orders(self):

        # The query is a bit complicated, but that's the price to pay
        # to freeze stuff before returning it

        c = all_non_relation_columns(SupplyOrder)
        r = session().query(Supplier.fullname.label('supplier_fullname'), *c ).select_from(SupplyOrder).join(Supplier).filter(SupplyOrder.active == True).order_by(SupplyOrder.creation_date).limit(self.MAX_RESULTS).all()
        session().commit()
        return r


    @RollbackDecorator
    def find_parts_expression_filter(self,text):
        filter_expression = parse_supply_order_parts_query(text)

        columns = self._columns_for_parts()

        q = session().query(*columns).select_from(SupplyOrderPart).join(SupplyOrder).join(Supplier).order_by(SupplyOrder.creation_date)
        q = q.filter(filter_expression)

        if 'ORDERACTIVE' not in text.upper():
            q = q.filter(SupplyOrder.active == True)

        r = q.limit(self.MAX_RESULTS).all()

        return r

    @RollbackDecorator
    def find_parts_filtered(self,text):
        if not text:
            raise DataException(DataException.CRITERIA_IS_EMPTY)

        text = text.strip().upper()

        if not text:
            raise DataException(DataException.CRITERIA_IS_EMPTY)

        order_id, part_label = split_horse_identifier(text)

        if len(text) < self.MINIMUM_QUERY_LENGTH and (not order_id and not part_label):
            raise DataException(DataException.CRITERIA_IS_TOO_SHORT)



        order_part_match = []
        matches = []
        super_matches = []

        columns = self._columns_for_parts()

        q = session().query(*columns).select_from(SupplyOrderPart).join(SupplyOrder).join(Supplier).order_by(SupplyOrder.creation_date).filter(SupplyOrder.active == True)


        mainlog.debug("order_id={}, part_label={}".format(order_id, part_label))

        if order_id and not part_label:
            fq = q.filter(SupplyOrder.accounting_label == text).order_by(SupplyOrder.supply_order_id)
            for r in fq.all():
                super_matches.append( r )

        if order_id and part_label:
            fq = q.filter(and_(SupplyOrder.accounting_label == order_id, SupplyOrderPart.label == part_label))
            for r in fq.all():
                super_matches.append( r )


        if len(text) >= self.MINIMUM_QUERY_LENGTH:
            seen_order_part_ids = set()

            # Find by customer name

            fq = q.add_column(Supplier.indexed_fullname).filter(Supplier.indexed_fullname.like(u"%{}%".format(text_search_normalize(text)))).order_by(Supplier.fullname,desc(SupplyOrder.supply_order_id)).limit(self.MAX_RESULTS)

            for r in fq.all():
                matches.append( r )

            # Find by order part description

            fq = q.filter(SupplyOrderPart._indexed_description.ilike(u"%{}%".format(text_search_normalize(text)))).order_by(Supplier.fullname,desc(SupplyOrder.supply_order_id)).limit(self.MAX_RESULTS)

            for r in fq.all():
                matches.append( r )

        # Finally we order the matches to bring the most relevant
        # first. The "most relevant" is really a business order.

        res = super_matches + matches

        # Now we filter out the double entries

        unique_parts = []
        already_seen = set()
        for part in res:
            if part.supply_order_part_id not in already_seen:
                already_seen.add(part.supply_order_part_id)
                unique_parts.append(part)

        session().commit()

        return unique_parts

        # if len(unique_parts) > self.MAX_RESULTS:
        #     return True, unique_parts[0:self.MAX_RESULTS]
        # else:
        #     # False = there are not too many results
        #     return False, unique_parts







    # @RollbackDecorator
    # def find_filtered(self,text):
    #     """ Return a tuple (boolean, array of (frozen) supply orders)
    #     if the boolean is False it means that all the results of the
    #     search are in the array. If True, it means the search
    #     has brought too many results back and those are truncated.
    #     """

    #     import re
    #     re_label_identifier = re.compile("^[0-9]+$")

    #     if not text:
    #         raise DataException(DataException.CRITERIA_IS_EMPTY)

    #     text = text.strip().upper()

    #     if not text:
    #         raise DataException(DataException.CRITERIA_IS_EMPTY)

    #     if len(text) < self.MINIMUM_QUERY_LENGTH and not re_label_identifier.match(text):
    #         raise DataException(DataException.CRITERIA_IS_TOO_SHORT)



    #     order_part_match = []
    #     matches = []
    #     super_matches = []

    #     columns = all_non_relation_columns(SupplyOrder)
    #     columns.append(Supplier.fullname.label('supplier_fullname'))
    #     q = session().query(*columns).select_from(SupplyOrder).join(Supplier).order_by(SupplyOrder.creation_date)

    #     if re_label_identifier.match(text):

    #         # find by order's label

    #         fq = q.filter(SupplyOrder.supply_order_id == text).order_by(SupplyOrder.supply_order_id)

    #         for r in fq.all():
    #             super_matches.append( r )


    #     if len(text) >= self.MINIMUM_QUERY_LENGTH:
    #         seen_order_part_ids = set()

    #         # Find by customer name

    #         fq = q.add_column(Supplier.indexed_fullname).filter(Supplier.indexed_fullname.like(u"%{}%".format(text_search_normalize(text)))).order_by(Supplier.fullname,desc(SupplyOrder.supply_order_id)).limit(self.MAX_RESULTS + 1)

    #         for r in fq.all():
    #             matches.append( r )

    #         # Find by order part description

    #         fq = q.join(SupplyOrderPart).filter(SupplyOrderPart._indexed_description.ilike(u"%{}%".format(text_search_normalize(text)))).distinct(*columns).order_by(Supplier.fullname,desc(SupplyOrder.supply_order_id)).limit(self.MAX_RESULTS + 1)

    #         for r in fq.all():
    #             matches.append( r )

    #     # Finally we order the matches to bring the most relevant
    #     # first. The "most relevant" is really a business order.

    #     res = super_matches + matches

    #     session().commit()

    #     if len(res) > self.MAX_RESULTS:
    #         return True, res[0:self.MAX_RESULTS]
    #     else:
    #         # False = there are not too many results
    #         return False, res


    @RollbackDecorator
    def find_by_id(self, supply_order_id):
        if not supply_order_id:
            raise DataException("Invalid supply order id (none)",DataException.INVALID_PK)

        supply_order = session().query(SupplyOrder).filter(SupplyOrder.supply_order_id == supply_order_id).one()
        frz_order = freeze(supply_order,commit=False)
        frz_parts = freeze(supply_order.parts,commit=True)
        return frz_order,frz_parts

    @RollbackDecorator
    def find_order_parts_for_order(self, supply_order_id):
        c = all_non_relation_columns(SupplyOrderPart)
        return session().query(SupplyOrderPart).filter(SupplyOrderPart.supply_order_id == supply_order_id).all()


    @RollbackDecorator
    def save(self, order_dto, parts_actions):

        # mainlog.debug("-"*80)
        # for so in session().query(SupplyOrder).all():
        #     mainlog.debug(so.accounting_label)

        supply_order = recursive_defrost_into(order_dto, SupplyOrder, ['_indexed_description'])

        if not supply_order.supplier_id:
            raise Exception("Missing supply_order.supplier_id")

        if not supply_order.tags:
            supply_order.tags = []

        if not supply_order.accounting_label:
            supply_order.accounting_label = gaplessseq('supply_order_id')

        if not supply_order.creation_date:
            supply_order.creation_date = datetime.date.today()

        # if not supply_order.description:
        #     supply_order.description = ""

        session().flush() # grab the (generated) primary key
        self._update_supply_order_parts(parts_actions,supply_order) # MUST commit

        # pub.sendMessage('supply_order.changed')

        return supply_order.supply_order_id


    @RollbackDecorator
    def deactivate(self, supply_order_id):
        # AKA logical delete

        session().query(SupplyOrder).filter(SupplyOrder.supply_order_id == supply_order_id).update( {"active" : False},synchronize_session=False )
        session().commit()
        # pub.sendMessage('supply_order.deactivated')

    # @RollbackDecorator
    # def delete(self, supply_order_id):
    #     session().query(SupplyOrderPart).filter(SupplyOrderPart.supply_order_id == supply_order_id).delete()
    #     session().query(SupplyOrder).filter(SupplyOrder.supply_order_id == supply_order_id).delete()
    #     session().commit()

    #     pub.sendMessage('supply_order.changed')

    @RollbackDecorator
    def find_last_order_id(self, supplier_id):
        order_id = session().query(func.max(SupplyOrder.supply_order_id)).filter(SupplyOrder.supplier_id == supplier_id).scalar()
        session().commit()
        return order_id



    @RollbackDecorator
    def find_next_for_supplier(self, supply_order_id, supplier_id):
        if not supply_order_id:
            order_id = session().query(SupplyOrder.supply_order_id).filter(SupplyOrder.supplier_id == supplier_id).filter(SupplyOrder.active == True).first()
            if order_id:
                order_id = order_id[0]
        else:
            order_id = session().query(func.min(SupplyOrder.supply_order_id)).filter(and_(SupplyOrder.supplier_id == supplier_id, SupplyOrder.supply_order_id > supply_order_id)).filter(SupplyOrder.active == True).scalar()

            if not order_id:
                order_id = session().query(func.min(SupplyOrder.supply_order_id)).filter(and_(SupplyOrder.supplier_id == supplier_id, SupplyOrder.supply_order_id <= supply_order_id)).filter(SupplyOrder.active == True).scalar()

        session().commit()
        return order_id


    @RollbackDecorator
    def find_previous_for_supplier(self, supply_order_id, supplier_id):
        if not supply_order_id:
            order_id = session().query(SupplyOrder.supply_order_id).filter(SupplyOrder.supplier_id == supplier_id).filter(SupplyOrder.active == True).first()
            if order_id:
                order_id = order_id[0]
        else:
            order_id = session().query(func.max(SupplyOrder.supply_order_id)).filter(and_(SupplyOrder.supplier_id == supplier_id, SupplyOrder.supply_order_id < supply_order_id)).filter(SupplyOrder.active == True).scalar()

            if not order_id:
                order_id = session().query(func.max(SupplyOrder.supply_order_id)).filter(and_(SupplyOrder.supplier_id == supplier_id, SupplyOrder.supply_order_id >= supply_order_id)).filter(SupplyOrder.active == True).scalar()

        session().commit()
        return order_id


    def _find_by_id(self,supply_order_part_id):
        return session().query(SupplyOrderPart).filter(SupplyOrderPart.supply_order_part_id == supply_order_part_id).one()

    def _recompute_position_labels(self,order):
        """ Recompute parts labels (A,B,...) on basis
        of parts positions.

        The supply order given is a SQLAlchemy object
        """

        ndx = 0
        for p in sorted(order.parts,key=lambda part:part.position):
            p.label = position_to_letters(ndx)
            ndx += 1


    def _update_supply_order_parts(self,actions,supply_order):
        """ Pay attention ! This will update the action array to reflect the
        order part that were merged

        The object in the actions don't necessarily have to be
        SQLA mapped object, they can be frozen as well.
        """

        # FIXME replace supply_order by supply_order_id and merge
        # save supply order and update supply order parts

        # supply_order = session().query(SupplyOrder).filter(SupplyOrderPart.supply_order_id == supply_order_id).one()

        new_pos = 10000

        mainlog.debug("Reloading order parts into SQLA's session")

        for i in range(len(actions)):
            action_type,op,op_ndx = actions[i]
            if action_type == DBObjectActionTypes.TO_UPDATE:
                op = defrost_to_session(op,SupplyOrderPart)

            elif action_type == DBObjectActionTypes.UNCHANGED:

                # I don't use merge because merge will trigger
                # a copy of the attributes. Which will in
                # turn result in an UPDATE being performed.
                # And that is useless (since it is unchanged).
                # Moreover it makes testing a bit harder because
                # I have to think about the session to make
                # test cases.

                op = self._find_by_id(op.supply_order_part_id)

            elif action_type == DBObjectActionTypes.TO_CREATE:
                op = defrost_to_session(op,SupplyOrderPart)
                mainlog.debug("supply_order.supply_order_id = {}".format(supply_order.supply_order_id))
                op.supply_order_id = supply_order.supply_order_id
                op.position = new_pos
                new_pos += 1

            elif action_type == DBObjectActionTypes.TO_DELETE:
                # Yes, we do need to merge the "TO_DELETE" ones. Because
                # SQLA will check against what it has in session.
                # SO if the part we want to destroy is already
                # in session and op is the same part but is not in
                # session, then SQLA will complain
                # op = session().merge(op)
                op = self._find_by_id(op.supply_order_part_id)
                supply_order.parts.remove(op) # We need the delete to cascade !
                # session().delete(op)

            actions[i] = (action_type,op,op_ndx)

        mainlog.debug("At this point, there are {} parts in the order".format(len(supply_order.parts)))

        # Remember that when doing flush, nothing guarantees
        # that the DB statements will be sent to the DB
        # in the order there were done in Python. SQLA
        # may reorder them at will.

        # Handles positions : order far away

        pos = 100000
        for action_type,op,op_ndx in actions:
            if action_type != DBObjectActionTypes.TO_DELETE:
                op.position = pos
                pos += 1

        session().flush()

        # Handles positions : bring back in place

        pos = 1
        for action_type,op,op_ndx in actions:
            if action_type != DBObjectActionTypes.TO_DELETE:
                # mainlog.debug(u"reposition {} {}".format(pos,op.description))
                op.position = pos
                pos += 1

        session().flush()
        self._recompute_position_labels(supply_order)

        session().commit()

        for action_type,op,op_ndx in actions:
            if action_type == DBObjectActionTypes.TO_CREATE:
                audit_trail_service.record("CREATE_SUPPLY_ORDER_PART",str(op), op.supply_order_part_id)
            if action_type == DBObjectActionTypes.TO_UPDATE:
                audit_trail_service.record("UPDATE_SUPPLY_ORDER_PART",str(op), op.supply_order_part_id)
            elif action_type == DBObjectActionTypes.TO_DELETE:
                # !!! Order id ! because order part id doesn't make sense after a delete :-)
                audit_trail_service.record("DELETE_SUPPLY_ORDER_PART",str(op), supply_order.supply_order_id)


        mainlog.debug(u"update_supply_order_parts -- done")

        return actions


supply_order_service = SupplyOrderService()
