from PySide.QtCore import Qt,Slot,QLineF
from PySide.QtGui import QDialog, QDialogButtonBox, QCheckBox, QLineEdit, QFormLayout, QComboBox, QLabel
from PySide.QtGui import QVBoxLayout,QGraphicsScene, QGraphicsView, QGraphicsSimpleTextItem, QFont,QPolygonF,QGraphicsPolygonItem,QPainter,QBrush,QPen,QGraphicsItem,QMenu,QGraphicsLineItem,QGraphicsRectItem,QPainterPath,QLinearGradient,QGradient,QColor,QGraphicsPathItem
from PySide.QtCore import QPointF,QRect


class HooverBar(QGraphicsRectItem):

    def __init__(self,*args):
        super(HooverBar,self).__init__(*args)
        self.setAcceptHoverEvents(True)
        self.gi = None
        self.description = [ "" ]
        self.base_font = QFont()


    def hoverEnterEvent(self,event):
        super(HooverBar,self).hoverEnterEvent(event)

        if self.gi == None:
            self.gi = QGraphicsRectItem(0, 0, 100, 100)
            self.gi.setBrush(QBrush(QColor(0,64,0,192)))
            self.gi.setPen(QPen(Qt.transparent))
            self.gi.setPos(event.scenePos().x() + 20,event.scenePos().y() + 20)

            x = y = 10
            w = 0
            for t in self.description:
                description = QGraphicsSimpleTextItem()
                description.setFont(self.base_font)
                description.setBrush(QBrush(Qt.white))
                description.setText(t)
                description.setParentItem(self.gi)
                description.setPos(x,y)
                y += description.boundingRect().height()
                w = max(w,description.boundingRect().width())
            y += x
            w += 2*x

            self.gi.setRect(0,0,w,y)
            self.scene().addItem(self.gi)


    def hoverMoveEvent(self,event):
        super(HooverBar,self).hoverMoveEvent(event)

        # if self.gi:
        #     mainlog.debug("hoverMoveEvent GI pos={}-{}".format(self.gi.pos().x(),self.gi.pos().y()))
        # mainlog.debug("hoverMoveEvent pos={}-{}".format(event.scenePos().x(),event.scenePos().y()))
        if self.gi:
            self.gi.setPos(event.scenePos().x() + 20,event.scenePos().y() + 20)


    def hoverLeaveEvent(self,event):
        super(HooverBar,self).hoverLeaveEvent(event)

        if self.gi:

            # QtDoc : Removes the item item and all its children from the scene.
            #         The ownership of item is passed on to the caller

            self.gi.setParentItem(None)
            # self.scene().removeItem(self.gi)
            self.gi = None
            # mainlog.debug("hoverLeaveEvent -- done")
