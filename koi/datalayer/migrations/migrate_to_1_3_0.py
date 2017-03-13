from datetime import date
import argparse
from sqlalchemy.sql import select,func,and_,or_

from koi.base_logging import mainlog,init_logging
from koi.Configurator import init_i18n,load_configuration,configuration,resource_dir
init_logging()
init_i18n()
load_configuration("server.cfg")

from koi.db_mapping import metadata, Operation
from koi.datalayer.database_session import init_db_session,db_engine,session
from koi.machine.machine_mapping import *

parser = argparse.ArgumentParser(description='This is an Horse! migration script.')
parser.add_argument('--db-url', default=configuration.database_url, help='Database connection URL {}'.format(configuration.database_url))

from sqlalchemy import create_engine
from sqlalchemy.schema import CreateTable
def dump(sql, *multiparams, **params):
    print(sql.compile(dialect=engine.dialect))
engine = create_engine('postgresql://', strategy='mock', executor=dump)
# print(CreateTable(Operation.__table__).compile(engine))


def alter_structure():

    try:
        session().connection().execute("ALTER TABLE horse.operations DROP CONSTRAINT fk_employee")
        session().connection().execute("ALTER TABLE horse.operations DROP COLUMN employee_id")
    except Exception as ex:
        session().rollback()

    session().connection().execute("ALTER TABLE horse.operations ADD employee_id INTEGER")
    session().connection().execute("ALTER TABLE horse.operations ADD CONSTRAINT fk_employee FOREIGN KEY(employee_id) REFERENCES horse.employees (employee_id)")

    # Commit necessary, else the next drop table hangs ad infinitum
    session().commit()

    try:
        session().connection().execute("ALTER TABLE horse.task_action_reports DROP COLUMN machine_id")
        session().commit()
    except Exception as ex:
        session().rollback()

    try:
        session().connection().execute("ALTER TABLE horse.timetracks DROP COLUMN machine_id")
        session().commit()
    except Exception as ex:
        session().rollback()

    try:
        session().connection().execute("ALTER TABLE horse.tasks_operations DROP COLUMN machine_id")
        session().commit()
    except Exception as ex:
        session().rollback()

    try:
        session().connection().execute("ALTER TABLE horse.tasks_operations DROP CONSTRAINT tasks_operations_operation_id_key")
        session().commit()
    except Exception as ex:
        session().rollback()
        
    Machine.__table__.drop(db_engine(), checkfirst=True)
    session().commit()

    try:
        session().connection().execute("DROP SEQUENCE horse.machine_id_generator")
    except Exception as ex:
        print(ex)
        print("###############################################")
        session().rollback()

    Resource.__table__.drop(db_engine(), checkfirst=True)
    session().commit()

    try:
        session().connection().execute("DROP SEQUENCE horse.resource_id_generator")
    except Exception as ex:
        print("---------------------------------------------------")
        print(ex)
        mainlog.exception(ex)
        session().rollback()

    session().commit()

    # resource_id_generator.create()
    Resource.__table__.create()




    session().connection().execute("GRANT ALL ON horse.resources TO horse_clt")
    session().connection().execute("GRANT ALL ON SEQUENCE horse.resource_id_generator TO horse_clt")

    session().commit()

    Machine.__table__.create()
    session().connection().execute("GRANT ALL ON horse.machines TO horse_clt")
    # session().connection().execute("GRANT ALL ON SEQUENCE horse.machine_id_generator TO horse_clt")
    session().commit()


    session().connection().execute("ALTER TABLE horse.task_action_reports ADD machine_id INTEGER")
    session().connection().execute("ALTER TABLE horse.task_action_reports ADD CONSTRAINT fk_machine FOREIGN KEY(machine_id) REFERENCES horse.machines (resource_id)")
    session().commit()



    session().connection().execute("ALTER TABLE horse.timetracks ADD machine_id INTEGER")
    session().connection().execute("ALTER TABLE horse.timetracks ADD CONSTRAINT fk_machine FOREIGN KEY(machine_id) REFERENCES horse.machines (resource_id)")
    session().commit()


    session().connection().execute("ALTER TABLE horse.tasks_operations ADD machine_id INTEGER")
    session().connection().execute("ALTER TABLE horse.tasks_operations ADD CONSTRAINT fk_machine FOREIGN KEY(machine_id) REFERENCES horse.machines (resource_id)")
    session().connection().execute("ALTER TABLE horse.tasks_operations ADD CONSTRAINT unique_task_on_machine_and_operation UNIQUE(operation_id,machine_id)")
    session().commit()




    # try:
    #     session().connection().execute("alter table horse.supply_orders add column active boolean not null constraint is_true default true")
    #     session().commit()
    # except Exception as ex:
    #     session().rollback()
    #     mainlog.exception(ex)

def alter_data():
    pass


args = parser.parse_args()
init_db_session(args.db_url, metadata, True or configuration.echo_query)

alter_structure()
alter_data()
print("Done")
