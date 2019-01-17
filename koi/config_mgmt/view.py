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
    import logging
    from PySide.QtGui import QMainWindow

    from koi.base_logging import init_logging, mainlog
    from koi.Configurator import init_i18n,load_configuration,configuration

    init_logging()
    mainlog.setLevel(logging.DEBUG)

    init_i18n()
    load_configuration()

    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session,session

    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)

# from koi.db_mapping import Employee
# for t in session().query(Employee.employee_id).all():
#     print("{} {}".format( type(t), t.employee_id))

from koi.base_logging import mainlog
from koi.config_mgmt.mapping import *

from koi.gui.ObjectModel import ObjectModel
from koi.gui.combo_object_model import ObjectComboModel
from koi.gui.ComboDelegate import PythonEnumComboDelegate
from koi.gui.ProxyModel import PrototypeController,IntegerNumberPrototype,FloatNumberPrototype, DurationPrototype,TrackingProxyModel,OperationDefinitionPrototype,PrototypedTableView,ProxyTableView,OrderPartDisplayPrototype,TextAreaPrototype, FutureDatePrototype,PrototypeArray,TextLinePrototype, Prototype, DatePrototype, BooleanPrototype
from koi.gui.dialog_utils import SubFrame, TitleWidget, showWarningBox, yesNoBox2

from koi.gui.PrototypedModelView import PrototypedModelView
from koi.config_mgmt.dragdrop_widget import DragDropWidget
from koi.gui.PersistentFilter import PersistentFilter
from koi.gui.horse_panel import HorsePanel
from koi.session.UserSession import user_session
from koi.datalayer.serializers import CopyConfiguration

if __name__ != "__main__":
    from koi.datalayer.serializers import *

from koi.config_mgmt.dummy_data import _make_quick_doc_dto
from koi.config_mgmt.service import configuration_management_service
from koi.config_mgmt.track_item import TrackNewItemDialog


def open_impact_documents( ac : ArticleConfiguration):
    return list( filter( lambda il: il.configuration_id is None, [ c for c in ac.impacts]))


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



def configuration_version_status( cfg : CopyConfiguration):
    if cfg.is_baseline:
        v = _("Baseline configuration")
    else:
        v = _("Revision {}").format( cfg.version)

    if cfg.frozen:
        return "{}, frozen".format( v)
    else:
        return "{}".format( v)

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

class SelectImpactDocumentsDialog(QDialog):

    def _make_ui(self, info_text):

        config_impact_proto = list()

        config_impact_proto.append( BooleanPrototype('selected', "", editable=True))
        config_impact_proto.append( TextLinePrototype('description',_('Description'),editable=False))
        # config_impact_proto.append( IntegerNumberPrototype('version',_('Cfg\nRev.'),editable=False))
        config_impact_proto.append( TextLinePrototype('document',_('File'), editable=False))
        config_impact_proto.append( EnumPrototype('approval',_('Approval'), ImpactApproval, editable=False))
        config_impact_proto.append( DatePrototype('date_upload',_('Date'), editable=False))

        top_layout = QVBoxLayout()

        top_layout.addWidget( QLabel( info_text))

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

        self._model_impact.dataChanged.connect( self._data_changed)


    @Slot()
    def _data_changed( self, topLeft : QModelIndex, bottomRight : QModelIndex):
        left_column = topLeft.column()
        right_column = bottomRight.column()

        if left_column <= 0 <= right_column:
            for impact in self._model_impact.read_only_objects():
                if impact.selected:
                    self.buttons.button(QDialogButtonBox.Ok).setEnabled( True)
                    return

        self.buttons.button(QDialogButtonBox.Ok).setEnabled( False)

    def __init__(self, parent, config : Configuration, impacts, info_text):
        super( SelectImpactDocumentsDialog, self).__init__(parent)

        self._make_ui( info_text)

        self.impacts = list( filter( lambda il: il.configuration_id is None, [ ImpactLineExtended( c ) for c in impacts]))
        self._model_impact.reset_objects( self.impacts )
        self.buttons.button(QDialogButtonBox.Ok).setEnabled( False)

    def selected_impacts(self):
        return [proxy._object for proxy in filter( lambda impact: impact.selected == True, self.impacts)]

    @Slot()
    def accept(self):
        return super(SelectImpactDocumentsDialog,self).accept()

    @Slot()
    def reject(self):
        return super(SelectImpactDocumentsDialog,self).reject()



class AddFileToConfiguration(QDialog):


    def __init__(self, parent, filename, previous_lines, for_impact_doc=False):
        super( AddFileToConfiguration, self).__init__(parent)

        self.crl = None
        self.filename = filename
        self.description = ""
        self.type_ = TypeConfigDoc.PROGRAM
        self.version = 1

        top_layout = QVBoxLayout()
        self.setLayout(top_layout)

        top_layout.addWidget( QLabel("Filename : <b>{}</b>".format( filename)))

        if not for_impact_doc:
            self.type_choice = QComboBox()
            for s in TypeConfigDoc:
                if s != TypeConfigDoc.IMPACT:
                    self.type_choice.addItem( s.value, s)

            self._type_label = QLabel("Type :")
            top_layout.addWidget( self._type_label)
            top_layout.addWidget( self.type_choice)
            title = _("Add a file to a configuration")
        else:
            self.type_choice = None
            title = _("Add an impact document")

        self.setWindowTitle(title)

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
        if self.type_choice:
            self.type_ = self.type_choice.itemData( self.type_choice.currentIndex())
        else:
            self.type_ = None

        return super(AddFileToConfiguration,self).accept()

    @Slot()
    def reject(self):
        return super(AddFileToConfiguration,self).reject()






class EditConfiguration(HorsePanel):
    order_part_selected = Signal(int)

    # def version_selected( self, ndx):
    #     self.set_config( self._current_article.configurations[ndx] )

    def set_configuration_articles( self, cfg_articles : list):
        #print("set_configuration_articles : {}".format(cfg_articles))
        #print("set_configuration_articles : {}".format(type(cfg_articles)))
        self._articles = cfg_articles
        self._model_articles.reset_objects( self._articles)

        if DEMO_MODE == 0:
            self._wl.set_objects( self._articles)

        if self._articles:
            self.set_article_configuration( self._articles[0])
        else:
            self.set_article_configuration( None)

    def set_article_configuration( self, ca : ArticleConfiguration):

        assert ca is None or isinstance(ca, ArticleConfiguration) or isinstance(ca, CopyArticleConfiguration), "Bad type {}".format( type(ca))

        # wrapped = self._change_tracker.wrap_in_change_detector(ca)
        # if wrapped == self._current_article:
        #     return
        # else:
        #     self._current_article = wrapped

        if self._current_article and self._current_article.article_configuration_id == ca.article_configuration_id:
            keep_configuration_open = self._current_config.configuration_id
        else:
            keep_configuration_open = False

        self._current_article = ca

        if self._current_article:
            #print("--- version combo setModel : {}".format( type( self._current_article.configurations)))
            self._version_combo_model.setObjects( self._current_article.configurations)
            #print("-o- "*10)
            self._model_impact.reset_objects( self._current_article.impacts )

            if self._view_articles.currentIndex().isValid():
                ndx = self._view_articles.currentIndex().row()
                selected_ca = self._model_articles.object_at( ndx)
                if selected_ca.article_configuration_id == ca.article_configuration_id:
                    self._model_articles.set_object_at( ndx, ca)

            # By default, we display the last frozen config.

            config_set = False

            if keep_configuration_open:
                for c in reversed( self._current_article.configurations):
                    if c.configuration_id == keep_configuration_open:
                        self.set_configuration(c)
                        config_set = True
                        break

            else:
                for c in reversed( self._current_article.configurations):
                    if c.frozen:
                        self.set_configuration(c)
                        config_set = True
                        break

            if not config_set:
                if len( self._current_article.configurations) > 0:
                    self.set_configuration(ca.configurations[len( self._current_article.configurations) - 1])
                else:
                    self.set_configuration( None)
        else:
            self._version_combo_model.setObjects([])
            self._model_impact.reset_objects([])
            self.set_configuration( None)


    def set_configuration( self, config : Configuration):

        self._current_config = config

        if config == None:
            self._model.reset_objects( None )
            self._subframe.set_title( "No configuration")
            self._version_config_label.setText( "No configuration")
            self._freeze_button.setEnabled(False)
            self._versions_combo.setEnabled(False)
            self._version_config_label.setText( "No Revision")

            if DEMO_MODE == 0:
                self._parts_widget.set_objects( [])
            elif DEMO_MODE == 1:
                self._parts_widget.setText( _("Not used"))

            #self._parts_widget.hide()
            return


        ac = config.article_configuration
        full_version = "{}/{}".format( ac.identification_number, ac.revision_number or "-")
        msg = "Configuration for part <b>{}</b>, client : <b>{}</b>".format( full_version, ac.customer_id)

        self._freeze_button.setEnabled(True)
        if config.frozen:
            freeze_msg = "<b><font color = 'green'>FROZEN on {} by {}</font></b>".format( config.frozen, config.freezer.fullname)

            self._freeze_button.setText(_("Unfreeze"))
            self._freeze_button.setEnabled( True)
        else:
            freeze_msg = "<b><font color = 'red'>NOT frozen</font></b>"

            can_freeze = len(config.lines) >= 1 # Configuration must not be empty
            self._freeze_button.setText(_("Freeze"))
            self._freeze_button.setEnabled( can_freeze)


        can_add_revision = len(config.lines) >= 1 # Adding a revision after an empty one seems strange
        self._add_config_button.setEnabled(can_add_revision)

        self._subframe.set_title( msg)

        if config.version == 0:
            rev = "Baseline"
        else:
            rev = "Revision {}".format(config.version)

        self._version_config_label.setText( "{}, {}".format(rev, freeze_msg))
        self._model.reset_objects( config.lines )

        self._versions_combo.setEnabled(True)
        self._versions_combo.setCurrentIndex(
            self._version_combo_model.objectIndex( config).row())


        if DEMO_MODE == 0:
            part_revs = [PartRev( config, part) for part in config.parts]
            self._parts_widget.set_objects( part_revs)
        else:
            if config.parts:
                self._parts_widget.setText( _("Used in order part(s) : ") + ", ".join(
                    [ "<a href='{}/{}'>{}</a>".format( part.order_part_id, part.order.customer_id,part.human_identifier) for part in config.parts] ))
            else:
                self._parts_widget.setText( _("Not used"))


    def _create_configuration( self, impact_documents):
        ac = configuration_management_service.add_configuration_revision(
            self._current_article.article_configuration_id, [ doc.impact_line_id for doc in impact_documents ])
        self.set_article_configuration( ac)
        return ac.configurations[-1]

    @Slot()
    def add_configuration(self):

        if self._current_config != self._current_article.configurations[-1]:
            if not yesNoBox2("Are you sure ?","There's another revision with higher version. Are you sure you want to create another one ?"):
                return

        oidocs = open_impact_documents( self._current_article)

        if oidocs :
            dialog = SelectImpactDocumentsDialog( self, self._current_config,
                                                  filter( lambda imp: imp.approval == ImpactApproval.UNDER_CONSTRUCTION, oidocs),
                                                  "Please select at least one impact document that correspond to the new revision.")
            dialog.setWindowTitle( _("Add a configuration revision"))
            dialog.exec_()
            if dialog.result() == QDialog.Accepted:
                self._create_configuration( dialog.selected_impacts())

            dialog.deleteLater()
        else:
            showWarningBox( _("Can't create new configuration revision !"),
                            _("You cannot create the configuration revision because there are no suitable impact document in the article. You should add a new impact document first."))


    @Slot()
    def freeze_configuration(self):
        if self._freeze_button.text() == _("Freeze"):
            self.set_article_configuration(
                configuration_management_service.freeze_configuration( self._current_config ))
        else:
            self.set_article_configuration(
                configuration_management_service.unfreeze_configuration( self._current_config ))


    @Slot()
    def configFilesDropped( self,paths):
        # if not self._current_config.is_baseline and self._model_impact.rowCount() == 0:
        #     showWarningBox( _("Trying to create a configuration without impact document"),
        #                     _('It is not allowed to add files to a configuration while there are no impact file that "frame" it. Please create an impact document first.'))
        #     return

        # selected_indices = self._view_impacts.selectedIndexes()
        # if selected_indices and len(selected_indices) >= 1:
        #     impact_documents = [self._model_impact.object_at(ndx.row()) for ndx in selected_indices]
        # else:
        #     impact_documents = None

        # if self._current_config is None:

        #     if not impact_documents:
        #         # no selected impact !
        #         showWarningBox( _("No impact selected document, so no active configuration"),
        #                         _("Please select an impact document to show which configuration to add a document to."))
        #         return

        if self._current_config.frozen:
            showWarningBox( _("Trying to modify a frozen configuration"),
                            _("It is not allowed to modify a frozen configuration. Unfreeze it first."))
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
            new_line.configuration_id = self._current_config.configuration_id

            ac = configuration_management_service.add_document_to_configuration( new_line)
            self.set_article_configuration( ac)

        dialog.deleteLater()

    @Slot()
    def impactFilesDropped( self,paths):
        dialog = AddFileToConfiguration( self, paths[0][1], [], for_impact_doc=True)

        dialog.exec_()
        if dialog.result() == QDialog.Accepted:

            new_line = CopyImpactLine()

            # new_line.article_configuration = self._current_article
            new_line.article_configuration_id = self._current_article.article_configuration_id
            # new_line.owner = user_session.employee()
            new_line.owner_id = user_session.employee().employee_id
            new_line.description = dialog.description
            new_line.document = _make_quick_doc_dto(dialog.filename)
            new_line.crl = dialog.crl
            new_line.approval = ImpactApproval.UNDER_CONSTRUCTION

            ac = configuration_management_service.add_impact_document( new_line)
            self.set_article_configuration( ac)

        dialog.deleteLater()

    @Slot()
    def impact_activated(self,selected,deselected):
        if selected and selected.indexes() and len(selected.indexes()) > 0:
            impact = self._model_impact.object_at( selected.indexes()[0])

            # print("cfg : {}".format(impact.configuration))
            # print(impact.description)
            # print(impact.document)

            if impact.configuration:
                self.set_configuration( impact.configuration)
            else:
                # Selecting an impact document that is not wired to a specific configuration
                # just produces no effect.
                pass
                # self.set_configuration( None)

    @Slot()
    def _search_configuration_articles(self):
        key = self._search_line_edit.text()
        mainlog.debug("Searching {}".format( key))
        self.set_configuration_articles( configuration_management_service.search_configuration_articles( key))

    @Slot(QPoint)
    def showACContextualMenu(self, position : QPoint):
        mainlog.debug("showACContextualMenu")
        menu = QMenu()
        # menu.addAction(self.copy_operations_action)
        menu.addAction( self.edit_ac_action)

        action = menu.exec_(QCursor.pos())

    @Slot()
    def edit_article_configuration(self):
        mainlog.debug("edit_article_configuration")

        ac = self._model_articles.object_at( self._view_articles.currentIndex().row())
        d = TrackNewItemDialog(None, None)
        d.load_inputs( ac)
        d.exec_()

        if d.result() == QDialog.Accepted:
            ac.customer_id, ac.identification_number, ac.revision_number = d.inputs()
            #self._article_configuration = configuration_management_service.edit_item( ac)
            #model.signal_object_change(self, obj):


    @Slot()
    def _track_new_item(self):
        d = TrackNewItemDialog(None, None)
        d.exec_()

        if d.result() == QDialog.Accepted:

            ac = ArticleConfiguration()
            ac.customer_id, ac.identification_number, ac.revision_number = d.inputs()
            self.set_configuration_articles( [ configuration_management_service.track_new_item( ac) ])

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
        self.set_configuration( self._version_combo_model.objectAt(ndx))

    @Slot(str)
    def apply_filter( self, f : str):
        # self.set_configuration_articles( self._articles)
        self.set_article_configuration( self._articles[0])

        for c in self._articles[0].configurations:
            for op in c.parts:
                if op.human_identifier == f:
                    self.set_configuration( c)
                    return

    @Slot(str)
    def partLinkClicked( self, link : str):
        order_part_id, customer_id = [int(x) for x in link.split('/')]

        self.order_part_selected.emit( order_part_id)

        #print(order_part_id)

    def __init__( self, parent):
        super(EditConfiguration,self).__init__(parent)
        self._change_tracker = ChangeTracker()

        self.set_panel_title(_('Configurations'))
        self._articles = []
        self._current_article = None


        self.edit_ac_action = QAction(_("Edit article configuration"),self)
        self.edit_ac_action.triggered.connect( self.edit_article_configuration)
        #self.edit_ac_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_C))
        self.edit_ac_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)


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

        # self.super_filter_entry = QLineEdit()
        # self.persistent_filter = PersistentFilter( self.super_filter_entry, "articles_configs" )
        # self.persistent_filter.apply_filter.connect( self.apply_filter)
        # top_layout.addWidget(self.persistent_filter)

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
        self._view_articles.customContextMenuRequested.connect(self.showACContextualMenu)
        self._view_articles.setContextMenuPolicy(Qt.CustomContextMenu)

        left_layout = QVBoxLayout()



        self._search_line_edit = QLineEdit()
        self._search_line_edit.returnPressed.connect( self._search_configuration_articles)

        search_box_hlayout = QHBoxLayout()
        search_box_hlayout.addWidget( QLabel( _("Find")))
        search_box_hlayout.addWidget( self._search_line_edit)
        b = QPushButton(_("New"))
        b.clicked.connect( self._track_new_item)
        search_box_hlayout.addWidget( b)



        if DEMO_MODE == 0:

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

            left_layout.addWidget(SubFrame(_("Configuration Articles"), scroll_area, self, right_layout=search_box_hlayout))
        else:
            left_layout.addWidget(SubFrame( _("Configuration Articles"), self._view_articles, self, right_layout=search_box_hlayout))

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
        self._version_combo_model = ObjectComboModel( parent, configuration_version_status)
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
        self.setText(_("Used in order part <b>{}</b> : {}").format( p.human_identifier, p.description) )

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



from sqlalchemy.orm import joinedload
from pyxfer.type_support import SQLADictTypeSupport, ObjectTypeSupport, SQLATypeSupport
from pyxfer.pyxfer import generated_code, USE, CodeWriter, SKIP, COPY
from pyxfer.sqla_autogen import SQLAAutoGen
import logging
from pprint import pprint
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
    #pprint( pyxfer_cache)
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

    with session().no_autoflush:
        sqla_article_configuration = call("serialize_{0}_dict_to_{0}".format(kn), d, None, session(), dict())
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
    #mainlog.setLevel(logging.DEBUG)

    from koi.dao import dao

    dao.set_session( session())

    # from koi.datalayer.gen_serializers import  write_code, generate_serializers
    # write_code( generate_serializers())
    from koi.datalayer.serializers import *



    e = serialize_Employee_Employee_to_CopyEmployee( session().query(Employee).first(), None, {})
    e = session().query(Employee).first()
    user_session.open(e)

    # op = session().query(OrderPart).all()[0]
    # serialize_OrderPart_OrderPart_to_CopyOrderPart( op, None, {})

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

    #configs = widget._change_tracker.wrap_in_change_detector(org_configs)
    configs = org_configs



    # print( type( org_configs[0].configurations))
    # print( type( configs[0].configurations))
    widget.set_configuration_articles( configs)
    #widget.persistent_filter.super_filter_entry.setText("5544A")
    #widget.persistent_filter._emit_apply_filter()




    app.exec_()
