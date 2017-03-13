#from db_mapping import OperationDefinition

from datetime import datetime,date

from PySide.QtGui import QAbstractItemDelegate,QStyledItemDelegate,QComboBox,QStyle,QPalette, QLineEdit,QFontMetrics,QValidator,QCompleter, \
    QPushButton,QIcon,QFileDialog,QImage,QPixmap,QCheckBox,QPlainTextEdit
from PySide.QtCore import Qt,QRect,QSize, QEvent, QByteArray,QTimer

from koi.date_parser import DateTimeParser,DurationParser,TimeParser,FutureDateParser
from koi.gui.completer import AutoCompleteComboBox
from koi.translators import duration_to_s,date_to_dm,duration_to_hm

#noinspection PyUnresolvedReferences
from koi.translators import EURO_SIGN

from koi.Configurator import mainlog
from six import text_type

class StandardTableDelegate(QStyledItemDelegate):

    def __init__(self,parent=None):
        QStyledItemDelegate.__init__(self,parent)
        self.edit_next_item = True

    def get_displayed_data(self,index):
        """

        :param index: Index pointing to the table cell we're displaying
        :return:
        """
        d = index.model().data( index,Qt.UserRole)
        if d is None:
            return index.model().data( index,Qt.DisplayRole)
        else:
            return text_type(d)

    def paint_data(self,painter,option,r,text,index):
        painter.drawText(r.x(),r.y(),r.width(),r.height(),option.displayAlignment,text)

    def paint(self,painter, option, index ):
        #print("paint {}-{}".format(index.row(), index.column()))
        painter.save()

        # All of this is here to make sure the text is
        # displayed with the appropriate style.

        cg = QPalette.Disabled
        if option.state & QStyle.State_Enabled:
            cg = QPalette.Normal
            if not (option.state & QStyle.State_Active):
                cg = QPalette.Inactive

        # we draw the background

        r = QRect(option.rect.x(),option.rect.y(),option.rect.width(),option.rect.height())
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.color(cg, QPalette.Highlight))
        elif index.data(Qt.BackgroundRole):
            # Alternating background color for the rows, to improve
            # readability
            # if index.row() % 2 == 1:
            #    painter.fillRect(option.rect, QColor(240,240,255))
            painter.fillRect(option.rect, index.data(Qt.BackgroundRole))
        else:
            painter.fillRect(option.rect, Qt.GlobalColor.white)

        # Then the foreground with the text

        data_displayed = self.get_displayed_data(index)

        if data_displayed:
            if index.data(Qt.TextColorRole) is not None:
                painter.setPen(index.data(Qt.TextColorRole))
            elif option.state & QStyle.State_Selected:
                painter.setPen(option.palette.color(cg, QPalette.HighlightedText))
            else:
                painter.setPen(option.palette.color(cg, QPalette.Text))

            self.paint_data(painter,option,r,data_displayed,index)

        painter.restore()

    def sizeHint(self, option, index):
        s = self.get_displayed_data(index)
        fm = QFontMetrics(option.font)

        # print s,option.rect.width(),option.rect.height()

        size = fm.size(0, s) # 0 allows Qt to take \n into account (useful for textarea)
        return size


    def createEditor(self,parent,option,index):
        # Qt takes ownership of the editor
        # Therefore I have recreate it each time this method is called

        editor = QLineEdit(parent)

        # This is needed to put the editor in the right place
        if option:
            editor.setGeometry(option.rect)

        return editor

    def setEditorData(self,editor,index):
        # Read the source data at the index of the source model
        t = index.model().data( index,Qt.UserRole)
        if t is not None: # account for "zero"
            editor.setText(text_type(t))
        else:
            editor.setText(None)

    def setModelData(self,editor,model,index):
        if editor.text() == None or editor.text().strip() == "":
            model.setData(index,"",Qt.UserRole)
        else:
            model.setData(index,editor.text().strip(),Qt.UserRole)

    def eventFilter(self,editor,event):

        # Allow this delegate to have its behaviour customized a bit

        if not self.edit_next_item:
            return super(StandardTableDelegate,self).eventFilter(editor,event)

        # The following code makes sure that for any kind of editor one uses then
        # the "EditNextItem" behaviour is triggered.
        # This is useful when one wants to fill in a great number of rows in a table in one go.
        # Of course this behaviour only makes sense if one hits the enter key (and only
        # that).

        # I use not (modifiers & Qt.*Modifier) because I don't know to to
        # test for "none" modifiers... This might be a PySide shortcoming
        # FIXME complete with other modifiers

        if event and (event.type() == QEvent.KeyPress)\
                and (event.key() in (Qt.Key_Enter,Qt.Key_Return))\
                and not (event.modifiers() & Qt.AltModifier)\
                and not (event.modifiers() & Qt.ControlModifier)\
                and not (event.modifiers() & Qt.ShiftModifier):

            accept = False
            if isinstance(editor,QLineEdit):
                v = editor.validator()
                # mainlog.debug("validating")
                if (v is None) or (v is not None and v.validate(editor.text(),0) == QValidator.Acceptable):
                    # mainlog.debug("validation OK")
                    accept = True
            else:
                accept = True

            if accept:
                # FIXME Not nice to have that here, it'be better if the editor would
                # only send the commit/close if it is valid...
                # print "AutoComboDelegate.eventFilter on {}".format(editor)
                # print "Enter/Return"
                # mainlog.debug("calling commitData on this editor {}".format(editor))
                self.commitData.emit(editor)
                self.closeEditor.emit(editor,QAbstractItemDelegate.EditNextItem)
                return True # Really important ! (segfault without this !)

        return super(StandardTableDelegate,self).eventFilter(editor,event)



class NotEmptyValidator(QValidator):
    def validate(self,intext,pos):
        if intext is None or len(intext.strip()) == 0:
            return QValidator.Intermediate
        else:
            return QValidator.Acceptable

import re
class FilenameValidator(QValidator):

    # Note that I don't do much fiddling about
    # the encoding. The server is expected to run an
    # UTF-8 file system.
    accepted_chars = re.compile(r'^[^/\\"]+$')

    def validate(self,intext,pos):

        # Helps manual entry
        intext = intext.strip()

        is_empty = not intext
        has_bad_chars = not self.accepted_chars.match(intext)

        if is_empty or has_bad_chars:
            return QValidator.Intermediate
        else:
            return QValidator.Acceptable

class FilenameDelegate(StandardTableDelegate):
    def __init__(self,parent=None):
        super(FilenameDelegate,self).__init__(parent)
        self._validator = FilenameValidator()

    def createEditor(self,parent,option,index):
        e = super(FilenameDelegate,self).createEditor(parent,option,index)
        e.setValidator(self._validator)
        return e

    def setModelData(self,editor,model,index):
        model.setData(index,editor.text().strip(),Qt.UserRole)


class NotEmptyStringDelegate(StandardTableDelegate):
    def __init__(self,parent=None):
        super(NotEmptyStringDelegate,self).__init__(parent)
        self._validator = NotEmptyValidator()

    def createEditor(self,parent,option,index):
        e = super(NotEmptyStringDelegate,self).createEditor(parent,option,index)
        e.setValidator(self._validator)
        return e

    def setModelData(self,editor,model,index):
        model.setData(index,editor.text().strip(),Qt.UserRole)


class IntegerValidator(QValidator):
    def __init__(self,mini,maxi):
        QValidator.__init__(self)
        self.mini = mini
        self.maxi = maxi

    def validate(self,intext,pos):
        if intext is None or len(intext.strip()) == 0:
            return QValidator.Acceptable

        try:
            n = int(intext)

            if (self.mini is None or self.mini <= n) and (self.maxi is None or n <= self.maxi):
                return QValidator.Acceptable
            else:
                return QValidator.Intermediate
        except Exception as e:
            return QValidator.Invalid


class FloatValidator(QValidator):
    def __init__(self,mini,maxi):
        QValidator.__init__(self)
        self.mini = mini
        self.maxi = maxi

    def validate(self,intext,pos):
        if intext is None or len(intext.strip()) == 0:
            return QValidator.Acceptable

        try:
            n = float(intext)
            if (self.mini is None or self.mini <= n) and (self.maxi is None or n <= self.maxi):
                return QValidator.Acceptable
            else:
                return QValidator.Intermediate
        except ValueError as e:
            # print e
            return QValidator.Invalid


class NumbersTableDelegate(StandardTableDelegate):

    def __init__(self,mini,maxi,parent=None):
        StandardTableDelegate.__init__(self,parent)
        self.number_validator = IntegerValidator(mini,maxi)

    def get_displayed_data(self,index):
        d = index.model().data( index,Qt.UserRole)
        if d is None or d == 0:
            return None
        else:
            return str(d)

    def paint_data(self,painter,option,r,text,index):
        painter.drawText(r.x(),r.y(),r.width(),r.height(),Qt.AlignRight | option.displayAlignment,text)

    def createEditor(self,parent,option,index):
        editor = super(NumbersTableDelegate,self).createEditor(parent,option,index)
        editor.setValidator(self.number_validator)
        return editor

    def setModelData(self,editor,model,index):
        data = editor.text()
        if data is None or len(data.strip()) == 0:
            model.setData(index,None,Qt.UserRole)
        else:
            model.setData(index,int(data),Qt.UserRole)

class FloatTableDelegate(StandardTableDelegate):
    def __init__(self,mini,maxi,parent=None):
        StandardTableDelegate.__init__(self,parent)
        self.number_validator = FloatValidator(mini,maxi)

    def get_displayed_data(self,index):
        d = index.model().data( index,Qt.UserRole)
        if d is None or d == 0:
            return None
        else:
            # Remove the ".0" to make the display easier
            d = float(d) # d can be a "decimal" istead of a float
            i = int(d)
            if float(d) - i == 0.0:
                return str(i)
            else:
                return str(d) # we rely on Python's float numbers formatting rules

    def paint_data(self,painter,option,r,text,index):
        painter.drawText(r.x(),r.y(),r.width(),r.height(),Qt.AlignRight | option.displayAlignment,text)

    def createEditor(self,parent,option,index):
        editor = super(FloatTableDelegate,self).createEditor(parent,option,index)
        editor.setValidator(self.number_validator)
        return editor

    def setModelData(self,editor,model,index):
        data = editor.text()
        if data is None or len(data.strip()) == 0:
            model.setData(index,None,Qt.UserRole)
        else:
            model.setData(index,float(data),Qt.UserRole)






class EuroDelegate(NumbersTableDelegate):
    def __init__(self,parent=None):
        NumbersTableDelegate.__init__(self,None,None,parent)

    def amount_to_str(self, amount):
        global EURO_SIGN
        # Display an amount in the french/belgian way
        t = u"{:,.2f}".format(amount).replace(u",",u" ").replace(u".",u",")
        return t + EURO_SIGN


    def get_displayed_data(self,index):
        d = index.model().data( index,Qt.UserRole)
        if d is None:
            return None
        else:
            return self.amount_to_str(d)

    def setModelData(self,editor,model,index):
        if editor.text() == None or len(editor.text().strip()) == 0:
            model.setData(index,None,Qt.UserRole)
        else:
            model.setData(index,float(editor.text()),Qt.UserRole)



class StandardValidator(QValidator):
    def __init__(self):
        QValidator.__init__(self)
        self.nullable = True

    def set_nullable(self,nullable):
        self.nullable = nullable

    def full_check(self,intext):
        """ Validates the string and gives an information about the
        error(s) """

        return True

    def validate(self,intext,pos):
        """ The regular QValidator's validate """

        if self.full_check(intext) == True:
            return QValidator.Acceptable
        else:
            return QValidator.Intermediate


class TimestampValidator(StandardValidator):
    def __init__(self, base_date = None):
        super(TimestampValidator,self).__init__()
        self.set_base_date(base_date)
        self.lower_bound = None

    def set_base_date(self,base_date):
        self.base_date = base_date
        if not base_date:
            self.parser = DateTimeParser()
        else:
            self.parser = TimeParser(base_date)

    def set_lower_bound(self,ts):
        self.lower_bound = ts

    def full_check(self,intext):
        """ Validates the string and gives an information about the
        error(s) """

        if (intext is None or len(intext.strip()) == 0) and not self.nullable:
            return _("Can't be empty")
        else:
            try:
                ts = self.parser.parse(intext)

                if ts:
                    if self.lower_bound and ts < self.lower_bound:
                        return _("Below lower bound")
                else:
                    return _("Error while parsing data")

            except ValueError as e:
                return _("Error while parsing data")

        mainlog.debug("check ok")
        return True





class TimestampDelegate(StandardTableDelegate):

    def __init__(self,parent=None,fix_date=None):
        StandardTableDelegate.__init__(self,parent)
        self.fix_date = fix_date
        self.validator = TimestampValidator(fix_date)

    def set_fix_date(self,fix_date):
        self.fix_date = fix_date

    def _date_format(self,ts):
        if ts:
            fd = self.fix_date
            if fd and fd.year == ts.year and fd.month == ts.month and fd.day == ts.day:
                return "{}:{:0>2}".format(ts.hour, ts.minute)
            else:
                return "{}/{}/{} {}:{:0>2}".format(ts.day,ts.month,ts.year,ts.hour, ts.minute)
        else:
            return None

    def get_displayed_data(self,index):
        d = index.model().data( index,Qt.UserRole)
        return self._date_format(d)

    def createEditor(self,parent,option,index):
        editor = QLineEdit(parent)
        editor.setValidator(self.validator)
        if option:
            editor.setGeometry(option.rect)
        return editor

    def setEditorData(self,editor,index):
        ts = index.model().data( index,Qt.UserRole)

        if ts:
            editor.setText(self._date_format(ts))
        else:
            editor.setText(None)

    def setModelData(self,editor,model,index):
        if editor.text() == None or len(editor.text().strip()) == 0:
            model.setData(index,None,Qt.UserRole)
        else:
            data = self.validator.parser.parse(editor.text())
            model.setData(index,data,Qt.UserRole)





class FutureDateValidator(QValidator):
    def __init__(self, base_date = None, enforce_future=False):
        QValidator.__init__(self)

        self.parser = FutureDateParser(base_date)
        self.enforce_future = enforce_future

    def validate(self,intext,pos):
        if intext is None or len(intext.strip()) == 0:
            return QValidator.Acceptable

        try:
            parsed_date = self.parser.parse(intext)
            mainlog.debug("Parsed date = {}".format(parsed_date))

            if ((not self.enforce_future) and parsed_date != False) or \
               (self.enforce_future and datetime.now().date() <= parsed_date):
                return QValidator.Acceptable
            else:
                return QValidator.Intermediate

            return QValidator.Acceptable
        except ValueError as e:
            return QValidator.Invalid


class FutureDateDelegate(StandardTableDelegate):

    def __init__(self,parent=None,fix_date=None):
        StandardTableDelegate.__init__(self,parent)
        self.validator = FutureDateValidator(fix_date)
        self.date_format = "{:%d/%m/%Y}"

    def paint_data(self,painter,option,r,text,index):
        painter.drawText(r.x(),r.y(),r.width(),r.height(),Qt.AlignRight | option.displayAlignment,text)

    def get_displayed_data(self,index):
        d = index.model().data( index,Qt.UserRole)
        if d:
            return date_to_dm(d) # self.date_format.format(d)
        else:
            return None

    def createEditor(self,parent,option,index):
        # editor = ValidatingLineEdit(parent)
        editor = QLineEdit(parent)
        editor.setValidator(self.validator)
        editor.setStyleSheet("padding-left: 0px;");
        if option:
            editor.setGeometry(option.rect)
        return editor

    def setEditorData(self,editor,index):
        # Read the timestamp
        ts = index.model().data( index,Qt.UserRole)

        if ts:
            editor.setText(self.date_format.format(ts))
        else:
            editor.setText(None)

    def setModelData(self,editor,model,index):
        if editor.text() == None or len(editor.text().strip()) == 0:
            model.setData(index,None,Qt.UserRole)
        else:
            data = self.validator.parser.parse(editor.text())
            if data:
                model.setData(index,data,Qt.UserRole)
            else: # data is False
                # Invalid dates are turned into None
                # so that if they are stored in the model
                # they are correct (False is not a Date
                # but None sounds better)
                model.setData(index,None,Qt.UserRole)


class DateDelegate(FutureDateDelegate):

    def __init__(self,parent=None):
        FutureDateDelegate.__init__(self,parent)
        self.validator = FutureDateValidator(date(1970,1,1))
        self.date_format = "{:%d/%m/%Y}"



class BooleanDelegate(StandardTableDelegate):

    def __init__(self,items,section_width = None,parent=None):
        # FIXME I don't think items are still necessary...
        super(BooleanDelegate,self).__init__(parent)

    def get_displayed_data(self,index):
        raise Exception("Not implemented yet")

    def createEditor(self,parent,option,index):
        editor = QCheckBox(parent)
        if option:
            editor.setGeometry(option.rect)
        return editor

    def setEditorData(self,editor,index):
        ts = index.model().data( index,Qt.UserRole)
        editor.setChecked( ts == True) # Protects against None

    def setModelData(self,editor,model,index):
        data = editor.isChecked()
        model.setData(index,data,Qt.UserRole)


from PySide.QtGui import QStandardItemModel



class EnumComboDelegate(StandardTableDelegate):
    """ The combo delegates will provide a drop down based editor for fixed enumerations.
    When in display mode, it will work as a simple label.
    When in edit mode, the delegate operates on the UserRole
    of the model (so that one can link the actual text
    representation with the object it represents)
    """

    # The combo box content is given by a model that
    # uses the DisplayRole for the labels and the UserRole for the data

    def __init__(self,enumeration,parent=None):
        StandardTableDelegate.__init__(self,parent)

        items = enumeration.symbols()

        self.model = QStandardItemModel(len(items), 1)
        for i in range(len(items)):
            self.model.setData( self.model.index(i,0), items[i].description, Qt.DisplayRole)
            self.model.setData( self.model.index(i,0), items[i], Qt.UserRole)

    def get_displayed_data(self,index):
        enum_symbol = index.model().data( index, Qt.UserRole)
        return enum_symbol.description

    def setEditorData(self,editor,index):

        # We provide a suitable default is the source data is null
        # (which is : leave the index on the first line of the combo)

        # Find the source data in our combo model so that we can
        # preselect it on the combo

        m = editor.model()

        # Read the source data at the index of the source model
        data = index.model().data( index,Qt.UserRole)
        if data:
            for i in range(m.rowCount()):
                if m.data(m.index(i,0),Qt.UserRole) == data:
                    editor.setCurrentIndex( i)
                    return



    def setModelData(self,editor,model,index):
        data = editor.itemData(editor.currentIndex()) # by default Qt.UserRole
        model.setData(index,data,Qt.UserRole)

    def createEditor(self,parent,option,index):

        # Qt takes ownership of the editor
        # Therefore I have recreate it each time this method is called

        combo = QComboBox(parent)
        combo.setModel(self.model)

        completer = QCompleter(combo)
        completer.setModel(self.model)
        completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion) # PopupCompletion)
        combo.setCompleter(completer)

        if option:
            # This is needed to put the combobox in the right place
            combo.setGeometry(option.rect)

        return combo



class AutoComboDelegate(StandardTableDelegate):

    def __init__(self,items,section_width = None,parent=None):
        super(AutoComboDelegate,self).__init__(parent)
        # Pay attention ! At this point labels and items
        # values are not set up !
        self.section_width = section_width

    def set_table(self,t):
        self.table = t

    def get_displayed_data(self,index):
        d = index.model().data( index,Qt.UserRole)
        if d:
            try:
                i = self.items.index(d)
            except ValueError as ex:
                mainlog.debug("Items are {}".format(self.items))
                return None
                raise ValueError("Can't find {} of type {} in the items".format(d,type(d)))

            return self.labels[i]
        else:
            return None

    def createEditor(self,parent,option,index):
        s = self.section_width
        if not s:
            s = [100,300]

        editor = AutoCompleteComboBox(self,parent,s)
        editor.make_str_model(self.labels,self.items)

        if option:
            editor.setGeometry(option.rect)

        return editor

    def setEditorData(self,editor,index):
        # print "setEditorData  AutoComboDelegate {}/{}".format(index.row(),index.column())
        ts = index.model().data( index,Qt.UserRole)
        # editor.setCurrentIndex( editor.findText(text_type(ts)))
        if ts in self.items:
            i = self.items.index(ts)
            editor.setCurrentIndex( i)
        elif len(self.items) > 0:
            editor.setCurrentIndex( 0)


    def setModelData(self,editor,model,index):
        #data = editor.currentText()
        ndx = editor.currentIndex()

        if ndx < 0:
            ndx = 0

        data = editor.itemData( ndx, Qt.UserRole)
        # print("AutoComboDelegate.setModelData ndx={} data={}".format(ndx,data))
        model.setData(index,data,Qt.UserRole)

    # closeEditor = Signal(QWidget,QAbstractItemDelegate.EndEditHint)



class DurationValidator(QValidator):
    def __init__(self):
        QValidator.__init__(self)
        self.parser = DurationParser()

    def validate(self,intext,pos):

        if intext == "." or intext == ":":
            # Allow to enter .5 for half an hour
            # or :5 for 5 minutes
            return QValidator.Intermediate

        try:
            p = self.parser.parse(intext)
        except ValueError as e:
            return QValidator.Invalid

        if p:
            # Duration must be positive
            return QValidator.Acceptable
        else:
            return QValidator.Intermediate



class DurationDelegate(StandardTableDelegate):
    def __init__(self,parent=None, format_as_float=True):
        StandardTableDelegate.__init__(self,parent)
        self.validator = DurationValidator()
        self.format_as_float = format_as_float

    def paint_data(self,painter,option,r,text,index):
        painter.drawText(r.x(),r.y(),r.width(),r.height(),Qt.AlignRight | option.displayAlignment,text)

    def get_displayed_data(self,index):
        d = index.model().data( index,Qt.UserRole)
        # mainlog.debug("DurationDelegate.get_displayed_data : ({}-{}) {} ({})".format(index.row(), index.column(), d, type(d)))
        if d:
            if self.format_as_float:
                return duration_to_s(d)
            else:
                return duration_to_hm(d, short_unit=True)

        else:
            return None

    def createEditor(self,parent,option,index):
        # editor = ValidatingLineEdit(parent)
        editor = QLineEdit(parent)
        editor.setValidator(self.validator)
        editor.setStyleSheet("padding-left: 0px;");
        editor.setGeometry(option.rect)
        return editor

    def setEditorData(self,editor,index):
        d = index.model().data( index,Qt.UserRole)
        if d:
            editor.setText( self.get_displayed_data(index))

    def setModelData(self,editor,model,index):

        if editor.text() == None or editor.text().strip() == "":
            model.setData(index,None,Qt.UserRole)
        else:
            parser = DurationParser()
            data = parser.parse(editor.text())
            # mainlog.debug("setModelData : {} -> {}".format(editor.text(),data))
            # The user gives the duration in hours
            model.setData(index,data,Qt.UserRole)





class PictureEditor(QPushButton):
    def __init__(self,parent):
        super(PictureEditor,self).__init__(parent)
        self.clicked.connect( self.new_picture)
        self.pixmap_as_icon = None

    def set_pixmap_as_icon(self,pixmap):

        self.pixmap_as_icon = pixmap

        if pixmap:
            icon = QIcon(pixmap)
            self.setIconSize(QSize(pixmap.width(),pixmap.height()))
            self.setIcon(pixmap)
        else:
            self.setIcon(QIcon())

    def new_picture(self):
        dialog = QFileDialog()
        if (dialog.exec_()):
            filename = dialog.selectedFiles()[0]
            # print "ok {}".format(filename)

            f = open(filename,"rb")
            bytes = f.read(-1)
            f.close()

            image = QImage.fromData(QByteArray(bytes))

            if image:
                # save as buffer(bytes)

                pixmap = QPixmap.fromImage(image.convertToFormat(QImage.Format_RGB16, Qt.MonoOnly).scaledToHeight(128))
                self.set_pixmap_as_icon(pixmap)


class PictureDelegate(StandardTableDelegate):
    def __init__(self,parent=None):
        StandardTableDelegate.__init__(self,parent)

    def paint(self,painter, option, index ):
        raise Exception("Not implemented yet !")

    def get_displayed_data(self,index):
        raise Exception("Not implemented yet !")

    def createEditor(self,parent,option,index):
        return PictureEditor(parent)

    def setEditorData(self,editor,index):
        pixmap = index.model().data( index,Qt.UserRole)
        editor.set_pixmap_as_icon(pixmap)

    def setModelData(self,editor,model,index):
        model.setData(index,editor.pixmap_as_icon,Qt.UserRole)


class TextAreaSpecialEdit(QPlainTextEdit):
    def __init__(self,parent):
        super(TextAreaSpecialEdit,self).__init__(parent)

    # def event(self,event):
    #     print "event!"
    #     # super(TextAreaSpecialEdit,self).event(event)
    #     return True

    def keyPressEvent(self,event):
        if event.key() in (Qt.Key_Enter,Qt.Key_Return) and \
                event.modifiers() & Qt.ControlModifier:
            self.insertPlainText("\n")
        super(TextAreaSpecialEdit,self).keyPressEvent(event)


class TextAreaTableDelegate(StandardTableDelegate):
    def timer_top(self):
        self.table.resizeRowsToContents()

    def __init__(self,parent=None):
        StandardTableDelegate.__init__(self,parent)
        self.i = 0
        self.last_bbox = dict()
        self.table = None

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.timer_top)

    def set_table(self,t):
        self.table = t

    def paint_data(self,painter,option,r,text,index):

        bbox = painter.boundingRect(r,Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap,text)
        k = "{}x{}".format(index.row(),index.column())

        # painter.drawRect(QRect(r.x(),r.y(),bbox.width(),bbox.height()))

        if bbox.height() > r.height():
            # We're too big
            # print "too big had ({}):{}x{} needed:{}x{}".format(k,r.width(),r.height(),bbox.width(),bbox.height())
            painter.drawText(r.x(),r.y(),r.width(),r.height(),Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap,text)
            self.last_bbox["{}x{}".format(index.row(),index.column())] = bbox

            if self.table:
                # If there are multiple redraws, they will be compressed
                # in only one

                # print "resizing"
                # self.table.program_redraw()
                self.timer.start(100)

                # self.table.resizeRowToContents(index.row())
        else:
            # print "enough space ({}) had:{}x{} needed:{}x{}".format(k, r.width(),r.height(),bbox.width(),bbox.height())
            painter.drawText(r.x(),r.y(),r.width(),r.height(),Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap,text)
            # if k in self.last_bbox:
            #     del self.last_bbox[k]

    def sizeHint(self, option, index):
        k = "{}x{}".format(index.row(),index.column())
        if "{}x{}".format(index.row(),index.column()) in self.last_bbox:
            s =  self.last_bbox[k]
            # print "reusing ndx={}  {}x{}".format(k,s.width(),s.height())
            del self.last_bbox[k]
            return QSize(s.width(),s.height())

        s = self.get_displayed_data(index)
        if s == None:
            return QSize(-1,-1)

        fm = QFontMetrics(option.font)
        w = self.table.columnWidth(index.column())
        # if option.rect.width() > 0:
        #     w = option.rect.width()
        size = fm.boundingRect(0, 0, w, 30000,Qt.AlignTop | Qt.AlignLeft | Qt.TextWordWrap, s, 0, [])

        # if s and len(s) > 50:
        #     print("[{}] w={} / s.w={} s.h={} txt:{}".format(self.i,w,size.width(),size.height(),s))

        # h = max( size.height(), self.last_bbox.height())
        # print "using ndx={}  {}x{}".format(k, size.width(),size.height())
        return QSize(size.width(),size.height()) # FIXME hardcoded value



    def createEditor(self,parent,option,index):
        # Qt takes ownership of the editor
        # Therefore I have recreate it each time this method is called

        editor = TextAreaSpecialEdit(parent)

        # print "setting geometry"

        w = 300
        h = 150

        if option:
            editor.setGeometry(option.rect.x(),option.rect.y(),w,h)
        else:
            editor.setGeometry(0,0,w,h)

        editor.setMinimumSize(w,h) # To set geometry is not enough

        return editor

    def setEditorData(self,editor,index):
        d = index.model().data( index,Qt.UserRole)
        if d:
            editor.setPlainText( self.get_displayed_data(index))
        else:
            editor.setPlainText( "")

    def setModelData(self,editor,model,index):
        data = editor.toPlainText()
        if data is None or len(data.strip()) == 0:
            model.setData(index,None,Qt.UserRole)
        else:
            model.setData(index,data,Qt.UserRole)



class TaskDisplayDelegate(StandardTableDelegate):
    def __init__(self,parent=None):
        StandardTableDelegate.__init__(self,parent)

    def get_displayed_data(self, index):
        t = index.model().data( index,Qt.UserRole)
        if t is None:
            return None
        else:
            return t.description



class DocumentCategoryDelegate(StandardTableDelegate):
    def __init__(self,parent=None):
        StandardTableDelegate.__init__(self,parent)
        self._categories = []

    def set_categories(self,categories=dict()):
        assert categories is not None,"Categories can't be None"

        self._categories = categories

    def get_displayed_data(self, index):
        c = index.model().data( index,Qt.UserRole)
        if c is None:
            return ""
        elif c in self._categories:
            return self._categories[c]
        else:
            mainlog.warn("Category {} is unknown to DocumentCategoryDelegate. Known categories are {}".format(c, self._categories))
            return ""



class OrderPartDisplayDelegate(StandardTableDelegate):
    def __init__(self,parent=None):
        StandardTableDelegate.__init__(self,parent)

    def get_displayed_data(self, index):
        d = index.model().data( index,Qt.UserRole)
        if d is None:
            return None
        else:
            return u"[{}] {}".format(d.human_identifier, d.description)

    def createEditor(self,parent,option,index):
        editor = super(OrderPartDisplayDelegate,self).createEditor(parent,option,index)
        if option:
            editor.setGeometry(option.rect)
        return editor

    def setEditorData(self,editor,index):
        # Read the source data at the index of the source model
        t = index.model().data( index,Qt.UserRole)
        if t is not None:
            editor.setText(t.human_identifier)
        else:
            editor.setText("")
