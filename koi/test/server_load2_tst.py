from datetime import datetime
import xmlrpc.client

import sys
sys.path.append('..')

import random

import logging
from koi.base_logging import init_logging
# init_logging(r"servertest.log") # Turn off logging to improve performance a bit (around 5%)
from Configurator import init_i18n,mainlog,load_configuration
load_configuration("server.cfg","server_config_check.cfg")
init_i18n()

import db_mapping
from BarCodeBase import BarCodeIdentifier

import rpctools
from chrono import *

from server import ClockServer
from dao import DAO
dao = DAO(db_mapping.session())
server = ClockServer(dao)

mainlog.setLevel(logging.ERROR)



#print server.recordPointage(5000043, 16, datetime.now().strftime("%Y%m%dT%H:%M:%S"))
# print server.recordPointage(10084801, 15, datetime.now().strftime("%Y%m%dT%H:%M:%S"))
#exit()


print("""To profile :

python -m cProfile -o stats.prof server_test2.py

To analyse data

import pstats
p = pstats.Stats('stats.prof')
p.sort_stats('cumulative').print_stats(40)
""")

print("Deleting")
mainlog.info("Deleting")
db_mapping.session().query(db_mapping.TaskActionReport).delete()
db_mapping.session().query(db_mapping.TimeTrack).delete()
db_mapping.session().commit()
mainlog.info("Deleting.. done")

print("Collecting")
barcodes = []
for order in dao.order_dao.active_orders():
    for order_part in order.parts:
        for operation in order_part.operations:
            opdef = operation.operation_model
            if opdef and opdef.imputable and opdef.on_operation and order.imputable:
                bc = BarCodeIdentifier.code_for(operation)
                barcodes.append( bc)


employees = dao.employee_dao.all()

go = True
while go:
    go = False


    # server = xmlrpclib.ServerProxy('http://localhost:8080',verbose=False)

    try:
        total_calls = 0
        for ndx in range(10000):
            if ndx % 10 == 0:
                print(ndx)

            nb_loops = 20

            cases = []
            for i in range(nb_loops):
                userid = employees[random.randint(0,len(employees)-1)].employee_id
                bc = barcodes[random.randint(0,len(barcodes)-1)]
                d = random.randint(1,30)
                cases.append((userid,bc,d))

            top = datetime.now()
            total_loops = 0
            for j in range(4):
                for i in range(nb_loops):
                    userid,bc,d = cases[i]

                    h = random.randint(3*j,3*j+2)
                    m = random.randint(0,59)
                    t = "201303{:02}T{:02}:{:02}:33".format(d,h,m)
                    server.recordPointage(bc, userid, t, "Nostromo")

                    total_loops += 1
                    total_calls += 1

            delta = (datetime.now() - top)
            cs = delta.seconds + float(delta.microseconds)/1000000.0
            print(( "{} loops in  {} sec. => {} sec/loop".format(total_loops, cs, cs/float(total_loops))))
            print(("Total calls {}".format(total_calls)))

    except Exception as e:
        print(e)
