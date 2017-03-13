from datetime import date

from PySide.QtCore import Qt,Slot
from PySide.QtGui import QVBoxLayout,QTextEdit,QTextBrowser,QDialog,QDialogButtonBox,QLabel

from koi.gui.dialog_utils import TitleWidget
from koi.Configurator import configuration

from koi.legal import copyright_years, copyright, license


class AboutDialog(QDialog):
    def __init__(self,parent):
        super(AboutDialog,self).__init__(parent)

        title = _("About {}...").format(configuration.get("Globals","name"))
        self.setWindowTitle(title)
        top_layout = QVBoxLayout()
        self.title_widget = TitleWidget(title,self)
        top_layout.addWidget(self.title_widget)


        text = QLabel(u"{}<br/>Version : {}<br/><br/>".format(copyright(), str(configuration.this_version)) +
                      _("""This program is given to you with a few important
freedoms and duties as specified in the license below. <b>We believe they will help to make a better world</b>. They are
also <b>legally binding</b> (see Free Software Foundation's website), so make sure you read the license
carefully. We give you the right to
<ul>
<li>run the program,</li>
<li>inspect it to make sure it is safe to use,</li>
<li>modify it to suit your needs,</li>
<li>distribute copies of it,</li>
</ul>
as long as you give those freedoms and duties to anybody you give this program to.
"""))
        text.setTextFormat(Qt.RichText)
        text.setWordWrap(True)
        # text.setMaximumWidth(400)
        top_layout.addWidget(text)

        browser = QTextBrowser()
        browser.setLineWrapMode(QTextEdit.NoWrap)
        browser.setPlainText( license() )
        browser.setMinimumWidth(browser.document().documentLayout().documentSize().toSize().width())
        browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        top_layout.addWidget(browser)

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.Ok)

        top_layout.addWidget(self.buttons)
        self.setLayout(top_layout)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    @Slot()
    def accept(self):
        self.deleteLater()
        return super(AboutDialog,self).accept()

    @Slot()
    def reject(self):
        self.deleteLater()
        return super(AboutDialog,self).reject()
