import logging
from datetime import date

from koi.base_logging import mainlog, init_logging
from koi.Configurator import init_i18n, load_configuration, configuration

init_logging()
init_i18n()

from koi.db_mapping import metadata, Order

from koi.datalayer.database_session import init_db_session, session
from koi.charts.indicators_service import IndicatorsService
from koi.dao import dao

load_configuration()
init_db_session(configuration.database_url, metadata, False or configuration.echo_query)
dao.set_session(session())

from koi.db_mapping import *


def show_part(part_or_number):
    if type(part_or_number) == int:
        part = session().query(OrderPart).filter(OrderPart.order_part_id == part_or_number).one()
        session().commit()
    else:
        part = part_or_number


    mainlog.debug(u"{} {} {} (order {} created : {})".format(str(part), part.state.description, part.human_identifier, part.order_id, part.order.creation_date))

    for operation in part.operations:
        mainlog.debug(u"         op: {} [{}]".format(operation.description[0:20], operation.operation_definition_id))

        work = session().query(TimeTrack).join(TaskOnOperation).filter(
                        TaskOnOperation.operation == operation).all()

        if len(work):
            for tt in work:
                mainlog.debug(u"             tt:{}".format(tt))
        else:
            mainlog.debug(u"             tt:no work done")

    slips = session().query(DeliverySlipPart).join(DeliverySlip).filter(
                    DeliverySlipPart.order_part == part).all()

    if slips:
        for slip in slips:
            mainlog.debug(u"       slip: {} - {}".format(slip.delivery_slip.creation, slip))
    else:
        mainlog.debug(u"       slip: no slip")


def show_order(order):
    if type(order) == int:
        order = session().query(Order).filter(Order.order_id == order).one()
        session().commit()

    mainlog.debug(
        u"Order [{}]: {} accounting label:{} state:{} created:{}".format(order.order_id, order.description or "no description", order.accounting_label,
                                                              order.state, order.creation_date))
    for part in order.parts:
        show_part( part)


mainlog.setLevel(logging.DEBUG)

def compare_series(a,b):
    mainlog.debug("In a but not in b {}".format(sorted( set(a) - set(b))))
    mainlog.debug("In b but not in a {}".format(sorted( set(b) - set(a))))
    # mainlog.debug("In a AND in b {}".format(sorted(set(a) & set(b))))


def compute_old_encours(n):
    active_orders = dao.order_dao._active_orders_in_month_subquery(n)
    res = session().query(active_orders.c.active_order_id).all()

    parts = dao.order_dao.order_parts_for_monthly_report(n)
    parts_ids = sorted( [part.order_part_id for part in parts] )

    mainlog.debug("Active parts " + "- " * 30)
    mainlog.debug( parts_ids)

    mainlog.debug("Active orders " + "- "*30)
    res = [int(r[0]) for r in res]
    mainlog.debug(str(sorted(res)))

    encours = dao.order_dao.compute_encours_for_month(n)
    mainlog.debug("OLD encours " + str(encours) + "- " * 30)
    return parts_ids # active order parts




#show_part(223052)
#show_part(142293)# In old but not in new. production_paused. Has work and delivery slip

#  In old but not in new 115771 :
# Completed, last work date > completion_date and = 2016-01-12 => normal qu'il ne soit pas dan l'encours
# Pourquoi old l'a-t-il ? Pcq :
# select * from order_parts where order_id = 5255 and state <> 'completed'
# la 115771 appartient à un order qui a par ex. 115984 qui est prod. paused
# donc, l'order est marqué active et donc, toutes ses parties sont prises en
# compte dans le calcul de l'encours.
show_part(180233)
#exit()

# show_part(222333)

# exit()
n = date(2018, 3, 31) # end of a month
#old_parts = compute_old_encours(n)


v1 = dao.order_part_dao.wip_valuation_over_time( date(2017, 1, 1), date(2017, 3, 31))
#old_r = dao.order_part_dao._debug_active_order_parts
old_r = dao.order_part_dao.debug_part_dates

v2 = dao.order_part_dao.wip_valuation_over_time( date(2016, 12, 1), date(2017, 2, 28))
#compare_series(old_r, dao.order_part_dao._debug_active_order_parts)
compare_series(old_r, dao.order_part_dao.debug_part_dates)

print(v1[date(2017,2,28)])
print(v2[date(2017,2,28)])
print(v1[date(2017,1,31)])
print(v2[date(2017,1,31)])
exit()



for year in range(2013,2018):
    n = date(year, 3, 31) # end of a month
    tk = 20
    v = None
    old_r = r = None
    ref_date = n + timedelta(days=tk-1)
    for k in range(tk):

        try:
            old_r = dao.order_part_dao._debug_active_order_parts
        except:
            pass

        r = dao.order_part_dao.wip_valuation_over_time( n + timedelta(days=k), n + timedelta(days=k+tk))

        nv = r[ ref_date]
        mainlog.debug("k={} v={} d={}".format(k, nv, ref_date))
        if v is None:
            v = nv
        else:
            if v == nv:
                pass
            else:
                compare_series( old_r, dao.order_part_dao._debug_active_order_parts)
                #show_part(103365)
                show_part(25182)
                exit()

exit()

mainlog.debug("NEW " * 10)
r = dao.order_part_dao.wip_valuation_over_time( date(n.year, n.month, n.day) - timedelta(days=2), n)
mainlog.debug("NEW " * 10)

for p in dao.order_part_dao._debug_active_order_parts:
    if p not in old_parts:
        mainlog.debug("In new but not in old {}".format(p))

for p in old_parts:
    if p not in dao.order_part_dao._debug_active_order_parts:
        mainlog.debug("In old but not in new {}".format(p))

exit()


# python -m koi.test.test_valuations
