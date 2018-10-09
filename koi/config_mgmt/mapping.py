import enum
from datetime import date
from typing import List

from sqlalchemy import Table, Column, Integer, String, Float, MetaData, ForeignKey, Date, DateTime, Sequence, Boolean, LargeBinary, Binary, Index, Numeric, Enum
from sqlalchemy.orm import relationship, backref

from koi.datalayer.sqla_mapping_base import metadata,Base,DATABASE_SCHEMA,MoneyType
from koi.db_mapping import Customer, OrderPart, Employee, id_generator
from koi.doc_manager.documents_mapping import Document



class ImpactApproval(enum.Enum):
    UNDER_CONSTRUCTION = "Under construction"
    APPROVED = "Approved"
    REJECTED = "Rejected"

class TypeConfigDoc(enum.Enum):
    IMPACT = "Impact document"
    PLAN_2D = "Plan 2D"
    PLAN_3D = "Plan 3D"
    PROGRAM = "Programme"

class CRL(enum.Enum):
    C = "À consulter"
    R = "À remplir"
    LC = "À livrer au client"
    RLC = "À remplir et livrer au client"
    LF = "À livrer au fournisseur"
    RLF = "À remplir et livrer au fournisseur"

    def __str__(self):
        return self.value

class Configuration(Base):
    __tablename__ = 'configurations'
    configuration_id = Column(Integer,id_generator,nullable=False,primary_key=True)

    frozen = Column(Date, default=None)
    version = Column(Integer, default=0)
    freezer_id = Column(Integer, ForeignKey(Employee.employee_id))
    article_configuration_id = Column(Integer, ForeignKey("article_configurations.article_configuration_id"))

    freezer = relationship(Employee, uselist=False)

    # A Configuration represents a version of a configuration
    # That version comes to existence because of some impacts
    # which are represented here.
    origins = relationship("ImpactLine", backref=backref("configuration", uselist=False))


    def __init__(self):
        self.version = 0


class ConfigurationLine(Base):
    __tablename__ = 'configuration_lines'

    configuration_line_id = Column(Integer,id_generator,nullable=False,primary_key=True)

    description = Column(String)

    # Version of the document in this configuration line
    version = Column(Integer, default=0)
    document_id = Column(Integer, ForeignKey(Document.document_id))
    document_type = Column(Enum( TypeConfigDoc, inherit_schema=True))
    modify_config = Column(Boolean)
    date_upload = Column(Date)
    crl = Column(Enum(CRL))

    document = relationship(Document, uselist=False)
    configuration_id = Column(Integer, ForeignKey(Configuration.configuration_id))
    configuration = relationship(Configuration, uselist=False, backref="lines" )


    def __init__(self):
        self.version = 0


""" solution 1 : muiltiple inheritance
    solution 2 : outside function => won't work with prototype
    solution 3 : add function at code gen time
"""



class ArticleConfiguration(Base):
    __tablename__ = 'article_configurations'
    article_configuration_id = Column(Integer,id_generator,nullable=False,primary_key=True)

    customer_id = Column(Integer, ForeignKey(Customer.customer_id))
    identification_number = Column(String)
    revision_number = Column(String, default="A")
    date_creation = Column(Date)

    part_plan_id = Column(Integer, ForeignKey(Document.document_id))

    customer = relationship(Customer, uselist=False)
    configurations = relationship( Configuration, order_by=Configuration.version, backref=backref('article_configuration', enable_typechecks=False), enable_typechecks=False)


    # Methods defined as static to be reused in DTO objects !
    # and as property to be easily accessible (because static
    # can't be used as properties...)

    # @property
    # def current_configuration(self):
    #     return ArticleConfiguration._current_configuration(self)

    @staticmethod
    def _current_configuration(self):
        i = len(self.configurations) - 1

        if i > 0:
            while i >= 0:
                if self.configurations[i].frozen:
                    return self.configurations[i]
                i -= 1

            return self.configurations[-1]
        else:
            return self.configurations[0]


class ImpactLine(Base):
    __tablename__ = 'impact_lines'
    impact_line_id = Column(Integer,id_generator,nullable=False,primary_key=True)


    # Short description of the document.
    # Some unstructured meta information about the document can fit here.
    description = Column(String)

    approval = Column(Enum(ImpactApproval, inherit_schema=True))
    approval_date = Column(Date)
    active_date = Column(Date)

    # An impact line may not be wired to a configuration.
    # Utlimately, it should end up wired to one, but
    # it may not be the case from its creation on. That's
    # because one may want to track an impact file before
    # it actually results in a new version of a configuration.

    configuration_id = Column(Integer, ForeignKey( Configuration.configuration_id))

    # Even if impact line defines confiugration versions, they
    # noentheless belong to one article confiugration.
    article_configuration_id = Column(Integer, ForeignKey(ArticleConfiguration.article_configuration_id),nullable=False)
    article_configuration = relationship(ArticleConfiguration, uselist=False, backref=backref("impacts", enable_typechecks=False), enable_typechecks=False)

    owner_id = Column(Integer, ForeignKey(Employee.employee_id), nullable=False)

    # The approver is set only if the approval state is ImpactApproval.APPROVED.
    approver_id = Column(Integer, ForeignKey(Employee.employee_id))

    document_id = Column(Integer, ForeignKey(Document.document_id), nullable=False)

    document = relationship(Document, uselist=False)



    @staticmethod
    def _version(self):
        """ When an impact file is associated to a configuration,
        it "creates" a version of that configuration. So the
        version of the configuration comes to existence *because*
        of one or more impact lines are wired to the configuration.
        """
        if self.configuration:
            return self.configuration.version
        else:
            return None

    @staticmethod
    def _date_upload(self):
        return self.document.upload_date

# Put here to be able to use foreign_keys parameters
# to desambiguate the two relationships to Employee
ImpactLine.owner = relationship(Employee, uselist=False, foreign_keys=[ImpactLine.owner_id])
ImpactLine.approved_by = relationship(Employee, uselist=False, foreign_keys=[ImpactLine.approver_id])






class LineDto:
    def __init__( self, description, version, type_, file_):
        self.description = description
        self.version = version
        self.type = type_
        self.file = file_
        self.modify_config = False
        self.date_upload = date.today()
        self.crl = CRL.C


class ImpactLineDto:
    approved_by: Employee

    def __init__( self):
        self.owner = "Chuck Noris"
        self.description = None
        self.file = None
        self.date_upload = date.today()
        self.approval = ImpactApproval.UNDER_CONSTRUCTION
        self.approved_by = None
        self.active_date = date.today()
        self.configuration = None

    @property
    def owner_short(self):
        return self.owner.login.upper()

    @property
    def approver_short(self):
        if self.approved_by:
            return self.approved_by.login.upper()
        else:
            return ""

    @property
    def version(self):
        if self.configuration:
            return self.configuration.version
        else:
            return None


class ConfigurationDto:
    article_configuration: "ArticleConfiguration"
    parts : List[OrderPart]

    def __init__(self):
        self.frozen = None
        self.freezer = None
        self.version = 0

        self.parts =  []
        self.lines = []
        self.article_configuration = None


class ArticleConfigurationDto:

    configurations: List[Configuration]
    customer : Customer
    impacts : List[ImpactLine]

    def __init__(self):
        self.customer = None
        self.identification_number = ""
        self.file = ""
        self.revision = "E"
        self.creation_date =  date.today()


        # The different configurations.
        # In the normal scenario, the first configuration has no impact file
        # and the following configurations have at least an impact file.
        # Some impact files may not have a configuration (for example, while
        # they are written) (this prevents, for example, an impact file that is
        # rejected has an empty configuiration tied to it).
        self.configurations = []

        # The story of changes brought to the article configuration.
        # Each working configuration should be tied to an impact.
        self.impacts = []

    @property
    def customer_id(self) -> str:
        return self.customer.customer_id

    @property
    def valid_since(self):
        return date(2017, 2, 28)

    @property
    def current_configuration_status(self):
        if self.current_configuration().frozen:
            return "Frozen"
        else:
            return "not frozen"

    @property
    def full_version(self) -> str:
        return "{}/{}".format( self.identification_number, self.revision)

    @property
    def current_configuration_id(self) -> int:
        return self.current_configuration().version

    def current_configuration(self):
        i = len(self.configurations) - 1

        if i > 0:
            while i >= 0:
                if self.configurations[i].frozen:
                    return self.configurations[i]
                i -= 1

            return self.configurations[-1]
        else:
            return self.configurations[0]