# -*- coding: utf-8 -*-

import hashlib
import os

if __name__ == "__main__":
    from koi.Configurator import load_configuration,init_i18n
    load_configuration()
    init_i18n()

from koi.Configurator import mainlog,configuration
from koi.db_mapping import *
from koi.datalayer.database_session import init_db_session,session,db_engine, reopen_session, disconnect_db
from koi.datalayer.audit_trail_mapping import AuditTrail
from koi.datalayer.employee_mapping import RoleType
from koi.doc_manager.documents_mapping import *
from koi.datalayer.supply_order_mapping import *
from koi.datalayer.supplier_mapping import *
from koi.datalayer.quality import *
from koi.machine.machine_mapping import *
from koi.people_admin.people_admin_mapping import DayEvent
# from koi.stock.stock_mapping import StockItem
from koi.user_mgmt.user_role_mapping import UserClass
from koi.doc_manager.documents_service import documents_service
from koi.Configurator import resource_dir

from koi.reporting.preorder.preorder_report import HORSE_TEMPLATE as HORSE_TEMPLATE_PREORDER
from koi.reporting.preorder.preorder_report import HORSE_REFERENCE as HORSE_REFERENCE_PREORDER
from koi.reporting.preorder.preorder_report import HORSE_TITLE as HORSE_TITLE_PREORDER

from koi.reporting.order_confirmation.order_confirmation_report2 import HORSE_TEMPLATE as HORSE_TEMPLATE_ORDER_CONFIRMATION
from koi.reporting.order_confirmation.order_confirmation_report2 import HORSE_REFERENCE as HORSE_REFERENCE_ORDER_CONFIRMATION
from koi.reporting.order_confirmation.order_confirmation_report2 import HORSE_TITLE as HORSE_TITLE_ORDER_CONFIRMATION

def drop_functions(current_session):

    try:
        current_session.connection().execute("SET search_path TO {}".format("horse"))
    except Exception as ex:
        # Schema's not there, so nothing to delete
        mainlog.exception(ex)
        return

    current_session.connection().execute("BEGIN")

    try:
        # current_session.connection().execute("DROP TRIGGER IF EXISTS control_orders_accounting ON orders")
        # current_session.connection().execute("DROP TRIGGER IF EXISTS control_orders_accounting2 ON orders")
        # current_session.connection().execute("DROP TRIGGER IF EXISTS control_orders_accounting3 ON orders")
        current_session.connection().execute("DROP TRIGGER IF EXISTS control_orders_accounting_delete ON {}.orders".format(DATABASE_SCHEMA))
        current_session.connection().execute("DROP TRIGGER IF EXISTS control_orders_accounting_update ON {}.orders".format(DATABASE_SCHEMA))
        current_session.connection().execute("DROP TRIGGER IF EXISTS control_orders_accounting_insert ON {}.orders".format(DATABASE_SCHEMA))
        current_session.connection().execute("DROP TRIGGER IF EXISTS control_delivery_slips_delete ON {}.delivery_slip".format(DATABASE_SCHEMA))
        current_session.connection().execute("DROP TRIGGER IF EXISTS control_delivery_slips_update ON {}.delivery_slip".format(DATABASE_SCHEMA))
        current_session.connection().execute("DROP TRIGGER IF EXISTS control_delivery_slips_insert ON {}.delivery_slip".format(DATABASE_SCHEMA))


        current_session.connection().execute("COMMIT")
    except:
        current_session.connection().execute("ROLLBACK")

    schema_name = "horse"

    current_session.connection().execute("BEGIN")
    current_session.connection().execute("DROP FUNCTION IF EXISTS {0}.check_orders_gapless_sequence()".format(DATABASE_SCHEMA))
    current_session.connection().execute("DROP FUNCTION IF EXISTS {0}.check_orders_gapless_sequence_insert()".format(DATABASE_SCHEMA))
    current_session.connection().execute("DROP FUNCTION IF EXISTS {0}.check_orders_gapless_sequence_delete()".format(DATABASE_SCHEMA))
    current_session.connection().execute("DROP FUNCTION IF EXISTS {0}.check_orders_gapless_sequence_update()".format(DATABASE_SCHEMA))

    current_session.connection().execute("DROP FUNCTION IF EXISTS {0}.check_delivery_slips_gapless_sequence_insert()".format(DATABASE_SCHEMA))
    current_session.connection().execute("DROP FUNCTION IF EXISTS {0}.check_delivery_slips_gapless_sequence_delete()".format(DATABASE_SCHEMA))
    current_session.connection().execute("DROP FUNCTION IF EXISTS {0}.check_delivery_slips_gapless_sequence_update()".format(DATABASE_SCHEMA))


    current_session.connection().execute("DROP FUNCTION IF EXISTS {0}.gseq_nextval(t text)".format(DATABASE_SCHEMA))
    current_session.connection().execute("COMMIT")

    mainlog.info("Dropped all functions")

def create_functions(current_session):
    mainlog.info("Creating all function")

    current_session.connection().execute("BEGIN")
    current_session.connection().execute("""CREATE FUNCTION {0}.gseq_nextval(t text) RETURNS integer AS
$BODY$    DECLARE
       n integer;
    BEGIN
       -- The select also puts a LOCK on the table, ensuring nobody
       -- else can increase the number while we're in our transaction
       SELECT INTO n gseq_value+1 FROM {0}.gapless_seq WHERE gseq_name = t FOR UPDATE;

       IF n IS NULL THEN
          RAISE EXCEPTION 'Gapless sequence does not exist in the gapless sequence table';
       END IF;

       -- Update will release the lock once the current TRANSACTION ends
       UPDATE {0}.gapless_seq SET gseq_value = n WHERE gseq_name = t;
       RETURN n;
    END;$BODY$
    LANGUAGE plpgsql VOLATILE;""".format(DATABASE_SCHEMA))

    current_session.connection().execute("""CREATE FUNCTION {0}.check_orders_gapless_sequence_insert() RETURNS trigger AS $$
DECLARE
    difference NUMERIC;
    min_id NUMERIC;
    max_id NUMERIC;
    cnt NUMERIC;
BEGIN
    -- Call this AFTER INSERT

    IF NEW.accounting_label IS NULL THEN
        -- we're only interested in orders; not pre orders
        RETURN NULL;
    END IF;

    SELECT min(accounting_label) INTO min_id FROM {0}.orders;
    SELECT max(accounting_label) INTO max_id FROM {0}.orders;
    SELECT count(*) INTO cnt FROM {0}.orders WHERE accounting_label IS NOT NULL;

    IF cnt > 1 AND max_id - min_id + 1  <> cnt THEN
        RAISE EXCEPTION 'Gapless sequence has been broken';
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;""".format(DATABASE_SCHEMA))


    current_session.connection().execute("""CREATE FUNCTION {0}.check_orders_gapless_sequence_delete() RETURNS trigger AS $$
DECLARE
    difference NUMERIC;
    min_id NUMERIC;
    max_id NUMERIC;
    cnt NUMERIC;
    n INTEGER;
BEGIN
    -- Call this *only* AFTER DELETE
    -- Rememeber ! OLD is a standard PostgreSQL parameter denoting the row
    -- we're about to delete

    IF OLD.accounting_label IS NULL THEN
        -- we're only interested in orders; not pre orders
        RETURN NULL;
    END IF;

    -- The following select is done only to lock the gseq row.
    -- The consequence of this is that all inserts will be delayed
    -- and, consequently, the following three selects (max_id,min_id,count)
    -- will be reliable. That is, they will concern the result of
    -- the DELETE statement *only* (ie not mixed with inserts).
    -- Moreover, since the UPDATE don't allow any change of
    -- accouting label, the UPDATE won't interfere with the next 3
    -- selects

    SELECT INTO n gseq_value FROM {0}.gapless_seq WHERE gseq_name = 'order_id' FOR UPDATE;
    SELECT min(accounting_label) INTO min_id FROM {0}.orders WHERE accounting_label IS NOT NULL;
    SELECT max(accounting_label) INTO max_id FROM {0}.orders WHERE accounting_label IS NOT NULL;
    SELECT count(*)              INTO cnt    FROM {0}.orders WHERE accounting_label IS NOT NULL;


    IF cnt > 0 AND (max_id - min_id + 1)  <> cnt THEN
        -- Pay attention, the condition above is incomplete because it allows
        -- delete of either first row or last row

        RAISE EXCEPTION 'DB: Gapless sequence has been broken';
    ELSE
        -- We allow a DELETE on the last order. Everything else
        -- will trigger an exception.

        IF OLD.accounting_label = n THEN
            UPDATE {0}.gapless_seq SET gseq_value = n - 1 WHERE gseq_name = 'order_id';
            RETURN NULL;
        ELSE
            RAISE EXCEPTION 'DB: One can only delete the last order';
        END IF;

    END IF;
END;
$$ LANGUAGE plpgsql;""".format(DATABASE_SCHEMA))



    current_session.connection().execute("""CREATE FUNCTION {0}.check_orders_gapless_sequence_update() RETURNS trigger AS $$
DECLARE
    cnt NUMERIC;
BEGIN
    IF (OLD.accounting_label IS NOT NULL) AND (NEW.accounting_label IS NULL OR NEW.accounting_label <> OLD.accounting_label) THEN
        RAISE EXCEPTION 'One cannot change the id of an order';
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;""".format(DATABASE_SCHEMA))



    current_session.connection().execute("""CREATE FUNCTION {0}.check_delivery_slips_gapless_sequence_insert() RETURNS trigger AS $$
DECLARE
    difference NUMERIC;
    min_id NUMERIC;
    max_id NUMERIC;
    cnt NUMERIC;
BEGIN
    -- Call this AFTER INSERT

    IF NEW.delivery_slip_id IS NULL THEN
        -- we're only interested in orders; not pre orders
        RETURN NULL;
    END IF;

    SELECT min(delivery_slip_id) INTO min_id FROM {0}.delivery_slip;
    SELECT max(delivery_slip_id) INTO max_id FROM {0}.delivery_slip;
    SELECT count(*) INTO cnt FROM {0}.delivery_slip WHERE delivery_slip_id IS NOT NULL;

    IF cnt > 1 AND max_id - min_id + 1  <> cnt THEN
        RAISE EXCEPTION 'Gapless sequence has been broken';
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;""".format(DATABASE_SCHEMA))


    current_session.connection().execute("""CREATE FUNCTION {0}.check_delivery_slips_gapless_sequence_delete() RETURNS trigger AS $$
DECLARE
    difference NUMERIC;
    min_id NUMERIC;
    max_id NUMERIC;
    cnt NUMERIC;
    n INTEGER;
BEGIN
    -- Call this *only* AFTER DELETE
    -- Rememeber ! OLD is a standard PostgreSQL parameter denoting the row
    -- we're about to delete

    IF OLD.delivery_slip_id IS NULL THEN
        -- we're only interested in orders; not pre orders
        RETURN NULL;
    END IF;

    -- The following select is done only to lock the gseq row.
    -- The consequence of this is that all inserts will be delayed
    -- and, consequently, the following three selects (max_id,min_id,count)
    -- will be reliable. That is, they will concern the result of
    -- the DELETE statement *only* (ie not mixed with inserts).
    -- Moreover, since the UPDATE don't allow any change of
    -- accouting label, the UPDATE won't interfere with the next 3
    -- selects

    SELECT INTO n gseq_value FROM {0}.gapless_seq WHERE gseq_name = 'delivery_slip_id' FOR UPDATE;
    SELECT min(delivery_slip_id) INTO min_id FROM {0}.delivery_slip;
    SELECT max(delivery_slip_id) INTO max_id FROM {0}.delivery_slip;
    SELECT count(*)              INTO cnt    FROM {0}.delivery_slip;


    IF cnt > 0 AND (max_id - min_id + 1)  <> cnt THEN
        -- Pay attention, the condition above is incomplete because it allows
        -- delete of either first row or last row

        RAISE EXCEPTION 'Gapless sequence has been broken in delivery slips';
    ELSE
        -- We allow a DELETE on the last order. Everything else
        -- will trigger an exception.

        IF OLD.delivery_slip_id = n THEN
            UPDATE {0}.gapless_seq SET gseq_value = n - 1 WHERE gseq_name = 'delivery_slip_id';
            RETURN NULL;
        ELSE
            RAISE EXCEPTION 'One can only delete the last delivery slip';
        END IF;

    END IF;
END;
$$ LANGUAGE plpgsql;""".format(DATABASE_SCHEMA))

    current_session.connection().execute("""CREATE FUNCTION {0}.check_delivery_slips_gapless_sequence_update() RETURNS trigger AS $$
DECLARE
    cnt NUMERIC;
BEGIN
    IF (OLD.delivery_slip_id IS NOT NULL) AND (NEW.delivery_slip_id IS NULL OR NEW.delivery_slip_id <> OLD.delivery_slip_id) THEN
        RAISE EXCEPTION 'One cannot change the id of a slip';
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;""".format(DATABASE_SCHEMA))


    # Trigger's name are note schem-qualified because it is inherited
    # from the table

    current_session.connection().execute("""CREATE TRIGGER control_orders_accounting_delete
    AFTER DELETE ON {0}.orders FOR EACH ROW EXECUTE PROCEDURE {0}.check_orders_gapless_sequence_delete()""".format(DATABASE_SCHEMA))

    current_session.connection().execute("""CREATE TRIGGER control_orders_accounting_insert
    AFTER INSERT ON {0}.orders FOR EACH ROW EXECUTE PROCEDURE {0}.check_orders_gapless_sequence_insert()""".format(DATABASE_SCHEMA))

    current_session.connection().execute("""CREATE TRIGGER control_orders_accounting_update
    BEFORE UPDATE ON {0}.orders FOR EACH ROW EXECUTE PROCEDURE {0}.check_orders_gapless_sequence_update()""".format(DATABASE_SCHEMA))

    current_session.connection().execute("""CREATE TRIGGER control_delivery_slips_delete
    AFTER DELETE ON {0}.delivery_slip FOR EACH ROW EXECUTE PROCEDURE {0}.check_delivery_slips_gapless_sequence_delete()""".format(DATABASE_SCHEMA))

    current_session.connection().execute("""CREATE TRIGGER control_delivery_slips_insert
    AFTER INSERT ON {0}.delivery_slip FOR EACH ROW EXECUTE PROCEDURE {0}.check_delivery_slips_gapless_sequence_insert()""".format(DATABASE_SCHEMA))

    current_session.connection().execute("""CREATE TRIGGER control_delivery_slips_update
    BEFORE UPDATE ON {0}.delivery_slip FOR EACH ROW EXECUTE PROCEDURE {0}.check_delivery_slips_gapless_sequence_update()""".format(DATABASE_SCHEMA))




def pl_migration():

    # q = current_session.query(Task.task_id).filter(Task.task_type != 'task_for_presence')
    # current_session.query(TaskActionReports).filter(TaskActionReports.kind.in_(TaskActionReportType.start_task,TaskActionReportType.end_task)).delete(False)
    # current_session.query(TimeTrack).filter(TimeTrack.task_id.in_(q)).delete(False)
    # current_session.query(TaskOnOperation).delete()
    # current_session.query(Task).filter(Task.task_type != 'task_for_presence').delete()

    # Operation.__table__.drop(engine, checkfirst=True)
    print((current_session.query(Operation).delete()))
    current_session.commit()

    # ProductionFile.__table__.drop(engine, checkfirst=True)
    print((current_session.query(ProductionFile).delete()))
    current_session.commit()

    # DeliverySlipPart.__table__.drop(engine, checkfirst=True)
    print((current_session.query(DeliverySlipPart).delete()))
    current_session.commit()

    # OrderPart.__table__.drop(engine, checkfirst=True)
    print((current_session.query(OrderPart).delete()))
    current_session.commit()

    # Order.__table__.drop(engine, checkfirst=True)
    mainlog.debug("deleting orders")
    session().connection().execute("UPDATE gapless_seq SET gseq_value=(select max(accounting_label) from orders) WHERE gseq_name='order_id'")

    i = 0
    for order in current_session.query(Order).order_by(desc(Order.accounting_label)).all():
        current_session.delete(order)
        i += 1
        if i % 100 == 0:
            print(i)
            current_session.commit()

    # print current_session.query(Order).delete()
    current_session.commit()

    # DeliverySlip.__table__.drop(engine, checkfirst=True)
    print((current_session.query(DeliverySlip).delete()))
    for delivery_slip in current_session.query(DeliverySlip).order_by(desc(DeliverySlip.delivery_slip_id)).all():
        current_session.delete(delivery_slip)
    current_session.commit()

    # Customer.__table__.drop(engine, checkfirst=True)
    print((current_session.query(Customer).delete()))
    current_session.commit()

    # OperationDefinitionPeriod.__table__.drop(engine, checkfirst=True)
    print((current_session.query(OperationDefinitionPeriod).delete()))
    current_session.commit()

    # OperationDefinition.__table__.drop(engine, checkfirst=True)
    print((current_session.query(OperationDefinition).delete()))
    current_session.commit()


def drop_all_tables(current_session):

    mainlog.info("Dropping all the functions in the database")
    drop_functions(current_session)

    # WARNING Pay attention with follwowing code, it destroys the session !
    # But the session may be in use in other components (dao for example)

    # Close the connection to PG
    # This avoids DROP's to lock
    # http://www.sqlalchemy.org/trac/wiki/FAQ#MyprogramishangingwhenIsaytable.dropmetadata.drop_all

    # current_session.connection().close()
    # current_session.close()
    # current_session.bind.dispose()
    # current_session = session_factory()


    mainlog.info("Dropping all the tables in the database")
    #db_engine().execute( DropTable(ProductionFile))

    Comment.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    CommentLocation.__table__.drop(db_engine(), checkfirst=True)
    #comments_locations.drop(db_engine(), checkfirst=True)
    current_session.commit()



    # StockItem.__table__.drop(db_engine(), checkfirst=True)
    # current_session.commit()

    DayEvent.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()


    TemplateDocument.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    documents_order_parts_table.drop(db_engine(), checkfirst=True)
    current_session.commit()

    documents_orders_table.drop(db_engine(), checkfirst=True)
    current_session.commit()

    documents_quality_events_table.drop(db_engine(), checkfirst=True)
    current_session.commit()

    QualityEvent.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    Document.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    DocumentCategory.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    AuditTrail.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    FilterQuery.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    MonthTimeSynthesis.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    SpecialActivity.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    TaskActionReport.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    TimeTrack.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    TaskForPresence.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    TaskOnOperation.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    TaskOnOrder.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    TaskOnNonBillable.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    Task.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    Operation.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    ProductionFile.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    DeliverySlipPart.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    OrderPart.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    Order.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    DeliverySlip.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    OfferPart.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    Offer.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    Customer.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    OperationDefinitionPeriod.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    Machine.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    OperationDefinition.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    DayTimeSynthesis.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    MonthTimeSynthesis.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    Employee.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    SupplyOrderPart.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    SupplyOrder.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    Supplier.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    Resource.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    UserClass.__table__.drop(db_engine(), checkfirst=True)
    current_session.commit()

    gapless_seq_table.drop(db_engine(), checkfirst=True)

    #current_session.connection().execute("DROP TYPE IF EXISTS ck_task_action_report_type")
    current_session.commit()


def set_up_database(url_admin, login, password):
    # The administrative user must be "horse_adm"
    # He must have the right to create databases and roles

    login_adm, password_adm, dbname, host, port = _extract_db_params_from_url(url_admin)

    mainlog.info("Admin is {}, regular user is {}".format(login_adm, login))
    # Just to be sure we're outside any connection
    disconnect_db()

    parsed_url = urlparse(url_admin)
    t1_url = parsed_url.scheme + "://" + parsed_url.netloc + "/template1"
    mainlog.info("Connecting to template1")
    init_db_session(t1_url)

    horsedb_url = parsed_url.scheme + "://" + login + ":" + password + "@" + host + ":" + port + "/" + dbname

    mainlog.info("creating database")

    conn = db_engine().connect()
    conn.execute("commit")
    conn.execute("drop database if exists {}".format(dbname))

    if login_adm != login:
        conn.execute("drop role if exists {}".format(login))
        conn.execute("CREATE ROLE {} LOGIN PASSWORD '{}'".format(login,password))
        conn.execute("ALTER ROLE {} SET statement_timeout = 30000".format(login))

    conn.execute("commit") # Leave transaction
    conn.execute("CREATE DATABASE {}".format(dbname))
    conn.execute("ALTER DATABASE {} SET search_path TO {},public".format(dbname, DATABASE_SCHEMA))
    conn.close()

    disconnect_db()
    init_db_session(url_admin)
    session().commit() # Leave SQLA's transaction

    # Schema will be created for current database (i.e. horse or horse_test)
    mainlog.info("Creating schema {}".format(DATABASE_SCHEMA))
    session().connection().execute("create schema {}".format(DATABASE_SCHEMA))

    if login_adm != login:
        mainlog.info("Granting privileges to {}".format(login))
        session().connection().execute("grant usage on schema {} to {}".format(DATABASE_SCHEMA, login))


        # Alter the default privileges so that every tables and sequences
        # created right after will be usable by horse_clt
        # Also, if one adds tables, etc. afterwards, they'll benefit from
        # the privileges as well

        session().connection().execute("""ALTER DEFAULT PRIVILEGES
            FOR ROLE {}
            IN SCHEMA {}
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}""".format(login_adm, DATABASE_SCHEMA, login))

        session().connection().execute("""ALTER DEFAULT PRIVILEGES
            FOR ROLE {}
            IN SCHEMA {}
            GRANT SELECT, UPDATE ON SEQUENCES TO {}""".format(login_adm, DATABASE_SCHEMA, login))
    session().commit()

    disconnect_db()

    mainlog.info("Database setup complete")


def create_all_tables():
    mainlog.info("Creating all the tables and sequences")
    Base.metadata.create_all(db_engine(), checkfirst=True)
    session().commit()

    mainlog.info("Creating all the functions in the database")
    create_functions(session())
    session().commit()



def do_basic_inserts(do_sequence = True):
    mainlog.info("Initialising content in the database")

    t = TaskForPresence()
    t.kind = TaskForPresenceType.regular_time
    session().add(t)

    t = TaskForPresence()
    t.kind = TaskForPresenceType.unemployment_time
    session().add(t)

    if do_sequence:
        session().connection().execute("INSERT INTO {}.gapless_seq VALUES('delivery_slip_id', '1')".format(DATABASE_SCHEMA))
        session().connection().execute("INSERT INTO {}.gapless_seq VALUES('order_id','1')".format(DATABASE_SCHEMA))
        session().connection().execute("INSERT INTO {}.gapless_seq VALUES('preorder_id','1')".format(DATABASE_SCHEMA))
        session().connection().execute("INSERT INTO {}.gapless_seq VALUES('supply_order_id','1')".format(DATABASE_SCHEMA))


    session().commit()


    c = DocumentCategory()
    c.full_name = "Qualité"
    c.short_name = "Qual."
    session().add(c)
    session().commit()

    c = DocumentCategory()
    c.full_name = "Sales"
    c.short_name = "Sale"
    session().add(c)
    session().commit()

    c = DocumentCategory()
    c.full_name = "Production"
    c.short_name = "Prod"
    session().add(c)
    session().commit()

    # This shall pick the root account because at this point
    # we expect there's only one account in the database.

    employee = session().query(Employee).first()
    assert employee

    fq = FilterQuery()
    fq.family = FilterQuery.ORDER_PARTS_OVERVIEW_FAMILY
    fq.query = "Status = ready_for_production"
    fq.owner_id = employee.employee_id
    fq.name = "In production"
    fq.shared = True
    session().add(fq)


    fq = FilterQuery()
    fq.family = FilterQuery.ORDER_PARTS_OVERVIEW_FAMILY
    fq.query = "Status = completed"
    fq.owner_id = employee.employee_id
    fq.name = "Completed"
    fq.shared = True
    session().add(fq)


    fq = FilterQuery()
    fq.family = FilterQuery.DELIVERY_SLIPS_FAMILY
    fq.query = "CreationDate IN CurrentMonth"
    fq.owner_id = employee.employee_id
    fq.name = "This month's slips"
    fq.shared = True
    session().add(fq)

    fq = FilterQuery()
    fq.family = FilterQuery.SUPPLIER_ORDER_SLIPS_FAMILY
    fq.query = "CreationDate IN CurrentMonth"
    fq.owner_id = employee.employee_id
    fq.name = "Delivered this month"
    fq.shared = True
    session().add(fq)
    session().commit()



def add_user(employee_id,login,password,fullname,roles):
    h = hashlib.md5()
    h.update(password)
    session().connection().execute("INSERT INTO employees (employee_id,login,fullname,roles,password) VALUES ('{}','{}','{}','{}','{}')".format(employee_id,login,fullname,roles,h.hexdigest()))

from urllib.parse import urlparse
def _extract_db_params_from_url(url):
    mainlog.debug("Analysing URL {}".format(url))
    parsed_url = urlparse(url)
    dbname = parsed_url.path[1:]
    login_pw_re = re.compile("^([^:]+):([^@]+)@([^:]+):?([0-9]+)?")
    login, password,host,port = login_pw_re.match(parsed_url.netloc).groups()
    return login, password, dbname, host, port


def create_root_account(login="admin", password="admin"):

    employee = session().query(Employee).filter(Employee.login == login).first()
    if not employee:
        employee = Employee()
        employee.login=login
        session().add(employee)

    # Don't forget that this may update the admin account instead of creating
    # it. So we have to make sure it is usable.

    employee.set_encrypted_password(password)
    employee.roles=RoleType.symbols() # Admin has all rights
    employee.fullname = 'Administrator'
    employee.is_active = True
    session().commit()

def create_blank_database(admin_url, client_url):

    # Do administrative level stuff

    login, password, dbname, host, port = _extract_db_params_from_url(client_url)
    set_up_database( admin_url, login, password)
    init_db_session(admin_url)
    create_all_tables()
    disconnect_db()

    # Do client level stuff

    init_db_session(client_url, metadata, False)
    mainlog.info("Creating administration user/employee")
    create_root_account()

    do_basic_inserts()
    session().commit()

    # Insert some basic files


    # template_id = documents_service.save_template( open( os.path.join(resource_dir, "order_confirmation_report.docx"), "rb"), "order_confirmation_report.docx")
    # documents_service.update_template_description( template_id, _("Order confirmation template"), "order_confirmation_report.docx", HORSE_TEMPLATE)

    def add_template( description, filename, reference):

        with open( os.path.join(resource_dir, "server", filename), "rb") as f:
            template_id = documents_service.save_template(
                f,
                filename)

            documents_service.update_template_description(
                template_id, description, filename, reference)

    add_template( HORSE_TITLE_PREORDER, HORSE_TEMPLATE_PREORDER, HORSE_REFERENCE_PREORDER)
    add_template( HORSE_TITLE_ORDER_CONFIRMATION, HORSE_TEMPLATE_ORDER_CONFIRMATION, HORSE_REFERENCE_ORDER_CONFIRMATION)

    # session().connection().execute("grant usage on schema {} to horse_clt".format(HORSE_SCHEMA))
    # session().connection().execute("grant select,insert,update,delete on all tables in schema {} to horse_clt".format(HORSE_SCHEMA))
    # session().connection().execute("grant select,update on all sequences in schema {} to horse_clt".format(HORSE_SCHEMA))






if __name__ == "__main__":
    import argparse
    import re

    parser = argparse.ArgumentParser(description="""This is the Koi administration command !
You'll need a working Postgres instance. You'll also need a admin
account on that instance. To create one, do (as postgres user) :

    createuser -d -l -P -r horse_adm""")
    parser.add_argument('--reset-database', action='store_const', const=True, help='Reset the database and returns. ')
    parser.add_argument('--db-admin-url', default='postgresql://horse_adm:horsihors@127.0.0.1:5432/horsedb', help='Database connection URL, default is : postgresql://horse_adm:horsihors@127.0.0.1:5432/horsedb')
    parser.add_argument('--db-url', default='postgresql://horse_clt:HorseAxxess@127.0.0.1:5432/horsedb', help='Database connection URL, default is : postgresql://horse_clt:HorseAxxess@127.0.0.1:5432/horsedb')
    parser.add_argument('--db-host', default='127.0.0.1', help='Replace host in connection URLs')

    args = parser.parse_args()

    db_url = args.db_url
    db_admin_url = args.db_admin_url

    if args.db_host:
        db_url = re.sub('@.*:','@{}:'.format(args.db_host), db_url)
        db_admin_url = re.sub('@.*:','@{}:'.format(args.db_host), db_admin_url)

    if args.reset_database:
        create_blank_database(db_admin_url, db_url)
    else:
        parser.print_help()
    exit()

    # init_db_session("postgresql://stefan:@127.0.0.1:5432/horsedb", metadata, False or configuration.echo_query)
    init_db_session("postgresql://stefan:@127.0.0.1:5432/test_db", metadata, False or configuration.echo_query)

    create_all_tables(session())
    # add_user(100,'admin','admin','Administrator','TimeTrackModify,ModifyParameters')

    employee = Employee()
    employee.login="admin"
    h = hashlib.md5()
    h.update("admin")
    employee.password=h.hexdigest()
    employee.roles=RoleType.symbols()
    employee.fullname = 'Administrator'

    session().add(employee)

    session().connection().execute("grant usage on schema {} to horse_clt".format(DATABASE_SCHEMA))
    session().connection().execute("grant select,insert,update,delete on all tables in schema {} to horse_clt".format(DATABASE_SCHEMA))
    session().connection().execute("grant select,update on all sequences in schema {} to horse_clt".format(DATABASE_SCHEMA))

    do_basic_inserts()
    session().commit()
