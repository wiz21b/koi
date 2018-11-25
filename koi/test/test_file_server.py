import urllib.request, urllib.error, urllib.parse

from koi.base_logging import init_logging,mainlog,horse_dir,log_stacktrace
init_logging("file_server.log")
from Configurator import load_configuration,init_i18n,configuration,resource_dir
load_configuration("server.cfg","server_config_check.cfg")


if __name__ == "__main__":

    base_url = "http://localhost:{}".format(configuration.get("DownloadSite","port"))

    mainlog.info("Testing {}".format(base_url))

    response = urllib.request.urlopen(base_url)
    if "This is the Horse download site !" not in response.read():
        mainlog.error("Can't see homepage")
    else:
        mainlog.info("Homepage OK")


    response = urllib.request.urlopen(base_url + "/database")
    mainlog.info("Database = " + response.read())


    response = urllib.request.urlopen(base_url + "/version")
    mainlog.info("Version = " + response.read())


    response = urllib.request.urlopen(base_url + "/file")


    mainlog.info("Client file = {} ".format(response.info().headers[4].strip()))
    mainlog.info("Client file = {} bytes".format(len(response.read())))
