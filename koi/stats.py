import os.path
from datetime import date
import argparse
from sqlalchemy.sql import select,func,and_,or_

from koi.base_logging import mainlog,init_logging
from koi.Configurator import init_i18n,load_configuration,configuration,resource_dir
init_logging()
init_i18n()
load_configuration("server.cfg")

from koi.db_mapping import metadata
from koi.datalayer.database_session import init_db_session,db_engine,session


parser = argparse.ArgumentParser(description='This is an Horse! migration script.')
parser.add_argument('--db-url', default=configuration.database_url, help='Database connection URL {}'.format(configuration.get("Database","admin_url")))

from sqlalchemy import create_engine
from sqlalchemy.schema import CreateTable

# def dump(sql, *multiparams, **params):
#     print(sql.compile(dialect=engine.dialect))
# engine = create_engine('postgresql://', strategy='mock', executor=dump)
# print(CreateTable(Operation.__table__).compile(engine))

args = parser.parse_args()
init_db_session("postgresql://horse_adm:horsihors@127.0.0.1:5432/horsedb", metadata, True or configuration.echo_query)

people = dict()

interval = 2
steps = 8

for i in range(steps):
    session().connection().execute("SET search_path to horse,public")
    r = session().connection().execute("""
    with
    part_done_in_period as (
       select *
       from (
          select part.order_part_id, part.quantity, max(ds.creation) as done_date, sum(quantity_out) as all_out
          from order_parts part
          join delivery_slip_parts dsp on dsp.order_part_id = part.order_part_id
          join delivery_slip ds on ds.delivery_slip_id = dsp.delivery_slip_id
          group by part.order_part_id
       ) p
       where all_out = quantity
             and done_date between ((DATE '2014-01-01') + (INTERVAL '{0} MONTH'))
                               and ((DATE '2014-01-01') + (INTERVAL '{0} MONTH') + (INTERVAL  '{1} MONTH'))
    ),
    slow_op as (
       select operation_id, order_part_id, least( 2, duration/planned_hours) as speed
       from (
          select op.operation_id as operation_id,
                 order_parts.order_part_id as order_part_id,
                 op.planned_hours * order_parts.quantity as planned_hours,
                 sum(tt.duration) as duration
          from operations op
          join production_files on production_files.production_file_id = op.production_file_id
          join order_parts on order_parts.order_part_id = production_files.order_part_id
          join tasks_operations top  on top.operation_id = op.operation_id
          join timetracks tt on tt.task_id = top.task_id
          where op.planned_hours * order_parts.quantity > 0
          group by op.operation_id, order_parts.order_part_id, op.planned_hours, order_parts.quantity
          order by op.operation_id desc
          ) perf
       order by speed desc
    ),
    emp_op as (
       select distinct employees.fullname, top.operation_id
       from timetracks tt
       join employees on employees.employee_id = tt.employee_id
       join tasks_operations top on top.task_id = tt.task_id
    )
    select emp_op.fullname, sum(slow_op.speed)/count(*) as avg_speed
    from emp_op
    join slow_op on slow_op.operation_id = emp_op.operation_id
    join part_done_in_period on part_done_in_period.order_part_id = slow_op.order_part_id
    group by emp_op.fullname
    order by avg_speed desc;
    """.format(i*interval, interval))

    for line in r:
        name = line[0]
        x = line[1]

        if name not in people:
            people[name] = []
        people[name].append(x)


session().commit()


f = open("out.csv","w")
for k,v in people.items():
    if len(v) == steps:
        print(",".join( [k] + [str(x) for x in v]))
        f.write(",".join( [k] + [str(x) for x in v]) + "\n")
        # print("{} : {}".format(k, v))

f.close()
