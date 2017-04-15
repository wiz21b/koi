# from PySide.QtOpenGL import QGLWidget

import math
from datetime import date, datetime

from koi.base_logging import mainlog
from koi.dao import dao
from koi.datalayer.database_session import session

from koi.date_utils import month_before,month_after,date_to_pg,timestamp_to_pg,_last_moment_of_month,_first_moment_of_month, month_period_as_date
from koi.charts.stacked_bars_chart import StackedBarsChart
from koi.charts.stacked_lines_chart import StackedLinesChart
from koi.charts.lines_chart import LinesChart
from koi.charts.bars_chart import BarsChart
from koi.charts.chart_widget import ChartWidget
from koi.gui.dialog_utils import KPIView
from koi.charts.indicators_service import indicators_service



def month_diff(begin, end):
    """Return the number of months between d1 and d2,
    such that d2 + month_diff(d1, d2) == d1
    """
    diff = (12 * end.year + end.month) - (12 * begin.year + begin.month)
    return diff or 1


def _standard_period(begin = None, end = None):
    mainlog.debug("IN: From {} to {}".format(begin,end))

    if not end:
        end = date.today()

    if not begin:
        begin = month_before(end,2)


    begin = _first_moment_of_month(begin)
    end = _last_moment_of_month(end)
    duration = month_diff( begin, end)

    mainlog.debug("From {} to {}".format(begin,end))

    return begin,end


def _standard_period2(begin = None, end = None):
    mainlog.debug("IN: From {} to {}".format(begin,end))

    if not end:
        end = date.today()

    if not begin:
        begin = month_before(end,2)


    begin = _first_moment_of_month(begin)
    end = _last_moment_of_month(end)
    duration = month_diff( begin, end)

    mainlog.debug("From {} to {}, {} months".format(begin,end, duration))

    return begin,end, duration



def to_arrays(series):
    """ Convert a serie of (x,y,value) tuple in three arrays :
    - an array with all the distinct values for x
    - an array with all the distinct values for y
    - a 2D array with all the values ordered around the x,y axis.
    """


    # Associate indices to axis values

    x_headers = dict()
    y_headers = dict()

    for x,y,v in series:
        if not x in x_headers:
            x_headers[x] = len(x_headers)

        if not y in y_headers:
            y_headers[y] = len(y_headers)

    # Make sure the indices of the y axis are sorted.
    i = 0
    for k in sorted(y_headers.keys()):
        y_headers[k] = i
        i += 1


    array = [[0 for i in range(len(y_headers))] for j in range(len(x_headers))]

    mini = 9999999999
    maxi = 0

    for x,y,v in series:
        array[x_headers[x]][y_headers[y]] = v

    legends = [item[0] for item in sorted( x_headers.items(), key=lambda a:a[1])]

    x_legends = sorted(y_headers)

    # for h,ndx in x_headers.iteritems():
    #     array[1+ndx][0] = str(h)

    # for h,ndx in y_headers.iteritems():
    #     array[0][1+ndx] = str(h)



    return x_legends, legends ,array



class DirectIndirectEvolutionChart(ChartWidget):
    def _gather_data(self, begin = None, end = None):
        begin,end = _standard_period(begin,end)

        r = session().connection().execute("""select CAST( date_trunc('month',start_time) AS DATE) as m, trunc(sum(duration)) as duration
        from timetracks
        join tasks on tasks.task_id = timetracks.task_id
        left outer join tasks_operation_definitions on tasks_operation_definitions.task_id = tasks.task_id
        left outer join operation_definitions on (operation_definitions.operation_definition_id = tasks_operation_definitions.operation_definition_id)
        where short_id is not null and start_time between timestamp '{}' and timestamp '{}'
        group by m
        order by m""".format(timestamp_to_pg(begin), timestamp_to_pg(end))).fetchall()

        indirects = [("Indirects",t[0],t[1])  for t in r]

        r = session().connection().execute("""select CAST( date_trunc('month',start_time) AS DATE) as m, trunc(sum(duration)) as duration from timetracks
        join tasks on tasks.task_id = timetracks.task_id
        left outer join tasks_operations on tasks_operations.task_id = tasks.task_id
        left outer join operations on tasks_operations.operation_id = operations.operation_id

        left outer join operation_definitions on operation_definitions.operation_definition_id = operations.operation_definition_id

        where short_id is not null and start_time between timestamp '{}' and timestamp '{}'
        group by m
        order by m;""".format(timestamp_to_pg(begin), timestamp_to_pg(end))).fetchall()

        directs = [("Directs",t[0],t[1])  for t in r]

        x_legends, legends ,array = to_arrays(directs + indirects)
        self.set_data( x_legends, legends ,array)


    def __init__(self,parent=None):
        s = StackedBarsChart(None)
        super(DirectIndirectEvolutionChart,self).__init__(parent, s, _("Proportion of direct and indirect hours, monthly"))



class DirectWorkEvolutionChart(ChartWidget):
    def _gather_data(self, begin = None, end = None):
        graph_data = self._remote_indicators_service.direct_work_evolution_chart(begin, end)
        self.set_data( graph_data.x_legends, graph_data.series_legends, graph_data.data)

    def __init__(self,parent,remote_indicators_service, mini, maxi):
        self._remote_indicators_service = remote_indicators_service
        s = StackedBarsChart(None)
        s.set_mini_maxi(mini, maxi)
        super(DirectWorkEvolutionChart,self).__init__(parent, s, _("Hours spent on operations per month"))



class IndirectWorkEvolutionChart(ChartWidget):
    def _gather_data(self, begin = None, end = None):
        graph_data = self._remote_indicators_service.indirect_work_evolution_chart(begin, end)
        self.set_data( graph_data.x_legends, graph_data.series_legends, graph_data.data)

    def __init__(self,parent,remote_indicators_service,mini=0,maxi=0):
        self._remote_indicators_service = remote_indicators_service
        s = StackedBarsChart(None)
        s.set_mini_maxi(mini, maxi)
        super(IndirectWorkEvolutionChart,self).__init__(parent, s, _("Hours on indirect operations"))



class DirectWorkCostEvolutionChart(ChartWidget):
    def _gather_data(self, begin = None, end = None):
        graph_data = self._remote_indicators_service.direct_work_cost_chart(begin, end)
        self.set_data( graph_data.x_legends, graph_data.series_legends, graph_data.data)

    def __init__(self,parent,remote_indicators_service,mini=0,maxi=0):
        self._remote_indicators_service = remote_indicators_service
        s = StackedBarsChart(None)
        s.set_mini_maxi(mini, maxi)
        super(DirectWorkCostEvolutionChart,self).__init__(parent, s, _("Cost of operations"))







class DirectIndirectEvolutionChart(ChartWidget):
    def _gather_data(self, begin = None, end = None):
        graph_data = self._remote_indicators_service.direct_vs_indirect_chart(begin, end)
        self.set_data( graph_data.x_legends, graph_data.series_legends, graph_data.data)
        # self.chart.set_horizontal_ruler(_("Target {}").format(25), 25)
        # self.chart.set_peak_values([str(int(x)) for x in self.chart.original_data[0]])

    def __init__(self,parent,remote_indicators_service):
        self._remote_indicators_service = remote_indicators_service

        #s = StackedLinesChart(None)
        s = StackedBarsChart(None)
        s.x_axis_as_months = True
        s.set_mini_maxi(0,5000)
        super(DirectIndirectEvolutionChart,self).__init__(parent, s, _("Proportion of direct and indirect hours, monthly"))



class NumberOfCustomerWhoOrdered(ChartWidget):
    def _gather_data(self, begin = None, end = None):
        graph_data = self._remote_indicators_service.number_of_customer_who_ordered_chart(begin, end)
        self.set_data( graph_data.x_legends, graph_data.series_legends, graph_data.data)
        self.chart.set_horizontal_ruler(_("Target {}").format(25), 25)
        self.chart.set_peak_values( make_peak_values( self.chart.original_data[0], "{}", 0, -1))

    def __init__(self,parent,remote_indicators_service):
        self._remote_indicators_service = remote_indicators_service

        #s = StackedLinesChart(None)
        s = BarsChart(None)
        s.x_axis_as_months = True
        s.set_mini_maxi(0,50)
        super(NumberOfCustomerWhoOrdered,self).__init__(parent, s, _("Number of customers who ordered"))


class NumberOfCreatedOrderParts(ChartWidget):
    def _gather_data(self, begin = None, end = None):
        graph_data = self._remote_indicators_service.number_of_created_order_parts_chart(begin, end)
        self.set_data( graph_data.x_legends, graph_data.series_legends, graph_data.data)
        self.chart.set_horizontal_ruler(_("Target {}").format(160), 160)
        self.chart.set_peak_values( make_peak_values( self.chart.original_data[0], "{}", 0, -1))

    def __init__(self,parent,remote_indicators_service):
        self._remote_indicators_service = remote_indicators_service

        #s = StackedLinesChart(None)
        s = BarsChart(None)
        s.x_axis_as_months = True
        s.set_mini_maxi(0,50)
        super(NumberOfCreatedOrderParts,self).__init__(parent, s, _("Number of created order parts"))




class OrderPartsValue(ChartWidget):
    def _gather_data(self, begin = None, end = None):
        graph_data = self._remote_indicators_service.order_parts_value_chart(begin, end)
        self.set_data( graph_data.x_legends, graph_data.series_legends, graph_data.data)
        self.chart.set_peak_values( make_peak_values( self.chart.original_data[0], "{:.0f}", 0, -1))

    def __init__(self,parent,remote_indicators_service):
        self._remote_indicators_service = remote_indicators_service

        #s = StackedLinesChart(None)
        s = BarsChart(None)
        s.set_mini_maxi(0,100000)
        s.x_axis_as_months = True
        super(OrderPartsValue,self).__init__(parent, s, _("Order parts value"))



class PreOrderPartsValue(ChartWidget):
    def _gather_data(self, begin = None, end = None):
        graph_data = self._remote_indicators_service.preorder_parts_value_chart(begin, end)
        self.set_data( graph_data.x_legends, graph_data.series_legends, graph_data.data)
        self.chart.set_peak_values( make_peak_values( self.chart.original_data[0], "{:.0f}", 0, -1))

    def __init__(self,parent,remote_indicators_service):
        self._remote_indicators_service = remote_indicators_service

        #s = StackedLinesChart(None)
        s = BarsChart(None)
        s.x_axis_as_months = True
        s.set_mini_maxi(0,100000)
        super(PreOrderPartsValue,self).__init__(parent, s, _("Preorder parts value"))



class EvolutionEncours(ChartWidget):
    def _gather_data(self, begin = None, end = None):
        graph_data = self._remote_indicators_service.evolution_encours_chart(begin, end)
        self.set_data( graph_data.x_legends, graph_data.series_legends, graph_data.data)
        self.chart.set_peak_values(["{}".format(int(x)) for x in self.chart.original_data[0]])

    def __init__(self,parent,remote_indicators_service):
        self._remote_indicators_service = remote_indicators_service
        s = BarsChart(None)
        super(EvolutionEncours,self).__init__(parent, s, _("Valuation over time"))



def make_peak_values(data, format, mini, maxi):
    """

    :param data:
    :param format:
    :param mini: Minimum value to ignore when drawing peak value (avoird showing
                 plenty of 0 on the basis of the chart)
    :param maxi: Maximum value to ignore
    :return:
    """

    pv = []
    for v in data:
        if v is None:
            pv.append('')
        elif v not in (mini, maxi):
            pv.append( format.format(v))
        else:
            pv.append('')
    return pv

class NonConformityCustomer(ChartWidget):
    def _gather_data(self, begin = None, end = None):
        graph_data = self._remote_indicators_service.number_of_customer_non_conformity_chart(begin, end)
        self.set_data( graph_data.x_legends, graph_data.series_legends, graph_data.data)
        self.chart.set_mini_maxi(0,5)

        self.chart.set_peak_values( make_peak_values( self.chart.original_data[0], "{}", 0, -1))
        self.chart.set_horizontal_ruler(_("Target {}").format(1), 1)

    def __init__(self,parent,remote_indicators_service):
        self._remote_indicators_service = remote_indicators_service
        s = BarsChart(None)
        s.set_mini_maxi(0,10)
        super(NonConformityCustomer,self).__init__(parent, s, _("Custsomer non-conformities"))



class NonConformityInternal(ChartWidget):
    def _gather_data(self, begin = None, end = None):
        graph_data = self._remote_indicators_service.number_of_internal_non_conformity_chart(begin, end)
        self.set_data( graph_data.x_legends, graph_data.series_legends, graph_data.data)
        self.chart.set_mini_maxi(0,100)
        self.chart.set_peak_values( make_peak_values( self.chart.original_data[0], "{:.0f}%", 0, 100))
        # self.chart.set_peak_values([str(int(x)) for x in self.chart.original_data[0]])
        self.chart.set_horizontal_ruler(_("Target {}%").format(5), 5)

    def __init__(self,parent,remote_indicators_service):
        self._remote_indicators_service = remote_indicators_service
        s = BarsChart(None)
        s.set_mini_maxi(0,10)
        super(NonConformityInternal,self).__init__(parent, s, _("Internal non conformities"))




class DoneVsPlannedHoursOnCompletedParts(ChartWidget):
    def _gather_data(self, begin = None, end = None):
        graph_data = self._remote_indicators_service.done_versus_planned_hours_on_completed_parts_chart(begin, end)
        self.set_data( graph_data.x_legends, graph_data.series_legends, graph_data.data)
        self.chart.set_peak_values( make_peak_values( self.chart.original_data[0], "{:.2}", 0.01,99999))
        #self.chart.set_peak_values(["{:.2}".format(x or 0) for x in self.chart.original_data[0]])
        self.chart.set_horizontal_ruler(_("Target {}").format(3), 3)

    def __init__(self,parent,remote_indicators_service,mini=0,maxi=0):
        self._remote_indicators_service = remote_indicators_service
        s = BarsChart(None)
        s.set_mini_maxi(0,2)
        super(DoneVsPlannedHoursOnCompletedParts,self).__init__(parent, s, _("Done / Planned Hours On Completed Parts"))



class DeadlinDeliveryChartOTD(ChartWidget):
    def _gather_data(self, begin = None, end = None):
        graph_data = self._remote_indicators_service.deadline_delivery_otd_chart(begin, end)
        self.set_data( graph_data.x_legends, graph_data.series_legends, graph_data.data)
        self.chart.set_mini_maxi(0,100)
        self.chart.set_peak_values( make_peak_values( self.chart.original_data[0], "{:.0f}%", 0, -1))
        self.chart.set_horizontal_ruler(_("Target {}%").format(70), 70)

    def __init__(self,parent,remote_indicators_service):
        self._remote_indicators_service = remote_indicators_service
        s = BarsChart(None)
        s.set_mini_maxi(0,100)
        super(DeadlinDeliveryChartOTD,self).__init__(parent, s, _("% completed parts on time (OTD)"))










class OQDChart(ChartWidget):
    def _gather_data(self, begin = None, end = None):
        graph_data = self._remote_indicators_service.oqd_chart(begin, end)
        self.set_data( graph_data.x_legends, graph_data.series_legends, graph_data.data)
        self.chart.set_mini_maxi(0,100)
        # self.chart.set_peak_values(["{}%".format(int(x)) for x in self.chart.original_data[0]])
        self.chart.set_peak_values( make_peak_values( self.chart.original_data[0], "{:.0f}%", 0, 100))

        self.chart.set_horizontal_ruler(_("Target {}%").format(95), 95)

    def __init__(self,parent,remote_indicators_service):
        self._remote_indicators_service = remote_indicators_service
        s = BarsChart(None)
        s.set_mini_maxi(0,100)
        super(OQDChart,self).__init__(parent, s, _("OQD"))







class DeadlinDeliveryChart(ChartWidget):
    def _gather_data(self, begin = None, end = None):

        begin,end = _standard_period(begin,end)

        r = session().connection().execute("""
select date_part( 'day', p.deadline - max(s.creation)) as delta
    from order_parts as p
    join delivery_slip_parts as sp on sp.order_part_id = p.order_part_id
    join delivery_slip as s on s.delivery_slip_id = sp.delivery_slip_id
    join orders as ord on ord.order_id = p.order_id
    where s.active and ord.creation_date > date '{}' and p.deadline is not null
    group by p.order_part_id, p.deadline, p.quantity
    order by delta;""".format(date_to_pg(begin), date_to_pg(end))).fetchall()


        # Negative values mean LATE

        r = map(lambda t: t[0],r)
        b = dict()

        for v in r:

            if v < -60:
                v = -60
            elif v > 60:
                v = 60

            bucket = round(v/2.0)
            if bucket not in b:
                b[bucket] = 0
            b[bucket] += 1

        sk = sorted(b.keys())
        self.set_data( [ int(k*2) for k in sk],[_("Delta")],[ [b[k] for k in sk] ])

        # avg = sum(r) / len(r)
        # std_dev = sum(map(lambda v: math.fabs(v-avg),r)) / len(r)
        # r = map(lambda v: math.copysign(min(3*std_dev, math.fabs(v)),v), r)
        # return [""]*len(r),["Delta"],[r]


    def __init__(self,parent=None):
        s = StackedBarsChart(None)
        super(DeadlinDeliveryChart,self).__init__(parent, s, _("Number of order parts with a given delivery delay (negative = late)"))




class ToFacturePerMonthChart(ChartWidget):
    def _gather_data(self, begin = None, end = None):
        graph_data = self._remote_indicators_service.to_facture_per_month_chart( begin, end)
        self.set_data( graph_data.x_legends, graph_data.series_legends, graph_data.data)

    def __init__(self,parent, remote_indicators_service):
        self._remote_indicators_service = remote_indicators_service
        s = LinesChart(None)
        super(ToFacturePerMonthChart,self).__init__(parent, s, _("Sell price vs cost for delivered units"))
        # s.x_axis_as_months = True





class EstimatedVersusActualTimePerMonthChart(ChartWidget):
    def _gather_data(self, begin = None, end = None):
        graph_data = self._remote_indicators_service.estimated_versus_actual_time_per_month_chart( begin, end)
        self.set_data(graph_data.x_legends, graph_data.series_legends, graph_data.data)

    def __init__(self, parent, remote_indicators_service):
        self._remote_indicators_service = remote_indicators_service
        s = StackedBarsChart(None)
        super(EstimatedVersusActualTimePerMonthChart,self).__init__(parent, s, _("Time spent on completed order parts"))



class SoldeCarnetCommande(ChartWidget):
    def _gather_data(self, begin = None, end = None):
        graph_data = self._remote_indicators_service.solde_carnet_commande_chart(begin, end)
        self.set_data( graph_data.x_legends, graph_data.series_legends, graph_data.data)

    def __init__(self,parent,remote_indicators_service):
        self._remote_indicators_service = remote_indicators_service
        s = LinesChart(None)
        super(SoldeCarnetCommande,self).__init__(parent, s, _("Order backlog valuation"))






class ToBillThisMonth(KPIView):
    def _gather_data(self, begin=None, end=None):
        self.set_amount( self._remote_indicators_service.to_bill_this_month_indicator(begin, end))

    def __init__(self, parent, remote_indicators_service):
        self._remote_indicators_service = remote_indicators_service
        super(ToBillThisMonth, self).__init__(_("To facture"), parent)
        self.setToolTip(_("""Compute the value of the delivered parts. The
value is the product of the quantities out by the sell price.
It is computed for deliveries which were completed in the given
month (so for which the last quantity was produced during
the month, regardless of the status of the order)"""))


class ValuationThisMonth(KPIView):
    def _gather_data(self, begin=None, end=None):
        self.set_amount( self._remote_indicators_service.valuation_this_month_indicator(begin, end))

    def __init__(self, parent, remote_indicators_service):
        self._remote_indicators_service = remote_indicators_service
        super(ValuationThisMonth, self).__init__( _("Valuation WIP this month"), parent)
        self.setToolTip(_("""The current month valuation is computed
for order parts which are started (that is, hours or actual production have been reported
for them) and not finished."""))


class ValuationLastMonth(KPIView):
    def _gather_data(self, begin=None, end=None):
        self.set_data( self._remote_indicators_service.valuation_last_month_indicator(begin, end))

    def __init__(self, parent, remote_indicators_service):
        self._remote_indicators_service = remote_indicators_service
        super(ValuationLastMonth, self).__init__( _("Valuation last month"), parent)
        self.setToolTip(_("""The current month valuation is computed
for order parts which were started and not finished on the last day of the previous
month."""))


class TurnOverThisMonth(KPIView):
    def _gather_data(self, begin=None, end=None):
        self.set_amount( self._remote_indicators_service.turn_over_indicator( begin, end))

    def __init__(self, parent, remote_indicators_service):
        self._remote_indicators_service = remote_indicators_service
        super(TurnOverThisMonth, self).__init__( _("Turnover"), parent)
        self.setToolTip(_("""Is to facture - valuation last month + valuation this month"""))




class RunningValuationChart(ChartWidget):

    #RUNNING_MONTHS = 3
    def _gather_data(self, begin = None, end = None):

        # begin, end =  month_before( begin, self.RUNNING_MONTHS), end

        graph_data = self._remote_indicators_service.valution_production_chart(begin, end)

        # mainlog.debug( "Data")
        # mainlog.debug( graph_data.x_legends)
        # mainlog.debug( graph_data.series_legends)
        # mainlog.debug( graph_data.data)

        self.set_data( graph_data.x_legends, graph_data.series_legends, graph_data.data)

    def __init__(self,parent,remote_indicators_service):
        self._remote_indicators_service = remote_indicators_service
        s = LinesChart(None)
        super( RunningValuationChart, self).__init__(parent, s, _("Work-in-progress valuation"))

