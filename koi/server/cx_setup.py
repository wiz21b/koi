import sys
import os
from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need fine tuning.
#build_exe_options = {"packages": ["os"], "excludes": ["tkinter"]}


BASE_DIR=None
try:
    # will be et by my release scripts
    BASE_DIR = os.environ['TMP_HOME'] # r'\PORT-STCA2\pl-PRIVATE\horse'
except:
    BASE_DIR = os.path.join( r'\Users\stefan\horse\horse')
    BASE_DIR = os.path.join( r'\PORT-STCA2\PL-Private\horse')

print("------------------------------------------------------XXX {}".format(BASE_DIR))

RESOURCE_DIR=os.path.join(BASE_DIR,"resources")


# GUI applications require a different base on Windows (the default is for a
# console application).
base = None
# if sys.platform == "win32":
#     base = "Win32GUI"
base = "Win32Service"

# Grab the koi directory (to get Logging, Configurator,...)
# FIXME rather fragile...
sys.path.append( os.path.join(os.path.abspath(__file__),'..','..') )

options = {
    'build_exe': {
        'includes': ['horse_server','cx_Logging','Logging','_winreg'],
        'include_files' : [ (os.path.join(RESOURCE_DIR,'package_version'),'resources/package_version'),
                            (os.path.join(RESOURCE_DIR,'file_server_logo.png'),'resources/file_server_logo.png'),
                            (os.path.join(RESOURCE_DIR,'server_config_check.cfg'),'resources/server_config_check.cfg')] 
    }
}

setup(  name = "HorseWindowsService",
        version = "0.1",
        description = "Horse server",
        options = options,
        executables = [Executable(os.path.join(BASE_DIR,"koi","server","cx_server_config.py"), base=base, targetName='horse_server.exe')])

