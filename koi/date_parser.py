import re
#import formencode
from datetime import datetime,date

from koi.Configurator import mainlog



"""
+class ActionKeyFilter(QObject):
+
+    def __init__(self, login, password, parent):
+        QObject.__init__(self, parent)
+
+        self.loginEdit = login
+        self.passwordEdit = password
+
+    def eventFilter(self, obj, event):
+        if not event:
+            return False
+
+        if event.type() != QEvent.KeyPress:
+            return False
+
+        if event.key() not in (Qt.Key_Return, Qt.Key_Enter):
+            return False
+
+        print "Obj", obj
+        if obj == self.loginEdit:
+            print "Changing focus"
+            self.passwordEdit.setFocus(Qt.OtherFocusReason)
+        elif obj == self.passwordEdit:
+            message = ""
+            icon = None
+
+            if not (self.loginEdit.text() or self.passwordEdit.text()):
+                message = "Please enter your credentials"
+                icon = QMessageBox.Warning
+            else:
+                message = "Login Successfull"
+                icon = QMessageBox.Information
+
+            messageBox = QMessageBox()
+            messageBox.setText(message)
+            messageBox.addButton("
OK", QMessageBox.AcceptRole)
+            messageBox.setIcon(icon)
+            messageBox.exec_()
+
+        return False
"""


def number_set_re(mini,maxi):
   # I use reversed because I think the RE exp engine might not be greedy
   # (or it's the other way around :-) )

   return r'[\s]*(' + '|'.join( map(lambda x:r'0*'+str(x),reversed(range(mini,maxi+1)))) + ')'


class TimeParser(object):
   _time_re_hms = re.compile( r'^\s*' +
                          number_set_re(0,23) + r'[\:h]' +
                          number_set_re(0,59) + r'[\:m]' +
                          number_set_re(0,59) + 's?' +
                          r'\s*$')

   _time_re_hm = re.compile( r'^\s*' +
                          number_set_re(0,23) + r'[\:h]' +
                          number_set_re(0,59) + r'[\:m]?' +
                          r'\s*$')

   _time_re_h = re.compile( r'^\s*' +
                          number_set_re(0,23) + r'[\:h]?' +
                          r'\s*$')

   _re = [_time_re_hms, _time_re_hm, _time_re_h]

   def __init__(self,base_date):
      self.base_date = base_date


   def parse(self,s):
      """ Parse a time stamp like ''23:59:59'' or ''22h59''.
      Returns ''False'' if the parsing is not successful. """

      # FIXME Having default values here is not elegant at all !

      if(s is None or s.strip() == ''):
         return datetime(year=self.base_date.year, month=self.base_date.month, day=self.base_date.day,
                         hour=8, minute=0, second=0)

      for re in self._re:
         time_scan = re.search(s)

         if time_scan and time_scan.groups():
            grps = time_scan.groups()

            t = [0] * 3
            for i in range(len(grps)):
               t[i] = grps[i]

            try:
               return datetime(year=self.base_date.year, month=self.base_date.month, day=self.base_date.day,
                               hour=int(t[0]), minute=int(t[1]), second=int(t[2]))
            except ValueError as e:
               return False

      return False




class DateTimeParser(object):
   _date_re = re.compile('^\s*' + number_set_re(1,31) + '/' + number_set_re(1,12)
                        + r'/[\s0]*([12][0-9]{3})(\s|$)')

   _time_re = re.compile( r'^'+number_set_re(0,23) + r'\s*[\:hH]'
                          + number_set_re(0,59) +  r'?\s*[\:mM]?'
                          + number_set_re(0,59) +  r'?\s*[sS]?$')


   def parse(self,s):
      """ Parse a date time stamp like ''28/2/2009 23:59:59''.
      The time part is optional.
      Returns ''False'' if the parsing is not successful. """

      # mainlog.debug("Parsing {}".format(s))
      if not s:
         return False

      date_scan = self._date_re.search(s)

      if date_scan and date_scan.groups():

         # mainlog.debug("Time scan on |{}|".format(s[date_scan.end():len(s)]))
         time_scan = self._time_re.search(s[date_scan.end():len(s)])
         # mainlog.debug("date_scan {}".format(date_scan.groups()))

         # if time_scan: mainlog.debug("time_scan {}".format(time_scan.groups()))
         if time_scan and time_scan.groups():
            t = time_scan.groups()
            if len(t) < 3:
               t = t + [0] * (3 - len(t))
         elif s[date_scan.end():len(s)].strip() == '':
            t = [0,0,0]
         else:
            # mainlog.debug("parse failed")
            return False


         try:
            d = date_scan.groups()

            #mainlog.debug("parse groups : {}".format(d))

            d = [ (dc or 0) for dc in d]
            t = [ (tc or 0) for tc in t]

            # mainlog.debug(d)
            # mainlog.debug(t)

            return datetime(year=int(d[2]),month=int(d[1]),day=int(d[0]),
                            hour=int(t[0]), minute=int(t[1]), second=int(t[2]))
         except ValueError as e:
            mainlog.debug("parse groups failed")
            mainlog.exception(e)
            return False
      else:
         # mainlog.debug("date scan parse failed")

         return False


class DurationParser(object):
   _regex_days =  re.compile('([0-9.]+) *j')
   _regex_hours = re.compile('([0-9.]+) *h')
   _regex_minutes = re.compile('([0-5]?[0-9]+(\\.[0-9]+)?) *m')

   _regex_hours_minutes = re.compile('([0-9]+)?( *h|H|: *)([0-9]+)?')

   def __init__(self):
      pass

   def parse(self,text):
      """ parse to hours (float). E.g. 2.5 hours == 2h 30m """

      if text == None or len(text.strip()) == 0:
         return None

      # Durations can be positive or negative
      multi = +1
      if text.strip()[0] == '-':
         multi = -1
         if text.strip() == '-':
            return 0

      match_days = self._regex_days.search(text)
      match_hours = self._regex_hours.search(text)
      match_minutes = self._regex_minutes.search(text)
      duration = 0

      match_hours_minutes = self._regex_hours_minutes.match(text)

      if match_hours_minutes:
         h, h_symbol, m = match_hours_minutes.groups()
         h = float(h or 0)
         if m:
            m = float(m)
         else:
            m = 0
         duration = h + m / 60.0
         return duration*multi

      # If not d/h/m then we assume hours. Hours expressed as float.
      if not match_minutes and not match_days and not match_hours:
         duration += float(text)
         return duration
      else:
         if match_minutes:
            duration += float(match_minutes.group(1)) / 60.0

         if match_hours:
            duration += float(match_hours.group(1))

         if match_days:
            duration += float(match_days.group(1)) * 24

         return duration*multi



class FutureDateParser(DateTimeParser):
   def __init__(self,base_date=None):
      self.day_month_regex = re.compile('([0-9]{1,2})/([0-9]{1,2})$')
      self.base_date = base_date
      super(FutureDateParser,self).__init__()

   def parse(self,text):
      m = self.day_month_regex.match(text)

      if m:
         day = int(m.groups()[0])
         month = int(m.groups()[1])
         today = self.base_date or datetime.now().date()
         # mainlog.debug("Today is {}".format(today))

         if month > today.month or (month == today.month and day > today.day):
            year = today.year
         else:
            year = today.year + 1

         try:
            return date(year,month,day) # FIXME Should return timestamp
         except ValueError as ex:
            return False
      else:
         # mainlog.debug("FutureDateParser using super")
         d = super(FutureDateParser,self).parse(text)
         if d is not False:
            return date(d.year,d.month,d.day)
         else:
            return False

class SimpleDateParser(FutureDateParser):
   def __init__(self):
      super(SimpleDateParser,self).__init__(date(1970,1,1))
