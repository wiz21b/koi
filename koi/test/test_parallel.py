import unittest
from unittest import skip
from sqlalchemy.orm.exc import NoResultFound
# Make sure we work with an in memory database
import Configurator
# Configurator.configuration.in_test()

from sqlalchemy.sql.expression import func,select,join


from db_mapping import *
from dao import dao,DataException

count = 1


class TestCustomer(unittest.TestCase):
    def test_create_delete(self):

        for i in range(count):
            c = Customer("Test")
            dao.customer_dao.save(c)
            id = c.customer_id

            dao.customer_dao.delete(c)

            try:
                dao.customer_dao.find_by_id(id)
                self.fail()
            except NoResultFound as ex:
                pass


class TestOperationDefinition(unittest.TestCase):
    def test_create_delete(self):

        for i in range(count):
            c = OperationDefinition()
            c.description = "Alpha"
            c.short_id = "AL"
            dao.operation_definition_dao.save(c)
            id = c.operation_definition_id

            dao.operation_definition_dao.delete(c)

            try:
                dao.operation_definition_dao.find_by_id(id)
                self.fail()
            except NoResultFound as ex:
                pass


class TestEmployee(unittest.TestCase):
    def test_create_delete(self):

        for i in range(count):
            c = Employee()
            c.fullname = "Alpha"
            dao.employee_dao.save(c)
            id = c.employee_id

            dao.employee_dao.delete(c.employee_id)

            try:
                dao.employee_dao.find_by_id(id)
                self.fail()
            except NoResultFound as ex:
                pass

class TestOrder(unittest.TestCase):
    def test_create_delete(self):
        customer = Customer("Test")
        dao.customer_dao.save(customer)
        print((customer.customer_id))

        for i in range(count):
            c = Order()
            c.description = "alpha"
            c.customer = customer
            dao.order_dao.save(c)
            id = c.order_id

            try:
                dao.customer_dao.delete(customer.customer_id)
                self.fail()
            except DataException as ex:
                pass

            dao.order_dao.delete(c)

            try:
                dao.order_dao.find_by_id(id)
                self.fail()
            except NoResultFound as ex:
                pass

        dao.customer_dao.delete(c)

if __name__ == '__main__':
    unittest.main()
