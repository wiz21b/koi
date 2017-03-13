from PySide.QtCore import QPoint, QRect, QTimer, Qt
from PySide.QtGui import QScrollArea


class PopupWidget(QScrollArea):
    Steps = 10

    def leaveEvent(self,event):
        self.timer.stop()
        self.y = 0
        self.hide()

    def showEvent(self,event):
        self.y = 0
        self.regeom()
        # self.timer.setSingleShot(True)
        self.timer.start(10)

    def regeom(self):
        if self.y > self.Steps:
            self.timer.stop()
            return
        else:
            self.y += 1

        w = self.data.sizeHint().width()

        ppos = self.parent.mapToGlobal( QPoint(0,0))
        x_base = ppos.x() # + self.parent.width()

        pos = self.pos()

        x_max = self.parent.window().pos().x() + self.parent.window().width()

        if x_base + w > x_max:
            x_base = x_max - w

        self.setGeometry( QRect(x_base,
                                pos.y(),
                                w,
                                int(self.data.sizeHint().height() / float(self.Steps) * float(self.y) - 3)))


    def __init__(self,widget,parent=None):
        super(PopupWidget,self).__init__(None)

        self.parent = parent
        self.data = widget
        self.data.setParent(self)

        self.timer = QTimer()
        self.timer.timeout.connect(self.regeom)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(self.data)
        self.setWidgetResizable(True)

        self.setWindowFlags(Qt.Popup)