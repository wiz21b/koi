from PySide.QtGui import QStyledItemDelegate,QStyle,QApplication,QStyleOptionButton,QPalette
from PySide.QtCore import Qt,QRect,QSize,QDate,QPoint,QEvent


class CheckBoxDelegate(QStyledItemDelegate):
    '''
    Code taken from : http://stackoverflow.com/questions/3363190/qt-qtableview-how-to-have-a-checkbox-only-column
    '''

    def createEditor(self, parent, option, index):
        '''
        Important, otherwise an editor is created if the user clicks in this cell.
        '''
        return None

    def paint(self, painter, option, index):
        '''
        Paint a checkbox without the label.
        '''

        value = index.model().data(index, Qt.DisplayRole)

        if value == None:
            return
        # we draw the background

        cg = QPalette.Disabled
        if option.state & QStyle.State_Enabled:
            cg = QPalette.Normal
            if not (option.state & QStyle.State_Active):
                cg = QPalette.Inactive

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

        checked = bool(index.model().data(index, Qt.DisplayRole))
        check_box_style_option = QStyleOptionButton()

        if (index.flags() & Qt.ItemIsEditable) > 0:
            check_box_style_option.state |= QStyle.State_Enabled
        else:
            check_box_style_option.state |= QStyle.State_ReadOnly

        if checked:
            check_box_style_option.state |= QStyle.State_On
        else:
            check_box_style_option.state |= QStyle.State_Off

        check_box_style_option.rect = self.getCheckBoxRect(option)

        # if not index.model().hasFlag(index, Qt.ItemIsEditable):
        if not ((index.flags() & Qt.ItemIsEditable) > 0):
             check_box_style_option.state |= QStyle.State_ReadOnly

        QApplication.style().drawControl(QStyle.CE_CheckBox, check_box_style_option, painter)


    def editorEvent(self, event, model, option, index):
        '''
        Change the data in the model and the state of the checkbox
        if the user presses the left mousebutton or presses
        Key_Space or Key_Select and this cell is editable. Otherwise do nothing.
        '''
        if not (index.flags() & Qt.ItemIsEditable) > 0:
            return False

        # Do not change the checkbox-state
        if event.type() == QEvent.MouseButtonRelease or event.type() == QEvent.MouseButtonDblClick:
            if event.button() != Qt.LeftButton or not self.getCheckBoxRect(option).contains(event.pos()):
                return False
            if event.type() == QEvent.MouseButtonDblClick:
                return True
        elif event.type() == QEvent.KeyPress:
            if event.key() != Qt.Key_Space and event.key() != Qt.Key_Select:
                return False
        else:
            return False

        # Change the checkbox-state
        self.setModelData(None, model, index)
        return True

    def setModelData (self, editor, model, index):
        '''
        The user wanted to change the old state in the opposite.
        '''
        newValue = not bool(index.model().data(index, Qt.DisplayRole))
        model.setData(index, newValue, Qt.EditRole)


    def getCheckBoxRect(self, option):
        check_box_style_option = QStyleOptionButton()
        check_box_rect = QApplication.style().subElementRect(QStyle.SE_CheckBoxIndicator, check_box_style_option, None)
        check_box_point = QPoint (option.rect.x() +
                                  option.rect.width() / 2 -
                                  check_box_rect.width() / 2,
                                  option.rect.y() +
                                  option.rect.height() / 2 -
                                  check_box_rect.height() / 2)
        return QRect(check_box_point, check_box_rect.size())
