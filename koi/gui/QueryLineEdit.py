import re

from PySide.QtGui import QWidget, QHBoxLayout, QLineEdit
from PySide.QtCore import Qt,Slot,Signal,QModelIndex,QPoint
from koi.qtableviewfixed import QTableView  # FIXME Ugly import !

from koi.base_logging import mainlog

from koi.QuickComboModel import QuickComboModel # FIXME Ugly import !

from koi.datalayer.parser_utils import word_at_point

class CompletionDropDown(QWidget):
    def __init__(self):
        super(CompletionDropDown,self).__init__()
        self.setWindowModality(Qt.NonModal)
        self.setWindowFlags(Qt.FramelessWindowHint) # Qt.Tool | Qt.FramelessWindowHint

        l = QHBoxLayout()
        self.items_view= QTableView()

        # Make the dropdown nice
        l.setContentsMargins(0,0,0,0)
        self.items_view.horizontalHeader().setStretchLastSection(True)
        self.items_view.horizontalHeader().hide()
        self.items_view.verticalHeader().hide()
        self.items_view.setShowGrid(False)
        self.setMinimumSize(300,100)

        self.model = QuickComboModel(self)
        self.items_view.setModel(self.model)
        l.addWidget(self.items_view)
        self.setLayout(l)


    def get_current_completion(self):
        """ Get the currently selected completion """
        return self.items_view.currentIndex().data()

    @Slot(list)
    def set_possible_completions(self,completions):
        if completions:
            self.model.buildModelFromArray(completions)
            # self.show()
        else:
            self.model.clear()
            self.hide()

    completion_discarded = Signal()

    def keyPressEvent(self,event):
        if event.key() == Qt.Key_Escape:
            event.ignore()
            self.hide()
            self.completion_discarded.emit()

        return super(CompletionDropDown,self).keyPressEvent(event)



class QueryLineEdit(QLineEdit):

    # Used to know if a suggestion must be quoted
    # Note that's a poor man quoting. Quoting should be decided
    # by the suggestion finder because a string can be decided to
    # be quoted or not with 100% certainty only if one knows
    # what that string represents

    ONE_PIECE_STRING_RE = re.compile(r"[^\w=<>~]")

    def __init__(self, suggestion_finder):
        super(QueryLineEdit,self).__init__()
        self.completion = CompletionDropDown()
        self.suggestion_finder = suggestion_finder

        self.completion.items_view.activated.connect(self.completion_selected)
        self.completion.completion_discarded.connect(self.completion_discarded)

        # self.completer = QCompleter(["alpha","bravo"])
        # self.setCompleter(self.completer)


        self.error_shown = False

    def show_error(self):
        self.error_shown = True

        palette = self.palette()
        palette.setColor(QPalette.Base, QColor(255,0,255))
        self.setPalette(palette)

    def show_success(self):
        self.error = False

        palette = self.palette()
        palette.setColor(QPalette.Base, QColor(255,255,255))
        self.setPalette(palette)


    @Slot()
    def completion_discarded(self):
        # Transfer the focus from the completion list to
        # self.

        self.completion.hide()
        self.activateWindow()
        self.setFocus(Qt.OtherFocusReason)

    @Slot(QModelIndex)
    def completion_selected(self,ndx):
        self.completion.hide()
        self.activateWindow()
        self.setFocus(Qt.OtherFocusReason)

        t = self.text()
        cp = self.cursorPosition()
        w,start,end = word_at_point(self.text(), cp)

        action,start,end  = self.replacement_area

        completion = self.completion.get_current_completion()
        # if self.quote:
        #     completion = u"\"{}\"".format(completion)

        # if self.ONE_PIECE_STRING_RE.search(completion):
        #     completion = u"\"{}\"".format(completion.strip())

        completion = u" {} ".format(completion)

        if action == 'rep':
            mainlog.debug("Replacing {} in |{}|={} [{},{}] by {}".format(w,t,self.cursorPosition(),start,end,self.completion.get_current_completion()))

            t_start = (t[0:start] + completion).lstrip()
            t_end = t[end+1:len(t)]
            cp = len(t_start)
            t = t_start + t_end
        else:
            t_start = (t[0:start] + u" " + completion + u" ").lstrip()
            t_end =  t[end+1:len(t)]
            cp = len(t_start)
            t = t_start + t_end

        self.setText( t)
        self.setCursorPosition(cp)


    def cursorPos(self):
        return self.cursorRect().topLeft()

    def _show_completion(self):
        replacement_area,suggestions,needs_quoting = self.suggestion_finder( self.text(),
                                                                             self.cursorPosition())

        if suggestions:
            # mainlog.debug("Suggestions are ..." + str(suggestions))

            self.replacement_area = replacement_area

            p = self.mapToGlobal(QPoint(self.cursorPos().x(),
                                        self.height()))
            self.completion.set_possible_completions(suggestions)
            self.completion.move(p)

            self.completion.activateWindow() # So that show works
            self.completion.show()
            self.completion.raise_()

            self.completion.items_view.setFocus(Qt.OtherFocusReason)
            self.completion.items_view.setCurrentIndex(self.completion.model.index(0,0))
        else:
            self.replacement_area = None
            self.completion.set_possible_completions(None)
            self.completion.hide()

        # self.activateWindow()
        self.setFocus(Qt.OtherFocusReason)

        return suggestions

    def keyPressEvent(self,event):
        if event.key() == Qt.Key_Down:
            self._show_completion()
            event.ignore()
            # if self.completion.model.rowCount() > 0:
            #     self.completion.activateWindow()
            #     self.completion.show()
            #     self.completion.raise_()
            #     self.completion.items_view.setFocus(Qt.OtherFocusReason)
            #     self.completion.items_view.setCurrentIndex(self.completion.model.index(0,0))
            #     mainlog.debug("Key down")
            #     event.ignore()
            return super(QueryLineEdit,self).keyPressEvent(event)
        else:
            return super(QueryLineEdit,self).keyPressEvent(event)
