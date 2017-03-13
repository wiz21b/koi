from sqlalchemy.exc import IntegrityError
from koi.Configurator import mainlog
from koi.datalayer.database_session import session
from koi.datalayer.RollbackDecorator import RollbackDecorator
from koi.db_mapping import Customer,freeze2

class CustomerDAO(object):
    def __init__(self,session):
        self._table_model = None

    @RollbackDecorator
    def number_of_customers(self):
        return session().query(Customer).count()

    @RollbackDecorator
    def all(self):
        return session().query(Customer).order_by(Customer.fullname).all()

    @RollbackDecorator
    def all_frozen(self):
        return freeze2(session().query(Customer).order_by(Customer.fullname).all())

    @RollbackDecorator
    def find_by_id(self,identifier,resilient=False):
        mainlog.debug(u"customer_dao.find_by_id : {}".format(identifier))
        q = session().query(Customer).filter(Customer.customer_id == identifier)
        if not resilient:
            return q.one()
        else:
            return q.first()

    @RollbackDecorator
    def find_by_id_frozen(self,identifier,resilient=False):
        mainlog.debug(u"customer_dao.find_by_id_frozn : {}".format(identifier))
        r = session().query(Customer).filter(Customer.customer_id == identifier).one()
        return freeze2(r)

    @RollbackDecorator
    def delete(self,customer_id):
        customer = self.find_by_id(customer_id)
        try:
            session().delete(customer)
            session().commit()
        except IntegrityError:
            session().rollback()
            raise DataException(_("Cannot delete this customer because there are orders for him. Remove the orders first."))

    def make(self,fullname):
        return Customer(fullname)

    @RollbackDecorator
    def save(self,customer):
        # FIXME Don't use this anymore

        if customer not in session():
            session().add(customer)
        session().commit()
