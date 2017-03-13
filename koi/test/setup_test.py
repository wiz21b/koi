import hashlib
import os
import logging
import inspect
import sys

import koi.python3

"""
createdb.exe horse_test_db
createuser.exe --no-superuser --no-createdb --no-createrole horse_test
"""

"""
Pay attention ! Tests are not a submodule of the project
"""

# def dirup(path):
#     return os.path.split(os.path.abspath(path))[0]

# updir = dirup(dirup(__file__))
# sys.path.append(updir)
# sys.path.append(os.path.join(updir,'server'))
# sys.path.append(os.path.join(updir,'datalayer'))

from koi.Configurator import init_i18n,load_configuration,resource_dir

from koi.base_logging import init_logging,mainlog
init_logging("test.log",hook_exceptions=False)
mainlog.setLevel(logging.DEBUG)
init_i18n()

mainlog.debug(u"Test resource dir is {}".format(resource_dir))
load_configuration(os.path.abspath( os.path.join( resource_dir,'test_config.cfg')))
from koi.Configurator import configuration

import koi.db_mapping
from koi.datalayer.database_session import init_db_session,session
init_db_session(configuration.database_url, koi.db_mapping.metadata, False or configuration.echo_query)

from koi.datalayer.create_database import create_all_tables,do_basic_inserts,drop_all_tables,set_up_database,disconnect_db, create_root_account
from koi.datalayer.utils import _extract_db_params_from_url

def add_user(login,password,fullname,roles):
    h = hashlib.md5()
    h.update(password.encode('utf-8')) # and you need h.hexdigest()
    session().connection().execute("INSERT INTO employees (employee_id,login,password,fullname,roles,is_active) VALUES ( (select nextval('employee_id_generator')),'dd',md5('dd'),'Daniel Dumont','TimeTrackModify,ModifyParameters',true);")


def init_sequences(session):

    # Always insert the number RIGHT BEFORE the one you expect to use next time...
    session.connection().execute("SET search_path TO {}".format("horse"))
    session.connection().execute("BEGIN")
    session.connection().execute("DELETE FROM gapless_seq")
    session.connection().execute("INSERT INTO gapless_seq VALUES('delivery_slip_id', '799')")
    session.connection().execute("INSERT INTO gapless_seq VALUES('order_id','100')")
    session.connection().execute("INSERT INTO gapless_seq VALUES('preorder_id','4999')")
    session.connection().execute("INSERT INTO gapless_seq VALUES('supply_order_id','100')")
    session.connection().execute("COMMIT")

def init_test_database():

    # My idea is that the tests run under the same database constraints
    # as production. That is, the code can only change data, not database
    # structure.

    admin_url = configuration.get("Database","admin_url")
    client_url = configuration.get("Database","url")

    login, password, dbname, host, port = _extract_db_params_from_url(client_url)

    set_up_database(admin_url, login, password)
    init_db_session(admin_url)
    create_all_tables()
    disconnect_db()

    # Do client level stuff

    init_db_session(client_url, koi.db_mapping.metadata, echo_query=False)

    mainlog.debug("Initializing DB for tests")
    create_root_account()
    do_basic_inserts(do_sequence=False)
    init_sequences(session())

    add_user('dd','dd','Gandalf','TimeTrackModify,ModifyParameters')

if __name__ == "__main__":
    pass
    # init_test_database()
