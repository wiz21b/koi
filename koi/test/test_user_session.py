import unittest
import tempfile

from PySide.QtGui import QApplication, QDialogButtonBox
from PySide.QtTest import QTest
from PySide.QtCore import Qt

from koi.test.test_base import TestBase
from koi.Configurator import resource_dir
from koi.session.UserSession import user_session
from koi.session.LoginDialog import LoginDialog
from koi.dao import *


class TestUserLogin(TestBase):

    @classmethod
    def setUpClass(cls):
        super(TestUserLogin,cls).setUpClass()
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        cls.app = app

        f = tempfile.NamedTemporaryFile(mode='w',delete=False)
        mainlog.debug(f.name)
        f.write(r"""[Database]
url = postgresql://tester:@localhost:5432/horse_test

echo_query = False
recreate_table = False
user = tester
password = ""
db_name = horse_test

[Proxy]
# proxy_url=127.0.0.1
#proxy_port=5865
proxy_url = ""
proxy_port = ""

[MediaFire]
email = schampailler@skynet.be
password = Smals23081
appid = 33522
sessionkey = 8zcfzgxq614j0a1ivyb2mllm402x443zxms99iul

[Backup]
prefix = horse_backup
dirname = horse_backup
# Size in megabytes
size = integer(default=9)
encryption_key = AZEDSFKHSDFIZERBDSFISRBAZEIRA3244234AZE434
backup_directory = c:\tmp

[Commands]
pg_dump_cmd = C:\PORT-STC\opt\pgsql\bin\pg_dump.exe
zip = zip

encrypt_cmd = string(default="C:\PORT-STC\opt\aescrypt.exe")
dropdb_cmd = string(default="C:\PORT-STC\opt\pgsql\bin\dropdb.exe")
createdb_cmd = string(default="C:\PORT-STC\opt\pgsql\bin\createdb.exe")
pg_restore_cmd = string(default="C:\PORT-STC\opt\pgsql\bin\pg_restore.exe")

[Mail]
SMTPServer = string
sender = backup@pl.be
destination = zulu@zulu.net
SMTPUser = fb569808
SMTPPassword = xjb6pqrx

[DownloadSite]
port = 8079
current_version = 1.0.10
client_path = c:\port-stc\pl-private\src\horse\dist\horse-%(current_version)s.zip
db_url = postgresql://horse_clt:HorseAxxess@192.168.0.96:5432/horsedb """)
        f.close()

        configuration.load(f.name, os.path.join( resource_dir, 'config-check.cfg'))



    @classmethod
    def tearDownClass(cls):
        pass
        # cls.app.exit()

    def setUp(self):
        user_session.invalidate()

    def _fill_in_valid_credentials(self):
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_D) # modifier, delay
        self.app.processEvents()
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_K) # modifier, delay
        self.app.processEvents()

        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_Tab) # modifier, delay
        self.app.processEvents()

        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_K) # modifier, delay
        self.app.processEvents()
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_K) # modifier, delay
        self.app.processEvents()


    def test_forget_me(self):
        configuration.set("AutoLogin","user",self.employee.login)
        configuration.set("AutoLogin","password","kk")
        configuration.save()

        d = LoginDialog(None,user_session)
        d.show()
        for i in range(100000):
            self.app.processEvents() # Linux needs a vrey long break

        self.assertTrue(d.remember_me.checkState() == Qt.Checked)

        d.remember_me.setCheckState(Qt.Unchecked)
        d.buttons.button(QDialogButtonBox.Ok).click()

        # The dialog will *not* save the configuration file because
        # "rememeber me" is not set
        self.app.processEvents()
        d.close()

        configuration.reload()
        self.assertEqual(None,configuration.get("AutoLogin","user"))
        self.assertEqual(None,configuration.get("AutoLogin","password"))


    def test_remember_me(self):
        configuration.set("AutoLogin","user",self.employee.login)
        configuration.set("AutoLogin","password",None)
        d = LoginDialog(None,user_session)
        d.show()
        for i in range(100000):
            self.app.processEvents() # Linux needs a vrey long break

        self.assertTrue(d.remember_me.checkState() == Qt.Checked)
        self.assertEqual(configuration.get("AutoLogin","user"), d.userid.text())

        # Short cut to clear the dialog
        d.userid.setText("")
        d.password.setText("")
        d.userid.setFocus(Qt.OtherFocusReason)

        self._fill_in_valid_credentials()
        self.assertTrue(d.remember_me.checkState() == Qt.Unchecked)

        d.remember_me.setCheckState(Qt.Checked)
        d.buttons.button(QDialogButtonBox.Ok).click()

        # The dialog will save the configuration file because
        # of "rememeber me"
        self.app.processEvents()
        d.close()

        self.assertEqual("dk",configuration.get("AutoLogin","user"))
        self.assertEqual("kk",configuration.get("AutoLogin","password"))

        configuration.reload()
        self.assertEqual("dk",configuration.get("AutoLogin","user"))
        self.assertEqual("kk",configuration.get("AutoLogin","password"))

    def test_no_login(self):

        d = LoginDialog(None,user_session)
        d.show()
        for i in range(100000):
            self.app.processEvents() # Linux needs a vrey long break
        d.close()

        self.assertFalse(user_session.is_active())

    def test_login(self):

        mainlog.debug("test_login")

        
        d = LoginDialog(None,user_session)
        d.show()
        mainlog.debug("test_login : shown")
        
        for i in range(100000):
            self.app.processEvents() # Linux needs a vrey long break

        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_D) # modifier, delay
        self.app.processEvents()
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_K) # modifier, delay
        self.app.processEvents()

        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_Tab) # modifier, delay
        self.app.processEvents()

        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_K) # modifier, delay
        self.app.processEvents()
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_K) # modifier, delay
        self.app.processEvents()

        d.buttons.button(QDialogButtonBox.Ok).click()
        self.app.processEvents()

        self.assertTrue(user_session.is_active())

if __name__ == "__main__":
    unittest.main()
