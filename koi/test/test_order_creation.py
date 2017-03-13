import unittest
from unittest import skip
import logging

import datetime
from datetime import date
import hashlib
from collections import OrderedDict
from sqlalchemy.sql.expression import desc

from koi.test.test_base import TestBase
from koi.db_mapping import *
from koi.dao import *
from koi.Configurator import mainlog

from koi.datalayer.types import DBObjectActionTypes
from koi.junkyard.sqla_dict_bridge import InstrumentedRelation

class TestOrderCreation(TestBase):

    def test_added_part_state_and_date_properly_set(self):

        order = self._order_dao.make(u"Test order"+chr(233),self.customer)
        self._order_dao.save(order)

        order_part1 = self._order_part_dao.make(order)
        order_part1.description = u"Part 1" + chr(233)
        order_part1.position = 1
        order_part1.state = OrderPartStateType.preorder # In line with the order
        self._order_part_dao.save(order_part1)

        order.parts[0].qty = 10
        session().commit()

        # order is a preorder now beacuse that's how they are initially
        self.assertEqual(OrderStatusType.preorder_definition, order.state)

        order_part2 = self._order_part_dao.make(order)
        order_part2.description = u"Part 2"
        order_part2.position = 2
        order_part2.state = OrderPartStateType.completed # In line with the order
        order_part2.completed = date.today()
        self._order_part_dao.save(order_part2)

        order_part3 = OrderPart()
        order_part3.description = u"Part new" + chr(233)

        actions = [
            ( (DBObjectActionTypes.UNCHANGED,order_part1,0,InstrumentedRelation()), None),
            ( (DBObjectActionTypes.UNCHANGED,order_part2,1,InstrumentedRelation()), None),
            ( (DBObjectActionTypes.TO_CREATE,order_part3,2,InstrumentedRelation()), None) ]

        order = self._order_dao.update_order(order.order_id,
                                             order.customer_id, order.customer_order_name, "preordername", OrderStatusType.order_ready_for_production,
                                             comments=None,
                                             estimate_sent_date=None,
                                             parts_results=actions)

        self.assertEqual( OrderPartStateType.ready_for_production, order.parts[0].state)
        assert order.parts[0].completed_date == None
        self.assertEqual( OrderPartStateType.ready_for_production, order.parts[1].state)
        self.assertEqual( "Part 2", order.parts[1].description)
        assert order.parts[1].completed_date == None
        self.assertEqual( OrderPartStateType.ready_for_production, order.parts[2].state)
        assert order.parts[2].completed_date == None



    def test_added_part_state_properly_set(self):

        order = self._order_dao.make(u"Test order"+chr(233),self.customer)
        self._order_dao.save(order)

        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 1" + chr(233)
        order_part.position = 1
        order_part.state = OrderPartStateType.preorder # In line with the order
        self._order_part_dao.save(order_part)

        order.parts[0].qty = 10
        session().commit()

        # order is a preorder now beacuse that's how they are initially
        self.assertEqual(OrderStatusType.preorder_definition, order.state)

        # -----------------------------------------------------------

        # self._order_dao.change_order_state(order.order_id, OrderStatusType.order_ready_for_production)

        order_part = OrderPart()
        order_part.description = u"Part 2" + chr(233)

        # actions = [(DBObjectActionTypes.TO_CREATE,order_part,2)]
        # self._order_part_dao.update_order_parts(actions,order)

        # actions = OrderedDict()
        # actions[ (DBObjectActionTypes.TO_CREATE,order_part,2) ] = []

        actions = [
            ( (DBObjectActionTypes.TO_CREATE,order_part,2,InstrumentedRelation()), None) ]





        # Changing the order state + adding a part
        # The part state must be set accordingly

        order = self._order_dao.update_order(order.order_id,
                                             order.customer_id, order.customer_order_name, "preordername", OrderStatusType.order_ready_for_production,
                                             comments=None,
                                             estimate_sent_date=None,
                                             parts_results=actions)

        # The order state was changed
        self.assertEqual(OrderStatusType.order_ready_for_production, order.state)

        # TO_CREATE worked fine
        assert len(order.parts) == 2

        # Check the "TO_CREATE" gave the new state for the order
        self.assertEqual( OrderPartStateType.ready_for_production, order.parts[1].state)
        assert order.parts[1].completed_date == None

        # And changed the already present part as well
        self.assertEqual( OrderPartStateType.ready_for_production, order.parts[0].state)
        assert order.parts[0].completed_date == None

        # -----------------------------------------------------------

        # self._order_dao.change_order_state(order.order_id, OrderStatusType.order_aborted)

        order_part = OrderPart()
        order_part.description = u"Part 3" + chr(233)


        # actions = OrderedDict()
        # actions[ (DBObjectActionTypes.TO_CREATE,order_part,3) ] = []

        actions = [
            ( (DBObjectActionTypes.TO_CREATE,order_part,3,InstrumentedRelation()), None) ]

        order = self._order_dao.update_order(order.order_id,
                                             order.customer_id, order.customer_order_name, "preordername", OrderStatusType.order_aborted,
                                             comments=None,
                                             estimate_sent_date=None,
                                             parts_results=actions)


        assert len(order.parts) == 3
        assert order.parts[0].state == OrderPartStateType.aborted
        assert order.parts[1].state == OrderPartStateType.aborted
        assert order.parts[2].state == OrderPartStateType.aborted

        self.assertEqual( date.today(), order.parts[0].completed_date)
        assert order.parts[1].completed_date == date.today()
        assert order.parts[2].completed_date == date.today()

        # -----------------------------------------------------------

        # Adding a part to a "completed" order brings back the order
        # into the production ready state. That's because the added part
        # is, by definition, not completed (i.e. it has no delivery slip
        # associated to it).

        # python test_delivery_slip_dao.py TestDeliverySlipDao.test_added_part_state_properly_set
        self._order_dao.change_order_state(order.order_id, OrderStatusType.order_completed)

        order_part = OrderPart()
        order_part.description = u"Part 3" + chr(233)

        # # build the update tree
        # actions = OrderedDict()
        # actions[ (DBObjectActionTypes.TO_CREATE,order_part,3) ] = []


        actions = [
            ( (DBObjectActionTypes.TO_CREATE,order_part,3,InstrumentedRelation()), None) ]




        self._order_dao.update_order(order.order_id,
                                     order.customer_id, order.customer_order_name, "preordername", OrderStatusType.order_completed,
                                     comments=None,
                                     estimate_sent_date=None,
                                     parts_results=actions)


        assert len(order.parts) == 4
        assert order.parts[0].state == OrderPartStateType.ready_for_production
        assert order.parts[1].state == OrderPartStateType.ready_for_production
        assert order.parts[2].state == OrderPartStateType.ready_for_production
        assert order.state == OrderStatusType.order_ready_for_production
        assert order.parts[0].completed_date == None
        assert order.parts[1].completed_date == None
        assert order.parts[2].completed_date == None



        # -----------------------------------------------------------

        # Adding a part to a "completed" order brings back the order
        # into the production state. Only if the state is not set
        # by the user (to something else than completed).

        self._order_dao.change_order_state(order.order_id, OrderStatusType.order_completed)

        order_part = OrderPart()
        order_part.description = u"Part 3" + chr(233)

        # build the update tree
        # actions = OrderedDict()
        # actions[ (DBObjectActionTypes.TO_CREATE,order_part,3) ] = []

        actions = [
            ( (DBObjectActionTypes.TO_CREATE,order_part,3,InstrumentedRelation()), None) ]

        self._order_dao.update_order(order.order_id,
                                     order.customer_id, order.customer_order_name, "preordername", OrderStatusType.order_aborted,
                                     comments=None,
                                     estimate_sent_date=None,
                                     parts_results=actions)


        assert len(order.parts) == 5
        for p in order.parts:
            assert p.state == OrderPartStateType.aborted
            assert p.completed_date == date.today()
        assert order.state == OrderStatusType.order_aborted



    @skip("This is a bug in SQLA I think, but it needs investigation")
    def test_sqlalchemy(self):
        # python test_delivery_slip_dao.py TestDeliverySlipDao.test_part_state_transitions_production_to_aborted

        order = self._order_dao.make(u"Test order"+chr(233),self.customer)
        order.state = OrderStatusType.order_ready_for_production
        self._order_dao.save(order)

        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 1"
        order_part.position = 1
        order_part.qty = 1
        self._order_part_dao.save(order_part)
        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 2"
        order_part.position = 2
        order_part.qty = 2
        self._order_part_dao.save(order_part)
        session().commit()

        assert order.preorder_label is None
        assert order.completed_date is None
        assert order_part.state == OrderPartStateType.preorder

        part_ids = [order.parts[0].order_part_id]
        self.order_dao.change_order_parts_state(order.order_id, part_ids, OrderPartStateType.ready_for_production)

        part_ids = [order.parts[1].order_part_id]
        self.order_dao.change_order_parts_state(order.order_id, part_ids, OrderPartStateType.aborted)

        assert order.preorder_label is None
        assert order.completed_date == None
        assert order.state == OrderStatusType.order_ready_for_production
        assert order.parts[0].state == OrderPartStateType.ready_for_production
        assert order.parts[0].completed_date == None
        assert order.parts[1].state == OrderPartStateType.aborted
        assert order.parts[1].completed_date == date.today()

        # Now the actual test

        # Simulate the action of the GUI
        actions = OrderedDict()

        a = OrderPart()
        a.order_part_id = int(order.parts[0].order_part_id)
        a.qty = int(order.parts[0].qty)
        a.position = int(order.parts[0].position)

        b = OrderPart()
        b.order_part_id = order.parts[1].order_part_id
        b.qty = order.parts[1].qty
        b.position = order.parts[1].position

        # order_id = order.order_id
        # session().expunge_all() # That's really the GUI...

        # actions[ (DBObjectActionTypes.UNCHANGED,a,0) ] = []
        # actions[ (DBObjectActionTypes.UNCHANGED,b,1) ] = []

        session().close()

        # remove those print statements, and the test passes ?!
        print((a.sell_price))
        print((b.sell_price))

        part = session().merge( a)
        partb = session().merge( b)




    def test_part_state_transitions_production_to_aborted(self):
        # python test_delivery_slip_dao.py TestDeliverySlipDao.test_part_state_transitions_production_to_aborted

        order = self._order_dao.make(u"Test order"+chr(233),self.customer)
        order.state = OrderStatusType.order_ready_for_production
        self._order_dao.save(order)

        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 1"
        order_part.position = 1
        order_part.qty = 1
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



        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 2"
        order_part.position = 2
        order_part.qty = 2
        self._order_part_dao.save(order_part)
        session().commit()

        assert order.preorder_label is None
        assert order.completed_date is None
        assert order_part.state == OrderPartStateType.preorder

        part_ids = [order.parts[0].order_part_id]
        self.order_dao.change_order_parts_state(order.order_id, part_ids, OrderPartStateType.ready_for_production)

        part_ids = [order.parts[1].order_part_id]
        self.order_dao.change_order_parts_state(order.order_id, part_ids, OrderPartStateType.aborted)

        assert order.preorder_label is None
        assert order.completed_date == None
        assert order.state == OrderStatusType.order_ready_for_production
        assert order.parts[0].state == OrderPartStateType.ready_for_production
        assert order.parts[0].completed_date == None
        assert order.parts[1].state == OrderPartStateType.aborted
        assert order.parts[1].completed_date == date.today()

        # Now the actual test

        # Simulate the action of the GUI

        a = OrderPart()
        a.order_part_id = order.parts[0].order_part_id
        b = OrderPart()
        b.order_part_id = order.parts[1].order_part_id

        opa = Operation()
        o = order.parts[0].production_file[0].operations[0]
        opa.operation_id = o.operation_id
        opa.production_file_id = o.production_file_id
        opa.planned_hours = o.planned_hours
        opa.position = o.position

        order_id = order.order_id
        session().expunge_all() # That's really the GUI...

        # actions = OrderedDict()
        # actions[ (DBObjectActionTypes.UNCHANGED,a,0) ] = [(DBObjectActionTypes.UNCHANGED,opa,0)]
        # actions[ (DBObjectActionTypes.UNCHANGED,b,1) ] = []


        actions = [
            ( (DBObjectActionTypes.UNCHANGED,a,0,InstrumentedRelation()), None),
            ( (DBObjectActionTypes.UNCHANGED,b,1,InstrumentedRelation()), None) ]



        session().close()

        # Now we set the aborted state
        self._order_dao.update_order(order.order_id,
                                     order.customer_id, order.customer_order_name, "preordername", OrderStatusType.order_aborted,
                                     comments=None,
                                     estimate_sent_date=None,
                                     parts_results=actions)

        order = self.order_dao.find_by_id(order.order_id)

        assert order.parts[0].state == OrderPartStateType.aborted
        assert order.parts[0].completed_date == date.today()
        assert order.parts[1].state == OrderPartStateType.aborted
        assert order.parts[1].completed_date == date.today()

        assert order.completed_date == date.today()
        assert order.state == OrderStatusType.order_aborted



    def _add_operation_to_part(self, order_part):
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

        return operation


    def test_part_state_transitions_production_to_aborted_and_add_an_operation(self):
        session().close()

        # python test_delivery_slip_dao.py TestDeliverySlipDao.test_part_state_transitions_production_to_aborted_and_add_an_operation

        self.customer = session().merge(self.customer)

        order = self._order_dao.make(u"Test order"+chr(233),self.customer)
        order.state = OrderStatusType.order_ready_for_production
        self._order_dao.save(order)

        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 1"
        order_part.position = 1
        order_part.qty = 1
        self._order_part_dao.save(order_part)
        self._add_operation_to_part(order_part)


        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 2"
        order_part.position = 2
        order_part.qty = 2
        self._order_part_dao.save(order_part)
        session().commit()

        assert order.preorder_label is None
        assert order.completed_date is None
        assert order_part.state == OrderPartStateType.preorder

        part_ids = [order.parts[0].order_part_id]
        self.order_dao.change_order_parts_state(order.order_id, part_ids, OrderPartStateType.ready_for_production)

        part_ids = [order.parts[1].order_part_id]
        self.order_dao.change_order_parts_state(order.order_id, part_ids, OrderPartStateType.aborted)

        assert order.preorder_label is None
        assert order.completed_date == None
        assert order.state == OrderStatusType.order_ready_for_production
        assert order.parts[0].state == OrderPartStateType.ready_for_production
        assert order.parts[0].completed_date == None
        assert order.parts[1].state == OrderPartStateType.aborted
        assert order.parts[1].completed_date == date.today()

        # Now the actual test

        # Simulate the action of the GUI

        a = OrderPart()
        a.order_part_id = order.parts[0].order_part_id
        b = OrderPart()
        b.order_part_id = order.parts[1].order_part_id

        opa = Operation()
        o = order.parts[0].production_file[0].operations[0]
        opa.operation_id = o.operation_id
        opa.production_file_id = o.production_file_id
        opa.planned_hours = o.planned_hours
        opa.position = o.position


        opb = Operation()
        opb.planned_hours = 111
        opb.position = 0

        opc = Operation()
        opc.planned_hours = 111
        opc.position = 0

        order_id = order.order_id
        session().expunge_all() # That's really the GUI...

        # actions = OrderedDict()
        # actions[ (DBObjectActionTypes.UNCHANGED,a,0) ] = [(DBObjectActionTypes.UNCHANGED,opa,0)]
        # actions[ (DBObjectActionTypes.UNCHANGED,b,1) ] = [(DBObjectActionTypes.TO_CREATE,opb,0),
        #                                                   (DBObjectActionTypes.TO_CREATE,opc,0) ]

        actions = [
            ( (DBObjectActionTypes.UNCHANGED,a,0,InstrumentedRelation()), [(DBObjectActionTypes.UNCHANGED,opa,0)]),
            ( (DBObjectActionTypes.UNCHANGED,b,1,InstrumentedRelation()), [(DBObjectActionTypes.TO_CREATE,opb,0),
                                                       (DBObjectActionTypes.TO_CREATE,opc,0) ]) ]





        order_id = order.order_id
        customer_id = order.customer_id
        customer_order_name = "eee"

        session().close()

        # Now we set the aborted state
        self._order_dao.update_order(order_id,
                                     customer_id, customer_order_name, "preordername", OrderStatusType.order_aborted,
                                     comments=None,
                                     estimate_sent_date=None,
                                     parts_results=actions)

        order = self.order_dao.find_by_id(order.order_id)

        assert order.parts[0].state == OrderPartStateType.aborted
        assert order.parts[0].completed_date == date.today()
        assert len(order.parts[0].operations) == 1
        assert order.parts[1].state == OrderPartStateType.aborted
        assert order.parts[1].completed_date == date.today()
        assert len(order.parts[1].operations) == 2

        assert order.completed_date == date.today()
        assert order.state == OrderStatusType.order_aborted

        # What happens if we do twice the same thing ?

        session().close()

        opa = Operation()
        o = order.parts[0].production_file[0].operations[0]
        opa.operation_id = o.operation_id
        opa.production_file_id = o.production_file_id
        opa.planned_hours = o.planned_hours
        opa.position = o.position

        opb = Operation()
        opb.planned_hours = 111
        opb.position = 0

        opc = Operation()
        opc.planned_hours = 111
        opc.position = 0

        # actions[ (DBObjectActionTypes.UNCHANGED,a,0) ] = [(DBObjectActionTypes.UNCHANGED,opa,0)]
        # actions[ (DBObjectActionTypes.UNCHANGED,b,1) ] = [(DBObjectActionTypes.TO_CREATE,opb,0),
        #                                                   (DBObjectActionTypes.TO_CREATE,opc,0) ]

        actions = [
            ( (DBObjectActionTypes.UNCHANGED,a,0,InstrumentedRelation()), [(DBObjectActionTypes.UNCHANGED,opa,0)]),
            ( (DBObjectActionTypes.UNCHANGED,b,1,InstrumentedRelation()), [(DBObjectActionTypes.TO_CREATE,opb,0),
                                                                           (DBObjectActionTypes.TO_CREATE,opc,0) ]) ]

        # Now we set the aborted state
        self._order_dao.update_order(order_id,
                                     customer_id, customer_order_name, "preordername", OrderStatusType.order_aborted,
                                     comments=None,
                                     estimate_sent_date=None,
                                     parts_results=actions)

        order = self.order_dao.find_by_id(order.order_id)

        assert order.parts[0].state == OrderPartStateType.aborted
        assert order.parts[0].completed_date == date.today()
        assert len(order.parts[0].operations) == 1
        assert order.parts[1].state == OrderPartStateType.aborted
        assert order.parts[1].completed_date == date.today()
        self.assertEqual(4, len(order.parts[1].operations))

        assert order.completed_date == date.today()
        assert order.state == OrderStatusType.order_aborted





    def test_create_first_part_empty_second_part_filled(self):
        # python test_order_creation.py TestOrderCreation.test_create_first_part_empty_second_part_filled

        # Simulate the action of the GUI

        part_a = OrderPart()
        part_a.description = "part 1"
        part_a.qty = 1
        part_a.sell_price = 100
        part_a.position = 0

        part_b = OrderPart()
        part_b.description = "part 2"
        part_b.qty = 2
        part_b.sell_price = 200
        part_a.position = 1

        opb = Operation()
        opb.planned_hours = 111
        opb.position = 0

        opc = Operation()
        opc.planned_hours = 111
        opc.position = 0

        # actions = OrderedDict()
        # actions[ (DBObjectActionTypes.TO_CREATE,part_a,0) ] = []
        # actions[ (DBObjectActionTypes.TO_CREATE,part_b,1) ] = [(DBObjectActionTypes.TO_CREATE,opb,0),
        #                                                        (DBObjectActionTypes.TO_CREATE,opc,0) ]

        actions = [
            ( (DBObjectActionTypes.TO_CREATE,part_a,0,InstrumentedRelation()), []),
            ( (DBObjectActionTypes.TO_CREATE,part_b,1,InstrumentedRelation()), [(DBObjectActionTypes.TO_CREATE,opb,0),
                                                            (DBObjectActionTypes.TO_CREATE,opc,0) ]) ]

        customer_id = self.customer_id
        customer_order_name = "eee"

        # Now we set the aborted state
        order = self._order_dao.update_order(None,
                                             customer_id, customer_order_name, "preordername", OrderStatusType.order_aborted,
                                             comments=None,
                                             estimate_sent_date=None,
                                             parts_results=actions)

        assert len(order.parts) == 2
        assert len(order.parts[0].operations) == 0
        assert len(order.parts[1].operations) == 2

        self.assertEqual("-", order.parts[0].label)
        self.assertEqual("A",order.parts[1].label)




    def test_create_more_than_26_parts(self):
        # python test_order_creation.py TestOrderCreation.test_create_more_than_26_parts

        # Simulate the action of the GUI
        # actions = OrderedDict()
        actions = []

        n = 30
        for i in range(n):
            part_a = OrderPart()
            part_a.description = "part {}".format(i)
            part_a.qty = i + 10
            part_a.sell_price = i*100
            part_a.position = i

            opc = Operation()
            opc.planned_hours = 111
            opc.position = 0

            # actions[ (DBObjectActionTypes.TO_CREATE,part_a,i) ] = [ (DBObjectActionTypes.TO_CREATE,opc,0) ]

            actions.append( ( (DBObjectActionTypes.TO_CREATE,part_a,i,InstrumentedRelation()), [(DBObjectActionTypes.TO_CREATE,opc,0)] ) )

        customer_id = self.customer_id
        customer_order_name = "eee"

        # Now we set the aborted state
        order = self._order_dao.update_order(None,
                                             customer_id, customer_order_name, "preordername", OrderStatusType.order_aborted,
                                             comments=None,
                                             estimate_sent_date=None,
                                             parts_results=actions)

        assert len(order.parts) == n

        self.assertEqual("A", order.parts[0].label)
        self.assertEqual("B",order.parts[1].label)
        self.assertEqual("AA",order.parts[26].label)
        self.assertEqual("AB",order.parts[27].label)



if __name__ == '__main__':
    unittest.main()
