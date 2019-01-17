import sys
import os

from cx_Freeze import setup, Executable


# Dependencies are automatically detected, but it might need fine tuning.
# FIXME Is this actually used ?
build_exe_options = {"packages": ["_json"],
                     "excludes": ["tkinter"] }


# Adding arguments parsing is next to impossible => I revert to enviro variables...

if 'TARGET_EXE' in os.environ:
    TARGET_EXE = os.environ['TARGET_EXE']
    NAME = "HorseClient"
    DESCRIPTION = "Horse user interface"
else:
    TARGET_EXE = 'koi.exe'
    NAME = "KoiClient"
    DESCRIPTION = "Koi user interface"


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
    GUI_BASE = "Win32GUI" # "Console" # "Win32GUI"

RESOURCE_DIR=os.path.join(BASE_DIR, "koi", "resources")
I18N_DIR=os.path.join(RESOURCE_DIR,"i18n")


# Grab the koi directory (to get Logging, Configurator,...)
# FIXME rather fragile...
sys.path.append( BASE_DIR ) # os.path.join(os.path.abspath(__file__),'..','..')


specific_data = [(r'resources\client_splash.png',  os.path.join(RESOURCE_DIR,'client_splash.png'),'DATA'),
                 (r'resources\package_version',    os.path.join(RESOURCE_DIR,'package_version'),'DATA'),
                 (r'resources\config.cfg',         os.path.join(RESOURCE_DIR,'config.cfg'),'DATA'),
                 (r'resources\config-check.cfg',   os.path.join(RESOURCE_DIR,'config-check.cfg'),'DATA'),
                 (r'resources\logo_pl.JPG',        os.path.join(RESOURCE_DIR,'logo_pl.JPG'),'DATA'),
                 (r'resources\letter_header.png',  os.path.join(RESOURCE_DIR,'letter_header.png'),'DATA'),
                 (r'resources\letter_footer.png',  os.path.join(RESOURCE_DIR,'letter_footer.png'),'DATA'),
                 (r'resources\standard.qss',       os.path.join(RESOURCE_DIR,'standard.qss'),'DATA'),
                 (r'resources\bigfont.qss',        os.path.join(RESOURCE_DIR,'bigfont.qss'),'DATA'),
                 (r'resources\DejaVuSansMono.ttf', os.path.join(RESOURCE_DIR,'DejaVuSansMono.ttf'),'DATA'),
                 (r'resources\Roboto-Regular.ttf', os.path.join(RESOURCE_DIR,'Roboto-Regular.ttf'),'DATA'),
                 (r'resources\Roboto-Bold.ttf',    os.path.join(RESOURCE_DIR,'Roboto-Bold.ttf'),'DATA'),
                 (r'resources\plus_icon.png',      os.path.join(RESOURCE_DIR,'plus_icon.png'),'DATA'),
                 (r'resources\plusplus_icon.png',  os.path.join(RESOURCE_DIR,'plusplus_icon.png'),'DATA'),
                 (r'resources\minus_icon.png',     os.path.join(RESOURCE_DIR,'minus_icon.png'),'DATA'),
                 (r'resources\up_icon.png',        os.path.join(RESOURCE_DIR,'up_icon.png'),'DATA'),
                 (r'resources\win_icon.png',       os.path.join(RESOURCE_DIR,'win_icon.png'),'DATA'),
                 (r'resources\win_icon.ico',       os.path.join(RESOURCE_DIR,'win_icon.ico'),'DATA'),
                 (r'resources\thumb-up-3x.png',    os.path.join(RESOURCE_DIR,'thumb-up-3x.png'),'DATA'),
                 (r'resources\appbar.book.hardcover.open.png', os.path.join(RESOURCE_DIR,'appbar.book.hardcover.open.png'),'DATA'),
                 (r'resources\appbar.cabinet.files.png',       os.path.join(RESOURCE_DIR,'appbar.cabinet.files.png'),'DATA'),
                 (r'resources\appbar.page.delete.png',         os.path.join(RESOURCE_DIR,'appbar.page.delete.png'),'DATA'),
                 (r'resources\appbar.page.download.png',       os.path.join(RESOURCE_DIR,'appbar.page.download.png'),'DATA'),
                 (r'resources\appbar.page.search.png',         os.path.join(RESOURCE_DIR,'appbar.page.search.png'),'DATA'),
                 (r'resources\appbar.page.upload.png',         os.path.join(RESOURCE_DIR,'appbar.page.upload.png'),'DATA'),
                 (r'resources\comments.png',       os.path.join(RESOURCE_DIR,'comments.png'),'DATA'),
                 (r'resources\SumatraPDF.exe',     os.path.join(RESOURCE_DIR,'SumatraPDF.exe'),'DATA'),
                 (r"resources\general_conditions.txt", os.path.join(RESOURCE_DIR,'general_conditions.txt'),'DATA'),
                 (r'resources\manual.html',        os.path.join(RESOURCE_DIR,'manual.html'),'DATA'),
                 (r"resources\i18n\en\LC_MESSAGES\all_messages.mo", os.path.join(I18N_DIR,    r"en\LC_MESSAGES\all_messages.mo"),'DATA'),
                 (r"resources\i18n\fr\LC_MESSAGES\all_messages.mo", os.path.join(I18N_DIR,    r"fr\LC_MESSAGES\all_messages.mo"),'DATA') ]

# I used the specific data of PyInstall, so I transform them to make the cxFreeze
include_files = [ (res_path.replace( "\\", '/'), res_name) for res_name, res_path, dummy in specific_data ]


print("Building client")

options = {
    'build_exe': {
        # cx_freeze detects those packages as part of Koi. It's wrong ini doing so.
        # Things you shall not try :
        # multiprocessing, used by jinja, used by docxtpl.
        'excludes': [ "tkinter","numpy","colorlog","colorama",
                      "setuptools" ],
        # 'optimize' : 2,
        # 'lxml._elementpath','inspect' : were introduced for docx template library
        'includes': ['koi', 'koi.resources',
                     'lxml._elementpath','inspect','openpyxl',
                     "pyxfer.pyxfer",
                     "sqlalchemy.sql.default_comparator",
                     "reportlab.graphics.barcode.ecc200datamatrix",
                     "asyncio.base_events",
                     "asyncio.base_futures",
                     "asyncio.base_subprocess",
                     "asyncio.base_tasks",
                     "asyncio.compat",
                     "asyncio.constants",
                     "asyncio.coroutines",
                     "asyncio.events",
                     "asyncio.futures",
                     "asyncio.locks",
                     "asyncio.log",
                     "asyncio.proactor_events",
                     "asyncio.protocols",
                     "asyncio.queues",
                     "asyncio.selector_events",
                     "asyncio.sslproto",
                     "asyncio.streams",
                     "asyncio.subprocess",
                     "asyncio.tasks",
                     "asyncio.test_utils",
                     "asyncio.transports",
                     "asyncio.unix_events",
                     "asyncio.windows_events",
                     "asyncio.windows_utils"  ],
        'include_files' : include_files,
        "include_msvcr" : True
    }
}

setup(  name = NAME,
        version = koi_version,
        description = DESCRIPTION,
        options = options,
        executables = [Executable(os.path.join(BASE_DIR,"koi","python.py"),
                                  base=GUI_BASE,
                                  targetName=TARGET_EXE,
                                  icon=os.path.join(RESOURCE_DIR,'win_icon.ico'))])
