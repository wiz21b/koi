import enum
from datetime import date
from typing import List

from koi.db_mapping import Customer, OrderPart, Employee

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


class Line:
    def __init__( self, description, version, type_, file_):
        self.description = description
        self.version = version
        self.type = type_
        self.file = file_
        self.modify_config = False
        self.date_upload = date.today()
        self.crl = CRL.C


class ImpactLine:
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


class Configuration:
    article_configuration: "ArticleConfiguration"
    parts : List[OrderPart]

    def __init__(self):
        self.frozen = None
        self.freezer = None
        self.parts =  []
        self.lines = []
        self.version = 0
        self.article_configuration = None


class ArticleConfiguration:

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
