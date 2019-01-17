import sys
import os
from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need fine tuning.
# FIXME Is this actually used ?
build_exe_options = {"packages": ["_json"],
                     "excludes": ["tkinter"] }


if 'TMP_HOME' in os.environ:
    # will be set by my release scripts
    BASE_DIR = os.environ['TMP_HOME']
else:
    # We're under tools, we go up a level
    BASE_DIR = os.path.join( os.getcwd(), os.path.dirname(__file__), '..')


if 'VERSION' in os.environ:
    koi_version = os.environ['VERSION']
else:
    koi_version = '1.0.0'

# GUI applications require a different base on Windows (the default is for a
# console application).
GUI_BASE = None
if sys.platform == "win32":
    GUI_BASE = "Win32GUI" # "Win32GUI"

RESOURCE_DIR=os.path.join(BASE_DIR, "koi", "resources")
I18N_DIR=os.path.join(RESOURCE_DIR,"i18n")


# Grab the koi directory (to get Logging, Configurator,...)
# FIXME rather fragile...
sys.path.append( BASE_DIR ) # os.path.join(os.path.abspath(__file__),'..','..')

# Server data

specific_data = [(r"resources\general_conditions.txt", os.path.join(RESOURCE_DIR,'general_conditions.txt'),'DATA'),
             (r'resources\package_version',    os.path.join(RESOURCE_DIR,'package_version'),'DATA'),
             (r'resources\file_server_logo.png',    os.path.join(RESOURCE_DIR,'file_server_logo.png'),'DATA'),
             (r'resources\server_config_check.cfg',   os.path.join(RESOURCE_DIR,'server_config_check.cfg'),'DATA'),
             (r"i18n\en\LC_MESSAGES\all_messages.mo", os.path.join(I18N_DIR,    r"en\LC_MESSAGES\all_messages.mo"),'DATA'),
             (r"i18n\fr\LC_MESSAGES\all_messages.mo", os.path.join(I18N_DIR,    r"fr\LC_MESSAGES\all_messages.mo"),'DATA') ]

# I used the specific data of PyInstall, so I transform them to make the cxFreeze
include_files = [ (res_path.replace( "\\", '/'), res_name) for res_name, res_path, dummy in specific_data ]

for k,v in include_files:
    print("{} -> {} : {}".format(k,v,os.path.isfile(k)))



print("Building server tools, BASE_DIR={}".format(BASE_DIR))

options = {
    'build_exe': {
        # 'optimize' : 2,
        # 'lxml._elementpath','inspect' : were introduced for docx template library
        'includes': [ 'koi',
                      'lxml._elementpath',
                      'inspect',
                      # Not necessary anymore ? 'cherrypy.wsgiserver.wsgiserver3',
                      'cx_Logging',
                      'win32com.shell',
                      #'koi.server.service',
                      'koi.user_mgmt', # not seen by cx_freeze for some reason
                      'winreg'],
        'include_files' : include_files,
        "include_msvcr" : True,
    }
}

setup(  name = "KoiServer",
        version = koi_version,
        description = "Koi server system",
        options = options,
        executables = [

                        # Commented for no reason :-( Right now it does build. The question
                        # left is : will it install as a windows service. That may explain
                        # why I kept th epyinstaller script.

                        # Executable(os.path.join(BASE_DIR,"koi","server",'cherry.py'),
                        #            base="Console",
                        #            targetName='koi_server.exe',
                        #            icon=os.path.join(RESOURCE_DIR,'win_icon.ico')),

                        Executable(os.path.join(BASE_DIR,"koi","server","admin_gui.py"),
                                   base="Console", #GUI_BASE
                                   targetName='koi_server_admin.exe',
                                   icon=os.path.join(RESOURCE_DIR,'win_icon.ico')),

                        Executable(os.path.join(BASE_DIR,"koi",'backup','pg_backup.py'),
                                   base="Console", targetName='koi_daily_batch.exe',
                                   icon=os.path.join(RESOURCE_DIR,'win_icon.ico'))
                        ])
