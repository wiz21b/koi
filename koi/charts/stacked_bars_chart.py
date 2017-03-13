import math

from PySide.QtCore import Qt,QTimer,Slot,QSize
from PySide.QtGui import QWidget,QPainterPath,QPainter,QConicalGradient,QBrush,QPen,QColor,QSizePolicy,QLabel,QVBoxLayout,QHBoxLayout,QPalette,QSizePolicy,QFrame
from PySide.QtCore import QSize

from koi.base_logging import mainlog
from koi.charts.lines_chart import LinesChart

class StackedBarsChart(LinesChart):
    def __init__(self,parent=None):
        super(StackedBarsChart,self).__init__(parent)


    def set_data(self,x_legends, legends,data):
        """ data : array of arrays
        """

        if not data or len(data) == 0:
            mainlog.debug("({}) set_data : no data".format(self.title))
            self.original_data = self.data = None
            return

        # We'll reverse the drawn series so that the
        # colors overlap nicely. Because of that we
        # also have to reverse the legend.

        # l = legends[0:len(legends)] # Copy
        # l.reverse() # in situ

        integrals = []
        for l in data:
            integrals.append( sum( [ (t or 0) * (t or 0) for t in l]))

        summed_series = []
        summed = [0] * len( data[0] )

        sorted_data = []
        sorted_legends = []
        for ndx,dummy in sorted( zip( range(len(integrals)), integrals), key=lambda a: - a[1]):
            l = data[ndx]
            summed = [x+ (y or 0) for x,y in zip(summed,l)]
            summed_series.append(summed)
            sorted_legends.append(legends[ndx])
            sorted_data.append(l)

        # The last element of summed series is the
        # serie which has the biggest "integral" (which
        # is the "tallest"), the one that is the lowest
        # on the graph.

        sorted_data.reverse()
        summed_series.reverse()
        sorted_legends.reverse()

        # Sorted data is not necessary for graph drawing but it makes
        # sure the "original_data" in lines_charts remains coherent
        # with its data. That's useeful when someone extracts data
        # from the lines charts object

        super(StackedBarsChart,self).set_data(x_legends, sorted_legends, sorted_data)


        if summed_series[0]:
            self.mini, self.maxi = self.clip_mini_maxi(0, max(summed_series[0]))
        else:
            self.mini, self.maxi = self.clip_mini_maxi(0, 0)
        #
        # self.mini = 0 #temporary fix

        self.data = summed_series


    def _compute_lengths(self, painter):

        if self.data:
            self._compute_screen_lengths(painter,self.mini,self.maxi,len(self.data[0]))
            if len(self.data[0]):
                self.bar_width = min(40,self.total_width / (len(self.data[0])*1.5))
            else:
                self.bar_width = 0

    def locate_serie(self, painter, x, y):
        """ Find the serie which is closes to the x,y point
        """

        screen_x_step = float(self.total_width) / (len(self.x_legends)-1)
        x_ndx = int(round(max(0,(x - self.margin - self.y_axis_label_width) / screen_x_step)))
        if x_ndx < 0:
            x_ndx = 0
        elif x_ndx >= len(self.data[0]):
            x_ndx = len(self.data[0]) - 1

        best_d = 999999999
        best_serie = None

        prev_y = self.y_base
        for serie in reversed(self.data):
            y0 = self.y_base - serie[x_ndx] * self.y_factor
            # mainlog.debug("{}: {} <= {} <= {}".format(self.data.index(serie), prev_y, y, y0))

            if prev_y >= y and y > y0:
                return serie,x_ndx
            else:
                prev_y = y0

        return None, None



    def _draw_selected_items_in_series(self, painter):
        pass

    def _item_coordinates(self, ndx_serie, ndx_in_serie):

        # x = float(ndx_in_serie) * self.x_factor
        # #mainlog.debug("ndx:{} x_fac:{}".format(ndx_in_serie,self.x_factor))

        # if ndx_in_serie == 0:
        #     x = float(self.x_base + x)
        # elif ndx_in_serie == len(serie) - 1:
        #     x = float(self.x_base + x - self.bar_width)
        # else:
        #     x = float(self.x_base + x - self.bar_width / 2)

        x = self.x_centers[ndx_in_serie] - self.bar_width/2

        serie = self.data[ndx_serie]
        y_top = float(serie[ndx_in_serie]) * self.y_factor

        if ndx_serie < len(self.data) - 1:
            serie_below = self.data[ ndx_serie + 1 ]
            y_below = float(serie_below[ndx_in_serie]) * self.y_factor
        else:
            y_below = 0

        return x, y_top, y_below


    def _draw_serie(self, painter, ndx_serie, color):

        last_item = len(self.data) - 1

        serie = self.data[ndx_serie]

        serie_below = [0] * len(self.data[last_item])
        if ndx_serie < len(self.data) - 1:
            serie_below = self.data[ ndx_serie + 1 ]

        fill_color = QColor(color)
        fill_color.setAlpha(64)
        brush = QBrush(fill_color)
        pen = QPen()
        pen.setCapStyle(Qt.SquareCap)
        pen.setColor(color)


        for i in range(len(serie)):
            x, y_top, y_below = self._item_coordinates(ndx_serie, i)

            qp = QPainterPath()

            h = float(y_top - y_below - 1)
            if h > 0:
                qp.addRect( x,
                            float(self.y_base-y_top),
                            float(self.bar_width),
                            h)

                painter.fillPath(qp,brush)

                if self.ndx_best_serie == ndx_serie and ( self.best_serie_intra_ndx is None or (self.best_serie_intra_ndx >= 0 and self.best_serie_intra_ndx == i)):
                    pen.setWidth(3)
                else:
                    pen.setWidth(1)

                painter.setPen(pen)
                painter.drawPath(qp)


        if ndx_serie == self.ndx_best_serie:
            fm = painter.fontMetrics()
            pen.setWidth(1)
            painter.setPen(pen)

            serie_below = None
            if ndx_serie < len(self.data) - 1:
                serie_below = self.data[ ndx_serie + 1 ]

            for i in range(len(serie)):
                if (self.best_serie_intra_ndx == i) or self.best_serie_intra_ndx is None:
                    x, y_top, y_below = self._item_coordinates(ndx_serie, i)
                    l_len = 15

                    v = serie[i]
                    if serie_below:
                        v = v - serie_below[i]
                    v = str(int(v))
                    bb = fm.boundingRect(v)

                    pen.setColor(color)
                    y = 0
                    if i < len(serie)-1:
                        # small diagonal going top, right
                        painter.drawLine(x + self.bar_width,
                                         self.y_base - y_top,
                                         x + self.bar_width + l_len,
                                         self.y_base - (y_top + l_len))

                        x = x + self.bar_width + l_len
                        y = y_top + l_len
                    else:
                        # small diagonal going top, left
                        painter.drawLine(x,
                                         self.y_base - y_top,
                                         x - l_len,
                                         self.y_base - (y_top - l_len))

                        x = x - l_len - bb.width()
                        y = y_top - l_len

                    bb.moveTo(int(x), int(self.y_base - y - bb.height()))

                    brush = QBrush(Qt.GlobalColor.red)
                    bb.adjust(-2,+2,+4,+4)

                    bb.adjust(-2,-2,+2,+2)
                    painter.fillRect(bb,brush)

                    bb.adjust(+2,+2,-2,-2)
                    painter.drawRect(bb)

                    pen.setColor(Qt.GlobalColor.white)
                    painter.setPen(pen)
                    painter.drawText(x,
                                     self.y_base - y ,
                                     str(int(v)))
