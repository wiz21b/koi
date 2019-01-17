from datetime import date

from PySide.QtCore import Slot, QDate
from PySide.QtGui import QDialog, QVBoxLayout, QLabel, QCalendarWidget, QDialogButtonBox, QPushButton, QHBoxLayout, QLayout

from koi.gui.dialog_utils import TitleWidget
from koi.base_logging import mainlog

class DatePick(QDialog):

    EMPTY_DATE = -1

    def accept(self, *args, **kwargs):

        if self.accepted_date == self.EMPTY_DATE:
            self.accepted_date = None
        elif self.accepted_date == None:
            d = self.qw.selectedDate()
            self.accepted_date = date( d.year(), d.month(), d.day())
        else:
            pass # we keep the accepted date

        return super(DatePick,self).accept()

    def reject(self, *args, **kwargs):
        self.accepted_date = None
        return super(DatePick,self).reject()

    @Slot()
    def _no_date_chosen(self):
        # User specifically chose "no date"
        self.accepted_date = self.EMPTY_DATE
        # accept will be called because the button has AcceptRole

    @Slot(date)
    def date_activated(self, chosen_date):
        self.accept()

    def resizeEvent(self, *args, **kwargs):
        # Will make sure the label gets all the size at show time.
        self.info_label.setMaximumWidth( self.width())

    def set(self, default_date : date, info_text : str, no_date_allowed = True):
        self.info_label.setText( info_text)
        self._no_date_button.setVisible( no_date_allowed)
        if default_date:
            self.qw.setSelectedDate( QDate( default_date.year, default_date.month, default_date.day))

        self.accepted_date = None

    def __init__(self, info_text, no_date_allowed = True):
        super(DatePick, self).__init__()

        self.accepted_date = None
        self.setObjectName("date_picker")
        layout = QVBoxLayout()

        title = _("Pick a date")
        self.setWindowTitle(title)
        layout.addWidget(TitleWidget(title, self))

        self.info_label =QLabel(info_text)
        self.qw = QCalendarWidget()

        hlayout = QHBoxLayout()
        hlayout.addStretch()
        hlayout.addWidget( self.qw)
        hlayout.addStretch()


        self.info_label.setWordWrap(True)
        self.info_label.setMaximumWidth(self.qw.minimumWidth())
        layout.addWidget( self.info_label)
        layout.addLayout(hlayout)
        self.qw.activated.connect(self.date_activated)

        self.buttons = QDialogButtonBox()

        self._no_date_button = QPushButton(_("No date"))
        self._no_date_button.clicked.connect( self._no_date_chosen)
        self.buttons.addButton( self._no_date_button, QDialogButtonBox.AcceptRole)

        self._no_date_button.setVisible( False) #not no_date_allowed)
        self._no_date_button.hide()

        self.buttons.addButton( QDialogButtonBox.StandardButton.Cancel)
        self.buttons.addButton( QDialogButtonBox.Ok)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout.addWidget(self.buttons)
        layout.addStretch()


        self.setLayout(layout)
        self.layout().setSizeConstraint( QLayout.SetFixedSize );



if __name__ == "__main__":
    import sys
    import logging
    from koi.base_logging import init_logging
    from koi.Configurator import init_i18n,load_configuration,configuration

    init_logging()

    from PySide.QtGui import QApplication
    app = QApplication(sys.argv)

    mainlog.setLevel( logging.DEBUG)

    global _
    _ = lambda x: x


    date_pick = DatePick( info_text="test text " * 20, no_date_allowed=False)
    date_pick.show()
    app.exec_()
    print( date_pick.accepted_date)
