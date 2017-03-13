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

from koi.people_admin.people_admin_mapping import *

parser = argparse.ArgumentParser(description='This is an Horse! migration script.')
parser.add_argument('--db-url', default=configuration.database_url, help='Database connection URL {}'.format(configuration.database_url))

from sqlalchemy import create_engine
from sqlalchemy.schema import CreateTable
def dump(sql, *multiparams, **params):
    print(sql.compile(dialect=engine.dialect))
engine = create_engine('postgresql://', strategy='mock', executor=dump)
# print(CreateTable(Operation.__table__).compile(engine))


def alter_structure():

    
    # session().connection().execute("DROP TABLE horse.day_event")
    # session().commit()
    
    DayEvent.__table__.drop(db_engine(), checkfirst=True)
    session().commit()

    print(" ---------------------------- table droppe")
    DayEventType.db_type().drop( bind=db_engine(), checkfirst=True)
    session().commit()

    # For some reason, SQLA doesn't drop the enum type :-(
    # Although the doc seems to state it does...
    
    # Will create the enum and sequence, in the right schema
    DayEvent.__table__.create()
    session().commit()

    session().connection().execute("GRANT ALL ON horse.day_event TO horse_clt")
    session().connection().execute("GRANT ALL ON SEQUENCE horse.day_event_id_generator TO horse_clt")

    session().commit()

def alter_data():
    pass


args = parser.parse_args()
init_db_session(args.db_url, metadata, True or configuration.echo_query)

alter_structure()
alter_data()
print("Done")
