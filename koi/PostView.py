if __name__ == "__main__":
    from PySide.QtGui import QApplication,QMainWindow

    from koi.base_logging import mainlog,init_logging
    from koi.Configurator import init_i18n,load_configuration,configuration

    init_logging()
    init_i18n()
    load_configuration()

    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session,session

    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)

from PySide.QtCore import Slot,Signal,Qt,QRectF,QTimer,QModelIndex
from PySide.QtGui import QGraphicsScene, QGraphicsView, QVBoxLayout, QGraphicsLineItem,QPen,QFontMetrics,QGraphicsRectItem,QBrush,QColor,QStandardItemModel,QGraphicsSimpleTextItem,QSizePolicy,QPushButton,QProgressDialog,QRadioButton, \
    QFont,QAbstractItemView,QSplitter

from koi.db_mapping import *
from koi.dao import dao
from koi.gui.dialog_utils import TitleWidget,SubFrame,NavBar
from koi.translators import nice_round,nunicode,date_to_dmy
from koi.qtableviewfixed import QTableView
from koi.gui.horse_panel import HorsePanel


class HooverBar(QGraphicsRectItem):

    def __init__(self,x,y,w,h,hoover_text,doubleclick_callback_widget,order_part_id):
        """ doubleclick_callback_widget : we will call the set_on_orderpart method
        of that object if a doubleclik happens here.
        """

        super(HooverBar,self).__init__(x,y,w,h)
        self.setAcceptHoverEvents(True)
        self.gi = None
        self.hoover_text = hoover_text
        self.description = None
        self.doubleclick_callback_widget = doubleclick_callback_widget
        self.order_part_id = order_part_id

        self.base_font = QFont()
        if configuration.font_select:
            self.base_font.setPointSize(self.base_font.pointSize()*2)


    def hoverEnterEvent(self,event): # QGraphicsSceneHoverEvent * event )
        # BUG I had a crash running this, I suspect ownership issues regarding
        # graphics items...

        global configuration
        #mainlog.debug("hoverEnterEvent pos={}-{}".format(event.scenePos().x(),event.scenePos().y()))
        # mainlog.debug("hoverEnterEvent data={}".format(self.data))
        super(HooverBar,self).hoverEnterEvent(event)

        if self.gi == None:
            if self.hoover_text:
                self.gi = QGraphicsRectItem(0, 0, 100, 100)
                self.gi.setBrush(QBrush(QColor(0,64,0,192)))
                self.gi.setPen(QPen(Qt.transparent))
                self.gi.setPos(event.scenePos().x() + 20,event.scenePos().y() + 20)


                # txt = [ "" ]

                # txt = [ u"{} {}".format(self.data.production_file.order_part.human_identifier,
                #                        date_to_dmy(self.data.production_file.order_part.deadline)),
                #         nstr(self.data.production_file.order_part.description),
                #         nstr(self.data.description),
                #         _("{}x{}={}h, rest:{}h").format(self.data.production_file.order_part.qty,
                #                                         nice_round(self.data.planned_hours),
                #                                         nice_round(self.data.production_file.order_part.qty*self.data.planned_hours),
                #                                         nice_round(self.data.planned_hours*self.data.production_file.order_part.qty - self.data.done_hours))]

                x = y = 10
                w = 0
                for t in self.hoover_text:
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

                # description.setHtml(u"|{}| <b>{}</b><br/>{}<br>{}x{}={}h".format(
                #         self.data.production_file.order_part.human_identifier,
                #         self.data.production_file.order_part.description,
                #         self.data.description,
                #         self.data.production_file.order_part.qty, self.data.planned_hours, self.data.production_file.order_part.qty*self.data.planned_hours))

                # description.setDefaultTextColor(Qt.white)
                # br = description.boundingRect()

                self.gi.setRect(0,0,w,y)
                self.scene().addItem(self.gi)
                #mainlog.debug("hoverEnterEvent GI={}".format(self.gi))

        # mainlog.debug("hoverEnterEvent Done")


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
            # mainlog.debug("hoverLeaveEvent GI={}".format(self.gi))
            # self.gi.setActive(False)
            # self.gi.setVisible(False)
            # return

            if self.description:
                # I do this so that I can handle the destruction of description
                # graphics item myself (i.e. description won't be deleted
                # as a children of self.gi)
                self.description.setParentItem(None)
                self.description = None # and delete...

            # QtDoc : Removes the item item and all its children from the scene.
            #         The ownership of item is passed on to the caller

            self.gi.setParentItem(None)
            # self.scene().removeItem(self.gi)
            self.gi = None
            # mainlog.debug("hoverLeaveEvent -- done")


    # order_part_double_clicked = Signal(int)

    def mouseDoubleClickEvent(self,event): # QGraphicsSceneHoverEvent * event )
        # mainlog.debug("mouseDoubleClickEvent {}".format(self.data))
        super(HooverBar,self).mouseDoubleClickEvent(event)
        self.doubleclick_callback_widget.set_on_order_part(self.order_part_id)
        # self.order_part_double_clicked.emit(self.order_part_id)



class BarsLine(object):

    def __init__(self,bar_size,bar_width,bar_height,start_x,base_y,scene,doubleclick_callback_widget):
        self.bar_size = float(bar_size)
        self.start_x = self.current_x = start_x
        self.base_y = base_y
        self.scene = scene
        self.bar_width = bar_width
        self.bar_height = bar_height
        self.insignificant_values = 0
        self.values = []
        self.doubleclick_callback_widget = doubleclick_callback_widget

    def set_start_pos(self,x,y):
        self.start_x = x
        self.base_y = y


    def bars_drawn(self):
        return len(self.values) > 0

    def _draw_bar(self,width,height,brush, hoover_text, order_part):
        # mainlog.debug("_draw_bar {}".format(order_part is None))

        order_part_id = None
        if order_part:
            order_part_id = order_part.order_part_id

        gi = HooverBar(self.current_x,self.base_y - self.bar_height/2 - height / 2, width, height, hoover_text, self.doubleclick_callback_widget,order_part_id)
        # mainlog.debug("_draw_bar // ")

        if brush:
            gi.setBrush(brush)

        self.scene.addItem(gi)
        self.current_x += width

    def finish_bar(self):
        if self.insignificant_values > 0:
            self.add_bar(self.insignificant_values,QBrush(Qt.lightGray),None,True,None)

        if len(self.values) == 0:
            return

        total_width = 0
        for w,h,brush,hoover_text,order_part in self.values:
            total_width += w


        gi = QGraphicsLineItem(self.start_x,self.base_y - self.bar_height,self.start_x + total_width + self.bar_width*2,self.base_y - self.bar_height)
        gi.setPen(QPen(Qt.lightGray))
        self.scene.addItem(gi)
        gi = QGraphicsLineItem(self.start_x,self.base_y,self.start_x + total_width + self.bar_width*2,self.base_y)
        gi.setPen(QPen(Qt.lightGray))
        self.scene.addItem(gi)


        gi = QGraphicsLineItem(self.start_x,self.base_y - self.bar_height*0.25,self.start_x + total_width + self.bar_width*2,self.base_y - self.bar_height*0.25)
        gi.setPen(QPen(Qt.lightGray))
        self.scene.addItem(gi)
        gi = QGraphicsLineItem(self.start_x,self.base_y - self.bar_height*0.75,self.start_x + total_width + self.bar_width*2,self.base_y - self.bar_height*0.75)
        gi.setPen(QPen(Qt.lightGray))
        self.scene.addItem(gi)

        self.current_x = self.start_x + self.bar_width
        for w,h,brush,hoover_text,order_part in self.values:
            self._draw_bar(w,h,brush,hoover_text,order_part)

        # gi = QGraphicsRectItem(self.start_x, self.base_y - self.bar_height, self.current_x - self.start_x, self.bar_height)
        # self.scene.addItem(gi)


    def estimate_width(self):
        width = 0
        for w,h,brush,hoover_text,order_part in self.values:
            width += w
        if self.insignificant_values:
            width += self.bar_width
        return width


    def add_bar(self, value, brush, hoover_text, force, order_part):
        if value < 0:
            raise Exception("Value must be positive. You gave {}".format(value))
        elif value == 0:
            pass
        elif value < self.bar_size / self.bar_width and not force:
            # Too small to appear on screen
            self.insignificant_values += value
        else:
            if value < self.bar_size:
                h = float(value) / float(self.bar_size) * float(self.bar_height)
                self.values.append((self.bar_width,h,brush,hoover_text,order_part))
            else:
                w = float(value) / float(self.bar_size) * float(self.bar_width)
                self.values.append((w,self.bar_height,brush,hoover_text,order_part))


class PostViewScene(QGraphicsScene):

    def set_cursor_on(self,opdef_id):
        if opdef_id in self.posts_offsets:
            coord = self.posts_offsets[opdef_id]
            cover = self.cursor.rect().united(coord)
            self.cursor.setRect(coord)
            self.update(cover)

    def _operation_hoover_description(self,op):
        # order_part = op.production_file.order_part

        txt = [ u"{} {}".format(op.order_part_human_identifier,
                                date_to_dmy(op.deadline)),  # order_part.deadline
                op.order_part_description or "",
                op.description or "",
                _("{}x{}={}h, rest:{}h").format(op.qty,
                                                nice_round(op.planned_hours),
                                                nice_round(op.qty*op.planned_hours),
                                                nice_round(op.planned_hours*op.qty - op.done_hours))]
        return txt


    def reload(self,order_overview_widget,all_ops, all_operations,sort=1):

        # mainlog.debug("reload...")
        progress = QProgressDialog(_("Collecting data..."), None, 0, len(all_ops) + 3, order_overview_widget)
        progress.setWindowTitle("Horse")
        progress.setMinimumDuration(0)
        progress.setWindowModality(Qt.WindowModal)
        progress.setValue( progress.value() + 1)
        progress.show()

        for i in self.items():
            self.removeItem(i)

        self.posts_offsets = dict()
        self.drawn_operations_data = dict()

        self.cursor = QGraphicsRectItem(0,0,50,300)
        self.cursor.setBrush(QBrush(QColor(208,208,255,255)))
        self.cursor.setPen(QPen(Qt.transparent))
        self.addItem(self.cursor)

        bar_width = 8
        bar_height = int(bar_width*60.0/8.0)


        ascent = QFontMetrics(self.base_font).ascent()
        ascent_big = QFontMetrics(self.base_font_big).ascent()

        post_ops = {}


        # mainlog.debug("reload...2")


        # z = 0
        # for op,order_part,parts in all_operations:
        #     z = op.planned_hours
        #     z = order_part.deadline
        #     z = order_part.qty
        #     z = order_part.human_identifier

        # all_operations = map(lambda i:i[0],all_operations)


        y = 0
        for opdef in all_ops:
            progress.setValue( progress.value() + 1)

            operations = filter(lambda op:op.operation_definition_id == opdef.operation_definition_id, all_operations)

            # We're only interested in the effort/time that remains
            # to be put on an operation. We're only interested in
            # the future.

            # We want the oeprations that are either
            # - ongoing
            # - ready to start.
            # In all cases we're only interested in operations
            # that are "active"

            if sort == 1:
                operations = sorted(operations,key=lambda op:op.deadline or date(3000,1,1))
            elif sort == 2:
                operations = sorted(operations,key=lambda op:op.planned_hours*op.qty - op.done_hours)
            else:
                # Don't sort
                pass

            maximum = 16.0 #float !
            small_hours = 0
            op_ndx =0
            current_x = 50
            bar_drawn = False

            total_done_hours = total_estimated = 0

            # --------------------------------------------------------------
            # Started operations

            bars_line = BarsLine(16,bar_width,bar_height,current_x,y,self,order_overview_widget)
            total_hours_to_do = 0

            for op in filter(lambda op:op.done_hours > 0,operations):
                hours_to_do = max(0,op.planned_hours*op.qty - op.done_hours) # max protects against reporting errors
                total_hours_to_do += hours_to_do

                total_estimated += op.planned_hours*op.qty
                total_done_hours += op.done_hours

                bars_line.add_bar(hours_to_do,QBrush(Qt.green),self._operation_hoover_description(op),False, None) # op.production_file.order_part)

            # --------------------------------------------------------------
            bars_line_unstarted_operations = BarsLine(16,bar_width,bar_height,current_x + 30,y,self,order_overview_widget)
            total_hours_to_do_on_unstarted_operations = 0
            for op in filter(lambda op:op.done_hours == 0,operations):

                hours_to_do = op.planned_hours*op.qty
                total_hours_to_do_on_unstarted_operations += hours_to_do

                total_estimated += hours_to_do

                bars_line_unstarted_operations.add_bar(hours_to_do,QBrush(Qt.yellow),
                                                       self._operation_hoover_description(op),
                                                       False,
                                                       None) #op.production_file.order_part)


            y_start = y

            total = total_hours_to_do + total_hours_to_do_on_unstarted_operations

            if total > 0:

                self.drawn_operations_data[opdef.operation_definition_id] = "{}h".format(int(round(total_estimated)))

                gi = QGraphicsSimpleTextItem(_("{} - Estimated to do : {}h; done : {}h").format(opdef.description,
                                                                                                int(round(total)),
                                                                                                int(round(total_done_hours))))
                gi.setFont(self.base_font_big)
                gi.setPos(0,y - gi.boundingRect().height())
                self.addItem(gi)

                th = gi.boundingRect().height()

                gi = QGraphicsLineItem(-ascent_big,y,1024+2*ascent_big,y)
                gi.setPen(QPen(Qt.black))
                self.addItem(gi)

                y += th
            else:
                continue

            y_bars = y



            if total_hours_to_do > 0:
                # There's something to draw

                head = QGraphicsSimpleTextItem(_("Started"))
                head.setFont(self.base_font)
                head.setPos(current_x, y)
                self.addItem(head)
                y += head.boundingRect().height()

                y += bar_height
                bars_line.set_start_pos(current_x,y)
                bars_line.finish_bar()

                foot = QGraphicsSimpleTextItem(_("{}h").format(int(total_hours_to_do+0.5)))
                foot.setFont(self.base_font)
                foot.setPos(current_x,y)
                self.addItem(foot)
                y += foot.boundingRect().height()

                current_x = max(current_x + bars_line.estimate_width(),
                                head.boundingRect().right(),
                                foot.boundingRect().right())

                bar_drawn = True



            if total_hours_to_do_on_unstarted_operations > 0:

                if bars_line_unstarted_operations.estimate_width() + current_x > 1200:
                    x = 50
                    y += ascent_big
                else:
                    y = y_bars
                    x = current_x + 50

                head = QGraphicsSimpleTextItem(_("Not started yet"))
                head.setFont(self.base_font)
                head.setPos(x, y)
                self.addItem(head)
                y += head.boundingRect().height()

                y += bar_height
                bars_line_unstarted_operations.set_start_pos(x,y)
                bars_line_unstarted_operations.finish_bar()

                foot = QGraphicsSimpleTextItem(_("{}h").format(int(total_hours_to_do_on_unstarted_operations+0.5)))
                foot.setFont(self.base_font)
                foot.setPos(x,y)
                self.addItem(foot)
                y += foot.boundingRect().height()

                bar_drawn = True

            y += 3*ascent_big

            r = self.sceneRect()
            self.posts_offsets[opdef.operation_definition_id] =  \
                QRectF(r.x() - 2*ascent_big, y_start - 1.5*ascent_big,
                       r.width() + 4*ascent_big, (y - ascent_big) - (y_start - 1.5*ascent_big) )
            y += ascent_big

        # mainlog.debug("reload...3")
        import functools
        max_width = functools.reduce( lambda acc,po:max(acc,po.width()), self.posts_offsets.values(),0)
        map( lambda po:po.setWidth(max_width), self.posts_offsets.values())

        # for r in self.posts_offsets.values():
        #     gi = QGraphicsLineItem(r.x(),r.y(),r.x()+r.width(),r.y())
        #     gi.setPen(QPen(Qt.lightGray))
        #     self.addItem(gi)

        progress.close()


    def __init__(self,parent,order_overview_widget):
        global configuration
        super(PostViewScene,self).__init__(parent)
        self.base_font = QFont()

        self.base_font_big = QFont()
        self.base_font_big.setPointSize(self.base_font.pointSize()*1.5)
        if configuration.font_select:
            self.base_font_big.setPointSize(self.base_font.pointSize()*2)



class PostViewWidget(HorsePanel):

    def __init__(self,parent,order_overview_widget,find_order_slot):
        global configuration

        super(PostViewWidget,self).__init__(parent)

        self.set_panel_title(_("Post overview"))
        self.bold_font = QFont(self.font())
        self.bold_font.setBold(True)
        self.nb_cols = 8 # Number of columns in the operation definition table

        self.order_overview_widget = order_overview_widget


        self.button = QPushButton(_("Refresh"),self)
        self.button.clicked.connect(self.refresh_action)
        self.sort_by_deadline_button = QRadioButton(_("By deadline"),self)
        self.sort_by_deadline_button.toggled.connect(self.sort_by_deadline)
        self.sort_by_size_button = QRadioButton(_("By hours left to do"),self)
        self.sort_by_size_button.toggled.connect(self.sort_by_size)


        # hlayout = QHBoxLayout()
        # hlayout.setObjectName("halyout")
        # hlayout.setContentsMargins(0,0,0,0)
        # hlayout.addWidget(self.sort_by_deadline_button)
        # hlayout.addWidget(self.sort_by_size_button)
        # hlayout.addWidget(self.button)
        # hlayout.addStretch()

        self.navbar = NavBar(self, [ (self.sort_by_deadline_button, None),
                                     (self.sort_by_size_button, None),
                                     (self.button, None),
                                     (_("Find"), find_order_slot) ] )
        self.navbar.buttons[3].setObjectName("specialMenuButton")

        self.vlayout = QVBoxLayout(self)
        self.vlayout.setObjectName("Vlayout")
        self.vlayout.addWidget(TitleWidget(_("Posts Overview"),self,self.navbar))


        self._table_model = QStandardItemModel(1, self.nb_cols, self)
        self.table_view = QTableView(None)
        self.table_view.setModel(self._table_model)
        self.table_view.selectionModel().currentChanged.connect(self.operation_selected)

        self.table_view.verticalHeader().hide()
        self.table_view.horizontalHeader().hide()
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)

        # This forces Qt to expand layout once I fill data in
        # FIXME dirty but I really don't get why setting
        # the mini width to something smaller (that happens at
        # startup, on first refresh) doesn't work
        self.table_view.setMinimumWidth(1)
        self.table_view.setMaximumWidth(1)

        self.post_view_scene = PostViewScene(self,order_overview_widget)
        self.post_view_scene_view = QGraphicsView(self)
        self.post_view_scene_view.setScene(self.post_view_scene)
        self.post_view_scene_view.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(SubFrame(_("Posts"),self.table_view,self.splitter))
        self.splitter.addWidget(SubFrame(_("Workload"),self.post_view_scene_view,self.splitter))
        # self.splitter.setStretchFactor(0,1)
        self.splitter.setStretchFactor(1,1)
        self.vlayout.addWidget(self.splitter)

        # hlayout = QHBoxLayout()
        # hlayout.addWidget(SubFrame(_("Posts"),self.table_view,self))
        # hlayout.addWidget(SubFrame(_("Workload"),self.post_view_scene_view,self))
        # hlayout.setStretch(1,1)
        # self.vlayout.addLayout(hlayout)

        self.vlayout.setStretch(0,0)
        self.vlayout.setStretch(1,1)

        self.setLayout(self.vlayout)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.slidePostsScene)

        self.current_view_y = 0




    def _data_load(self):
        global dao

        all_operations = dao.operation_dao.load_all_operations_ready_for_production()
        operation_definitions = dao.operation_definition_dao.all_direct_frozen()

        return operation_definitions,all_operations



    def _reset_operation_definitions(self,operations):
        self._table_model.setColumnCount(1)
        self._table_model.setRowCount(len(operations))

        # BUG This should be refreshed on reload() too

        row = col = 0
        first_active = None

        for opdef in operations:

            if opdef.operation_definition_id in self.post_view_scene.drawn_operations_data:
                # currently total planned time
                t = self.post_view_scene.drawn_operations_data[opdef.operation_definition_id]
                ndx = self._table_model.index(row,col)
                if not first_active:
                    first_active = ndx
                self._table_model.setData(ndx,u"{} {}".format(opdef.description,t),Qt.DisplayRole)
                # self._table_model.setData(ndx,self.bold_font,Qt.FontRole)

                self._table_model.setData(self._table_model.index(row,col),opdef.operation_definition_id,Qt.UserRole)
                row += 1

            else:
                pass
                # self._table_model.setData(self._table_model.index(row,col),opdef.description,Qt.DisplayRole)

            # = col + 1
            # if col == self.nb_cols:
            #     col = 0
            #     row += 1

        self._table_model.setRowCount(row)

        # self.table_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        # self.vlayout.setStretch(0,0)
        # self.vlayout.setStretch(1,10)
        # self.vlayout.setStretch(2,10000)


        # height = 0
        # for c in range(self.table_view.model().rowCount()):
        #     height += self.table_view.rowHeight(c) + 1 # +1 for cell border
        # self.table_view.setMinimumHeight(height)
        # self.table_view.setMaximumHeight(height)
        for i in range(self.nb_cols):
            self.table_view.resizeColumnToContents(i)
        self.table_view.setMaximumWidth(self.table_view.columnWidth(0))
        self.table_view.setMinimumWidth(self.table_view.columnWidth(0))
        self.table_view.setSizePolicy(QSizePolicy.Maximum,QSizePolicy.Preferred)

        self.table_view.update()
        self.splitter.update()


        return first_active


    def slide_to_operation(self,opdef_id):
        if opdef_id in self.post_view_scene.posts_offsets:
            self.slide_target_opdef_id = opdef_id
            # mainlog.debug("Target y = {}".format(self.post_view_scene.posts_offsets[self.slide_target_opdef]))
            self.timer.start(20)

    @Slot()
    def slidePostsScene(self):
        if self.slide_target_opdef_id is None:
            return

        # self.post_view_scene_view
        self.post_view_scene.set_cursor_on(self.slide_target_opdef_id) # This done here also aviod some screen trashing

        v = self.post_view_scene_view.verticalScrollBar().value()
        # mainlog.debug( "slidePostsScene : {}".format(v))

        r = self.post_view_scene.posts_offsets[self.slide_target_opdef_id]
        target_y = r.y() + r.height()/2
        delta = (target_y - self.current_view_y) * 0.4
        self.current_view_y = self.current_view_y + delta
        self.post_view_scene_view.centerOn(0,self.current_view_y)
        # mainlog.debug( "slidePostsScene : {} / {}".format(target_y, self.current_view_y))

        if self.post_view_scene_view.verticalScrollBar().value() == v:
            # Close enough => stop moving
            # FIXME not correct because we must stop when the view stops moving, not when the goal we set for centerOn is reached
            self.timer.stop()

    @Slot(QModelIndex,QModelIndex)
    def operation_selected(self, ndx_cur, ndx_old):
        if ndx_cur.isValid():
            opdef = self._table_model.data(ndx_cur,Qt.UserRole)
            if opdef:
                self.slide_to_operation( self._table_model.data(ndx_cur,Qt.UserRole))



    @Slot()
    def refresh_action(self):
        # FIXME reload operations as well

        operation_definitions,all_operations = self._data_load()

        # mainlog.debug("reload")
        if self.sort_by_deadline_button.isChecked():
            self.post_view_scene.reload(self,operation_definitions,all_operations,1)
        elif self.sort_by_size_button.isChecked():
            self.post_view_scene.reload(self,operation_definitions,all_operations,2)
        else:
            self.post_view_scene.reload(self,operation_definitions,all_operations,0)

        # mainlog.debug("reset")
        first_active = self._reset_operation_definitions(operation_definitions)
        # self.table_view.selectionModel().currentChanged.connect(self.operation_selected)
        if first_active:
            self.table_view.setCurrentIndex(first_active)

        # mainlog.debug("done reset")

    @Slot(bool)
    def sort_by_deadline(self,checked):
        if checked:
            self.refresh_action()

    @Slot(bool)
    def sort_by_size(self,checked):
        if checked:
            self.refresh_action()

    order_part_double_clicked = Signal(int)

    # Callback that will be called by HooverBar
    def set_on_order_part(self, order_part_id):
        self.order_part_double_clicked.emit(order_part_id)



if __name__ == "__main__":
    from koi.db_mapping import Employee
    employee = dao.employee_dao.any()
    app = QApplication(sys.argv)

    window = QMainWindow()
    window.setMinimumSize(1024,768)
    presence = PostViewWidget(window,None,None)
    window.setCentralWidget(presence)
    window.show()
    presence.refresh_action()

    app.exec_()
