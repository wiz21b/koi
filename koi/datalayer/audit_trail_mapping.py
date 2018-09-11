from sqlalchemy import Table, Column, String, Date, Sequence, Integer, ForeignKey, DateTime
from sqlalchemy.schema import CheckConstraint
from sqlalchemy.orm import relationship

from koi.datalayer.sqla_mapping_base import metadata,Base,DATABASE_SCHEMA
from koi.datalayer.employee_mapping import Employee

# I make a separate id because it can grow very fast.
audit_trail_id_generator = Sequence('audit_trail_id_generator',start=10000, schema=DATABASE_SCHEMA,metadata=metadata)

class AuditTrail(Base):
    __tablename__ =  'audit_trail'

    audit_trail_id = Column(Integer,audit_trail_id_generator,nullable=False,primary_key=True)


    what = Column(String,nullable=False)
    # A code describing what was done (order created)
    # We don't use a enmu right now because it'd make coding
    # harder. FIXME Switch to enum when the set of codes
    # is better known.

    detailed_what = Column(String,nullable=True)

    target_id = Column(Integer,nullable=False)
    # Id of the object on which it was done (order_id)

    # WARNING FIXME This is actually a foreign key but since
    # we don't know to which table, this is rather weak.

    when = Column(DateTime,nullable=False,index=True)
    """ when the action was done """

    who_id = Column(Integer, ForeignKey('employees.employee_id'),nullable=True)
    who = relationship(Employee,primaryjoin=Employee.employee_id == who_id)
    # It was done by a recognized employee

    who_else = Column(String,nullable=True)
    # It was done by something else (admin, batch,...)

    __table_args__ = (CheckConstraint( "(who_id IS NULL AND who_else IS NOT NULL) OR (who_id IS NOT NULL AND who_else IS NULL)",
                                       name='who_is_human_or_computer'),)
    # Either an employee or something/someone else, but at least one of them.
