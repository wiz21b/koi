from sqlalchemy import Table, Column, String, Integer, Float, ForeignKey, Date, Boolean
from sqlalchemy.orm import relationship,backref
from sqlalchemy.schema import UniqueConstraint,CheckConstraint

from koi.datalayer.sqla_mapping_base import metadata,Base,DATABASE_SCHEMA
from koi.datalayer.quality import QualityEvent

class DocumentCategory(Base):
    __tablename__ =  'documents_categories'

    document_category_id = Column(Integer,autoincrement=True,primary_key=True)

    full_name = Column(String(),nullable=False)

    # Used for display, but not as a foreign key (there's the surrogate
    # key for that).
    short_name = Column(String(),nullable=False, unique=True)

    __table_args__ = (CheckConstraint( 'char_length(full_name) > 0',
                                       name='non_empty_full_name'),
                      CheckConstraint( 'char_length(short_name) > 0',
                                       name='non_empty_short_name'),)

    @property
    def color_index(self):
        return self.document_category_id

# Here we define some relation tables

# A document is attached to one order_part *at most* (so PK on document_id)
# We put the relationship into a separate table to keep the document
# table FK-free (else I'd have to add a column for each FK which not
# as nice and not future proof -- my hypothesis is that we'll need
# to add documents to various things in Horse)

documents_order_parts_table = Table(
    'documents_order_parts', Base.metadata,
    Column('document_id', Integer, ForeignKey('documents.document_id'),primary_key=True),
    Column('order_part_id', Integer, ForeignKey('order_parts.order_part_id'))
)


# A document is attached to one order *at most* (so PK on document_id)

documents_orders_table = Table(
    'documents_orders', Base.metadata,
    Column('document_id', Integer, ForeignKey('documents.document_id'),primary_key=True),
    Column('order_id', Integer, ForeignKey('orders.order_id'))
)


documents_quality_events_table = Table(
    'documents_quality_events', Base.metadata,
    Column('document_id', Integer, ForeignKey('documents.document_id'),primary_key=True),
    Column('quality_event_id', Integer, ForeignKey('quality_events.quality_event_id'))
)


class Document(Base):
    __tablename__ =  'documents'

    document_id = Column(Integer,autoincrement=True,primary_key=True)

    # A quick descritption for the file
    # Used only for templates
    description = Column(String(),default="",nullable=False)

    # The name of the file; without a path.
    filename = Column(String(),nullable=False)

    # The file name (without a path). We don't put a path
    # because in case of backup/Restore, the path may be
    # altered.
    server_location = Column(String(),nullable=False)

    # File size in bytes (it duplicates the file size which
    # can be obtained from the filesystem, but it makes things faster
    # when looking at a set of files). See this as a cache
    # for os.path.getsize.
    file_size = Column(Integer,nullable=False)

    # When the last version was uploaded
    upload_date = Column(Date,nullable=False)

    document_category_id = Column(Integer,ForeignKey('documents_categories.document_category_id'),nullable=True)

    # @property
    # def category(self) -> str:
    #     return ['QUALITY','SALES','TECHNICAL'][(self.document_id or 0) % 3]

    # Strangely, if I change OrderPart definition to add a relationship
    # described in the same way as the backref, then I get issues
    # with delete cascades when deleting an orderPart.

    # Collection class is a set because the same document can't
    # appear twice in the relationship.

    order_part = relationship('OrderPart',secondary=documents_order_parts_table,
                              uselist=False,
                              backref=backref('documents',collection_class=set,cascade='delete'))

    order = relationship('Order',secondary=documents_orders_table,
                         uselist=False,
                         backref=backref('documents',collection_class=set,order_by='Document.server_location',cascade='delete'))

    quality_event = relationship(QualityEvent,secondary=documents_quality_events_table,
                         uselist=False,
                         backref=backref('documents',collection_class=set,order_by='Document.server_location',cascade='delete'))

    __table_args__ = (CheckConstraint( 'file_size > 0',
                                       name='non_empty_file'),)


    is_template = Column( Boolean(), nullable=False)

    __mapper_args__ = {
        'polymorphic_identity':False, # Value for is_tempalte to represent a non template
        'polymorphic_on':is_template
    }

    def __str__(self):
        return self.filename

from sqlalchemy.orm import column_property
from sqlalchemy.sql import select

Document.order_id = column_property(
    select([ documents_orders_table.c.order_id ],
           from_obj=documents_orders_table).\
    where(documents_orders_table.c.document_id == Document.document_id).correlate_except(documents_orders_table).as_scalar())


class TemplateDocument(Document):
    __tablename__ =  'template_documents'

    template_document_id = Column(Integer, ForeignKey(Document.document_id), nullable=True,primary_key=True)

    tags = Column(String(),default="",nullable=False)


    __mapper_args__ = {
        'polymorphic_identity':True,
    }



def extend_data_model( klass, field, type_):
    model_class = globals()[klass]
    setattr(model_class,field, type_)


# For the purpose of a unique constraint, null values are not considered equal.
# And we must be able to have several templates without a reference
extend_data_model("TemplateDocument","reference",Column(String(),default=None,nullable=True,unique=True))

# TemplateDocument.reference = Column(String(),default="",nullable=False)
# TemplateDocument.language = Column(String(),default="",nullable=False)

'''
Class used to generate the data model. Not intended for use.


class StockItem(MyBase):
    name = FreeString(not_empty=True)
    description = FreeString()
    value_per_quantity = Currency()
    quantity = Quantity( greater_than(0))

    supply_order_part = link_to_zero_or_one(SupplyOrderPart)
    movements = linked_to_zero_or_more(StockItemMovement) --> each movement will have a "stock_item" field

    def validation(self):
        if not self.part or self.order:
            raise Exception("Must have either a part or an order")

    hints = [
        ("description", SetWordIndex)
        ("part", SecondaryTable),
        ("part", AddToDto),
        ("order", SecondaryTable),
        ("tsk_description", column_property(
            select([ "[" + SAOperationDefinition.__table__.c.short_id.concat( "] ").concat( func.coalesce(SAOperation.__table__.c.description,"")) ],\
                   from_obj=SAOperation.__table__.join(SAOperationDefinition.__table__)).\
            where(SATaskOnOperation.__table__.c.operation_id == Operation.__table__.c.operation_id).as_scalar()))

    ]

class HTemplateDocument(HDocument):
    tags = Tags()

make_sqla_entities(HDocument)
make_sqla_entities(HTemplateDocument)
register_dto(HDocument)
register_json_serializer(HDocument)
add_to_database(HDocument)

prototype = [HDocument.name, HDocument.description]



'''
