# import urllib2
from urllib.request import urlopen
from urllib.parse import urlparse
import platform

import sys
import subprocess
import socket

import os
import glob
import tempfile
import zipfile
import shutil
from distutils.version import StrictVersion
import re
import configobj
import logging

from koi.base_logging import mainlog,init_logging,init_server_directory
init_server_directory()
mainlog.setLevel(logging.DEBUG)
init_logging("admin.log")

from koi.Configurator import init_i18n,load_configuration, resource_dir, configuration, get_data_dir
from koi.legal import copyright_years, copyright, license_short



init_i18n()

try:
    load_configuration("server.cfg","server_config_check.cfg")
except:
    load_configuration(None,"server_config_check.cfg")





from PySide.QtCore import Slot,Qt
from PySide.QtGui import QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QApplication, QMainWindow, QLabel, QFileDialog, QTextEdit, QLineEdit,QGridLayout
from PySide.QtGui import QDialog,QDialogButtonBox,QMessageBox,QGroupBox

from koi.datalayer.database_session import init_db_session, db_engine, check_postgres_connection,disconnect_db,check_database_connection,check_active_postgres_connections
from koi.datalayer.create_database import create_blank_database, set_up_database, create_root_account
from koi.download_version import get_server_version

from koi.server.zipconf import configure_zip
from koi.server.client_config_injector import load_public_ip,inject_public_ip_in_client
from koi.server.net_tools import guess_server_public_ip
from koi.backup.pg_backup import full_restore

def isUserAdmin():
    # (C) COPYRIGHT Preston Landers 2010
    # Released under the same license as Python 2.6.5

    if os.name == 'nt':
        import ctypes
        # WARNING: requires Windows XP SP2 or higher!
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    elif os.name == 'posix':
        # Check for root on Posix
        return os.getuid() == 0
    else:
        raise RuntimeError("Unsupported operating system for this module: %s" % (os.name,))


class YesConfirm(QDialog):
    def __init__(self,parent):
        super(YesConfirm,self).__init__()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("The following operation is irreversible. Type 'yes' to confirm"))

        self.line_edit = QLineEdit()
        layout.addWidget(self.line_edit)

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.StandardButton.Cancel)
        self.buttons.addButton( QDialogButtonBox.Ok)
        layout.addWidget(self.buttons)

        self.setLayout(layout)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    @Slot()
    def accept(self):
        if self.line_edit.text() == 'yes':
            return super(YesConfirm,self).accept()

    @Slot()
    def reject(self):
        return super(YesConfirm,self).reject()





class VersionDialog(QDialog):
    def __init__(self,parent):
        super(VersionDialog,self).__init__()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Which version do you want to download ?"))

        self.line_edit = QLineEdit()
        layout.addWidget(self.line_edit)

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.StandardButton.Cancel)
        self.buttons.addButton( QDialogButtonBox.Ok)
        layout.addWidget(self.buttons)

        self.setLayout(layout)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    @Slot()
    def accept(self):
        try:
            StrictVersion(self.line_edit.text())
            return super(VersionDialog,self).accept()
        except:
            pass

    @Slot()
    def reject(self):
        return super(VersionDialog,self).reject()


class MainWindow (QMainWindow):

    html_tag = re.compile("<[^>]+>")

    def _clear_log(self):
        self.log_view.clear()

    def _base_log(self, txt):
        if type(txt) == bytes:
            txt = txt.decode('utf-8','replace')

        if self.isVisible():
            self.log_view.append(txt)
            scrollbar = self.log_view.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            app.processEvents()

        return re.sub(self.html_tag,'',txt)


    def _log(self,txt):
        self._base_log(txt)

    def _log_error(self, txt):
        m = "<b><font color='red'>{}</font></b>".format(txt)
        self._base_log(m)

    def _log_warning(self, txt):
        m = "<b><font color='orange'>{}</font></b>".format(txt)
        self._base_log(m)

    def _log_success(self, txt):
        self._log( "<b><font color='green'>{}</font></b>".format(txt))

    def _run_detached_shell(self,cmd):
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        self._log("Executing : " + " ".join(cmd))
        popen = subprocess.Popen( cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,creationflags=DETACHED_PROCESS|CREATE_NEW_PROCESS_GROUP)

    def _run_shell(self,cmd, env=dict()):

        self._log("About to run {}".format(" ".join(cmd)))

        if env and platform.system() == "Windows":

            # For some reason, on widnows, using enviro variables
            # disturbs popen when trying to connect to the DB via psql.
            # I suspect that's more a problem with postgresql authentification
            # scheme, but after playing a bit with PG's config files
            # I wasn't able to turn something up...

            self._log("We're on Windows, I can't use environment variables...")
            env = None


        try:
            popen = subprocess.Popen( cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, universal_newlines=True)
        except Exception as ex:
            self._log_error("Can't run the command because {}".format(ex))
            raise ex

        # I used "poll" to follow the command's execution
        # but there were many issues (Python's doc talks about
        # deadlocks, I think that's what I've seen)

        stdout_data, stderr_data = popen.communicate()

        self._log(stdout_data)
        self._log(stderr_data)

        self._log("Returned {} ".format(int(popen.returncode)))
        return int(popen.returncode), stdout_data, stderr_data


    def _exec_out_of_transaction(self,sql):
        # Some Postgres administrative commands cannot run inside
        # a transaction. Unfortunately, SQLA tries very hard
        # to put us in a transaction at any time.
        # This is a small hack to leave the transaction.

        connection = db_engine().connect()
        connection.execute("commit") # Get out of SQLA's transaction
        self._log(sql)
        connection.execute(sql)
        connection.close()

    def _confirm_dangerous_operation(self):
        d = YesConfirm(self)
        d.exec_()
        return d.result() == QDialog.Accepted


    def _unzip_version(self,zipName,tmp_dir = ""):

        shutil.rmtree(tmp_dir)

        z = zipfile.ZipFile(zipName)
        for f in z.namelist():
            dest = os.path.join(tmp_dir,f.replace('/',os.sep))
            if f.endswith('/'):
                os.makedirs(dest)
            else:
                z.extract(f,tmp_dir)
        z.close()


    def _update_config(self,pg_url,host,port,path_cfg,path_spec):
        cfg = configobj.ConfigObj(infile=path_cfg,configspec=path_spec)
        cfg['Database']['url'] = pg_url
        cfg['DownloadSite']['url_file'] = 'http://{}:{}/file'.format(host,port)
        cfg['DownloadSite']['url_version'] = 'http://{}:{}/version'.format(host,port)
        cfg.write()


    def _zip_version(self,source_path,dest_path):
        z = zipfile.ZipFile(dest_path,"w",zipfile.ZIP_DEFLATED)

        for root, dirs, files in os.walk(source_path):
            for filename in files:
                # print source_path, root, filename

                fn = os.path.join(root, filename)
                arcname = os.path.join(root, filename).replace(source_path,"")
                z.write(fn, arcname=arcname)

        z.close()



    def _upgrade_client_to_version(self,version,pg_url,host,port):

        tmp_dir = "c:\\tmp"
        unzip_dir = os.path.join(tmp_dir,"azer")

        # Grab the zip
        # original_file = self._download_version(version,tmp_dir)
        original_file = os.path.join(tmp_dir,"horse-{}.zip".format(version))

        self._unzip_version(original_file,unzip_dir)

        self._update_config(pg_url,host,port,
                            os.path.join(unzip_dir, "koi", "resources", "config.cfg"),
                            os.path.join(unzip_dir, "koi", "resources", "config-check.cfg"))

        self._zip_version(unzip_dir, original_file)


    def _extract_db_params_from_url(self,url):
        parsed_url = urlparse(url)
        dbname = parsed_url.path[1:]
        login_pw_re = re.compile("^([^:]+):([^@]+)@([^:]+):?([0-9]+)?")
        login, password,host,port = login_pw_re.match(parsed_url.netloc).groups()
        return login, password, dbname, host, port



    def upgrade_client(self):

        d = VersionDialog(self)
        d.exec_()
        if d.result() == QDialog.Accepted:

            pg_url = self.public_url_edit.text()
            host = re.search("(@.*:)",pg_url).groups()[0].replace("@","").replace(":","")
            port = configuration.get("DownloadSite","port")

            self._upgrade_client_to_version("1.0.42",pg_url,host,port)



    @Slot(bool)
    def restore_backup(self):

        self._clear_log()
        self._log("Restore procedure started")

        url = self.url_edit.text()
        psql_path = configuration.get("Commands","psql")

        if not psql_path:
            self._log_error("The Commands/psql path is not set in the server.cfg")
            self._log("Please fix the configuration file (on the right)")
            return

        if not configuration.get("Commands","pg_restore"):
            self._log_error("The Commands/pg_restore path is not set in the server.cfg")
            self._log("Please fix the configuration file (on the right)")
            return

        if not configuration.get("Backup","backup_directory"):

            self._log("The Backup/backup_directory path is not set in the server.cfg")
            self._log("I'm setting it myself.")

            configuration.set("Backup","backup_directory", get_data_dir())
            configuration.set("DocumentsDatabase","documents_root", os.path.join(get_data_dir(), "documents"))
            configuration.save()
            self.edit_config.load_configuration()

        login_clt, password_clt, dummy, dummy, dummy = self._extract_db_params_from_url(configuration.get("Database","url"))
        login_adm, password_adm, dbname, host, port = self._extract_db_params_from_url(configuration.get("Database","admin_url"))

        self._log("{} / {}".format(login_adm, password_adm))

        full_path_backup = None
        d = ""
        if configuration.get("Backup","backup_directory"):
            d = configuration.get("Backup","backup_directory")




        if platform.system() == "Windows":

            if configuration.get("Backup","backup_directory"):
                d = configuration.get("Backup","backup_directory")

            # Using the static method gives a more native FileDialog.
            # with support for network
            backup_file = QFileDialog.getOpenFileName(self, _("Please select a backup file"), d,
                                                      "{} database backup (*.pgbackup)".format(configuration.get("Globals","name")))[0]

            if not backup_file:
                self._log("Restore aborted")
                return

            full_path_backup = backup_file
            if not os.path.isdir(full_path_backup):
                self._log("{} is not a directory, so I'll go up a level".format(full_path_backup))
                full_path_backup = os.path.dirname(full_path_backup)

                if not os.path.isdir(full_path_backup):
                    self._log_error("{} is not a directory either. Aborting restore.".format(full_path_backup))
                    return


        elif platform.system() == "Linux":

            d = AskWindowsShare(None)
            d.exec_()
            if d.result() == QDialog.Accepted:

                # //192.168.0.6/postgresqlbackup

                script_path = "/tmp/horse_mount.sh"
                script = open(script_path,"w")
                script.write("""#!/bin/bash
echo "Creating transfer directory"
mkdir /tmp/backup_win
echo "Unmounting previous transfer directory (can fail)"
umount /tmp/backup_win
echo "Mouting the backup directory"
mount -t cifs -ousername={},password={} {} /tmp/backup_win
                """.format(d.user.text().strip(), d.password.text().strip(), d.address.text().strip()))
                script.close()

                import stat
                os.chmod(script_path, stat.S_IEXEC | stat.S_IWRITE | stat.S_IREAD)

                cmd = ['gksudo', '--sudo-mode',
                       '--message', 'Allow Koi to connect to the backup server.',
                       script_path ]

                # gksudo seems to like to have the DISPLAY set. So I basically copy
                # it from the calling environment.

                ret, dummy, dummy = self._run_shell(cmd, {'DISPLAY':os.environ.get('DISPLAY')})

                if ret > 0:
                    self._log_error("The mount operation failed. Please review the parameters you've given.")
                    self._log_error("Network address : {}, windows user name : {}".format(d.address.text() or "?", d.user.text() or "?"))
                    return

                full_path_backup = "/tmp/backup_win"
            else:
                dialog = QFileDialog(self)
                dialog.setFileMode(QFileDialog.Directory)
                dialog.setNameFilters(['Koi database backup (*.pgbackup)'])
                dialog.setWindowTitle("Please select a backup file")
                if configuration.get("Backup","backup_directory"):
                    dialog.setDirectory(configuration.get("Backup","backup_directory"))
                if dialog.exec_():
                    full_path_backup = dialog.selectedFiles()[0]
                else:
                    self._log_error("Without proper source directory, I can't continue !")
                    return
        else:
            self._log_error("Unsupported operating system")


        # At this poitn full_path_backup is the path to the backup
        # directory of Horse that we want to restore.
        # It is different than the current backup directory.

        if full_path_backup:
            full_restore(configuration, full_path_backup, backup_file, True, mainlog)
            self._log_success("Backup successfully restored !")



    def create_root_account(self):
        if not configuration.get("Database","url"):
            self._log_error("Can't read Database/url ini config file")
            return

        login="admin"
        password="admin"

        self._clear_log()
        self._log("<b>Creating or recreating a root account")
        try:
            init_db_session(configuration.get("Database","url"))
            create_root_account(login, password)
            self._log_success("Root account successfully reset to login:{}, password:{}".format(login,password))
        except Exception as ex:
            self._log_error("Root account creation failed")
            self._log_error(ex)

    def create_database(self, localhost=False):

        # If in command line, skip requesting confirmation for database creation
        if self.isVisible() and not self._confirm_dangerous_operation():
            return

        self._clear_log()

        if not configuration.get("Database","admin_url"):
            self._log_error("Can't read Database/admin_url ini config file")
            return

        if not configuration.get("Database","url"):
            self._log_error("Can't read Database/url ini config file")
            return

        admin_url = configuration.get("Database","admin_url")
        local_url = configuration.get("Database","url")

        if check_postgres_connection(configuration.get("Database","admin_url")):
            self._log("Successfuly connected to PostgreSQL server")
        else:
            self._log_error("Failed to connect to PostgreSQL server")
            return False

        self._log("<b>Creating a database")
        try:
            create_blank_database(configuration.get("Database","admin_url"), configuration.get("Database","url"))
            self._log("<b><font color='green'>Database created")
        except Exception as ex:
            self._log_error("Database creation failed")
            self._log_error(ex)

        disconnect_db()
        return


    def check_database(self):
        self._clear_log()

        url = self.url_edit.text()

        self._log("<b>Checking database at {}".format(url))

        service_installed = False

        if platform.system() == "Windows":
            cmd = ["sc", "query", self.POSTGRESQL_SERVICE_NAME]
            service_installed, stdout, stderr = self._run_shell(cmd)

            if check_postgres_connection(url):

                self._log_success("Successfuly connected with the PostgreSQLserver")
                if service_installed == 0:
                    self._log("The {} Windows service seems installed correctly. So the database should resist to a reboot.".format(self.POSTGRESQL_SERVICE_NAME))
                else:
                    self._log_error("I didn't find the {} service in Windows services. Did the installation complete correctly ? If this PC restarts, the database won't start, making the system unusable.".format(self.POSTGRESQL_SERVICE_NAME))

            else:
                self._log_error("Unable to connect to PostgreSQL server.")
                if service_installed == 0:
                    self._log("The {} service seems installed though. You should locate it in Windows services and start it".format(self.POSTGRESQL_SERVICE_NAME))
                else:
                    self._log("The {} service is not installed. You should try to install with (see Install services button in this program) or, if that doesn't work, install it manually.".format(self.POSTGRESQL_SERVICE_NAME))


                return False

        disconnect_db()
        init_db_session(url, None, False)

        # check = check_database_connection()
        # if  check == True:
        #     self._log_success("Successfuly connected to database")
        # else:
        #     self._log(u"Failed to connect to database. Maybe you should create it or restore a backup ? Error was :")
        #     self._log_error(check)
        #     return False
        #
        # self._log("")

        r = check_active_postgres_connections()
        disconnect_db()

        if r > 1:
            self._log("There are {} other people connected".format(r))
            self._log("The database seems fine".format(r))
            return False
        elif r == 1:
            self._log("Nobody connected to the database (besides us)")
            self._log("The database seems fine".format(r))
        else:
            self._log_error("Can't check number of connected people...")
            # self._log("The database seems broken".format(r))
            return False

        return True


    def check_server(self):
        self._clear_log()
        self._log("<b>Checking web server")

        # Because of difficulties with cxFreeze and cherrypy and windows service, the
        # Koi windows service is not installed; only a scheduled taks is installed.

        # if platform.system() == "Windows":
        #
        #     cmd = ["sc", "query", self.SERVER_NAME+self.SERVER_NAME_SUFFIX]
        #
        #     try:
        #         if self._run_shell(cmd):
        #             self._log_error("Can't find the server's Windows service ({}). Check your installation or use 'Install services'. If this PC restarts, the server won't start, making the system unusable.".format(self.SERVER_NAME+self.SERVER_NAME_SUFFIX))
        #             return
        #     except Exception as ex:
        #         return

        v = get_server_version(configuration.update_url_version)

        db_url = None
        try:
            self._log("Looking for advertised DB version at {}".format(configuration.database_url_source()))
            response = urlopen(configuration.database_url_source(),timeout=2)
            db_url = response.read()
        except Exception as ex:
            self._log_error("Unable to connect to the web server. Is it running ? I tried to get the databse url from it. If the server is running, check the configuration at DownloadSite/base_url and verify it's good.")

            HOST = guess_server_public_ip()
            self._log("Looking again for advertised DB version at {}".format(HOST))
            response = urlopen("http://{}".format(HOST),timeout=2)
            db_url = response.read()

            pass

        if v and db_url:
            self._log("Server version : {}".format(v))
            self._log("Public announced database : {}".format(db_url))
            self._log("")
            self._log("<b><font color='green'>Server is fine")
        else:
            self._log_error("Server didn't answer. Maybe you should start it manually ?")




    def stop_server_manually(self):
        self._clear_log()
        self._log("<b>Shutting down server...")

        cmd = ["taskkill","/F","/IM","horse_server_console.exe"]
        self._run_shell(cmd)

        cmd = [configuration.get("Commands","pg_ctl"), "-D", configuration.get("Database","db_path"), "stop"]
        self._run_shell(cmd)
        self._log("<b>Server shut down")


    def start_server_manually(self):
        self._clear_log()
        self._log("<b>Starting server...")

        cmd = [configuration.get("Commands","horse_server_console")]
        self._run_detached_shell(cmd)

        cmd = [configuration.get("Commands","pg_ctl"), "-D", configuration.get("Database","db_path"), "start"]
        self._run_detached_shell(cmd)

        self._log("<b>Server started")

    POSTGRESQL_SERVICE_NAME = "Postgresql" # No space here !
    SERVER_NAME = "HorseService" # No space here !
    SERVER_NAME_SUFFIX = "Production"
    BACKUP_NAME = "HorseBackup"

    def install_on_start_tasks(self):
        self.stop_server_manually()

        self._clear_log()
        self._log("<b>Installing on-start services...")
        self._log("Installing backup as a scheduled task (once every night)...")
        cmd = ["SCHTASKS","/Create","/F","/SC","DAILY","/ST","00:30","/TN",self.BACKUP_NAME,"/TR",configuration.get("Commands","horse_backup")]
        self._run_shell(cmd)

        # self._log("Installing webserver as a scheduled task (once at startup)...")
        # cmd = ["SCHTASKS","/Create","/F","/SC","ONSTART","/TN",self.XXX,"/TR",configuration.get("Commands","horse_server")]
        # self._run_shell(cmd)



    def install_service(self):
        self.stop_server_manually()

        self._clear_log()
        self._log("<b>Installing services...")
        self._log("Installing backup as a scheduled task...")
        cmd = ["SCHTASKS","/Create","/F","/SC","DAILY","/ST","00:30","/TN","HorseDailyBackup","/TR",configuration.get("Commands","horse_backup")]
        self._run_shell(cmd)

        self._log("Installing PostgreSQL as a service...")

        cmd = [configuration.get("Commands","pg_ctl"), "register","-N", self.POSTGRESQL_SERVICE_NAME, "-D", configuration.get("Database","db_path")]
        self._run_shell(cmd)
        cmd = ["sc", "start", self.POSTGRESQL_SERVICE_NAME]
        self._run_shell(cmd)
        cmd = ["sc", "query", self.POSTGRESQL_SERVICE_NAME]
        self._run_shell(cmd)

        self._log("Installing server as a service...")
        cmd = [configuration.get("Commands","horse_server"),"--install",self.SERVER_NAME_SUFFIX]
        self._run_shell(cmd)

        self._log("<b>Services installed")

        cmd = ["sc", "start", self.SERVER_NAME+self.SERVER_NAME_SUFFIX]
        self._run_shell(cmd)



    def uninstall_service(self):
        self._clear_log()
        self._log("<b>Uninstalling services...")
        self._log("Uninstalling backup as a scheduled task...")
        cmd = ["SCHTASKS","/Delete","/F","/TN","HorseDailyBackup"] # /F to avoid an interactive confirmation
        self._run_shell(cmd)

        self._log("Uninstalling PostgreSQL as a service...")

        cmd = ["sc", "stop", self.POSTGRESQL_SERVICE_NAME]
        self._run_shell(cmd)

        cmd = [configuration.get("Commands","pg_ctl"), "unregister","-N", self.POSTGRESQL_SERVICE_NAME, "-D", configuration.get("Database","db_path")]
        self._run_shell(cmd)

        self._log("Uninstalling server as a service...")
        cmd = [configuration.get("Commands","horse_server"),"remove"]
        self._run_shell(cmd)

        self._log("<b>Services uninstalled")


    def show_intro(self):
        self._log("<b>This is {} !".format(configuration.get("Globals","name")))

        self._log("<b>"+copyright())
        self._log("<b>"+license_short())
        self._log("")

        if platform.system() == "Windows" and not isUserAdmin():
            self._log_warning("You don't have amdinistrative rights ! Therefore some of the functionality in this program won't work.")
            self._log("To change that, use the 'run as administrator' functionality of Windows. Right-click on the {} admnististration program in the start menu and select 'run as administrator'".format(configuration.get("Globals","name")))

        if self.check_backup_directory() != True:
            self._log_error("The backup directory is not correct !")


    def check_backup_directory(self):
        self._log("Testing the backup directory")
        directory = configuration.get("Backup","backup_directory")
        try:
            f = open( os.path.join(directory,"test_file"), "w")
            f.write("TestBackup")
            f.close()
            self._log("<b><font color='green'>Backup directory is fine !")
            return True
        except Exception as ex:
            return str(ex)

    def set_backup_directory(self):
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.ShowDirsOnly, True)
        dialog.setWindowTitle("Please select a backup directory")

        if configuration.get("Backup","backup_directory"):
            dialog.setDirectory(configuration.get("Backup","backup_directory"))

        if dialog.exec_():
            mainlog.debug(dialog.selectedFiles())
            directory = dialog.selectedFiles()[0]

            self._log("Testing the backup directory")
            try:
                f = open( os.path.join(directory,"test_file"), "w")
                f.write("TestBackup")
                f.close()
            except Exception as ex:
                box = QMessageBox(QMessageBox.Warning,
                                  "Unable to write into the backup directory",
                                  u"I can't write in the backup directory you selected. Have I the necessary permissions  on that directory ({})? The error was : {}".format(directory, str(ex)))
                box.exec_()
                return

            self.backup_directory_edit.setText(directory)

            configuration.set("Backup","backup_directory",directory)

            self._log("Saving the backup directory in the configuration")
            configuration.save()

        dialog.close()


    def show_client_dowload_page(self):
        import webbrowser

        self._log("<hr>")

        url = configuration.get("DownloadSite","public_url")
        self._log("<b>Opening delivery_slips download page at : {}".format(url))

        if True or url:
            try:
                webbrowser.open(url)
            except Exception as ex:
                self._log_error("Unable to open the page because of an error: {}".format(ex))
        else:
            self._log("Could not open the delivery_slips page because URL is empty. The configuration is not good.")

    def set_public_ip(self):
        d = AskIPAddress(self)
        d.exec_()
        guessed_ip = d.address.text()

        ip_in_zip = load_public_ip()
        if ip_in_zip != guessed_ip:
            if confirmationBox(_("Setting IP addresse in delivery_slips zip"),
                               _("The IP address configured in the zipped delivery_slips ({}) is not the " +
                                         "same as the one you gave ({}). Maybe the server has " +
                                         "changed network. Should I fix that ?").format(ip_in_zip, guessed_ip)):
                inject_public_ip_in_client(guessed_ip)

        server_ip = configuration.get("DEFAULT","public_ip")
        if guessed_ip != server_ip:
            if confirmationBox(_("Setting IP addresse in server configuration"),
                               _("The IP address configured for the server ({}) is not the " +
                                         "same as the one you gave ({}). Maybe the server has " +
                                         "changed network. Should I fix that ?").format(server_ip, guessed_ip)):

                configuration.set("DEFAULT","public_ip",guessed_ip)
                configuration.save()
                window.edit_config.load_configuration()


    def __init__(self):
        super(MainWindow,self).__init__()

        self.edit_config = EditConfigurationDialog(self)
        self.edit_config.load_configuration()

        w = QWidget(self)

        big_hlayout = QHBoxLayout()

        layout = QVBoxLayout()
        big_hlayout.addLayout(layout)
        big_hlayout.addWidget(self.edit_config)

        layout.addWidget( QLabel("<h1>{} administration</h1>".format(configuration.get("Globals","name"))))

        glayout = QGridLayout()

        row = 0

        HOST = "{} or {}".format(guess_server_public_ip(), socket.gethostname())
        glayout.addWidget(QLabel("<b>Server's IP address"),row,0)
        ip_address = configuration.get("DEFAULT","public_ip")
        if not ip_address:
            ip_address = "<font color='red'><b>NOT DEFINED</b></font>"
        glayout.addWidget( QLabel("{} (guessed: {})".format(ip_address, HOST)),row,1)

        row += 1
        glayout.addWidget(QLabel("<b>Client database URL"),row,0)
        db_url = configuration.get("Database","url")
        self.public_url_edit = QLabel(db_url)
        glayout.addWidget( self.public_url_edit,row,1)

        row += 1
        glayout.addWidget(QLabel("<b>Client server URL"),row,0)
        url = configuration.get("DownloadSite","public_url")
        self.public_web_url_edit = QLabel(url)
        glayout.addWidget( self.public_web_url_edit,row,1)

        row += 1
        glayout.addWidget(QLabel("Server local DB URL"),row,0)
        db_url = configuration.get("Database","admin_url")
        self.url_edit = QLabel(db_url)
        glayout.addWidget( self.url_edit,row,1)

        row += 1
        glayout.addWidget(QLabel("Backup directory"),row,0)
        db_url = configuration.get("Backup","backup_directory")
        self.backup_directory_edit = QLabel(db_url)
        glayout.addWidget( self.backup_directory_edit,row,1)

        row += 1
        glayout.addWidget(QLabel("Data/logs directory"),row,0)
        self.data_directory_edit = QLabel( get_data_dir())
        glayout.addWidget( self.data_directory_edit,row,1)

        qgb = QGroupBox("Life data")
        qgb.setLayout(glayout)
        layout.addWidget(qgb)


        hlayout = QHBoxLayout()
        b = QPushButton("Check database")
        b.clicked.connect(self.check_database)
        hlayout.addWidget( b)

        b = QPushButton("Check web server")
        b.clicked.connect(self.check_server)
        hlayout.addWidget( b)

        b = QPushButton("Show delivery_slips download page")
        b.clicked.connect(self.show_client_dowload_page)
        hlayout.addWidget( b)

        qgb = QGroupBox("Checks")
        qgb.setLayout(hlayout)
        layout.addWidget(qgb)

        hlayout = QHBoxLayout()
        # b = QPushButton("Set backup directory")
        # b.clicked.connect(self.set_backup_directory)
        # hlayout.addWidget( b)

        b = QPushButton("Restore backup")
        b.clicked.connect(self.restore_backup)
        hlayout.addWidget( b)

        b = QPushButton("Reset admin account")
        b.clicked.connect(self.create_root_account)
        hlayout.addWidget( b)

        # b = QPushButton("Set public IP")
        # b.clicked.connect(self.set_public_ip)
        # hlayout.addWidget( b)

        # Please use the command line, this is not for the faint hearted.

        # b = QPushButton("Clear database")
        # b.clicked.connect(self.create_database)
        # hlayout.addWidget( b)

        qgb = QGroupBox("Actions")
        qgb.setLayout(hlayout)
        layout.addWidget(qgb)



        vlayout = QVBoxLayout()

        # if platform.system() == 'Windows':
        #     # when running on Linux, it's expected that the
        #     # whole server configuration is set up by us
        #
        #     hlayout = QHBoxLayout()
        #     b = QPushButton("Start server manually")
        #     b.clicked.connect(self.start_server_manually)
        #     hlayout.addWidget( b)
        #
        #     b = QPushButton("Stop server manually")
        #     b.clicked.connect(self.stop_server_manually)
        #     hlayout.addWidget( b)
        #     vlayout.addLayout(hlayout)
        #
        #     hlayout = QHBoxLayout()
        #     b = QPushButton("Install services")
        #     b.clicked.connect(self.install_service)
        #     hlayout.addWidget( b)
        #
        #     b = QPushButton("Uninstall services")
        #     b.clicked.connect(self.uninstall_service)
        #     hlayout.addWidget( b)
        #     vlayout.addLayout(hlayout)
        #
        #     b = QPushButton("Install scheduled services")
        #     b.clicked.connect(self.install_on_start_tasks)
        #     vlayout.addWidget( b)
        #
        #     # b = QPushButton("Upgrade delivery_slips")
        #     # b.clicked.connect(self.upgrade_client)
        #     # layout.addWidget( b)
        #
        #     qgb = QGroupBox("Service & installation")
        #     qgb.setLayout(vlayout)
        #     layout.addWidget(qgb)

        self.log_view = QTextEdit()
        layout.addWidget( self.log_view)

        self.url_edit.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.public_url_edit.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.public_web_url_edit.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.backup_directory_edit.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.log_view.setReadOnly(True)

        w.setLayout(big_hlayout)

        self.setCentralWidget(w)

class EditConfigurationDialog(QWidget):
    def __init__(self, log, parent = None):
        super(EditConfigurationDialog,self).__init__(parent)
        layout = QVBoxLayout()
        self._log = log
        self.text_edit_widget= QTextEdit()
        layout.addWidget(self.text_edit_widget)

        buttons = QDialogButtonBox()
        # buttons.addButton( QDialogButtonBox.StandardButton.Cancel)
        buttons.addButton( QDialogButtonBox.StandardButton.Save)
        layout.addWidget(buttons)

        buttons.button(QDialogButtonBox.StandardButton.Save).clicked.connect(self._save)

        self.setLayout(layout)

    def _save(self):

        try:
            old_server_ip = configuration.get("DEFAULT","public_ip")

            cfg_path = os.path.join(get_data_dir(), "server.cfg")
            f = open( cfg_path, "w")
            f.write(self.text_edit_widget.toPlainText())
            f.close()
            self._log._log_success("Server configuration saved in {}".format(cfg_path))

            load_configuration(cfg_path,"server_config_check.cfg")
            self._log._log_success("Server configuration reloaded")

            server_ip = configuration.get("DEFAULT","public_ip")
            if old_server_ip != server_ip:
                self._log._log_success("Updating IP address in the downloadable delivery_slips")
                inject_public_ip_in_client(server_ip)

        except Exception as ex:
            self._log._log_error("Something went wrong while saving the configuration : {}".format(ex))

        self._log._log("Reloading server configuration")
        import threading

        def open_server(url):
            try:
                urlopen(url)
            except ConnectionResetError as ex:
                pass

        threading.Thread(target=open_server, args=['http://127.0.0.1:8079/reload']).start()

    def load_configuration(self):
        cfg_path = os.path.join(get_data_dir(), "server.cfg")

        # try:
        f = open( cfg_path, "r")
        t = f.read()
        f.close()
        self.text_edit_widget.setText(t)
        # except:
        #     self._log.error("Can't read config file at {}".format(cfg_path))
        #     raise


class AskWindowsShare(QDialog):
    def __init__(self,parent):
        super(AskWindowsShare,self).__init__()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Please give the connection parameter to the Windows share.<br/>" +
                                "The address is the regular Windows network address, for example : //the-server/Share<br/>" +
                                "You can also use IP addresses : //192.168.0.86/horse_backup"))

        glayout = QGridLayout()

        self.address = QLineEdit()
        glayout.addWidget(QLabel("Address"),0,0)
        glayout.addWidget(self.address,0,1)

        self.user = QLineEdit()
        glayout.addWidget(QLabel("User name"),1,0)
        glayout.addWidget(self.user,1,1)

        self.password= QLineEdit()
        glayout.addWidget(QLabel("Password"),2,0)
        glayout.addWidget(self.password,2,1)

        layout.addLayout(glayout)

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.Ok)
        self.buttons.addButton( QDialogButtonBox.Cancel )
        layout.addWidget(self.buttons)

        self.setLayout(layout)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    @Slot()
    def accept(self):
        return super(AskWindowsShare,self).accept()

    @Slot()
    def reject(self):
        return super(AskWindowsShare,self).reject()



class AskIPAddress(QDialog):
    def __init__(self,parent):
        super(AskIPAddress,self).__init__()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Please enter a valid address"))

        glayout = QGridLayout()

        self.address = QLineEdit()
        glayout.addWidget(QLabel("IP Address"),0,0)
        glayout.addWidget(self.address,0,1)

        self.address.setText( guess_server_public_ip())
        layout.addLayout(glayout)

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.Ok)
        layout.addWidget(self.buttons)

        self.setLayout(layout)

        self.buttons.accepted.connect(self.accept)

    @Slot()
    def accept(self):
        return super(AskIPAddress,self).accept()



def confirmationBox(text,info_text,object_name="confirmationBox"):
    box = QMessageBox()
    box.setObjectName(object_name)
    box.setWindowTitle(_("Please confirm"))
    box.setIcon(QMessageBox.Question)
    box.setText(text)
    if info_text:
        box.setInformativeText(info_text)
    box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel);

    # box.show()
    # from PySide.QtTest import QTest
    # from PySide.QtGui import QApplication
    # QTest.qWaitForWindowShown(box)
    # QApplication.instance().removePostedEvents()

    r = box.exec_() == QMessageBox.Ok

    box.deleteLater()
    return r



from logging import Handler
import logging

class LoggerHandler(Handler):
    def __init__(self, mainwindow : MainWindow):
        self._main_window = mainwindow
        super(LoggerHandler, self).__init__()

    def emit(self, record):
        if record.levelno == logging.ERROR:
            self._main_window._base_log( "<b><font color='red'>{}</font></b>".format(str(record.msg) % record.args))
        elif record.levelno == logging.WARNING:
            self._main_window._base_log( "<b><font color='orange'>{}</font></b>".format(record.msg % record.args))
        elif record.levelno == logging.DEBUG:
            pass
            # self._main_window._base_log( "<b><font color='gray'>{}</font></b>".format(record.msg % record.args))
        else:
            self._main_window._base_log( record.msg % record.args)



import argparse

parser = argparse.ArgumentParser(description='This is the administration console for {}!'.format(configuration.get("Globals","name")))
parser.add_argument('--reset-database', action='store_const', const=True, help='Reset the database and returns. ')
parser.add_argument('--create-root-account', action='store_const', const=True, help='Create a root account. ')
parser.add_argument('--psql', default='psql.exe', help='Full path to psql')
parser.add_argument('--configure-zip', help='Path to zip file')
parser.add_argument('--host', help='Host')

if __name__ == "__main__":

    args = parser.parse_args()

    if args.configure_zip:
        if args.host:
            mainlog.info("Configuring zip at {} with host {}".format(args.configure_zip, args.host))
            configure_zip(args.configure_zip, args.host)
            sys.exit(0)
        else:
            mainlog.error("Missing host")
            sys.exit(1)


    app = QApplication(sys.argv)
    window = MainWindow()
    mainlog.addHandler( LoggerHandler(window))

    # d = AskWindowsShare(None)
    # d.exec_()



    if args.reset_database:
        window.create_database()
        sys.exit(0)
    if args.create_root_account:
        window.create_root_account()
        sys.exit(0)


    window.setMinimumSize(1000,700)
    # window._upgrade_client_to_version("1.0.42","postgresql://jsdfksdhf","192.168.16.16","666")



    cfg_path = os.path.join(get_data_dir(), "server.cfg")

    if not os.path.exists(cfg_path):
        f = open( cfg_path, "w")

        c = configuration.base_configuration.copy()
        for section in sorted(c.keys()):
            f.write("[{}]\n".format(section))

            for entry,value in c[section].items():
                f.write("{} = {}\n".format(entry,value))

            f.write("\n")

        f.close()



    window.show()
    window.show_intro()
    window._log("If the database doesn't exist, you can create it and then create the admin user like this :")
    window._log("CREATE USER horse_adm LOGIN CREATEDB CREATEROLE PASSWORD 'horsihors';")



    # exit()

    #window.restore_backup()

    app.exec_()
