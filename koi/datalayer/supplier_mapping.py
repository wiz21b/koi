from sqlalchemy import Column, String, Integer
from sqlalchemy import event

from koi.datalayer.sqla_mapping_base import Base
from koi.translators import text_search_normalize


class Supplier(Base):
    __tablename__ = 'suppliers'

    supplier_id = Column(Integer,autoincrement=True,primary_key=True)
    fullname = Column(String)

    indexed_fullname = Column(String)

    address1 = Column(String)
    address2 = Column(String)
    phone = Column(String)
    phone2 = Column(String)
    email = Column(String)
    country = Column(String)
    notes =  Column(String)
    fax = Column(String)


def set_supplier_indexed_fullname(target, value, oldvalue, initiator):
    if value:
        target.indexed_fullname = text_search_normalize(str(value))

event.listen(Supplier.fullname, 'set', set_supplier_indexed_fullname)
