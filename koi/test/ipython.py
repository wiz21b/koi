import hashlib
import os
import logging
import inspect
import sys

"""
createdb.exe horse_test
createuser.exe --no-superuser --no-createdb --no-createrole tester
"""

"""
Pay attention ! Tests are not a submodule of the project
"""

def dirup(path):
    return os.path.split(os.path.abspath(path))[0]

updir = dirup(dirup(__file__))
# sys.path.append(updir)
# sys.path.append(os.path.join(updir,'server'))
# sys.path.append(os.path.join(updir,'datalayer'))

from koi.Configurator import init_i18n,load_configuration,resource_dir

from koi.base_logging import init_logging
init_logging("test.log")

init_i18n()

# load_configuration(os.path.join( resource_dir,'test_config.cfg'))
load_configuration('config.cfg')
# load_configuration() # Default run on my PC

from koi.Configurator import mainlog,configuration

import koi.db_mapping
from koi.datalayer.database_session import init_db_session,session
init_db_session(configuration.database_url, koi.db_mapping.metadata, True or configuration.echo_query)

from koi.db_mapping import *
from koi.dao import *
