from enum import Enum
from datetime import date
import sys
from typing import List, Any

from PySide.QtCore import Qt,Slot,QModelIndex,QAbstractTableModel,Signal, QPoint
from PySide.QtCore import QTimer
from PySide.QtGui import QHBoxLayout,QVBoxLayout,QLineEdit,QLabel,QGridLayout, QColor, QDialog, QMessageBox,QHeaderView,QAbstractItemView, \
    QKeySequence, QStandardItem,QComboBox, QAction,QMenu,QWidget,QCursor, QSizePolicy, QPushButton, QComboBox, QColor, QBrush, QDialogButtonBox, QLineEdit, QAbstractItemView


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

# from koi.db_mapping import Employee
# for t in session().query(Employee.employee_id).all():
#     print("{} {}".format( type(t), t.employee_id))

from koi.gui.ObjectModel import ObjectModel
from koi.gui.ComboDelegate import PythonEnumComboDelegate
from koi.gui.ProxyModel import PrototypeController,IntegerNumberPrototype,FloatNumberPrototype, DurationPrototype,TrackingProxyModel,OperationDefinitionPrototype,PrototypedTableView,ProxyTableView,OrderPartDisplayPrototype,TextAreaPrototype, FutureDatePrototype,PrototypeArray,TextLinePrototype, Prototype, DatePrototype, BooleanPrototype
from koi.gui.dialog_utils import SubFrame, TitleWidget

from koi.gui.PrototypedModelView import PrototypedModelView
from koi.config_mgmt.dragdrop_widget import DragDropWidget

class ImpactApproval(Enum):
    UNDER_CONSTRUCTION = "Under construction"
    APPROVED = "Approved"
    REJECTED = "Rejected"

class TypeConfigDoc(Enum):
    IMPACT = "Impact document"
    PLAN_2D = "Plan 2D"
    PLAN_3D = "Plan 3D"
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
    def __init__( self):
        self.owner = "Chuck Noris"
        self.description = None
        self.file = None
        self.date_upload = date.today()
        self.approval = ImpactApproval.UNDER_CONSTRUCTION
        self.approved_by = None
        self.active_date = date.today()
        self.configuration = None

    @property
    def version(self):
        if self.configuration:
            return self.configuration.version
        else:
            return None


class ImpactLineExtended:
    """ adds a "selected" field to a regular impact using a Proxy"""

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

il = ImpactLine()
il.description = 'test'
ilo = ImpactLineExtended( il)
assert ilo.description == "test"
assert ilo.selected == False

ilo.description = "new"
ilo.selected = True
assert ilo.description == "new"
assert ilo.selected == True, "{} ?".format(ilo.selected)

assert il.description == "new"


class Configuration:
    article_configuration: "ArticleConfiguration"

    def __init__(self):
        self.frozen = None
        self.freezer = None
        self.lines = []
        self.version = 0
        self.article_configuration = None


        # self.impacts = []


class ArticleConfiguration:
    configurations: List[Configuration]

    def __init__(self):
        self.description = ""
        self.file = ""
        self.file_revision = "E"

        # The different configurations.
        # In the normal scenario, the first configuration has no impact file
        # and the following configurations have at least an impact file.
        # Some impact files may not have a configuration (for example, while
        # they are written) (this prevents, for example, an impact file that is
        # rejected has an empty configuiration tied to it).
        self.configurations = []

        # The story of changes brought to the article configuration.
        # Each working configuration should be tied to an impact.
        self.impacts = []


    @property
    def full_version(self):
        return "{}/{}".format( self.description, self.file_revision)

    def current_configuration(self):
        i = len(self.configurations) - 1

        if i > 0:
            while i >= 0:
                if self.configurations[i].frozen:
                    return self.configurations[i]
                i -= 1

            return self.configurations[-1]
        else:
            return self.configurations[0]



def make_configs():

    ac = ArticleConfiguration()

    c = Configuration()
    c.version = 1
    c.article_configuration = ac
    c.frozen = date(2018,1,31)
    c.freezer = "Daniel Dumont"
    c.lines = [ Line( "Plan ZZ1D", 2, TypeConfigDoc.PLAN_3D, "plan3EDER4.3ds"),
                Line( "Config TN", 2, TypeConfigDoc.PROGRAM, "tige.gcode"),
                Line( "Config TN", 1, TypeConfigDoc.PROGRAM, "anti-tige.gcode") ]
    ac.configurations.append( c)

    c = Configuration()
    c.article_configuration = ac
    c.lines = [ Line( "Plan coupe 90°", 1, TypeConfigDoc.PLAN_3D, "impact_1808RXC.doc"),
                Line( "Plan ZZ1D", 2, TypeConfigDoc.PLAN_2D, "plan3EDER4.3ds"),
                Line( "Config TN", 2, TypeConfigDoc.PROGRAM, "tige.gcode"),
                Line( "Config TN", 1, TypeConfigDoc.PROGRAM, "anti-tige.gcode") ]
    c.version = 2
    c.frozen = date(2018,2,5)
    c.freezer = "Falken"
    c.lines[2].modify_config = False
    ac.configurations.append( c)

    c = Configuration()
    c.article_configuration = ac
    c.lines = [ Line( "Operations", 1, TypeConfigDoc.PLAN_3D, "impact_1808RXC.doc"),
                Line( "Plan ZZ1D", 2, TypeConfigDoc.PLAN_2D, "plan3EDER4.3ds"),
                Line( "Config TN", 2, TypeConfigDoc.PROGRAM, "tige.gcode"),
                Line( "Config TN", 1, TypeConfigDoc.PROGRAM, "anti-tige.gcode") ]
    c.version = 3
    c.frozen = None
    c.lines[2].modify_config = True
    ac.configurations.append( c)

    impact = ImpactLine()
    impact.owner = "Chuck Noris"
    impact.description = "preproduction measurement side XPZ changed"
    impact.date_upload = date.today()
    impact.approval = ImpactApproval.APPROVED
    impact.approved_by = "Deckerd"
    impact.active_date = date(2013,1,11)
    impact.configuration = ac.configurations[0]
    ac.impacts.append( impact)

    impact = ImpactLine()
    impact.owner = "Chuck Noris"
    impact.description = "Aluminium weight reduction"
    impact.date_upload = date.today()
    impact.approval = ImpactApproval.APPROVED
    impact.approved_by = "John Wayne"
    impact.active_date = None
    impact.configuration = ac.configurations[1]
    ac.impacts.append( impact)

    impact = ImpactLine()
    impact.owner = "Chuck Noris"
    impact.description = "Production settings"
    impact.date_upload = date.today()
    impact.approval = ImpactApproval.UNDER_CONSTRUCTION
    impact.approved_by = None
    impact.active_date = None
    impact.configuration = None
    ac.impacts.append( impact)

    impact = ImpactLine()
    impact.owner = "Bruce Lee"
    impact.description = "Production settings v2"
    impact.date_upload = date.today()
    impact.approval = ImpactApproval.UNDER_CONSTRUCTION
    impact.approved_by = None
    impact.active_date = None
    impact.configuration = None
    ac.impacts.append( impact)

    ac.description = "Plan ZERDF354-ZXZ-2001"
    ac.file = "ZERDF354-ZXZ-2001.3ds"
    ac.file_revision = "P1"

    ac2 = ArticleConfiguration()
    ac2.description = "Plan ZERDF354-ZXZ-2001"
    ac2.file = "ZERDF354-ZXZ-2001.3ds"
    ac2.file_revision = "P2"
    c = Configuration()
    c.article_configuration = ac2
    ac2.configurations.append( c)

    return [ac, ac2]





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

    def _make_ui(self):
        title = _("Freeze a configuration")
        self.setWindowTitle(title)

        config_impact_proto = []
        config_impact_proto.append( BooleanPrototype('selected', "", editable=True))
        config_impact_proto.append( TextLinePrototype('description',_('Description'),editable=True))
        config_impact_proto.append( IntegerNumberPrototype('version',_('Rev.'),editable=False))
        config_impact_proto.append( TextLinePrototype('file',_('File'), editable=False))
        config_impact_proto.append( EnumPrototype('approval',_('Approval'), ImpactApproval, editable=False))
        config_impact_proto.append( DatePrototype('date_upload',_('Date'), editable=False))


        top_layout = QVBoxLayout()

        top_layout.addWidget( QLabel("Please select the impact(s) document(s) that correspond to the new frozen configuration."))

        self._model_impact = ImpactsModel( self, config_impact_proto, None) # We won't create impact lines here
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

    def __init__(self, parent, config : Configuration, impacts):
        super( FreezeConfiguration, self).__init__(parent)

        self._make_ui()

        self.impacts = [ ImpactLineExtended( c ) for c in impacts]
        self._model_impact.reset_objects( self.impacts )

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




from koi.gui.horse_panel import HorsePanel


class EditConfiguration(HorsePanel):

    def version_selected( self, ndx):
        self.set_config( self._configs.configurations[ndx] )

    def set_config( self, config):

        self._current_config = config

        msg = "Configuration for <b>{}</b>, ".format( config.article_configuration.full_version)


        if config.frozen:
            freeze_msg = "<b><font color = 'green'>FROZEN on {} by {}</font></b>".format( config.frozen, config.freezer)
            self._freeze_button.setText("Unfreeze")
        else:
            freeze_msg = "<b><font color = 'red'>NOT frozen</font></b>"
            self._freeze_button.setText("Freeze")


        self._subframe.set_title( msg)

        self._version_config_label.setText( "Revision {}, {}".format(config.version, freeze_msg))

        self._model.reset_objects( config.lines )

    def set_article_configuration( self, aconfig):
        self._model_impact.reset_objects( aconfig.impacts )

    @Slot()
    def freeze_configuration(self):

        impacts = filter( lambda imp: imp.approval == ImpactApproval.UNDER_CONSTRUCTION, self._configs.impacts)

        dialog = FreezeConfiguration( self, self._current_config, impacts)
        dialog.exec_()
        if dialog.result() == QDialog.Accepted:

            self._current_config.frozen = date.today()
            self._current_config.freezer = "Daniel Dumont"

            c = Configuration()
            c.frozen = None
            c.version = max([c.version for c in self._configs.configurations]) + 1
            self._configs.configurations.append( c)

            # for c in range( self.version_choice.count()):
            #     self.version_choice.removeItem(0)

            # for c in self._configs:
            #     self.version_choice.addItem("Revision {}".format(c.version))

            # self.version_choice.setCurrentIndex( len(self._configs) - 2)
            #self.version_selected( len(self._configs) - 2)

        dialog.deleteLater()

    @Slot()
    def configFilesDropped( self,paths):
        dialog = AddFileToConfiguration( self, paths[0][1], [])
        dialog.exec_()
        if dialog.result() == QDialog.Accepted:
            new_line = Line( dialog.description, dialog.version, dialog.type, dialog.filename)
            new_line.crl = dialog.crl
            new_line.modify_config = True
            self._current_config.lines.append( new_line)

            # FIXME should use a simpmle "datachagned" no ?
            self._model.reset_objects( self._current_config.lines )

        dialog.deleteLater()

    @Slot()
    def impactFilesDropped( self,paths):
        dialog = AddFileToConfiguration( self, paths[0][1], [])
        dialog.exec_()
        if dialog.result() == QDialog.Accepted:
            new_line = ImpactLine( dialog.description, dialog.version, dialog.filename)
            new_line.crl = dialog.crl
            new_line.modify_config = True
            self._current_config.impacts.append( new_line)

            # FIXME should use a simpmle "datachagned" no ?
            self._model_impact.reset_objects( self._current_config.impacts )

        dialog.deleteLater()

    @Slot()
    def impact_activated(self,selected,deselected):
        if selected and selected.indexes() and len(selected.indexes()) > 0:
            impact = self._model_impact.object_at( selected.indexes()[0])

            if impact.configuration:
                self.set_config( impact.configuration)
            else:
                self.set_config( self._configs.configurations[-1])

    @Slot()
    def article_activated(self,selected,deselected):
        if selected and selected.indexes() and len(selected.indexes()) > 0:
            ac = self._model_articles.object_at( selected.indexes()[0])

            if ac.configurations:
                self._configs = ac
                self.set_config( self._configs.configurations[0])
                self._model_impact.reset_objects( self._configs.impacts)


    # @Slot(QModelIndex)
    # def impact_activated(self, ndx):
    #     if ndx.isValid():
    #         print(ndx)

    def __init__( self, parent):
        super(EditConfiguration,self).__init__(parent)

        self._articles = make_configs()
        self._configs = self._articles[0]

        self._title_widget = TitleWidget( "Configuration", self)

        self._title_widget.set_title("Configuration")
        config_file_proto = []
        config_file_proto.append( TextLinePrototype('description',_('Description'),editable=False))
        config_file_proto.append( IntegerNumberPrototype('version',_('Rev.'),editable=False))
        config_file_proto.append( EnumPrototype('type',_('Type'), TypeConfigDoc, editable=False))
        config_file_proto.append( TextLinePrototype('file',_('File'), editable=False))
        config_file_proto.append( DatePrototype('date_upload',_('Date'), editable=False))
        config_file_proto.append( EnumPrototype('crl',_('CRL'), CRL, editable=True))

        config_impact_proto = []
        config_impact_proto.append( IntegerNumberPrototype('version',_('Rev.'),editable=False))
        config_impact_proto.append( TextLinePrototype('description',_('Description'),editable=False))
        config_impact_proto.append( TextLinePrototype('owner',_('Owner'),editable=False))
        config_impact_proto.append( TextLinePrototype('file',_('File'), editable=False))
        config_impact_proto.append( EnumPrototype('approval',_('Approval'), ImpactApproval, editable=False))
        config_impact_proto.append( TextLinePrototype('approved_by',_('Approved by'), editable=False))
        config_impact_proto.append( DatePrototype('active_date',_('Since'), editable=False))

        config_article_proto = list()
        config_article_proto.append(TextLinePrototype('description',_('Plan number'),editable=False))
        config_article_proto.append(TextLinePrototype('file_revision',_('Rev.'), editable=False))
        config_article_proto.append(TextLinePrototype('file',_('File'), editable=False))



        # self.version_choice = QComboBox()
        # for c in self._configs.configurations:
        #     self.version_choice.addItem("Revision {}".format(c.version))
        # hlayout2.addWidget( self.version_choice)
        # self.version_choice.activated.connect( self.version_selected)


        top_layout = QVBoxLayout()
        top_layout.addWidget( self._title_widget)

        content_layout = QHBoxLayout()
        top_layout.addLayout( content_layout)

        self._view_articles = PrototypedTableView(None, config_article_proto)
        self._model_articles = ObjectModel( self, config_article_proto, lambda : None)
        self._view_articles.setModel( self._model_articles)
        self._view_articles.horizontalHeader().setResizeMode( QHeaderView.ResizeToContents)
        self._view_articles.horizontalHeader().setResizeMode( 0, QHeaderView.Stretch)
        self._view_articles.verticalHeader().hide()
        self._view_articles.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._view_articles.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._view_articles.selectionModel().selectionChanged.connect(self.article_activated)
        self._model_articles.reset_objects( self._articles)
        content_layout.addWidget(SubFrame("Articles", self._view_articles, self))

        config_layout = QVBoxLayout()

        content_layout.addLayout( config_layout)
        # top_layout.addLayout(hlayout2)

        self._view = PrototypedTableView(None, config_file_proto)

        # self.headers_view = QHeaderView( Qt.Orientation.Horizontal)
        # self.header_model = make_header_model( config_file_proto, self._model)
        # self.headers_view.setModel( self.header_model) # qt's doc : The view does *not* take ownership (but there's something with the selecion mode)



        self._model = ConfigModel( self, config_file_proto, lambda : None)
        self._view.setModel( self._model)
        self._view.verticalHeader().hide()
        self._view.horizontalHeader().setResizeMode( QHeaderView.ResizeToContents)
        self._view.horizontalHeader().setResizeMode( 0, QHeaderView.Stretch)


        self._version_config_label = QLabel("Version configuration")
        self._freeze_button = QPushButton("Accept && Freeze")

        hlayout2 = QHBoxLayout()
        hlayout2.addWidget( self._version_config_label)
        hlayout2.addStretch()
        hlayout2.addWidget( self._freeze_button)

        z = DragDropWidget(self, self._view)
        z.filesDropped.connect( self.configFilesDropped)

        vlayout_cfg = QVBoxLayout()
        vlayout_cfg.addLayout(hlayout2)
        vlayout_cfg.addWidget( z)

        self._subframe = SubFrame("Configuration", vlayout_cfg, self)
        config_layout.addWidget( self._subframe)

        self._model_impact = ImpactsModel( self, config_impact_proto, ImpactLine)

        self._view_impacts = PrototypedTableView(None, config_impact_proto)
        self._view_impacts.setModel( self._model_impact)
        self._view_impacts.verticalHeader().hide()
        self._view_impacts.horizontalHeader().setResizeMode( QHeaderView.ResizeToContents)
        self._view_impacts.horizontalHeader().setResizeMode( 1, QHeaderView.Stretch)
        self._view_impacts.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._view_impacts.setSelectionBehavior(QAbstractItemView.SelectRows)
        #self._view_impacts.activated.connect(self.impact_activated)
        self._view_impacts.selectionModel().selectionChanged.connect(self.impact_activated)

        z = DragDropWidget(self, self._view_impacts)
        z.filesDropped.connect( self.impactFilesDropped)
        subframe2 = SubFrame("Changes", z, self)
        config_layout.addWidget( subframe2)

        #self.version_choice.setCurrentIndex(len( self._configs.configurations) - 1)
        self.version_selected( len( self._configs.configurations) - 1)
        self.setLayout( top_layout)

        self._freeze_button.clicked.connect( self.freeze_configuration)

        self.set_article_configuration( self._configs)



if __name__ == "__main__":

    app = QApplication(sys.argv)

    mw = QMainWindow()
    mw.setMinimumSize(1024+256,512)
    widget = EditConfiguration(mw)
    mw.setCentralWidget(widget)
    mw.show()


    app.exec_()
