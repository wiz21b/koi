__author__ = 'stc'


import zipfile
import tempfile
import os
from koi.base_logging import mainlog
from koi.Configurator import configuration


def config_file():
    return configuration.get('Globals','codename') + '/resources/net.cfg'

def _updateZip(zip_path, filename, data):

    mainlog.info("Injecting into file {} located in zip {}. Data to inject is {}.".format(filename, zip_path, data))
    needs_replace = False

    with zipfile.ZipFile(zip_path, 'r') as zin:
        for item in zin.infolist():
            if item.filename == filename:

                data_in = zin.read(item.filename).decode('ascii')

                if data == data_in:
                    mainlog.info("good data already in file, nothing to do")
                    return
                else:
                    mainlog.info("File is there but its content doesn't match data")
                    needs_replace = True
                    break


    if needs_replace:
        mainlog.info("Copying zip file without the file")
        # generate a temp file
        tmpfd, tmpname = tempfile.mkstemp(dir=os.path.dirname(zip_path))
        os.close(tmpfd)

        # create a temp copy of the archive without filename
        with zipfile.ZipFile(zip_path, 'r') as zin:
            with zipfile.ZipFile(tmpname, 'w') as zout:
                zout.comment = zin.comment # preserve the comment
                for item in zin.infolist():
                    if item.filename != filename:
                        zout.writestr(item, zin.read(item.filename))

        # replace with the temp archive
        os.remove(zip_path)
        os.rename(tmpname, zip_path)

    mainlog.info("append filename with its new data")
    with zipfile.ZipFile(zip_path, mode='a', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(filename, data)


def load_public_ip():
    with zipfile.ZipFile(configuration.get("DownloadSite","client_path"), 'r') as zin:
        for item in zin.infolist():
            if item.filename == config_file():

                public_ip = zin.read(item.filename).decode('ascii')
                return public_ip

def inject_public_ip_in_client(public_ip):
    _updateZip(configuration.get("DownloadSite","client_path"),
               filename = config_file(),
               data=str(public_ip))

