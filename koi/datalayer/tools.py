from datetime import datetime, timedelta
import calendar


def last_moment_of_month(month_date):
    """ Compute the last moment of the month. Any timestamp greater
    than tha is in the next month. The accuracy of the computation
    must be sufficient for comparing timestamps in database as well.
    """

    first_of_month = datetime(month_date.year,month_date.month,1)
    first_of_next_month = first_of_month + timedelta(calendar.monthrange(month_date.year,month_date.month)[1])

    # FIXME PostgreSQL has microsecond accuracy for its timestamp and so
    # does Python. So the way I compute the first moment of the
    # month below is OK as long as we stay on PostgreSQL !

    return first_of_next_month - timedelta(microseconds=1)


def first_moment_of_month(month_date):
    return datetime(month_date.year,month_date.month,1) #which will set the rest of the fields to zero


def day_span(date):

    # FIXME If the DB gives more than microseconds accuracy, then we have a problem

    begin = datetime(date.year,date.month,date.day,0,0,0)
    end = datetime(date.year,date.month,date.day,23,59,59,999999)
    return (begin,end)
