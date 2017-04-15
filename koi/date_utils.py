import calendar
from datetime import datetime,timedelta,date

def clone_date(d):
    if isinstance(d,datetime):
        return datetime( d.year,
                         d.month,
                         d.day,
                         d.hour,
                         d.minute,
                         d.second,
                         d.microsecond,
                         d.tzinfo)
    elif isinstance(d,date):
        return date( d.year,
                     d.month,
                     d.day)

def timestamp_to_date(ts):

    assert isinstance(ts, datetime), "Expecting a timestamp (datetime)"

    return date( ts.year,
                 ts.month,
                 ts.day)

def month_after(d, nmonth=1):
    assert nmonth >= 1
    month = d.month # one based
    year = d.year

    while nmonth > 0:
        if nmonth >= 12:
            year = year + 1
            nmonth -= 12
        elif (12-month) >= nmonth:
            month += nmonth
            nmonth = 0
        elif (12-month) < nmonth:
            month = nmonth - (12 - month)
            year += 1
            nmonth = 0

    day = min(d.day,calendar.monthrange(year,month)[1])

    if isinstance(d,date):
        return date(year,month,day)
    elif isinstance(d,DateTime):
        return datetime(year,month,day,d.hour,d.minute,d.second,d.microsecond,d.tzinfo)
    else:
        raise Exception("I work only on date and datetime")


def month_before(d, nmonth = 1):
    """ Shift a given date/datetime nmonth months in the past.
    If the new day is not in the new month, then it is pulled
    to the last day of the month.
    """

    assert nmonth >= 1
    month = d.month # one based
    year = d.year

    while nmonth > 0:
        if nmonth >= 12:
            year = year - 1
        elif month > nmonth:
            month = month - nmonth
        elif month <= nmonth:
            month = month - nmonth
            month += 12
            year -= 1

        nmonth -= 12

    day = min(d.day,calendar.monthrange(year,month)[1])

    if isinstance(d,date):
        return date(year,month,day)
    elif isinstance(d,DateTime):
        return datetime(year,month,day,d.hour,d.minute,d.second,d.microsecond,d.tzinfo)
    else:
        raise Exception("I work only on date and datetime")


def _last_moment_of_previous_month(month_date):
    """ Compute the last moment of the month before month_date. Any timestamp greater
    than that is in the passed month. The accuracy of the computation
    must be sufficient for comparing timestamps in database as well.
    """

    first_of_month = datetime(month_date.year,month_date.month,1)
    return first_of_month - timedelta(microseconds=1)


def _last_moment_of_month(month_date):
    """ Compute the last moment of the month. Any timestamp greater
    than tha is in the next month. The accuracy of the computation
    must be sufficient for comparing timestamps in database as well.
    """

    first_of_month = datetime(month_date.year,month_date.month,1)
    first_of_next_month = first_of_month + timedelta(calendar.monthrange(month_date.year,month_date.month)[1])

    # PostgreSQL has microsecond accuracy for its timestamp and so
    # does Python. So the way I compute the first moment of the
    # month below is compatible across them.

    return first_of_next_month - timedelta(microseconds=1)


def _first_moment_of_month(month_date):
    """ The very first moment of a month.
    """

    return datetime(month_date.year,month_date.month,1) # 0 hour, 0 minuts 0 seconds ...


def date_to_pg(d):
    """ Format a date so that it can be used in a Postrgres
    SQL expression.
    """

    return "{}-{:02}-{:02}".format(d.year, d.month, d.day)


def timestamp_to_pg(d):
    """ Format a timestamp so that it can be used in a Postrgres
    SQL expression.

    We don't take care of time zones !!!
    """

    return "{}-{:02}-{:02} {}:{}:{}".format(d.year, d.month, d.day, d.hour, d.minute, d.second)


def ts_to_date(ts):
    return date(ts.year,ts.month,ts.day)


def day_period(date_ref):
    begin = datetime(date_ref.year,date_ref.month,date_ref.day,0,0,0)
    end = datetime(date_ref.year,date_ref.month,date_ref.day,23,59,59,999999) # FIXME If the DB gives more than microseconds, then we have a problem
    return begin, end


def day_period_to_ts(begin, end):
    begin = datetime(begin.year,begin.month,begin.day,0,0,0)
    end = datetime(end.year,end.month,end.day,23,59,59,999999) # FIXME If the DB gives more than microseconds, then we have a problem
    return begin, end

def month_period_as_date( base_date):
    d_start = date(base_date.year,
                   base_date.month,
                   1)

    d_end = date(base_date.year,
                 base_date.month,
                 calendar.monthrange(base_date.year,base_date.month)[1])

    return d_start, d_end


def compute_overlap(A_start, A_end, B_start, B_end):
    latest_start = max(A_start, B_start)
    earliest_end = min(A_end, B_end)
    if latest_start <= earliest_end:
        return latest_start,earliest_end
    else:
        return None
