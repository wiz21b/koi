import re

from sqlalchemy import Table, Column, String, Date, Sequence, Integer, ForeignKey, DateTime, Boolean
from sqlalchemy.schema import CheckConstraint
from sqlalchemy.orm import relationship,backref
from sqlalchemy.sql.expression import Join, func
from sqlalchemy.orm import column_property
from sqlalchemy import select

from koi.datalayer.sqla_mapping_base import metadata,Base,DATABASE_SCHEMA
from koi.datalayer.employee_mapping import Employee
from koi.db_mapping import OrderPart
from koi.datalayer.SQLAEnum import DeclEnum


# comments_locations = Table(
#     'comments_locations', Base.metadata,
#     Column('comment_location_id', Integer,autoincrement=True,primary_key=True),
#     Column('quality_event_id', Integer, ForeignKey('horse.quality_events.quality_event_id'))
# )


class CommentLocation(Base):
    __tablename__ = "comments_locations"

    comment_location_id = Column('comment_location_id', Integer,autoincrement=True,primary_key=True)

    # Add as many links to other entities as you need
    quality_event_id = Column('quality_event_id', Integer, ForeignKey(DATABASE_SCHEMA+'.quality_events.quality_event_id'), nullable=False)

    # When a comment location is deleted, then all the comments are deleted
    # that's not 100% necessary for business as deleting is unlikely
    # but it makes a nicer data model.
    comments = relationship('Comment',cascade='delete')

    def __repr__(self):
        return "<CommentLocation: comment_location_id:{} quality_event_id:{}>".format(self.comment_location_id, self.quality_event_id)


class Comment(Base):
    __tablename__ = "comments"

    comment_id = Column(Integer,autoincrement=True,primary_key=True)

    who_id = Column(Integer, ForeignKey('employees.employee_id'),nullable=False)
    creation = Column(DateTime,nullable=False)
    text = Column(String)
    active = Column(Boolean,nullable=False,default=True)

    indexed_description = Column(String)
    who = relationship(Employee,primaryjoin=Employee.employee_id == who_id)

    location_id = Column(Integer, ForeignKey("comments_locations.comment_location_id"),nullable=False)

    def __repr__(self):
        return "<Comment:{}>".format(self.text)


class QualityEventType(DeclEnum):
    non_conform_customer = 'non_conform_customer',_("Non conform customer")
    non_conform_intern = 'non_conform_intern', _("Non conform intern")
    non_conform_supplier = 'non_conform_supplier', _("Non conform supplier")

from sqlalchemy.ext.declarative import declared_attr

class Commentable:
    """
    WARNING : Don't forget to update CommentLocation table when you use this mixin.

    There's some serious SQL Alchemy magic running here. When using this mixin, SQLA will
    deduce automatically the relationship between the mixed-in and the
    comment table, via commentlocation, by following the appropriate FK's...
    """
    def __init__(self):
        # Automatically wire the mixed-in object to its "location"
        self.location = CommentLocation() # The 'location' relationship has "uselist = False"

    @declared_attr
    def location(self):
        # When the mixed in class instance is deleted, then its location must be destroyed
        # as well (so there's a cascade here). After that, another cascade will trigger
        # the destruction of comments (see the 'comments' relationship in this Commentable mixin)
        return relationship(CommentLocation,uselist=False,cascade='save-update,delete')

    @declared_attr
    def comments(self):
        # The relationship here is not a classical many-to-many because the association
        # table has only one foreign key and not two as usual. Therefore, I have
        # to specify a secondary join. It is view only because I don't think SQLA
        # will be able to handle the cascade updates easily.

        return relationship(Comment,
                            secondary=Join(CommentLocation,Comment,Comment.location_id==CommentLocation.comment_location_id),
                            order_by=Comment.creation,
                            viewonly=True)



#class QualityEvent(Commentable,Base): # Inheritance order is important !
class QualityEvent(Base):
    __tablename__ = "quality_events"

    quality_event_id = Column(Integer,autoincrement=True,nullable=False,primary_key=True)
    when = Column(DateTime,nullable=False,unique=True)
    kind = Column(QualityEventType.db_type(),nullable=False)
    description = Column(String, nullable=False, default="")

    who_id = Column(Integer, ForeignKey('employees.employee_id'),nullable=False)
    who = relationship(Employee,primaryjoin=Employee.employee_id == who_id,uselist=False)
    order_part_id = Column(Integer, ForeignKey(OrderPart.order_part_id),nullable=False)
    order_part = relationship(OrderPart,primaryjoin=OrderPart.order_part_id == order_part_id, backref=backref('quality_events', cascade="all, delete, delete-orphan"))

    human_identifier = column_property(
        select( [ func.concat( "NC-", OrderPart.human_identifier, "-", quality_event_id)]).where(OrderPart.order_part_id == order_part_id).correlate_except(OrderPart))


# Note that since the order part label is redundant, we allow a
# non conformity label to omit it. The quality_event_id (last part of the label)
# remains mandatory of course.
re_non_conformity_label = re.compile("NC-([0-9]+[A-Z]+)?-?([0-9]+)")


def is_non_conformity_label(s : str):
    if not s:
        return False

    if re_non_conformity_label.match(s):
        return True



OrderPart.nb_non_conformities = column_property(
    select([func.count(QualityEvent.quality_event_id)]).where(QualityEvent.order_part_id == OrderPart.order_part_id).correlate_except(QualityEvent))
