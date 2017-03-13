import math

from PySide.QtCore import Qt,QTimer,Slot,QSize
from PySide.QtGui import QWidget,QPainterPath,QPainter,QConicalGradient,QBrush,QPen,QColor,QSizePolicy,QLabel,QVBoxLayout,QHBoxLayout,QPalette,QSizePolicy,QFrame
from PySide.QtCore import QSize

from koi.base_logging import mainlog
from koi.charts.lines_chart import LinesChart

class StackedLinesChart(LinesChart):
    def __init__(self,parent=None):
        super(StackedLinesChart,self).__init__(parent)


    def set_data(self,x_legends, legends,data):
        """ data : array of arrays
        """

        # We'll reverse the drawn series so that the
        # colors overlap nicely. Because of that we
        # also have to reverse the legend.

        # l = legends[0:len(legends)] # Copy
        # l.reverse() # in situ

        integrals = []
        for l in data:
            integrals.append( sum( map( lambda t:t*t, l)))

        summed_series = []
        summed = [0] * len( data[0] )

        sorted_legends = []
        for ndx,dummy in sorted( zip( range(len(integrals)), integrals), lambda a,b: - cmp(a[1],b[1])):
            l = data[ndx]
            summed = [x+y for x,y in zip(summed,l)]
            summed_series.append(summed)
            sorted_legends.append(legends[ndx])

        summed_series.reverse()
        sorted_legends.reverse()


        super(StackedLinesChart,self).set_data(x_legends, sorted_legends, data)
        self.maxi = max(summed_series[0])
        self.mini = 0 #temporary fix


        # FIXME not very nice that swap....
        self.original_data = self.data

        self.data = summed_series


    def _compute_lengths(self, painter):

        self._compute_screen_lengths(painter,self.mini,self.maxi,len(self.data[0]))



    def _draw_serie(self, painter, ndx_serie, color):

        last_item = len(self.data) - 1

        serie = self.data[ndx_serie]

        serie_below = [0] * len(self.data[last_item])
        if ndx_serie < len(self.data) - 1:
            serie_below = self.data[ ndx_serie + 1 ]

        qlp = QPainterPath() # The top line path
        qfp = QPainterPath() # the filled region path


        x = float(0) * self.x_factor
        y = serie[0] * self.y_factor
        qlp.moveTo(self.x_base + x,self.y_base - y)
        qfp.moveTo(self.x_base + x,self.y_base - y)

        for i in range(1,len(serie)):
            x = float(i) * self.x_factor
            y = float(serie[i]) * self.y_factor

            #print i,y

            qlp.lineTo(self.x_base + x, self.y_base-y)
            qfp.lineTo(self.x_base + x, self.y_base-y)



        for i in reversed(range(0,len(serie_below))):
            x = float(i) * self.x_factor
            y = float(serie_below[i]) * self.y_factor

            qfp.lineTo(self.x_base + x, self.y_base-y)

        qfp.closeSubpath()


        fill_color = QColor(color)
        fill_color.setAlpha(64)
        brush = QBrush(fill_color)
        painter.fillPath(qfp,brush)

        pen = QPen()
        pen.setColor(color)
        if ndx_serie == self.ndx_best_serie:
            pen.setWidth(6)
        else:
            pen.setWidth(2)

        painter.setPen(pen)

        painter.drawPath(qlp)
