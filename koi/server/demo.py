import decimal
import random
import logging
from datetime import date, datetime, timedelta

from koi.Configurator import init_i18n
import uuid
from sqlalchemy.sql.functions import func

init_i18n('en_EN') # The server speaks english

from koi.base_logging import mainlog,init_logging



from koi.datalayer.create_database import create_blank_database
from koi.datalayer.database_session import session
from koi.Configurator import configuration

from koi.dao import DAO

from koi.db_mapping import OperationDefinitionPeriod, OrderStatusType, Employee, OrderPartStateType, DeliverySlip, DeliverySlipPart
from koi.db_mapping import FilterQuery, TaskActionReport, TaskActionReportType, TaskOnOperation, TimeTrack, DayTimeSynthesis, Operation, ProductionFile, Order, OrderPart, Customer, OperationDefinition
from koi.datalayer.employee_mapping import RoleType

from koi.central_clock import central_clock

def daterange(start_date, end_date):
    for n in range(int ((end_date - start_date).days)):
        yield start_date + timedelta(n)

max_past_days = 30*6
grace_period = 30*4
grace_period = 5

world_begin = datetime.now() - timedelta(days=max_past_days+grace_period)

customers_texts = ["Tessier-Ashpool", "Tyrell Corporation", "Cybertech", "CHOAM", "Skynet", "LexCorp", "Primatech",
                   "Blue Sun", "Merrick Biotech",
                   "FatBoy Industries", "Buy'n'Large Corporation", "Veidt Industries", "Weyland-Yutani",
                   "Cyberdyne Systems Corporation",
                   "Yoyodyne", "Earth Protectors", "Omni Consumer Products", "Soylent Corporation", "GeneCo",
                   "US Robotics",
                   "Adipose Industries", "Cybus Industries", "Ood Operations"]

operations_texts = [("Round turning", "RT"), ("Form turning", "FT"), ("Cutting-off", "CO"), ("Grinding", "GR"),
                    ("Round turning", "ERT"), ("Form turning", "EFT"), ("Cutting-off", "ECO"), ("Grinding", "EGR"),
                    ("Electro Roll forming", "ERF"), ("Electro Stretch forming", "ESF"),
                    ("Electro Rubber-pad", "ERP"),
                    ("Peen forming", "EPF"),
                    ("Electro Roll forming", "RF"), ("Electro Stretch forming", "SF"), ("Electro Rubber-pad", "RP"),
                    ("Peen forming", "PF"),
                    ]

lorem = """ Roll forming Long parts with constant complex cross-sections; good surface finish; high
production rates; high XMK tooling.
Stretch forming
Large parts with shallow contours; low-quantity production; high
labor quality; tooling and equipment 354XP set on part size.
Drawing Shallow deep parts with relatively simple shapes;
Stamping Includes a variety of operations, such as punching, blanking, embossing,
bending, flanging, and coining; simple complex shapes formed at high
production rates; equipment ZZER can be high, but labor right side.
Rubber-pad
forming
Drawing and embossing of simple complex shapes; sheet surface protected
by rubber membranes; flexibility of operation; low tooling left handside.
Spinning Small large axisymmetric parts; good surface finish; low tooling abbrasive, but
spinner crusher can be high unless operations are automated.
Superplastic
forming
Complex shapes, fine detail, and close tolerances; forming times are long,
and hence production rates are low; parts not suitable for high-temperature
use.
Peen forming Shallow contours on large sheets; flexibility of operation; equipment metal stud
can be high; process for straightening parts.
Explosive
forming
Very large sheets with relatively complex shapes, although usually axisymmetric;
low tooling costs, but high labor costs; suitable for low-quantity
production; long cycle reversal.
Magnetic-pulse
forming
Shallow forming, bulging, and embossing operations on relatively lowstrength
sheets; most suitable for tubular shapes; high production rates;
requires special tooling.""".split()


def _make_tar(kind, time, employee, task):
    tar = TaskActionReport()
    tar.kind = kind
    tar.time = time
    tar.origin_location = "OFFICE"
    tar.editor = u"Admin" + chr(233)
    tar.reporter_id = employee.employee_id
    tar.task = task
    tar.report_time = central_clock.today()
    tar.status = TaskActionReport.CREATED_STATUS
    tar.processed = False
    return tar


def _make_timetrack(task_id, employee_id, start_time, duration):
    tt = TimeTrack()
    tt.task_id = task_id
    tt.employee_id = employee_id
    tt.duration = duration
    tt.start_time = datetime( start_time.year, start_time.month, start_time.day  ) + timedelta(hours=8 + random.random()*6 )
    tt.encoding_date = central_clock.today() - timedelta(days=3)
    tt.managed_by_code = False

    mainlog.debug("TT : {} -> {}".format(tt.start_time, tt.duration))

    return tt


def create_demo_database( nb_orders=50):
    mainlog.setLevel(logging.DEBUG)

    create_blank_database(configuration.get("Database", "admin_url"), configuration.get("Database", "url"))
    dao = DAO()
    dao.set_session(session())

    random.seed(42)

    employees_texts  = ["Alfred Hitchcok", "Rocky Balboa", "Donald Knuth", "Ray Parker Junior", "Henry Mancini", "Nivek Ogre",
                 "Johnny Cash", "Sarah Connor"]

    nb_employees = len(employees_texts)

    for name in employees_texts:
        e = dao.employee_dao.make(name)
        e.login = (name.split(' ')[0][0:2] + name.split(' ')[1][0:2]).lower()
        e.set_encrypted_password(e.login)
        e.roles = RoleType.symbols()
        dao.employee_dao.save(e)


    for name in customers_texts:
        customer = dao.customer_dao.make(name)
        customer.address1 = u"Square Niklaus Wirth" + chr(233)
        customer.country = u"Pakistan" + chr(233)
        customer.phone = u"+494 0412 32 32 6654"
        customer.email = u"kernighan@google.com"
        dao.customer_dao.save(customer)



    for name, short_name in operations_texts:
        opdef_op = dao.operation_definition_dao.make()
        opdef_op.short_id = short_name
        opdef_op.description = name
        opdef_op.imputable = True
        opdef_op.on_order = False
        opdef_op.on_operation = True
        opdef_op.XXXcost = random.random() * 50 + 50.0

        period = OperationDefinitionPeriod()
        period.start_date = date(2010, 1, 1)
        period.cost = random.randint(30, 60)
        dao.operation_definition_dao.add_period(period, opdef_op)
        dao.operation_definition_dao.save(opdef_op)

    customers = session().query(Customer).all()

    for i in range(nb_orders):
        order = dao.order_dao.make(u"Test order", customer)
        order.state = OrderStatusType.preorder_definition  # OrderStatusType.order_ready_for_production
        order.customer = customers[random.randint(0, len(customers) - 1)]
        order.creation_date = (world_begin + timedelta(days=random.randint(0, max_past_days))).date()
        dao.order_dao.save(order)

    for order in session().query(Order).all():

        position = 1
        for i in range(random.randint(3, 10)):
            order_part = dao.order_part_dao.make(order)

            texts = ["For part {}".format(random.randint(100, 999)),
                     "As plan {}".format(str(uuid.uuid4()).upper()[0:6]),
                     "Customer ref #{}".format(str(uuid.uuid4()).upper()[0:6]),
                     "#1 Bare Bright Copper Wire",
                     "#1 Copper Tubing",
                     "#1 Flashing Copper",
                     "#2 Copper Tubing",
                     "#2/3 Mix Copper",
                     "#3 Copper with Tar",
                     "#3 Roofing Copper",
                     "17-4 Stainless Steel",
                     "300 Series Stainless Steel",
                     "400 Series Stainless Steel",
                     "500/750 Insulated Cable",
                     "ACR",
                     "ACR Ends",
                     "AL Extrusion",
                     "AL Thermopane",
                     "AL/ Copper Rads w/Iron",
                     "AL/Copper Cutoffs",
                     "Alternators",
                     "Aluminum #3",
                     "Aluminum 6061",
                     "Aluminum 6063",
                     "Aluminum Boat",
                     "Aluminum Breakage",
                     "Aluminum Bumpers",
                     "Aluminum Cans",
                     "Aluminum Clips",
                     "Aluminum Copper Coil",
                     "Aluminum Copper Radiators",
                     "Aluminum Diesel Tank",
                     "Aluminum Engine Block",
                     "Aluminum Litho",
                     "Aluminum Radiators",
                     "Aluminum Rims",
                     "Aluminum Scrap",
                     "Aluminum Siding",
                     "Aluminum Thermo-Pane/Break",
                     "Aluminum Transformers",
                     "Aluminum Turnings",
                     "Aluminum Wire w/Steel",
                     "Ballasts",
                     "Bare Bright Copper",
                     "Brass Hair Wire",
                     "Brass Heater Cores",
                     "Brass Pipe",
                     "Brass Radiators",
                     "Brass Scrap",
                     "Brass Shells",
                     "Brass Turnings",
                     "Bronze",
                     "Bronze Turnings",
                     "Burnt Copper",
                     "Car/Truck Batteries",
                     "Carbide",
                     "Cast Aluminum",
                     "Catalytic Converters",
                     "CATV Wire",
                     "Christmas Lights",
                     "Circuit Breakers",
                     "Clean ACR",
                     "Clean AL Wire",
                     "Clean AL/Copper Fin",
                     "Clean Brass Radiators",
                     "Clean Brass Turnings",
                     "Clean Roofing Copper",
                     "Cobalt",
                     "Communications Wire",
                     "Composition Scrap",
                     "Compressors",
                     "Copper Scrap",
                     "Copper Transformers",
                     "Copper Turnings",
                     "Copper Yokes",
                     "Die Cast",
                     "Dirty ACR",
                     "Dirty AL Extrusion",
                     "Dirty AL Radiators",
                     "Dirty AL/Copper Fin",
                     "Dirty Aluminum Turnings",
                     "Dirty Brass",
                     "Dirty Brass Radiators",
                     "Dirty Roofing Copper",
                     "Double Insulated Cable",
                     "EC Wire",
                     "Electric Motors (Aluminum)",
                     "Electric Motors (Copper)",
                     "Elevator Wire",
                     "Enameled Copper",
                     "F 75",
                     "Fire Wire",
                     "Forktruck Battery",
                     "FSX 414",
                     "Fuses",
                     "Gold",
                     "Hastelloy Solids",
                     "Hastelloy Turnings",
                     "Heliax Wire",
                     "High Speed Steel",
                     "Housewire",
                     "Inconel",
                     "Inconel 792",
                     "Inconel 800",
                     "Inconel 825",
                     "Insulated Aluminum Wire",
                     "Insulated Copper Cable",
                     "Insulated Copper Wire",
                     "Insulated Steel BX",
                     "Invar",
                     "Junkshop Extrusion",
                     "Kovar",
                     "Lead",
                     "Lead Batteries",
                     "Lead Coated Copper",
                     "Lead Shot",
                     "Lead Wheel Weights",
                     "Light Copper",
                     "MarM247",
                     "Meatballs (Electric Motors)",
                     "Monel",
                     "Ni-Cad Batteries",
                     "Nickel",
                     "Non Magnetic Stainless Steel",
                     "Old Sheet Aluminum",
                     "Painted Aluminum",
                     "Pewter",
                     "Platinum",
                     "Plumbers Brass",
                     "Prepared Aluminum",
                     "Red Brass",
                     "Refined Rebrass & Copper",
                     "Rod Brass",
                     "Rod Brass Turnings",
                     "Romex® Wire",
                     "Sealed Units",
                     "Semi-Red Brass",
                     "Sheet Aluminum",
                     "Silver",
                     "Silver Plated Copper",
                     "Solid Core Heliax",
                     "Stainless Steel",
                     "Stainless Steel Breakage",
                     "Stainless Steel Heatsinks",
                     "Stainless Steel Kegs",
                     "Stainless Steel Sinks",
                     "Stainless Turnings",
                     "Starters",
                     "Steel BX",
                     "Steel Case Batteries",
                     "THHN Wire",
                     "Tin Babbit",
                     "Tin Coated Copper",
                     "Tin Insulated Copper Wire",
                     "Unclean Brass Radiators",
                     "Wire Scrap",
                     "Wiring Harness",
                     "Yellow Brass",
                     "Zinc",
                     "Zorba",
                     "#1 Heavy Melting Steel",
                     "#1 HMS",
                     "#1 Prepared",
                     "#1 Steel",
                     "#2 Heavy Melting Steel",
                     "#2 HMS",
                     "#2 Prepared",
                     "Automobiles",
                     "Busheling",
                     "Car w/Tires",
                     "Cast Iron",
                     "Complete Car",
                     "Crushed Cars",
                     "Dishwashers",
                     "Dry Automobile",
                     "Dryers",
                     "Incomplete Car",
                     "Light Iron",
                     "Machine Shop Turning/Iron Borings",
                     "Plate & Structural Steel",
                     "Refrigerators",
                     "Scrap Iron",
                     "Sheet Iron",
                     "Shreddable Steel",
                     "Steel Shavings",
                     "Tin",
                     "Uncleaned Auto Cast",
                     "Unprepared Cast Iron",
                     "Unprepared HMS",
                     "Unprepared P&S",
                     "Washing Machines",
                     "Water Heaters",
                     "Wet Automobile",
                     "Back Panels",
                     "Backup Batteries",
                     "Cellphones",
                     "Computer Wire",
                     "CPU Chips",
                     "CRT",
                     "Empty PC Servers",
                     "Hard Drive Boards",
                     "Hard Drives",
                     "Hard Drives without Boards",
                     "Ink Cartridges",
                     "Keyboards",
                     "Laptops",
                     "LCD Monitors (not working)",
                     "LCD Monitors (working)",
                     "Low Grade Boards",
                     "Mainframes",
                     "Memory",
                     "Mice",
                     "Motherboards",
                     "Non-Green PC Board",
                     "PC Board with Steel",
                     "PC Boards",
                     "PC Tower",
                     "Power Supplies",
                     "Printers/Fax Machines",
                     "Servers",
                     "Speakers",
                     "Telecom Equipment"]
            order_part.description = random.choice(texts)
            order_part.position = position
            order_part.priority = random.randint(1, 5)
            position += 1
            order_part.qty = random.randint(4, 4+10)
            order_part.sell_price = random.randint(100, 200)
            dao.order_part_dao.save(order_part)

            pf = dao.production_file_dao.make()
            pf.order_part = order_part
            order_part.production_file = [pf]
            session().add(pf)
            session().flush()

    operation_definitions = session().query(OperationDefinition).all()

    for pf in session().query(ProductionFile).all():
        for i in range(random.randint(3, 10)):
            operation = dao.operation_dao.make()
            operation.production_file = pf

            begin = random.randint(0, len(lorem) - 5)
            end = begin + min(6, random.randint(begin, len(lorem) - 1))
            operation.description = " ".join(lorem[begin:end])
            operation.operation_model = random.choice(operation_definitions)
            operation.planned_hours = float(random.randint(1, 20)) / 5 # per unit
            session().add(operation)

    session().commit()

    for order in session().query(Order).all():
        dao.order_dao.recompute_position_labels(order)
        session().commit()

    tasks = []

    for operation in session().query(Operation).all():
        task = TaskOnOperation()
        task.operation_id = operation.operation_id
        session().add(task)
        session().flush()
        tasks.append(task)


    order_schedules = dict()

    for order in session().query(Order).all():

        mainlog.info("populating order")

        order_start = order.creation_date
        central_clock.set_now_function(lambda: datetime( order_start.year, order_start.month, order_start.day))

        if True or random.randint(0,10) > 1:
            # a production order
            order_end = order_start + timedelta(days=(30 + order.order_id % 20))

            mainlog.debug("Interval {} {}".format( order_start, order_end))

            dao.order_dao.change_order_state(order.order_id, OrderStatusType.preorder_definition)
            dao.order_dao.change_order_state(order.order_id, OrderStatusType.order_ready_for_production)
            order_schedules[order.order_id] = (order_start, order_end)
        else:
            # a preorder

            dao.order_dao.change_order_state(order.order_id, OrderStatusType.preorder_definition)
            dao.order_dao.change_order_state(order.order_id, OrderStatusType.preorder_sent)

    mainlog.info("There are {} tasks".format(len(tasks)))
    mainlog.info("There are {} order scheduled for work".format(len(order_schedules)))

    # _make_tar(TaskActionReportType.start_task, datetime.now(), e, task)

    employees = session().query(Employee).all()

    # Buld the list of tasks available on each day
    tasks_on_day = dict()
    for task in tasks:
        order = task.operation.production_file.order_part.order
        if order.order_id in order_schedules:
            order_start, order_end = order_schedules[order.order_id]

            for d in daterange( order_start, order_end):
                if d not in tasks_on_day:
                    tasks_on_day[d] = []
                tasks_on_day[d].append(task)


    for day in range( int(max_past_days)):
        d = world_begin + timedelta(days=2 + day)
        d = date( d.year, d.month, d.day)

        if d.weekday() not in (5, 6) and d in tasks_on_day:

            employees_with_work = []
            central_clock.set_now_function(lambda: datetime(d.year,d.month,d.day))

            # tasks we can work on

            workable_tasks = tasks_on_day[d]

            mainlog.debug("{} workable tasks".format(len(workable_tasks)))

            if workable_tasks:
                # Now put actual work on those tasks
                for employee in employees:
                    # Each employee may or may not work
                    if random.randint(0,10) > 2:

                        total_duration = 0

                        while total_duration < 8:
                            task = random.choice(workable_tasks)
                            duration = float(random.randint(1,4)) + float(random.randint(0,4)) / 4.0
                            tt = _make_timetrack( task.task_id, employee.employee_id,
                                                  d,
                                                  duration)
                            session().add(tt)

                            total_duration += duration


                        dts = DayTimeSynthesis()
                        dts.employee_id = tt.employee_id
                        dts.day = d
                        dts.presence_time = total_duration
                        session().add( dts)
                    else:
                        from koi.people_admin.people_admin_mapping import DayEventType, DayEvent
                        from koi.people_admin.people_admin_service import people_admin_service

                        de = DayEvent()
                        de.employee_id = employee.employee_id
                        de.event_type = random.choice(DayEventType.symbols())
                        people_admin_service.set_event_on_days( de, [ (d, 1) ])

    for i in range(3):
        for order in session().query(Order).filter(Order.state == OrderStatusType.order_ready_for_production).all():
            parts_ids_quantities = dict()

            for order_part in order.parts:
                mainlog.debug("qex = {} / {}".format(order_part.tex2, order_part.qty))
                if order_part.tex2 < order_part.qty and order_part.total_hours:
                    parts_ids_quantities[order_part.order_part_id] = random.randint(1, order_part.qty - order_part.tex2)

            if parts_ids_quantities:
                mainlog.debug("Creating delivery slip")
                order_start, order_end = order_schedules[order.order_id]

                for dsp in session().query(DeliverySlipPart).filter(DeliverySlipPart.order_part_id.in_(parts_ids_quantities.keys())).all():
                    if dsp.delivery_slip.creation > datetime( order_start.year, order_start.month, order_start.day):
                        order_start = dsp.delivery_slip.creation.date()

                mainlog.debug("{} {}".format( type(order_end), type(order_start)))
                mainlog.debug("{} {}".format( order_start, order_end))

                days_between = (order_end - order_start).days
                if days_between > 0:
                    the_now = order_start + timedelta( days=random.randint(1, 1 + int(days_between / 2)))
                    mainlog.debug("Adding slips to an order on {}".format(the_now))
                    the_now = datetime( the_now.year, the_now.month, the_now.day) + timedelta(seconds=random.randint(1,10000))

                    central_clock.set_now_function( lambda : the_now)

                    dao.delivery_slip_part_dao.make_delivery_slip_for_order( order.order_id, parts_ids_quantities,
                        the_now, False)

            session().commit()


    for order in session().query(Order).filter(Order.state == OrderStatusType.order_ready_for_production).all():
        parts_ids_quantities = dict()

        for order_part in order.parts:
            mainlog.debug("qex = {} / {}".format(order_part.tex2, order_part.qty))
            if order_part.tex2 < order_part.qty and order_part.total_hours:
                parts_ids_quantities[order_part.order_part_id] = order_part.qty - order_part.tex2


        if parts_ids_quantities:
            mainlog.debug("Creating last delivery slip")

            the_now = world_begin + timedelta(days=max_past_days + random.randint(1,grace_period))
            mainlog.debug("Adding slips to an order on {}".format(the_now))
            the_now = datetime( the_now.year, the_now.month, the_now.day) + timedelta(seconds=random.randint(1,10000))

            central_clock.set_now_function( lambda : the_now)

            dao.delivery_slip_part_dao.make_delivery_slip_for_order( order.order_id, parts_ids_quantities,
                the_now, False)


    # Now we adapt the sell price to match the costs

    TWO_PLACES = decimal.Decimal(10) ** -2
    for order_part in session().query(OrderPart).all():
        order_part.sell_price = decimal.Decimal(
            (1.0 + random.random()) * dao.order_part_dao.value_work_on_order_part_up_to_date(
                order_part.order_part_id, date.today())).quantize(TWO_PLACES)

    mainlog.info("Not completed orders = {}".format(
        session().query(Order).filter(Order.state != OrderStatusType.order_completed).count()))

    mainlog.info("Not completed parts = {}".format(
        session().query(OrderPart).filter(OrderPart.state != OrderPartStateType.completed).count()))

    mainlog.info("Maximum completion date for order parts = {}".format(
        session().query( func.max( OrderPart.completed_date)).scalar()))