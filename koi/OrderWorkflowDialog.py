import math

from PySide.QtCore import Qt,Slot
from PySide.QtGui import QDialog, QDialogButtonBox
from PySide.QtGui import QVBoxLayout,QGraphicsScene, QGraphicsView, QGraphicsSimpleTextItem, QFont,QPolygonF,QGraphicsPolygonItem,QPainter,QBrush,QPen,QGraphicsItem
from PySide.QtCore import QPointF

from koi.gui.dialog_utils import TitleWidget


if __name__ == "__main__":
    import sys
    from PySide.QtGui import QApplication

    from koi.base_logging import mainlog,init_logging
    from koi.Configurator import init_i18n,load_configuration,configuration

    init_logging()
    init_i18n()
    load_configuration()

from koi.db_mapping import OrderStatusType


def helper(a,b,ang):
    if 0 <= ang <= math.pi/2:
        z = a/b * math.tan( ang )
        return math.atan( z*z)
    elif math.pi/2 <= ang <= math.pi:
        ang = math.pi - ang
        return math.pi - math.atan( math.pow( a/b * math.tan( ang ),2))

def to_squircle_angle(a,b,ang):
    """ Taks a regular angle (radian, from -PI to + PI) and converts
    it to a squircle's equation parameter that will map onto tha angle. """

    if ang >= 0:
        return helper(a,b,ang)
    else:
        return - helper(a,b,-ang)

def dist(dx,dy = None):
    if dy is not None:
        return math.sqrt(dx*dx + dy*dy)
    else:
        return math.sqrt(dx[0]*dx[0] + dx[1]*dx[1])

class MyQGraphicsSimpleTextItem(QGraphicsSimpleTextItem):
    def __init__(self,state,dialog):
        super(MyQGraphicsSimpleTextItem,self).__init__(state.description)
        self.state = state
        self.dialog = dialog

    def mouseDoubleClickEvent(self,event): # QGraphicsSceneMouseEvent
        self.dialog.save_and_accept()



class OrderWorkflowDialog(QDialog):

    def _makeArrow( self, ra, rb, both_ways=True):

        ca = QPointF( ra.x() + float(ra.width()) / 2.0, ra.y() + float(ra.height()) / 2.0)
        cb = QPointF( rb.x() + rb.width() / 2.0, rb.y() + rb.height() / 2.0)

        dx = cb.x() - ca.x()
        dy = cb.y() - ca.y()
        d = dist(dx,dy)


        a = math.atan2(float(dy),float(dx)) # The result is between -pi and pi

        # ra_rad = dist(ra.width() / 2, ra.height() / 2)
        # rb_rad = dist(rb.width() / 2, rb.height() / 2)

        x,y = squircle(ra.width() / 2, ra.height() / 2, to_squircle_angle(ra.width() / 2, ra.height() / 2,a))
        ra_rad = dist(x,y) + 10
        # painter.drawLine(ca,QPoint(ca.x() + x, ca.y() + y))

        na = a
        if a < 0:
            na += math.pi
        else:
            na -= math.pi

        x,y = squircle(float(rb.width()) / 2.0, float(rb.height()) / 2.0, to_squircle_angle(float(rb.width()) / 2.0, float(rb.height()) / 2.0,na))
        rb_rad = dist(x,y)+10

        # ra_rad = rb_rad = 0


        # painter.drawLine(ca,cb)
        # painter.drawRect(ra)
        # painter.setPen(Qt.GlobalColor.red)
        # painter.drawRect(rb)
        # painter.setPen(Qt.GlobalColor.black)

        # for t in range(100):
        #     ang = 6.28/100.0*float(t)
        #     x,y = squircle( 200,50,ang)
        #     painter.drawPoint(300 + x,100 + y)

        qp = QPolygonF()
        h = 5

        v = []
        v.append(QPointF(ra_rad,0))

        if not both_ways:
            v.append(QPointF(ra_rad,-h/2))
        else:
            v.append(QPointF(ra_rad + 2*h,-2*h))
            v.append(QPointF(ra_rad + 2*h,-h/2))


        v.append(QPointF(d - rb_rad - 2*h,-h/2))
        v.append(QPointF(d - rb_rad - 2*h,-2*h))
        v.append(QPointF(d - rb_rad, 0))
        v.append(QPointF(d - rb_rad - 2*h,+2*h))
        v.append(QPointF(d - rb_rad - 2*h,+h/2))

        if not both_ways:
            v.append(QPointF(ra_rad,+h/2))
        else:
            v.append(QPointF(ra_rad + 2*h,+h/2))
            v.append(QPointF(ra_rad + 2*h,+2*h))

        v.append(QPointF(ra_rad,0))

        p = QPolygonF(v)
        item = QGraphicsPolygonItem(p)
        item.translate(ca.x(),ca.y())
        item.rotate(math.degrees(a))
        return item


    def _drawNodes(self,scene,selected_state,initial_state):
        for i in scene.items():
            scene.removeItem(i)

        pos = dict()

        sx = 1
        sy = 1
        if configuration.font_select:
            sx = sx * 2
            sy = sy

        pos[OrderStatusType.preorder_definition] = (200*sx,200*sy)
        pos[OrderStatusType.order_definition] = (10*sx,300*sy)
        pos[OrderStatusType.order_ready_for_production] = (300*sx,300*sy)
        pos[OrderStatusType.order_production_paused] = (200*sx,550*sy)
        pos[OrderStatusType.order_completed] = (400*sx,600*sy)
        pos[OrderStatusType.order_aborted] = (10*sx,600*sy)

        mainlog.debug("_drawNodes : selected_state {}".format(selected_state))
        mainlog.debug("_drawNodes : initial_state {}".format(initial_state))

        for org in OrderStatusType.symbols():
            x,y = pos[org]

            item = QGraphicsSimpleTextItem(org.description)

            if (selected_state and org in OrderStatusType.next_states(selected_state)) or org == initial_state or org == selected_state:
                item = MyQGraphicsSimpleTextItem(org, self)
                item.setFlags( item.flags() | QGraphicsItem.ItemIsSelectable)

                if org == selected_state:
                    mainlog.debug("Preselcting {}".format(org))
                    item.setSelected(True)

            item.setFont(self.thinfont)
            item.setPos(x,y)
            scene.addItem(item)

            pos[org] = item.boundingRegion( item.sceneTransform()).boundingRect()

            # scene.addRect(pos[org])


        g_orgs = dict()
        for org in OrderStatusType.symbols():
            g_orgs[org] = OrderStatusType.next_states(org)


        # Draw all arrows which don't end up or leave the selected_state
        drawn = []
        for org,dests in g_orgs.iteritems():
            for dest in dests:
                if selected_state != org and ((org,dest) not in drawn) and ((dest,org) not in drawn):
                    # If an arrow must have two directions, we draw it
                    # like that directly.
                    item = self._makeArrow( pos[org],pos[dest],dest in g_orgs and org in g_orgs[dest])
                    item.setPen(self.grey_pen)
                    scene.addItem( item)
                    drawn.append((org,dest))



        if initial_state:
            scene.addRect(pos[initial_state])

        if selected_state:
            for dest in OrderStatusType.next_states(selected_state):
                item = self._makeArrow( pos[selected_state],pos[dest],False)
                item.setBrush(QBrush(Qt.green))
                scene.addItem( item)
                drawn.append((org,dest))

    @Slot()
    def selectionChanged(self):
        pass

    def __init__(self,parent):
        global configuration
        super(OrderWorkflowDialog,self).__init__(parent)

        self.grey_pen = QPen(Qt.gray)

        title = _("Order workflow")
        self.setWindowTitle(title)
        self.title_widget = TitleWidget(title,self)

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.Ok)
        self.buttons.addButton( QDialogButtonBox.Cancel)

        self.thinfont = QFont()
        if configuration.font_select:
            self.thinfont.setPointSize(self.thinfont.pointSize()*2)

        self.scene = QGraphicsScene()
        self.scene.selectionChanged.connect(self.selectionChanged)

        self.view = QGraphicsView(self)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setScene(self.scene)

        top_layout = QVBoxLayout()
        top_layout.addWidget(self.title_widget)
        top_layout.addWidget(self.view)
        top_layout.addWidget(self.buttons)

        self.setLayout(top_layout) # QWidget takes ownership of the layout
        self.buttons.accepted.connect(self.save_and_accept)
        self.buttons.rejected.connect(self.cancel)

        self.initial_state = None
        self.selected_state = None
        self._drawNodes(self.scene,self.selected_state,self.initial_state)

    def set_selected_state(self,selected_state,initial_state):
        mainlog.debug("selected_state {}".format(selected_state))
        mainlog.debug("initial_state {}".format(initial_state))

        self.initial_state = initial_state
        self.selected_state = selected_state
        self._drawNodes(self.scene,selected_state,self.initial_state)


    @Slot()
    def cancel(self):
        return super(OrderWorkflowDialog,self).reject()

    @Slot()
    def save_and_accept(self):
        super(OrderWorkflowDialog,self).accept()

        s = self.scene.selectedItems()
        if s:
            # In cas there are more than one item selected,
            # we pick the first one (arbitrarily)
            self.selected_state = s[0].state
        else:
            self.selected_state = self.initial_state



def squircle(width, height, ang):

    cos = math.cos(ang)
    x = math.copysign(float(width) * math.sqrt(math.fabs(cos)), cos)

    sin = math.sin(ang)
    y = math.copysign(float(height) * math.sqrt(math.fabs(sin)), sin)

    return x,y

"""

polar = atan(y/x)
polar = atan(b*sqrt(sin(ang)) / a*sqrt(cos(ang)))
tan(polar) = b*sqrt(sin(ang)) / a*sqrt(cos(ang))
tan(polar) * a/b = sqrt(sin(ang)) / sqrt(cos(ang))
pow(tan(polar) * a/b) = tan(ang)
atan( pow(tan(polar) * a/b)) = ang

"""

if __name__ == "__main__":
    app = QApplication(sys.argv)
    d = OrderWorkflowDialog(None)
    # d.set_selected_state(OrderStatusType.order_ready_for_production)
    d.set_selected_state(OrderStatusType.order_definition, OrderStatusType.order_ready_for_production)
    d.exec_()
    print( d.selected_state)
