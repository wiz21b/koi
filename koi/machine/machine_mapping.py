from sqlalchemy import Column, String, LargeBinary, Boolean, Integer, Sequence, ForeignKey
from sqlalchemy.orm import reconstructor, relationship

# from PySide.QtGui import QPixmap,QImage
# from PySide.QtCore import Qt,QByteArray,QBuffer,QIODevice

from koi.datalayer.SQLAEnum import DeclEnum
from koi.datalayer.sqla_mapping_base import metadata,Base,DATABASE_SCHEMA
from koi.Configurator import mainlog


resource_id_generator = Sequence('resource_id_generator',start=1, schema=DATABASE_SCHEMA,metadata=metadata)

class Resource(Base):
    __tablename__ = 'resources'

    version_id = Column(Integer) # See mapper configuration to understand this
    resource_type = Column('resource_type',String,nullable=False)

    __mapper_args__ = {'polymorphic_on': resource_type,
                       'polymorphic_identity': 'resource',
                       'version_id_col': version_id} # FIXME not a very good name

    # Autoincrment is effectless if the primary key is referenced by
    # a foreign key

    resource_id = Column('resource_id',Integer,resource_id_generator,index=True,primary_key=True)



class Machine(Resource):
    __mapper_args__ = {'polymorphic_identity': 'machine'}

    __tablename__ = 'machines'

    machine_id = Column('resource_id',Integer,ForeignKey('resources.resource_id'),nullable=True,primary_key=True)

    # machine_id = Column('machine_id',Integer,machine_id_generator,nullable=False,primary_key=True)

    fullname = Column(String)
    """ The full name of the machine"""

    is_active = Column(Boolean,default=True,nullable=False)
    """ An inactive machine don't show up in Horse (except in the machine
    edit screen) """

    clock_zone = Column(String)
    """ Clock zone indicates where the machine is located. It is customary
    that there's a clock in the middle of the zone.
    Right now, zones are called 'Zone 1', 'Zone 2',... but that's not mandatory
    Therefore we don't add any constraint on the data model
    Zones will be used to prepare the barcode list of machines.
    """

    operation_definition_id = Column('operation_definition_id', ForeignKey('operation_definitions.operation_definition_id'),nullable=True)
    operation_definition = relationship('OperationDefinition', uselist=False)
    """ A machine is tied to an operation
    It is not tied to several operations. FIXME Why is it so ?
    """


    def __repr__(self):
        return u"<MACHINE: {}>".format(self.fullname)
