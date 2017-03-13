import sys
from PySide.QtGui import QApplication

from koi.Configurator import init_i18n
init_i18n()
from koi.gui.ask_date import DatePick


app = QApplication(sys.argv)
# MAke sure word wraps
dialog = DatePick("alpha bravo zulu alpha bravo zulu alpha bravo zulu alpha bravo zulu alpha bravo zulu alpha bravo zulu")
dialog.exec_()
print(dialog.accepted_date)