from datetime import date

from koi.datalayer.serializers import *
from koi.config_mgmt.mapping import  TypeConfigDoc, ImpactApproval

def _make_quick_doc( name : str):
    document = Document()
    session().add(document)
    document.filename = name
    document.server_location = "dummy"
    document.file_size = 9999
    document.upload_date = date.today()

    return document


def _make_quick_doc_dto( name : str):
    document = CopyDocument()
    document.filename = name
    document.server_location = "dummy"
    document.file_size = 9999
    document.upload_date = date.today()
    document.is_template = False

    return document

copy_employees = dict()
def _make_quick_employee( name : str, login : str):

    if name in copy_employees:
        return copy_employees[name]

    employee = CopyEmployee()
    copy_employees[name] = employee
    employee.fullname = name
    employee.login = login
    employee.employee_id = hash(name)
    return employee


def _make_config_line( description, version, type_, file_):
    line = ConfigurationLine()
    session().add(line)
    line.description = description
    line.version = version
    line.document_type = type_

    d = Document()
    session().add(d)

    line.document = d
    line.document.filename = file_
    line.document.server_location = "dummy"
    line.document.file_size = 9999
    line.document.upload_date = date.today()

    return line

def _make_config_line_dto( description, version, type_, file_):
    line = CopyConfigurationLine()
    line.description = description
    line.version = version
    line.document_type = type_

    line.document = _make_quick_doc_dto( "quickdoc")

    return line


def make_configs( session):

    ac = ArticleConfiguration()
    session().add(ac)

    ac.customer = session().query(Customer).filter( Customer.customer_id == 18429).one()
    ac.identification_number = "4500250418"
    ac.revision_number = "C"


    c = Configuration()
    session().add(c)

    op = session().query(OrderPart).filter( OrderPart.order_part_id == 151547).one()
    op2 = session().query(OrderPart).filter( OrderPart.order_part_id == 246051).one()
    op3 = session().query(OrderPart).filter( OrderPart.order_part_id == 230512).one()

    c.parts = [op,op3]
    c.version = 1
    c.article_configuration = ac
    c.frozen = date(2018,1,31)
    c.freezer = session().query(Employee).filter(Employee.employee_id == 100).one()
    c.lines = [ _make_config_line( "Plan ZZ1D", 2, TypeConfigDoc.PLAN_3D, "plan3EDER4.3ds"),
                _make_config_line( "Config TN", 2, TypeConfigDoc.PROGRAM, "tige.gcode"),
                _make_config_line( "Config TN", 1, TypeConfigDoc.PROGRAM, "anti-tige.gcode") ]
    #ac.configurations.append( c)

    c = Configuration()
    session().add(c)

    c.parts = [op2]
    c.article_configuration = ac
    c.lines = [ _make_config_line( "Plan coupe 90°", 1, TypeConfigDoc.PLAN_2D, "90cut-RXC.doc"),
                _make_config_line( "Plan ZZ1D", 2, TypeConfigDoc.PLAN_3D, "plan3EDER4.3ds"),
                _make_config_line( "Config TN", 2, TypeConfigDoc.PROGRAM, "tige.gcode"),
                _make_config_line( "Config TN", 1, TypeConfigDoc.PROGRAM, "anti-tige.gcode") ]
    c.version = 2
    c.frozen = date(2018,2,5)
    c.freezer = session().query(Employee).filter(Employee.employee_id == 118).one()
    c.lines[2].modify_config = False
    #ac.configurations.append( c)

    c = Configuration()
    session().add(c)

    c.article_configuration = ac
    c.lines = [ _make_config_line( "Operations", 1, TypeConfigDoc.PLAN_3D, "impact_1808RXC.doc"),
                _make_config_line( "Plan ZZ1D", 2, TypeConfigDoc.PLAN_3D, "plan3EDER4.3ds"),
                _make_config_line( "Config TN", 2, TypeConfigDoc.PROGRAM, "tige.gcode"),
                _make_config_line( "Config TN", 1, TypeConfigDoc.PROGRAM, "anti-tige.gcode") ]
    c.version = 3
    c.frozen = None
    c.lines[2].modify_config = True
    #ac.configurations.append( c)


    impact = ImpactLine()
    i1 = impact

    impact.owner = session().query(Employee).filter( Employee.employee_id == 118).one()
    impact.description = "one preproduction measurement side XPZ changed"
    impact.approval = ImpactApproval.APPROVED
    impact.approved_by = session().query(Employee).filter( Employee.employee_id == 112).one()
    impact.active_date = date(2013,1,11)
    impact.document = _make_quick_doc("bliblo.doc")
    session().add(impact)
    impact.article_configuration = ac
    impact.configuration =  ac.configurations[0]
    session().flush()

    ac.configurations[0].origin_id = impact.impact_line_id
    assert i1.configuration is not None
    session().flush()
    assert i1.configuration is not None

    #print( ac.configurations)

    impact = ImpactLine()
    impact.owner = session().query(Employee).filter( Employee.employee_id == 112).one()
    assert i1.configuration is not None, i1.configuration
    impact.description = "two Aluminium weight reduction"
    impact.approval = ImpactApproval.APPROVED
    impact.approved_by = session().query(Employee).filter( Employee.employee_id == 8).one()
    impact.active_date = None
    impact.document = _make_quick_doc("impactmr_genry.doc")
    session().add(impact)
    impact.article_configuration = ac
    impact.configuration =  ac.configurations[1]
    session().flush()

    impact = ImpactLine()
    impact.owner = session().query(Employee).filter( Employee.employee_id == 8).one()
    impact.description = "three Production settings"
    impact.approval = ImpactApproval.UNDER_CONSTRUCTION
    impact.approved_by = None
    impact.active_date = None
    impact.configuration = None
    impact.document = _make_quick_doc("impact_v3.doc")
    session().add(impact)
    impact.article_configuration = ac

    impact = ImpactLine()
    impact.owner = session().query(Employee).filter( Employee.employee_id == 20).one()
    impact.description = "four Production settings v2"
    impact.approval = ImpactApproval.UNDER_CONSTRUCTION
    impact.approved_by = None
    impact.active_date = None
    impact.configuration = None
    impact.document = _make_quick_doc("impact_v3bis.doc")
    session().add(impact)
    impact.article_configuration = ac


    ac2 = ArticleConfiguration()
    session().add(ac2)
    ac2.customer = session().query(Customer).filter( Customer.customer_id == 2145).one()
    ac2.identification_number = "ZERDF354-ZXZ-2001"
    ac2.revision_number = "D"

    c = Configuration()
    session().add(c)
    # op = session().query(OrderPart).filter( OrderPart.order_part_id == 95642).one()
    # op2 = session().query(OrderPart).filter( OrderPart.order_part_id == 128457).one()
    # op3 = session().query(OrderPart).filter( OrderPart.order_part_id == 96799).one()
    # c.parts = [op, op2, op3]
    c.article_configuration = ac2
    #ac2.configurations.append( c)

    session().commit()

    assert i1.configuration is not None
    assert ac.article_configuration_id

    return [ac]


def make_configs_dto( session):

    customers = session().query(Customer).limit(5).all()

    cust1 = serialize_Customer_Customer_to_CopyCustomer( customers[0], None, {})
    cust2 = serialize_Customer_Customer_to_CopyCustomer( customers[1], None, {})

    # Limit is to alloww to run on a test DB with too many parts.
    oparts = session().query(OrderPart).limit(5).all()

    op = serialize_OrderPart_OrderPart_to_CopyOrderPart( oparts[0], None, {})
    op2 = serialize_OrderPart_OrderPart_to_CopyOrderPart( oparts[1], None, {})
    op3 = serialize_OrderPart_OrderPart_to_CopyOrderPart( oparts[2], None, {})

    employees = session().query(Employee).limit(5).all()

    employee1 = serialize_Employee_Employee_to_CopyEmployee( employees[0], None, {})
    employee2 = serialize_Employee_Employee_to_CopyEmployee( employees[1], None, {})
    employee3 = serialize_Employee_Employee_to_CopyEmployee( employees[2], None, {})

    # cust1 = CopyCustomer()
    # cust1.fullname = "Cockerill"
    # cust1.customer_id = 1232

    # cust2 = CopyCustomer()
    # cust2.fullname = "Laminer"
    # cust2.customer_id = 5589

    ac = CopyArticleConfiguration()

    ac.customer = cust1
    ac.customer_id = cust1.customer_id

    ac.identification_number = "4500250418"
    ac.revision_number = "C"
    ac.date_creation = date(2016,11,19)


    #op = session().query(OrderPart).filter( OrderPart.order_part_id == 151547).one()
    #op2 = session().query(OrderPart).filter( OrderPart.order_part_id == 246051).one()
    #op3 = session().query(OrderPart).filter( OrderPart.order_part_id == 230512).one()

    # op = CopyOrderPart()
    # op2 = CopyOrderPart()
    # op3 = CopyOrderPart()

    c = CopyConfiguration()
    c.configuration_id = 1000
    c.parts = [op,op3]
    c.version = 1
    c.article_configuration = ac
    ac.configurations.append(c)
    c.frozen = date(2018,1,31)
    c.freezer = employee1
    c.lines = [ _make_config_line_dto( "Plan ZZ1D", 2, TypeConfigDoc.PLAN_3D, "plan3EDER4.3ds"),
                _make_config_line_dto( "Config TN", 2, TypeConfigDoc.PROGRAM, "tige.gcode"),
                _make_config_line_dto( "Config TN", 1, TypeConfigDoc.PROGRAM, "anti-tige.gcode") ]
    #ac.configurations.append( c)

    ec1 = CopyEffectiveConfiguration()
    ec1.effective_configuration_id = 1101
    ec1.lines = [ _make_config_line_dto( "Plan coupe 90°", 1, TypeConfigDoc.PLAN_2D, "90cut-RXC.doc") ]
    ec1.order_part = op2
    ec1.parent_configuration = c
    ec1.parent_configuration_id = c.configuration_id

    ec2 = CopyEffectiveConfiguration()
    ec2.effective_configuration_id = 1102
    ec2.lines = [ _make_config_line_dto( "Plan coupe ZULU TANGO 90°", 1, TypeConfigDoc.PLAN_2D, "90cut-RXC.doc") ]
    ec2.order_part = op3
    ec2.parent_configuration = c
    ec2.parent_configuration_id = c.configuration_id

    c.effective_configurations = [ec1, ec2]



    c = CopyConfiguration()

    c.parts = [op2]
    c.article_configuration = ac
    ac.configurations.append(c)
    c.lines = [ _make_config_line_dto( "Plan coupe 90°", 1, TypeConfigDoc.PLAN_2D, "90cut-RXC.doc"),
                _make_config_line_dto( "Plan ZZ1D", 2, TypeConfigDoc.PLAN_3D, "plan3EDER4.3ds"),
                _make_config_line_dto( "Config TN", 2, TypeConfigDoc.PROGRAM, "tige.gcode"),
                _make_config_line_dto( "Config TN", 1, TypeConfigDoc.PROGRAM, "anti-tige.gcode") ]
    c.version = 2
    c.frozen = date(2018,2,5)
    c.freezer = employee1
    c.lines[2].modify_config = False
    #ac.configurations.append( c)

    c = CopyConfiguration()

    c.article_configuration = ac
    ac.configurations.append(c)
    c.lines = [ _make_config_line_dto( "Operations", 1, TypeConfigDoc.PLAN_3D, "impact_1808RXC.doc"),
                _make_config_line_dto( "Plan ZZ1D", 2, TypeConfigDoc.PLAN_3D, "plan3EDER4.3ds"),
                _make_config_line_dto( "Config TN", 2, TypeConfigDoc.PROGRAM, "tige.gcode"),
                _make_config_line_dto( "Config TN", 1, TypeConfigDoc.PROGRAM, "anti-tige.gcode") ]
    c.version = 3
    c.frozen = date(2018,3,5)
    c.freezer = employee2
    c.frozen = None
    c.freezer = None
    c.lines[3].modify_config = True
    #ac.configurations.append( c)


    impact = CopyImpactLine()
    i1 = impact

    impact.owner = employee2
    impact.description = "one preproduction measurement side XPZ changed"
    impact.approval = ImpactApproval.APPROVED
    impact.approved_by = employee3
    impact.active_date = date(2013,1,11)
    impact.document = _make_quick_doc_dto("bliblo.doc")
    impact.article_configuration = ac
    ac.impacts.append(impact)
    impact.configuration =  ac.configurations[0]

    ac.configurations[0].origin_id = impact.impact_line_id
    assert i1.configuration is not None
    assert i1.configuration is not None

    #print( ac.configurations)

    impact = CopyImpactLine()
    impact.owner = employee2
    assert i1.configuration is not None, i1.configuration
    impact.description = "two Aluminium weight reduction"
    impact.approval = ImpactApproval.APPROVED
    impact.approved_by = employee1
    impact.active_date = None
    impact.document = _make_quick_doc_dto("impactmr_genry.doc")
    impact.article_configuration = ac
    ac.impacts.append(impact)
    impact.configuration =  ac.configurations[1]

    impact = CopyImpactLine()
    impact.owner = employee3
    # impact.owner = session().query(Employee).filter( Employee.employee_id == 8).one()
    impact.description = "three Production settings"
    impact.approval = ImpactApproval.UNDER_CONSTRUCTION
    impact.approved_by = None
    impact.active_date = None
    impact.configuration = None
    impact.document = _make_quick_doc_dto("impact_v3.doc")
    impact.article_configuration = ac
    impact.configuration =  ac.configurations[2]
    ac.impacts.append(impact)

    # impact = CopyImpactLine()
    # impact.owner = employee1
    # #impact.owner = session().query(Employee).filter( Employee.employee_id == 20).one()
    # impact.description = "four Production settings v2"
    # impact.approval = ImpactApproval.UNDER_CONSTRUCTION
    # impact.approved_by = None
    # impact.active_date = None
    # impact.configuration = None
    # impact.document = _make_quick_doc_dto("impact_v3bis.doc")
    # impact.article_configuration = ac
    # ac.impacts.append(impact)


    # -------------------------------------------------------------------------

    ac2 = CopyArticleConfiguration()
    # ac2.customer = session().query(Customer).filter( Customer.customer_id == 2145).one()
    ac2.identification_number = "ZERDF354-ZXZ-2001"
    ac2.revision_number = "D"
    ac2.date_creation = date(2016,11,12)
    ac2.customer = cust2
    ac2.customer_id = cust2.customer_id

    c = CopyConfiguration()
    # op = session().query(OrderPart).filter( OrderPart.order_part_id == 95642).one()
    # op2 = session().query(OrderPart).filter( OrderPart.order_part_id == 128457).one()
    # op3 = session().query(OrderPart).filter( OrderPart.order_part_id == 96799).one()
    # c.parts = [op, op2, op3]
    c.article_configuration = ac2
    #ac2.configurations.append( c)

    assert i1.configuration is not None

    return [ac, ac2]
