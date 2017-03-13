from datetime import datetime
from koi.base_logging import mainlog,log_stacktrace
from koi.server.json_decorator import ServerException

class LoggedError(object):
    def __init__(self,code,message):
        self.time = datetime.now()
        self.triggers_count = 1
        self.code, self.message = code, message

    def same_as(self,err):
        return self.code == err.code and self.message == err.message

    def retrigger(self):
        self.time = datetime.now()
        self.triggers_count += 1


class MemLogger(object):
    def __init__(self,max_lines = 500):
        self.clear_errors()

    def clear_errors(self):
        """ Remove all the errors currently present in thelogger
        """

        self.errors = []


    def exception(self, ex):
        log_stacktrace()

        if isinstance(ex, ServerException):
            mainlog.error(u"MemLog {}".format(str(ex)))
            self.error(ex.code, ex.translated_message)
        else:
            self.error(-1, str(ex))


    def error(self,code,msg):

        new_err = LoggedError(code,msg)

        if len(self.errors) >= 1 and self.errors[-1].same_as(new_err):
            self.errors[-1].retrigger()
        else:
            self.errors.append(new_err)

    def last_error(self,max_age = 60):
        """ Return the last error up to max_age.
        Returns None if there's no such error

        Max age in seconds
        """

        if len(self.errors) > 0:
            last = self.errors[-1]
            now = datetime.now()

            if (now - last.time).seconds < max_age:
                return last

        return None
