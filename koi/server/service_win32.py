#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import platform
import os
import time
import locale
import traceback
import logging
import logging.handlers
import io
##import colorlog

import win32serviceutil
import win32service
import win32event
import win32api
import servicemanager
from win32com.shell import shell, shellcon


from koi.as_unicorn import codename
from koi.base_logging import mainlog,init_logging,init_server_directory
from koi.server.cherry import configure_server, start_server, base_init
from koi.Configurator import configuration

import cherrypy
class HelloWorld:
    """ Sample request handler class. """

    def __init__(self):
        self.i = 0

    def index(self):
        self.i += 1
        # CSIDL_COMMON_APPDATA
        return "Hello world! {} user={} cwd={} shelld={} programdata={}".format(self.i,  os.getlogin(), os.getcwd(),
                                                                                shell.SHGetFolderPath(0, shellcon.CSIDL_APPDATA, 0, 0),
                                                                                shell.SHGetFolderPath(0, shellcon.CSIDL_COMMON_APPDATA, 0, 0))
    index.exposed = True



def configure_logging():
    cherrypy.config.update({
        'global':{
            'log.screen': False,
        }
    })

# def configure_server():
#
#     cherrypy.config.update({
#         'global':{
#             'log.screen': False,
#             'log.access_log' : mainlog,
#             'log.error_log' : mainlog,
#             'engine.autoreload.on': False,
#             'engine.SIGHUP': None,
#             'engine.SIGTERM': None
#         }
#     })
#
#     # Specific for Windows service
#     application_config = {
#         'global' : {
#             'log.screen' : False,
#             'log.access_log' :  mainlog,
#             'log.error_log' : mainlog,
#             'engine.autoreload.on': False,
#             'engine.SIGHUP': None,
#             'engine.SIGTERM': None
#         }
#     }
#
#     application = cherrypy.tree.mount(HelloWorld(), '/', config=application_config)
#
#     # That's it :
#     application.log.screen = False
#     application.log.access_log = mainlog
#     application.log.error_log = mainlog
#
#
# def start_server():
#     cherrypy.engine.start()
#     cherrypy.engine.block()
#
# def base_init():
#     pass
    
class Service(win32serviceutil.ServiceFramework):
    _svc_name_ = 'HorseWebServer' #here is now the name you would input as an arg for instart
    _svc_display_name_ = 'Horse web server' #arg for instart
    _svc_description_ = 'Horse web server service'# arg from instart

    # no parameters are permitted; all configuration should be placed in the
    # configuration file and handled in the Initialize() method
    def __init__(self, *args):
        win32serviceutil.ServiceFramework.__init__(self, *args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)

        # log_file_path = pathlib.Path(sys.executable).parent.resolve().joinpath("handler_log.log")

        # log_file_path = 'c:/tmp/handler_log.log'
        #
        # logging.basicConfig(level="DEBUG", format="%(asctime)s - %(levelname)s - %(funcName)s: %(message)s",
        #     filename=str(log_file_path))
        # logging.info("*******************************************************")


    def log(self, msg):
        servicemanager.LogInfoMsg(str(msg))

    # called when the service is starting
    def Initialize(self, configFileName = ""):
        self.log("Initalize() - The configfilename is %s", configFileName)

    # called when the service is starting immediately after Initialize()
    # use this to perform the work of the service; don't forget to set or check
    # for the stop event or the service GUI will not respond to requests to
    # stop the service
    def run(self):
        self.log("run()")
        configure_server()
        self.log("start server")
        start_server()


    # called when the service is being stopped by the service manager GUI
    def stop(self):
        self.log("Stop()")
        cherrypy.engine.exit()


    def SessionChanged(self, sessionId, eventType):
    
        # NOT IMPLEMENTED
        # needs SESSION_CHANGES set to True in your config.py file
        # see https://msdn.microsoft.com/en-us/library/windows/desktop/ms683241%28v=vs.85%29.aspx for the event types
        pass


    def sleep(self, minute):
        win32api.Sleep((minute*1000), True)

    def SvcDoRun(self):
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        try:
            self.ReportServiceStatus(win32service.SERVICE_RUNNING)
            self.log('start')
            self.run()
            self.log('wait')
            win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)
            self.log('done')
        except Exception as  ex:
            self.log('Exception : %s' % ex)
            self.SvcStop()

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.log('stopping')
        self.stop()
        self.log('stopped')
        win32event.SetEvent(self.stop_event)
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)


"""
Building with py2exe :

py2exe will magically find the class of the service.
It will give us its own service start/sop/install/... wrapper so we don't have to take care of that.
This will be provided on a command line, just run the exe to see it.

set PYTHONPATH=c:\PORT-STC\PRIVATE\PL\horse
build_exe --summary --service koi.server.service_win32 --include cherrypy.wsgiserver.wsgiserver3


Building with pyinstaller :

set PYTHONPATH=c:\PORT-STC\PRIVATE\PL\horse
pyinstaller --clean --onedir koi\server\service_win32.py



"""

if __name__ == '__main__':

    init_server_directory()
    if len(sys.argv) == 1: # No parameters passed, that's when Windows itself starts the service.
        init_logging("webserver.log", console_log=False)
    else:
        init_logging("webserver.log", console_log=True)

    mainlog.setLevel(logging.DEBUG)

    configuration.load_server_configuration()
    base_init()

    if len(sys.argv) == 1: # No parameters passed
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(Service)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        if sys.argv[1] == 'test':
            configure_server()
            configure_logging()
            start_server()
        else:
            # python -m koi.server.service_win32 --user %USERNAME%\%USERDOMAIN% --password 2323 install

            if '--password' in sys.argv:
                # In InnoSetup, I can't request a password
                print("\n"*100)
                password = input("Please give {}\\{}'s password : ".format(os.environ['USERDOMAIN'],os.environ['USERNAME']))
                sys.argv[sys.argv.index('--password') + 1] = password

            win32serviceutil.HandleCommandLine(Service)
