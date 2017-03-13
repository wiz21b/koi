from koi.Configurator import mainlog

from koi.datalayer.RollbackDecorator import RollbackDecorator
from koi.datalayer.database_session import session
from koi.datalayer.supplier_mapping import Supplier
from koi.datalayer.types import DBObjectActionTypes
from koi.datalayer.generic_access import freeze,all_non_relation_columns,recursive_defrost_into
from koi.datalayer.audit_trail_service import audit_trail_service



class SupplierService(object):
    def __init__(self):
        pass

    @RollbackDecorator
    def save(self, supplier):
        c = recursive_defrost_into(supplier, Supplier)
        session().flush()
        supplier_id = c.supplier_id
        session().commit()
        return supplier_id


    @RollbackDecorator
    def number_of_suppliers(self):
        return session().query(Supplier).count()

    @RollbackDecorator
    def find_by_id(self, supplier_id):
        mainlog.debug("SupplierService.find_by_id {}".format(supplier_id))

        c = all_non_relation_columns(Supplier)
        supplier = session().query(*c).filter(Supplier.supplier_id == supplier_id).one()
        session().commit()
        return supplier


    @RollbackDecorator
    def find_all(self):
        c = all_non_relation_columns(Supplier)
        suppliers = session().query(*c).all()
        session().commit()
        return suppliers

supplier_service = SupplierService()
