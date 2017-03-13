import decimal
from collections import OrderedDict
from datetime import date, timedelta

from koi.Configurator import mainlog
from koi.configuration.business_functions import business_computations_service
from koi.datalayer.RollbackDecorator import RollbackDecorator
from koi.datalayer.database_session import session
from koi.date_utils import month_before,month_after,date_to_pg,timestamp_to_pg,_last_moment_of_month,_first_moment_of_month
from koi.db_mapping import OrderPart
from koi.utils import CacheResult
from koi.dao import dao

def month_diff(begin, end):
    """Return the number of months between d1 and d2,
    such that d2 + month_diff(d1, d2) == d1
    """
    diff = (12 * end.year + end.month) - (12 * begin.year + begin.month)
    return diff or 1


def _standard_period2(begin = None, end = None):
    # mainlog.debug("IN: From {} to {}".format(begin,end))

    if not end:
        end = date.today()

    if not begin:
        begin = month_before(end,2)


    begin = _first_moment_of_month(begin)
    end = _last_moment_of_month(end)
    duration_in_months = month_diff( begin, end)

    # mainlog.debug("From {} to {}, {} months".format(begin,end, duration))

    return begin,end, duration_in_months


def to_series(data):
    x_legends = []
    first_row = data[0]

    nb_series = len(first_row) - 1
    values = []
    for i in range(nb_series):
        values.append([])
    for row in data:
        x_legends.append(row[0])
        for i in range(nb_series):
            values[i].append(row[i+1])

    return x_legends, values


def to_serie(data):
    """ Convert a serie of (x, value) pair to two arrays :
    - an array with all the x
    - an array with all the values
    :param data:
    :return:
    """



    x_legends = []
    values = []

    for x, v in data:
        x_legends.append(x)

        if type(v) == decimal.Decimal: # FIXME Too slow !
            values.append(float(v))
        else:
            values.append(v)

    return x_legends, values


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

    for x,y,v in series:
        array[x_headers[x]][y_headers[y]] = v

    legends = [item[0] for item in sorted( x_headers.items(), key=lambda a:a[1])]

    x_legends = sorted(y_headers)

    # for h,ndx in x_headers.iteritems():
    #     array[1+ndx][0] = str(h)

    # for h,ndx in y_headers.iteritems():
    #     array[0][1+ndx] = str(h)



    return x_legends, legends ,array


# class Cache:
#     def __init__(self):
#         self._data = dict()
#         self._expiration = dict()
#
#     def put(self, key, data, lifetime_in_hours):
#         self._data[key] = data
#         self._expiration[key] = datetime.now() + timedelta(hours=lifetime_in_hours)
#
#     def is_expired(self, key):
#         if self._expiration[key] < datetime.now():
#             return True




class GraphData:
    def __init__(self, x_legends, series_legends, data):
        self.x_legends = x_legends
        self.series_legends = series_legends
        self.data = data

    @classmethod
    def to_jsonable(klass, obj):
        return obj.__dict__

    @classmethod
    def from_jsonable(klass, dikt):
        mainlog.debug("GraphData.from_jsonable {}".format(dikt))
        graph_data = GraphData(dikt['x_legends'], dikt['series_legends'], dikt['data'])
        return graph_data


class IndicatorsService:
    """ Indicators methods must have the name 'chart' in them for the cache mechanism
    to be fully operational !
    """

    def __init__(self):
        self._turnover_computation_cache = None

    #@JsonCallable([])
    def clear_caches(self):
        self._turnover_computation_cache = None

        for attr_name in dir(self):
            if "chart" in attr_name:
                a = getattr(self, attr_name)

                # We assume the function is decorated and has the clear_cache
                # method !

                try:
                    a.clear_cache()
                except Exception as ex:
                    mainlog.error("Error while refreshing {}".format(attr_name))
                    mainlog.exception(ex)

                # mainlog.debug("refresh_cached_indicators: refreshed : {}".format(a))



    #@JsonCallable([date, date])
    @CacheResult
    @RollbackDecorator
    def solde_carnet_commande_chart(self, begin= None, end = None):
        """It's the delta between
        the value of the work accomplished on
        and the expected sell price of
        the order part that are in production on a given day.
        So if an order part is completed, then it leaves the solde
        computation. Conversely, if a part is not yet in production,
        it is not in the computation.

        L'argent que je dois ("dois" car les commandes sont fermes et a faire,
        cad pretes pour la production)  encore realiser.
        C'est donc la difference entre le prix de vente de la partie de commande
        et l'argent deja depense sur cette commande
        On suppose ici qu'au final, l'argent depense sur une commande sera
        toujours inferieur au prix de vente.
        """

        begin,end,duration = _standard_period2(begin,end)
        duration = (end - begin).days

        r = session().connection().execute("""
with dates as  (
	select date '{}' + generate_series(0, {})   AS day
), active_parts as (
	-- We find the "active" order parts on a given day
	-- for those, we compute the beginning of their validity period and its end
	select p.order_part_id, p.quantity, o.creation_date,
               least(p.completed_date, dates.day ) as end_date, dates.day as rday
	from order_parts p
	join orders o on o.order_id = p.order_id
	cross join dates
	where o.creation_date <= dates.day
		and (    (p.completed_date >= dates.day and p.state not in ('aborted','preorder'))
              or (p.completed_date is null      and p.state not in ('aborted','preorder')))
), money_planned_per_part as (
        -- Money planned is the planned (during preorder phase) cost (what it will cost) or benefit
        -- (what it will bring to the company) of an order part.
	-- Money planned per order part. We can compute the planned money in
	-- two ways : cost or sell price.
	-- *** Planned money is COST :
	-- select opart.order_part_id, sum((op.value * 1.25 + op.planned_hours * opdef.hourly_cost) * 1.15 * opart.quantity ) as money_planned_per_part
	-- from order_parts opart
	-- join production_files pf on pf.order_part_id = opart.order_part_id
	-- join operations op on op.production_file_id = pf.production_file_id
	-- join operation_definitions opdef on opdef.operation_definition_id = op.operation_definition_id
	-- group by opart.order_part_id
	-- *** Planned money is SELL PRICE
	select opart.order_part_id, (opart.sell_price * opart.quantity ) as money_planned_per_part  --  SELL PRICE
	from order_parts opart
), money_planned_on_day as (
	select dates.day as day,
	           sum(money_planned_per_part.money_planned_per_part) as money_planned
	from dates
	join active_parts on active_parts.rday = dates.day
	join money_planned_per_part on money_planned_per_part.order_part_id = active_parts.order_part_id
	group by dates.day
),  timetracks_date as (
	select *, cast(start_time as date) start_date
	from timetracks
), money_consumed_up_to_day_for_parts_active_on_that_day as (
   	-- Let's show the timetracks (consumed hours on a given day for a given operation) :
     	--           Day 1  2  3  4  5
	-- ---------------------------
     	-- Part A
     	--     Op A.1    2  .  .  .  .
     	--     Op A.2    2  .  1  .  .
     	-- Part 2
     	--     Op B.1    3  .  2  .  .
     	--     Op B.2    0  .  1  .  5
	--               -------------
        --
	-- The join-clause on dates with tt.start_date <= dates.day
	-- lets us consider a growing group of column, starting
	-- left and growing one column at a time to the right
	-- The group by clause sums all the done hours in each of these
	-- groups :
     	--           Day 1  2  3  4  5
	-- ---------------------------
     	-- Part A
     	--     Op A.1    2  .  .  .  .
     	--     Op A.2    2  .  1  .  .
     	-- Part 2
     	--     Op B.1    3  .  2  .  .
     	--     Op B.2    0  .  1  .  5
	--               -------------
        --               7  7 11 11 16
	-- But doing so will produce an ever increasing number of hours
	-- so we also join on active_parts to only consider the parts
	-- actives on a given day.
	-- For example, if A is active up to day 3 and B only from day 3 :
     	--           Day 1  2  3  4  5
	-- ---------------------------
     	-- Part A
     	--     Op A.1    2  .  .  .  .
     	--     Op A.2    2  1  1  .  .
     	-- Part 2
     	--     Op B.1    .  .  .  4  .
     	--     Op B.2    .  .  1  1  5
	--               -------------
        --               4  5  7  6 10
	select dates.day as day,
	       sum( tt.duration*opdef.hourly_cost) as money_consumed
	from timetracks_date tt
	join dates on tt.start_date <= dates.day
	join tasks on tasks.task_id = tt.task_id
	join tasks_operations on tasks_operations.task_id = tasks.task_id
	join operations on tasks_operations.operation_id = operations.operation_id
	join operation_definitions opdef on opdef.operation_definition_id = operations.operation_definition_id
	join production_files pf on operations.production_file_id = pf.production_file_id
	-- FIXME Don't the timetracks automatically select that ?
	join active_parts opart on pf.order_part_id = opart.order_part_id and opart.rday = dates.day
	group by dates.day -- This is not naive at all
)
select dates.day,
    cast( coalesce( mpd.money_planned,0) as int),
    cast( coalesce( mcd.money_consumed,0) as int),
    cast( greatest( 0, coalesce( mpd.money_planned,0) - coalesce( mcd.money_consumed,0)) as int) as solde
from dates
left join money_planned_on_day mpd on mpd.day = dates.day
left join money_consumed_up_to_day_for_parts_active_on_that_day mcd on mpd.day = mcd.day
order by dates.day
        """.format(timestamp_to_pg(begin), duration)).fetchall()

        x_axis = []
        soldes = []
        consumed = []
        planned = []
        for d,money_planned,money_consumed,solde in r:
            x_axis.append(d)
            planned.append(money_planned)
            consumed.append(money_consumed)
            soldes.append( solde )

        # self.set_data( x_axis,[_("Remaining"),_("Consumed"),_("Sell price")],[soldes, consumed, planned])

        return GraphData( x_axis,[_("Remaining"),_("Consumed"),_("Sell price")],[soldes, consumed, planned])


    #@JsonCallable([date, date])
    @CacheResult
    @RollbackDecorator
    def oqd_chart(self, begin = None, end = None):
        begin,end,duration = _standard_period2(begin,end)

        r = session().connection().execute("""
with
completed_parts as (
	-- Figure when each part is completed
	select order_part_id, completion_date
	from
	 	(select
	 		case when (spq.q_out >= p.quantity) and (p.completed_date is not null) THEN greatest( p.completed_date, spq.first_slip_time)
	 			when (spq.q_out >= p.quantity) and (p.completed_date is null) THEN spq.first_slip_time
	 		     else p.completed_date -- can be null !
	 		end as completion_date,
	 	     p.order_part_id
		from
		   order_parts as p
		left join
		   (select order_part_id,
		           sum(quantity_out) as q_out,
		           min(creation) as first_slip_time,
		           max(creation) as last_slip_time
		    from delivery_slip_parts sp
		    join delivery_slip s on s.delivery_slip_id = sp.delivery_slip_id
		    where s.active
		    group by order_part_id) as spq
		on p.order_part_id = spq.order_part_id) cpl_date
	where cpl_date.completion_date is not null
),
month_start as (
	select date '{}' + generate_series(0, {}) * (interval '1' month) AS month_start_day
),
nc_per_month as (
	select
		date_trunc( 'MONTH', quality_events.when) as month_year,
	     count(*) nb_non_conformity
	from quality_events
	where kind = 'non_conform_customer'
	group by date_trunc( 'MONTH', quality_events.when)
),
completed_per_month as (
	select
		date_trunc( 'MONTH', completion_date) as month_year,
		count(*) as nb_completed_per_month
	from completed_parts
	group by date_trunc( 'MONTH', completion_date)
)
select
	date_trunc( 'MONTH', month_start.month_start_day) as month_year,
	CASE WHEN completed_per_month.nb_completed_per_month > 0
	     THEN 100.0 - 100.0 * coalesce( nc_per_month.nb_non_conformity, 0) / completed_per_month.nb_completed_per_month
	     ELSE 0
	END
from  month_start
left join nc_per_month on nc_per_month.month_year = month_start.month_start_day
left join completed_per_month on completed_per_month.month_year = month_start.month_start_day
order by date_trunc( 'MONTH', month_start.month_start_day)
""".format(timestamp_to_pg(begin), duration)).fetchall()
        x_legends, values = to_serie(r)

        return GraphData(x_legends, [''], [values]) # data are one serie of values => [values]





    #@JsonCallable([date, date])
    @CacheResult
    @RollbackDecorator
    def deadline_delivery_otd_chart(self, begin = None, end = None):
        begin,end,duration = _standard_period2(begin,end)

        r = session().connection().execute("""
with
completed_parts as (
	-- Figure when each part is completed
	select order_part_id, completion_date
	from
	 	(select
	 		case when (spq.q_out >= p.quantity) and (p.completed_date is not null) THEN greatest( p.completed_date, spq.first_slip_time)
	 			when (spq.q_out >= p.quantity) and (p.completed_date is null) THEN spq.first_slip_time
	 		     else p.completed_date -- can be null !
	 		end as completion_date,
	 	     p.order_part_id
		from
		   order_parts as p
		left join
		   (select order_part_id,
		           sum(quantity_out) as q_out,
		           min(creation) as first_slip_time,
		           max(creation) as last_slip_time
		    from delivery_slip_parts sp
		    join delivery_slip s on s.delivery_slip_id = sp.delivery_slip_id
		    where s.active
		    group by order_part_id) as spq
		on p.order_part_id = spq.order_part_id) cpl_date
	where cpl_date.completion_date is not null
),
month_start as (
	select date '{}' + generate_series(0, {}) * (interval '1' month) AS month_start_day
),
data as (
	select
		date_trunc( 'MONTH', completion_date) as completion_date,
		--sum(	late),
		--count(*),
		-- 'a' || sum( on_time) * 100.0 /1,
		-- count(*),
		sum( on_time) * 100.0 / count(*) as ratio
	from (
		select
			-- for each order part we dtermine if it is on time (1) or not (0)
			order_parts.order_part_id,
			completed_parts.completion_date as completion_date,
		    case when completed_parts.completion_date < order_parts.deadline then 1 else 0 end as on_time
		from order_parts as order_parts
		join completed_parts on order_parts.order_part_id = completed_parts.order_part_id
	) as data
	group by date_trunc( 'MONTH', completion_date)
	order by date_trunc( 'MONTH', completion_date))
select
	date_trunc( 'MONTH', month_start.month_start_day),
     ratio
from month_start
left join data on date_trunc( 'MONTH', month_start.month_start_day) = date_trunc( 'MONTH', data.completion_date)
order by month_start_day""".format(timestamp_to_pg(begin), duration)).fetchall()
        x_legends, values = to_serie(r)

        return GraphData(x_legends, [''], [values]) # data are one serie of values => [values]




    #@JsonCallable([date, date])
    @CacheResult
    @RollbackDecorator
    def done_versus_planned_hours_on_completed_parts_chart(self, begin = None, end = None):
        begin,end,duration = _standard_period2(begin,end)

        r = session().connection().execute("""
with
completed_parts as (
	-- Figure when each part is completed
	select order_part_id,
	       completion_date
	from
	 	(select
	 		case when (spq.q_out >= p.quantity) and (p.completed_date is not null) THEN greatest( p.completed_date, spq.first_slip_time)
	 			when (spq.q_out >= p.quantity) and (p.completed_date is null) THEN spq.first_slip_time
	 		     else p.completed_date -- can be null !
	 		end as completion_date,
	 	     p.order_part_id
		from
		   order_parts as p
		left join
		   (select order_part_id,
		           sum(quantity_out) as q_out,
		           min(creation) as first_slip_time,
		           max(creation) as last_slip_time
		    from delivery_slip_parts sp
		    join delivery_slip s on s.delivery_slip_id = sp.delivery_slip_id
		    where s.active
		    group by order_part_id) as spq
		on p.order_part_id = spq.order_part_id) cpl_date
	where cpl_date.completion_date is not null
),
hours_done_on_part as (
	select completed_parts.order_part_id,
	       sum(tt.duration) as hours
	from completed_parts -- make sure we compute the done hours only for the completed parts
	join production_files pf on pf.order_part_id = completed_parts.order_part_id
	join operations op on op.production_file_id = pf.production_file_id
	join tasks_operations taskop on taskop.operation_id = op.operation_id
	join timetracks tt on tt.task_id = taskop.task_id
	group by completed_parts.order_part_id
),
hours_planned_on_part as (
	select completed_parts.order_part_id,
	       sum(op.planned_hours*part.quantity) as hours
	from completed_parts -- make sure we compute the planned hours only for the completed parts
	join order_parts part on part.order_part_id = completed_parts.order_part_id
	join production_files pf on pf.order_part_id = completed_parts.order_part_id
	join operations op on op.production_file_id = pf.production_file_id
	group by completed_parts.order_part_id
),
month_start as (
	select date '{}' + generate_series(0, {}) * (interval '1' month) AS month_start_day
)
select
	date_trunc( 'MONTH', completion_date) as month_year,
	-- sum( done_hours) as done_hours,
	-- sum( plan_hours) as plan_hours,
	case when sum(plan_hours) > 0 then sum(done_hours) / sum(plan_hours)
	     else null -- no ratio is not 0 nor 1; it's no ration hence, null.
	end as ratio
from (
	select
	     month_start.month_start_day completion_date,
		h_done.order_part_id,
	     h_done.hours as done_hours,
	     h_plan.hours as plan_hours
	from month_start
	left join completed_parts on date_trunc( 'MONTH', month_start.month_start_day) = date_trunc( 'MONTH', completed_parts.completion_date)
	left join hours_done_on_part h_done on h_done.order_part_id = completed_parts.order_part_id
	left join hours_planned_on_part h_plan on h_plan.order_part_id = completed_parts.order_part_id
) as data
group by date_trunc( 'MONTH', completion_date)
order by date_trunc( 'MONTH', completion_date);
""".format(timestamp_to_pg(begin), duration)).fetchall()
        x_legends, values = to_serie(r)

        return GraphData(x_legends, [''], [values]) # data are one serie of values => [values]



    #@JsonCallable([date, date])
    @CacheResult
    @RollbackDecorator
    def direct_vs_indirect_chart(self, begin = None, end = None):
        begin,end,duration = _standard_period2(begin,end)

        r = session().connection().execute("""with
month_start as (
	select date '{}' + generate_series(0, {}) * (interval '1' month) AS month_start_day
),
durations as (
select
    date_trunc( 'MONTH', timetracks.start_time) as start_time,
    trunc(sum( coalesce( timetracks.duration,0))) as duration
from timetracks
join horse.tasks                       on tasks.task_id = timetracks.task_id
join horse.tasks_operation_definitions on horse.tasks_operation_definitions.task_id = tasks.task_id
join horse.operation_definitions opdef on opdef.operation_definition_id = horse.tasks_operation_definitions.operation_definition_id
group by date_trunc( 'MONTH', timetracks.start_time)
)
select
    month_start_day as month_year,
    trunc(sum( coalesce( duration,0))) as duration
from month_start
left join durations on durations.start_time = month_start_day
group by month_start_day""".format(timestamp_to_pg(begin), duration)).fetchall()

        indirects = [("Indirects",t[0],t[1])  for t in r]

        r = session().connection().execute("""with
month_start as (
	select date '{}' + generate_series(0, {}) * (interval '1' month) AS month_start_day
),
durations as (
    select
        date_trunc( 'MONTH', timetracks.start_time) as start_time,
        trunc(sum( coalesce( timetracks.duration,0))) as duration
    from timetracks
    join horse.tasks                       on horse.tasks.task_id = timetracks.task_id
    join horse.tasks_operations            on horse.tasks_operations.task_id = tasks.task_id
    join horse.operations                  on horse.operations.operation_id = horse.tasks_operations.operation_id
    join horse.operation_definitions opdef on opdef.operation_definition_id = horse.operations.operation_definition_id
    group by date_trunc( 'MONTH', timetracks.start_time)
)
select
    month_start_day as month_year,
    trunc(sum( coalesce( duration,0))) as duration
from month_start
left join durations on durations.start_time = month_start_day
group by month_start_day
""".format(timestamp_to_pg(begin), duration)).fetchall()

        directs = [("Directs",t[0],t[1])  for t in r]

        x_legends, legends ,array = to_arrays(directs + indirects)

        return GraphData(x_legends, legends ,array)



    #@JsonCallable([date, date])
    @CacheResult
    @RollbackDecorator
    def number_of_internal_non_conformity_chart(self, begin = None, end = None):
        begin,end,duration = _standard_period2(begin,end)

        r = session().connection().execute("""
with
completed_parts as (
	-- Figure when each part is completed
	select order_part_id, completion_date
	from
	 	(select
	 		case when (spq.q_out >= p.quantity) and (p.completed_date is not null) THEN greatest( p.completed_date, spq.first_slip_time)
	 			 when (spq.q_out >= p.quantity) and (p.completed_date is null) THEN spq.first_slip_time
	 		     else p.completed_date -- can be null !
	 		end as completion_date,
	 	    p.order_part_id
		from
		   order_parts as p
		left join
		   (select order_part_id,
		           sum(quantity_out) as q_out,
		           min(creation) as first_slip_time,
		           max(creation) as last_slip_time
		    from delivery_slip_parts sp
		    join delivery_slip s on s.delivery_slip_id = sp.delivery_slip_id
		    where s.active
		    group by order_part_id) as spq
		on p.order_part_id = spq.order_part_id) cpl_date
	where cpl_date.completion_date is not null
),
completed_per_month as (
	select
		date_trunc( 'MONTH',completion_date) as month_year,
		count(*) as cnt
	from completed_parts
	group by date_trunc( 'MONTH',completion_date)
),
nc_per_month as (
	select
		date_trunc( 'MONTH', quality_events.when) as month_year,
	    count(*) as cnt
	from quality_events
	where kind = 'non_conform_intern'
	group by date_trunc( 'MONTH', quality_events.when)
),
month_start as (
	select date '{}' + generate_series(0, {}) * (interval '1' month) AS month_start_day
)
select
	date_trunc( 'MONTH', month_start_day) as month_year,
	case when completed_per_month.cnt > 0
	     THEN 100.0 * coalesce(nc_per_month.cnt,0) / completed_per_month.cnt
	     -- then coalesce(nc_per_month.cnt,0)
	     else 0
	end as ratio
from month_start
left join nc_per_month on nc_per_month.month_year = month_start.month_start_day
left join completed_per_month on completed_per_month.month_year = month_start.month_start_day
order by date_trunc( 'MONTH', month_start_day);
""".format(timestamp_to_pg(begin), duration)).fetchall()
        x_legends, values = to_serie(r)

        return GraphData(x_legends, [''], [values]) # data are one serie of values => [values]




    #@JsonCallable([date, date])
    #@dto_maker.JsonCallable()
    @CacheResult
    @RollbackDecorator
    def number_of_customer_non_conformity_chart(self, begin : date = None, end : date = None) -> GraphData:
        begin,end,duration = _standard_period2(begin,end)

        r = session().connection().execute("""
with
month_start as (
	select date '{}' + generate_series(0, {}) * (interval '1' month) AS month_start_day
),
nc_per_month as (
	select
		date_trunc( 'MONTH', quality_events.when) as month_year,
	     count(*) nb_non_conformity
	from quality_events
	where kind = 'non_conform_customer'
	group by date_trunc( 'MONTH', quality_events.when)
)
select
	date_trunc( 'MONTH', month_start.month_start_day) as month_year,
	coalesce( nc_per_month.nb_non_conformity, 0)
from  month_start
left join nc_per_month on nc_per_month.month_year = month_start.month_start_day
order by date_trunc( 'MONTH', month_start.month_start_day)
""".format(timestamp_to_pg(begin), duration)).fetchall()
        x_legends, values = to_serie(r)

        return GraphData(x_legends, [''], [values]) # data are one serie of values => [values]



    #@JsonCallable([date, date])
    @CacheResult
    @RollbackDecorator
    def evolution_encours_chart(self, begin = None, end = None):
        global dao

        begin,end,duration = _standard_period2(begin,end)


        x_axis = []
        a_encours_this_month = []

        for i in range(duration):
            mainlog.debug(i)
            if i > 0:
                d = month_after(begin,i)
            else:
                d = begin

            x_axis.append( "{}/{}".format(d.month, d.year))
            a_encours_this_month.append( dao.order_dao.compute_encours_for_month(d))

        return GraphData(x_axis, [''], [a_encours_this_month]) # data are one serie of values => [values]


    #@JsonCallable([date, date])
    @CacheResult
    @RollbackDecorator
    def number_of_customer_who_ordered_chart(self, begin = None, end = None):
        begin,end,duration = _standard_period2(begin,end)

        r = session().connection().execute("""
with
month_start as (
	select date '{}' + generate_series(0, {}) * (interval '1' month) AS month_start_day
),
clients_per_month as (
	select
		month_year,
		count(*) as cnt
	from
		(select distinct
			date_trunc( 'MONTH', o.creation_date) as month_year,
			o.customer_id
		from
			orders o) as clients_per_month
	group by month_year
)
select
	date_trunc( 'MONTH', month_start.month_start_day) as month_year,
	coalesce( clients_per_month.cnt, 0)
from  month_start
left join clients_per_month on clients_per_month.month_year = month_start.month_start_day
order by date_trunc( 'MONTH', month_start.month_start_day)
""".format(timestamp_to_pg(begin), duration)).fetchall()
        x_legends, values = to_serie(r)

        return GraphData(x_legends, [''], [values]) # data are one serie of values => [values]


    #@JsonCallable([date, date])
    @CacheResult
    @RollbackDecorator
    def number_of_created_order_parts_chart(self, begin = None, end = None):
        begin,end,duration = _standard_period2(begin,end)

        r = session().connection().execute("""
with
month_start as (
	select date '{}' + generate_series(0, {}) * (interval '1' month) AS month_start_day
),
parts_created_per_month as (
	select
		date_trunc( 'MONTH', o.creation_date) as month_year,
		count(*) as cnt
	from orders o
	join order_parts op on op.order_id = o.order_id
	group by date_trunc( 'MONTH', o.creation_date)
)
select
	date_trunc( 'MONTH', month_start.month_start_day) as month_year,
	coalesce( parts_created_per_month.cnt, 0)
from  month_start
left join parts_created_per_month on parts_created_per_month.month_year = month_start.month_start_day
order by date_trunc( 'MONTH', month_start.month_start_day)
""".format(timestamp_to_pg(begin), duration)).fetchall()
        x_legends, values = to_serie(r)

        return GraphData(x_legends, [''], [values]) # data are one serie of values => [values]


    #@JsonCallable([date, date])
    @CacheResult
    @RollbackDecorator
    def order_parts_value_chart(self, begin = None, end = None):
        begin,end,duration = _standard_period2(begin,end)

        r = session().connection().execute("""
with
month_start as (
	select date '{}' + generate_series(0, {}) * (interval '1' month) AS month_start_day
),
parts_values as (
	select
		date_trunc( 'MONTH', o.creation_date) as month_year,
		sum(opart.sell_price * opart.quantity ) as value
	from order_parts opart
	join orders o on o.order_id = opart.order_id
	group by date_trunc( 'MONTH', o.creation_date)
)
select
	date_trunc( 'MONTH', month_start.month_start_day) as month_year,
	coalesce( parts_values.value, 0)
from  month_start
left join parts_values on parts_values.month_year = month_start.month_start_day
order by date_trunc( 'MONTH', month_start.month_start_day)
""".format(timestamp_to_pg(begin), duration)).fetchall()
        x_legends, values = to_serie(r)

        return GraphData(x_legends, [''], [values]) # data are one serie of values => [values]



    #@JsonCallable([date, date])
    @CacheResult
    @RollbackDecorator
    def preorder_parts_value_chart(self, begin = None, end = None):
        begin,end,duration = _standard_period2(begin,end)

        r = session().connection().execute("""
with
month_start as (
	select date '{}' + generate_series(0, {}) * (interval '1' month) AS month_start_day
),
preorder_sent as (
	select order_id, date_trunc( 'MONTH', was_preorder_on) as month_year
	from horse.orders
),
order_values as (
	select o.order_id,
 	       sum(opart.sell_price * opart.quantity ) as value
	from order_parts opart
	join orders o on o.order_id = opart.order_id
	group by o.order_id
)
select month_start_day as month_year, total_value
from (
	select
		month_start.month_start_day,
		coalesce( round(sum(value)), 0) as total_value
	from month_start
	left join preorder_sent on  preorder_sent.month_year = date_trunc( 'MONTH', month_start.month_start_day)
	left join order_values on order_values.order_id = preorder_sent.order_id
	group by month_start.month_start_day) as data
order by data.month_start_day
""".format(timestamp_to_pg(begin), duration)).fetchall()

        x_legends, values = to_serie(r)

        return GraphData(x_legends, [''], [values]) # data are one serie of values => [values]



    #@JsonCallable([date, date])
    #@dto_maker.JsonCallable()
    @CacheResult
    @RollbackDecorator
    def indirect_work_evolution_chart(self, begin = None, end = None):
        begin,end,duration = _standard_period2(begin,end)

        r = session().connection().execute("""
with
month_start as (
	select date '{}' + generate_series(0, {}) * (interval '1' month) AS month_start_day
),
short_ids as (
    select short_id, operation_definition_id
    from horse.operation_definitions
    where short_id is not null and not on_operation
),
durations as (
    select
        date_trunc( 'MONTH', timetracks.start_time) as start_time,
        short_id,
        trunc(sum( coalesce( timetracks.duration,0))) as duration
    from timetracks
    join horse.tasks                       on tasks.task_id = timetracks.task_id
    join horse.tasks_operation_definitions on horse.tasks_operation_definitions.task_id = tasks.task_id
    join horse.operation_definitions opdef on opdef.operation_definition_id = horse.tasks_operation_definitions.operation_definition_id
    group by date_trunc( 'MONTH', timetracks.start_time), short_id
)
select
    short_ids.short_id,
    month_start_day as month_year,
    trunc(sum( coalesce( duration,0))) as duration
from month_start
left join short_ids on 1=1 -- left join because we might have no short id at all...
left join durations on durations.start_time = month_start_day and durations.short_id = short_ids.short_id
group by short_ids.short_id, month_start_day
order by short_ids.short_id, month_start_day
""".format(timestamp_to_pg(begin), duration)).fetchall()

        x_legends, legends, array = to_arrays(r) # r = serie_id, x coord, value

        return GraphData(x_legends, legends ,array)


    @CacheResult
    @RollbackDecorator
    def estimated_versus_actual_time_per_month_chart(self, begin = None, end = None):

        begin,end,duration = _standard_period2(begin,end)

        r = session().connection().execute("""
with dates as  (
	select date '{}' + generate_series(0, {})  * (interval '1' month)  AS day
),
data as (
     select date_trunc('month',last_slip_time) as m,
        sum(part_planned_hours_per_unit * p.quantity) as planned,
        sum(part_data.work_done) as actual
	from order_parts as p
	join orders as o on o.order_id = p.order_id
	join
	   (select order_part_id,
                sum(quantity_out) as q_out,
                max(creation) as last_slip_time
	    from delivery_slip_parts sp
	    join delivery_slip s on s.delivery_slip_id = sp.delivery_slip_id
	    where s.active
	    group by order_part_id)
	as spq on spq.order_part_id = p.order_part_id
	join
	    (select order_part_id,
	                sum(op.planned_hours) as part_planned_hours_per_unit
		from production_files pf
	     join operations op on op.production_file_id = pf.production_file_id
	     group by pf.order_part_id)
	as pph on pph.order_part_id = p.order_part_id
	join
	(select order_part_id, sum(duration) as work_done
		from production_files pf
	     join operations op on op.production_file_id = pf.production_file_id
	     join tasks_operations on tasks_operations.operation_id = op.operation_id
	     join timetracks on timetracks.task_id = tasks_operations.task_id
	    group by pf.order_part_id)
	as part_data  on part_data.order_part_id = p.order_part_id
	where last_slip_time > date '{}'
	      and q_out = p.quantity
	group by m order by m)
select dates.day, data.planned, data.actual
from dates
left join data on date_trunc('month',data.m) = date_trunc('month',dates.day)
order by dates.day
""".format(date_to_pg(begin), duration, date_to_pg(begin))).fetchall()

        x_axis = []
        aplanned = []
        aactual = []
        for m,planned,actual in r:
            if m not in x_axis:
                x_axis.append(m)
            aplanned.append( planned )
            aactual.append( actual )

        return GraphData(x_axis, [_("Planned"),_("Actual")], [aplanned,aactual])




    @CacheResult
    @RollbackDecorator
    def direct_work_evolution_chart(self, begin = None, end = None):
        begin,end,duration = _standard_period2(begin,end)

        r = session().connection().execute("""with dates as  (
	select date '{}' + generate_series(0, {})  * (interval '1' month)  AS day
),
data as (
     select short_id,
         CAST( date_trunc('month',start_time) AS DATE) as m,
         trunc(sum(duration)) as duration
        from timetracks
        join tasks on tasks.task_id = timetracks.task_id
        left outer join tasks_operations on tasks_operations.task_id = tasks.task_id
        left outer join operations on tasks_operations.operation_id = operations.operation_id
        left outer join operation_definitions on operation_definitions.operation_definition_id = operations.operation_definition_id
        where short_id is not null and start_time between timestamp '{}' and timestamp '{}'
        group by short_id,m
)
select
    horse.operation_definitions.short_id,
    dates.day days,
    coalesce( data.duration, 0)
from dates
-- cross joins makes sure we have all the dates and all the operation id's. It's necessary
-- to build the series
cross join horse.operation_definitions
left join data on date_trunc('month',data.m) = date_trunc('month',dates.day)
              and data.short_id = horse.operation_definitions.short_id
order by days, short_id""".format(timestamp_to_pg(begin), duration, timestamp_to_pg(begin), timestamp_to_pg(end))).fetchall()


        x_legends, legends, array = to_arrays(r) # x,y value
        return GraphData(x_legends, legends ,array)


    @CacheResult
    @RollbackDecorator
    def to_facture_per_month_chart(self, begin = None, end = None):
        begin,end,duration = _standard_period2(begin,end)

        r = session().connection().execute("""
with dates as  (
	select date '{}' + generate_series(0, {}) * (interval '1' month) AS day
),
billable as (
	select
	   date_trunc('month',s.creation) as m,
	   sum(sp.quantity_out * p.sell_price)
	from order_parts as p
	join delivery_slip_parts as sp on sp.order_part_id = p.order_part_id
	join delivery_slip as s on s.delivery_slip_id = sp.delivery_slip_id
	join orders as ord on ord.order_id = p.order_id
	where s.active = true and s.creation between timestamp '{}' and timestamp '{}'
	group by m
),
actual_cost as (
	select
		date_trunc('month',s.creation) as m,
		sum(tt.duration * opdefper.hourly_cost)
	from order_parts as p
	join orders as o on o.order_id = p.order_id
	join production_files pf on pf.order_part_id = p.order_part_id
	join operations op on op.production_file_id = pf.production_file_id
	join tasks_operations taskop on taskop.operation_id = op.operation_id
	join timetracks tt on tt.task_id = taskop.task_id
	join operation_definitions opdef on opdef.operation_definition_id = op.operation_definition_id
	join operation_definition_periods opdefper on opdefper.operation_definition_id = opdef.operation_definition_id and o.creation_date between opdefper.start_date and coalesce(opdefper.end_date, TO_DATE('01/10/2100','DD/MM/YYYY'))
	join delivery_slip_parts as sp on sp.order_part_id = p.order_part_id
	join delivery_slip as s on s.delivery_slip_id = sp.delivery_slip_id
	where s.active and s.creation between timestamp '{}' and timestamp '{}'
	group by m
),
planned_cost as (
	select
	   date_trunc('month',s.creation) as m,
	   sum( pph.part_planned_cost_per_unit * p.quantity) as planned
	from order_parts as p
	join orders as o on o.order_id = p.order_id
	join delivery_slip_parts sp on sp.order_part_id = p.order_part_id
	join delivery_slip s on s.delivery_slip_id = sp.delivery_slip_id
	join
	    (select order_part_id,
	            sum(op.planned_hours*opdef.hourly_cost) as part_planned_cost_per_unit
		 from production_files pf
	     join operations op on op.production_file_id = pf.production_file_id
	     join operation_definitions opdef on op.operation_definition_id = opdef.operation_definition_id
	     group by pf.order_part_id) as pph on pph.order_part_id = p.order_part_id
	where s.active and s.creation between timestamp '{}' and timestamp '{}'
	group by m
)
select
	dates.day,
	cast( coalesce( billable.sum,0) as real),
   	cast( coalesce( actual_cost.sum,0) as real),
   	cast( coalesce( planned_cost.planned,0) as real)
from dates
left join billable on billable.m = dates.day
left join actual_cost on actual_cost.m = dates.day
left join planned_cost on planned_cost.m = dates.day
order by dates.day
        """.format(timestamp_to_pg(begin), duration,
                   timestamp_to_pg(begin), timestamp_to_pg(end),
                   timestamp_to_pg(begin), timestamp_to_pg(end),
                   timestamp_to_pg(begin), timestamp_to_pg(end))).fetchall()


        x_legends, data = to_series(r)

        return GraphData(x_legends, [_("To bill"),_("Actual cost"),_("Planned cost")], data)




    @CacheResult
    @RollbackDecorator
    def direct_work_cost_chart(self, begin = None, end = None):
        begin,end,duration_in_months = _standard_period2(begin,end)

        r = session().connection().execute("""
with dates as  (
	select date '{}' + generate_series(0, {}) * (interval '1' month) AS month
),
data as (
	select short_id,
	       CAST( date_trunc('month',start_time) AS DATE) as m,
	       sum(duration*opdef.hourly_cost) as duration
	from timetracks
	join tasks on tasks.task_id = timetracks.task_id
	join tasks_operations on tasks_operations.task_id = tasks.task_id
	join operations on tasks_operations.operation_id = operations.operation_id
	join operation_definitions opdef on opdef.operation_definition_id = operations.operation_definition_id
	where short_id is not null and start_time between timestamp '{}' and timestamp '{}'
	group by short_id,m
	order by short_id,m
)
select coalesce(short_id,''), month, coalesce( duration, 0)
from dates
left join data on data.m = dates.month
        """.format(timestamp_to_pg(begin), duration_in_months, timestamp_to_pg(begin), timestamp_to_pg(end))).fetchall()

        x_legends, legends ,array = to_arrays(r)
        return GraphData(x_legends, legends ,array)


    def _compute_turnover_info(self, begin_date : date):
        global dao
        if not self._turnover_computation_cache:
            self._turnover_computation_cache = dao.order_dao.compute_turnover_on( begin_date)
        return self._turnover_computation_cache

    @CacheResult
    def to_bill_this_month_indicator(self, begin=None, end=None):
        to_facture, encours_this_month, encours_previous_month, turnover = self._compute_turnover_info(begin)
        return to_facture


    @CacheResult
    def valuation_this_month_indicator(self, begin=None, end=None):
        to_facture, encours_this_month, encours_previous_month, turnover = self._compute_turnover_info(begin)
        mainlog.debug("valuation_this_month_indicator = {}".format(encours_this_month))
        return encours_this_month


    @CacheResult
    def valuation_last_month_indicator(self, begin=None, end=None):
        to_facture, encours_this_month, encours_previous_month, turnover = self._compute_turnover_info(begin)
        return encours_previous_month


    @CacheResult
    def turn_over_indicator(self, begin=None, end=None):
        to_facture, encours_this_month, encours_previous_month, turnover = self._compute_turnover_info(begin)
        return turnover



    @CacheResult
    def valution_production_chart(self, begin, end):
        begin,end,duration = _standard_period2( begin, end)

        duration_in_days = (end - begin).days
        mainlog.debug("From {} to {}, Duration in days = {}".format(begin,end,duration_in_days))

        r = session().connection().execute("""
with
events_q_out as (
	select
	   cast( date_trunc('day',s.creation) as date) as day,
	   sp.order_part_id,
	   sp.quantity_out
	from delivery_slip_parts sp
	join delivery_slip as s on s.delivery_slip_id = sp.delivery_slip_id
	where s.active = true
),
events_work as (
	select
	    cast( date_trunc('day',timetracks.start_time) as date) as day,
	    order_part_id,
	    timetracks.duration
	from production_files pf
	join operations op on op.production_file_id = pf.production_file_id
	join tasks_operations on tasks_operations.operation_id = op.operation_id
	join timetracks on timetracks.task_id = tasks_operations.task_id and timetracks.duration > 0
),
all_events as (
     -- we're interested in what happens for a given part on a given day.
     -- for that, we collapse all data on each days (so if we have 1 qty out
     -- and one done hour on the same day, then they both must appear on the
     -- same row). That's why we sum over grouped dates.
	select day, order_part_id, sum(quantity_out) as quantity_out, sum(duration) as done_hours
	from (
		select day, order_part_id, quantity_out, 0 as duration
		from events_q_out
		union all
		select day, order_part_id, 0, duration
		from events_work
	) merged_data
	-- filter out useless events. Do that early to remove as much computations
	-- as possible
	where day <= date '{}'
	group by order_part_id, day
),
last_event as (
	select
	    least(
            CASE
                WHEN part.completed_date IS NOT NULL
                THEN
                   -- completed order parts leave the valuation computation
                   greatest( data.max_date, part.completed_date)
                ELSE part.completed_date -- data.max_date
            END,
            date '{}') as day,
		part.order_part_id
	from horse.order_parts part
	-- parts without events won't have a completion date ?!
	join (select order_part_id,
	             max(day) as max_date
	      from all_events
	      group by order_part_id) data on data.order_part_id = part.order_part_id
	-- where state in ( 'completed', 'aborted')
),
merged_last_event as (
    select
        order_part_id,
        day,
        sum(all_data.quantity_out) quantity_out,
        sum(all_data.done_hours) done_hours
    from (
        select day, order_part_id, quantity_out, done_hours
        from all_events
        union all
        select day, order_part_id, 0, 0 -- this may introduce double dates
        from last_event
    ) as all_data
    group by order_part_id, day
)
select
    order_part_id,
    day,
    -- We use the fact this specific partition will accumulate values in its series.
    sum( merged_last_event.quantity_out) over (partition by order_part_id  order by merged_last_event.day) quantity_out,
    sum( merged_last_event.done_hours)   over (partition by order_part_id  order by merged_last_event.day) done_hours
from merged_last_event
order by order_part_id, day asc -- This ordering is crucial for the python part.


        """.format( timestamp_to_pg(end), timestamp_to_pg(end))).fetchall()

        valuations = OrderedDict()

        if len(r) == 0:
            i = date(begin.year, begin.month, begin.day)
            end = date(end.year, end.month, end.day)
            while i <= end:
                valuations[i] = 0
                i = i + timedelta(days=1)

        if len(r) > 0   :

            # Preinitialise the mapping so that we don't have to check
            # for the existence of a given date before adding items.
            #first_date = min([row.day for row in r])
            first_date = date(begin.year, begin.month, begin.day)


            i = first_date
            end = date(end.year, end.month, end.day)
            while i <= end:
                valuations[i] = 0
                i = i + timedelta(days=1)

            # i = date(end.year, end.month, end.day)
            # while i >= first_date:
            #     valuations[i] = 0
            #     i = i + timedelta(days=-1)

            # We'll need quick access to parts
            parts = dict()

            all_ids = list(set([row.order_part_id for row in r])) # list/set to compress the array

            # We use a step because the IN clause doesn't accept as many integer as we want.

            step = 100
            ndx = 0
            while ndx < len(all_ids):
                parts_ids = set( all_ids[ndx:ndx+step])
                for part in session().query(OrderPart).filter( OrderPart.order_part_id.in_(parts_ids)).all():
                    parts[ part.order_part_id] = part
                    # mainlog.debug("Part {} completed_date = {}".format(part.order_part_id, part.completed_date))
                ndx += step

            # Now we compute the sum of valuations on each day

            last_date = None
            last_valuation = 0
            last_order_part_id = None

            mainlog.debug("valution_production_chart")
            mainlog.debug( sorted(list(set([row.order_part_id for row in r]))))

            for row in r:

                # mainlog.debug("Row {}".format(row))

                if last_order_part_id != row.order_part_id:
                    last_order_part_id = row.order_part_id
                    last_date = None
                    last_valuation = 0


                if last_date:

                    # Copy the last valuation over several days because it's constant
                    # on that period.

                    i = last_date + timedelta(days=1) # skip last date, it's already accounted for.
                    while i < row.day: # Don't go till new date, it will be accounted for afterwards.
                        if i in valuations:
                            if i == date(2016, 3, 31):
                                mainlog.debug(
                                    "valuation on {} for {} is {}".format(i, last_order_part_id, last_valuation))
                            valuations[i] += last_valuation
                        i = i + timedelta(days=1)

                part = parts[row.order_part_id]
                last_valuation = business_computations_service.encours_on_params(
                    row.quantity_out, part.qty, row.done_hours, part.total_estimated_time, part.sell_price, part.material_value, row.order_part_id, row.day
                )

                # mainlog.debug("Valuation {}".format(last_valuation))

                if row.day in valuations:
                    if row.day == date(2016,3,31):
                        mainlog.debug("On basis of {}".format( (row.quantity_out, part.qty, row.done_hours, part.total_estimated_time, part.sell_price, part.material_value, row.order_part_id, row.day) ))
                        mainlog.debug("valuation on {} for {} is {}".format(row.day, row.order_part_id, last_valuation))
                    valuations[ row.day] += last_valuation

                last_date = row.day

            # for k in sorted(valuations.keys()):
            #     mainlog.debug("{} {}".format(k,valuations[k]))

        x_legends, values = to_serie( valuations.items() )
        return GraphData(x_legends, [''], [ values ])

indicators_service = IndicatorsService()
