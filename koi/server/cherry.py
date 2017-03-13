"""
Install whit VisualStudio Express

set PATH=%PATH%;c:\ Users\stefan\PL\pgsql\bin
"C:\Program Files\Microsoft Visual Studio 10.0\VC\vcvarsall.bat"
installer les redistribuables de windows
pip install psycopg2
pip install sqlalchemy
pip install jsonrpc2

Download pywin32 from http://www.lfd.uci.edu/~gohlke/pythonlibs/#pywin32 
... bercause it is built for Python 3.4 (may take time)
pip install Downloads\ pywin32-219-cp34-none-win32.whl

Because http://code.activestate.com/lists/python-list/667719/

python C:\Python34\Scripts\pywin32_postinstall.py
"""

import logging
import os
import argparse
import cherrypy
import re
import zipfile


from mediafire.client import MediaFireClient


from koi.Configurator import init_i18n

init_i18n('en_EN') # The server speaks english

from koi.base_logging import mainlog,init_logging,get_data_dir
from koi.as_unicorn import codename

if __name__ == "__main__":
    init_logging("http.log", console_log=True)
    # mainlog.setLevel(logging.DEBUG)



from koi.tools.chrono import *
from koi.Configurator import configuration,resource_dir,configuration_file_exists, path_to_config, make_empty_configuration_file, load_configuration_server, guess_server_url
from koi.server.net_tools import guess_server_public_ip
from koi.legal import copyright, license_short
from koi.dao import dao
from koi.backup.pg_backup import full_restore
from koi.server.demo import create_demo_database
from koi.datalayer.create_database import create_root_account


def base_init():
    global services, json_rpc_dispatcher


    init_db_session(configuration.get('Database','url'), metadata, False or configuration.echo_query)
    dao.set_session(session())

    json_rpc_dispatcher = HorseJsonRpc()

    make_server_json_server_dispatcher(json_rpc_dispatcher,
                                       JsonCallWrapper(
                                           ClockService(), JsonCallWrapper.CHERRYPY_MODE))

    make_server_json_server_dispatcher(json_rpc_dispatcher,
                                       JsonCallWrapper(
                                           DocumentsService(), JsonCallWrapper.CHERRYPY_MODE))

    make_server_json_server_dispatcher(json_rpc_dispatcher,
                                       JsonCallWrapper(
                                           IndicatorsService(), JsonCallWrapper.CHERRYPY_MODE))

    services = Services()
    services.register_for_server(session, Base)

    # return services, json_rpc_dispatcher



# init_logging("http.log")
# mainlog.setLevel(logging.DEBUG)
# init_i18n('en_EN') # The server speaks english
# load_configuration("server.cfg","server_config_check.cfg")

from koi.datalayer.sqla_mapping_base import metadata
from koi.datalayer.database_session import init_db_session, disconnect_db

# mainlog.debug("Starting server, DB is : {}".format(configuration.get('Database','url')))
# init_db_session(configuration.get('Database','url'), metadata, False or configuration.echo_query)

from koi.doc_manager.documents_service import documents_service
from koi.server.clock_service import ClockService

# wget "http://localhost:8079/json_rpc?query={\"jsonrpc\": \"2.0\", \"method\": \"supply_order_service.find_recent_parts\", \"id\":\"269\"}"
# from simplejson import loads,dumps : Faster but not won windows ? FIXME



# jsonrpc_dispatcher = JsonRpc()
# jsonrpc_dispatcher['supply_order_service.find_recent_parts'] = supply_order_service.find_recent_parts


from koi.server.json_decorator import make_server_json_server_dispatcher, horse_json_encoder, JsonCallWrapper, ServerException, \
    HorseJsonRpc

#from koi.server.server import ServerException

# json_rpc_dispatcher = HorseJsonRpc()
#
# make_server_json_server_dispatcher(json_rpc_dispatcher,
#                                    JsonCallWrapper(
#                                        ClockService(), JsonCallWrapper.CHERRYPY_MODE))

from koi.doc_manager.documents_service import DocumentsService

# make_server_json_server_dispatcher(json_rpc_dispatcher,
#                                    JsonCallWrapper(
#                                        DocumentsService(), JsonCallWrapper.CHERRYPY_MODE))

from koi.server.client_config_injector import inject_public_ip_in_client


from koi.charts.indicators_service import IndicatorsService
# make_server_json_server_dispatcher(json_rpc_dispatcher,
#                                    JsonCallWrapper(
#                                        IndicatorsService(), JsonCallWrapper.CHERRYPY_MODE))


from urllib.request import build_opener,ProxyHandler,HTTPHandler,HTTPSHandler,HTTPRedirectHandler
from http.client import HTTPConnection

from jsonrpc2 import JsonRpc


from koi.datalayer.database_session import session
from koi.datalayer.sqla_mapping_base import Base
from koi.junkyard.services import Services

# services = Services()
# services.register_for_server(session, Base)




def http_download(download_url, outfile, proxy_url=None, proxy_port = None):

    if proxy_url:
        proxy = "{}:{}".format(proxy_url,proxy_port)
        mainlog.info("Using a proxy : {}".format(proxy))

        urlopener = build_opener(
            ProxyHandler({'https': proxy,
                          'http' : proxy}),
            HTTPRedirectHandler())
    else:
        mainlog.info("Not using a proxy")
        urlopener = build_opener(
            HTTPHandler(),
            HTTPSHandler(),
            HTTPRedirectHandler())


    urlopener.addheaders = [('User-agent', 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:32.0) Gecko/20100101 Firefox/32.0')]

    datasource = urlopener.open(download_url)

    out = open(outfile,'wb')
    while True:
        d = datasource.read(8192)
        # self.logger.debug("Downloaded {} bytes".format(len(d)))
        if not d:
            break
        else:
            out.write( d)
            out.flush()
    out.close()
    datasource.close()


def upgrade_file(path):
    global configuration
    re_file = re.compile(r'koi-delivery_slips-([0-9]+\.[0-9]+\.[0-9]+)\.zip')
    exe_filename = "{}/{}.exe".format( configuration.get("Globals","codename"), configuration.get("Globals","codename"))

    if os.path.exists(path):
        match = re_file.match(os.path.basename(path))

        if match:
            version = match.groups()[0]

            candidates = []
            exe_correct = False
            with zipfile.ZipFile(path, 'r') as zin:
                for item in zin.infolist():
                    if item.filename == exe_filename:
                        exe_correct = True
                        break
                    elif ".exe" in item.filename:
                        candidates.append(item.filename)

            if exe_correct:
                configuration.set("DownloadSite","current_version",str(version))
                configuration.set("DownloadSite","client_path",path)
                configuration.save()
                mainlog.info("Configuration successfully updated with delivery_slips version {}.".format(version))
                mainlog.warning("Don't forget to restart the server to take it into account !")
                return True
            else:
                mainlog.error("Didn't find {} inside the file you've given. Possible candidates {}".format(exe_filename, ", ".join(candidates)))
        else:
            mainlog.error("I don't recognize the filename. It should be 'koi-delivery_slips-a.b.c.zip'.")
    else:
        mainlog.error("The file {} was not found.".format(path))

    return False





def upgrade_http(version, url, proxy_url=None, proxy_port = None):
    codename = configuration.get("Globals","codename")
    filename = "{}-{}.zip".format(codename, version)
    dest = os.path.join(get_data_dir(),filename)

    mainlog.info("Upgrading from {} to version {}. File will be sotred in {}".format(url, version, dest))
    http_download(url, dest, configuration.get("Proxy","proxy_url"),
                          configuration.get("Proxy","proxy_port"))

    configuration.set("DownloadSite","current_version",str(version))
    configuration.set("DownloadSite","client_path",dest)
    configuration.save()

    return "Successfully downloaded version {} from {}. Config was updated.".format(str(version), url)




def upgrade_mediafire(version):
    """ Upgrade to the given version. The upgrades
    will be downloaded from mediafire.

    The version can be higher or lower than the current one.
    This allows to downgrade (in case of a failed upgrade)
    """

    codename = configuration.get("Globals","codename")
    filename = "{}-{}.zip".format(codename, version)
    dest = os.path.join(get_data_dir(),filename)

    mainlog.info("Downloading a new version {} into {} proxyport={}".format(filename,dest,configuration.get("Proxy","proxy_port")))

    client = MediaFireClient()
    client.login(
        email=configuration.get("MediaFire","email"),
        password=configuration.get("MediaFire","password"),
        app_id=configuration.get("MediaFire","appid"),
        api_key=configuration.get("MediaFire","sessionkey"))
    client.download_file("mf:/" + filename, dest)

    configuration.set("DownloadSite","current_version",str(version))
    configuration.set("DownloadSite","client_path",dest)
    configuration.save()
    return



def horse_json_handler(*args, **kwargs):
    value = cherrypy.serving.request._json_inner_handler(*args, **kwargs)
    # print("horse_json_handler --------------------------- ")
    # print(value)
    # print(type(value['result']['activity'][0]))
    # print(isinstance(value['result']['activity'][0], (list, tuple)))

    # In cherrypy, they seem to prefer iterencode (but from what I
    # understand, this pays off only for big serialisations)
    # cherrypy needs bytes

    return horse_json_encoder.encode(value).encode('utf-8')



class HorseWebServer(object):

    @cherrypy.expose
    def default(self,attr='abc'):
        message = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
  "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html><head>
<meta http-equiv="content-type" content="text/html; charset=UTF-8"><style>
p,h2 {text-align:center; font-family:Verdana; }
table, th, td { border: 1px solid #2900af; border-collapse:collapse; padding:0; margin:0; }
img {background-color:white;}
</style></head>

<body>
   <br/>
   <p><img src="logo.png"/></p>
   <br/>
   <table width="100%" height="1"><tr><td></td><tr/></table><br/><br/>
   <h2>This is the #NAME# download site !</h2>
<p>The current version is <b>{version}</b>.</p>
<p>To download the latest delivery_slips, <a href='/file'>click here</a>.</p>
<br/><br/><br/><br/>
<div style='color:grey'>
<p>#COPYRIGHT#</p>
<p>#LICENSE#</p>
</div>
</body></html>
""".replace("#COPYRIGHT#", copyright()).replace("#LICENSE#", license_short()).replace("#NAME#", configuration.get("Globals","name"))

        try:
            message = message.replace("{version}",configuration.get("DownloadSite","current_version"))
        except Exception as ex:
            pass

        return message


    @cherrypy.expose
    def upgrade(self, version):
        """
        :param version: Upgrades the delivery_slips to a specific version (higher or lower than current one.
        :return:
        """
        return upgrade_mediafire(version)

    #@cherrypy.expose
    #def upgrade(self, version, url):
    #    return upgrade_http(version, url,
    #                        configuration.get("Proxy","proxy_url"),
    #                        configuration.get("Proxy","proxy_port"))

    @cherrypy.expose
    def file(self):
        file_path = configuration.get("DownloadSite","client_path")

        if not file_path or not os.path.exists(file_path):
            msg = "I can't serve the file {} because it doesn't exist.".format(file_path)
            mainlog.error(msg)
            raise cherrypy.HTTPError(404, message=msg) # Won't create an exception

        # I don't inject at update time because if one copies
        # a delivery_slips in, then that delivery_slips must be injected as well.

        public_ip = configuration.get("DEFAULT","public_ip")

        if not public_ip:
            public_ip = guess_server_public_ip()
            mainlog.warn("Server configuration is borken : missing DEFAULT/public_ip. I'll default to what I guessed instead : {}".format(public_ip))

        inject_public_ip_in_client(public_ip)

        return cherrypy.lib.static.serve_download(file_path, name=configuration.get("Globals","codename") + '.zip')

    @cherrypy.expose
    def database(self):
        return configuration.get("Database","url")

    @cherrypy.expose
    def version(self):
        return configuration.get("DownloadSite","current_version")

    @cherrypy.expose
    def reload(self):
        # Browsers don't like that at all
        reload_config()


    @cherrypy.expose
    def remove_file(self, file_id):
        documents_service.delete(file_id)
        return

    @cherrypy.expose
    def instanciate_template(self, tpl_id):
        return str(documents_service.copy_template_to_document(tpl_id))

    @cherrypy.expose
    def download_file(self, file_id):
        doc = documents_service.find_by_id(file_id)
        path = documents_service.path_to_file(file_id)

        # FIXME I have the feeling that CherryPy transcode the
        # filenamne from utf-8 to iso-8859-1 (or CP-1252 which is alike)
        # Or is it somehitng akin to :(IETF, RFC 2183, section 2.3 :
        # Current [RFC 2045] grammar restricts parameter values (and
        # hence Content-Disposition filenames) to US-ASCII.
        # ???

        mainlog.debug(u"download_file : {}".format(doc.filename))
        return cherrypy.lib.static.serve_file(path, "application/x-download",
                                              "attachment", doc.filename)


    @cherrypy.expose
    def upload_file(self,file_id,description,uploaded_file):

        mainlog.warn("upload_file : DEPRECATED")
        # !!! Deprecated, use upload_file2 which is unicode safe


        # mainlog.debug("upload_file {} {} {}".format(file_id,description,uploaded_file))
        file_id = documents_service.save(int(file_id), uploaded_file.file, uploaded_file.filename, description)
        return str(file_id)

    @cherrypy.expose
    def upload_template_document(self,uploaded_file):
        # DEPRECATED !!!
        file_id = documents_service.save_template(uploaded_file.file, uploaded_file.filename)
        return str(file_id)

    @cherrypy.expose
    def upload_file2(self,file_id,description,encoding_safe_filename,uploaded_file):

        mainlog.warn("upload_file2 : DEPRECATED")
        # DEPRECATED

        # mainlog.debug(u"upload_file2 {} {} {}".format(file_id,description,uploaded_file))
        file_id = documents_service.save(int(file_id), uploaded_file.file, encoding_safe_filename, description)
        return str(file_id)


    @cherrypy.expose
    def upload_template_document2(self,encoding_safe_filename,uploaded_file):
        # DEPRECATED !!!
        file_id = documents_service.save_template(uploaded_file.file, encoding_safe_filename)
        return str(file_id)



    @cherrypy.expose
    def upload_file3(self, file_id, encoding_safe_filename, uploaded_file):
        assert int(file_id) == 0, "File replacement is not supported"
        # mainlog.debug(u"upload_file2 {} {} {}".format(file_id,description,uploaded_file))
        file_id = documents_service.save(int(file_id), uploaded_file.file, encoding_safe_filename, "")
        return str(file_id)



    @cherrypy.expose
    def upload_template_document3(self,encoding_safe_filename,doc_id,uploaded_file):
        """ Create or replace a new template document.

        :param encoding_safe_filename:
        :param uploaded_file:
        :param doc_id:
        :return:
        """

        mainlog.warn("upload_template_document3 : DEPRECATED")

        doc_id = int(doc_id)

        if doc_id == 0:
            mainlog.debug("upload_template_document3 : upload")
            file_id = documents_service.save_template(uploaded_file.file, encoding_safe_filename)
            return str(file_id)
        elif doc_id > 0:
            mainlog.debug("upload_template_document3 : replace  doc_id={}".format(doc_id))
            documents_service.replace_template(doc_id, uploaded_file.file, encoding_safe_filename)
            return


    @cherrypy.expose
    def upload_template_document4(self, file_id, encoding_safe_filename, uploaded_file):
        """ Create or replace a new template document.

        :param encoding_safe_filename:
        :param uploaded_file:
        :param doc_id:
        :return:
        """

        mainlog.debug("upload_template_document4")

        doc_id = int(file_id)

        if doc_id == 0:
            mainlog.debug("upload_template_document4 : upload")
            doc_id = documents_service.save_template(uploaded_file.file, encoding_safe_filename)
        elif doc_id > 0:
            mainlog.debug("upload_template_document4 : replace  doc_id={}".format(doc_id))
            doc_id = documents_service.replace_template(doc_id, uploaded_file.file, encoding_safe_filename)

        return str(doc_id)



    @cherrypy.expose
    @cherrypy.tools.json_in() # processor = ... my own json -> jsonable stuff
    @cherrypy.tools.json_out()
    def json_rpc3(self):
        chrono_start()
        r = services.rpc_dispatcher( cherrypy.request.json)
        chrono_click()
        return r

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def json_rpc2(self):
        chrono_start()
        try:
            mainlog.debug("Dispatching JSON call {}".format(cherrypy.request.json))
            result = json_rpc_dispatcher(cherrypy.request.json)
            # mainlog.debug("... success! Result is {}".format(str(result)))
            # Normally, exception handling is worked ou in the JsonRpc handler and
            # not in cherrypy

        except ServerException as ex:
            mainlog.error("Intercepted error ?")
            mainlog.error(cherrypy.request.json)
            mainlog.exception(u"[{}] {}".format(ex.code, ex.msg))
            raise ex
        except Exception as ex:
            mainlog.error(cherrypy.request.json)
            mainlog.exception(ex)
            raise ex
        chrono_click()
        return result

    # @cherrypy.expose
    # def json_rpc(self,params, jsonrpc, method, id):
    #     mainlog.debug("JSOOOOOOOOOOOOOOOOOOOOON")
    #     cl = cherrypy.request.headers['Content-Length']
    #     rawbody = cherrypy.request.body.read(int(cl))

    #     print(rawbody)
    #     print(params, jsonrpc, method, id)
    #     return ""

    #     result = jsonrpc_dispatcher(loads(raw_body))

    #     # print(loads(query))
    #     # print("-------------------------")
    #     # print(result)
    #     return dumps(result, default=json_serial)


def set_default_document_root( configuration):

    if configuration.is_set("DocumentsDatabase","documents_root"):
        d = configuration.get("DocumentsDatabase","documents_root")
    else:
        d = None

    config_needs_update = False

    if not d:
        d = os.path.join(get_data_dir(), "documents")
        config_needs_update = True

    if not os.path.exists(d):
        os.mkdir(d)

    if not os.path.isdir(d):
        raise Exception("The path {} should be a directory".format(d))

    if config_needs_update:
        configuration.set("DocumentsDatabase","documents_root",d)
        configuration.save()
        return True



def configure_server():
    mainlog.info("Configuring the server")
    # 'server.socket_host': '64.72.221.48',

    # Bind to all local addresses => Might be a security concern
    # But that way I don't have to look explicitly for an address
    # to bind to (and so this service is available outside localhost)
    cherrypy.config.update({ 'server.socket_host': configuration.get('DownloadSite','host')})
    cherrypy.config.update({ 'server.socket_port': configuration.get('DownloadSite','port') })

    # The auto reload thing is super dangerous in production. for example If one updates
    # a python file that cherrypy relies on via aptitude, then cherrypy tries to respawn
    # and that fails with my package set up !!!
    # It is also problematic when running as a Windows service

    cherrypy.config.update({ 'engine.autoreload.on': False })

    cherrypy.config.update({ "tools.encode.on" : True })
    cherrypy.config.update({ "tools.encode.encoding" :"utf-8"})

    # cherrypy.tools.jsonify = cherrypy.Tool('before_finalize', jsonify_tool_callback, priority=30)
    cherrypy.config.update({ "tools.json_out.handler" : horse_json_handler})


    # Specific for Windows service
    cherrypy.config.update({
        'global':{
            'log.screen': False,
            'engine.autoreload.on': False,
            'engine.SIGHUP': None,
            'engine.SIGTERM': None
            }
        })

    # Static content requires absolute path
    conf = {

        '/logo.png': {
            "tools.staticfile.on" : True,
            "tools.staticfile.filename" : os.path.abspath(os.path.join(resource_dir,"file_server_logo.png"))
            }
        }

    mainlog.debug("/logo.png will be found in {}".format(conf['/logo.png']['tools.staticfile.filename']))
    application = cherrypy.tree.mount(HorseWebServer(), '', conf)

    cherrypy.log.screen = False
    cherrypy.log.access_log = mainlog
    cherrypy.log.error_log = mainlog

    application.log.screen = False
    application.log.access_log = mainlog
    application.log.error_log = mainlog

    d = configuration.get("DocumentsDatabase","documents_root")
    config_needs_update = False

    if not d:
        d = os.path.join(get_data_dir(), "documents")
        config_needs_update = True

    if not os.path.exists(d):
        os.mkdir(d)

    if not os.path.isdir(d):
        raise Exception("The path {} should be a directory".format(d))

    if config_needs_update:
        mainlog.debug("Updating the configuration file")
        configuration.set("DocumentsDatabase","documents_root",d)
        configuration.save()

    # import sys
    # from PySide.QtGui import QApplication
    # app = QApplication(sys.argv)
    mainlog.info("Done configuration")

def start_server():
    mainlog.info("Starting the server")
    cherrypy.engine.start()
    cherrypy.engine.block()

def reload_config():
    disconnect_db()
    base_init()
    configure_server()
    cherrypy.engine.restart()
    cherrypy.engine.block()


# import win32serviceutil
# import win32service
# import win32event
# import servicemanager
#
# class MyService(win32serviceutil.ServiceFramework):
#     """NT Service, for Cx_freeze """
#
#     _svc_name_ = "HorseService"
#     _svc_display_name_ = "Horse Service"
#
#     def __init__(self, args):
#         win32serviceutil.ServiceFramework.__init__(self, args)
#         # create an event that SvcDoRun can wait on and SvcStop
#         # can set.
#         self.stop_event = win32event.CreateEvent(None, 0, 0, None)
#         configure_server()
#
#     def SvcStop(self):
#         self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
#         cherrypy.engine.exit()
#
#         self.ReportServiceStatus(win32service.SERVICE_STOPPED)
#         # very important for use with py2exe (I know, we work on
#         # cx_freeze, but well, I copy/pasted this from the web...)
#         # otherwise the Service Controller never knows that it is stopped !
#
#
#     def SvcDoRun(self):
#         self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
#         servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
#                               servicemanager.PYS_SERVICE_STARTED,
#                               (self._svc_name_,''))
#
#         start_server()
#
#
# import argparse
# parser = argparse.ArgumentParser(description='This is Horse! Here are the command line arguments you can use :')
# parser.add_argument('--install', default=False, help='Install as a service')
#
# args = parser.parse_args()
#
# if __name__ == '__main__':
#     win32serviceutil.HandleCommandLine(MyService)
#
# # if args.install:
# #     print("Unable to register the Horse server as a Windows service")
# #     mainlog.error("--install parameter not supported yet")
# #     exit()
#
#
#

def init_configuration():
    p = path_to_config("server.cfg")
    if not os.path.exists(p) :
        ps = os.path.join( resource_dir, "server_config_check.cfg")
        if os.path.exists(ps) :
            make_empty_configuration_file(p, ps)
            load_configuration_server( p, ps)

            configuration.set_server_network_address(ip_or_host=guess_server_url(), port=8079, overwrite=True)

            set_default_document_root(configuration)
            configuration.save()
            mainlog.info("Configuration file created at {}".format(p))
            return True
        else:
            mainlog.error("Can't find the specification configuration file, there : {}".format(ps))
            return False
    else:
        mainlog.error("Can't initialize configuration file because it already exists, there : {}".format(p))
        return False


from koi.datalayer.create_database import create_blank_database


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='This is the server for Koi!')
    parser.add_argument('--make-config', action='store_const', const=True, help='Make a blank configuration file.')
    parser.add_argument('--reset-database', action='store_const', const=True, help='Reset the database and returns.')
    parser.add_argument('--restore-backup', help='Restore a backup from the given directory.')
    parser.add_argument('--load-client', help='Loads a packaged client in the server (the server needs to be restarted afterwards)')
    parser.add_argument('--demo-database', action='store',
                        type=int,
                        help='Creates a DB filled with dummy data that shows {} features. The value is the number of orders to create in that database.'.format(codename),
                        metavar="NB_ORDERS")
    parser.add_argument('--reset-root', action='store_const', const=True, help='Resets the root account to admin/admin'.format(codename))
    parser.add_argument('--debug', action='store_const', const=True, help='Activate debug logging'.format(codename))

    args = parser.parse_args()

    if args.debug:
        mainlog.setLevel(logging.DEBUG)
    else:
        mainlog.setLevel(logging.INFO)

    if args.make_config:
        if init_configuration():
            exit(0)
        else:
            exit(-1)


    p = path_to_config("server.cfg")
    if os.path.exists(p):
        load_configuration_server( p, "server_config_check.cfg")
    else:
        mainlog.error("Configuration file not found (looked here : {}). You should use --make-config.".format(p))
        exit(-1)

    if args.demo_database:
        mainlog.warn("Creating a demonstration database with {} orders ! This will destroy the current database.".format(args.demo_database))
        create_demo_database(args.demo_database)
        exit(0)

    if args.reset_database:
        try:
            create_blank_database(configuration.get("Database","admin_url"), configuration.get("Database","url"))
            exit(0)
        except Exception as ex:
            mainlog.exception(ex)
            exit(-1)
    elif args.restore_backup:
        try:

            base, filename = os.path.split(args.restore_backup)

            if filename:
                filename = os.path.join(base, filename)

            full_restore(configuration, base, filename, True, mainlog)
            exit(0)
        except Exception as ex:
            mainlog.exception(ex)
            exit(-1)


    if args.load_client:
        if upgrade_file(args.load_client):
            exit(0)
        else:
            exit(-1)

    base_init()

    if args.reset_root:
        mainlog.info("Resetting the database root account")
        create_root_account()
        exit(-1)

    configure_server()
    start_server()
