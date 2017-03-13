import sys

import random

from PySide.QtCore import Qt,Slot, QPointF, QTimer
from PySide.QtGui import QLabel,QPolygonF,QPainterPath,QPainter,QPen,QBrush,QAction,QMenu
from PySide.QtGui import QWidget,QVBoxLayout,QHBoxLayout,QMessageBox,QTextBrowser,QDialog,QDialogButtonBox,QTextEdit,QFrame,QLayout,QStandardItemModel, \
    QPushButton,QProgressDialog,QColor,QDesktopWidget, QComboBox,QSizePolicy

from koi.Configurator import mainlog
from koi.base_logging import log_stacktrace

#noinspection PyUnresolvedReferences
from koi.session.UserSession import user_session


class NavBar(QFrame):
    def __init__(self,parent,definitions):
        """ Set up a navigation bar.

        The definitions parameter is a list of tuples:
        - text : title of navigation item _or_ a widget that has the "clicked" signal.
        - slot : the slot to call when the action is triggered
        - shortcut (optional) : keyboard shortcut to start the action.

        The navbar being a layout, it takes ownership of the widgets.

        :param parent:
        :param definitions:
        :return:
        """
        super(NavBar,self).__init__(parent)

        self.setObjectName("NavigationBar")
        self.buttons = []

        layout = QHBoxLayout()
        layout.setContentsMargins(0,0,0,0)

        for definition in definitions:

            text = definition[0]
            slot = definition[1]
            shortcut = None
            if len(definition) >= 3:
                shortcut = definition[2]

            b = None
            if isinstance(text,str):
                b = QPushButton(text)
                if shortcut:
                    b.setShortcut(shortcut)
            else:
                b = text

            self.buttons.append(b)
            layout.addWidget(b)

            if slot:
                b.clicked.connect(slot)

        self.setLayout(layout)


class TitleBox(QWidget):

    Colors= [QColor(255,255,255),QColor(255,255,255),QColor(255,255,255),
             QColor(240,240,255),QColor(220,220,255),QColor(200,200,255),
             QColor(220,220,255),QColor(240,240,255),
             QColor(255,255,255),QColor(255,255,255),QColor(255,255,255)]

    def time_out(self):
        if self.step >= len(self.Colors) - 3:
            self.step = 0
            self.timer.start(random.randint(3600*1000,7200*1000))
            return
        elif self.step == 0:
            self.timer.start(50)

        self.step += 1

        self.repaint( self.rect())

    def __init__(self,parent,associated_label):
        super(TitleBox,self).__init__(parent)
        self.associated_label = associated_label
        self.shadow_size = 4

        h = self.associated_label.sizeHint().height()

        # Don't redefine the getters or hints, just set the property
        self.setMinimumHeight( h + self.shadow_size)
        self.setMinimumWidth( h * 3.3)

        self.step = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.time_out)
        self.timer.start(2000)

    def italic_block(self, start, width, h):
        slope = 0.3

        # The QPoint below are ordered this way :
        #   1__2
        #  /  /
        # 4__3

        pts = []
        pts.append(QPointF(start + h*slope,2))
        pts.append(QPointF(start + h*slope + width,2))
        pts.append(QPointF(start + 1 + width,h-1))
        pts.append(QPointF(start + 1,h-1))
        pts.append(pts[0]) # Closes the path

        qpp = QPainterPath()
        qpp.addPolygon(QPolygonF(pts))
        return qpp

    def paintEvent(self, pe):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        pen = QPen()
        pen.setColor(Qt.GlobalColor.black)
        pen.setWidth(2)
        pen.setJoinStyle(Qt.MiterJoin)
        p.setPen(pen)

        h = self.associated_label.sizeHint().height()
        w = h
        pw = pen.width()

        b = self.italic_block(pw+0,w,h)
        p.translate(self.shadow_size,self.shadow_size)
        p.fillPath(b, QBrush(Qt.gray))
        p.translate(-self.shadow_size,-self.shadow_size)
        p.fillPath(b, QBrush(self.Colors[self.step]))
        p.drawPath(b)
        b = self.italic_block(pw+w*1.25,w*0.75,h)
        p.translate(self.shadow_size,self.shadow_size)
        p.fillPath(b, QBrush(Qt.gray))
        p.translate(-self.shadow_size,-self.shadow_size)
        p.fillPath(b, QBrush(self.Colors[self.step+1]))
        p.drawPath(b)
        b = self.italic_block(pw+w*2.25,w*0.4,h)
        p.translate(self.shadow_size,self.shadow_size)
        p.fillPath(b, QBrush(Qt.gray))
        p.translate(-self.shadow_size,-self.shadow_size)
        p.fillPath(b, QBrush(self.Colors[self.step+2]))
        p.drawPath(b)


class TitleWidget(QWidget):

    def set_modified_flag(self,on_off=True):
        if on_off != self.modified_flag:
            # work only if necessary

            self.modified_flag = on_off
            self._update_title()

    def set_title(self,title):
        self.original_title = title
        self._update_title()

    def _update_title(self):
        new_title = self.original_title
        if self.modified_flag:
            new_title += " <b><font color='red'>***</font></b>"
        self.title_label.setText(new_title)

    def __init__(self,title,parent,right_layout=None):
        super(TitleWidget,self).__init__(parent)

        self.modified_flag = False

        self.title_label = QLabel()
        self.title_label.setObjectName("TitleWidgetLabel") # For QSS styling
        self.set_title(title)

        hlayout = QHBoxLayout()
        hlayout.setAlignment(Qt.AlignVCenter)
        hlayout.addWidget(TitleBox(self,self.title_label),0,Qt.AlignVCenter)
        hlayout.addWidget(self.title_label,1,Qt.AlignVCenter)

        if right_layout:
            if isinstance(right_layout,QLayout):
                hlayout.addLayout(right_layout)
            else:
                hlayout.addWidget(right_layout)

        # top_layout = QVBoxLayout( )
        # top_layout.addLayout(hlayout)
        # top_layout.addSpacing(20)
        hlayout.setContentsMargins(10,0,10,0)

        self.setLayout(hlayout)
        # self.setContentsMargins(0,0,0,10) # applied correctly


class SubTitleWidget(QWidget):
    def set_title(self,title):
        self.title.setText(title)
        # self.repaint()

    def __init__(self,title,parent,right_layout=None):
        super(SubTitleWidget,self).__init__(parent)

        self.title = QLabel()
        self.title.setObjectName("subtitle")
        self.title.setScaledContents(True)
        self.set_title(title)

        hlayout = QHBoxLayout()
        hlayout.setAlignment(Qt.AlignTop)
        # hlayout.addWidget(TitleBox(self))
        hlayout.addWidget(self.title)
        hlayout.addStretch()

        if right_layout:
            if isinstance(right_layout,QLayout):
                hlayout.addLayout(right_layout)
            else:
                hlayout.addWidget(right_layout)

        # hlayout.setStretch(1,1)

        top_layout = QVBoxLayout()
        top_layout.addLayout(hlayout)
        top_layout.addSpacing(10)
        top_layout.setContentsMargins(0,0,0,0)

        self.setLayout(top_layout)
        self.setContentsMargins(0,0,0,0)

class SubFrame(QFrame):
    def __init__(self,title,content_widget_or_layout,parent,right_layout=None):
        super(SubFrame,self).__init__(parent)
        self.setFrameShape(QFrame.Panel)
        self.setFrameShadow(QFrame.Sunken)
        self.setObjectName("HorseSubFrame")

        if title != None:
            self.title_widget = SubTitleWidget(title,self,right_layout)
        else:
            self.title_widget = None

        vlayout2 = QVBoxLayout(None)

        if self.title_widget:
            vlayout2.addWidget(self.title_widget)

        if isinstance(content_widget_or_layout,QLayout):
            vlayout2.addLayout(content_widget_or_layout)
        elif content_widget_or_layout:
            vlayout2.addWidget(content_widget_or_layout)

        vlayout2.setStretch(0,0)
        vlayout2.setStretch(1,1)

        self.setLayout(vlayout2)

    def set_title(self,t):
        if self.title_widget:
            self.title_widget.set_title(t)
        else:
            raise Exception("You can't set a title on a sub frame that had no title first")

# class KPILabel(QLabel):
#     def __init__(self,parent=None):
#         super(KPILabel,self).__init__(parent)
#         self.setAlignment(Qt.AlignHCenter)
#
#     def setText(self,t):
#         super(KPILabel,self).setText(u"<h2>{}</h2>".format(t))



class KPIView(QFrame):
    def __init__(self,title,parent):
        super(KPIView,self).__init__(parent)

        self.widget = QLabel(parent=self)
        self.widget.setAlignment(Qt.AlignHCenter)

        self.setFrameShape(QFrame.Panel)
        self.setFrameShadow(QFrame.Sunken)
        self.setStyleSheet("background:white")

        l = QLabel("<h2><font color='grey'>" + title + "</h2>")
        l.setAlignment(Qt.AlignHCenter)
        l.setWordWrap(True)

        vlayout2 = QVBoxLayout()
        vlayout2.addWidget(l,0,Qt.AlignHCenter)
        # vlayout2.addStretch(1000)
        vlayout2.addWidget(self.widget)


        # hlayout = QHBoxLayout()
        # hlayout.addStretch()
        # hlayout.addWidget(widget)
        # hlayout.addStretch()
        # vlayout2.addLayout(hlayout)


        self.setLayout(vlayout2)

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def set_data(self, txt):
        self.widget.setText( "<h2>{}</h2>".format(txt))

    def set_amount(self, amount):
        self.widget.setText( "<h2>{} €</h2>".format(int(amount)))

def _setBoxTexts(box,text,info_text):
    box.setText(text)
    if info_text:
        box.setInformativeText(info_text)


def place_dialog_on_screen(dialog, x_ratio=0.5, y_ratio=0.5):
    sg = QDesktopWidget().screenGeometry()
    dialog.setMinimumWidth(x_ratio*sg.width())
    dialog.setMinimumHeight(y_ratio*sg.height())

def makeErrorBox(text,info_text = None,ex=None):
    mainlog.warning("makeErrorBox : {}".format(text))
    errorBox = QMessageBox()
    errorBox.setObjectName("error_box")
    errorBox.setWindowTitle(_("Error !"))
    errorBox.setIcon(QMessageBox.Critical)

    t = info_text
    if ex:
        nfo = ""
        if info_text:
            nfo = info_text + u'\n'
        t = u"{}{}\n{}".format(nfo,_("Additional information :"), str(ex))
    _setBoxTexts(errorBox,text,t)
    errorBox.setStandardButtons(QMessageBox.Ok)

    if ex:
        log_stacktrace()
        mainlog.exception(ex)
    return errorBox

def showMultiErrorsBox(errs):

    if errs is None or len(errs) == 0:
        return

    if len(errs) == 1:
        d = makeErrorBox(errs[0])
    else:
        info_text = ",".join(errs)
        d = makeErrorBox(_("There are several errors"), info_text)

    d.exec_()
    d.deleteLater()

def makeWarningBox(text,info_text,parent=None):
    warningBox = QMessageBox(parent)
    warningBox.setObjectName("warning_box")
    warningBox.setWindowTitle(_("Warning !"))
    warningBox.setIcon(QMessageBox.Warning)
    _setBoxTexts(warningBox,text,info_text)
    warningBox.setStandardButtons(QMessageBox.Ok);
    return warningBox


def saveCheckBox():
    msgBox = makeWarningBox(_("The data have been changed."),_("Do you want to save your changes?"))
    msgBox.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
    msgBox.setDefaultButton(QMessageBox.Save)
    return msgBox.exec_()


def showErrorBox(text,info_text = None,ex=None,object_name="errorBox"):
    d = makeErrorBox(text,info_text,ex)
    d.setObjectName(object_name)
    d.exec_()
    d.deleteLater()

def showServerErrorBox(ex,object_name="serverErrorBox"):
    d = makeErrorBox(ex.translated_message,_("Server error code is {}").format(ex.code))
    d.setObjectName(object_name)
    d.exec_()
    d.deleteLater()

def showWarningBox(text,info_text = None,parent=None,object_name="warning_box"):
    d = makeWarningBox(text,info_text,parent)
    d.setObjectName(object_name)
    d.exec_()
    d.deleteLater()


def confirmationBox(text,info_text,object_name="confirmationBox"):
    """ Show a confirmation box to the user.

    :param text: Summary of the confirmation.
    :param info_text: Detailed message explaining what to confirm
    :param object_name: Name for Qt's object.
    :return: True if the user confirmed. False else.
    """

    box = QMessageBox()
    box.setObjectName(object_name)
    box.setWindowTitle(_("Please confirm"))
    box.setIcon(QMessageBox.Question)
    _setBoxTexts(box,text,info_text)
    box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel);

    # box.show()
    # from PySide.QtTest import QTest
    # from PySide.QtGui import QApplication
    # QTest.qWaitForWindowShown(box)
    # QApplication.instance().removePostedEvents()

    r = box.exec_() == QMessageBox.Ok

    box.deleteLater()
    return r

def yesNoBox(text,info_text,object_name="confirmationBox"):
    warningBox = QMessageBox()
    warningBox.setObjectName(object_name)
    warningBox.setWindowTitle(_("Please confirm"))
    warningBox.setIcon(QMessageBox.Question)
    _setBoxTexts(warningBox,text,info_text)
    warningBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel);
    return warningBox.exec_()


def makeInformationBox(text,info_text = None):
    warningBox = QMessageBox()
    warningBox.setWindowTitle(_("Information"))
    warningBox.setIcon(QMessageBox.Information)
    warningBox.setText(text);
    warningBox.setInformativeText(info_text)
    warningBox.setStandardButtons(QMessageBox.Ok);
    return warningBox

def formatErrorsOnLine(error_lines):
    s = u""
    for line,errors in error_lines.items():
        s = s + _("On line <b>{}</b>:").format(line+1) + '<ul>'
        for error in errors:
            s = s + u'<li>' + error + u'</li>'
        s = s + '</ul>'

    return s

def showTableEntryErrorBox(error_lines):
    """ error_lines is a dict.
    """

    s = u""
    for line,errors in error_lines.items():
        s = s + _("On line <b>{}</b>:").format(line+1) + '<ul>'
        for error in errors:
            s = s + u'<li>' + error + u'</li>'
        s = s + '</ul>'

    errorBox = makeErrorBox(_("Some of the data you entered are not valid"), s)
    errorBox.exec_()
    errorBox.deleteLater()


def showTableEntrySudModelsErrorBox(error_lines):
    """ error_lines is a dict.
    """

    s = u""
    for line,errors in error_lines.items():
        s = s + _("On line <b>{}</b>:").format(line) + '<ul>'
        for error in errors:
            s = s + '<li>' + error + '</li>'
        s = s + '</ul>'

    errorBox = makeErrorBox(_("Some of the data you entered are not valid"), s)
    errorBox.exec_()
    errorBox.deleteLater()





def make_header_model(titles,headers=None):
    if headers is None:
        headers = QStandardItemModel(1, len(titles))

    i = 0
    for p in titles:
        headers.setHeaderData(i, Qt.Orientation.Horizontal, p)
        i = i + 1
    return headers








class HelpDialog(QDialog):
    def __init__(self,parent):
        super(HelpDialog,self).__init__(parent)

        title = _("A bit of help")
        self.setWindowTitle(title)
        top_layout = QVBoxLayout()
        self.title_widget = TitleWidget(title,self)
        top_layout.addWidget(self.title_widget)

        browser = QTextBrowser()

        import os.path
        from koi.Configurator import resource_dir

        with open( os.path.join(resource_dir,"manual.html"), encoding='utf-8') as input:
            html = input.read()
        browser.setHtml(html)

        # browser.setLineWrapMode(QTextEdit.NoWrap)
        #         browser.setHtml("""<h1>Tables</h1>
        #
        # In tables you can edit, don't forget these few useful shortcuts :
        # <ul>
        # <li><b>F5</b> : will insert a line under your cursor</li>
        # <li><b>Shift + F5</b> : will append a line at the end of the table</li>
        # <li><b>F8</b> : will delete the line under your cursor (if you're allowed to)</li>
        # <li><b>F1</b> and <b>Shift + F1</b> : will allow you to move up/move down a row </li>
        # </ul>
        # """)
        # browser.setMinimumWidth(browser.document().documentLayout().documentSize().toSize().width())
        browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        top_layout.addWidget(browser)

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.Ok)

        top_layout.addWidget(self.buttons)
        self.setLayout(top_layout)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    @Slot()
    def accept(self):
        self.deleteLater()
        return super(HelpDialog,self).accept()

    @Slot()
    def reject(self):
        self.deleteLater()
        return super(HelpDialog,self).reject()


def populate_menu( menu, action_target, list_actions, context=Qt.WindowShortcut):
    """ action_target is a QWidget where the menu's action can be
    added so that they are callable from there
    """

    global configuration
    global user_session

    for t in list_actions:
        # t = (Text, Slot to call, KeySequence shortcut, roles which can use the action)
        # t = (QAction, roles which can use the action)
        # if QAction then slot, KeySequence will be ignored

        roles = a = None
        if isinstance( t[0], QAction):
            a = t[0]
            roles = t[1]
            if a.parent() is None:
                action_target.addAction(a)
        elif isinstance( t[0], QMenu):
            a = t[0]
            roles = t[1]
        else:
            a = QAction(t[0],action_target) # text, parent

            if t[1]:
                a.triggered.connect(t[1])

            if t[2]:
                a.setShortcut(t[2])
                a.setShortcutContext(context)
            roles = t[3]
            action_target.addAction(a)

        if roles is not None:
            a.setEnabled(user_session.has_any_roles(roles))

        if isinstance( a, QMenu):
            menu.addMenu(a)
        else:
            menu.addAction(a)


def make_progress(msg,total_steps):
    progress = QProgressDialog(msg, None, 0, total_steps, None)
    progress.setWindowTitle("Horse")
    progress.setMinimumDuration(0)
    progress.setWindowModality(Qt.WindowModal)
    progress.setValue( progress.value() + 1)
    progress.show()
    return progress



class DescribedTextEdit(QTextEdit):
    def __init__(self,description,parent=None):
        super(DescribedTextEdit,self).__init__(parent)
        self._description = description
        self._description_show = False
        self.setText(None)

    def focusInEvent(self,event):
        if self._description_show:
            self._description_show = False
            self.blockSignals(True)
            super(DescribedTextEdit,self).setText("")
            self.blockSignals(False)
        super(DescribedTextEdit,self).focusInEvent(event)

    def toPlainText(self):
        if self._description_show:
            return ""
        else:
            return super(DescribedTextEdit,self).toPlainText()


    def setText(self,text):
        if not text:
            super(DescribedTextEdit,self).setHtml("<font color='grey'>{}</font>".format(self._description))
            self._description_show = True
        else:
            super(DescribedTextEdit,self).setText(text)
            self._description_show = False


def priority_to_stars(p):
    return " ".join(["\u2605"]*p)

def priority_stars():
    stars = []
    for i in range(1,6):
        stars.append( (i, priority_to_stars(i)) )
    return stars

class PriorityCombo(QComboBox):
    def __init__(self,parent=None):
        super(PriorityCombo, self).__init__(parent)

        self.model = QStandardItemModel(len(priority_stars()), 1)
        for i,stars in priority_stars():
            ndx = self.model.index( i-1, 0)
            self.model.setData( ndx, stars, Qt.DisplayRole)
            self.model.setData( ndx, i, Qt.UserRole)

        self.setModel( self.model)

    def current_priority(self):
        return self.currentIndex().data(Qt.UserRole)



class FlexiLabel(QLabel):
    def __init__(self, converter= lambda x:str(x), value = None):
        super(FlexiLabel, self).__init__()

        self._value = None
        self._converter = converter

        self.setValue( value)

    def setValue(self, value):
        self._value = value
        self.setText( self._converter( value))

    def value(self):
        return self._value
