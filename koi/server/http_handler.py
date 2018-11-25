import os
import cgi
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import urlparse
import re
import socket

from koi.base_logging import init_logging,mainlog,horse_dir,log_stacktrace
from Configurator import load_configuration,configuration,resource_dir
from pymediafire import MediaFireSession, MediaFireFile,MediaFireFolder

from koi.zipconf import configure_zip_with_config

def upgrade(version):
    filename = "horse-{}.zip".format(version)
    dest = os.path.join(horse_dir,filename)

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
            return "Successfully downloaded version {}. Config was updated.".format(str(version))

    raise Exception("Version {} was not found on MediaFire".format(str(version)))


class HorseHTTPHandler(BaseHTTPRequestHandler):

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

            configure_zip_with_config(configuration.get("DownloadSite","client_path"), configuration)

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
            self.wfile.write(configuration.get("Database","url"))
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
            self.send_header('Content-Length', str(len(bytes)))
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

            bytes = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
  "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html><head>
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
<p>The current version is <b>{version}</b>.</p>
<p>To download the latest delivery_slips, <a href='/file'>click here</a>.</p>
</body></html>
"""
            bytes = bytes.replace("{version}",configuration.get("DownloadSite","current_version"))

            self.send_response(200)
            self.send_header('Content-type',    'text/html')
            self.send_header('Content-Length', str(len(bytes)))
            self.end_headers()
            self.wfile.write(bytes)
