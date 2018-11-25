"""
stock_entry:
    name
    unit
    current_quantity

stock_movement:
    stock_entry
    old_quantity
    new_quantity
    reason
    who
    time_change
"""

import decimal
from sqlalchemy.orm import composite
from sqlalchemy import Column, String, Boolean, Float, Integer, Sequence, ForeignKey, DateTime, Numeric
from koi.datalayer.sqla_mapping_base import metadata,Base,DATABASE_SCHEMA

stock_item_id_generator = Sequence('resource_id_generator',start=1, schema=DATABASE_SCHEMA,metadata=metadata)


Price = Numeric(10,2)

def TextLine( label, short_label=""):
    c = Column(String)
    c._horse_label = label
    c._horse_short_label = short_label
    return c

def Quantity( label, short_label=""):
    c = Column(Float)
    c._horse_label = label
    c._horse_short_label = short_label
    return c


from decimal import Decimal

class StockItem(Base):
    __tablename__ = 'stock_items'

    stock_item_id = Column(Integer,stock_item_id_generator,nullable=False,primary_key=True)

    name = TextLine("Item's name","Name")

    quantity_left = Quantity("Left quantity", "Q. left")

    """ We note the initial quantity because it might be tied to a buy
    price or some other "initial" conditions.
    """
    initial_quantity = Quantity("Initial quantity", "Q. init.")

    """ Price we bought the first quantity of the stock item.
    """
    buy_price = Column(Price)





# for k,v in dict(StockItem.__dict__).items():
#     if type(v) == Quantity:
#         q_col = v._name
#         u_col = v._name + '_unit'
#
#         q_attr = k + '_qty'
#         u_attr = k + '_unit'
#         setattr(StockItem, q_attr, Column(q_col, Numeric(10,2)))
#         setattr(StockItem, u_attr, Column(u_col, String))
#         setattr(StockItem, k, composite(HorseQuantity, getattr(StockItem,q_attr), getattr(StockItem, u_attr)))

# class HorseQuantity:
#
#     def __init__(self, qty, unit):
#         self.qty = decimal.Decimal(qty)
#         self.unit = unit
#
#     def __composite_values__(self):
#         return self.qty, self.unit
#
#     def __mul__(self, other):
#         return HorseQuantity(self.qty * other, self.unit)
#
#     def __str__(self):
#         return "{} {}".format(self.qty, self.unit)
#
#
#
#
# class Quantity:
#     def __init__(self, name):
#         self._name = name

# from koi.datalayer.employee_mapping import Employee
# from koi.datalayer.supply_order_mapping import SupplyOrderPart
#
#
class StockMovement(Base):
    __tablename__ = 'stock_movements'

    stock_item_id = Column( Integer, ForeignKey(StockItem))
    stock_item = relationship(StockItem)
    old_quantity = Column(Quantity)
    new_quantity = Column(Quantity)

    when = Column(DateTime,nullable=False,index=True)

    who_id = Column(Integer, ForeignKey('employees.employee_id'),nullable=True)
    who = relationship(Employee,primaryjoin=Employee.employee_id == who_id)

    supply_order_part_id = Column(Integer, ForeignKey(SupplyOrderPart.supply_order_part_id),nullable=True)
    supply_order_part = relationship(SupplyOrderPart)

