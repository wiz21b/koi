from PySide.QtCore import Slot,Qt,QModelIndex,QPoint
from PySide.QtGui import QPainter,QWidget,QPen,QPolygon,QBrush,QColor



class BigArrow(QWidget):
    def __init__(self,parent):
        super(BigArrow,self).__init__(parent)
        self.y = -1
        self.end_y = 100
        self.right_top = 30
        self.setMinimumWidth(20)

        self.left_top = 0
        self.left_bottom = 0
        self.right_top = 0
        self.right_bottom = 0

        self.left_view = self.right_view = self.right_model = None

        self.right_model = None


    def connect_to_right(self,view):
        if self.right_model != view.model():
            if self.right_model:
                self.right_model.rowsInserted.disconnect(self._right_model_changed)
                self.right_model.rowsRemoved.disconnect(self._right_model_changed)

            self.right_view = view
            self.right_model = view.model() # Sometimes the view's model changes

            self.right_model.rowsInserted.connect(self._right_model_changed)
            self.right_model.rowsRemoved.connect(self._right_model_changed)
            self.repaint()


    def connect_to_left(self,view):
        if self.left_view != view:
            if self.left_view:
                self.left_view.selectionModel().currentChanged.disconnect(self._cursor_moved_left_pane) # FIXME Clear ownership issue
                self.left_view.verticalScrollBar().valueChanged.disconnect(self._left_slider_moved)

            self.left_view = view

            self.left_view.selectionModel().currentChanged.connect(self._cursor_moved_left_pane) # FIXME Clear ownership issue
            self.left_view.verticalScrollBar().valueChanged.connect(self._left_slider_moved)
            self.repaint()


    @Slot(int)
    def _left_slider_moved(self,value):
        self.repaint()

    @Slot(QModelIndex,QModelIndex)
    def _cursor_moved_left_pane(self, current, previous):
        if current.isValid() and (previous is None or current.row() != previous.row()) and current.row() != -1:
            self.repaint()

    @Slot(QModelIndex,int,int)
    def _right_model_changed(self,parent,start,end):
        self.repaint()

    def paintEvent(self, pe):
        if self.left_view and self.right_view and self.right_view.model():
            vr = self.left_view.visualRect(self.left_view.currentIndex())

            self.left_top = self.mapFromGlobal(self.left_view.viewport().mapToGlobal(vr.topRight())).y()
            self.left_bottom = self.mapFromGlobal(self.left_view.viewport().mapToGlobal(vr.bottomRight())).y()

            vr_top = self.right_view.visualRect( self.right_view.model().index(0,0))
            vr = self.right_view.visualRect( self.right_view.model().index( self.right_view.model().rowCount()-1,0))

            self.right_top = self.mapFromGlobal(self.left_view.viewport().mapToGlobal(vr_top.topLeft())).y()
            self.right_bottom = self.mapFromGlobal(self.left_view.viewport().mapToGlobal(vr.bottomLeft())).y()

            w = self.minimumWidth() - 1

            p = QPainter(self)
            p.setBrush(QBrush(QColor(210, 255, 210)))

            pen = QPen()
            pen.setColor(Qt.transparent)
            p.setPen(pen)

            poly = QPolygon()
            poly.append(QPoint(0,self.left_top))
            poly.append(QPoint(w,self.right_top))
            poly.append(QPoint(w,self.right_bottom))
            poly.append(QPoint(0,self.left_bottom))
            p.drawConvexPolygon(poly)

            p.setRenderHint(QPainter.Antialiasing)
            pen.setColor(Qt.GlobalColor.black)
            pen.setWidth(2)
            p.setPen(pen)
            p.drawLine(0,self.left_top,w,self.right_top)
            p.drawLine(0,self.left_bottom,w,self.right_bottom)
