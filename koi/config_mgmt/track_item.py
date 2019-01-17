import enum
from datetime import date
import sys

from PySide.QtCore import Qt,Slot,QModelIndex,QAbstractTableModel,Signal, QPoint, QObject, QEvent
from PySide.QtCore import QTimer
from PySide.QtGui import QHBoxLayout,QVBoxLayout,QLineEdit,QLabel,QGridLayout, QColor, QDialog, QMessageBox,QHeaderView,QAbstractItemView, \
    QKeySequence, QStandardItem,QComboBox, QAction,QMenu,QWidget,QCursor, QSizePolicy, QPushButton, QComboBox, QColor, QBrush, QDialogButtonBox, QLineEdit, QAbstractItemView, QMouseEvent, QPalette, QFormLayout
from PySide.QtGui import QTableWidget,QScrollArea, QResizeEvent, QFrame, QApplication
from PySide.QtGui import QRadioButton


if __name__ == "__main__":
    from PySide.QtGui import QMainWindow

    from koi.base_logging import init_logging
    from koi.Configurator import init_i18n,load_configuration,configuration

    init_logging()
    init_i18n()
    load_configuration()

    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session,session

    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)

from koi.base_logging import mainlog
from koi.gui.dialog_utils import TitleWidget
from koi.dao import dao
from koi.gui.completer import AutoCompleteComboBox
from koi.config_mgmt.mapping import ArticleConfiguration, Configuration
from koi.config_mgmt.service import configuration_management_service
from koi.datalayer.serializers import CopyArticleConfiguration

class TrackNewItemDialog(QDialog):

    def load_inputs(self, ac : CopyArticleConfiguration):
        self._customer_combo.setCurrentReference( ac.customer_id)
        self._plan_number.setText( ac.identification_number)
        self._revision_number.setText( ac.revision_number)

    def inputs(self):
        return  self._customer_combo.getCurrentReference(), self._plan_number.text(), self._revision_number.text()

    def __init__(self, parent, order_part):
        super( TrackNewItemDialog, self).__init__(parent)

        customers = dao.customer_dao.all()

        self._customer_combo = AutoCompleteComboBox( sections = [400] )
        self._customer_combo.make_model( [ [c.fullname] for c in customers ], [c.fullname for c in customers], [c.customer_id for c in customers])

        top_layout = QVBoxLayout()
        top_layout.addWidget( TitleWidget( _("Track a plan with configuration management"), None))

        hl = QHBoxLayout()
        hl.addWidget( QLabel("Customer :"))
        hl.addWidget( self._customer_combo)
        top_layout.addLayout( hl)

        hl = QHBoxLayout()
        hl.addWidget( QLabel("Plan number :"))
        self._plan_number = QLineEdit()
        hl.addWidget( self._plan_number)
        top_layout.addLayout( hl)

        hl = QHBoxLayout()
        hl.addWidget( QLabel("Plan revision number :"))
        self._revision_number = QLineEdit()
        hl.addWidget( self._revision_number)
        top_layout.addLayout( hl)

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.Cancel)
        self.buttons.addButton( QDialogButtonBox.Ok)
        top_layout.addWidget(self.buttons)

        self.setLayout(top_layout)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)


if __name__ == "__main__":
    dao.set_session( session())
    app = QApplication(sys.argv)
    d = TrackNewItemDialog(None, None)
    d.show()
    app.exec_()
