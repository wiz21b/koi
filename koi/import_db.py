import sys
import hashlib
from email.utils import parsedate

def pick_arg(n,default):
    if len(sys.argv) > n:
        return sys.argv[n]
    else:
        return default

SCHEMA="horse"
BASE_DIR=pick_arg(1,"/home/stefan/Projects")
BASE_DIR_PICS=pick_arg(2,"/home/stefan/Projects/Data/Pictures")
MODE=pick_arg(3,"migration")


import os
try:
    os.remove('test.sqlite')
except:
    pass

from datetime import date,datetime
import time


from koi.Configurator import mainlog,load_configuration,init_i18n,configuration
load_configuration()
configuration.database_url="postgresql://horse_adm:horsihors@localhost:5432/horsedb"
#configuration.database_url="postgresql://stc:@localhost:5432/horsedb"
init_i18n()

from koi.db_mapping import metadata
from koi.datalayer.database_session import init_db_session,session,db_engine,check_db_connection
init_db_session(configuration.database_url, metadata, False or configuration.echo_query)
from koi import db_mapping

from sqlalchemy.sql.expression import null,text
from koi.dao import dao


from koi.translators import text_search_normalize

from koi.datalayer.create_database import create_all_tables



def add_user(employee_id,login,password,fullname,roles):
    h = hashlib.md5()
    h.update(password)
    session().connection().execute("INSERT INTO {}.employees (employee_id,login,fullname,roles,password) VALUES ('{}','{}','{}','{}','{}')".format(SCHEMA,employee_id,login,fullname,roles,h.hexdigest()))



def argify(s):
    if s == None or len(s.strip()) == 0:
        return "NULL"
    else:
        if s.find("'") >= 0:
            return "E'" + s.replace("'",r"\'") + "'"
            return "'" + s + "'"
        else:
            return "'" + s + "'"

def identity(f):
    return f

def employee_picture(s):
    names = ['images1.PNG','images2.PNG','images3.PNG','images4.PNG','images5.PNG','images6.PNG','images7.PNG','images8.PNG','images9.PNG','images10.PNG','images11.PNG','images12.PNG','images13.PNG','images14.PNG','images15.PNG','images16.PNG','images17.PNG','images18.PNG','images19.PNG']

    names = ['man.png'] * 19
    name = names[s % len(names)]

    f = open( os.path.join(BASE_DIR_PICS, name),"rb")
    bytes = buffer(f.read(-1))
    f.close()

    # print "employee picutre has {}".format(len(bytes))
    # print type(bytes)
    return bytes

def uc(s):
    try:
        return str(s,encoding="utf-8").replace('@@@',"\n")
    except Exception as e:
        print(s)
        raise e

def duration(s):
    return float(s)

def timerfc2822(s):
    d = parsedate(s)
    return "{:04}-{:02}-{:02} {:02}:{:02}:{:02}".format(d[0],d[1],d[2],d[3],d[4],d[5])
    # return time.mktime(d)

def adate(s):
    if len(s) > 1:
        return datetime.strptime(s,'%Y-%m-%d')
    else:
        return None

def now(dummy):
    return datetime.now()

def start_year(dummy):
    return datetime(2012,1,1,0,0,0)

def blank(s):
    return None

def one(s):
    return 1

def btrue(s):
    return True

def opdef_imputable(s):
    return not s >= 26

def bbool(s):
    # print("{} -> {}".format(s,s=="true"))
    return s == "true"

def default_task_type(s):
    return "default" # FIXME shoudl be useless with polymoprhic identity

def normalize(s):
    try:
        return text_search_normalize(str(s))
    except Exception as ex:
        print(s)
        return s


def insertify(fields,filename,ftypes,debug=False):

    nfields = 1+fields.count(",")
    print("{} nfields={}".format(os.path.join(BASE_DIR,filename),nfields))

    params = []
    for i in range(nfields):
        params.append(":p{}".format(i))

    # params = ['?']*nfields

    base = "INSERT INTO {}.{} VALUES ".format(SCHEMA,fields) + "(" + (','.join(params)) + ")"
    base = text("INSERT INTO {}.{} VALUES ".format(SCHEMA,fields) + "(" + (','.join(params)) + ")")


    nline = 1
    for line in open(os.path.join(BASE_DIR,filename),'r'):

        org_args = line.split('\t')
        org_args[-1] = org_args[-1].strip()

        args = []
        for i in range(len(org_args)):
            if len(org_args[i]) == 0:
                args.append(None)
            else:
                if debug: print("applying {} at position {}".format(ftypes[i],i))
                args.append( ftypes[i](org_args[i]))

        # Complete with fields we don't import a value for
        for i in range(nfields-len(org_args)):
            args.append(ftypes[i+len(org_args)](nline))

        hargs = {}
        for  i in range(len(args)):
            hargs["p{}".format(i)] = args[i]

        if debug:
            print()
            print("---- line {}: {}".format(nline,line))
            print("{}\n{}".format(base,hargs))
            print("{} args : {}".format(len(org_args),org_args))
            print( map(lambda x:type(x), hargs.values()))

        # db_mapping.current_session.connection().execute(base,args)

        try:
            session().connection().execute(base,hargs)
        except Exception as ex:
            print(ex)
            print("Input line {}: {}".format(nline,line))
            print("Args hash : {} {}".format(base,hargs))
            print("Agrs types: {}".format( map(lambda x:type(x), hargs.values())))
            session().rollback()

        nline += 1

        if nline % 1000 == 0:
            # print("Commit {}".format(nline))
            session().commit()

    session().commit()
    print("done {} lines".format(nline))


# -----------------------------------------------------------------------------
print("Source dir is {}".format(BASE_DIR))
print("Destination dir is {}".format(BASE_DIR_PICS))
print("Mode is {}".format(MODE))

migration = MODE == 'migration'


if migration:
    db_mapping.pl_migration()
    # print db_mapping.session().connection().execute("UPDATE gapless_seq SET gseq_value=(select max(accounting_label) from orders) WHERE gseq_name='order_id'")
    # print db_mapping.session().connection().execute("UPDATE gapless_seq SET gseq_value=1 WHERE gseq_name='order_id'")
else:
    # drop_all_tables(session())
    create_all_tables(session())

print( session().query(db_mapping.gapless_seq_table).all())

if not migration:
    add_user(100,'stc','stc','Stefan Champailler','TimeTrackModify,ModifyParameters')
    add_user(101,'dd','dd','Daniel Dumont','TimeTrackModify,ModifyParameters')

    session().connection().execute(text("insert into horse.employees (fullname,login,password,employee_id) values ('Thierry Georis','gst','36e1a5072c78359066ed7715f5ff3da8','102');"))

    session().commit()
    insertify("employees (employee_id,fullname,picture_data)", "employees.txt",[int,uc,employee_picture])
    session().commit()


insertify("operation_definitions (operation_definition_id, short_id, description, hourly_cost, on_order, on_operation, imputable, start_date)",
          "operation_definitions.txt",
          [int,identity,identity,float,bbool,bbool,bbool,start_year],debug=False)


f = open(os.path.join(BASE_DIR,"operation_definitions.txt"))

# Quick fix for non imputable tasks
session().connection().execute(text("UPDATE {}.operation_definitions SET imputable = false WHERE short_id in ('MA','TR','EX')".format(SCHEMA)))


id = 1
for line in f:
    args = line.split('\t')
    base = text("INSERT INTO {}.operation_definition_periods (start_date, end_date, hourly_cost, operation_definition_id, operation_definition_period_id) VALUES (:p0, NULL,:p1,:p2,:p3)".format(SCHEMA))
    hargs = dict()
    hargs['p0'] = date(2000,1,1)
    hargs['p1'] = args[3]
    hargs['p2'] = args[0]
    hargs['p3'] = id
    session().connection().execute(base,hargs)
    id += 1
session().commit()
f.close()


#   csvout_customers = CSVOut.new([:customer_id,:name, :locality, :street , :phone1,  :phone2, :notes])

insertify("customers (customer_id,fullname,indexed_fullname,address2,address1,phone,phone2,notes)", "customers.txt",[int,uc,normalize,uc,uc,uc,uc,uc])

# exit()

insertify("orders (order_id, accounting_label, customer_id, customer_order_name, indexed_customer_order_name, state, creation_date, completed_date)",
          "orders.txt",
          [        int,      int,              int,         uc,                  normalize,                   str,   start_year,    adate],
          False)

insertify("order_parts (order_part_id,order_id,position,description,indexed_description, quantity, deadline,  qex,tex,dev,  eff,   sell_price)",\
              "order_parts.txt",\
              [         int,          int,     int,     uc,         normalize,           int,      adate,     int,int,float,float, float])


insertify("production_files (production_file_id, description, date, order_part_id, quantity, note)",
          "production_file.txt",
          [                  int,                uc,         adate, int,           int,      uc])


insertify("operations (operation_id,operation_definition_id,description,production_file_id,value,planned_hours, t_reel,position)",
          "operations.txt",
          [            int,         int,                    uc,         int,               float, duration,float, int])


insertify("tasks (task_id,active,task_type,version_id)",
          "tasks.txt",
          [int,btrue,str,one],False)

insertify("tasks_operations (task_id,operation_id)",
          "task_operation.txt",
          [int,int])


insertify("timetracks (timetrack_id,task_id,employee_id,duration,start_time,managed_by_code)",
          "timetracks.txt",
          [int,int,int,duration,timerfc2822,btrue],debug=False)


print(datetime.now())

# Always insert the number RIGHT BEFORE the one you expect to use next time...
if not migration:
    print (session().connection().execute("INSERT INTO {}.gapless_seq VALUES('delivery_slip_id', '799')".format(SCHEMA)))
    print (session().connection().execute("INSERT INTO {0}.gapless_seq select 'order_id',max(order_id) from {0}.orders".format(SCHEMA)))
    print (session().connection().execute("INSERT INTO {}.gapless_seq VALUES('preorder_id','4999')".format(SCHEMA)))



mainlog.debug("updating task activities")

q = """update {0}.tasks
        set active = (orders.state = 'order_ready_for_production' and {0}.operation_definitions.imputable)
        from {0}.tasks_operations
        join {0}.operations on {0}.tasks_operations.operation_id = {0}.operations.operation_id
        join {0}.production_files on {0}.production_files.production_file_id = {0}.operations.production_file_id
        join {0}.order_parts on {0}.order_parts.order_part_id = {0}.production_files.order_part_id
        join {0}.orders on {0}.orders.order_id = {0}.order_parts.order_id
        left outer join {0}.operation_definitions on {0}.operation_definitions.operation_definition_id = {0}.operations.operation_definition_id
        where {0}.tasks_operations.task_id = {0}.tasks.task_id
        and tasks.active != (orders.state = 'order_ready_for_production' and ({0}.operation_definitions.imputable is null or {0}.operation_definitions.imputable))""".format(SCHEMA)
session().connection().execute(q)

mainlog.debug("resetting sequences")

q = "select setval('{0}.id_generator',MAX(operation_id)+1) from {0}.operations".format(SCHEMA)
session().connection().execute(q)

q = "select setval('{0}.order_id_generator',MAX(order_id)+1) from {0}.orders".format(SCHEMA)
session().connection().execute(q)

q = "select setval('{0}.order_accounting_id_generator',MAX(order_id)+1) from {0}.orders".format(SCHEMA)
session().connection().execute(q)

q = "select setval('{0}.employee_id_generator',MAX(employee_id)+1) from {0}.employees".format(SCHEMA)
session().connection().execute(q)

q = "select setval('{0}.operation_definition_id_generator',MAX(operation_definition_id)+1) from {0}.operation_definitions".format(SCHEMA)
session().connection().execute(q)

session().commit()

mainlog.debug("Determine which order are completed")
i = 0
for order in session().query(db_mapping.Order).all():
    finished = True
    for part in order.parts:
        if part.tex2 < part.qty:
            finished = False
            break
    if finished:
        order.state = db_mapping.OrderStatusType.order_completed

    i+=1
    if i% 100 == 0:
        print(i)
        session().commit()

session().commit()


i=0
mainlog.debug("Compute labels")
for order in session().query(db_mapping.Order).all():
    dao.order_dao.recompute_position_labels(order)

    i+=1
    if i% 100 == 0:
        print(i)
        session().commit()

session().commit()
mainlog.debug("Done")


i=0
mainlog.debug("Fix labels")

for order in session().query(db_mapping.Order).all():

    for part in order.parts:

        last_op = None
        for operation in part.operations:
            
            desc = operation.description
            if desc and len(desc) > 1 and operation.operation_model is None:
                if last_op:
                    last_op.description = last_op.description + "\n" + desc
                    session().delete(operation)
            elif operation.operation_model:
                last_op = operation
                if not last_op.description:
                    last_op.description = ""

    i+=1
    if i% 100 == 0:
        print(i)
        session().commit()

session().commit()
mainlog.debug("Done")

