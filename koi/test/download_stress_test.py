from multiprocessing import Process,Pool
import os
import sys


import sys
if sys.version[0] == "2":
    from httplib import HTTPConnection,BadStatusLine
else:
    from http.client import HTTPConnection,BadStatusLine

from koi.download_version import get_server_version, download_file

from koi.Configurator import init_i18n,load_configuration,resource_dir
from koi.base_logging import mainlog
mainlog.debug(u"Test resource dir is {}".format(resource_dir))
load_configuration(os.path.abspath( os.path.join( resource_dir,'test_config.cfg')))
from koi.Configurator import configuration


from koi.doc_manager.client_utils import download_document, upload_document

def upload_download(pid):
    for i in range(100):
        print("[{}] {}".format(pid,i))

        # Download the client version
        next_version = get_server_version(configuration.update_url_version) # available on the server (abd maybe already downloaded)

        # Download the client
        tmpfile = r"c:\temp\test_{}.tst".format(pid)
        # download_file(configuration.update_url_file,tmpfile)

        # Upload a document
        n = r"c:\temp\test_{}_{}.tst".format(pid,i)
        fh = open(n,'w')
        fh.write(n)
        fh.close()

        doc_id = 0
        try:
            doc_id = upload_document(n)
        except BadStatusLine as ex:
            print("upload")
            print(doc_id)
            print( ex.__dir__())
            raise ex

        df = None
        try:
            df = download_document(doc_id) # sys.executable
        except BadStatusLine as ex:
            print("download")
            print(doc_id)
            print( ex.__dir__())
            raise ex

        fh = open(df,'r')
        t = fh.read(1000)
        fh.close()

        assert t == n

if __name__ == "__main__":
    # Here we use processes, but cherrypy uses threads...
    # When we use threading, the log might have issues
    # because we concurrently access the same log file
    # So we don't use the log files

    nb_processes = 3
    pool = Pool(processes=nb_processes)
    pool.map_async(upload_download,list(range(nb_processes))).get()
