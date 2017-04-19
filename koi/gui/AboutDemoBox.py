from PySide.QtCore import Qt,Slot
from PySide.QtGui import QVBoxLayout,QDialog,QDialogButtonBox,QLabel

from koi.gui.dialog_utils import TitleWidget
from koi.Configurator import configuration

class AboutDemoDialog(QDialog):
    def __init__(self,parent):
        super(AboutDemoDialog,self).__init__(parent)

        title = _("Welcome to {}...").format(configuration.get("Globals","name"))
        self.setWindowTitle(title)
        top_layout = QVBoxLayout()
        self.title_widget = TitleWidget(title,self)
        top_layout.addWidget(self.title_widget)


        text = QLabel(_("""
  <p>Welcome to the demo of {0}. This demo is fully functional and it
    comes with an example database. That should be enough to have a full
    tour of {0}.</p>
  <p>The first screen you'll see is a list of orders that were done
    in our imaginary company. If you double click on one of them,
    you'll see its details. From there on, you can browse around
    and test everything.</p>
  <p>As it is the demo version, all the data you'll change will be visible
    on internet. The demonstration database will be reased from time to time.</p>
  <p>Enjoy and feel free to contact us in case of problems :
    <a href="mailto:koimes@proximus.be">koimes@proximus.be</a></p>
""").format(configuration.get("Globals","name")))
        text.setTextFormat(Qt.RichText)
        text.setWordWrap(True)
        top_layout.addWidget(text)

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.Ok)

        top_layout.addWidget(self.buttons)
        self.setLayout(top_layout)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    @Slot()
    def accept(self):
        self.deleteLater()
        return super(AboutDemoDialog,self).accept()

    @Slot()
    def reject(self):
        self.deleteLater()
        return super(AboutDemoDialog,self).reject()
