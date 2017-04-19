"""
To build a Wheel :

    python tools/server-wheel.py clean bdist_wheel

--> wheel will be put under the ./dist directory

You can install and reinstall it over and over :

    pip3 install --upgrade --no-deps --force-reinstall dist\KoiServer-1.11.9-py3-none-any.whl



To build a source package (zip file) : python tools/server-wheel.py clean sdist (note the directory position)

The wheel will be put in tools\dist\KoiServer-0.1.0-py3-none-any.whl

To test the wheel :

wheel install tools\dist\KoiServer-0.1.0-py3-none-any.whl # Doesn't work on virtualenv I think

To install on virtual env :
---------------------------

Enter virtualenv :

# In, C:\PORT-STC\PRIVATE\PL\Koi :

C:\PORT-STC\PRIVATE\PL\venv\Scripts\activate.bat

pip list # to see what's installed

# If you need dependencies not on  PyPI :
# On Windows, the following package won't be installed because they require
# compilation : lxml, psycopg2.

pip install c:\ Users\stc\Downloads\psycopg2-2.6.1-cp34-none-win32.whl
pip install c:\ Users\stc\Downloads\lxml-3.4.4-cp34-none-win32.whl


On Linux, pymediafire requests lxml. Since lxml compilation is a bit tricky,
use the python3-lxml debian package (instead of pip). So inistall that first,
then pymediafire next.



pip install Koi\dist\KoiServer-0.1.0-py3-none-any.whl

# Clean install of the Koi server (dependencies should be downloaded automatically by pip)
pip uninstall KoiServer # guess what
pip install dist\KoiServer-0.1.0-py3-none-any.whl


# Test it
python -m src.server.cherry

# Leave virtual env
deactivate

"""




import os
from setuptools import setup, find_packages


if 'TMP_HOME' in os.environ:
    # will be set by my release scripts
    BASE_DIR = os.environ['TMP_HOME']
else:
    # We're under tools, we go up a level
    BASE_DIR = os.path.join( os.getcwd(), os.path.dirname(__file__), '..')

if 'VERSION' in os.environ:
    VERSION = os.environ['VERSION']
else:
    VERSION = "0.1.0"


print("Packages will be looked for in {}".format(BASE_DIR))

p = find_packages(BASE_DIR, include=[ "koi.server", # server, administration GUI
                                      "koi", # FIXME what for ? Configurator at least
                                      "koi.backup", # To have the back up tool
                                      "koi.datalayer",
                                      "koi.configobj",
                                      "koi.configuration",
                                      "koi.doc_manager",
                                      "koi.gui",
                                      "koi.user_mgmt",
                                      "koi.machine",
                                      "koi.quality",
                                      "koi.session", # FIXME what for ?
                                      "koi.people_admin", # FIXME for the mapping only
                                      "koi.ply",
                                      "koi.junkyard",
                                      "koi.charts",
                                      "koi.tools",
                                      "koi.reporting",
                                      "koi.reporting.preorder",
                                      "koi.reporting.order_confirmation",
                                      "koi.resources",
                                      "koi.resources.server"])
print( "Packages are {}".format(p))

setup(
    name= "KoiServer",
    version= VERSION,
    url="https://koi-mes.net/html/index.html",
    author="Stefan Champailler",
    author_email="schampailler@skynet.be",
    packages=p,
    package_data= {"koi.resources": ["server_config_check.cfg", "file_server_logo.png"],
                   "koi.resources.server": ["order_confirmation_report.docx", "preorder_letter.docx"]},
    install_requires=['CherryPy==3.6.0',
                      'configobj>=5.0.0, <5.1.0',
                      'sqlalchemy>=0.9.9, <1.0.0',
                      'mediafire>=0.5.2, <0.6.0',
                      'docxtpl',
                      'reportlab',
                      'psycopg2',
                      # 'PySide==1.2.2', # commented out because pyside doesn't provide python binaries packages
                      # for Linux (so pip install will rebuild everything :( )
                      # It is thus easier to use the binaries provied by the host operating system.
                      'lxml>=3.4.2',
                      'jsonrpc2>=0.4.1'],
    classifiers=['Programming Language :: Python :: 3.4']
)
