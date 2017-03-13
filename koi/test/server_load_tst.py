import xmlrpc.client
import rpctools
from datetime import datetime,timedelta
from db_mapping import TaskActionReport
from dao import dao


start_time = datetime.today()

server = xmlrpc.client.ServerProxy('http://localhost:8080',verbose=False,allow_none=True)

task = rpctools.hash_to_object(server.getTaskInformation(100011))
user = rpctools.hash_to_object(server.getEmployeeInformation(10))
# print server.recordPointage(100012,10,datetime.today())
# print server.recordPointage(100012,10,datetime.today(),TaskActionReport.STOP_ACTION)

reports = rpctools.hash_to_object(server.getTaskActionReports(100012))
own_reports = [report for report in reports if report.reporter_id == 10]
others_reports = [report for report in reports if report.reporter_id != 10]


def time_spent_on_task(reports):

    counters = dict()
    for r in reports:

        if r.reporter_id not in counters:
            counters[r.reporter_id] = (None,None,timedelta())

        start_time,end_time,total_time = counters[r.reporter_id]

        if r.kind == TaskActionReport.START_ACTION:

            # We count the time here because we want to count the
            # time between the first start and the last end
            if start_time and end_time:
                total_time = total_time + (end_time - start_time)
                end_time = None
            start_time = r.time

        elif r.kind == TaskActionReport.STOP_ACTION:
            if start_time:
                end_time = r.time

        counters[r.reporter_id] = (start_time,end_time,total_time)


    for reporter_id in list(counters.keys()):

        start_time,end_time,total_time = counters[reporter_id]
        if start_time and end_time:
            total_time = total_time + (end_time - start_time)
        counters[reporter_id] = (start_time,end_time,total_time)

    return counters



# print task.__dict__
# print user.__dict__
print("------")
print((time_spent_on_task(rpctools.hash_to_object(server.getTaskActionReports(100012)))))

print((rpctools.hash_to_object(server.getLastActionReport(100001,9))))
