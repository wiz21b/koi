import re
from urllib.parse import urlparse
from koi.datalayer.SQLAEnum import EnumSymbol, DeclEnum

re_order_part_identifier = re.compile("^ *([0-9]+)([A-Z]+)? *$")

def split_horse_identifier(identifier):
    m = re_order_part_identifier.match(identifier)
    if not m:
        return None, None

    order_id = int(m.group(1))
    label = m.group(2)

    return order_id, label



def _extract_db_params_from_url(url):
    parsed_url = urlparse(url)
    dbname = parsed_url.path[1:]
    login_pw_re = re.compile("^([^:]+):([^@]+)@([^:]+):?([0-9]+)?")
    login, password,host,port = login_pw_re.match(parsed_url.netloc).groups()
    return login, password, dbname, host, port



def extend_enumeration(enumeration : DeclEnum, symbol : EnumSymbol):

    # The following statement really wants to run outside of a transaction.
    # SO I have to use the raw_connection stuff to escape SQLA's autoamted
    # transaction management.

    # See enumeration type information
    # select enumtypid, typname, enumlabel from pg_enum join pg_type on pg_type.oid = pg_enum.enumtypid order by enumtypid, enumlabel;

    from koi.base_logging import mainlog
    from koi.datalayer.database_session import db_engine

    c = db_engine().raw_connection()
    cursor = c.cursor()
    cursor.execute("COMMIT") # Leave any pending transaction
    try:
        sql = "ALTER TYPE {} ADD VALUE '{}'".format(enumeration.db_type().impl.name, symbol.value)
        mainlog.debug(" /// " + sql)
        cursor.execute(sql)
    except Exception as ex:
        mainlog.exception(ex)
    cursor.close()
    c.close()
