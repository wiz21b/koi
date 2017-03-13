import math

from PySide.QtCore import Qt,QTimer,Slot,QSize, QRect
from PySide.QtGui import QWidget,QPainterPath,QPainter,QConicalGradient,QBrush,QPen,QColor,QSizePolicy,QLabel,QVBoxLayout,QHBoxLayout,QPalette,QSizePolicy,QFrame
from PySide.QtCore import QSize

from koi.base_logging import mainlog
from koi.charts.lines_chart import LinesChart

class BarsChart(LinesChart):
    def __init__(self,parent=None):
        super(BarsChart,self).__init__(parent)
        self._peak_values = None

    def set_data(self,x_legends,series_legends,data):
        assert data and (len(data) == 1), "Simple bar chart can only draw one serie ({})".format(data)
        super(BarsChart,self).set_data(x_legends, [''], data)
        # self._peak_values = None


    def _compute_lengths(self, painter):

        if self.data:
            self._compute_screen_lengths(painter,self.mini,self.maxi,len(self.data))
            if len(self.data):
                self.bar_width = min( 40, float(self.total_width) / (len(self.data[0])*1.5))
            else:
                self.bar_width = 0

    def _draw_peak_values(self, painter, labels):
        #mainlog.debug('_draw_peak_values : {}'.format(labels))
        text_pen = QPen()
        text_pen.setCapStyle(Qt.RoundCap)
        text_pen.setColor(Qt.GlobalColor.white) # alpha=255=fully opaque
        text_pen.setWidth(1)
        fm = painter.fontMetrics()

        rects = []

        painter.setPen(text_pen)

        # The sort allow to draw the peak values which are lower first.
        # We do that to visually connect a peak value to its bar in a
        # (hopefully) better way

        for i in sorted( range(len(labels)), key=lambda i:self._item_coordinates(i)[1]):
            x, y_top, y_below = self._item_coordinates(i)

            label = labels[i]

            w = fm.boundingRect(label).width()
            h = fm.boundingRect(label).height()

            r = QRect(self.x_centers[i] - int(w/2), self.y_base-y_top - 5 - h, w, h)

            i = 0
            while i < len(rects):
                old_r = rects[i]
                if r.intersect(old_r):
                    i = 0
                    # Move r atop old_r
                    r.translate(0, -(r.bottom() - old_r.y()) - 2)
                else:
                    i += 1
            rects.append(r)

            self._draw_box_under_text(painter, r.x(), r.y() + h,label)
            painter.drawText( r.x(), r.y() + h,label)

    def _item_coordinates(self, ndx_in_serie):

        serie = self.data[0]

        x = self.x_centers[ndx_in_serie] - self.bar_width/2
        y_top = float(serie[ndx_in_serie] or 0  ) * self.y_factor
        y_below = 0

        return x, y_top, y_below


    def set_peak_values(self, peak_values):
        #mainlog.debug("Setting peak values {}".format(peak_values))
        self._peak_values = peak_values

    def _draw_selected_items_in_series(self, painter):
        pass

    def _draw_serie(self, painter, ndx_serie, color):

        serie = self.data[ndx_serie]

        #mainlog.debug(serie)

        fill_color = QColor(color)
        fill_color.setAlpha(64)
        brush = QBrush(fill_color)
        pen = QPen()
        pen.setCapStyle(Qt.SquareCap)
        pen.setColor(color)

        qp = QPainterPath()
        painter.setPen(pen)

        for i in range(len(serie)):
            x, y_top, y_below = self._item_coordinates(i)

            h = max(1, float(y_top - y_below - 1))
            qp.addRect( x,
                        float(self.y_base-y_top),
                        float(self.bar_width),
                        h)

        painter.fillPath(qp,brush)
        painter.drawPath(qp)

        #mainlog.debug("Drawing peak values, juste before {}".format(self._peak_values))
        if self._peak_values:
            #mainlog.debug("Drawing peak values")
            self._draw_peak_values(painter, self._peak_values )
