import math
from datetime import date

from PySide.QtCore import Qt,QTimer,Slot,QSize,QRect
from PySide.QtGui import QPainterPath,QPainter,QBrush,QPen,QColor,QFrame,QFont

from koi.base_logging import mainlog

class LinesChart(QFrame):

    graph_colors = [Qt.GlobalColor.white, Qt.GlobalColor.blue, Qt.GlobalColor.red, Qt.GlobalColor.darkRed, Qt.GlobalColor.green, Qt.GlobalColor.darkGreen, Qt.GlobalColor.yellow]


    def __init__(self,parent=None):
        super(LinesChart,self).__init__(parent)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.timer_tick) # timerUpdate)
        self.timer.start(400)
        self.timer_ticks = 0

        self.gride_lines_number = 0
        self._create_pens()
        self.stacked = False
        self.title = "Sic transit gloria mundi"
        self.title_font = self.thinfont = QFont("Arial",10,QFont.Bold)

        self.margin = 10
        self.total_width = 0
        self.legend_labels_bounding_boxes = []

        self.ndx_best_serie = -1
        self.best_serie_intra_ndx = None
        self.no_draw = True # Set to True if we can't draw (because of numerical problems or non initialized data for example)
        self.data = None

        # When set to true, if the x axis values are dates
        # then, they'll be shown as month (so intead of 31/12/2014,
        # you'll get something like 12/14)
        self.x_axis_as_months = False
        self.set_mini_maxi(None, None)
        self.set_horizontal_ruler(None,None)

        self.forced_maxi = None
        self.forced_mini = None

    def set_title(self,t):
        self.title = t

    def timer_tick(self):
        self.timer_ticks += 1
        self.update()

    def set_data(self,x_legends, legends,data):
        """ Sets the data to draw.

        :param x_legends: Labels to write on the X axis
        :param series_legends: Name of the various series.
        :param data: a list of series; each serie is a list of tuples : (x_coordinate, value).
        :return:
        """

        mainlog.debug("({}) line_chart : set_data".format(self.title))
        mainlog.debug(data)
        if len(legends) != len(data):
            raise Exception("The number of legends for data series ({}) is different than the number of series ({})".format(len(legends),len(data)))

        self.legends = legends
        self.x_legends = x_legends
        self.original_data = self.data = data

        # Compute the smallest and greatest value of the dataset

        # if self.forced_maxi == None and self.forced_mini == None:
        self.mini = 9999999999
        self.maxi = 0

        for l in self.data:
            if l:
                # There can be some None in the list, or the list might
                # even by made only of None's !
                filtered = [x or 0 for x in l]
                if filtered:
                    self.mini = min(min( filtered),self.mini)
                    self.maxi = max(max( filtered),self.maxi)

        self.mini, self.maxi = self.clip_mini_maxi( self.mini, self.maxi)
        # if self.mini == self.maxi and self.forced_mini != None and self.forced_maxi != None:
        #     self.mini, self.maxi = self.forced_mini, self.forced_maxi

        # Compute the sum of each "column" of data

        summed = [0] * len( data[0] )
        for l in data:
            if l:
                summed = [(x or 0) + (y or 0) for x,y in zip(summed,l)]
        self.summed = summed

        self.highlighted_serie = None


    def clip_mini_maxi(self, mini, maxi):
        mainlog.debug("({}) Clipping {} {}, forced:{} {}".format( self.title, type(mini), type(maxi), type(self.forced_mini), type(self.forced_maxi)))
        if self.forced_mini != None and self.forced_maxi != None:
            mainlog.debug("Clipping to forced values {} {}".format( self.forced_mini, self.forced_maxi))
            mini, maxi = min( mini, self.forced_mini), max( maxi, self.forced_maxi)
            return mini, maxi
        else:
            mainlog.debug("Clipping no clipping :{} {}".format(mini, maxi))
            return mini, maxi

    def sizeHint(self):
        # QSizePolicy.expanding doesn't exapand as much as I want,
        # so I push myself :-)
        return QSize(4000,300)

    def _compute_legend_lengths(self, painter, legends):

        self.max_legend_label_width = 0
        fm = painter.fontMetrics()
        for label in legends:
            self.max_legend_label_width = max(fm.boundingRect(label).width(),
                                              self.max_legend_label_width)

        self.space_between_legend_labels = 10
        self.max_legend_label_width += self.space_between_legend_labels # a bit of room

        self.legend_labels_per_line = int(self.total_width / self.max_legend_label_width)
        if self.total_width % self.max_legend_label_width > 0:
            self.legend_labels_per_line += 1

        self.legend_lines = len(legends) / self.legend_labels_per_line
        if len(legends) % self.legend_labels_per_line > 0:
            self.legend_lines += 1

        self.legend_height = self.text_height * self.legend_lines


    def _compute_x_centers(self, nb_x, available_width):

        #  ----------------------------- 29
        #  __1__ __2__ __3__ __4__ __5__
        # 29/5 = 5.8
        #   2.9,  8.7, 14.5, 20.3, 26.1

        # mainlog.debug("_compute_x_centers({}, {})".format(nb_x, available_width))

        if nb_x == 0:
            return []

        step_width = float(available_width) / float(nb_x)

        all_x = []
        for i in range(nb_x):
            all_x.append( self.x_base + step_width/2 + i * step_width )

        return all_x

    def _compute_screen_lengths(self,painter,mini,maxi,x_steps):
        """

        :param painter: QPainter
        :param mini: Minimum value that will be displayed on the Y axis
        :param maxi: Maximum value that will be displayed on the Y axis
        :param x_steps: Number of steps on the X axis
        :return:
        """

        if x_steps > 0:
            assert 0 <= mini <= maxi, "We should have 0 <= {} <= {}".format(mini, maxi)


        # Measure regular font height
        fm = painter.fontMetrics()
        h = fm.boundingRect("A9j").height()
        self.text_height = h

        # Measure y_axis labels max width
        self.y_axis_label_width = fm.boundingRect(str(int(self.maxi))+"M").width()

        # Measure title font height
        base_font = painter.font()
        painter.setFont(self.title_font)
        r = QRect(self.margin,0,self.width() - 2*self.margin,self.height())
        bb = painter.boundingRect(r,Qt.AlignLeft+Qt.TextWordWrap,self.title)
        painter.setFont(base_font)


        self.total_width = self.width() - 2*self.margin - self.y_axis_label_width

        # Lengths of the legend
        self._compute_legend_lengths(painter, self.legends)
        self.legend_y_start = self.margin + bb.height()

        # Distance between top of widget and top of chart
        self.yoffset = self.margin + bb.height() + self.legend_height

        self.total_height = self.height() - self.yoffset - self.margin - self.text_height

        # print total_width,total_height

        # Go from actual value to a screen position (without offset, see x/y_base)
        d = max(maxi,maxi - mini)
        self.no_draw = self.total_width < 1 or self.total_height < 1 or d <= 0
        if self.no_draw:
            mainlog.debug("No draw because d:{} (mini {}, maxi {}) total_width:{} total_height:{}".format(d, mini, maxi, self.total_width, self.total_height ))
            return

        self.y_factor = float(min(self.total_height,self.total_width)) / d
        self.y_factor = float(self.total_height) / d

        if x_steps <= 3:
            self.x_factor = float(self.total_width) / float(3-1)

        elif x_steps > 1:
            self.x_factor = float(self.total_width) / float(x_steps - 1)

        else:
            self.x_factor = 0

        # self.x_axis_offset = max(0, (self.total_width -  x_steps * self.x_factor)/2)
        self.x_axis_offset = 0

        # print self.maxi,self.mini,self.y_factor

        # The axis positions
        self.y_base = float(maxi) * self.y_factor + self.yoffset
        self.x_base = self.margin + self.y_axis_label_width + self.x_axis_offset



        # Now we compute the vertical axis step size.
        # Remember the graph is fit in the window

        # First we want each step to display a human firendly
        # value (so, no 12.3462, 24.68... but 10, 20, 30...)
        # And we start with an arbitrary number of steps

        # if self.mini == self.maxi:
        #     steps = 6
        #     self.rounded_step_size = int(10 ** round(math.log10(self.maxi / steps))) or 1
        # else:
        #     steps = min(6, self.maxi - self.mini) or 1
        #     self.rounded_step_size = int(10 ** round(math.log10( (self.maxi - self.mini) / steps))) or 1
        #
        #
        # if self.rounded_step_size > 1:
        #
        #     # MAke sure the step size is small enough to have "steps" steps.
        #
        #     while int(self.maxi / self.rounded_step_size) < steps:
        #         self.rounded_step_size = int(self.rounded_step_size / 2)
        #
        #     # Second, make sure the step is tall enough to let the text in
        #
        #     while h > self.rounded_step_size * self.y_factor:
        #         # mainlog.debug("{} > {} * {}".format(h, self.rounded_step_size, self.y_factor))
        #         self.rounded_step_size = self.rounded_step_size * 2
        #
        # if self.maxi > 0:
        #     step_size = (10 ** int(math.log10(self.maxi - 0.00001))) or 1
        #     mainlog.debug("Maxi={} Actual {}, new {}".format(self.maxi,self.rounded_step_size,step_size))
        #     self.rounded_step_size = step_size
        # else:
        #     mainlog.debug("zero")

        log10 = math.log10( self.maxi)

        # This fix to make sure there is more than one step
        # in case the maxi is aligned on a power of 10.
        # In this case there will be 10 steps.

        if log10 - int(log10) == 0:
            fix = -1
        else:
            fix = 0

        step_size = 10 ** int(math.floor(log10) + fix)

        # If we rely only on power of 10, we might end up
        # with a small number of steps (e.g. 2). That is
        # correct but unpleasant to look at. To avoid
        # this, I increase the size of steps to reach
        # a minimum number of steps.
        # Dividing by two a power of 10 make sure we'll keep
        # "human readable" steps (1/2, 1/4, 1/8,...)

        MINIMUM_NUMBER_OF_STEPS = 4

        while self.maxi / step_size < MINIMUM_NUMBER_OF_STEPS:  # number of steps < MINIMUM_NUMBER_OF_STEPS
            step_size = step_size / 2

        # Second, make sure the step is tall enough to let the text in

        while h > step_size * self.y_factor:
            # mainlog.debug("{} > {} * {}".format(h, self.rounded_step_size, self.y_factor))
            step_size = step_size * 2

        self.rounded_step_size = step_size

        self.x_centers = self._compute_x_centers(len(self.data[0]), self.total_width)

    def _compute_lengths(self,painter):
        self._compute_screen_lengths(painter,self.mini,self.maxi,len(self.data[0]))


    def leaveEvent( self, q_leave_event):
        if self.ndx_best_serie:
            self.ndx_best_serie = -1
            self.update()


    def leaveEvent(self, event):
        self.ndx_best_serie = None
        self.best_serie_intra_ndx = None
        self.update()

    def mouseMoveEvent ( self, q_mouse_event):
        if not self.data or self.no_draw:
            return

        p = q_mouse_event.pos()

        # No need to highlight a serie if there's only one
        # in the graph.

        self.ndx_best_serie = -1
        self.best_serie_intra_ndx = None

        if len(self.data) >= 1:

            ndx,serie = self._locate_legend(p.x(), p.y())
            if not serie:
                # mainlog.debug("Trying to locate on graph")
                serie,self.best_serie_intra_ndx = self.locate_serie(None, p.x(), p.y())
                if serie:
                    #mainlog.debug("Located serie : {}".format(serie))
                    ndx = self.data.index(serie)

                # 2014/04/14 13:45:43 [DEBUG]   Locate legend data_ndx:2 TO 77481144 - 20
                # 2014/04/14 13:45:43 [DEBUG]   mouseMove : Highlighting another serie found ndx:1 locate_ndx:2 77481144
                # 2014/04/14 13:45:43 [DEBUG]   _draw_legend: Highlighting serie ndx=1 77481144

            if serie and self.ndx_best_serie != ndx:
                self.ndx_best_serie = ndx # self.data.index(serie)
                # mainlog.debug("mouseMove : Highlighting another serie found ndx:{} locate_ndx:{} {} loacte:{}".format(self.ndx_best_serie, ndx, id(serie), id(self.data[ndx])))
                self.update()


    def _locate_legend(self, x, y):

        for i in range(len(self.legend_labels_bounding_boxes)):
            data_ndx,bb = self.legend_labels_bounding_boxes[i]
            if bb.contains(x,y):
                # mainlog.debug(u"Locate legend data_ndx:{} {} {} - {}".format( data_ndx,self.legends[data_ndx], id(self.data[data_ndx]),i))
                return data_ndx, self.data[data_ndx]

        return None,None


    def locate_serie(self, painter, x, y):
        """ Find the serie which is closes to the x,y point
        """

        if len(self.x_legends) <= 1:
            return None, None

        # y = self.height() - y

        screen_x_step = float(self.total_width) / len(self.x_legends)

        # The x corrdinates can be outside the graph area.
        # So I use som min and max to have an index in the serie's range
        x_ndx = min(len(self.data[0])-1,
                    int(max(0, (x - self.margin - self.y_axis_label_width) / screen_x_step)))
        x_ndx1 = min( len(self.data[0])-1,
                      x_ndx+1)


        delta_x = x - self.margin - self.y_axis_label_width - (x_ndx * screen_x_step )

        # print "{}-{} -> {} - {} d={}".format(x,y,x_ndx,x_ndx1,delta_x)

        best_d = 999999999
        best_serie = None

        for serie in self.data:
            if serie[x_ndx] is not None and serie[x_ndx1] is not None:
                y0 = serie[x_ndx] * self.y_factor
                y1 = serie[x_ndx1] * self.y_factor

                # Screen slope
                slope = (y1 - y0)  / screen_x_step
                sy =  self.y_base - ( y0 + slope * delta_x)

                d = (sy - y ) ** 2
                # print d

                if d < best_d:
                    best_d = d
                    best_serie = serie

        return best_serie,x_ndx



    def _item_coordinates_lines(self, ndx_serie, ndx_in_serie):

        assert ndx_serie >= 0 and ndx_serie < len(self.data), "Incorrect ndx_serie ({})".format(ndx_serie)
        serie = self.data[ndx_serie]

        x = self.x_centers[ndx_in_serie]
        y_top = float(serie[ndx_in_serie]) * self.y_factor

        return x, y_top


    def _draw_selected_items_in_series(self, painter):
        fm = painter.fontMetrics()

        pen = QPen()
        pen.setWidth(1)
        pen.setColor(Qt.GlobalColor.white)
        painter.setPen(pen)

        # We assume all series have the very same number of values
        # and all values on the same index are drawn on the same X
        # coordinate

        ndx_serie = self.best_serie_intra_ndx

        aesthetic_shift = 5

        if ndx_serie is not None:

            to_draw = []
            for i in range(len(self.data)):
                x, y = self._item_coordinates_lines(i, ndx_serie)
                #mainlog.debug("{} {}".format(ndx_serie,i))
                v = self.data[i][ndx_serie]

                text = str(int(v))

                to_draw.append( (self.y_base - y, text) )

            last_y = 100000
            for y, text in sorted( to_draw, key=lambda z : z[0], reverse=True):
                r = QRect(x + aesthetic_shift,0,1000,1000)
                bb = painter.boundingRect(r,Qt.AlignLeft,text)
                if bb.right() > self.width():
                    x = x - bb.width() - 2*aesthetic_shift# left align

                if y + bb.height() > last_y:
                    y = last_y - bb.height()

                fill_color = QColor(16, 16, 48)
                fill_color.setAlpha(196)
                brush = QBrush(fill_color)
                margin = 2
                r = QRect(x + aesthetic_shift - margin,
                          y - aesthetic_shift - bb.height() - margin,
                          bb.width() + 2*margin,
                          bb.height() + 2*margin)
                painter.fillRect(r, brush)

                painter.drawText(x + aesthetic_shift,
                                 y - aesthetic_shift,
                                 text)

                last_y = y

            x, y = self._item_coordinates_lines(0, ndx_serie)
            qp = QPainterPath()
            qp.moveTo(x, self.y_base)
            qp.lineTo(x, self.y_base - self.total_height)
            painter.drawPath(qp)


    def _draw_serie(self, painter, ndx_serie, color):

        serie = self.data[ndx_serie]

        if not serie:
            return

        qp = QPainterPath()
        # qp.addRect(2,2,total_width-4,total_height-4)

        x = float(0) * self.x_factor
        y = serie[0] * self.y_factor
        qp.moveTo(self.x_centers[0],self.y_base - y)
        # print y_base

        for i in range(1,len(serie)):
            x = float(i) * self.x_factor
            y = float(serie[i]) * self.y_factor

            qp.lineTo(self.x_centers[i], self.y_base-y)

        pen = QPen()
        pen.setColor(color)

        if ndx_serie == self.ndx_best_serie:
            pen.setWidth(6)
        else:
            pen.setWidth(2)

        painter.setPen(pen)
        painter.drawPath(qp)



        # self.max_legend_label_width = 0
        # fm = painter.fontMetrics()
        # for label in legends:
        #     self.max_legend_label_width = max(fm.boundingRect(label).width(),
        #                                       self.max_legend_label_width)

        # self.max_legend_label_width += 10 # a bit of room

        # self.legend_labels_per_line = int(self.total_width / self.max_legend_label_width)
        # self.legend_lines = len(legends) / self.legend_labels_per_line
        # if len(legends) % self.legend_labels_per_line > 0:
        #     self.legend_lines += 1

        # self.legend_height = self.text_height * self.legend_lines

    def _draw_legend2(self, painter, labels):
        text_pen = QPen()
        text_pen.setCapStyle(Qt.RoundCap)
        text_pen.setColor(QColor(200, 200, 200)) # alpha=255=fully opaque
        text_pen.setWidth(1)

        highlighted_text_pen = QPen()
        highlighted_text_pen.setColor(QColor(255, 255, 255)) # alpha=255=fully opaque
        highlighted_text_pen.setWidth(1)

        line_pen = QPen()
        line_pen.setCapStyle(Qt.RoundCap)
        line_pen.setColor(QColor(200, 200, 200)) # alpha=255=fully opaque
        line_pen.setWidth(2)


        row = col = 0

        self.legend_labels_bounding_boxes = []

        for data_ndx, label in sorted( zip(range(len(labels)),labels), key=lambda a:a[1]):

            if label:
                # One can hide a series' legend by using a blank label

                x = self.margin + col * self.max_legend_label_width + 3
                y = self.legend_y_start + row * self.text_height

                # Draw coloured line

                line_pen.setColor(self.graph_colors[data_ndx % len(self.graph_colors)]) # alpha=255=fully opaque
                painter.setPen(line_pen)

                if data_ndx == self.ndx_best_serie:
                    r = QRect(x-3, y-self.text_height+3, self.max_legend_label_width, self.text_height)
                    painter.drawRect(r)
                    painter.setPen(highlighted_text_pen)
                else:
                    painter.drawLine(x,y+3,x+self.max_legend_label_width - 6,y + 3)
                    painter.setPen(text_pen)

                painter.drawText(x,y, label)

                # Remember text bounding box
                r = QRect(x,y - self.text_height, self.max_legend_label_width, self.text_height)
                bb = painter.boundingRect(r,Qt.AlignLeft,label)

                # if label == 'TV':
                #     painter.drawRect(r)

                self.legend_labels_bounding_boxes.append( (data_ndx,r) )


                if not (col < self.legend_labels_per_line - 1):
                    col = 0
                    row += 1
                else:
                    col += 1



    def _draw_legend(self, painter, labels):
        text_pen = QPen()
        text_pen.setCapStyle(Qt.RoundCap)
        text_pen.setColor(QColor(200, 200, 200)) # alpha=255=fully opaque
        text_pen.setWidth(1)

        highlighted_text_pen = QPen()
        highlighted_text_pen.setColor(QColor(255, 255, 255)) # alpha=255=fully opaque
        highlighted_text_pen.setWidth(1)

        line_pen = QPen()
        line_pen.setCapStyle(Qt.RoundCap)
        line_pen.setColor(QColor(200, 200, 200)) # alpha=255=fully opaque
        line_pen.setWidth(2)

        max_width = 0
        fm = painter.fontMetrics()
        for label in labels:
            max_width = max(fm.boundingRect(label).width(), max_width)

        y_room = int(self.height() * 0.5 / self.text_height)

        nb_columns = int( len(labels)  / y_room)
        if len(labels) % y_room > 0:
            nb_columns += 1

        y_room = y_room * self.text_height

        x = self.margin + self.total_width - nb_columns * (max_width + 10)



        # 100 / 20 = 5 entry per column
        # 17 / 5 = 3 => 4 columns
        # print self.height() * 0.5, "  ", len(labels), "   ", nb_columns, " y_room:", y_room

        y = 0
        i = 0
        y_offset = self.yoffset
        self.legend_labels_bounding_boxes = []

        # Draw a background rectanlge behin the legend

        fill_color = QColor(16,16,48)
        fill_color.setAlpha(196)
        brush = QBrush(fill_color)

        h = y_room
        w = nb_columns * (max_width + 10)
        if nb_columns == 1:
            h = len(labels) * self.text_height

        r = QRect(x-3, y_offset - self.text_height , w, h + 6)
        painter.fillRect(r,brush)

        sorted_labels = sorted( zip( range(len(labels)), labels, map(id,self.data)),
                                lambda a,b:cmp(a[1],b[1]))

        # mainlog.debug( sorted_labels)

        # We sort labels on their names (but keep the indices right)
        for data_ndx, label in sorted( zip(range(len(labels)),labels), lambda a,b:cmp(a[1],b[1])):

            # Draw coloured line

            line_pen.setColor(self.graph_colors[data_ndx % len(self.graph_colors)]) # alpha=255=fully opaque
            painter.setPen(line_pen)

            if data_ndx == self.ndx_best_serie:
                r = QRect(x-3, y_offset+ y-self.text_height+3, max_width + 6, self.text_height)
                painter.drawRect(r)
                painter.setPen(highlighted_text_pen)
            else:
                painter.drawLine(x,y_offset+y+3,x+max_width,y_offset+y + 3)
                painter.setPen(text_pen)

            painter.drawText(x,y_offset+y,label)

            # Remember text bounding box
            r = QRect(x,y_offset+y - self.text_height,max_width,self.text_height)

            # if label == "TO":
            #    painter.drawRect(r)

            bb = painter.boundingRect(r,Qt.AlignLeft,label)
            # bb.adjust(-5,-5,+5,+5)
            # print label,label_ndx,r.x(), r.y(), r.width(), r.height()

            self.legend_labels_bounding_boxes.append( (data_ndx,bb) )


            if y >= y_room - self.text_height:
                y = 0
                x += max_width + 10
            else:
                y += self.text_height


            i += 1





    def _create_pens(self):
        self.axis_text_pen = QPen()
        self.axis_text_pen.setCapStyle(Qt.RoundCap)
        self.axis_text_pen.setColor(QColor(200, 200, 200)) # alpha=255=fully opaque
        self.axis_text_pen.setWidth(1)


    def _draw_x_axis_dates(self, painter, l):

        def months_between(a,b):
            """ Nb of months, inclusive.
            """

            if a > b:
                a,b = b,a

            if a.year == b.year:
                return b.month - a.month + 1
            else:
                m = (12 - a.month + 1) + (b.month + 1)
                my = (b.year - a.year - 1) * 12

                return m + my


        if not l or len(l) <= 2:
            return l

        fm = painter.fontMetrics()
        char_width = fm.boundingRect("9").width()
        nbchars = self.total_width / char_width

        nb_days = (l[-1] - l[0]).days
        if nb_days <= 10 and not self.x_axis_as_months:
            return l

        # mainlog.debug("Too many days")

        nb_months = months_between(l[0], l[-1])
        if nb_months < (nbchars / len("MM/YY")):

            old_d = l[0]
            nl = [short_my(old_d)] # Will have the same length as l

            # print l[1:-1]

            for d in l[1:len(l)]:
                if d.month != old_d.month:
                    if d.year != old_d.year:
                        nl.append(short_my(d))
                    else:
                        nl.append(str(d.month))
                    old_d = d
                else:
                    nl.append("")

            if len(l) != len(nl):
                mainlog.error("something is wrong")

            return nl

        mainlog.debug("Too many months")

        nb_years = l[-1].year - l[0].year + 1

        old_d = l[0]
        nl = [short_my(old_d)] # Will have the same length as l

        for d in l[1:len(l)]:
            if d.year != old_d.year:
                nl.append(short_my(d))
                old_d = d
            else:
                nl.append("")

        return nl


    def _draw_x_axis(self, painter, labels):

        if not labels:
            return

        if isinstance(labels[0],date):

            # In this case we expect to have, for example, a label per day
            # Of course that's too many to draw, hence this "dithering"

            dithered_labels = []

            # 12 expresses a "density" which allows us to switch between days and month
            # steps. Ideally we should generalize that to weeks, years...

            if len(labels) > 12:
                dithered_labels.append(labels[0])

                for i in range(1,len(labels)):
                    if labels[i].month != labels[i-1].month:
                        dithered_labels.append(labels[i])
                    else:
                        dithered_labels.append(None)
                labels = dithered_labels

                # mainlog.debug(labels)

            def short_my(d):
                if d:
                    return u"{}/{:0>02}".format(d.month,d.year % 100)
                else:
                    return ""

            # labels = self._draw_x_axis_dates(painter, labels)
            # labels = [short_my(l) for l in labels]

            old_d = labels[0]
            nl = [short_my(old_d)] # Will have the same length as l

            for d in labels[1:len(labels)]:
                if d and d.month != old_d.month:
                    if d.year != old_d.year:
                        nl.append(short_my(d))
                    else:
                        nl.append(str(d.month))
                    old_d = d
                else:
                    nl.append("") # Dithering == cleraing unwanted values

            labels = nl

        max_height = 0
        total_label_width = 0

        fm = painter.fontMetrics()
        for label in labels:
            br = fm.boundingRect(str(label))
            max_height = max(br.height(), max_height)
            total_label_width += br.width()

        painter.setPen(self.axis_text_pen)

        last_x = -1
        last_label = None

        for i in range(len(labels)):
            label = str(labels[i])
            w = fm.boundingRect(label).width()
            x = self.x_centers[i] - w / 2

            # Somehow, the width of an empty string is not 0 :-)
            if label and last_label != label and x > last_x:
                # Avoid that this label overlaps the previous one
                painter.drawText(x, self.y_base + max_height, label)
                last_x = x + w - 1
                last_label = label

            if label:
                painter.drawLine(self.x_centers[i], self.y_base + 2, self.x_centers[i], self.y_base - 2)
            # else:
            #     mainlog.debug("Skipping label={} x={} last_x={}".format(label, x, last_x))

    def _draw_over_grid(self,painter):
        # painter.setRenderHint(QPainter.Antialiasing, False)

        line_color = QColor(60, 20, 200, 255)
        flat_structure = QColor(20,20,255,128)
        line_color = flat_structure

        w = min(self.height(), self.width()) / 20
        m = self.margin / 2

        x0 = m
        x1 = m + w
        x15 = m + 9*w
        x2 = self.width() - m - w
        x3 = self.width() - m

        y0 = m
        y1 = m + w
        y15 = m + 5*w
        y2 = self.height() - m - w
        y3 = self.height() - m


        # ----------------------------------------------------------------------

        d = w / 4
        p = [ (x0,y15+d),
              (x0,y1),
              (x1,y0),

              (x15+2*d,y0),     #         /
              (x15+d,y0+d),     #    ____/
              (x1,y0+d),    #   /
              (x0+d,y1),        #  |
              (x0+d,y15),       #  |
              (x0,y15+d)        # _|
        ]

        qp = QPainterPath()
        qp.moveTo( p[0][0], p[0][1],)
        for i in range(1,len(p)):
            qp.lineTo( p[i][0], p[i][1],)
        qp.closeSubpath()


        painter.fillPath(qp,QBrush(QColor(20,20,255,128)))

        pen = QPen()
        pen.setCapStyle(Qt.RoundCap)

        pen.setColor(line_color) # alpha=255=fully opaque
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPath(qp)

        # ---------------------------------------------------------

        qp = QPainterPath()


        p = [ (x0,y1), (x1,y0),
              (x2,y0), (x3,y1),
              (x3,y2), (x2,y3),
              (x1,y3), (x0,y2),
              (x0,y1)]

        qp.moveTo( p[0][0], p[0][1],)
        for i in range(1,len(p)):
            qp.lineTo( p[i][0], p[i][1],)

        pen = QPen()
        pen.setCapStyle(Qt.RoundCap)
        pen.setColor(QColor(0, 0, 80, 196)) # alpha=255=fully opaque
        pen.setWidth(5)
        painter.setPen(pen)

        painter.drawPath(qp)

        pen = QPen()
        pen.setCapStyle(Qt.RoundCap)
        pen.setColor(line_color) # alpha=255=fully opaque
        pen.setWidth(1)
        painter.setPen(pen)

        painter.drawPath(qp)





    def _draw_grid(self,painter, y_base, width, height, steps):

        m = int(self.maxi / self.rounded_step_size)

        if self.timer.isActive():
            self.gride_lines_number = self.timer_ticks

            if self.gride_lines_number >= m:
                self.timer.stop()
        else:
            self.gride_lines_number = m


        for i in range( self.gride_lines_number + 2):
            qp = QPainterPath()
            #mainlog.debug("self.rounded_step_size = {}, self.maxi={}".format(self.rounded_step_size, self.maxi))
            y = y_base - self.rounded_step_size * i * self.y_factor
            qp.moveTo(0,y)

            # A bit of shuffle on y for visual effect
            qp.lineTo(width,y + (i % 3) - 1)

            pen = QPen()
            pen.setCapStyle(Qt.RoundCap)
            pen.setColor(QColor(0, 0, 25)) # alpha=255=fully opaque
            pen.setWidth(5)
            painter.setPen(pen)

            painter.drawPath(qp)

            pen = QPen()
            pen.setCapStyle(Qt.RoundCap)
            pen.setColor(QColor(30, 30, 30)) # alpha=255=fully opaque
            pen.setWidth(1)
            painter.setPen(pen)

            painter.drawPath(qp)




    def _draw_y_axis(self,painter, y_base, width, height, steps):

        text_pen = QPen()
        text_pen.setCapStyle(Qt.RoundCap)
        text_pen.setColor(QColor(200, 200, 200)) # alpha=255=fully opaque
        text_pen.setWidth(1)
        painter.setPen(text_pen)


        if self.rounded_step_size < 1:
            fmt = "{:.1f}"
        else:
            fmt = "{:.0f}"

        if self.rounded_step_size > 0:
            for i in range(int(self.maxi / self.rounded_step_size) + 1):

                y = y_base - self.rounded_step_size * i * self.y_factor
                painter.drawText(self.margin,y, fmt.format(self.rounded_step_size * i))


    def draw_title(self, painter):
        text_pen = QPen()
        text_pen.setCapStyle(Qt.RoundCap)
        text_pen.setColor(QColor(255, 255, 255)) # alpha=255=fully opaque
        text_pen.setWidth(1)
        painter.setPen(text_pen)

        painter.setFont(self.title_font)

        r = QRect(self.margin,0,self.width() - 2*self.margin,self.height())
        painter.drawText(r, Qt.AlignLeft + Qt.TextWordWrap, self.title)


    def draw_no_data(self, painter):
        text_pen = QPen()
        text_pen.setCapStyle(Qt.RoundCap)
        text_pen.setColor(QColor(128, 128, 128)) # alpha=255=fully opaque
        text_pen.setWidth(1)
        painter.setPen(text_pen)

        painter.setFont(self.title_font)
        r = QRect( self.margin, 0, self.width() - 2*self.margin, self.height())
        painter.drawText(r, (Qt.AlignCenter | Qt.AlignLeft) + Qt.TextWordWrap, _("No data"))

    def paintEvent(self,event):


        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        base_font = painter.font()

        self._compute_lengths(painter)

        if self.no_draw:
            self.draw_title(painter)
            self.draw_no_data(painter)
            return

        self._draw_grid(painter, self.y_base, self.width(), self.total_height, 6)
        # self._draw_over_grid(painter)

        self._draw_legend2(painter, self.legends)
        self._draw_x_axis(painter, self.x_legends)
        self._draw_y_axis(painter, self.y_base, self.width(), self.total_height, 6)
        self.draw_title(painter)
        painter.setFont(base_font)
        if self.data:
            for i in range(len(self.data)):
                self._draw_serie(painter, i, self.graph_colors[i % len(self.graph_colors)])

        if self._horizontal_ruler_y_value != None:
            self._draw_horizontal_ruler(painter,
                                        self._horizontal_ruler_text,
                                        self._horizontal_ruler_y_value,
                                        self._horizontal_ruler_color)

        self._draw_selected_items_in_series(painter)

    # def compute_mini_maxi(self, delta_min):
    #     if self.data:
    #         mini = 99999999999
    #         maxi = 0
    #         for l in self.data:
    #             if l:
    #                 mini = min(min(l),mini)
    #                 maxi = max(max(l),maxi)
    #
    #         if maxi - mini < delta_min:
    #             # mainlog.debug("* "*20 + str(delta_min) )
    #             maxi = mini + delta_min
    #
    #         self.mini, self.maxi = mini, maxi
    #
    #         assert 0 <= self.mini <= self.maxi, "0 <= {} <= {}".format(self.mini, self.maxi)

    def set_mini_maxi(self,mini,maxi):
        """ Set mini/maxi Y values. That's useful to have, for example,
        the 0 value on the graph.

        If mini and maxi are None, the their value will be guessed
        from the data drawn.

        :param mini: Minimum value that will be displayed on the Y axis
        :param maxi: Maximum value that will be displayed on the Y axis
        :return:
        """

        assert (mini == None and maxi == None) or (0 <= mini <= maxi), "0 <= {} <= {}".format( mini, maxi)

        self.forced_maxi = maxi
        self.forced_mini = mini

    def set_horizontal_ruler(self, text, y_value, color = Qt.GlobalColor.green):

        self._horizontal_ruler_text = text
        self._horizontal_ruler_y_value = y_value
        self._horizontal_ruler_color = color

    def _draw_box_under_text(self,painter,x,y,text):
        r = QRect(1,1,1000,1000)
        bb = painter.boundingRect(r,Qt.AlignLeft,text)
        bb = QRect(x,y - bb.height() +2 , bb.width() + 2, bb.height())

        # print("{} {} {} {}".format(bb.x(),bb.y(),bb.width(),bb.height()))

        fill_color = QColor(0,0,0)
        fill_color.setAlpha(170)
        brush = QBrush(fill_color)

        painter.fillRect(bb,brush)


    def _draw_horizontal_ruler(self, painter, text, y_value, color):

        y = y_value * self.y_factor

        pen = QPen()
        pen.setCapStyle(Qt.SquareCap)
        pen.setColor(color)

        qp = QPainterPath()

        r = QRect(1,1,1000,1000)
        bb = painter.boundingRect(r,Qt.AlignLeft,text)
        bb = QRect(self.x_base,self.y_base - y - bb.height(), bb.width() + 2, bb.height())

        # print("{} {} {} {}".format(bb.x(),bb.y(),bb.width(),bb.height()))

        fill_color = QColor(0,0,0)
        fill_color.setAlpha(128)
        brush = QBrush(fill_color)

        painter.fillRect(bb,brush)

        qp.moveTo(self.x_base,self.y_base - y)
        qp.lineTo(self.total_width + self.x_base, self.y_base - y)

        painter.setPen(pen)
        painter.drawPath(qp)

        text_pen = QPen()
        text_pen.setCapStyle(Qt.RoundCap)
        text_pen.setColor(color) # alpha=255=fully opaque
        text_pen.setWidth(1)

        painter.setPen(text_pen)
        painter.drawText(self.x_base,self.y_base - y - 5,text)
