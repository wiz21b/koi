from math import ceil
from datetime import date

try:
    # This is a hack to avoid errors when gettext is not installed

    # Test if gettext is installed in the builtins

    _days = [_("Monday"),_("Tuesday"),_("Wednesday"),_("Thursday"),_("Friday"),_("Saturday"),_("Sunday")]
    _months = [_("January"),_("February"),_("March"),_("April"),_("May"),
               _("June"),_("July"),_("August"),_("September"),_("October"),
               _("November"),_("December")]
except Exception as ex:
    # Allow this module to work without gettext
    _ = lambda x:x
    _days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    _months = ["January","February","March","April","May",
               "June","July","August","September","October",
               "November","December"]

def zero(n):
    if n is None:
        return 0
    else:
        return n

def nunicode(t):
    if t is None:
        return u""
    else:
        return str(t)

def nice_round(n,no_dec_limit = 100):
    if -0.00001 < n < 0.00001:
        return ""
    elif n >= no_dec_limit:
        return str(int(n))
    elif n < 1:
        return "{:,.2f}".format(n).lstrip("0").rstrip("0").rstrip(".")
    else:
        return "{:,.1f}".format(n).lstrip("0").rstrip("0").rstrip(".")


EURO_SIGN = chr(8364)

def amount_to_s(amount,zero=None,money_sign=True):
    """ Transforms an amount in a string, with goal
    of giving a complete and pleasant information.
    That is, we don't round, we don't try to make the
    numbers as short as possible.

    :param amount: The amount
    :param zero: The string to display if the amount is null
    :param money_sign: True if the money sign is to be shown.
    :return:
    """

    global EURO_SIGN

    t = ""
    if not amount and zero != None:
        return zero
    else:
        # Display an amount in the french/belgian way
        t = u"{:,.2f}".format(amount).replace(u",",u" ").replace(u".",u",")

    if money_sign:
        return t + EURO_SIGN
    else:
        return t

def amount_to_short_s(amount):
    """ Display an amount in the french/belgian way
    in a compact form (without euro sign).
    """
    if not amount:
        return ""
    else:
        return u"{: .2f}".format(amount).replace(u".",u",")

def date_to_s(d,full=False):
    if not d:
        return ""

    if not full:
        return "{}/{}/{}".format(d.day,d.month,d.year)
    else:
        days = [_("Monday"),_("Tuesday"),_("Wednesday"),_("Thursday"),_("Friday"),_("Saturday"),_("Sunday")]
        return u"{} {}/{}/{}".format(days[d.weekday()], d.day,d.month,d.year)

def date_to_dmy(d,full_month=False):
    global _days, _months

    if d is None:
        return u""

    day = u"{}".format(d.weekday())

    month = u"/{}/".format(d.month)
    if full_month:
        month = u" {} ".format(_months[d.month-1])

    return u"{}{}{}".format(d.day, month,d.year)


def date_to_dm(d,year=True):
    if d:
        s = u"{}/{}".format(d.day,d.month)
        if year and d.year != date.today().year:
            s += u"/{:0>02}".format(d.year % 100)
        return s
    else:
        return ""



def date_to_my(d,full=False):

    if not full:
        return "{} {}".format(d.month, d.year)
    else:
        months = [_("January"),_("February"),_("March"),_("April"),_("May"),
                  _("June"),_("July"),_("August"),_("September"),_("October"),
                  _("November"),_("December")]

        return u"{} {}".format(months[d.month-1], d.year)



def timedelta_to_s(td):
    h = td.days * 24 + td.seconds / 3600
    m = (td.seconds % 3600) / 60

    s = []
    if h > 0:
        s.append( _("{}h").format(h))

    if m > 0:
        s.append( _("{:0>02}m").format(m) )

    return u" ".join(s)


def duration_to_s(d,unit=False):
    if d is None or d == 0:
        return u""

    unit_text = u""
    if unit:
        unit_text = _("h")

    sign = ""
    if d < 0:
        d = -d
        sign = "-"

    hours = float(d)

    # print "{:.30f} {:.30f}".format(hours,d)
    # print "{:.30f}".format(ceil(hours*100)/100.0)

    # Will work up to 8 - 2 digits = 6 signifcant numbers
    return u"{}{:.8g}{}".format(sign,round(hours*100)/100.0,unit_text)


    # d = int(d)

    # s = ""
    # if True:
    #     hours = float(d) / float(60*60)
    #     s = "{:.3g}h".format(hours)
    # else:
    #     seconds,millisecs = divmod(d,1000)
    #     minutes,seconds = divmod(seconds,60)
    #     hours,minutes = divmod(minutes,60)
    #     days,hours = divmod(hours,24)

    #     if days > 0:
    #         s = s + "{}j".format(days)
    #     if hours > 0:
    #         s = s + " {}h".format(hours)
    #     if minutes > 0:
    #         s = s + " {}m".format(minutes)
    #     if seconds > 0:
    #         s = s + " {}s".format(seconds) #  + float(millisecs)/1000)
    #     return s


def duration_to_hm(t,short_unit=False):
    """ converts a duration given in hours (2.5 = 2 hours and a half)
    to a nice string.
    """

    if t:
        h,m=int(t),int((t-int(t))*60 + 0.5)

        if m > 0:
            if not short_unit:
                return _("{}h{:0>02}m").format(h,m)
            else:
                return _("{}:{:0>02}").format(h,m)
        else:
            if not short_unit:
                return _("{}h").format(h)
            else:
                return str(h)

def time_to_hm(t):
    if t:
        return _("{}h{:0>02}").format(t.hour,t.minute)

def time_to_timestamp(ts,base_date=None):
    if ts:
        fd = base_date
        if fd and fd.year == ts.year and fd.month == ts.month and fd.day == ts.day:
            return "{}:{:0>2}".format(ts.hour, ts.minute)
        else:
            return "{}/{}/{} {}:{:0>2}".format(ts.day,ts.month,ts.year,ts.hour, ts.minute)
    else:
        return None


import unicodedata
def text_search_normalize(data):
    return ''.join(x for x in unicodedata.normalize('NFKD', str(data)) if unicodedata.category(x)[0] in 'LN').lower().strip()


def crlf_to_br(s):
    if s:
        return s.replace('\n','<br/>') # DO NOT ESCAPE .replace('<','&lt;')
    else:
        return ""

def remove_crlf(s):
    if s is None:
        return s
    else:
        return s.replace('\n',' ')

def shorten_str(s):
    if s:
        if ' ' in s:
            return s[0:s.index(' ')]
        else:
            return s[0:5]
    else:
        return ''


def format_number(n):
    if n - int(n):
        # There's a decimal part
        return "{:,.2f}".format(n).replace(u",",u" ").replace(u".",u",")
    else:
        # No decimal part
        return "{:,d}".format(int(n)).replace(u",",u" ")

import locale
decimal_point = locale.localeconv()['decimal_point']

def format_csv(n):
    if n is None:
        return ""
    elif n - int(n):
        # There's a decimal part
        return "{:.2f}".format(n).replace(u".",decimal_point)
    else:
        # No decimal part
        return "{:d}".format(int(n))



def quantity_to_str(q):
    if not q:
        return "-"
    else:
        return format_number(q)


def escape_xml(s):
    """ Prepares a string to be rendered in ReportLab report.
    This means :
    - escaping XML entities
    - transform None into "" (which makes things a little easier)
    """

    if s:
        return str(s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;'))
    else:
        return ""


def ellipsis(s : str, lmax : int = 10):
    if not s:
        return s
    elif len(s) > lmax:
        return s[:lmax] + "..."
    else:
        return s



def order_number_title(preorder_number, order_number, customer_number):
    t = []

    if order_number:
        t.append(u"<span style='color:red;'>{}</span>".format( _("Cde: {}").format(order_number)))

    if preorder_number:
        t.append(u"<span style='color:green;'>{}</span>".format(_("Dev.: {}").format(preorder_number)))

    if customer_number:
        t.append(u"<span style='color:black;'>{}</span>".format(customer_number))

    return u" / ".join(t)


def wrap_html_text(s: str, l=10):
    if l < 1:
        # Mainly to avoid 0
        l = 10

    i = 0
    fragments = []
    while i < len(s):
        fragments.append(s[i: min(i + l, len(s))])
        i += l
    return "<br/>".join(fragments)
