import math

from PySide.QtCore import Qt,QTimer,Slot,QSize
from PySide.QtGui import QWidget,QPainterPath,QPainter,QConicalGradient,QBrush,QPen,QColor,QSizePolicy,QLabel,QVBoxLayout,QPalette
# from PySide.QtOpenGL import QGLWidget


class VuMeter(QWidget):

    UNIDIRECTIONAL = 1
    BIDIRECTIONAL = 2

    def __init__(self,direction=UNIDIRECTIONAL,parent=None):
        super(VuMeter,self).__init__(parent)
        self.direction = direction
        self.angle = 0
        self.target_angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.repaint) # timerUpdate)

        if direction == self.UNIDIRECTIONAL:
            self.set_gradient(1)
        elif direction == self.BIDIRECTIONAL:
            self.set_gradient(3)

        self.setMinimumSize(QSize(120,30))
        # self.setMinimumSizeHint(QSize(120,30))
        # self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding))





    def set_target(self,t):
        """ sets a new target for the arrow. The target is always
        between [-1,1] for bidirectional meters and [0,1] for
        unidirectional. If outside that interval, then it is
        clipped (-12.3 becomes -1.0)
        """

        if self.direction == self.UNIDIRECTIONAL:
            if t < -0.00:
                self.target_angle = -0.0
            elif t > 1.00:
                self.target_angle = 1.00
            else:
                self.target_angle = t
        elif self.direction == self.BIDIRECTIONAL:
            if t < -1.01:
                self.target_angle = -1.01
            elif t > 1.01:
                self.target_angle = 1.01
            else:
                self.target_angle = t

        self.timer.start(1000/50)

    def set_gradient(self,type):
        self.gradient_type = type


    def paintEvent(self,event):
        # print self.height()

        s = (self.target_angle - self.angle) * 0.09

        self.angle += s
        if math.fabs(self.angle - self.target_angle) < 0.001:
            self.angle = self.target_angle
            self.timer.stop()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)


        qp = QPainterPath()

        width = min(self.height(),(self.width() / 2))
        height = self.height()

        # center
        x = self.width() / 2

        big_radius = 1000
        y = big_radius + 10
        small_radius = big_radius - 15

        ac = math.atan(float(self.width()) / 2.0 / float(big_radius)) / math.pi * 180.0 * 0.95

        qp.arcMoveTo(x-big_radius,  y-big_radius,  2*big_radius,  2*big_radius,   90-ac)
        qp.arcTo(    x-big_radius,  y-big_radius,  2*big_radius,  2*big_radius,   90-ac,2*ac)
        qp.arcTo(    x-small_radius,y-small_radius,2*small_radius,2*small_radius, 90+ac,-2*ac)
        qp.arcTo(    x-big_radius,  y-big_radius,  2*big_radius,  2*big_radius,   90-ac,0)
        # qp.lineTo(x+big_radius,y)

        grange = ac*2.0 / 360.0

        # Centered on 0, starting at angle 90-ac, counterclockwise
        self.gradient = QConicalGradient ( 0,0, 90-ac-1 )

        if self.gradient_type == 1:
            self.gradient.setColorAt(0,   Qt.GlobalColor.red)
            self.gradient.setColorAt(0.1, Qt.GlobalColor.yellow)
            self.gradient.setColorAt(0.2, Qt.GlobalColor.green)
            self.gradient.setColorAt(0.5, Qt.GlobalColor.green)
            self.gradient.setColorAt(0.5, Qt.GlobalColor.green)
        elif self.gradient_type == 2:
            self.gradient.setColorAt(0,           Qt.GlobalColor.green)
            self.gradient.setColorAt(0.6*grange,  Qt.GlobalColor.yellow)
            self.gradient.setColorAt(1*grange,    Qt.GlobalColor.red)
        elif self.gradient_type == 3:
            self.gradient.setColorAt(0*grange,    Qt.GlobalColor.red)
            self.gradient.setColorAt(0.05*grange, Qt.GlobalColor.yellow)
            self.gradient.setColorAt(0.1*grange,  Qt.GlobalColor.green)
            self.gradient.setColorAt(0.4*grange,  Qt.GlobalColor.green)
            self.gradient.setColorAt(0.45*grange, Qt.GlobalColor.yellow)
            self.gradient.setColorAt(0.5*grange,  Qt.GlobalColor.red)

        self.gradient.setCenter(x,y)
        painter.fillPath(qp,QBrush(self.gradient))

        pen = QPen()
        pen.setColor(Qt.GlobalColor.black)
        pen.setWidth(max(1,int(1*self.width()/300)))
        painter.setPen(pen)
        painter.drawPath(qp)

        qp = QPainterPath()
        #qp.moveTo(0,0)
        #qp.lineTo(x,y)
        #qp.lineTo(self.width(),0)

        angle = 0
        ac = math.atan(float(self.width()) / 2.0 / float(big_radius)) * 0.95

        if self.direction == self.UNIDIRECTIONAL:
            angle = math.pi/2 + ac * (1 - 2*self.angle)

        elif self.direction == self.BIDIRECTIONAL:
            angle = math.pi/2 - self.angle * ac


        length = big_radius + 10
        short_length = small_radius - 10

        qp.moveTo(x + math.cos(angle) * short_length, y - math.sin(angle) * short_length)
        qp.lineTo(x + math.cos(angle) * length,       y - math.sin(angle) * length)
        pen = QPen()
        pen.setCapStyle(Qt.RoundCap)
        pen.setColor(Qt.GlobalColor.black)
        pen.setWidth(max(3,int(3*width/300)))
        painter.setPen(pen)
        painter.drawPath(qp)


        qp = QPainterPath()
        delta = self.width()*0.025

        # print "{}-{} {} c:{}".format(x,y,delta,math.cos(angle))
        qp.moveTo(x + delta + math.cos(angle) * short_length ,y + delta - math.sin(angle) * short_length)
        qp.lineTo(x + delta + math.cos(angle) * length,       y + delta - math.sin(angle) * length)
        pen = QPen()
        pen.setCapStyle(Qt.RoundCap)
        pen.setColor(QColor.fromRgbF(0, 0, 0, 0.3))
        pen.setWidth(max(3,int(3*width/300)))
        painter.setPen(pen)
        painter.drawPath(qp)

        qp = QPainterPath()
        qp.addRect(0,0,self.width(),self.height())
        painter.drawPath(qp)


class VuMeterWidget(QWidget):
    def __init__(self,direction=VuMeter.UNIDIRECTIONAL,parent=None):
        super(VuMeterWidget,self).__init__(parent)

        l = QVBoxLayout()
        l.setContentsMargins(0,0,0,0)
        self.vumeter = VuMeter(direction,self)
        self.value_label = QLabel()

        self.vumeter.setStyleSheet("background:white")
        self.vumeter.setMinimumHeight(30)
        self.vumeter.setMaximumHeight(30)
        self.vumeter.setMinimumWidth(150)
        self.vumeter.setMaximumWidth(150)

        l.addWidget( self.vumeter,0,Qt.AlignHCenter)
        l.addWidget( self.value_label,0,Qt.AlignHCenter)

        self.setLayout(l)

    def set_values(self,vumeter,real):
        self.value_label.setText(u"<h2><b>{}</b></h2>".format(real))
        self.vumeter.set_target(vumeter)



if __name__ == "__main__":
    import sys
    from PySide.QtGui import QMainWindow,QApplication

    app = QApplication(sys.argv)
    window = QMainWindow()
    vu = VuMeterWidget(VuMeter.UNIDIRECTIONAL)
    vu.vumeter.set_gradient(2)
    vu.set_values(0,"00.0")
    window.setCentralWidget(vu)
    window.show()
    app.exec_()
