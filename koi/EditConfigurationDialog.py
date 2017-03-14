import re

from PySide.QtCore import Slot
from PySide.QtGui import QDialog, QDialogButtonBox, QCheckBox, QLineEdit
from PySide.QtGui import QVBoxLayout,QFormLayout

from koi.Configurator import configuration
from koi.gui.dialog_utils import TitleWidget,showWarningBox


class EditConfigurationDialog(QDialog):
    def __init__(self,parent):
        global configuration
        super(EditConfigurationDialog,self).__init__(parent)

        title = _("Preferences")
        self.setWindowTitle(title)
        self.title_widget = TitleWidget(title,self)

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.Ok)
        self.buttons.addButton( QDialogButtonBox.Cancel)

        self.font_select = QCheckBox()
        self.server_address = QLineEdit()

        form_layout = QFormLayout()
        form_layout.addRow( _("Fonts"), self.font_select)
        form_layout.addRow( _("Server's IP address"), self.server_address)

        top_layout = QVBoxLayout()
        top_layout.addWidget(self.title_widget)
        top_layout.addLayout(form_layout)
        top_layout.addWidget(self.buttons)

        self.setLayout(top_layout) # QWidget takes ownership of the layout
        self.buttons.accepted.connect(self.save_and_accept)
        self.buttons.rejected.connect(self.cancel)

        self._load_configuration(configuration)


    def _load_configuration(self,config):

        host_or_ip = ""
        if config:
            if config.get("DownloadSite","base_url"):
                r = re.compile('https?://([^:]+):.*')
                host_or_ip = r.match( config.get("DownloadSite","base_url")).groups()[0]

            elif config.database_url:
                r = re.compile('.*@([^:]+):.*')
                host_or_ip = r.match(config.database_url).groups()[0]

        self.server_address.setText( host_or_ip)
        self.font_select.setChecked(config.font_select)


    @Slot()
    def cancel(self):
        return super(EditConfigurationDialog,self).reject()

    @Slot()
    def save_and_accept(self):
        super(EditConfigurationDialog,self).accept()

        configuration.font_select = self.font_select.isChecked()
        configuration.set_server_network_address(self.server_address.text().strip(), overwrite=True)
        configuration.save()

        showWarningBox(_("Restart needed"),
                       _("The modifications you have requested needs a restart of the application to be applied. They will take effect when you restart the application."))

        self.deleteLater()
