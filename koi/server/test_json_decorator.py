from koi.base_logging import init_logging
from koi.Configurator import init_i18n,load_configuration,configuration

init_logging()
init_i18n()
load_configuration()
from koi.db_mapping import metadata, TaskActionReportType
from koi.datalayer.database_session import init_db_session

init_db_session(configuration.database_url, metadata, False or configuration.echo_query)



from koi.tools.chrono import *
from koi.json_decorator import JsonCallWrapper

from PySide.QtGui import QApplication
app = QApplication(sys.argv)


from koi.clock_service import ClockService
t = JsonCallWrapper( ClockService(), JsonCallWrapper.IN_PROCESS_MODE)
# t = JsonCallWrapper( ClockService(), JsonCallWrapper.HTTP_MODE)
# t = ClockService()

from datetime import timedelta, date, datetime

start_date = date.today() + timedelta(-360)

# t.get_person_data(16, date.today())

chrono_start()
t.record_presence( 16, datetime.now(), "Location")
chrono_click("t.record_presence")

print(" ----- "*100)

from contextlib import contextmanager
import time

@contextmanager
def timeit_context(name):
    startTime = time.time()
    yield
    elapsedTime = time.time() - startTime
    print('[{}] finished in {} ms'.format(name, int(elapsedTime * 1000)))


# mainlog.setLevel(logging.WARNING)
t.record_pointage_on_operation(127975,16,datetime.now(),"location",TaskActionReportType.start_task)

exit()

# t.record_pointage(10084780,16,datetime.now(),"location",TaskActionReportType.start_task)

o,m,next_action = t.get_operation_information(16, 128137)
mainlog.debug(o)
mainlog.debug(m)
mainlog.debug(next_action)

exit()

with timeit_context("loop"):
    for i in range(10):
        t.get_person_data(16, date.today())

with timeit_context("loop"):
    for i in range(10):
        t.record_presence( 16, datetime.now(), "Location")

with timeit_context("loop"):
    for i in range(10):
        t.get_person_data(16, date.today())
        t.record_presence( 16, datetime.now(), "Location")

# try:
#     t.get_person_data(-1, date.today())
#     print("------------")
#     assert False
# except ServerException as ex:
#     mainlog.exception(ex)

# chrono_start()
# for i in range(120):
#     p = t.get_person_data(16, start_date)
#     print(len(p.picture_data)) # 16, 100
#     # print(t.get_person_data(16).activity) # 16, 100
#     # print(t.get_person_data(16).activity[0].day)
#     # print(t.get_person_activity(16)[0].day)
#     # print(t.get_person_activity(16))
#     chrono_click()

chrono_click()
