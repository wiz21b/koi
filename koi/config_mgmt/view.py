from enum import Enum
from datetime import date
import os.path
import sys
import platform

from PySide.QtCore import Qt,Slot,QModelIndex,QAbstractTableModel,Signal, QPoint
from PySide.QtCore import QTimer
from PySide.QtGui import QHBoxLayout,QVBoxLayout,QLineEdit,QLabel,QGridLayout, QColor, QDialog, QMessageBox,QHeaderView,QAbstractItemView, \
    QKeySequence, QStandardItem,QComboBox, QAction,QMenu,QWidget,QCursor, QSizePolicy, QPushButton, QComboBox, QColor, QBrush, QDialogButtonBox, QLineEdit, QAbstractItemView
from PySide.QtGui import QDragEnterEvent,QDragMoveEvent, QStandardItem, QStandardItemModel


if __name__ == "__main__":
    from PySide.QtGui import QApplication,QMainWindow

    from koi.base_logging import mainlog,init_logging
    from koi.Configurator import init_i18n,load_configuration,configuration

    init_logging()
    init_i18n()
    load_configuration()

    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session,session

    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)

from koi.gui.ObjectModel import ObjectModel
from koi.gui.ComboDelegate import PythonEnumComboDelegate
from koi.gui.ProxyModel import PrototypeController,IntegerNumberPrototype,FloatNumberPrototype, DurationPrototype,TrackingProxyModel,OperationDefinitionPrototype,PrototypedTableView,ProxyTableView,OrderPartDisplayPrototype,TextAreaPrototype, FutureDatePrototype,PrototypeArray,TextLinePrototype, Prototype, DatePrototype, BooleanPrototype
from koi.gui.dialog_utils import SubFrame

from koi.gui.PrototypedModelView import PrototypedModelView


class ImpactApproval(Enum):
    UNDER_CONSTRUCTION = "Under construction"
    APPROVED = "Approved"
    REJECTED = "Rejected"

class TypeConfigDoc(Enum):
    IMPACT = "Impact document"
    PLAN_2D = "Plan 2D"
    PROGRAM = "Programme"

class CRL(Enum):
    C = "À consulter"
    R = "À remplir"
    LC = "À livrer au client"
    RLC = "À remplir et livrer au client"
    LF = "À livrer au fournisseur"
    RLF = "À remplir et livrer au fournisseur"

    def __str__( self, e):
        return e.value[1]



class EnumPrototype(Prototype):
    def __init__(self,field,title,enumeration : Enum,editable=True,nullable=False):
        super(EnumPrototype,self).__init__(field,title,editable,nullable)
        self.set_delegate(
            PythonEnumComboDelegate( enumeration)) # items, sizes


class Line:
    def __init__( self, description, version, type_, file_):
        self.description = description
        self.version = version
        self.type = type_
        self.file = file_
        self.modify_config = False
        self.date_upload = date.today()
        self.crl = CRL.C


class ImpactLine:
    def __init__( self, description = "", version = "", file_ = ""):
        self.description = description
        self.version = version
        self.file = file_
        self.date_upload = date.today()
        self.approval = ImpactApproval.UNDER_CONSTRUCTION

class ImpactLineExtended:

    def __init__( self, obj : ImpactLine):
        object.__setattr__( self, "_object", obj)
        object.__setattr__( self, "selected", False)

    def __getattr__(self,name):
        if hasattr(  object.__getattribute__( self, "_object"), name):
            return getattr( self._object, name)
        else:
            return object.__getattribute__(self, name)

    def __setattr__(self,name, value):
        if hasattr(  object.__getattribute__( self, "_object"), name):
            return setattr( object.__getattribute__( self, "_object"), name, value)
        else:
            return object.__setattr__(self, name, value)

il = ImpactLine("test")
ilo = ImpactLineExtended( il)
assert ilo.description == "test"
assert ilo.selected == False

ilo.description = "new"
ilo.selected = True
assert ilo.description == "new"
assert ilo.selected == True, "{} ?".format(ilo.selected)

assert il.description == "new"


class Configuration:
    def __init__(self):
        self.frozen = date(2018,1,31)
        self.version = 1
        self.freezer = "Daniel Dumont"
        self.lines = [ Line( "Plan ZZ1D", 2, TypeConfigDoc.PLAN_2D, "plan3EDER4.3ds"),
                       Line( "Config TN", 2, TypeConfigDoc.PROGRAM, "tige.gcode"),
                       Line( "Config TN", 1, TypeConfigDoc.PROGRAM, "anti-tige.gcode") ]

def make_configs():

    configurations = []
    configurations.append( Configuration())

    c = Configuration()
    c.lines = [ Line( "Fiche d'impact", 1, TypeConfigDoc.IMPACT, "impact_1808RXC.doc"),
                Line( "Plan ZZ1D", 2, TypeConfigDoc.PLAN_2D, "plan3EDER4.3ds"),
                Line( "Config TN", 2, TypeConfigDoc.PROGRAM, "tige.gcode"),
                Line( "Config TN", 1, TypeConfigDoc.PROGRAM, "anti-tige.gcode") ]
    c.version = 2
    c.frozen = date(2018,2,5)
    c.lines[2].modify_config = False
    configurations.append( c)

    c = Configuration()
    c.lines = [ Line( "Fiche d'impact", 1, TypeConfigDoc.IMPACT, "impact_1808RXC.doc"),
                Line( "Plan ZZ1D", 2, TypeConfigDoc.PLAN_2D, "plan3EDER4.3ds"),
                Line( "Config TN", 2, TypeConfigDoc.PROGRAM, "tige.gcode"),
                Line( "Config TN", 1, TypeConfigDoc.PROGRAM, "anti-tige.gcode") ]
    c.version = 3
    c.frozen = None
    c.lines[2].modify_config = True
    configurations.append( c)

    return configurations


def make_impacts():
    impacts = [ ImpactLine("Dilatation issues"),
                ImpactLine("From mini-series to series") ]

    for i in range( len( impacts)):
        impacts[i] = ImpactLineExtended( impacts[i] )
    return impacts


from koi.gui.dialog_utils import TitleWidget


class ConfigModel(ObjectModel):

    def __init__(self, parent, prototypes, blank_object_factory):
        super(ConfigModel, self).__init__( parent, prototypes, blank_object_factory)

    def background_color_eval(self,index):

        l = self.object_at( index)
        if l.modify_config:
            return QBrush(Qt.GlobalColor.yellow)
        elif l.type == TypeConfigDoc.IMPACT:
            return QBrush(Qt.GlobalColor.green)
        else:
            return super(ConfigModel, self).background_color_eval( index)


class ImpactsModel(ObjectModel):

    def __init__(self, parent, prototypes, blank_object_factory):
        super(ImpactsModel, self).__init__( parent, prototypes, blank_object_factory)



class FreezeConfiguration(QDialog):
    def __init__(self, parent, impacts):
        super( FreezeConfiguration, self).__init__(parent)

        self._impacts = impacts

        title = _("Freeze a configuration")
        self.setWindowTitle(title)

        config_impact_proto = []
        config_impact_proto.append( BooleanPrototype('selected', "", editable=True))
        config_impact_proto.append( TextLinePrototype('description',_('Description'),editable=True))
        config_impact_proto.append( IntegerNumberPrototype('version',_('Rev.'),editable=False))
        config_impact_proto.append( TextLinePrototype('file',_('File'), editable=False))
        config_impact_proto.append( DatePrototype('date_upload',_('Date'), editable=False))
        config_impact_proto.append( EnumPrototype('approval',_('Approval'), ImpactApproval, editable=False))


        top_layout = QVBoxLayout()

        top_layout.addWidget( QLabel("Please select the impact(s) document(s) that triggers the new configuration. You must select at least one of them."))

        self._model_impact = ImpactsModel( self, config_impact_proto, ImpactLine)
        self._view_impacts = PrototypedTableView(None, config_impact_proto)
        self._view_impacts.setModel( self._model_impact)
        self._view_impacts.verticalHeader().hide()
        self._view_impacts.horizontalHeader().setResizeMode( QHeaderView.ResizeToContents)
        # self._view_impacts.setEditTriggers(QAbstractItemView.NoEditTriggers)
        # self._view_impacts.setSelectionBehavior(QAbstractItemView.SelectRows)

        top_layout.addWidget( self._view_impacts)

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.Cancel)
        self.buttons.addButton( QDialogButtonBox.Ok)
        top_layout.addWidget(self.buttons)

        self.setLayout(top_layout)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        self._model_impact.reset_objects( self._impacts )

    @Slot()
    def accept(self):
        return super(FreezeConfiguration,self).accept()

    @Slot()
    def reject(self):
        return super(FreezeConfiguration,self).reject()



class AddFileToConfiguration(QDialog):
    def __init__(self, parent, filename, previous_lines):
        super( AddFileToConfiguration, self).__init__(parent)

        self.filename = filename
        self.description = ""
        self.type = TypeConfigDoc.PROGRAM
        self.version = 1

        title = _("Add a file to a configuration")
        self.setWindowTitle(title)

        top_layout = QVBoxLayout()
        self.setLayout(top_layout)

        top_layout.addWidget( QLabel("Filename : <b>{}</b>".format( filename)))

        type_choice = QComboBox()
        for s in TypeConfigDoc:
            type_choice.addItem( s.value[0])

        top_layout.addWidget( QLabel("Type :"))
        top_layout.addWidget( type_choice)

        self._decription_widget = QLineEdit()
        top_layout.addWidget( QLabel("Description :"))
        top_layout.addWidget( self._decription_widget)

        version_choice = QComboBox()
        version_choice.addItem(None)
        for l in previous_lines:
            version_choice.addItem( l.file)

        top_layout.addWidget( QLabel("Updates"))
        top_layout.addWidget( version_choice)
        top_layout.addStretch()

        self.crl_choice = QComboBox()
        for s in CRL:
            self.crl_choice.addItem( s.value[0], s)

        top_layout.addWidget( QLabel("CRL :"))
        top_layout.addWidget( self.crl_choice)


        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.Cancel)
        self.buttons.addButton( QDialogButtonBox.Ok)
        top_layout.addWidget(self.buttons)

        self.setLayout(top_layout)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    @Slot()
    def accept(self):
        self.description = self._decription_widget.text()
        self.crl = self.crl_choice.itemData( self.crl_choice.currentIndex())
        return super(AddFileToConfiguration,self).accept()

    @Slot()
    def reject(self):
        return super(AddFileToConfiguration,self).reject()





class EditConfiguration(QWidget):

    def version_selected( self, ndx):
        self.set_config( self._configs[ndx] )

    def set_config( self, config):

        self._current_config = config

        msg = "Version <b>{}</b>, ".format( config.version)
        if config.frozen:
            msg += "<b><font color = 'green'>FROZEN on {} by {}</font></b>".format( config.frozen, config.freezer)
            self._freeze_button.setText("Unfreeze")
        else:
            msg += "<b><font color = 'red'>NOT frozen</font></b>"
            self._freeze_button.setText("Freeze")

        self._info_label.setText( msg)
        self._model.reset_objects( config.lines )

    def __init__( self, parent):
        super(EditConfiguration,self).__init__(parent)

        self._configs = make_configs()
        self._impacts = make_impacts()
        self._title_widget = TitleWidget( "Configuration", self)

        self._title_widget.set_title("Configuration, commande <b>{}</b>, article <b>{}</b>".format("2576B", "XDR-1234-Z"))
        config_file_proto = []
        config_file_proto.append( TextLinePrototype('description',_('Description'),editable=False))
        config_file_proto.append( IntegerNumberPrototype('version',_('Rev.'),editable=False))
        config_file_proto.append( EnumPrototype('type',_('Type'), TypeConfigDoc, editable=False))
        config_file_proto.append( TextLinePrototype('file',_('File'), editable=False))
        config_file_proto.append( DatePrototype('date_upload',_('Date'), editable=False))
        config_file_proto.append( EnumPrototype('crl',_('CRL'), CRL, editable=True))

        config_impact_proto = []
        config_impact_proto.append( TextLinePrototype('description',_('Description'),editable=False))
        config_impact_proto.append( IntegerNumberPrototype('version',_('Rev.'),editable=False))
        config_impact_proto.append( TextLinePrototype('file',_('File'), editable=False))
        config_impact_proto.append( DatePrototype('date_upload',_('Date'), editable=False))
        config_impact_proto.append( EnumPrototype('approval',_('Approval'), ImpactApproval, editable=False))




        hlayout2 = QHBoxLayout()

        self._info_label = QLabel("msg")
        hlayout2.addWidget( self._info_label)
        hlayout2.addStretch()
        self._freeze_button = QPushButton("Accept && Freeze")
        hlayout2.addWidget( self._freeze_button)
        version_choice = QComboBox()
        for c in self._configs:
            version_choice.addItem("Revision {}".format(c.version))
        hlayout2.addWidget( version_choice)
        self.version_choice = version_choice
        self.version_choice.activated.connect( self.version_selected)

        top_layout = QVBoxLayout()
        top_layout.addWidget( self._title_widget)
        top_layout.addLayout(hlayout2)

        self._view = PrototypedTableView(None, config_file_proto)

        # self.headers_view = QHeaderView( Qt.Orientation.Horizontal)
        # self.header_model = make_header_model( config_file_proto, self._model)
        # self.headers_view.setModel( self.header_model) # qt's doc : The view does *not* take ownership (but there's something with the selecion mode)



        self._model = ConfigModel( self, config_file_proto, lambda : None)
        self._view.setModel( self._model)
        self._view.verticalHeader().hide()
        self._view.horizontalHeader().setResizeMode( QHeaderView.ResizeToContents)
        subframe = SubFrame("<B>Con</b>figuration", self._view, self)
        top_layout.addWidget( subframe)


        self._model_impact = ImpactsModel( self, config_impact_proto, ImpactLine)
        self._model_impact.insertRows( 0,3)

        self._view_impacts = PrototypedTableView(None, config_impact_proto)
        self._view_impacts.setModel( self._model_impact)
        self._view_impacts.verticalHeader().hide()
        self._view_impacts.horizontalHeader().setResizeMode( QHeaderView.ResizeToContents)
        subframe2 = SubFrame("Changes", self._view_impacts, self)
        top_layout.addWidget( subframe2)

        self.version_choice.setCurrentIndex(len( self._configs) - 1)
        self.version_selected( len( self._configs) - 1)
        self.setLayout(top_layout)
        self.setAcceptDrops(True)

        self._model_impact.reset_objects( self._impacts )

        self._freeze_button.clicked.connect( self.freeze_configuration)

    @Slot()
    def freeze_configuration(self):
        dialog = FreezeConfiguration( self, self._impacts)
        dialog.exec_()
        if dialog.result() == QDialog.Accepted:
            self._model_impact.reset_objects( self._impacts )

        dialog.deleteLater()


    def dragEnterEvent(self, e : QDragEnterEvent):
        """ Only accept what looks like a file drop action
        :param e:
        :return:
        """

        if e.mimeData() and e.mimeData().hasUrls() and e.mimeData().urls()[0].toString().startswith("file://") and e.proposedAction() == Qt.DropAction.CopyAction:

            mainlog.debug("dragEnterEvent : I accept")
            # Attention ! The actual drop area is smaller
            # than the dragEnter area !

            e.acceptProposedAction()
            e.accept()

    def dragMoveEvent(self, e: QDragMoveEvent):
        e.accept()

    def dragLeaveEvent(self, e):
        e.accept()

    def dropEvent(self, e):
        e.accept()

        paths = []
        for url in e.mimeData().urls():
            if platform.system() == "Windows":
                full_path_client = url.toString().replace('file:///','')
            else:
                full_path_client = url.toString().replace('file://','')

            # FIXME prototype !!

            filename = os.path.split( full_path_client)[-1]
            paths.append( filename)

        dialog = AddFileToConfiguration( self, paths[0], [])
        dialog.exec_()
        if dialog.result() == QDialog.Accepted:
            new_line = Line( dialog.description, dialog.version, dialog.type, dialog.filename)
            new_line.crl = dialog.crl
            new_line.modify_config = True
            self._current_config.lines.append( new_line)

            # FIXME should use a simpmle "datachagned" no ?
            self._model.reset_objects( self._current_config.lines )

        dialog.deleteLater()

if __name__ == "__main__":

    app = QApplication(sys.argv)

    mw = QMainWindow()
    mw.setMinimumSize(768,512)
    widget = EditConfiguration(mw)
    mw.setCentralWidget(widget)
    mw.show()


    app.exec_()
