import platform

RETURN_CODE_SUCCESS = 65

if platform.system() == 'Windows':
    import win32api
    import win32con

import subprocess
import traceback
import sys

from urllib.request import urlopen

import os
import tempfile
from distutils.version import StrictVersion
from zipfile import ZipFile
import shutil
import time
import re


from koi.Configurator import mainlog,configuration,get_data_dir,resource_dir
from koi.utils import download_file, make_temp_file



def extractAll(zipName,tmp_dir = ""):
    mainlog.info("Unzipping {} to {}".format(zipName, tmp_dir))

    z = ZipFile(zipName)
    for f in z.namelist():
        dest = os.path.join(tmp_dir,f.replace('/',os.sep))
        if f.endswith('/'):
            os.makedirs(dest)
        else:
            z.extract(f,tmp_dir)


def get_server_version(url_version):
    try:
        response = urlopen(url_version,timeout=5)
        html = response.read().decode('ascii')
        version = StrictVersion(html.strip())
        mainlog.debug("Version advertised by server : {}".format(str(version)))
        return version
    except Exception as e:
        mainlog.error("I was unable to get the version from server {}".format(url_version))
        mainlog.error(e)
        return None

def get_current_dir():
    current_dir = None
    if getattr(sys, 'frozen', False):
        mainlog.debug("I'm frozen")
        # Handle PyInstaller situation
        return os.path.dirname(sys.executable)
    elif __file__:
        return os.path.dirname(__file__)


def find_highest_installed_version():

    codename = configuration.get("Globals","codename")

    mainlog.debug("Looking for new version of '{}' in {}".format( codename, get_data_dir()))

    select = re.compile(codename + r'-([0-9]+\.[0-9]+\.[0-9]+)$')

    highest_version = None

    for dirname in os.listdir(get_data_dir()):
        res = select.match(dirname)
        if res:
            d = os.path.join(get_data_dir(), dirname)
            if os.path.isdir(d):
                version = StrictVersion(res.group(1))
                if not highest_version or version > highest_version:
                    highest_version = version

    return highest_version


def version_to_str(version):
    if version.version[2] == 0:
        return str(version) + ".0"
    else:
        return str(version)

def upgrade_process( args):
    if platform.system() != 'Windows':
        mainlog.info("The upgrade process won't work on something else than Windows... I skip that.")
        return


    this_version = configuration.this_version # the one of this very code
    mainlog.debug("Client version is {}".format(this_version))

    if args.no_update:
        mainlog.info("Skipping update process because --no-update is set")

        # This is rather strange. If we are started by regular Windows ways
        # (double click, cmd,...) PySide finds its DLL fine.
        # But, if it is started through the upgrade process (via Popen), then
        # it doesn't because Windows can't expand junction points correctly
        # (according to what I saw, this is not a bug in windows, but rather a
        # feature to prevent old code to misuse junction points)
        # So, for this code to work, one has to make sure that _setupQtDir
        # is not called during the import but right after (else it crashes).

        # This is how to patch the __init__py of PySide :

        # def _setupQtDirectories(zedir=None):
        #     import sys
        #     import os
        #     from . import _utils
        #
        #     if zedir:
        #         pysideDir = zedir
        #     else:
        #         pysideDir = _utils.get_pyside_dir()
        #

        try:
            from PySide import _setupQtDirectories
        except Exception as ex:
            mainlog.error("Unable to import _setupQtDirectories. Remember this was a bug fix, make sure "
                          + "_setupQtDirectories is not called at the end of the __init__.py of pyside. "
                          + "Check the comments in the code for more info.")
            mainlog.exception(ex)
            return

        if getattr(sys, 'frozen', False):
            # Frozen
            mainlog.debug("Fixing Qt import on frozen exe {}".format(os.path.normpath(os.getcwd())))
            _setupQtDirectories(os.path.normpath(os.getcwd()) )
        else:
            mainlog.debug("Fixed Qt import on NON frozen exe")
            _setupQtDirectories()

        return

    next_version = get_server_version( configuration.update_url_version ) # available on the server (abd maybe already downloaded)
    current_version = find_highest_installed_version() # one we have downloaded in the past

    mainlog.info("This version is {}, last downloaded version = {}, version available on server = {}".format(this_version,current_version, next_version))

    if (not current_version or (current_version and this_version >= current_version)) and \
            (not next_version or (next_version and this_version >= next_version)):
        mainlog.info("The available versions are not more recent than the current one. No update necessary.")
        return

    codename = configuration.get("Globals","codename")

    # Update only if we have no current version or if the
    # next version is higher than ours

    if next_version and (not current_version or next_version > current_version):

        try:
            tmpfile = make_temp_file(prefix='NewVersion_'+version_to_str(next_version), extension='.zip')
            download_file( configuration.update_url_file, tmpfile)

            newdir = os.path.join(get_data_dir(), "{}-{}".format(codename, version_to_str(next_version)))
            extractAll(tmpfile,newdir)

            # show that we actually downloaded something
            current_version = next_version
        except Exception as ex:
            mainlog.error("The download of version {} failed. Therefore, I'll go on with the current one.".format(next_version))
            mainlog.exception(ex)

    # If we were able to download a version now or in the
    # past, then use this one. If not, then we run the
    # program (that is, the version that was installed
    # by the user)

    if current_version:
        current_dir = os.path.join(get_data_dir(), "{}-{}".format(codename, version_to_str(current_version)))

        # --no-update "signals" the control transfer (without it we'd
        # try to update with the latest version again creating an
        # endless loop)

        # os.chdir(os.path.join(current_dir,codename)) # FIXME Not sure this is useful; too tired to test
        cmd = [ os.path.join(os.path.join(current_dir,codename), codename + '.exe'), '--no-update']
        mainlog.info("Transferring control to {}".format( ' '.join(cmd)))

        # DETACHED_PROCESS = 0x00000008
        # CREATE_NEW_PROCESS_GROUP = 0x00000200
        # subprocess.Popen( cmd,cwd=os.path.join(current_dir,'xxx'),creationflags=DETACHED_PROCESS|CREATE_NEW_PROCESS_GROUP)

        # From what I can see WinExec don't run in os.getcwd(), so I give it an absolute path.

        try:
            # win32api.WinExec will *NOT* block. The new version is run
            # in parallel. This allow us to quit so we don't have two
            # instances of Koi running simulatenaously

            # Unfortunaately, because of that it's hard to build a watch
            # dog that will protect us against a broken upgrade.
            # For example, we'd have to release our log files...

            res = win32api.WinExec(" ".join(cmd),win32con.SW_SHOWMAXIMIZED)
            sys.exit(RETURN_CODE_SUCCESS)

        except Exception as ex:
            mainlog.error("Control transfer failed. There was an error while starting the newer version {}".format(current_version))
            mainlog.exception(ex)
            return False


if __name__ == "__main__":
    from koi.base_logging import init_logging
    from koi.Configurator import load_configuration
    init_logging()
    load_configuration()
    upgrade_process()
