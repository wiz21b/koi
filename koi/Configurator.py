# -*- coding: utf-8 -*-

import locale
import sys
import os
import platform
import gettext
import time
import logging
import ipaddress
import shutil
import socket
from urllib.request import urlopen

from distutils.version import StrictVersion

# from ConfigParser import SafeConfigParser

# These two must be made available to Python
from koi.configobj import configobj
import validate

from koi.base_logging import mainlog,get_data_dir
from koi.server.net_tools import string_represents_ip_address

from koi.as_unicorn import codename
from koi.server.net_tools import guess_server_public_ip


if sys.platform == 'win32':
    from win32com.shell import shell, shellcon

BASE_PACKAGE = 'koi'

class Configuration(object):
    def __init__(self):
        self.backup_configuration = None
        pass

    @property
    def font_select(self):
        return self.base_configuration['User interface']['font_select']

    @font_select.setter
    def font_select(self,b):
        self.base_configuration['User interface']['font_select'] = b

    @property
    def database_url(self):
        return self.get('Database','url')

    @database_url.setter
    def database_url(self,url):
        self.base_configuration['Database']['url'] = url

    @property
    def echo_query(self):
        return self.base_configuration["Database"]["echo_query"]

    @property
    def recreate_table(self):
        return self.base_configuration["Database"]["recreate_table"]

    @property
    def update_url_version(self):
        return self.get("DownloadSite","base_url") + "/version"

    @property
    def database_url_source(self):
        return self.get("DownloadSite","base_url") + "/database"

    @property
    def update_url_file(self):
        return self.get("DownloadSite","url_file")

    def is_set(self, section, tag):
        # Pay attention ! If the key is not found in the configuration, configobj will
        # look at the default value in the spec.
        if section in self.base_configuration and tag in self.base_configuration[section] and self.base_configuration[section][tag]:
            # mainlog.debug(u"Found tag {}/{} in config file -> {}".format(section,tag,self.base_configuration[section][tag]))
            return True
        else:
            return False

    def get(self, section, tag):
        # Pay attention ! If the key is not found in the configuration, configobj will
        # look at the default value in the spec.
        if section in self.base_configuration and tag in self.base_configuration[section] and self.base_configuration[section][tag]:
            # mainlog.debug(u"Found tag {}/{} in config file -> {}".format(section,tag,self.base_configuration[section][tag]))
            return self.base_configuration[section][tag]
        else:
            mainlog.warning("Could not find tag {}/{} in config file (or it has dubious empty value). Trying embedded config file.".format(section,tag))
            if self.backup_configuration and section in self.backup_configuration and tag in self.backup_configuration[section]:
                return self.backup_configuration[section][tag]
            else:
                mainlog.error("Could not find tag {}/{} in config file nor in embedded config file. Defaulting to None".format(section,tag))
                return None

    def set(self,section,tag,value):
        if section not in self.base_configuration:
            self.base_configuration[section] = dict()

        self.base_configuration[section][tag] = value

    def clear(self,section,tag):
        if self.is_set( section, tag):
            self.base_configuration[section].remove(tag)


    def load_backup(self,config_path,config_spec):
        self.backup_configuration = configobj.ConfigObj(infile=config_path,configspec=config_spec,encoding='utf-8')


    def load_version(self):
        try:
            f = open(os.path.join(resource_dir, "package_version"))
            v = f.read().strip()
            f.close()
            self.this_version = StrictVersion(v)
            mainlog.debug("Located version file in {}, version is {}".format(resource_dir,self.this_version))
        except:
            mainlog.error("Could not find the package_version file in {}".format(resource_dir))
            self.this_version = StrictVersion("1.0.0")

    def set_server_network_address(self, ip_or_host, port=443, overwrite=False):

        # actual_ip = None
        # try:
        #     actual_ip = ipaddress.ip_address(ip)
        # except Exception as ex:
        #     raise Exception(_("Invalid IP address : {}").format(ip))

        if port == 443:
            protocol = 'https'
        else:
            protocol = 'http'

        base = "{}://{}:{}".format(protocol, ip_or_host, port)
        mainlog.info("Server base address is {}.".format(base))

        if overwrite or not self.get("DownloadSite", "url_version"):
            self.set("DownloadSite", "url_version", base + "/version")
        else:
            mainlog.debug("Leaving url_version as it is")

        if overwrite or not self.get("DownloadSite", "base_url"):
            self.set("DownloadSite", "base_url", base)
        else:
            mainlog.debug("Leaving base_url as it is")

        if overwrite or not self.get("DownloadSite", "url_file"):
            self.set("DownloadSite", "url_file",    base + "/file")
        else:
            mainlog.debug("Leaving url_file as it is")

    def load_database_param(self):

        # This will raise exceptions if connection fails.

        url = self.database_url_source
        mainlog.debug("Loading DB connection string from server at '{}'".format(url))
        response = urlopen(url, timeout=5)
        db_url = response.read().decode('ascii')
        mainlog.debug("Connection string is ({})".format(db_url))

        if ',' in db_url:
            db_url = db_url.split(',')

        if db_url != self.base_configuration['Database']['url']:
            mainlog.debug("Replacing old DB url")
            # The DB url advertised by the server always takes
            # priority

            self.base_configuration['Database']['url'] = db_url
            mainlog.info("The DB url has changed, so I save it locally.")
            self.save()

    def load_network_param(self):
        """ Load the network parameters. The priority is the config file first,
        then, if empty or not properly filled in, we guess it for net.cfg.
        This is for the delivery_slips side.
        :return:
        """

        ip_address = None
        try:
            f = open(os.path.join(resource_dir, "net.cfg"))
            ip_address = f.read().strip()
            f.close()
        except Exception as ex:
            mainlog.warn("net.cfg file not found, using current configuration")
            return

        # if string_represents_ip_address(ip_address):
        mainlog.debug("net.cfg file was read. Server is there : {}".format(ip_address))

        if ":" in ip_address:
            host, port = ip_address.split(":")
            port = int(port)
            mainlog.debug("Address has port : {}:{}".format(host, port))
            self.set_server_network_address(host, port, overwrite=False)
        else:
            self.set_server_network_address(ip_address, overwrite=False)

        # else:
        #     mainlog.error("net.cfg content seems bad, it is : {}. I'm ignoring it".format(ip_address))


    # def _load_embedded_public_ip(self):
    #   ndx = 0
    #   url = None
    #   while True:
    #     f = None
    #     try:
    #       f = open(os.path.join(resource_dir, "web_server_url_"+str(ndx)))
    #       url = f.read().strip()
    #       f.close()
    #     except IOError,ex:
    #       break
    #   return url


    def reload(self):
        self.load(self._config_file, self._config_spec)

    def load_from_spec(self, config_path, config_spec):
        self._config_file = config_path
        self._config_spec = config_spec
        self.base_configuration = configobj.ConfigObj( configspec=config_spec, encoding='utf-8')


    def load_server_configuration(self):

        config_spec = os.path.join( resource_dir, "server_config_check.cfg")

        data_dir = os.path.join( shell.SHGetFolderPath(0, shellcon.CSIDL_COMMON_APPDATA, 0, 0),
                                 codename)
        config_file = os.path.join(data_dir, 'server.cfg')

        if not os.path.exists(os.path.join(data_dir)):
            os.mkdir(data_dir)

        if not os.path.exists(os.path.join(config_file)):
            self.base_configuration = configobj.ConfigObj( encoding='utf-8')

            self.base_configuration['Database'] = {}
            self.base_configuration['Database']['url'] = 'postgresql://horse_clt:HorseAxxess@{}:5432/horsedb'.format(guess_server_public_ip())
            self.base_configuration['Database']['admin_url'] = 'postgresql://horse_clt:HorseAxxess@localhost:5432/horsedb'
            self.base_configuration.filename = config_file
            self.base_configuration.write()

        self.load(config_file, config_spec)




    def load(self, config_path, config_spec):
        self._config_file = config_path
        self._config_spec = config_spec

        config_path = os.path.normpath(os.path.join(os.getcwd(),config_path))

        mainlog.info("Reading configuration file -> {}".format(config_path))
        mainlog.debug("Reading configuration spec file -> {}".format(config_spec))

        if not os.path.exists(config_path):
            mainlog.error("Configuration file not found at {}".format(config_path))
            raise Exception("Configuration file not found at {}".format(config_path))

        try:
            self.base_configuration = configobj.ConfigObj(infile=config_path,
                                                          configspec=config_spec,
                                                          encoding='utf-8')
        except UnicodeDecodeError:
            mainlog.warn("The encoding of the config file is not UTF-8. I'll try {}".format(locale.getpreferredencoding()))
            self.base_configuration = configobj.ConfigObj(infile=config_path,
                                                          configspec=config_spec,
                                                          encoding=locale.getpreferredencoding())

        self.base_configuration.validate(validate.Validator())

        if 'Programs' not in self.base_configuration or 'pdf_viewer' not in self.base_configuration['Programs'] or not self.base_configuration['Programs']['pdf_viewer'] or not os.path.exists(self.base_configuration['Programs']['pdf_viewer']):

            if platform.system() == 'Linux':
                self.base_configuration['Programs']['pdf_viewer'] = 'xpdf'
            else:
                self.base_configuration['Programs']['pdf_viewer'] = os.path.join(resource_dir,'SumatraPDF.exe')


                # self._load_web_server_source()

    def save(self):
        mainlog.debug("Saving configuration in {}".format(self.base_configuration.filename))
        self.base_configuration.write()
        mainlog.debug("Configuration saved")


def package_dir():

    try:

        # When PyInstaller builds a one-file EXE,
        # it creates a temp folder and stores path in _MEIPASS2

        return sys._MEIPASS

    except AttributeError:
        # mainlog.debug("Failed MEIPASS")

        if getattr(sys, 'frozen', False):
            # PyInstaller multifile package
            return os.path.dirname(sys.executable)
        elif not getattr(sys, 'frozen', False):
            # Not in PyInstaller package
            d = os.path.join( os.path.dirname(__file__))
            # mainlog.debug("Python execution => package dir base is {}".format(d))
            return d
        else:
            raise Exception("Can't figure out the base bath")



def init_i18n( locale_txt=None):
    import locale

    path = os.path.join( package_dir(), 'resources', 'i18n')

    if not locale_txt:
        locale_txt = locale.getdefaultlocale()
        locale_txt = "fr_FR" # hardcoded to french

    # mainlog.debug("Chosen language is {}. Path to i18n data is : {}".format(locale_txt, str(path)))
    language = locale_txt.split('_')[0]
    lang1 = gettext.translation('all_messages',path,languages=[language],fallback=True)
    lang1.install()


def path_to_config( config_file):
    if os.path.isabs(config_file):
        return config_file
    else:
        return os.path.join(get_data_dir(), config_file)

def configuration_file_exists( config_file):
    p = path_to_config(config_file)

    if os.path.exists(p):
        return p
    else:
        return False

def load_configuration_server(config_file = None, config_spec = 'server_config_check.cfg'):
    p = path_to_config(config_file)

    if os.path.exists(p):
        configuration.load_version()
        configuration.load( p, os.path.join( resource_dir, config_spec))
    else:
        raise Exception("Unable to load configuration file at {} because it doesn't exist.".format(p))

def create_blank_configuration( config_spec):
    global configuration
    spec = os.path.join( resource_dir, config_spec)


def load_configuration(config_file = None, config_spec = 'config-check.cfg'):
    """ Figure out the configuration by all possible means.

    :param config_file:
    :param config_spec:
    :return:
    """
    # The spec file is always loaded from the resource directory
    global configuration

    mainlog.debug("load_configuration : config_file is {}".format(config_file))
    spec = os.path.join( resource_dir, config_spec)
    configuration.load_version()

    if config_file:
        p = path_to_config(config_file)

        if not os.path.exists(p):
            shutil.copy(os.path.join( resource_dir,'config.cfg'), os.path.join(get_data_dir(), 'config.cfg'))

        configuration.load(p, spec)
    else:
        if not os.path.exists(get_data_dir()):
            os.mkdir(get_data_dir())

        if not os.path.exists(os.path.join(get_data_dir(), 'config.cfg')):
            mainlog.info("Creating a default configuration file")
            shutil.copy(os.path.join( resource_dir,'config.cfg'), os.path.join(get_data_dir(), 'config.cfg'))

        configuration.load(os.path.join(get_data_dir(), 'config.cfg'), spec)
        mainlog.debug("Loading backup configuration")
        configuration.load_backup(os.path.join( resource_dir,'config.cfg'), spec)

        configuration.load_network_param()

    mainlog.debug("Done with load configuration")



def make_empty_configuration_file( dest_path, spec_path):
    cfg = configobj.ConfigObj(create_empty=True,
                              configspec=spec_path,
                              default_encoding = 'utf-8')

    # Make sure the default values are copied
    cfg.validate( validate.Validator(), copy=True)

    mainlog.info("Writing configuration file {}".format(dest_path))
    with open( dest_path, mode="wb") as out_file:
        cfg.write( out_file)




def guess_server_url():

    try:
        # First we look for the URL of this server, assuming
        # it is visible on the internet

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('google.com', 0))
        return socket.gethostbyaddr(s.getsockname()[0])[0]
    except Exception as ex:
        return "127.0.0.1"


resource_dir = os.path.join( package_dir(), 'resources')
configuration = Configuration()


__all__ = ['resource_dir', 'configuration']


if __name__ == "__main__":
    mainlog.info("Resource dir : {}".format(resource_dir))
    init_i18n()
    load_configuration()
    mainlog.info("Config dir : {}".format(get_data_dir()))
