import unittest

from koi.configuration.business_functions import business_computations_service
from koi.db_mapping import OrderStatusType, OrderPartStateType

class TestStock(unittest.TestCase):

    def test_order_states(self):
        for n in OrderStatusType.symbols():
            # Make sure the symbol is kown in the next_states function
            business_computations_service.order_possible_next_states(n)


    def test_order_part_states(cls):
        for n in OrderStatusType.symbols():
            # state_from_order_state
            assert business_computations_service.order_part_state_from_order_state(n)

        for n in OrderPartStateType.symbols():
            assert n in business_computations_service.order_states_precedence(), "Missing a enum {}".format(n)
            # Make sure the cymobl is kown in the next_states function
            business_computations_service.order_part_possible_next_states(n)
