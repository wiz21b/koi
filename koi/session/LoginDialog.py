import hashlib

from PySide.QtCore import Slot,Qt
from PySide.QtGui import QDialog, QDialogButtonBox, QLabel, QCheckBox, QApplication
from PySide.QtGui import QVBoxLayout,QLineEdit,QFormLayout

from koi.base_logging import mainlog
from koi.Configurator import configuration
from koi.gui.dialog_utils import TitleWidget,makeErrorBox

from koi.dao import dao
from koi.junkyard.services import services
from koi.datalayer.employee_mapping import Employee


class LoginDialog(QDialog):

    def __init__(self,parent,user_session):
        super(LoginDialog,self).__init__(parent)
        self.user = None
        self.user_session = user_session

        title = _("{} Login").format(configuration.get("Globals","name"))

        self.setWindowTitle(title)
        self.title_widget = TitleWidget(title,self)

        self.userid = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)

        self.remember_me = QCheckBox()

        form_layout = QFormLayout()
        form_layout.addRow( _("User ID"), self.userid)
        form_layout.addRow( _("Password"), self.password)
        form_layout.addRow( _("Remember me"), self.remember_me)

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.Ok)

        top_layout = QVBoxLayout()
        top_layout.addWidget(self.title_widget)
        top_layout.addWidget(QLabel(_("Please identify yourself")))
        top_layout.addLayout(form_layout)
        top_layout.addWidget(self.buttons)

        self.setLayout(top_layout) # QWidget takes ownership of the layout

        self.buttons.accepted.connect(self.try_login)
        self.buttons.rejected.connect(self.cancel)

        self.userid.textEdited.connect(self.login_changed)

        if configuration.get("AutoLogin","user"):
            self.remember_me.setCheckState(Qt.Checked)
            self.userid.setText(configuration.get("AutoLogin","user"))
            self.password.setText(configuration.get("AutoLogin","password"))

        mainlog.debug("__init__ login dialog")

    def showEvent(self,event):
        # Center the dialog on the screen

        super(LoginDialog,self).showEvent(event)

        scr = QApplication.desktop().screenGeometry()
        self.move( scr.center() - self.rect().center())

    @Slot()
    def login_changed(self,text):
        self.remember_me.setCheckState(Qt.Unchecked)

    @Slot()
    def try_login(self):

        # self.user = services.employees.authenticate(self.userid.text(),pw)
        self.user = dao.employee_dao.authenticate(
            self.userid.text(),
            Employee.hash_password(self.password.text()))

        if self.user:
            super(LoginDialog,self).accept()
            self.initialize_session()
            self.setResult(QDialog.Accepted)
            return

        d = makeErrorBox(_("You can't log"), _("The user or password is not valid."))
        d.exec_()
        d.deleteLater()
        return

    def authenticated_user(self):
        return self.user

    @Slot()
    def cancel(self):
        return super(LoginDialog,self).reject()


    def initialize_session(self):
        # if not user_session.is_active(): # the configuration may have forced a user

        self.user_session.open(self.user)

        if self.remember_me.checkState() == Qt.Checked:
            configuration.set("AutoLogin","user",self.user_session.login)
            configuration.set("AutoLogin","password",self.password.text())
            configuration.save()

        elif configuration.get("AutoLogin","user") or configuration.get("AutoLogin","password"):
            configuration.set("AutoLogin","user","")
            configuration.set("AutoLogin","password","")
            configuration.save()
