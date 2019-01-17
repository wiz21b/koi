import enum
from datetime import date
import sys

from PySide.QtCore import Qt,Slot,QModelIndex,QAbstractTableModel,Signal, QPoint, QObject, QEvent
from PySide.QtCore import QTimer
from PySide.QtGui import QHBoxLayout,QVBoxLayout,QLineEdit,QLabel,QGridLayout, QColor, QDialog, QMessageBox,QHeaderView,QAbstractItemView, \
    QKeySequence, QStandardItem,QComboBox, QAction,QMenu,QWidget,QCursor, QSizePolicy, QPushButton, QComboBox, QColor, QBrush, QDialogButtonBox, QLineEdit, QAbstractItemView, QMouseEvent, QPalette, QFormLayout

from PySide.QtGui import QTableWidget,QScrollArea, QResizeEvent, QFrame, QApplication

from PySide.QtGui import QRadioButton

from koi.gui.dialog_utils import TitleWidget

if __name__ == "__main__":
    from PySide.QtGui import QMainWindow

    from koi.base_logging import mainlog,init_logging
    from koi.Configurator import init_i18n,load_configuration,configuration

    init_logging()
    init_i18n()
    load_configuration()

    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session,session

    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)


class WireConfigurationToPart(QDialog):
    def __init__(self, parent, order_part):
        super( WireConfigurationToPart, self).__init__(parent)

        top_layout = QVBoxLayout()

        top_layout.addWidget( TitleWidget( "Attach configuration to part", None))

        hl = QHBoxLayout()
        hl.addWidget( QLabel("Plan number :"))
        hl.addWidget( QLineEdit())
        top_layout.addLayout( hl)

        top_layout.addWidget( QRadioButton("New configuration"))

        hlayout = QHBoxLayout()
        rb = QRadioButton()
        hlayout.addWidget( rb)
        hlayout.setAlignment( rb, Qt.AlignTop)

        vl = QVBoxLayout()
        vl.addWidget( QLabel( "Copy configuration"))
        hl = QHBoxLayout()
        hl.addWidget( QLabel("Part number :"))
        hl.addWidget( QLineEdit())
        vl.addLayout( hl)
        hlayout.addLayout( vl)

        top_layout.addLayout( hlayout)




        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.Cancel)
        self.buttons.addButton( QDialogButtonBox.Ok)
        top_layout.addWidget(self.buttons)

        self.setLayout(top_layout)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    d = WireConfigurationToPart(None, None)
    d.show()
    app.exec_()
