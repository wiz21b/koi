# -*- coding: utf-8 -*-
# I set the encoding for Emacs because there's a unicode test
# at the end of this file

import platform
import os
import sys
import time
import locale
import traceback
import logging
import logging.handlers
import io
from urllib.request import URLError
# import colorlog # Not Windows service friendly apparently

if platform.system() == 'Windows':
    import winreg
    from win32com.shell import shell, shellcon


from koi.as_unicorn import codename

# import sqlalchemy.exc
# from win32com.shell import shellcon, shell

class EncodingFormatter(logging.Formatter):

    def __init__(self):
        logging.Formatter.__init__(self, "", None)

    def format(self, record):
        '''
        :param record:
        :return: A string (as specified by Python 3 documentation. str means unicode)
        '''
        msg = None

        if type(record.msg) == URLError:
            if type(record.msg.reason) == str:
                msg = str(record.msg.reason)
            else:
                msg = "URLError / " + str(type(record.msg.reason))

        # elif type(record.msg) == sqlalchemy.exc.ProgrammingError:
        #     msg = "sqlalchemy.exc.ProgrammingError" # FIXME Why this ???

        elif type(record.msg) == str:
            msg = record.msg
        else:
            try:
                msg = str(record.msg)
            except Exception as ex:
                msg = "Can't log {} because {}".format(type(record.msg), str(ex))

        line = u"{} {} {}".format( time.strftime( '%Y/%m/%d %H:%M:%S', time.localtime(record.created) ),
                                   "[{}]".format(record.levelname).ljust(9),
                                   msg)

        return line


def _make_base_directory_name( basename):

    if platform.system()  == 'Linux':
        return os.path.join(os.environ['HOME'],'.config',basename)
    else:
        # It's windows (MacOs anybody ?)

        if 'APPDATA' in os.environ:
            # We're running from command line

            # Pay attention, this is an old Windows directory
            # It is now transferred to \Users\xxx\AppData\Roaming
            # via a junction point (see Windows documentation)

            return os.path.join(os.environ['APPDATA'],basename)
        else:

            # I *guess* we're running as a service
            # FIXME But that's a guess

            # The application dir is to be found in the registry

            # Pay attention, we need the 32 bits registry because
            # well, that's arbitrary. But that must be kept in
            # sync with the InnoSetup installer
            try:
                k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                   "Software\\" + basename.capitalize(),
                                   0,winreg.KEY_READ|winreg.KEY_WOW64_32KEY)
                return winreg.QueryValueEx(k,'base_dir')[0]
            except:
                return os.path.join( shell.SHGetFolderPath(0, shellcon.CSIDL_COMMON_APPDATA, 0, 0), codename)


def init_server_directory():

    if platform.system()  == 'Linux':
        koi_dir = os.path.join(os.environ['HOME'],'.config', codename)
    else:
        try:
            koi_dir = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                               "Software\\" + basename.capitalize(),
                               0,winreg.KEY_READ|winreg.KEY_WOW64_32KEY)
            koi_dir = winreg.QueryValueEx(k,'base_dir')[0]
        except:
            koi_dir = os.path.join( shell.SHGetFolderPath(0, shellcon.CSIDL_COMMON_APPDATA, 0, 0), codename)


    try:
        if not os.path.exists(koi_dir):
            os.makedirs(koi_dir)
        _root_dir['root_dir'] = koi_dir

    except:
        _root_dir['root_dir'] = "."


def init_application_directory():
    """ Figure out where the base application directory is.
    The base directory is where we store the configuration files,
    the log files, eventually the database or documents database.

    This involves several dirty tricks...
    """

    try:
        # Try legacy directory first
        koi_dir = _make_base_directory_name(codename)
    except:
        koi_dir = _make_base_directory_name('koimes')


    # The try statement is a hack, it allows the windows
    # version to run under Wine (in Linux)

    try:
        if not os.path.exists(koi_dir):
            os.makedirs(koi_dir)
        return koi_dir

    except:
        return "."



def log_stacktrace():
    for l in traceback.format_tb(sys.exc_info()[2]):
        mainlog.error(l)

def excepthook(type_ex,ex,tback):
    mainlog.exception(ex)
    mainlog.error(str(ex))
    for l in traceback.format_tb(tback):
        mainlog.error(l)


def init_logging(log_file = "{}.log".format(codename),hook_exceptions=True, console_log=True):
    global mainlog

    logfile_encoding = 'UTF-8'

    # platform_encoding = locale.getpreferredencoding() # locale.getdefaultlocale()[1]

    console_encoding = "ascii"
    try:
        console_encoding = sys.stdout.encoding
    except AttributeError as ex:
        # This to avoid "nose" error. My guess is that
        # nose redefines sys.stdout and forget to add
        # the encoding field
        pass

    if log_file:
        log_file = os.path.join(get_data_dir(), log_file)
        handler = logging.handlers.RotatingFileHandler(log_file, encoding=logfile_encoding,
                                                       maxBytes=1024*1024, backupCount = 100)
        handler.setFormatter(EncodingFormatter())
        mainlog.addHandler(handler)

    # if not getattr(sys, 'frozen', False) and console_log:
    if console_log:
        # I'm under the impression that once we run without
        # a console, things get a little bit trickier
        # so I disable logging to console in that case
        # (and all in all, it doesn't make much sense to
        # log to a console that is not shown :-))


        # Make sure encoding errors are caught when writing
        # to the console (by default sys.stdout will crash on them)
        wrapper = io.TextIOWrapper(sys.stdout.buffer, encoding=console_encoding, errors='backslashreplace')
        handler = logging.StreamHandler(wrapper) # sys.stdout
        handler.setFormatter(EncodingFormatter())
        mainlog.addHandler(handler)

        # handler = colorlog.StreamHandler(wrapper) # sys.stdout
        #
        # handler.setFormatter(colorlog.ColoredFormatter(
        #     '%(asctime)s [%(log_color)s%(levelname)s%(reset)s] %(message)s', datefmt='%Y/%m/%d %H:%M:%S'))

        # mainlog.addHandler(handler)

    mainlog.propagate = False
    mainlog.trace = log_stacktrace

    try:
        # Make sure the logging is tested right now
        handler.flush()
    except Exception as ex:
        raise Exception("Can't log to {}".format(log_file))

    # FIXME I'm under the impression that if I do that
    # before the handler.flush, then things go very
    # wrong when running as a service

    # Route all uncaught exceptions to our logger
    if hook_exceptions:
        sys.excepthook = excepthook

_root_dir = {'root_dir' : init_application_directory()}

def get_data_dir():
    return _root_dir['root_dir']

class Devnull(object):
    def write(self, *_): pass

logging.basicConfig(level=logging.DEBUG, stream=Devnull(), format='%(asctime)s [%(levelname)s] %(message)s')
mainlog = logging.getLogger('MainLog')
mainlog.setLevel(logging.INFO)

# mainlog.debug("Clearing handler {} ".format(mainlog.handlers))
for h in mainlog.handlers:
    mainlog.removeHandler(h)

# I don't log anything at this point because sometimes the logger must
# be manipulated some more before being used (for example when one
# makes a Windows service, nothing must be sent to STDOUT)
mainlog.propagate = False

# if getattr(sys, 'frozen', False):
#     mainlog.setLevel(logging.INFO)

# Temporary fix to display info for special crash
# mainlog.setLevel(logging.DEBUG)

# mainlog.setLevel(logging.ERROR)

if __name__ == "__main__":
    init_logging()
    mainlog.setLevel(logging.DEBUG)
    # Here we test unicode logging
    mainlog.warn(u"warning level Testing configuration logging with unicode : äùééé")
    mainlog.debug("debug level Testing configuration logging")
