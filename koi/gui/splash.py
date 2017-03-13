import sys
from PySide import QtGui
import time
 
class Frame(QtGui.QWidget):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.resize(600,500)
        size_ecran = QtGui.QDesktopWidget().screenGeometry()
        size_fenetre = self.geometry()
 
 
app = QtGui.QApplication(sys.argv)
pixmap = QtGui.QPixmap("horse.png")
splash = QtGui.QSplashScreen(pixmap)
splash.setMask(pixmap.mask())
splash.show()
app.processEvents()
time.sleep(5)
frame = Frame()
frame.show()
splash.finish(frame)
sys.exit(app.exec_())

