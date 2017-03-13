import os.path

from PySide.QtCore import Slot,QSignalMapper
from PySide.QtGui import QWidget, QHBoxLayout, QVBoxLayout, QPixmap,QIcon,QStackedLayout,QPushButton,QFrame,QToolButton

from PySide.QtCore import Qt
from PySide.QtGui import QPainter, QBrush,QColor,QPen, QStyleOption, QStyle

from koi.Configurator import mainlog,configuration,resource_dir
from koi.gui.inline_sub_frame import InlineSubFrame



from PySide.QtCore import QPoint,QRect,QTimer
from PySide.QtGui import QPen,QPainter,QBrush,QColor
import math

class Star(QWidget):
    def __init__(self,enlightened):

        p = enlightened.parent()
        while p.parent():
            p = p.parent()

        super(Star,self).__init__(p)

        self.enlightened = enlightened

        # self.parent = parent
        self.setMinimumSize(50,50)

        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(20)

        self.progress = self.progress2 = 0
        self.enabled = True

    def paintEvent(self, pe):

        if not self.enlightened.isVisible() or not self.enabled:
            return

        g = self.enlightened.mapToGlobal(QPoint(0,0))
        pos = self.parent().mapFromGlobal(g)
        self.setGeometry( QRect(pos.x(), pos.y(), self.minimumWidth(), self.minimumHeight()))

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        pen = QPen()
        pen.setColor(QColor(128,128,255))
        pen.setWidth(2)

        p.setBrush(QBrush(QColor(225+math.sin(self.progress)*30,225,255)))
        self.progress += 0.09 * 2
        self.progress2 += 0.109 * 2

        p.setPen(pen)


        s = 10
        sz = 7
        w = s*1.1 + sz
        p.drawEllipse(0 + s*math.sin(self.progress + 0.5)+w,s*math.cos(self.progress)+w,sz,sz)

        p.drawEllipse(s*1.1*math.sin(self.progress2)+w,s*math.cos(self.progress + 0.5)+w,sz-2,sz-2)

        p.drawEllipse(s*math.sin(self.progress + 1)+w,s*1.1*math.cos(self.progress2/2 + self.progress/2)+w,sz-4,sz-4)


class VerticalSeparator(QWidget):
    def __init__(self,parent=None):
        super(VerticalSeparator,self).__init__(parent)
        self.setMinimumWidth(1)
        self.setMaximumWidth(1)
        self.setObjectName("VerticalSeparator")

    def paintEvent(self, pe):

        # Those lines are from
        # http://stackoverflow.com/questions/18344135/why-do-stylesheets-not-work-when-subclassing-qwidget-and-using-q-object
        # the big idea is : According to the Qt help files, "Every widget displaying custom content must implement the paintEvent".

        o = QStyleOption()
        o.initFrom(self);
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, o, p, self)

        w = self.minimumWidth()

        pen = QPen()
        pen.setColor(QColor(128,128,192))
        # pen.setWidth(1)
        p.setPen(pen)
        p.drawLine(0,0,max(0,self.width()-1),self.height()-1)


class VerticalSideBarLayout(QFrame):

    def _hide_content_pane(self):
        self.layout().setStretch(0,1)
        self.layout().setStretch(1,0)

        self.stack_widget.setVisible(False)
        self.separator.setVisible(False)

    @Slot(int)
    def _tab_changed(self, ndx):
        w = self.side_widgets[ndx]

        if self.stack.currentWidget() == w and self.stack_widget.isVisible():
            self._hide_content_pane()
        else:
            self.layout().setStretch(0,4)
            self.layout().setStretch(1,1)
            self.stack_widget.setVisible(True)
            self.separator.setVisible(True)

        self.stack.setCurrentWidget(w)

    def _make_tabs_button(self, side_widgets, side_icons):

        if len(side_widgets) != len(side_icons):
            raise Exception("Bad parameters : len(side_widgets) ({}) != len(side_icons) ({})".format(len(side_widgets), len(side_icons)))

        layout = QVBoxLayout()

        self._side_icons = []

        ndx = 0
        for w in side_widgets:

            resource_name = side_icons[ndx]
            pixmap = QPixmap(os.path.join(resource_dir,resource_name))
            icon = QIcon(pixmap)
            self._side_icons.append(icon)

            b = QToolButton()
            b.setIcon(icon);
            b.setIconSize(pixmap.rect().size())
            b.setMaximumWidth(pixmap.rect().width() + 6)

            b.clicked.connect(self.signal_mapper_tab_changed.map)
            self.signal_mapper_tab_changed.setMapping(b, ndx)

            layout.addWidget(b)
            layout.setStretch(ndx,1)
            ndx += 1

        layout.addStretch()

        return layout

    def show_star_on_widget(self, w, show=True):
        mainlog.debug("show_star_on_widget {} {}".format(w, show))

        n = self.stack.indexOf(w)

        if n < 0:
            mainlog.error("The widget was not found")
            return

        b = self.buttons_layout.itemAt(n).widget()


        widget_star = None
        for s in self.stars:
            if s.enlightened == b and s.enabled:
                mainlog.debug("Found a star for the widget")
                widget_star = s

        if show == False and widget_star:
            mainlog.debug("Removing a star")
            self.stars.remove(widget_star)
            widget_star.hide()
            widget_star.setParent(None)
            del widget_star
            return

        elif show == True and widget_star:
            mainlog.debug("Reshow")
            widget_star.show()
            widget_star.enabled = True

        elif show == True and not widget_star:

            mainlog.debug("Show new star")
            star = Star(b)
            star.show()
            star.raise_()
            self.stars.append(star)

    def show_widget(self,widget):

        if widget not in self.side_widgets:
            raise Exception("Tring to show a widget that is not in the side widgets")

        self.stack_widget.setVisible(True)
        self.separator.setVisible(True)
        self.stack.setCurrentWidget(widget)


    def __init__( self, main_widget_or_layout, side_widgets, parent=None):
        super(VerticalSideBarLayout,self).__init__(parent)

        self.stars = []

        self.signal_mapper_tab_changed = QSignalMapper()
        self.signal_mapper_tab_changed.mapped.connect(self._tab_changed)

        self.side_widgets = side_widgets

        self.stack = QStackedLayout(self)
        for w in side_widgets:
            self.stack.addWidget(w)

        self.stack.setCurrentIndex(-1)

        # I need a widget so that I can show/hide it.
        # (we can't do that with a layout)
        self.stack_widget = QWidget(self)
        self.stack_widget.setLayout(self.stack)

        layout = QHBoxLayout()
        if isinstance(main_widget_or_layout, QWidget):
            layout.addWidget(main_widget_or_layout)
        else:
            layout.addLayout(main_widget_or_layout)


        # The panel layout is made of
        # stack of widgets, vertical separator, buttons for widget selection
        panel_layout = QHBoxLayout()
        panel_layout.addWidget(self.stack_widget)

        self.separator = VerticalSeparator( self)
        panel_layout.addWidget(self.separator)

        self.buttons_layout = self._make_tabs_button(side_widgets, ["appbar.cabinet.files.png","thumb-up-3x.png"]) # ,"comments.png"
        panel_layout.addLayout(self.buttons_layout)

        # The panel layout is wrapped into an inline sub frame

        isf = InlineSubFrame(panel_layout, parent=self)
        isf.setObjectName("HorseSubFrame") # ""HorseTightFrame")
        isf.layout().setContentsMargins(2,2,2,2)

        # isf.setObjectName("HorseTightFrame")
        layout.addWidget(isf)

        # layout.setStretch(0,3)
        # layout.setStretch(1,2)

        self.setLayout(layout)
        self._hide_content_pane()
