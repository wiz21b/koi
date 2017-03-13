import sys
import os
import cgi
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import urlparse
import re

from pymediafire import MediaFireSession, MediaFireFile,MediaFireFolder


# import pythoncom
# import win32serviceutil
# import win32service
# import win32event
# import servicemanager
import socket





def upgrade(version):
    filename = "horse-{}.zip".format(version)
    dest = os.path.join(get_data_dir(), filename)

    mainlog.info("Downloading a new version {} into {}".format(filename,dest))
    mf = MediaFire(configuration.get("MediaFire","email"),
                   configuration.get("MediaFire","password"),
                   configuration.get("MediaFire","appid"),
                   configuration.get("MediaFire","sessionkey"),
                   configuration.get("Proxy","proxy_url"),
                   configuration.get("Proxy","proxy_port"))

    res = ""

    folder = mf.load_directory()
    for entry in folder:
        if isinstance(entry,MediaFireFile) and entry.filename == filename:
            mf.download(entry, dest) # FIXME dest
            configuration.set("DownloadSite","current_version",str(version))
            configuration.set("DownloadSite","client_path",dest)

            configuration.save()
            return "Successfully downloaded {}. Config was updated.".format(str(version))

    raise Exception("Version {} was not found on MediaFire".format(str(version)))

class MyHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        mainlog.info("{} from {}".format(format % args, self.client_address))


    def do_GET(self):
        try:
            self.handle_request()
        except Exception as ex:
            mainlog.exception(ex)
            log_stacktrace()

    def handle_request(self):

        path = re.sub("\\?.*","",self.path)
        params = urlparse.parse_qs( urlparse.urlparse(self.path).query)

        if path == '/version':
            self.send_response(200)
            self.send_header('Content-type',    'text/html')
            self.end_headers()
            self.wfile.write(configuration.get("DownloadSite","current_version"))
            return

        elif path == '/file':
            f = open( configuration.get("DownloadSite","client_path"), 'rb' )
            bytes = f.read()
            f.close()
            self.send_response(200)
            self.send_header('Content-type',    'application/octet-stream')
            self.send_header('Content-Length',    str(len(bytes)))
            self.send_header('Content-Disposition', 'attachment; filename={}'.format(os.path.split(configuration.get("DownloadSite","client_path"))[-1]))
            self.send_header('Content-Transfer-Encoding', 'binary')
            self.end_headers()
            self.wfile.write(bytes)
            mainlog.info("Served {} with {} bytes".format(configuration.get("DownloadSite","client_path"), len(bytes)))
            return

        elif path == '/database':
            self.send_response(200)
            self.send_header('Content-type',    'text/html')
            self.end_headers()
            self.wfile.write(configuration.get("DownloadSite","db_url"))
            return

        elif path == '/delivery_slips':
            f = open( configuration.get("DownloadSite","client_path"), 'rb' )
            bytes = f.read()
            f.close()
            self.send_response(200)
            self.send_header('Content-type',    'application/octet-stream')
            self.send_header('Content-Length',    str(len(bytes)))
            self.end_headers()
            self.wfile.write(bytes)
            return

        elif path == '/logo.png':
            f = open( os.path.join(resource_dir,"file_server_logo.png"), 'rb' )
            bytes = f.read()
            f.close()
            self.send_response(200)
            self.send_header('Content-type', 'image/png')
            self.end_headers()
            self.wfile.write(bytes)
            return

        elif self.path.startswith('/upgrade'):

            if 'version' not in params:
                mainlog.error("Upgrade requested without version")

                self.send_response(500)
                self.send_header('Content-type',    'text/html')
                self.end_headers()
                self.wfile.write("Version parameter not supplied")
                return

            version = ''.join(params['version']).strip()
            mainlog.info("Upgrade requested to version {}".format(version))

            res = "No message"
            try:
                res = upgrade(version)
                self.send_response(200)
            except Exception as ex:
                mainlog.error("Upgrade failed because {}".format(str(ex)))
                res = str(ex)
                self.send_response(500)

            self.send_header('Content-type',    'text/html')
            self.end_headers()
            self.wfile.write(cgi.escape(res))

            return
        else:
            mainlog.error("Unsupported path {} from {}".format(self.path, self.client_address))

            load_configuration("server.cfg","server_config_check.cfg")

            self.send_response(200)
            self.send_header('Content-type',    'text/html')
            self.end_headers()
            self.wfile.write("""<html><head>
<meta http-equiv="content-type" content="text/html; charset=ISO-8859-1"><style>
p,h2 {text-align:center; font-family:Verdana; }
table, th, td { border: 1px solid #2900af; border-collapse:collapse; padding:0; margin:0; }
img {background-color:white;}
</style></head>

<body>
   <br/>
   <p><img koi="logo.png"></p>
   <br/>
   <table width="100%" height="1"><tr><td></td><tr/></table><br/><br/>
   <h2>This is the Horse download site !</h2>
""")
            self.wfile.write("<p>The current version is <b>{}</b>.</p>".format(configuration.get("DownloadSite","current_version")))
            self.wfile.write("<p>To download the latest delivery_slips, <a href='/file'>click here</a>.</p>")
            self.wfile.write("</body></html>")

def keep_running():
    return True


def main():
    try:
        server = HTTPServer(('', int(configuration.get("DownloadSite","port"))), MyHandler)
        mainlog.info("Starting server on port {}".format(configuration.get("DownloadSite","port")))

        while keep_running():
            server.handle_request()

    except KeyboardInterrupt:
        mainlog.info('^C received, shutting down server')
        server.socket.close()

if __name__ == '__main__':
    from koi.base_logging import init_logging,mainlog,log_stacktrace
    init_logging("file_server.log")
    from koi.Configurator import load_configuration,init_i18n,configuration,resource_dir
    load_configuration("server.cfg","server_config_check.cfg")

    frozen = getattr(sys, 'frozen', False)
    mainlog.info(len(sys.argv))
    mainlog.info(frozen)

    if (not frozen and len(sys.argv) >= 2) or (frozen and len(sys.argv) >= 1):
        import pythoncom
        import win32serviceutil
        import win32service
        import win32event
        import servicemanager

        class AppServerSvc (win32serviceutil.ServiceFramework):
            _svc_name_ = "HorseWebServer"
            _svc_display_name_ = "Horse web server"

            def __init__(self,args):
                win32serviceutil.ServiceFramework.__init__(self,args)
                self.hWaitStop = win32event.CreateEvent(None,0,0,None)
                socket.setdefaulttimeout(60)

            def SvcStop(self):
                self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
                win32event.SetEvent(self.hWaitStop)

            def SvcDoRun(self):
                servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                                      servicemanager.PYS_SERVICE_STARTED,
                                      (self._svc_name_,''))
                self.main()

            def main(self):
                server = HTTPServer(('', int(configuration.get("DownloadSite","port"))), MyHandler)

                while True:
                    server.handle_request()
        
        
        win32serviceutil.HandleCommandLine(AppServerSvc)
    else:
        mainlog.info("Command line execution")
        main()
