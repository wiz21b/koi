#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import asyncio
import pathlib
import sys


import cherrypy
from koi.server.cherry import configure_server, start_server
from koi.base_logging import mainlog

class HelloWorld:
    """ Sample request handler class. """

    def index(self):
        return "Hello world!"
    index.exposed = True



import win32serviceutil
import win32service
import win32event
import win32api
import servicemanager


    
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

        log_file_path = 'c:/tmp/handler_log.log'

        logging.basicConfig(level="DEBUG", format="%(asctime)s - %(levelname)s - %(funcName)s: %(message)s",
            filename=str(log_file_path))
        logging.info("*******************************************************")

        # # set up instance variables
        # self.loop = asyncio.ProactorEventLoop()
        # asyncio.set_event_loop(self.loop)
        # self.stopRequestedEvent = asyncio.Event(loop=self.loop)
        # self.stopFinishedEvent = asyncio.Event(loop=self.loop)

        configure_server()


        #logs into the system event log
    def log(self, msg):
        servicemanager.LogInfoMsg(str(msg))

    # called when the service is starting
    def Initialize(self, configFileName):

        logging.info("Initalize() - The configfilename is %s", configFileName)

    # @asyncio.coroutine
    # def theloop(self):
    #     logging.info("waiting for event")
    #     yield from self.stopRequestedEvent.wait()
    #     logging.info("stopRequestedEvent set! setting stopFinishedEvent")
    #
    #     self.stopFinishedEvent.set()

    # called when the service is starting immediately after Initialize()
    # use this to perform the work of the service; don't forget to set or check
    # for the stop event or the service GUI will not respond to requests to
    # stop the service
    def Run(self):
        logging.info("Run()")

        # asyncio.async(self.theloop())

        
        # # Specific for Windows service
        # cherrypy.config.update({
        #     'global':{
        #         'log.screen': False,
        #         'engine.autoreload.on': False,
        #         'engine.SIGHUP': None,
        #         'engine.SIGTERM': None
        #     }
        # })
        #
        # application = cherrypy.tree.mount(HelloWorld(), '/')
        #
        # cherrypy.log.screen = False
        # cherrypy.log.access_log = logging
        # cherrypy.log.error_log = logging
        #
        # application.log.screen = False
        # application.log.access_log = logging
        # application.log.error_log = logging
        #
        # logging.info("starting run_until_complete()-1")
        # cherrypy.engine.start()
        # logging.info("starting run_until_complete()-2")
        # cherrypy.engine.block()
        # logging.info("starting run_until_complete()-3")
        #
        #
        # cherrypy.engine.start()
        # cherrypy.engine.block()
        start_server()

        # self.loop.run_forever()
        # logging.info("stopFinishedEvent set, loop completed")
        # self.loop.shutdown()
        # logging.info("loop shutdown")

    # @asyncio.coroutine
    # def stoploop(self):
    #
    #     logging.info("setting stopReuqestedEvent")
    #     self.stopRequestedEvent.set()
    #     yield from self.stopFinishedEvent.wait()
    #     logging.info("stopFinishedEvent is set, shutting down loop")
    #
    #     self.loop.stop()

    # called when the service is being stopped by the service manager GUI
    def Stop(self):
        logging.info("Stop()")
        cherrypy.engine.exit()

        # make sure that stoploop() runs on the same thread as Run(), since Stop() gets called on
        # a different thread other then the 'main one'
        # self.loop.call_soon_threadsafe(asyncio.async,self.stoploop())
        
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
            self.start()
            self.log('wait')
            win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)
            self.log('done')
        except Exception as x:
            self.log('Exception : %s' % x)
            self.SvcStop()

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        #self.log('stopping')
        self.stop()
        #self.log('stopped')
        win32event.SetEvent(self.stop_event)
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(Service)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(Service)
