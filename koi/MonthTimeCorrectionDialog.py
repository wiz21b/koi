from PySide.QtCore import Slot
from PySide.QtGui import QDialog,QLabel,QFormLayout,QDialogButtonBox,QVBoxLayout

if __name__ == "__main__":
    import sys
    from PySide.QtGui import QApplication

    from koi.base_logging import init_logging
    from koi.Configurator import init_i18n,load_configuration

    init_logging()
    init_i18n()
    load_configuration()
from koi.dao import dao

from koi.gui.editors import DurationEdit
from koi.translators import date_to_my

class MonthTimeCorrectionDialog(QDialog):
    def __init__(self,parent):
        super(MonthTimeCorrectionDialog,self).__init__(parent)

        self.setWindowTitle(_("Correction for month"))
        self.info = QLabel(_("Correction for month"),self)
        self.info.setWordWrap(True)

        self.correction_time_widget = DurationEdit(self)
        form_layout = QFormLayout()
        form_layout.addRow( _("Correction (hours)"), self.correction_time_widget)

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.Ok)
        self.buttons.addButton( QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.save_and_accept)
        self.buttons.rejected.connect(self.cancel)

        top_layout = QVBoxLayout()
        top_layout.addWidget(self.info)
        top_layout.addLayout(form_layout)
        top_layout.addWidget(self.buttons)

        self.setLayout(top_layout)

    def set_data(self,employee_fullname,d,correction):

        self.year = d.year
        self.month = d.month
        self.info.setText(_("Correction for {} on {}").format(employee_fullname,date_to_my(d,True)))
        self.correction_time_widget.setText(str(correction))

    @Slot()
    def save_and_accept(self):
        self.correction_time = self.correction_time_widget.value()
        return super(MonthTimeCorrectionDialog,self).accept()

    @Slot()
    def cancel(self):
        self.correction_time = 0
        return super(MonthTimeCorrectionDialog,self).reject()




if __name__ == "__main__":

    from koi.junkyard.services import services
    employee = services.employees.any()

    app = QApplication(sys.argv)
    d = MonthTimeCorrectionDialog(None)

    year = 2012
    month = 12
    correction_time = dao.month_time_synthesis_dao.load_correction_time(employee,year,month)

    print( correction_time)

    d.set_data(employee,year,month,correction_time)
    d.exec_()

    if d.result() == QDialog.Accepted:
        dao.month_time_synthesis_dao.save(d.employee,
                                          d.year, d.month,
                                          d.correction_time)
