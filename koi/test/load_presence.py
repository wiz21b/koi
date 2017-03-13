from datetime import datetime,date,timedelta

# Make sure we work with an in memory database
import Configurator
# Configurator.configuration.in_test()


import logging
from Logging import init_logging
init_logging("test.log")

from Configurator import init_i18n,load_configuration
init_i18n()
load_configuration()
from Configurator import mainlog,configuration

from sqlalchemy.exc import IntegrityError,InternalError
from sqlalchemy.sql.expression import func,select,join,and_,desc

import db_mapping

from db_mapping import Employee,Task, OperationDefinition, TaskActionReport,TimeTrack,DeliverySlipPart,Order, Customer,OrderPart,Operation,ProductionFile,TaskOnOperation,TaskActionReportType, TaskOnNonBillable
from db_mapping import OrderStatusType

from dao import *
from server import ClockServer,ServerException


s = db_mapping.global_session()

d = date(2013,1,1)

for i in range(90):
    for employee in s.query(Employee).all():

        presence = Presence()
        presence.start = datetime(d.year,d.month,d.day,8,0,0)
        presence.duration = 3
        presence.employee_id = employee.employee_id
        s.add(presence)

    d += timedelta(+1)
    s.commit()
