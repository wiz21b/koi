from PySide.QtGui import QFrame, QVBoxLayout, QLayout


class InlineSubFrame(QFrame):
    def __init__(self,content_widget,parent=None):
        super(InlineSubFrame,self).__init__(parent)
        self.setFrameShape(QFrame.Panel)
        self.setFrameShadow(QFrame.Sunken)
        self.setObjectName("HorseRegularFrame")

        if isinstance(content_widget,QLayout):
            self.setLayout(content_widget)
        elif content_widget:
            vlayout2 = QVBoxLayout(None)
            vlayout2.addWidget(content_widget)
            self.setLayout(vlayout2)
