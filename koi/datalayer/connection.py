from sqlalchemy.exc import OperationalError

from koi.datalayer.sqla_mapping_base import DATABASE_SCHEMA
from koi.datalayer.database_session import session
from koi.Configurator import mainlog

def check_db_connection(db_url):
    # I need DB url because I didn't find a way to get that information
    # from the session(), connection()...

    # Rage hard, maxi vinyl

    import subprocess
    import re

    if not db_url:
        return False

    mainlog.info("check_db_connection: Trying to connect to the database")
    try:
        session().connection().execute("SELECT count(*) from {}.employees".format(DATABASE_SCHEMA))
        mainlog.info("check_db_connection: Executed query")
        session().commit()
        mainlog.info("check_db_connection: commited")

        return True
    except Exception as ex:
        mainlog.error("Can't query the database !!! Is it connected ?")

        ret = str(ex)

        # mainlog.exception(ex)

        if type(db_url) == list:
            db_url = db_url[0]

        server_host = re.search("(@.*:)",db_url).groups()[0].replace("@","").replace(":","")

        try:
            mainlog.info("I'll try a ping at {}".format(server_host))
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
