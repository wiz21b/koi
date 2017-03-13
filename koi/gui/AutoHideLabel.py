from PySide.QtCore import Qt
from PySide.QtGui import QLabel


class AutoHideLabel(QLabel):
    def __init__(self,parent=None):
        super(AutoHideLabel,self).__init__(parent)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)

    def setText(self, text):
        super(AutoHideLabel,self).setText(text)
        self.setHidden(not (text and text.strip()))