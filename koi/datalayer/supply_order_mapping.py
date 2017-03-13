from sqlalchemy import Column, String, Integer, Float, ForeignKey, Date, Boolean
from sqlalchemy.schema import CheckConstraint,UniqueConstraint
from sqlalchemy import event
from sqlalchemy.orm import relationship, column_property
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.sql import select, func

from koi.translators import text_search_normalize
from koi.datalayer.sqla_mapping_base import Base
from koi.datalayer.supplier_mapping import Supplier
from koi.datalayer.gapless_sequence import gaplessseq

from koi.datalayer.sqla_mapping_base import MoneyType

class SupplyOrderPart(Base):
    __tablename__ =  'supply_order_parts'

    supply_order_part_id = Column(Integer,autoincrement=True,primary_key=True)
    description = Column(String, nullable=False, default="")
    _indexed_description = Column("indexed_description", String, nullable=False)
    quantity = Column(Float,nullable=False)

    # Unit price
    unit_price = Column(MoneyType,nullable=False)
    position = Column(Integer,nullable=False)
    label = Column(String)
    supply_order_id = Column(Integer, ForeignKey('supply_orders.supply_order_id'))


    __table_args__ = (CheckConstraint( 'quantity > 0',
                                       name='actual_quantity'),
                      UniqueConstraint('supply_order_id','position',
                                       name='positions_are_strictly_ordered'))



class SupplyOrder(Base):
    __tablename__ = 'supply_orders'

    supply_order_id = Column(Integer,autoincrement=True,primary_key=True)

    accounting_label = Column(Integer,default=gaplessseq('supply_order_id'),unique=True,nullable=False)

    description = Column(String,nullable=False, default="")
    _indexed_description = Column("indexed_description",String, nullable=True)
    creation_date = Column(Date,nullable=False)
    supplier_id = Column(Integer, ForeignKey('suppliers.supplier_id'))

    supplier_reference = Column(String,nullable=True)
    expected_delivery_date = Column(Date,nullable=True)
    tags = Column(ARRAY(String),nullable=False,default=[])

    parts = relationship(SupplyOrderPart,primaryjoin=SupplyOrderPart.supply_order_id == supply_order_id,order_by=SupplyOrderPart.position)

    supplier = relationship(Supplier,primaryjoin=Supplier.supplier_id == supplier_id)

    active = Column(Boolean,nullable=False,default=True)


SupplyOrderPart.human_identifier = column_property(
    select( [ SupplyOrder.__table__.c.accounting_label.\
              concat(func.coalesce(SupplyOrderPart.__table__.c.label,"-")) ],
            from_obj=SupplyOrder.__table__).\
    where(SupplyOrder.__table__.c.supply_order_id == SupplyOrderPart.__table__.c.supply_order_id).\
    correlate_except(SupplyOrder).\
    as_scalar())


def set_supply_order_indexed_description(target, value, oldvalue, initiator):
    if value:
        target._indexed_description = text_search_normalize(str(value))

event.listen(SupplyOrder.description, 'set', set_supply_order_indexed_description)

def set_supply_order_part_indexed_description(target, value, oldvalue, initiator):
    if value:
        target._indexed_description = text_search_normalize(str(value))

event.listen(SupplyOrderPart.description, 'set', set_supply_order_part_indexed_description)
