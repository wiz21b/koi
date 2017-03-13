from datetime import date

from PySide.QtCore import Slot
from PySide.QtGui import QDialog, QVBoxLayout, QLabel, QCalendarWidget, QDialogButtonBox, QPushButton

from koi.gui.dialog_utils import TitleWidget


class DatePick(QDialog):

    def accept(self, *args, **kwargs):
        return super(DatePick,self).accept()

    def reject(self, *args, **kwargs):
        return super(DatePick,self).reject()

    @Slot(date)
    def date_chosen(self, chosen_date):
        self.accepted_date = date( chosen_date.year(), chosen_date.month(), chosen_date.day())
        self.accept()

    def resizeEvent(self, *args, **kwargs):
        self.info_label.setMaximumWidth( self.qw.width())

    def __init__(self, info_text, no_date_allowed = True):
        super(DatePick, self).__init__()

        self.accepted_date = None

        layout = QVBoxLayout()

        title = _("Pick a date")
        self.setWindowTitle(title)
        layout.addWidget(TitleWidget(title, self))

        self.info_label =QLabel(info_text)
        self.qw = QCalendarWidget()

        self.info_label.setWordWrap(True)
        self.info_label.setMaximumWidth(self.qw.minimumWidth())
        layout.addWidget( self.info_label)
        layout.addWidget( self.qw)
        self.qw.activated.connect(self.date_chosen)

        self.buttons = QDialogButtonBox()

        if no_date_allowed:
            self.buttons.addButton( QPushButton("No date"), QDialogButtonBox.ButtonRole.AcceptRole)

        self.buttons.addButton( QDialogButtonBox.StandardButton.Cancel)
        self.buttons.addButton( QDialogButtonBox.Ok)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout.addWidget(self.buttons)
        layout.addStretch()
        self.setLayout(layout)