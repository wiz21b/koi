from PySide.QtCore import Qt,Signal
from PySide.QtCore import QSize
from PySide.QtGui import QWidget,QSizePolicy,QLabel,QVBoxLayout,QHBoxLayout,QFrame,QSizePolicy


class ChartWidget(QWidget):
    """ A widget representing a chart.

     The data are set with the set_data method """

    clicked = Signal()

    def mouseDoubleClickEvent ( self, event):
        self.clicked.emit()

    def __init__(self,parent,chart,caption=""):
        super(ChartWidget,self).__init__(parent)

        self.setStyleSheet("background:black")

        l = QVBoxLayout()
        l.setContentsMargins(0,0,0,0)
        self.chart = chart
        self.chart.set_title(caption)
        self.value_label = QLabel(caption)

        # self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.MinimumExpanding,QSizePolicy.Policy.MinimumExpanding))

        # self.chart.setMinimumSize(QSize(100,50))
        # self.chart.setSizePolicy(QSizePolicy(QSizePolicy.Policy.MinimumExpanding,QSizePolicy.Policy.MinimumExpanding))
        # self.chart.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.chart.setMouseTracking(True)

        h = QHBoxLayout()
        h.addWidget(self.chart)

        l.addLayout( h)
        # l.addWidget( self.value_label,0,Qt.AlignHCenter)

        self.setLayout(l)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_data(self,x_legends,legends,data):
        self.chart.set_data(x_legends,legends,data)

