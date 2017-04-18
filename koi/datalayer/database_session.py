try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

import re
from sqlalchemy import create_engine
from sqlalchemy import exc
from sqlalchemy.orm import sessionmaker,scoped_session
from sqlalchemy.pool import NullPool

from koi.datalayer.sqla_mapping_base import DATABASE_SCHEMA
from koi.base_logging import mainlog


_config = dict()


def disconnect_db():
    global _config

    if 'session' in _config:
        try:
            mainlog.debug("Closing connection")
            _config['session'].connection().close()
            mainlog.debug("Closing session")
            _config['session'].close()
            mainlog.debug("done closing session")
        except Exception as ex:
            mainlog.exception(ex)
        finally:
            _config.pop('session')

    if 'engine' in _config:
        mainlog.debug("Dropping engine")
        _config.pop('engine')


def extract_db_params_from_url(url):
    assert type(url) == str

    mainlog.debug("Analysing URL {}".format(url))
    parsed_url = urlparse(url)
    dbname = parsed_url.path[1:]
    login_pw_re = re.compile("^([^:]+):([^@]+)@([^:]+):?([0-9]+)?")
    login, password,host,port = login_pw_re.match(parsed_url.netloc).groups()
    return login, password, dbname, host, port


def template1_connection_parameters( db_url):
    db_url, params = parse_db_url(db_url)
    parsed_url = urlparse(db_url)
    t1_url = parsed_url.scheme + "://" + parsed_url.netloc + "/template1"

    return t1_url, params


def parse_db_url( db_url):
    mainlog.debug("Init DB session " + str(db_url))

    if not db_url:
        raise Exception("Sorry, but the URL you provided is empty")

    if ',' in db_url:
        db_url = ','.split(db_url)

    mainlog.debug("{} ({})".format(db_url, type(db_url)))

    params = dict()
    if type(db_url) == list:
        mainlog.debug("DB connection URL has parts : {}".format(db_url))
        if 'sslmode' in db_url:
            params['sslmode'] = 'require'
        db_url = db_url[0]
    else:
        mainlog.debug("Regular DB URL")

    return db_url, params

def init_db_session(db_url,metadata=None,echo_query=False,autocommit=False, params=dict()):
    global _config

    mainlog.debug("Init DB session " + str(db_url))

    if 'session' in _config:
        raise Exception("Sorry, but you're trying ot double initialize the db session")

    db_url, params_from_url = parse_db_url( db_url)
    params =  dict(list(params_from_url.items()) + list(params.items()))

    mainlog.debug("Creating engine to {} with params {}".format(db_url, params))
    engine = create_engine(db_url,
                           encoding='utf-8',
                           echo=echo_query,
                           poolclass=NullPool,
                           connect_args=params)

    _config['engine'] = engine


    if metadata:
        metadata.bind = engine

    # Scoped session gives us thread safety which is very important
    # in our web server (multi thread) context

    _config['session_factory'] = sessionmaker(bind=engine,autocommit=autocommit)
    _config['session'] = scoped_session(_config['session_factory'])


def reopen_session():
    mainlog.debug("Reopening session")
    _config['session'] = scoped_session(_config['session_factory'])


def session():
    global _config
    if 'session' in _config:
        return _config['session']() # Those () are really important :) See SQLA's scoped_session
    else:
        raise Exception("Seems like the SQLAlchemy session was not initialized")

def db_engine():
    global _config
    return _config['engine']


def check_active_postgres_connections():
    # I need DB url because I didn't find a way to get that information
    # from the session(), connection()...

    # Rage hard, maxi vinyl with spoken words (super rare)

    mainlog.info("check_active_postgres_connections : Trying to connect to the database")

    try:
        r = session().connection().execute("SELECT count(*) from pg_stat_activity").scalar()
        mainlog.debug("Trying to connect to the database - 2")
        session().commit()
        mainlog.debug("Trying to connect to the database - 3")
        return r
    except exc.OperationalError as ex:
        mainlog.exception(ex)
        mainlog.error("Can't query the database !!! Is it connected ?")

    return False

def check_postgres_connection(db_url):
    """ Make sure we can connect to the server.
    We use the template1 schema for that, because it exists
    on any postgresql server.
    """

    # I need DB url because I didn't find a way to get that information
    # from the session(), connection()...

    db_url, params_from_url = parse_db_url( db_url)
    parsed_url = urlparse(db_url)
    t1_url = parsed_url.scheme + "://" + parsed_url.netloc + "/template1"

    # Rage hard, maxi vinyl with spoken words (super rare)

    mainlog.info("Trying to connect to PostgreSQL server...")

    engine = create_engine(t1_url)
    c = None
    try:
        c = engine.connect()
        c.execute("SELECT count(*) from pg_stats")
        return True
    except exc.OperationalError as ex:
        mainlog.exception(ex)
        mainlog.error("Can't query the database !!! Is it connected ?")
    finally:
        # This one is rather tricky. Somehow, I have
        # the impression that the select above opens
        # a connection and don't close it.
        # Because of that, in some cases, PostgreSQL
        # is cannot proceed with some operations.
        # For example, if one stays connected to template1
        # he cannot do a "drop table". So it is very important
        # that the connection, transaction, whatever is
        # actually closed when leaving this function.

        mainlog.debug("Closing conenction")
        if c: c.close()

        # I think this helps to better close the connection
        # although SQLA's documentation is a bit unclear.
        engine.dispose()
        del engine

    return False



def check_database_connection():
    # I need DB url because I didn't find a way to get that information
    # from the session(), connection()...

    # Rage hard, maxi vinyl with spoken words (super rare)

    mainlog.info("check_database_connection : Trying to connect to the database")
    try:
        session().connection().execute("SELECT count(*) from {}.employees".format(DATABASE_SCHEMA))
        session().commit()
        return True
    except Exception as ex:
        mainlog.exception(ex)
        return str(ex)


def check_db_connection(db_url):
    # I need DB url because I didn't find a way to get that information
    # from the session(), connection()...

    import subprocess
    import re

    mainlog.info("check_db_connection : Trying to connect to the database")
    try:
        session().connection().execute("SELECT count(*) from {}.employees".format(DATABASE_SCHEMA))
        session().commit()
        return True
    except Exception as ex:
        mainlog.error("Can't query the database !!! Is it connected ?")

        ret = str(ex)

        # mainlog.exception(ex)
        mainlog.info("I'll try a ping")
        server_host = re.search("(@.*:)",db_url).groups()[0].replace("@","").replace(":","")

        try:
            r = subprocess.Popen("\\Windows\\System32\\ping -n 1 " + server_host, stdout=PIPE, shell=False).stdout.read()
            mainlog.info("Ping to {} result is : {}".format(server_host, r))

            ret += "<br/><br/>"
            if "Reply" in r:
                mainlog.info("Ping was successful, the DB server machine seems up")
                ret += _(" A ping was successful (so host is up, database is down)")
            else:
                ret += _(" A ping was not successful (so host is down)")

            return ret
        except Exception as ex:
            #mainlog.error(str(ex,'ASCII','replace'))
            return _("Ping failed, the host is down.")
