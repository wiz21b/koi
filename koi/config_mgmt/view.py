import enum
from datetime import date
import sys

from PySide.QtCore import Qt,Slot,QModelIndex,QAbstractTableModel,Signal, QPoint, QObject, QEvent
from PySide.QtCore import QTimer
from PySide.QtGui import QHBoxLayout,QVBoxLayout,QLineEdit,QLabel,QGridLayout, QColor, QDialog, QMessageBox,QHeaderView,QAbstractItemView, \
    QKeySequence, QStandardItem,QComboBox, QAction,QMenu,QWidget,QCursor, QSizePolicy, QPushButton, QComboBox, QColor, QBrush, QDialogButtonBox, QLineEdit, QAbstractItemView, QMouseEvent, QPalette

from PySide.QtGui import QTableWidget,QScrollArea, QResizeEvent, QFrame, QApplication

DEMO_MODE = 1

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

# from koi.db_mapping import Employee
# for t in session().query(Employee.employee_id).all():
#     print("{} {}".format( type(t), t.employee_id))

from koi.config_mgmt.mapping import *

from koi.gui.ObjectModel import ObjectModel
from koi.gui.ComboDelegate import PythonEnumComboDelegate
from koi.gui.ProxyModel import PrototypeController,IntegerNumberPrototype,FloatNumberPrototype, DurationPrototype,TrackingProxyModel,OperationDefinitionPrototype,PrototypedTableView,ProxyTableView,OrderPartDisplayPrototype,TextAreaPrototype, FutureDatePrototype,PrototypeArray,TextLinePrototype, Prototype, DatePrototype, BooleanPrototype
from koi.gui.dialog_utils import SubFrame, TitleWidget, showWarningBox

from koi.gui.PrototypedModelView import PrototypedModelView
from koi.config_mgmt.dragdrop_widget import DragDropWidget
from koi.gui.PersistentFilter import PersistentFilter
from koi.gui.horse_panel import HorsePanel

class EnumPrototype(Prototype):
    def __init__(self,field,title,enumeration : enum.Enum,editable=True,nullable=False):
        super(EnumPrototype,self).__init__(field,title,editable,nullable)
        self.set_delegate(
            PythonEnumComboDelegate( enumeration)) # items, sizes

def configuration_version_status( self : Configuration):
    if self.frozen:
        return "Rev. {}, frozen".format( self.version)
    else:
        return "Rev. {}".format( self.version)

setattr( Configuration, "version_status", property(configuration_version_status))

class ImpactLineExtended:
    """ adds a "selected" field to a regular impact using a Proxy"""

    def __init__( self, obj : ImpactLineDto):
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


class ConfigModel(ObjectModel):

    def __init__(self, parent, prototypes, blank_object_factory):
        super(ConfigModel, self).__init__( parent, prototypes, blank_object_factory)

    def background_color_eval(self,index):

        l = self.object_at( index)
        if l.modify_config:
            return QBrush(Qt.GlobalColor.yellow)
        elif l.document_type == TypeConfigDoc.IMPACT:
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

        config_impact_proto = list()
        config_impact_proto.append( BooleanPrototype('selected', "", editable=True))
        config_impact_proto.append( TextLinePrototype('description',_('Description'),editable=True))
        config_impact_proto.append( IntegerNumberPrototype('version',_('Cfg\nRev.'),editable=False))
        config_impact_proto.append( TextLinePrototype('document',_('File'), editable=False))
        config_impact_proto.append( EnumPrototype('approval',_('Approval'), ImpactApproval, editable=False))
        config_impact_proto.append( DatePrototype('date_upload',_('Date'), editable=False))

        top_layout = QVBoxLayout()

        top_layout.addWidget( QLabel("Please select the impact(s) document(s) that " +
                                     "correspond to the new frozen configuration."))

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

    def __init__(self, parent, config : ConfigurationDto, impacts):
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

        self.crl = None
        self.filename = filename
        self.description = ""
        self.type_ = TypeConfigDoc.PROGRAM
        self.version = 1

        title = _("Add a file to a configuration")
        self.setWindowTitle(title)

        top_layout = QVBoxLayout()
        self.setLayout(top_layout)

        top_layout.addWidget( QLabel("Filename : <b>{}</b>".format( filename)))

        self.type_choice = QComboBox()
        for s in TypeConfigDoc:
            self.type_choice.addItem( s.value, s)

        top_layout.addWidget( QLabel("Type :"))
        top_layout.addWidget( self.type_choice)

        self._description_widget = QLineEdit()
        top_layout.addWidget( QLabel("Description :"))
        top_layout.addWidget(self._description_widget)

        version_choice = QComboBox()
        version_choice.addItem(None)
        for l in previous_lines:
            version_choice.addItem( l.file)

        top_layout.addWidget( QLabel("Updates"))
        top_layout.addWidget( version_choice)
        top_layout.addStretch()

        self.crl_choice = QComboBox()
        for s in CRL:
            self.crl_choice.addItem( s.value, s)

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
        self.description = self._description_widget.text()
        self.crl = self.crl_choice.itemData( self.crl_choice.currentIndex())
        self.type_ = self.type_choice.itemData( self.type_choice.currentIndex())
        return super(AddFileToConfiguration,self).accept()

    @Slot()
    def reject(self):
        return super(AddFileToConfiguration,self).reject()






class EditConfiguration(HorsePanel):

    # def version_selected( self, ndx):
    #     self.set_config( self._current_article.configurations[ndx] )

    def set_configuration_articles( self, cfg_articles : list):
        self._articles = cfg_articles
        self._model_articles.reset_objects( self._articles)
        self._wl.set_objects( self._articles)
        self.set_article_configuration( self._articles[0])

    def set_article_configuration( self, ca):
        self._current_article = ca
        self._model_impact.reset_objects( ca.impacts )

        self._version_combo_model.setObjects( ca.configurations)

        # By default, we display the last frozen config.

        config_set = False
        for c in reversed( ca.configurations):
            if c.frozen:
                self.set_config(c)
                config_set = True
                break

        if not config_set:
            self.set_config(ca.configurations[len( ca.configurations) - 1])


    def set_config( self, config : Configuration):

        self._current_config = config

        msg = "Configuration for part <b>{}</b>, client : <b>{}</b>".format( config.article_configuration.full_version, config.article_configuration.customer_id)

        if config.frozen:
            freeze_msg = "<b><font color = 'green'>FROZEN on {} by {}</font></b>".format( config.frozen, config.freezer)
            self._freeze_button.setText("Unfreeze")
        else:
            freeze_msg = "<b><font color = 'red'>NOT frozen</font></b>"
            self._freeze_button.setText("Freeze")


        self._subframe.set_title( msg)

        self._version_config_label.setText( "Revision {}, {}".format(config.version, freeze_msg))

        self._model.reset_objects( config.lines )

        self._versions_combo.setCurrentIndex(
            self._version_combo_model.objectIndex( config).row())


        if DEMO_MODE == 0:
            part_revs = [PartRev( config, part) for part in config.parts]
            self._parts_widget.set_objects( part_revs)
        else:
            if config.parts:
                self._parts_widget.setText( _("Used in : ") + ", ".join(
                    [ "<a href='{}'>{}</a>".format( part.order_part_id, part.human_identifier) for part in config.parts] ))
            else:
                self._parts_widget.setText( _("Not used"))



    @Slot()
    def add_configuration(self):

        for c in reversed( self._current_article.configurations):
            if not c.frozen:
                showWarningBox(_("There's already a not frozen revision. Edit that one first."))
                return

        c = Configuration()
        session().add( c)

        c.version = max( [c.version for c in self._current_article.configurations]) + 1
        self._current_article.configurations.append(c)
        self.set_config( c)


    @Slot()
    def freeze_configuration(self):

        impacts = filter( lambda imp: imp.approval == ImpactApproval.UNDER_CONSTRUCTION, self._current_article.impacts)

        dialog = FreezeConfiguration( self, self._current_config, impacts)
        dialog.exec_()
        if dialog.result() == QDialog.Accepted:

            self._current_config.frozen = date.today()
            self._current_config.freezer = "Daniel Dumont"

            c = ConfigurationDto()
            c.frozen = None
            c.version = max([c.version for c in self._current_article.configurations]) + 1
            self._current_article.configurations.append( c)

            # for c in range( self.version_choice.count()):
            #     self.version_choice.removeItem(0)

            # for c in self._current_article:
            #     self.version_choice.addItem("Revision {}".format(c.version))

            # self.version_choice.setCurrentIndex( len(self._current_article) - 2)
            #self.version_selected( len(self._current_article) - 2)

        dialog.deleteLater()

    @Slot()
    def configFilesDropped( self,paths):

        if self._current_config.frozen:
            showWarningBox( _("Trying to modify a frozen configuration"),
                            _("It is not allowed to modify a frozen configuration."))
            return

        dialog = AddFileToConfiguration( self, paths[0][1], [])
        dialog.exec_()
        if dialog.result() == QDialog.Accepted:
            new_line = ConfigurationLine()
            session().add( new_line)
            new_line.description = dialog.description
            new_line.version = dialog.version
            new_line.document_type = dialog.type_
            new_line.document = _make_quick_doc(dialog.filename)
            new_line.crl = dialog.crl
            new_line.modify_config = True
            self._current_config.lines.append( new_line)
            session().commit()

            # FIXME should use a simpmle "datachagned" no ?
            self._model.reset_objects( self._current_config.lines )

        dialog.deleteLater()

    @Slot()
    def impactFilesDropped( self,paths):
        dialog = AddFileToConfiguration( self, paths[0][1], [])
        dialog.exec_()
        if dialog.result() == QDialog.Accepted:
            new_line = ImpactLineDto( dialog.description, dialog.version, dialog.filename)
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

            # print("cfg : {}".format(impact.configuration))
            # print(impact.description)
            # print(impact.document)

            if impact.configuration:
                self.set_config( impact.configuration)
            else:
                self.set_config( self._current_article.configurations[-1])

    @Slot()
    def article_selected(self,selected,deselected):
        if selected and selected.indexes() and len(selected.indexes()) > 0:
            ac = self._model_articles.object_at( selected.indexes()[0])

            if ac.configurations:
                self._current_article = ac
                self.set_config( self._current_article.configurations[0])
                self._model_impact.reset_objects( self._current_article.impacts)

    @Slot(int)
    def article_activated( self, ndx : int):
        ac = self._model_articles.object_at( ndx)
        self.set_article_configuration( ac)

    @Slot(int)
    def _version_selected_slot(self, ndx : int):
        self.set_config( self._version_combo_model.objectAt(ndx))

    @Slot(str)
    def apply_filter( self, f : str):
        self.set_configuration_articles( self._articles)
        self.set_article_configuration( self._articles[0])

        for c in self._articles[0].configurations:
            for op in c.parts:
                if op.human_identifier == f:
                    self.set_config( c)
                    return

    @Slot(str)
    def partLinkClicked( self, link : str):
        order_part_id = int(link)
        print(order_part_id)

    def __init__( self, parent):
        super(EditConfiguration,self).__init__(parent)

        self._articles = []
        self._current_article = None

        config_article_proto = list()
        config_article_proto.append(TextLinePrototype('customer_id',_('Customer'),editable=False))
        config_article_proto.append(TextLinePrototype('identification_number',_('Part number'),editable=False))
        config_article_proto.append(TextLinePrototype('revision',_('Part.\nRev.'), editable=False))
        config_article_proto.append(TextLinePrototype('current_configuration_version',_('Cfg\nRev'), editable=False))
        config_article_proto.append(DatePrototype('valid_since',_('Valid since'), editable=False))
        config_article_proto.append(TextLinePrototype('current_configuration_status',_('Status'), editable=False))

        config_file_proto = []
        config_file_proto.append( EnumPrototype('document_type',_('Type'), TypeConfigDoc, editable=False))
        config_file_proto.append( TextLinePrototype('description',_('Description'),editable=False))
        config_file_proto.append( IntegerNumberPrototype('version',_('Rev.'),editable=False))
        config_file_proto.append( TextLinePrototype('document',_('File'), editable=False))
        config_file_proto.append( DatePrototype('date_upload',_('Date'), editable=False))
        config_file_proto.append( EnumPrototype('crl',_('CRL'), CRL, editable=True))

        config_impact_proto = []
        config_impact_proto.append( IntegerNumberPrototype('version',_('Cfg.\nRev.'),editable=False))
        config_impact_proto.append( TextLinePrototype('description',_('Description de la modification'),editable=False))
        config_impact_proto.append( TextLinePrototype('owner_short',_('Owner'),editable=False))
        config_impact_proto.append( TextLinePrototype('document',_('File'), editable=False))
        config_impact_proto.append( EnumPrototype('approval',_('Approval'), ImpactApproval, editable=False))
        config_impact_proto.append( TextLinePrototype('approver_short',_('By'), editable=False))
        config_impact_proto.append( DatePrototype('active_date',_('Since'), editable=False))



        self._title_widget = TitleWidget( "Configurations", self)
        self._title_widget.set_title("Configuration")




        top_layout = QVBoxLayout()
        top_layout.addWidget( self._title_widget)

        self.persistent_filter = PersistentFilter( filter_family="articles_configs")

        self.persistent_filter.apply_filter.connect( self.apply_filter)

        top_layout.addWidget(self.persistent_filter)

        content_layout = QHBoxLayout()
        top_layout.addLayout( content_layout)

        self._model_articles = ObjectModel( self, config_article_proto, lambda : None)
        self._view_articles = PrototypedTableView(None, config_article_proto)
        self._view_articles.setModel( self._model_articles)
        self._view_articles.horizontalHeader().setResizeMode( QHeaderView.ResizeToContents)
        self._view_articles.horizontalHeader().setResizeMode( 1, QHeaderView.Stretch)
        self._view_articles.verticalHeader().hide()
        self._view_articles.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._view_articles.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._view_articles.selectionModel().selectionChanged.connect(self.article_selected)

        left_layout = QVBoxLayout()

        wl = SelectableWidgetsList(self)
        wl.item_selected.connect( self.article_activated)
        self._wl = wl
        scroll_area = Scroll()
        self._gefilter = GEFilter()
        self._gefilter.widget_list = wl
        self._gefilter.scroll_area = scroll_area
        scroll_area.installEventFilter( self._gefilter)

        addw = QWidget(self)
        addw.setLayout( QVBoxLayout())
        addw.layout().setContentsMargins(0,0,0,0)
        addw.layout().addWidget( wl)
        addw.layout().addStretch() # that's the importnat bit
        scroll_area.setWidget(addw) # wl


        if DEMO_MODE == 0:
            left_layout.addWidget(SubFrame(_("Parts"), scroll_area, self))
        else:
            left_layout.addWidget(SubFrame( _("Parts"), self._view_articles, self))

        content_layout.addLayout( left_layout)


        config_layout = QVBoxLayout()


        content_layout.addLayout( config_layout)
        content_layout.setStretch(0,4)
        content_layout.setStretch(1,6)
        # top_layout.addLayout(hlayout2)

        self._view = PrototypedTableView(None, config_file_proto)

        # self.headers_view = QHeaderView( Qt.Orientation.Horizontal)
        # self.header_model = make_header_model( config_file_proto, self._model)
        # self.headers_view.setModel( self.header_model) # qt's doc : The view does *not* take ownership (but there's something with the selecion mode)



        self._model = ConfigModel( self, config_file_proto, lambda : None)
        self._view.setModel( self._model)
        self._view.verticalHeader().hide()
        self._view.horizontalHeader().setResizeMode( QHeaderView.ResizeToContents)
        self._view.horizontalHeader().setResizeMode( 1, QHeaderView.Stretch)


        self._version_config_label = QLabel("Version configuration")
        self._version_combo_model = ObjectComboModel( parent, "version_status")
        self._versions_combo = QComboBox()
        self._versions_combo.activated.connect( self._version_selected_slot)
        self._versions_combo.setModel( self._version_combo_model)
        self._freeze_button = QPushButton("Accept && Freeze")
        self._add_config_button = QPushButton("New revision")

        hlayout2 = QHBoxLayout()
        hlayout2.addWidget( self._version_config_label)
        hlayout2.addStretch()
        hlayout2.addWidget( self._versions_combo)
        hlayout2.addWidget( self._freeze_button)
        hlayout2.addWidget( self._add_config_button)


        z = DragDropWidget(self, self._view)
        z.filesDropped.connect( self.configFilesDropped)

        vlayout_cfg = QVBoxLayout()
        vlayout_cfg.addLayout(hlayout2)
        vlayout_cfg.addWidget( z)

        if DEMO_MODE == 0:
            self._parts_widget = OrderPartsWidgetList2( self)
        else:
            self._parts_widget = QLabel("Used in")
            self._parts_widget.setTextInteractionFlags(Qt.TextBrowserInteraction)
            self._parts_widget.linkActivated.connect( self.partLinkClicked)

        vlayout_cfg.addWidget( self._parts_widget)

        #self._parts_widget.setVisible( DEMO_MODE == 1)

        self._subframe = SubFrame("Configuration", vlayout_cfg, self)
        config_layout.addWidget( self._subframe)

        self._model_impact = ImpactsModel( self, config_impact_proto, ImpactLineDto)

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

        self.setLayout( top_layout)

        self._freeze_button.clicked.connect( self.freeze_configuration)
        self._add_config_button.clicked.connect( self.add_configuration)



class Scroll(QScrollArea):
    def __init__( self, parent = None):
        super( Scroll, self).__init__( parent)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.viewport().setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        self.setWidgetResizable(True)

    # This is the main reason why we need a specialized QScrollArea object
    # With this, the list's widgets always fit the scroll area perfectly
    # (on the horizontal direction)
    def resizeEvent( self, event : QResizeEvent):
        self.widget().setFixedWidth( self.width() - 2)



class WidgetsList( QWidget):
    def _show_n_widgets( self, n):

        current_n = len( self._widgets)
        # All this stuff to avoid to delete QWidgets
        if n > current_n:
            for i in range(n - current_n):
                w = self._make_line_widget()
                self._widgets.append(w)
                self.layout().addWidget(w)

        if n < current_n:
            for i in range( n, current_n):
                self._widgets[i].hide()
                self._widgets[i].setEnabled(False)

        for i in range( n):
            self._widgets[i].show()
            self._widgets[i].setEnabled(True)

    def _make_line_widget( self):
        return QLabel( self)

    def object_at(self, ndx : int):
        return self._widgets[ndx]

    def set_objects( self, obj : []):
        self._show_n_widgets( len(obj))

        for i in range( len(obj)):
            self._widgets[i].set_object( obj[i])

    def __init__(self, parent : QWidget):
        super(WidgetsList, self).__init__( parent)
        self._widgets = []
        layout = QVBoxLayout()
        self.setLayout( layout)
        self.layout().setContentsMargins(5,5,5,5)

class OrderPartDetail( QLabel):
    def __init__(self, parent : QWidget):
        super(OrderPartDetail, self).__init__( parent)

    def set_object( self, p):
        # p is an order part like object
        self.setText("Rev. <b>{}</b> in <b>{}</b> : {}".format( p.config_level, p.human_identifier, p.description) )

class OrderPartsWidgetList( WidgetsList):
    def __init__(self, parent : QWidget):
        super(OrderPartsWidgetList, self).__init__( parent)

    def _make_line_widget( self):
        return OrderPartDetail( self)


class OrderPartDetail2( QLabel):
    def __init__(self, parent : QWidget):
        super(OrderPartDetail2, self).__init__( parent)

    def set_object( self, p):
        # p is an order part like object
        self.setText("Used in <b>{}</b> : {}".format( p.human_identifier, p.description) )

class OrderPartsWidgetList2( WidgetsList):
    def __init__(self, parent : QWidget):
        super(OrderPartsWidgetList2, self).__init__( parent)

    def _make_line_widget( self):
        return OrderPartDetail2( self)


class PartRev:
    def __init__(self, configuration, part):
        self._configuration = configuration
        self._part = part

    @property
    def human_identifier(self):
        return self._part.human_identifier

    @property
    def description(self):
        return self._part.description

    @property
    def config_level(self):
        return self._configuration.version


class ACWidget(QFrame):

    def set_object( self, obj):
        for p in self._prototype:
            p.set_display_widget_data( getattr( obj, p.field))

        part_revs = []
        for config in obj.configurations:
            for part in config.parts:
                part_revs.append( PartRev( config, part))

        self._parts_widget.set_objects( part_revs)

        if not part_revs:
            self._parts_layout.itemAt(0).widget().setVisible(False)
            self._separator.setVisible(False)

    def _verti_widget(self, field : str):
        layout = QVBoxLayout()
        layout.addWidget( QLabel(self._prototype[field].title))
        w = self._prototype[field].display_widget()
        w.setStyleSheet("font-weight: bold")
        w.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.MinimumExpanding)
        layout.addWidget( w)

        return layout

    def __init__(self, parent : QWidget):
        super(ACWidget, self).__init__( parent)
        self.setFrameStyle( QFrame.Box)

        self._parts_widget = OrderPartsWidgetList( self)

        self._prototype = PrototypeArray(
            [ TextLinePrototype('customer_id',_('Customer'),editable=False),
              TextLinePrototype('identification_number',_('Part number'),editable=False),
              TextLinePrototype('revision',_('Rev.'), editable=False),
              TextLinePrototype('current_configuration_version',_("Cfg\nrev."), editable=False),
              DatePrototype('valid_since',_('Valid since'), editable=False),
              TextLinePrototype('current_configuration_status',_('Status'), editable=False) ])

        vlayout = QVBoxLayout()


        layout = QHBoxLayout()

        fm = QLabel().fontMetrics()

        max_widths = { 'customer_id' : '9999', 'identification_number' : '', 'revision' : 'MM','current_configuration_version' : '00', 'valid_since' : '29/12/99', 'current_configuration_status' :"NOT FROZEN"}
        for n in ['customer_id', 'identification_number', 'revision','current_configuration_version', 'valid_since', 'current_configuration_status']:
            w = self._verti_widget(n)

            if max_widths[n]:
                mw = max( fm.width( max_widths[n]), fm.width( self._prototype[n].title))
                w.itemAt(0).widget().setFixedWidth( mw)
                #w.itemAt(1).widget().setFixedWidth( mw)

            layout.addLayout( w)

        layout.insertStretch(2) # right after identification number, which is the lengthiest

        vlayout.addLayout( layout)

        frame = QFrame()
        self._separator = frame
        frame.setFrameStyle( QFrame.Box)
        frame.setFixedHeight(1)
        vlayout.addWidget( frame)

        leftlayout = QVBoxLayout()
        leftlayout.setAlignment( Qt.AlignTop)
        leftlayout.addWidget(QLabel("→")) # adding horizontal line doesn't work, long arrow don't work neither.
        leftlayout.addStretch()

        rightlayout = QVBoxLayout()
        rightlayout.addWidget(self._parts_widget)
        self._parts_layout = rightlayout

        layout = QHBoxLayout()
        layout.addLayout( leftlayout)
        layout.addLayout( rightlayout)
        layout.addStretch()

        self._parts_layout = leftlayout

        vlayout.addLayout( layout)
        self.setLayout( vlayout)

        self.setAutoFillBackground( True)
        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Maximum)
        #self.layout().setSizeConstraint( )

class GEFilter(QObject):
    def __init__(self):
        super(GEFilter, self).__init__()
        self.widget_list = None
        self.scroll_area = None

    def eventFilter(self, target: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.MouseButtonDblClick:
            self.widget_list.emit_selected()
            return False

        elif event.type() == QEvent.MouseButtonPress:
            # and target in self.widget_list._widgets
            w = QApplication.widgetAt( event.globalPos())

            # w is the lowest QWidget in the widget hierarchy
            # I have to climb up to find "my" widget. Note I don't
            # have to go any more up than the widgets list itself.
            # FIXME just go up to widget_list and then one down...

            found = False
            while (w is not None) and (w != self.widget_list):
                if w in self.widget_list._widgets:
                    found = True
                    break
                else:
                    w = w.parent()

            if found:
                self.widget_list.select( w)

            return False

        elif event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Down:
                self.widget_list.select_next()
            elif event.key() == Qt.Key_Up:
                self.widget_list.select_previous()
            self.scroll_area.ensureWidgetVisible( self.widget_list._current_selection)

            return True
        else:
            return False




class SelectableWidgetsList(WidgetsList):

    item_selected = Signal(int)

    def _set_widget_background( self, target, fg_color, bg_color):
        p = target.palette()
        p.setColor(target.foregroundRole(), fg_color)
        p.setColor(target.backgroundRole(), bg_color)
        target.setPalette(p)

    def emit_selected(self):
        ndx = self._widgets.index(self._current_selection)
        self.item_selected.emit( ndx)


    @Slot(QWidget)
    def select( self, target):
        if target != self._current_selection:

            fg = QApplication.palette().color( QPalette.ColorGroup.Active, QPalette.ColorRole.HighlightedText)
            bg = QApplication.palette().color( QPalette.ColorGroup.Active, QPalette.ColorRole.Highlight)
            self._set_widget_background( target, fg, bg)

            if self._current_selection:
                fg = QApplication.palette().color( QPalette.ColorGroup.Active, QPalette.ColorRole.Text)
                bg = QApplication.palette().color( QPalette.ColorGroup.Active, QPalette.ColorRole.Base)
                self._set_widget_background( self._current_selection, fg, bg)

            self._current_selection = target
            self.emit_selected()

    def select_next(self):
        if self._current_selection:
            ndx = min( len(self._widgets) - 1, self._widgets.index(self._current_selection) + 1 )
        else:
            ndx = 0

        if self._widgets:
            self.select( self._widgets[ ndx] )

    def select_previous(self):
        if self._current_selection:
            ndx = max( 0, self._widgets.index(self._current_selection) - 1 )
        else:
            ndx = 0

        if self._widgets:
            self.select( self._widgets[ ndx] )

    def _make_line_widget( self):
        # w.setDisabled(True) # No more events, but widget grayed out :-(
        # w.setAttribute(Qt.WA_TransparentForMouseEvents)

        w = ACWidget( self)
        p = w.palette()
        p.setColor(w.backgroundRole(), Qt.white)
        w.setPalette(p)

        return w

    def __init__(self, parent : QWidget):
        super(SelectableWidgetsList, self).__init__( parent)

        self.layout().setContentsMargins(0,0,0,0)
        self._current_selection = None
        #self.layout().addStretch() # Helps the scroll area to resize the list properly (ie only resize horizontally)


def _make_quick_doc( name : str):
    document = Document()
    session().add(document)
    document.filename = name
    document.server_location = "dummy"
    document.file_size = 9999
    document.upload_date = date.today()

    return document

def _make_config_line( description, version, type_, file_):
    line = ConfigurationLine()
    session().add(line)
    line.description = description
    line.version = version
    line.document_type = type_

    d = Document()
    session().add(d)

    line.document = d
    line.document.filename = file_
    line.document.server_location = "dummy"
    line.document.file_size = 9999
    line.document.upload_date = date.today()

    return line

def make_configs( session):

    ac = ArticleConfiguration()
    session().add(ac)

    ac.customer = session().query(Customer).filter( Customer.customer_id == 18429).one()
    ac.identification_number = "4500250418"
    ac.revision = "C"


    c = Configuration()
    session().add(c)

    op = session().query(OrderPart).filter( OrderPart.order_part_id == 151547).one()
    op2 = session().query(OrderPart).filter( OrderPart.order_part_id == 246051).one()
    op3 = session().query(OrderPart).filter( OrderPart.order_part_id == 230512).one()

    c.parts = [op,op3]
    c.version = 1
    c.article_configuration = ac
    c.frozen = date(2018,1,31)
    c.freezer = session().query(Employee).filter(Employee.employee_id == 100).one()
    c.lines = [ _make_config_line( "Plan ZZ1D", 2, TypeConfigDoc.PLAN_3D, "plan3EDER4.3ds"),
                _make_config_line( "Config TN", 2, TypeConfigDoc.PROGRAM, "tige.gcode"),
                _make_config_line( "Config TN", 1, TypeConfigDoc.PROGRAM, "anti-tige.gcode") ]
    #ac.configurations.append( c)

    c = Configuration()
    session().add(c)

    c.parts = [op2]
    c.article_configuration = ac
    c.lines = [ _make_config_line( "Plan coupe 90°", 1, TypeConfigDoc.PLAN_2D, "90cut-RXC.doc"),
                _make_config_line( "Plan ZZ1D", 2, TypeConfigDoc.PLAN_3D, "plan3EDER4.3ds"),
                _make_config_line( "Config TN", 2, TypeConfigDoc.PROGRAM, "tige.gcode"),
                _make_config_line( "Config TN", 1, TypeConfigDoc.PROGRAM, "anti-tige.gcode") ]
    c.version = 2
    c.frozen = date(2018,2,5)
    c.freezer = session().query(Employee).filter(Employee.employee_id == 118).one()
    c.lines[2].modify_config = False
    #ac.configurations.append( c)

    c = Configuration()
    session().add(c)

    c.article_configuration = ac
    c.lines = [ _make_config_line( "Operations", 1, TypeConfigDoc.PLAN_3D, "impact_1808RXC.doc"),
                _make_config_line( "Plan ZZ1D", 2, TypeConfigDoc.PLAN_3D, "plan3EDER4.3ds"),
                _make_config_line( "Config TN", 2, TypeConfigDoc.PROGRAM, "tige.gcode"),
                _make_config_line( "Config TN", 1, TypeConfigDoc.PROGRAM, "anti-tige.gcode") ]
    c.version = 3
    c.frozen = None
    c.lines[2].modify_config = True
    #ac.configurations.append( c)


    impact = ImpactLine()
    i1 = impact

    impact.owner = session().query(Employee).filter( Employee.employee_id == 118).one()
    impact.description = "one preproduction measurement side XPZ changed"
    impact.date_upload = date.today()
    impact.approval = ImpactApproval.APPROVED
    impact.approved_by = session().query(Employee).filter( Employee.employee_id == 112).one()
    impact.active_date = date(2013,1,11)
    impact.document = _make_quick_doc("bliblo.doc")
    ac.configurations[0].origin = impact
    session().add(impact)
    session().flush()
    ac.impacts.append( impact)

    ac.configurations[0].origin_id = impact.impact_line_id
    assert i1.configuration is not None
    session().flush()
    assert i1.configuration is not None

    #print( ac.configurations)

    impact = ImpactLine()
    impact.owner = session().query(Employee).filter( Employee.employee_id == 112).one()
    assert i1.configuration is not None, i1.configuration
    impact.description = "two Aluminium weight reduction"
    impact.date_upload = date.today()
    impact.approval = ImpactApproval.APPROVED
    impact.approved_by = session().query(Employee).filter( Employee.employee_id == 8).one()
    impact.active_date = None
    ac.configurations[1].origin = impact
    impact.document = _make_quick_doc("impactmr_genry.doc")
    session().add(impact)
    ac.impacts.append( impact)

    impact = ImpactLine()
    impact.owner = session().query(Employee).filter( Employee.employee_id == 8).one()
    impact.description = "three Production settings"
    impact.date_upload = date.today()
    impact.approval = ImpactApproval.UNDER_CONSTRUCTION
    impact.approved_by = None
    impact.active_date = None
    impact.configuration = None
    impact.document = _make_quick_doc("impact_v3.doc")
    session().add(impact)
    ac.impacts.append( impact)

    impact = ImpactLine()
    impact.owner = session().query(Employee).filter( Employee.employee_id == 20).one()
    impact.description = "four Production settings v2"
    impact.date_upload = date.today()
    impact.approval = ImpactApproval.UNDER_CONSTRUCTION
    impact.approved_by = None
    impact.active_date = None
    impact.configuration = None
    impact.document = _make_quick_doc("impact_v3bis.doc")
    session().add(impact)
    ac.impacts.append( impact)


    ac2 = ArticleConfiguration()
    session().add(ac2)
    ac2.customer = session().query(Customer).filter( Customer.customer_id == 2145).one()
    ac2.identification_number = "ZERDF354-ZXZ-2001"
    ac2.revision = "D"

    c = Configuration()
    session().add(c)
    # op = session().query(OrderPart).filter( OrderPart.order_part_id == 95642).one()
    # op2 = session().query(OrderPart).filter( OrderPart.order_part_id == 128457).one()
    # op3 = session().query(OrderPart).filter( OrderPart.order_part_id == 96799).one()
    # c.parts = [op, op2, op3]
    c.article_configuration = ac2
    #ac2.configurations.append( c)

    session().commit()

    assert i1.configuration is not None

    return [ac]


def test_extended_dto():
    il = ImpactLine()
    il.description = 'test'
    ilo = ImpactLineExtended(il)
    assert ilo.description == "test"
    assert ilo.selected == False

    ilo.description = "new"
    ilo.selected = True
    assert ilo.description == "new"
    assert ilo.selected == True, "{} ?".format(ilo.selected)

    assert il.description == "new"



class ObjectComboModel(QAbstractTableModel):
    def __init__(self,parent,field_name):
        super(ObjectComboModel,self).__init__(parent)
        self._objects = []
        self._field_name = field_name

    def clear(self):
        self.beginRemoveRows(QModelIndex(),0,self.rowCount()-1)
        self.beginRemoveColumns(QModelIndex(),0,self.columnCount()-1)
        self._objects = []
        self.endRemoveColumns()
        self.endRemoveRows()

    def parent(self):
        return QModelIndex()

    def index(self, row, column, parent = QModelIndex()):
        return self.createIndex(row, column)

    def rowCount(self,parent = None):
        return len(self._objects)

    def columnCount(self,parent = None):
        if self.rowCount() == 0:
            return 0
        else:
            return 1

    def data(self, index, role):
        if index.row() < 0 or index.row() >= self.rowCount():
            # print "TurboModel.data(). bad index {}".format(index.row())
            return None

        if role in (Qt.EditRole, Qt.DisplayRole):
            return getattr( self._objects[index.row()], self._field_name)
        elif role == Qt.UserRole:
            return self._objects[index.row()]
        else:
            return None

    def flags(self, index):
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled


    def objectAt( self, ndx : int):
        return self._objects[ndx]

    def objectIndex(self, obj):
        return self.index( self._objects.index( obj), 0)

    def setObjects(self,objects):

        if self.rowCount() > 0:
            self.clear()

        if objects is not None:
            self.beginInsertRows(QModelIndex(),0,len(objects)-1)
            self.beginInsertColumns(QModelIndex(),0,0)

            self._objects = objects

            self.endInsertColumns()
            self.endInsertRows()


if __name__ == "__main__":

    app = QApplication(sys.argv)

    mw = QMainWindow()
    mw.setMinimumSize(1024+768,512+256)
    widget = EditConfiguration(mw)
    mw.setCentralWidget(widget)
    mw.show()

    widget.set_configuration_articles( make_configs( session))
    widget.persistent_filter.super_filter_entry.setText("5544A")
    widget.persistent_filter._emit_apply_filter()




    app.exec_()
