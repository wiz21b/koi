import enum
from datetime import date
import sys

from PySide.QtCore import Qt,Slot,QModelIndex,QAbstractTableModel,Signal, QPoint, QObject, QEvent
from PySide.QtCore import QTimer
from PySide.QtGui import QHBoxLayout,QVBoxLayout,QLineEdit,QLabel,QGridLayout, QColor, QDialog, QMessageBox,QHeaderView,QAbstractItemView, \
    QKeySequence, QStandardItem,QComboBox, QAction,QMenu,QWidget,QCursor, QSizePolicy, QPushButton, QComboBox, QColor, QBrush, QDialogButtonBox, QLineEdit, QAbstractItemView, QMouseEvent, QPalette, QFormLayout

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
from koi.session.UserSession import user_session



class EnumPrototype(Prototype):
    def __init__(self,field,title,enumeration : enum.Enum,editable=True,nullable=False):
        super(EnumPrototype,self).__init__(field,title,editable,nullable)
        self.set_delegate(
            PythonEnumComboDelegate( enumeration)) # items, sizes


class InstrumentedObject:
    def __init__(self):
        self.clear_changes()

    def has_changed(self):
        return len(self._changed) > 0

    def clear_changes(self):
        object.__setattr__(self, "_changed", set())

    def __setattr__(self, name, value):
        if name != '_changed':

            if getattr(self, name) != value:
                # Checking if value is actually different is really important
                # for some behaviours. In particular the
                # 'position' tracking. But it's not 100% correct.
                # Indeed if attribute X with initial value 9 becomes 1 then 3 then 9
                # then we should note it didn't change...

                self._changed.add(name)

            object.__setattr__(self, name, value)
        else:
            raise Exception("Forbidden access to _change ! This field is reserved for change tracking")



# def configuration_version_status( self : Configuration):
#     if self.frozen:
#         return "Rev. {}, frozen".format( self.version)
#     else:
#         return "Rev. {}".format( self.version)

# setattr( Configuration, "version_status", property(configuration_version_status))

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


class EditArticleConfiguration(QDialog):
    def _make_ui(self):
        title = _("Add article in configuration")
        self.setWindowTitle(title)
        config_impact_proto = list()
        config_impact_proto.append( TextLinePrototype('customer', _("Customer"), editable=True))
        config_impact_proto.append( TextLinePrototype('identification_number', _("Identification"), editable=True))

        form_layout = QFormLayout()
        for p in self.form_prototype:
            w = p.edit_widget(self)
            w.setEnabled(p.is_editable)
            w.setObjectName("form_" + p.field)
            form_layout.addRow( p.title, w)

        top_layout = QVBoxLayout()
        self.title_widget = TitleWidget(title,self)
        top_layout.addWidget(self.title_widget)
        top_layout.addLayout( form_layout)

    def __init__(self, parent, config : Configuration, impacts):
        super( EditArticleConfiguration, self).__init__(parent)

        self._make_ui()

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
        print("set_configuration_articles : {}".format(cfg_articles))
        print("set_configuration_articles : {}".format(type(cfg_articles)))
        self._articles = cfg_articles
        self._model_articles.reset_objects( self._articles)
        self._wl.set_objects( self._articles)
        self.set_article_configuration( self._articles[0])

    def set_article_configuration( self, ca : ArticleConfiguration):

        wrapped = self._change_tracker.wrap_in_change_detector(ca)

        if wrapped == self._current_article:
            return

        self._current_article = wrapped
        #print("--- version combo setModel : {}".format( type( self._current_article.configurations)))
        self._version_combo_model.setObjects( self._current_article.configurations)
        #print("-o- "*10)
        self._model_impact.reset_objects( self._current_article.impacts )


        # By default, we display the last frozen config.

        config_set = False
        for c in reversed( self._current_article.configurations):
            if c.frozen:
                self.set_config(c)
                config_set = True
                break

        if not config_set:
            if len( self._current_article.configurations) > 0:
                self.set_config(ca.configurations[len( self._current_article.configurations) - 1])
            else:
                self.set_config( None)


    def set_config( self, config : Configuration):

        self._current_config = config

        if config == None:
            self._model.reset_objects( None )
            return


        ac = config.article_configuration
        full_version = "{}/{}".format( ac.identification_number, ac.revision_number)
        msg = "Configuration for part <b>{}</b>, client : <b>{}</b>".format( full_version, ac.customer_id)

        if config.frozen:
            freeze_msg = "<b><font color = 'green'>FROZEN on {} by {}</font></b>".format( config.frozen, config.freezer.fullname)
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


    def _create_configuration( self, impact_documents):
        assert impact_documents, "Configuration *must* be wired to impact document"

        c = CopyConfiguration()

        existing_versions = [c.version for c in self._current_article.configurations]
        if existing_versions:
            c.version = max( existing_versions) + 1
        else:
            c.version = 1

        c.article_configuration = self._current_article
        self._current_article.configurations.append(c)

        for impact in impact_documents:
            #impact.configuration_id = c.configuration_id
            impact.configuration = c

        return c

    @Slot()
    def add_configuration(self):

        for c in reversed( self._current_article.configurations):
            if not c.frozen:
                showWarningBox(_("There's already a not frozen revision. Edit that one first."))
                return

        selected_indices = self._view_impacts.selectedIndexes()
        if selected_indices and len(selected_indices) >= 1:
            impact_documents = [self._model_impact.object_at(ndx.row()) for ndx in selected_indices]
        else:
            # no selected impact !
            showWarningBox( _("No impact selected document, so no active configuration"),
                            _("Please select an impact document to show which configuration to add a document to."))
            return


        c = self._create_configuration( impact_documents)
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
        if self._model_impact.rowCount() == 0:
            showWarningBox( _("Trying to create a configuration without impact document"),
                            _('It is not allowed to add files to a configuration while there are no impact file that "frame" it. Please create an impact document first.'))
            return

        if self._current_config is None:

            ndx = self._view_impacts.selectedIndexes()
            if ndx and len(ndx) >= 1:
                impact = self._model_impact.object_at(ndx[0].row())
                self._current_config = self._create_configuration( [impact])
            else:
                # no selected impact !
                showWarningBox( _("No impact selected document, so no active configuration"),
                                _("Please select an impact document to show which configuration to add a document to."))
                return

        elif self._current_config.frozen:
            showWarningBox( _("Trying to modify a frozen configuration"),
                            _("It is not allowed to modify a frozen configuration."))
            return

        dialog = AddFileToConfiguration( self, paths[0][1], [])
        dialog.exec_()
        if dialog.result() == QDialog.Accepted:
            new_line = CopyConfigurationLine()
            new_line.description = dialog.description
            new_line.version = dialog.version
            new_line.document_type = dialog.type_
            new_line.document = _make_quick_doc_dto(dialog.filename)
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

            new_line = CopyImpactLine()

            new_line.article_configuration = self._current_article
            new_line.article_configuration_id = self._current_article.article_configuration_id
            new_line.owner = user_session.employee()
            new_line.owner_id = user_session.employee().employee_id
            new_line.description = dialog.description
            new_line.document = _make_quick_doc_dto(dialog.filename)
            new_line.crl = dialog.crl
            new_line.modify_config = True


            # saved_line = store_impact_line( new_line)
            self._current_article.impacts.append( new_line)

            # FIXME should use a simpmle "datachanged" no ?
            self._model_impact.reset_objects( self._current_article.impacts )

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
                self.set_config( None)

    @Slot()
    def article_selected(self,selected,deselected):
        if selected and selected.indexes() and len(selected.indexes()) > 0:
            first_selected_index = selected.indexes()[0]
            ac = self._model_articles.object_at( first_selected_index)
            self.set_article_configuration( ac)


    @Slot(int)
    def article_activated( self, ndx : int):
        ac = self._model_articles.object_at( ndx)
        self.set_article_configuration( ac)

    @Slot(int)
    def _version_selected_slot(self, ndx : int):
        self.set_config( self._version_combo_model.objectAt(ndx))

    @Slot(str)
    def apply_filter( self, f : str):
        # self.set_configuration_articles( self._articles)
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
        self._change_tracker = ChangeTracker()

        self._articles = []
        self._current_article = None

        config_article_proto = list()
        config_article_proto.append(TextLinePrototype('customer_id',_('Customer'),editable=False))
        config_article_proto.append(TextLinePrototype('identification_number',_('Part number'),editable=False))
        config_article_proto.append(TextLinePrototype('revision_number',_('Part\nRev.'), editable=False))
        config_article_proto.append(TextLinePrototype('current_configuration_version',_('Cfg\nRev.'), editable=False))
        config_article_proto.append(DatePrototype('date_creation',_('Valid\nSince'), editable=False))
        config_article_proto.append(TextLinePrototype('current_configuration_status',_('Status'), editable=False))

        config_file_proto = []
        config_file_proto.append( EnumPrototype('document_type',_('Type'), TypeConfigDoc, editable=False))
        config_file_proto.append( TextLinePrototype('description',_('Description'),editable=False))
        config_file_proto.append( IntegerNumberPrototype('version',_('Rev.'),editable=False))
        config_file_proto.append( TextLinePrototype('document',_('File'), editable=False))
        config_file_proto.append( DatePrototype('date_upload',_('Date'), editable=False))
        config_file_proto.append( EnumPrototype('crl',_('CRL'), CRL, editable=True))

        config_impact_proto = []
        config_impact_proto.append( IntegerNumberPrototype('version',_('Cfg\nRev.'),editable=False))
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

        self._model_impact = ImpactsModel( self, config_impact_proto, CopyImpactLine)

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
              TextLinePrototype('revision_number',_('Rev.'), editable=False),
              TextLinePrototype('current_configuration_version',_("Cfg\nrev."), editable=False),
              DatePrototype('date_creation',_('Valid since'), editable=False),
              TextLinePrototype('current_configuration_status',_('Status'), editable=False) ])

        vlayout = QVBoxLayout()


        layout = QHBoxLayout()

        fm = QLabel().fontMetrics()

        max_widths = { 'customer_id' : '9999', 'identification_number' : '', 'revision_number' : 'MM','current_configuration_version' : '00', 'date_creation' : '29/12/99', 'current_configuration_status' :"NOT FROZEN"}
        for n in ['customer_id', 'identification_number', 'revision_number','current_configuration_version', 'date_creation', 'current_configuration_status']:
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


from sqlalchemy.orm import joinedload
from pyxfer.type_support import SQLADictTypeSupport, ObjectTypeSupport, SQLATypeSupport
from pyxfer.pyxfer import SQLAAutoGen, find_sqla_mappers, generated_code, USE, CodeWriter, SKIP
import logging
from pprint import pprint
logging.getLogger("pyxfer").setLevel(logging.DEBUG)




additioanl_code_for_document_dto = """
def __str__(self):
   return self.filename
"""

additioanl_code_for_article_configuration_dto = """@property
def current_configuration_status(self):
   c = ArticleConfiguration._current_configuration(self)

   if c and c.frozen:
      return "Frozen"
   else:
      return "Not frozen"

@property
def current_configuration_version(self):
   c = ArticleConfiguration._current_configuration(self)
   if c and c.version:
      return c.version
   else:
      return "-"
"""


additional_code_for_version_status_dto ="""
@property
def version_status(self):
    if self.frozen:
        return "Rev. {}, frozen".format( self.version)
    else:
        return "Rev. {}".format( self.version)
"""

additioanl_code_for_impact_line_dto ="""
@property
def approver_short(self):
    if self.approved_by:
        return self.approved_by.login.upper()
    else:
        return ""

@property
def owner_short(self):
    return self.owner.login.upper()

@property
def version(self):
    return ImpactLine._version(self)

@property
def date_upload(self):
    return ImpactLine._date_upload(self)
"""


model_and_field_controls = find_sqla_mappers( Base)
model_and_field_controls[Document] = {
    'order' : SKIP,
    'order_part' : SKIP,
    'quality_event' : SKIP }
model_and_field_controls[Employee] = {
    'picture_data' : SKIP,
    'filter_queries' : SKIP }
model_and_field_controls[OrderPart] = {
    'human_position' : SKIP,
    'production_file' : SKIP,
    'operations' : SKIP,
    'delivery_slip_parts' : SKIP,
    'documents' : SKIP,
    'quality_events' : SKIP,
    'configuration' : SKIP,
    'order' : SKIP }
model_and_field_controls[ImpactLine] = {
    'article_configuration' : SKIP } #,
# model_and_field_controls[ArticleConfiguration] = {
#     '_current_configuration' : SKIP }

# 'configuration' : SKIP }

pprint(model_and_field_controls)

global_cw = CodeWriter()
global_cw.append_code("from koi.config_mgmt.mapping import ArticleConfiguration, ImpactLine")

autogen = SQLAAutoGen( SQLADictTypeSupport, ObjectTypeSupport)

autogen.type_support(ObjectTypeSupport, ArticleConfiguration).additional_global_code.append_code(additioanl_code_for_article_configuration_dto)
autogen.type_support(ObjectTypeSupport, ImpactLine).additional_global_code.append_code(additioanl_code_for_impact_line_dto)
autogen.type_support(ObjectTypeSupport, Document).additional_global_code.append_code(additioanl_code_for_document_dto)
autogen.type_support(ObjectTypeSupport, Configuration).additional_global_code.append_code(additional_code_for_version_status_dto)

serializers = autogen.make_serializers( model_and_field_controls)
autogen.reverse()
serializers2 = autogen.make_serializers( model_and_field_controls)


#autogen = SQLAAutoGen( SQLATypeSupport, SQLADictTypeSupport)
autogen.set_type_supports( SQLATypeSupport, SQLADictTypeSupport)
serializers5 = autogen.make_serializers( model_and_field_controls)
autogen.reverse()
serializers6 = autogen.make_serializers( model_and_field_controls)



# Just for testing

model_and_field_controls2 = {
    Employee : model_and_field_controls[Employee],
    OrderPart : model_and_field_controls[OrderPart],
    Document : model_and_field_controls[Document]
    }

pprint(model_and_field_controls2)
autogen.set_type_supports(SQLATypeSupport, ObjectTypeSupport)
serializers3 = autogen.make_serializers( model_and_field_controls)
autogen.reverse()
serializers4 = autogen.make_serializers( model_and_field_controls)




# + serializers5 + serializers6
gencode = generated_code( serializers + serializers2 + serializers3 + serializers4+ serializers5 + serializers6, global_cw)

with open("t.py","w") as fo:
    fo.write( gencode)

from koi.config_mgmt.t import *

#executed_code = dict()
#print_code(gencode)
#exec( compile( gencode, "<string>", "exec"), executed_code)




from koi.config_mgmt.observer import ChangeTracker


def store_impact_line( impact_line):
    d = serialize_ImpactLine_CopyImpactLine_to_dict( impact_line, dict(), dict())
    encoded = encode(d)
    d = decode(encoded)

    with session().no_autoflush:
        serialize_ImpactLine_dict_to_ImpactLine( d, None, session(), dict())
        session().flush()
    session().commit()




def store_article_configuration( article_configuration):
    pyxfer_cache = dict()
    d = serialize_ArticleConfiguration_CopyArticleConfiguration_to_dict( org_configs[0], dict(), pyxfer_cache)

    mainlog.debug(d)

    encoded = encode(d)
    chrono_click("DTO to dict")
    d = decode(encoded)

    acid = -1
    with session().no_autoflush:
        sqla_article_configuration = serialize_ArticleConfiguration_dict_to_ArticleConfiguration( d, None, session(), dict())
        acid = sqla_article_configuration.article_configuration_id
    session().flush() # Don't commit as it empties the session (reloading entities afterwards takes tenth of seconds!)

    chrono_click( "from dict to SQLA - and flush")

    pyxfer_cache = dict()
    d = serialize_ArticleConfiguration_ArticleConfiguration_to_dict( sqla_article_configuration, None, pyxfer_cache)
    pprint( pyxfer_cache)
    chrono_click("read from SQLA to dict")

    encoded = encode(d)
    d = decode(encoded)
    ac = serialize_ArticleConfiguration_dict_to_CopyArticleConfiguration( d, None, dict())
    chrono_click("dict to DTO")

    return ac


def call( func_name, *func_params):
    return globals()[func_name](*func_params)


def store_object( klass, obj):

    chrono_start()

    kn = klass.__name__
    pyxfer_cache = dict()
    d = call( "serialize_{0}_Copy{0}_to_dict".format(kn,kn), obj, dict(), pyxfer_cache)
    #d = serialize_ArticleConfiguration_CopyArticleConfiguration_to_dict( org_configs[0], dict(), pyxfer_cache)

    mainlog.debug(d)

    encoded = encode(d)
    chrono_click("DTO to dict")
    d = decode(encoded)

    acid = -1
    with session().no_autoflush:
        sqla_article_configuration = call("serialize_{0}_dict_to_{0}".format(kn), d, None, session(), dict())
        # sqla_article_configuration = serialize_ArticleConfiguration_dict_to_ArticleConfiguration( d, None, session(), dict())
        acid = sqla_article_configuration.article_configuration_id
    session().flush() # Don't commit as it empties the session (reloading entities afterwards takes tenth of seconds!)

    chrono_click( "from dict to SQLA - and flush")

    pyxfer_cache = dict()

    d = call("serialize_{0}_{0}_to_dict".format(kn), sqla_article_configuration, None, pyxfer_cache)
    #d = serialize_ArticleConfiguration_ArticleConfiguration_to_dict( sqla_article_configuration, None, pyxfer_cache)
    mainlog.debug( pyxfer_cache)
    chrono_click("read from SQLA to dict")

    encoded = encode(d)
    d = decode(encoded)
    ac = call("serialize_{0}_dict_to_Copy{0}".format(kn), d, None, dict())
    #ac = serialize_ArticleConfiguration_dict_to_CopyArticleConfiguration( d, None, dict())
    chrono_click("dict to DTO")

    return ac


def load_article_configurations():

    chrono_start()
    res= []
    acs = session().query(ArticleConfiguration).\
        options(
            joinedload(ArticleConfiguration.part_plan),
            joinedload(ArticleConfiguration.customer),
            joinedload(ArticleConfiguration.impacts),
            joinedload(ArticleConfiguration.impacts).joinedload(ImpactLine.document),
            joinedload(ArticleConfiguration.impacts).joinedload(ImpactLine.owner),
            joinedload(ArticleConfiguration.impacts).joinedload(ImpactLine.approved_by),
            joinedload(ArticleConfiguration.configurations),
            joinedload(ArticleConfiguration.configurations).joinedload(Configuration.parts),
            joinedload(ArticleConfiguration.configurations).joinedload(Configuration.freezer),
            joinedload(ArticleConfiguration.configurations).joinedload(Configuration.lines),
            joinedload(ArticleConfiguration.configurations).joinedload(Configuration.lines).joinedload(ConfigurationLine.document),
            joinedload(ArticleConfiguration.configurations).joinedload(Configuration.origins),
            joinedload(ArticleConfiguration.configurations).joinedload(Configuration.origins).joinedload(ImpactLine.document),
            joinedload(ArticleConfiguration.configurations).joinedload(Configuration.origins).joinedload(ImpactLine.owner),
            joinedload(ArticleConfiguration.configurations).joinedload(Configuration.origins).joinedload(ImpactLine.approved_by)).\
        order_by(ArticleConfiguration.article_configuration_id)

    chrono_click("prepared query")
    acs = acs.all()


    #print("---"*100)
    #zz = acs[0].impacts
    #print("---"*100)

    chrono_click("Loaded all articles configurations")

    for ac in acs: #[:1]:
        #print("---"*100)
        d = serialize_ArticleConfiguration_ArticleConfiguration_to_dict( ac, None, dict())
        d = decode( encode( d))
        ac1 = serialize_ArticleConfiguration_dict_to_CopyArticleConfiguration( d, None, dict())
        res.append( ac1)
        #session().commit()
        chrono_click("Loaded {}/{} article configuration".format(len(res),len(acs)))
    #print("---"*100)

    return res



if __name__ == "__main__":
    from koi.config_mgmt.json_tools import encode, decode, register_enumerations
    from koi.db_mapping import OrderStatusType, TaskActionReportType, OrderPartStateType
    from koi.people_admin.people_admin_mapping import DayEventType
    from koi.datalayer.quality import QualityEventType
    from koi.datalayer.employee_mapping import RoleType

    register_enumerations( [TypeConfigDoc, ImpactApproval, DayEventType, OrderStatusType, TaskActionReportType, QualityEventType, OrderPartStateType, RoleType])

    from koi.tools.chrono import *
    from koi.config_mgmt.dummy_data import make_configs_dto, _make_quick_doc_dto
    mainlog.setLevel(logging.DEBUG)

    e = serialize_Employee_Employee_to_CopyEmployee( session().query(Employee).first(), None, {})
    user_session.open(e)

    op = session().query(OrderPart).all()[0]
    serialize_OrderPart_OrderPart_to_CopyOrderPart( op, None, {})

    app = QApplication(sys.argv)

    mw = QMainWindow()
    mw.setMinimumSize(1024+768,512+256)
    widget = EditConfiguration(mw)
    mw.setCentralWidget(widget)
    mw.show()

    org_configs = make_configs_dto( session)
    # store_object( ArticleConfiguration, org_configs[0])

    # org_configs = load_article_configurations()

    #exit()


    #pprint(d)

    # Change tracker for GUI
    # configs = [widget._change_tracker.wrap_in_change_detector(c)
    #            for c in org_configs][0:2]

    # Avoid edge cases of null cofniguration
    # for ac in org_configs:
    #     if not ac.configurations:
    #         c = CopyConfiguration()
    #         c.article_configuration = ac
    #         ac.configurations.append( c )

    configs = widget._change_tracker.wrap_in_change_detector(org_configs)

    # print( type( org_configs[0].configurations))
    # print( type( configs[0].configurations))
    widget.set_configuration_articles( configs)
    widget.persistent_filter.super_filter_entry.setText("5544A")
    widget.persistent_filter._emit_apply_filter()




    app.exec_()
