import unittest
from unittest import skip
import datetime
from datetime import date, timedelta
from koi.test.test_base import TestBase
from db_mapping import *
from dao import *
from Configurator import mainlog
from date_utils import date_to_pg

def query(date_start, date_end):
    duration = (date_end - date_start).days
    print(("duration {}".format(duration)))

    return session().connection().execute("""
with dates as  (
	select date '{}' + generate_series(0, {})   AS day
), active_parts as (
	-- We find the "active" order parts on a given day
	-- for those, we compute the beginning of their validity period and its end
	select p.order_part_id, p.quantity, o.creation_date, 
               least(p.completed_date, dates.day ) as end_date, dates.day as rday
	from horse.order_parts p
	join horse.orders o on o.order_id = p.order_id
	cross join dates
	where o.creation_date <= dates.day
		and ( (p.completed_date >= dates.day and p.state not in ('aborted','preorder'))
              	   or (p.completed_date is null      and p.state not in ('aborted','preorder') ))
), money_planned_per_part as (
	-- Money planned per order part. We can compute the planned money in
	-- two ways : cost or sell price.
	-- * Planned money is COST :
	-- select opart.order_part_id, sum((op.value * 1.25 + op.planned_hours * opdef.hourly_cost) * 1.15 * opart.quantity ) as money_planned_per_part  
	-- from horse.order_parts opart 
	-- join horse.production_files pf on pf.order_part_id = opart.order_part_id
	-- join horse.operations op on op.production_file_id = pf.production_file_id
	-- join horse.operation_definitions opdef on opdef.operation_definition_id = op.operation_definition_id
	-- group by opart.order_part_id
	-- * Planned money is SELL PRICE	
	select opart.order_part_id, (opart.sell_price * opart.quantity ) as money_planned_per_part  --  SELL PRICE
	from horse.order_parts opart 
), money_planned_on_day as (
	select dates.day as day,
	           sum(money_planned_per_part.money_planned_per_part) as money_planned
	from dates 
	join active_parts on active_parts.rday = dates.day
	join money_planned_per_part on money_planned_per_part.order_part_id = active_parts.order_part_id
	group by dates.day
),  timetracks_date as (
	select *, cast(start_time as date) start_date
	from horse.timetracks
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
	join horse.tasks on horse.tasks.task_id = tt.task_id
	join horse.tasks_operations on horse.tasks_operations.task_id = horse.tasks.task_id
	join horse.operations on horse.tasks_operations.operation_id = horse.operations.operation_id
	join horse.operation_definitions opdef on opdef.operation_definition_id = horse.operations.operation_definition_id
	join horse.production_files pf on horse.operations.production_file_id = pf.production_file_id
	-- FIXME Don't the timetracks automatically select that ?
	join active_parts opart on pf.order_part_id = opart.order_part_id and opart.rday = dates.day
	group by dates.day -- This is not naive at all
) 
select mpd.day,
	cast(mpd.money_planned as int), cast( mcd.money_consumed as int),
	cast( mpd.money_planned - mcd.money_consumed as int) as solde
from money_planned_on_day mpd, money_consumed_up_to_day_for_parts_active_on_that_day mcd
where mpd.day = mcd.day
order by mpd.day
        """.format(date_to_pg(date_start), duration)).fetchall()




    


class TestStatistics(TestBase):

    def setUp(self):
        self._clear_database_content()


    def test_orders_book_balance(self):

        d = date.today() + timedelta(-20)

        order = self._make_order()
        order.creation_date = d
        order.parts[0].qty = 16
        order.parts[0].sell_price = 23
        session().commit()

        self.add_work_on_operation(order.parts[0].operations[0], d)

        dao.order_dao.change_order_state(order.order_id, OrderStatusType.order_ready_for_production)

        # The order has no work on it before today
        r = query(d + timedelta(-300), d + timedelta(-1))
        self.assertEqual([], r)

        # Since the order was not completed, it is 'active'
        # forever
        r = query(d, d + timedelta(3))
        self.assertEqual(r[0], (d, 368, 0, 368) )
        self.assertEqual(r[-1], (d + timedelta(3), 368, 0, 368) )
        self.assertEqual(len(r), 3 + 1 )

        # So let's complete the order (and its parts)
        
        # FIXME we hack through the database
        dao.order_dao.change_order_state(order.order_id, OrderStatusType.order_completed)
        order.completed_date = d + timedelta(5)
        order.parts[0].completed_date = d + timedelta(5)
        session().commit()

        self.show_order(order)

        # The order is active from its creation date to its completion date
        r = query(d - timedelta(10), d + timedelta(10))
        self.assertEqual(len(r), 6 )

        # Now we add a new order, which overlaps the first

        d2 = d + timedelta(5)
        order = self._make_order()
        order.creation_date = d
        order.parts[0].qty = 12
        order.parts[0].sell_price = 12
        session().commit()

        dao.order_dao.change_order_state(order.order_id, OrderStatusType.order_completed)
        order.completed_date = d2 + timedelta(5)
        order.parts[0].completed_date = d2 + timedelta(5)
        session().commit()


if __name__ == '__main__':
    unittest.main()

