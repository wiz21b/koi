# python cx_setup.py build
# http://stackoverflow.com/questions/153221/runnning-a-python-web-server-as-a-service-in-windows
# To install : horse_server.exe --install TEST
# To uninstall :
# sc stop HorseServerTEST
# sc delete HorseServerTEST

import os
import sys
import threading
from BaseHTTPServer import HTTPServer



# from BaseHTTPServer import BaseHTTPRequestHandler
# class HorseHTTPHandler(BaseHTTPRequestHandler):
#     def do_GET(self):
#         try:
#             self.handle_request()
#         except Exception, ex:
# 	    print ex

#     def handle_request(self):        
#         from Logging import mainlog,horse_dir

#         mainlog.info(self.path)

#         self.send_response(200)
#         self.send_header('Content-type',    'text/html')
#         self.end_headers()
#         self.wfile.write("ljlkjkljlk" + str(os.environ) + horse_dir)
#         return


class Handler(object):
    """ cx_Freeze's style Windows service
    """

    # no parameters are permitted; all configuration should be placed in the
    # configuration file and handled in the Initialize() method
    def __init__(self):
        self.stopEvent = threading.Event()
        self.stopRequestedEvent = threading.Event()

    # called when the service is starting
    def Initialize(self, configFileName):
        from Logging import mainlog, horse_dir, init_logging
        init_logging('web_server.log')
        mainlog.info("Horse dir : {}".format(horse_dir))

        try:
            from Configurator import load_configuration, configuration, resource_dir
            mainlog.info("Resource dir : {}".format(resource_dir))
            load_configuration("server.cfg","server_config_check.cfg")
            mainlog.info("configuration loaded")

            from koi.http_handler import HorseHTTPHandler
            p = int(configuration.get("DownloadSite","port"))
            mainlog.info("Listening on port {}".format(p))
            self.server = HTTPServer(('', p), HorseHTTPHandler)
        except Exception as ex:
            mainlog.exception(ex)
            raise ex


    # called when the service is starting immediately after Initialize()
    # use this to perform the work of the service; don't forget to set or check
    # for the stop event or the service GUI will not respond to requests to
    # stop the service
    def Run(self):
        from Logging import mainlog
        mainlog.info("Running service")
        # All of this to make sure the service remains
        # stoppable whatever happens
        while True:
            try:
                # serve_forever will be interrupted by server.shutdown
                # when Windows' Service Manager will call the
                # Stop method.

                # I set the poll interval because I think
                # Python's default is too high
                self.server.serve_forever(poll_interval=1)

                # Warn the Stop method that we have
                # acknowledged the stop request
                self.stopEvent.set()

            except Exception as ex:
                # Make sure the service restarts if something
                # went wrong
                mainlog.error(str(ex))
                pass

    # called when the service is being stopped by the service manager GUI
    def Stop(self):
        from Logging import mainlog
        mainlog.info("Service shut down requested")
        self.server.shutdown() # stop the server_forever loop
        self.stopRequestedEvent.set() # not really necessary
        self.stopEvent.wait() # will be set when leaving self.Run()
        mainlog.info("Service shut down acknowledged")

# import logging
# import logging.handlers

# logging.basicConfig(level=logging.DEBUG,format='%(asctime)s [%(levelname)s] %(message)s')
# mainlog = logging.getLogger('MainLog')


# import win32service
# import win32event
# import win32api
# import win32serviceutil
# import servicemanager

# class HorseWindowsService(win32serviceutil.ServiceFramework):
#     _svc_name_ = "HorseWebServer"
#     _svc_display_name_ = "Horse web server"
#     _svc_description_ = "Horse web server"

#     def __init__(self, args):
#         win32serviceutil.ServiceFramework.__init__(self, args)
#         self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)           
#         self.ReportServiceStatus(win32service.SERVICE_START_PENDING,waitHint=10000)


#     def SvcStop(self):
#         self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
#         sys.exit(0)

#     # def SvcStop(self):
#     #     self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
#     #     self.httpd.stop()

#     def SvcDoRun(self):
#         self.ReportServiceStatus(win32service.SERVICE_RUNNING)
#         servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
#                               servicemanager.PYS_SERVICE_STARTED,
#                               (self._svc_name_, '')) 
#         servicemanager.LogInfoMsg("Horse server starting run ")

#         self.timeout = 3000
#         server = HTTPServer(('', int(configuration.get("DownloadSite","port"))), HorseHTTPHandler)

#         mainlog.info("Ready to run")
#         while 1:
#             rc = win32event.WaitForSingleObject(self.hWaitStop, self.timeout)
#             if rc == win32event.WAIT_OBJECT_0:
#                 servicemanager.LogInfoMsg("Horse server Stopped ")
#                 break
#             server.handle_request()

# def ctrlHandler(ctrlType):
#     return True

from SocketServer import ThreadingMixIn
import threading

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """ This class allows to handle requests in separated threads.
    No further content needed, don't touch this. 
    This is important because some browsers *need* to
    be able to send several requests simultaneously to the
    server. And if they can't, because the server is single threaded
    then some browser's request will hang."""


def console_runner():

    try:
        # Thanks ! http://stackoverflow.com/questions/8403857/python-basehttpserver-not-serving-requests-properly
        server = ThreadedHTTPServer(('', int(configuration.get("DownloadSite","port"))), HorseHTTPHandler)

        while True:
            server.handle_request()

    except KeyboardInterrupt:
        print('^C received, shutting down server')
        server.socket.close()


if __name__ == '__main__':
    # Grab the koi directory (to get Logging, Configurator,...)
    # FIXME rather fragile...
    sys.path.append( os.path.join(os.path.abspath(__file__),'..','..') )
    from koi.http_handler import HorseHTTPHandler

    from Logging import init_logging,mainlog,horse_dir,log_stacktrace
    init_logging("file_server.log")
    from Configurator import load_configuration,init_i18n,configuration,resource_dir
    load_configuration("server.cfg","server_config_check.cfg")

    mainlog.info("Starting server on port {}".format(configuration.get("DownloadSite","port")))

    frozen = getattr(sys, 'frozen', False)

    # if (not frozen and len(sys.argv) >= 2) or (frozen and len(sys.argv) >= 2):
    #     mainlog.info("Service invocation")
    #     win32api.SetConsoleCtrlHandler(ctrlHandler, True)
    #     r = win32serviceutil.HandleCommandLine(HorseWindowsService)
    #     if r == 0:
    #         mainlog.info("Service invocation successful")
    #     else:
    #         mainlog.error("Service invocation failed with return code {}".format(r))
    #         sys.exit(1)
    # else:
    mainlog.info("Command line invocation")
    console_runner()
