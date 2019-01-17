import sys
import subprocess
import os

from PySide.QtCore import Qt,Signal,Slot,QModelIndex,QSignalMapper
from PySide.QtGui import QHBoxLayout,QVBoxLayout, QDialog,QLabel,QWidget,QTableView, QToolButton, QHeaderView, QAbstractItemView, QMenu, QAction, QCursor
from PySide.QtGui import QFileDialog, QStandardItemModel
from PySide.QtGui import QPixmap,QIcon,QDragEnterEvent,QDragMoveEvent

from koi.Configurator import configuration, resource_dir

if __name__ == "__main__":
    from PySide.QtGui import QApplication

    from koi.base_logging import init_logging
    from koi.Configurator import init_i18n,load_configuration
    init_logging()
    init_i18n()
    load_configuration()

    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session
    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)

import platform
from PySide.QtGui import QPainter, QColor, QPen, QFont
from PySide.QtCore import QRect, QPoint

from koi.doc_manager.client_utils import download_document, upload_document, instanciate_template, documents_service
from koi.gui.dialog_utils import showErrorBox,make_progress,showServerErrorBox,confirmationBox
from koi.doc_manager.documents_mapping import Document
from koi.gui.ProxyModel import PrototypeArray
from koi.doc_manager.template_select_dialog import TemplateSelectDialog
from koi.base_logging import mainlog
from koi.server.json_decorator import ServerException
from koi.gui.ObjectModel import ObjectModel
from koi.gui.ProxyModel import FilenamePrototype, EmptyPrototype,DocumentCategoryPrototype
from koi.datalayer.types import DBObjectActionTypes


resources_cache = dict()

zone_colors = [Qt.GlobalColor.blue, Qt.GlobalColor.darkRed, Qt.GlobalColor.darkMagenta,
               Qt.GlobalColor.darkGreen, Qt.GlobalColor.darkYellow, Qt.GlobalColor.darkCyan]

def inverse_colors(c):
    if QColor(c).lightness() <= 150:
        return Qt.GlobalColor.white
    else:
        return Qt.GlobalColor.black

def category_colors(i : int):
    c = QColor(zone_colors[i % len(zone_colors)])
    return c



class AnimatedTableView(QTableView):

    def __init__(self, parent, drop_event_handler):
        super(AnimatedTableView,self).__init__(parent)
        #return # -TRACE- Doesn't prevent bugs

        self._drop_zones_shown = False
        self._selected_drop_zone = -1
        self._drop_event_handler = drop_event_handler

        self.setMouseTracking(True)
        self.setAcceptDrops(True)

        # Autoamatically sort by name
        self.setSortingEnabled(True)
        self.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self._titles_font = QFont("Arial",10,QFont.Bold)

    def _set_buttons_visible(self, visible=True):
        # mainlog.debug("_hide_buttons : {} rows to hide".format(self.model().rowCount()))

        # Actions should alwyas be on the last column...
        # FIXME Nothing prooves that
        action_column = self.model().columnCount() - 1

        for r in range(self.model().rowCount()):
            ndx = self.model().index(r, action_column)
            w = self.indexWidget(ndx)
            if w:
                w.setVisible(visible)

    def set_drop_zones(self, drop_zones_titles, drop_zones_color_indexes):
        assert len(drop_zones_titles) == len(drop_zones_color_indexes)

        mainlog.debug("Set drop zones {}".format(drop_zones_titles))
        self._drop_zones_titles = []
        self._drop_zones_colors = []
        for t,c in sorted(zip(drop_zones_titles, drop_zones_color_indexes), key=lambda p:p[0]):
            self._drop_zones_titles.append(t)
            self._drop_zones_colors.append(category_colors(c))

    def show_drop_zones(self, show : bool):
        # Have we at least one drop zone ? Else it's not very useful to display them :-)
        if len(self._drop_zones_titles) >= 1:
            if self._drop_zones_shown != show: # avor unnecessary screen update
                self._drop_zones_shown = show
                if not self._drop_zones_shown:
                    self._selected_drop_zone = -1
                self.viewport().update()

    def paintEvent(self, pe):

        if self._drop_zones_shown:
            painter = QPainter(self.viewport()) # See documentation to know why I draw on the viewport
            painter.setFont(self._titles_font)
            vr = self.rect()

            nb_drop_zones = len(self._drop_zones_titles)

            subr = QRect(vr)
            subr.setHeight( vr.height() / nb_drop_zones)

            for i in range(nb_drop_zones):
                c = self._drop_zones_colors[i]

                text_pen = QPen()
                text_pen.setColor(inverse_colors(c))
                painter.setPen(text_pen)

                if i == self._selected_drop_zone:
                    # mainlog.debug("selected drop zone is {}".format(i))
                    c = c.lighter(200)
                painter.setBrush(c)

                subr.moveTop(int(i*vr.height() / nb_drop_zones))
                painter.drawRect(subr)
                painter.drawText( QPoint(10,int((i+0.5)*vr.height() / nb_drop_zones)), self._drop_zones_titles[i])
            return None
        else:
            return super(AnimatedTableView,self).paintEvent(pe)

        #return x

    # def mouseMoveEvent(self, event : QMouseEvent):
    #
    #     #print("mouseMoveEvent {}".format(self._show_boxes))
    #     if self._drop_zones_shown:
    #         self._selected_drop_zone = event.y() / len(self._drop_zones_titles)
    #     else:
    #         self._selected_drop_zone = -1

    def _compute_drop_zone(self, pos, mimeData):
        nb_drop_zones = len(self._drop_zones_titles)
        w = self.viewport()
        drop_y = w.mapFromGlobal( self.mapToGlobal(pos)).y()

        if nb_drop_zones:

            bag = int(drop_y / (w.height() / nb_drop_zones))

            if bag < 0:
                bag = 0
            elif bag > nb_drop_zones - 1:
                bag = nb_drop_zones - 1

            self._selected_drop_zone = bag
        else:
            self._selected_drop_zone = -1


        if nb_drop_zones <= 1:

            if len(mimeData.urls()) == 1:
                drop_row = self.rowAt(drop_y)
                if drop_row >= 0:
                    self.selectRow(drop_row)
                else:
                    self.clearSelection()
            else:
                # More than on url then we're not going to replace
                # a file.
                self.clearSelection()

        # mainlog.debug("_selected drop zone {}".format(self._selected_drop_zone))

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

            # I don't use childAt because childAt will be fooled by the buttons
            # I have in this tableview (the buttons are the children of the
            # tableview, not the viewport... I guess)

            #if self.viewport().geometry().contains(e.pos()):
            self._compute_drop_zone(e.pos(), e.mimeData())
            self.show_drop_zones(True)
            self._set_buttons_visible(False)

            self.update()

        else:
            mainlog.debug("dragEnterEvent : I ignore")
            e.ignore()

        # This does no good at all :
        # return super(AnimatedTableView,self).dragEnterEvent(e)

    def dragMoveEvent(self, e: QDragMoveEvent):
        """ Show the user where he's gonna drop its file
        :param e:
        :return:
        """
        self._compute_drop_zone(e.pos(), e.mimeData())
        e.accept()

        # See not in dragEnterEvent about childAt
        if self.viewport().geometry().contains(e.pos()):
            #mainlog.debug("dragMoveEvent : inside")
            if not self._drop_zones_shown:
                self.show_drop_zones(True)
                self._set_buttons_visible(False)
            # Each time we move, the selected drop zone may change
            self.update()
        else:
            #mainlog.debug("dragMoveEvent : outside")
            self.show_drop_zones(False)
            self._set_buttons_visible(True)
            self.update()

        # return super(AnimatedTableView,self).dragMoveEvent(e)


    def dragLeaveEvent(self, e):
        # For some reason, I don't always receive the leave event. Don't know why...

        e.accept()
        mainlog.debug("dragLeaveEvent")
        self.show_drop_zones(False)
        self._set_buttons_visible(True)


    def dropEvent(self, e):
        e.accept()
        mainlog.debug("AnimatedTableView : accepted dropEvent")

        # Event forward
        self._drop_event_handler(e, self._selected_drop_zone)

        # will clear self._selected_drop_zone
        self.show_drop_zones(False)




def make_tool_button(filename,name=None):

    res_path = os.path.join(resource_dir,filename)
    if filename not in resources_cache:
        if not os.path.exists(res_path):
            raise Exception("Can't find resource {}".format(res_path))

        pixmap = QPixmap(res_path)
        icon = QIcon(pixmap)
        resources_cache[filename] = (pixmap, icon)

    pixmap, icon = resources_cache[filename]
    b = QToolButton()
    b.setIcon(icon);
    b.setIconSize(pixmap.rect().size())
    b.setMaximumWidth(pixmap.rect().width()) # 6
    if name:
        b.setObjectName(name)

    return b


from PySide.QtGui import QStyledItemDelegate
from PySide.QtGui import QUndoCommand,QUndoStack,QLineEdit

undo_stack = QUndoStack()


class UndoProxyEdit(QUndoCommand):
    def __init__(self, old_value, new_value, proxy_model, index):
        super(UndoProxyEdit,self).__init__()

        self._old_value, self._new_value, self._proxy_model, self._index = old_value, new_value, proxy_model, index
        self.setText("Undo")

    def undo(self):
        mainlog.info("Undo")
        self._proxy_model.setData(self._index, self._old_value)

    def redo(self):
        mainlog.info("Redo")
        self._proxy_model.setData(self._index, self._new_value)


class UndoDelegate(QStyledItemDelegate):
    def __init__(self,parent=None):
        QStyledItemDelegate.__init__(self,parent)

    def createEditor(self,parent,option,index):
        # Qt takes ownership of the editor
        # Therefore I have recreate it each time this method is called

        editor = QLineEdit(parent)

        # This is needed to put the editor in the right place
        if option:
            editor.setGeometry(option.rect)

        return editor

    def setModelData(self,editor,model,index):
        new_value = editor.text()
        old_value = index.data()
        undo = UndoProxyEdit( old_value, new_value, model, index)

        global undo_stack
        undo_stack.push(undo)
        mainlog.debug("Called push {}".format(undo_stack.count()))




class DocumentsModel(ObjectModel):
    """ This document model is expected to be a singleton tied to the
    widget.
    """

    def __init__(self, prototype):
        super(DocumentsModel,self).__init__(None, prototype, None)

        self.prototype = prototype # For testing purpose

        # Remeber if this model was already connected to the view
        # (to avoid double connection which PySide doesn't handle very well)
        self.__connected__ = False

    def has_changed(self) -> bool:
        """ Changed = edited, inserted or deleted.
        :return:
        """

        actions = self.export_objects_as_actions()

        # FIXME Not quite optimised, but at least I can do
        # it with very few lines of code

        for action_type, doc, op_ndx in actions:
            mainlog.debug("has_changed {} ".format(action_type))
            if action_type != DBObjectActionTypes.UNCHANGED:
                mainlog.debug("has_changed : true ")
                return True

        return False

    def apply_delayed_renames(self, documents_service):
        mainlog.debug("apply_delayed_renames")
        actions = self.export_objects_as_actions()
        for action_type, doc, doc_ndx in actions:

            # Since creation are not delayed, we can have the following :
            # 1. User upload a file (file stored with actual name, marked as TO_CREATE)
            # 2. User renames the file (file stays TO_CREATE, rename is delayed)
            # 3. User saves order parts (since file is TO_CREATE, and rename is delayed, we must apply the rename)

            if action_type == DBObjectActionTypes.TO_UPDATE or action_type == DBObjectActionTypes.TO_CREATE:
                mainlog.debug("apply_delayed_renames : applying")
                documents_service.update_name_and_description(doc.document_id, doc.filename, doc.description)


    def documents(self):
        # We make the assumption that each document can be present
        # only once in the list.

        return set(self.export_objects())

    def documents_to_remove(self):
        return self._deleted_objects

    def load_documents(self, documents):
        assert documents is not None, "Documents array is expected to be an aray, maybe empty, but array nonetheless"

        # I use reset objects so they don't look like
        # added object. See comments in reset_objects.

        # Be aware that I pass the documents array as it is.
        # So that documents array might be an instrumented one to check for adds/deletes/...
        # If you ever need to have a sort order which is better than
        # this, you'll have to change this model's index behaviour...)

        self.reset_objects(documents)

    def delete_document(self, doc):
        if doc.document_id:
            # the document is currently stored on the server
            # documents_service.delete(doc.document_id)
            self.remove_object(doc)
        else:
            # the doc is client side only
            self.remove_object(doc)

            # Not necessary to remember this object because
            # we won't need to delete it later on the server side
            self._deleted_objects.remove(doc)


    def text_color_eval(self,index : QModelIndex):
        r = index.row()

        if r >= 0:
            cid = self._objects[r].document_category_id
            if cid:
                return category_colors( cid)

        return Qt.GlobalColor.black

    def __getitem__(self, ndx):
        return self._objects[ndx]

    def __len__(self):
        return len(self._objects)


def documents_model_factory() -> DocumentsModel:
    prototype = PrototypeArray([
        DocumentCategoryPrototype('document_category_id',_("Cat."),editable=False), # Will be configured at instance lvel
        FilenamePrototype('filename',_("Filename")),
        EmptyPrototype(_("Actions"))
    ])

    return DocumentsModel(prototype)


class DocumentCollectionWidget(QWidget):



    """ Emitted whenever a document is added or removed from the list. """
    documents_list_changed = Signal()


    # def model_data(self):
    #     r = DocumentsModel()
    #     r.documents_changed = self.documents_changed
    #     r.documents_to_remove = self.documents_to_remove
    #     r.documents = self.model.export_objects()
    #     return r


    def set_model_data(self, model_data):
        mainlog.debug("set_model_data : setting on {}".format(model_data))
        if model_data:
            mainlog.debug("we're in for {} documents, structured as {} (id:{})".format(len(model_data.documents), type(model_data.documents), id(model_data.documents)))
            self.model.load_documents(model_data.documents)
        else:
            self.model.clear()


    def documents_ids(self):
        return [d.document_id for d in self.model.export_objects()]


    # WARNING : This is overriden in TemplatesCollectionWidget !!!
    @Slot(QModelIndex,QModelIndex)
    def _data_edited(self, top_left, bottom_right):
        if self.track_edits:
            mainlog.debug("Row edited {} {}".format(top_left.row(), bottom_right.row()))
            for i in range(top_left.row(), bottom_right.row()+1):
                ndx = self.model.index(i, 1)
                name = self.model.index(i, 0).data(Qt.UserRole)

                doc_id = self.model.object_at(i).document_id

                try:
                    # self.documents_service.update_name_and_description(doc_id, name, ndx.data())
                    self.documents_list_changed.emit()
                except ServerException as ex:

                    # Undo is tricky here. Indeed, at this point the model *is* changed
                    # to a value that is rejected (see exception). So if we'd like to
                    # undo that, we'll have to change the model back to its original value
                    # which will in turn trigger a "data edited". So that's not the way
                    # to do it... I guess the undo should be handled at the delegate level.

                    showServerErrorBox( ex)
                    return


    def set_model(self, model: DocumentsModel):
        """

        :param model:
        :return:
        """

        # -TRACE-
        # assert (model is not None) and isinstance(model, DocumentsModel), "Expecting DocumentsModel, but had {}".format(type(model))

        self.model = model

        # return # -TRACE- passees if return here


        # Replaced model won't be deleted (see Qt's doc). The view does not take ownership of the model unless it is the model's parent object because the model may be shared between many different views.

        # -TRACE- Using standarditem model makes things work
        # Using a DocumentsModel, event if not initiliazed crashes

        self.view.setModel(model) # TRACE- Crashes
        # self.view.setModel(QStandardItemModel()) # TRACE- Passes

        # return # -TRACE- crashesif return here

        if isinstance(model, DocumentsModel) and not self.model.__connected__:
            # Defensive : not sure how pyside handles re-re-re-reconnect
            self.model.__connected__ == True

            self.model.modelReset.connect(self.model_reset)
            self.model.rowsInserted.connect(self.rows_inserted)
            self.model.rowsAboutToBeRemoved.connect(self.rows_about_to_be_deleted)
            self.model.dataChanged.connect(self._data_edited)

        # If the model is already populated when set here, then
        # we must add the buttons...

        if self.model.rowCount() > 0:
            self.model_reset()

        # The first delegate support undo operation (well, it should)
        # The last delegate is not a delegate because we use a "table widget".

        # self.view.setItemDelegateForColumn(0, self.delegate)
        for i in range(len(self.prototype)):
            self.view.setItemDelegateForColumn(i, self.prototype[i].delegate())


    def set_documents_service(self,doc_service):
        """ Used by tests
        :param doc_service:
        :return:
        """

        assert doc_service
        self.documents_service = doc_service


    def set_used_categories(self,categories):
        """ Define the category that will be used for all documents that
        will be added.

        :param cat: None/[] == we don't use categories at all,  an array (order is important) of categories.
        :return:
        """

        self._used_categories = categories or []

        if self._used_categories:
            self.view.set_drop_zones([c.full_name for c in self._used_categories],
                                     [c.document_category_id for c in self._used_categories])

        else:
            self.view.set_drop_zones([], [])

        mainlog.debug("set_used_categories")
        if self._used_categories:
            # print("*********")
            # print(self._used_categories)
            self.prototype['document_category_id'].set_categories( self._used_categories)

    def __init__(self,parent=None, doc_service=None, show_description = False, used_category_short_name=[], no_header=False, prototype = None):
        super(DocumentCollectionWidget,self).__init__(parent)


        # -TRACE- Crashing code seems after this
        # return

        self.view = AnimatedTableView(self, drop_event_handler=self.animated_drop_event_handler)
        # self.view = QTableView() # -TRACE- prevents crash
        # Editing is started by single clicking on a selected cell or by using F2
        # Double click is disabled for editing => it will just open the file
        self.view.setEditTriggers(QAbstractItemView.SelectedClicked | QAbstractItemView.AnyKeyPressed | QAbstractItemView.EditKeyPressed)
        self.view.verticalHeader().setVisible(False)
        self.view.horizontalHeader().setVisible(False)
        self.view.setMinimumSize(250,100)
        self.view.setShowGrid(True)
        self.view.doubleClicked.connect(self._doubleClicked)

        #return # -TRACE- Crashing code seems before this

        if prototype:
            self.prototype = prototype
        else:
            # I tie the prototype to the instance because I will change some
            # of its delegate => I cannot share prototypes across instances...

            self.prototype = PrototypeArray([
                DocumentCategoryPrototype('document_category_id',_("Cat."),editable=False), # Will be configured at instance lvel
                FilenamePrototype('filename',_("Filename")),
                EmptyPrototype(_("Actions"))
            ])


        if doc_service:
            self.documents_service = doc_service
        else:
            self.documents_service = documents_service

        self.button_data = dict()
        self.button_id_counter = 1

        self.show_description = show_description
        self.documents_changed = False
        self.track_edits = True
        self.documents_to_remove = []



        # [] == we don't want to use categories at all (so no drop zones)
        if used_category_short_name != None and used_category_short_name != [] :
            categories = [ self.documents_service.find_category_by_short_name(used_category_short_name) ]
        elif used_category_short_name == [] : # Use all categories
            categories = self.documents_service.categories()
        else: # None => use no categories at all
            categories = None
        self.set_used_categories(categories)


        # self.delegate = FilenameDelegate()

        self.prototype['filename'].edit_next_item = False


        # self.delegate.edit_next_item = False

        mainlog.debug(self.prototype)

        # return # -TRACE- Test passes or crashes

        # I don't use the factory because I want this to work
        # also when inherited
        dummy_model = DocumentsModel(self.prototype)

        # dummy_model = QStandardItemModel()
        self.set_model(dummy_model ) # Doesn't prevent crash

        # return # -TRACE- Test crashes if it reaches here


        hb = QHBoxLayout()
        if no_header:
            hb.addWidget(QLabel(_("Documents")))
        else:
            hb.addWidget(QLabel(u"<h3>{}</h3>".format(_("Documents"))))

        pb = make_tool_button("appbar.page.upload.png","upload_button")
        pb.clicked.connect(self.add_document_dialog)
        pb.setObjectName("upload_button")
        hb.addWidget(pb)

        # pb = make_tool_button("appbar.book.hardcover.open.png", "add_template_button")
        # pb.clicked.connect(self.add_template_dialog)
        # pb.setToolTip(_("Add documents from the template library"))
        # hb.addWidget(pb)

        # return # -TRACE- Test crashes

        # -TRACE- return Crash after this

        l = QVBoxLayout()
        l.setContentsMargins(0,0,0,0)
        l.addLayout(hb)
        l.addWidget(self.view) # -TRACE- Commenting this makes the crash disappear
        self.setLayout(l)

        # -TRACE- Crash before this

        self.signal_mapper_open_button = QSignalMapper()
        self.signal_mapper_open_button.mapped.connect(self.open_clicked)
        self.signal_mapper_close_button = QSignalMapper()
        self.signal_mapper_close_button.mapped.connect(self.delete_remote_clicked)
        self.signal_mapper_save_a_copy_button = QSignalMapper()
        self.signal_mapper_save_a_copy_button.mapped.connect(self.save_a_copy_clicked)

        self.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.popup_menu)

    @Slot()
    def model_reset(self):
        mainlog.debug("model reset")
        for row in range(self.model.rowCount()):
            self._set_widget_buttons(row)

        # Make the buttons as small as possible
        self.view.resizeColumnToContents( self.model.columnCount()-1)
        self.view.resizeRowsToContents()

        # Pack the categories
        self.view.resizeColumnToContents( self.prototype.index_of('document_category_id'))

        self.view.horizontalHeader().setResizeMode(self.prototype.index_of('filename'), QHeaderView.Stretch)
        if self.show_description:
            self.view.horizontalHeader().setResizeMode(self.prototype.index_of('description'), QHeaderView.Stretch)
        # self.view.resizeColumnToContents(3)
        # self.view.resizeColumnToContents(2)


    @Slot(QModelIndex,int,int)
    def rows_inserted(self,parent,first,last):
        mainlog.debug("rows_inserted {} {} / row_count={}/{}".format(first,last,self.model.rowCount(), self.model.columnCount()))
        for row in range(first,last+1):
            self._set_widget_buttons(row)

        self.documents_list_changed.emit()

    @Slot(QModelIndex,int,int)
    def rows_about_to_be_deleted(self,parent,first,last):
        for row in range(first,last+1):
            doc_id = self.model.object_at(row).document_id

            for k,v in self.button_data.items():
                if v == doc_id:
                    del self.button_data[k]
                    break

        self.documents_list_changed.emit()


    def _set_widget_buttons(self, row):
        # mainlog.debug("_set_widget_buttons({})".format(row))

        doc = self.model.object_at(row)

        p_download = make_tool_button("appbar.page.download.png","download{}".format(self.button_id_counter))
        p_download.clicked.connect(self.signal_mapper_save_a_copy_button.map)
        self.signal_mapper_save_a_copy_button.setMapping(p_download, self.button_id_counter)

        # FIXME Json calls should produce rela objects and not tuples or Frozen,...
        has_reference = False
        try:
            has_reference = doc.reference
        except:
            pass


        # FIXME HAchkish this is really valid for templates, and not super-really-valid for mere documents
        if not has_reference:
            p_delete = make_tool_button("appbar.page.delete.png")
            p_delete.clicked.connect(self.signal_mapper_close_button.map)
            self.signal_mapper_close_button.setMapping(p_delete, self.button_id_counter)

        # I've already tested several things here
        # use a qss style, setting strecth, borders, contentsmargins, etc.
        # But for some reasons, when I test the widget in a dialog
        # the space between buttons is wide. If I run the widget in Horse
        # (that is, in normal conditions) then the display works as exepcted
        # (buttons close together and not wide apart)

        z = QWidget()
        layout = QHBoxLayout()
        layout.setSpacing(0)
        # layout.setStretch(0,0)
        # layout.setStretch(1,0)
        layout.setContentsMargins(0,0,0,0)
        # layout.addWidget(p_open)

        p_download.setContentsMargins(0,0,0,0)
        layout.addWidget(p_download)

        if not has_reference:
            p_delete.setContentsMargins(0,0,0,0)
            layout.addWidget(p_delete)
        # z.setMinimumHeight(64)

        z.setLayout(layout)

        # QTableView takes ownership of the widget (see Qt doc.)
        self.view.setIndexWidget( self.model.index( row,self.model.columnCount()-1), z)

        #doc.button_id = self.button_id

        # A bit complicated, but that's the simplest way
        # to tie an in-table button to some data
        self.button_data[self.button_id_counter] = (doc.document_id)
        self.button_id_counter += 1


    def _test_file_access(self, full_path_client):
        import os.path

        file_size = 0
        # Test the file access
        try:
            t = open(full_path_client,'rb')
            t.close()

            file_size = os.path.getsize(full_path_client)
            if file_size == 0:
                raise Exception(_("The file is empty"))

            return True
        except Exception as exc:
            showErrorBox(_("Can't open the file located at {}").format(full_path_client), ex=exc, object_name="drag_drop_error")
            return False

    @Slot(str, int)
    def _add_file_from_drop_zone(self, full_path_client : str, drop_zone : int):
        mainlog.debug("_add_file_from_drop_zone.Drop zone {}".format(drop_zone))

        if drop_zone != -1:
            self._add_file(full_path_client, self._used_categories[drop_zone].document_category_id)
        else:
            self._add_file(full_path_client)

    # WARNING : This is overrided in TemplatesCollectionWidget !!!
    def _add_file(self, full_path_client : str, document_category_id=None):
        mainlog.debug("document widget _add_file categ={}".format(document_category_id))
        if self._test_file_access(full_path_client):
            progress_bar = make_progress(_("Uploading"),100)
            def progress_tracker(percent):
                progress_bar.setValue( int(percent))

            try:
                doc_id = upload_document(full_path_client, progress_tracker)
            except Exception as exc:
                progress_bar.close()
                showErrorBox(_("There was a problem while uploading the file to the server"), ex=exc, object_name="file_upload_error")
                return

            d = self.documents_service.find_by_id(doc_id)
            doc = Document()
            doc.document_id = d.document_id
            doc.file_size = d.file_size
            doc.description = d.description
            doc.filename = d.filename
            doc.server_location = d.server_location
            doc.upload_date = d.upload_date

            if document_category_id:
                doc.document_category_id = document_category_id

            self.model.append_objects([doc])


    # WARNING : This is overrided in TemplatesCollectionWidget !!!
    def animated_drop_event_handler(self, e, selected_drop_zone):
        mainlog.debug("DocumentCollectionWidget.animated_drop_event_handler : _selected drop zone {}".format(selected_drop_zone))

        # No replace, just add

        for url in e.mimeData().urls():
            mainlog.debug("DropEvent -> {}".format(url.toString()))
            if platform.system() == "Windows":
                full_path_client = url.toString().replace('file:///','')
            else:
                full_path_client = url.toString().replace('file://','')

            self._add_file_from_drop_zone(full_path_client, selected_drop_zone)



    def _download_on_button_id(self, button_id, destination):
        """ Download a file.
        Returns the path to file or None if nothing was downloaded
        """

        # mainlog.debug("_download_on_button_id() : button_id={}".format(button_id))
        doc_id = self.button_data[button_id]

        # if os.path.isabs(full_path_client):
        #     # The file was uploaded during this GUI session. Therefore we
        #     # still know where we picked it from (FIXME unless someone has
        #     # removed it...)
        #
        #     return full_path_client
        # else:

        progress_bar = make_progress(_("Downloading"),100)
        def progress_tracker(percent):
            progress_bar.setValue( int(percent))

        try:
            path = download_document(doc_id, progress_tracker, destination)
            return path
        except Exception as exc:
            progress_bar.close()
            showErrorBox(_("There was a problem while downloading the file from the server"), ex=exc, object_name="file_upload_error")
            return None

        progress_bar.close()

    @Slot(int)
    def _doubleClicked(self, ndx):
        if ndx.isValid() and ndx.row() >= 0: # and ndx.column() == 0:
            # mainlog.debug("_doubleClicked {}".format(ndx.row()))
            # table_button_id = self.model.data( self.model.index(ndx.row(),0), Qt.UserRole + 1)

            doc_id = self.model.object_at(ndx.row()).document_id

            for k,v in self.button_data.items():
                if v == doc_id:
                    self.open_clicked(k)
                    break


    def _button_id_to_doc(self, button_id):
        doc_id = self.button_data[button_id]
        for doc in self.model.export_objects():
            if doc.document_id == doc_id:
                return doc

        raise Exception("Unable to locate doc_id {}".format(doc_id))


    def _save_file_dialog(self, proposed_filename):
        """ Return the selected file path or None if none was selected (bvb
        the user has hit Cancel

        This method exists to allow the test to avoid the file dialog.
        Automating test of QFileDialog is super complex.

        :param proposed_filename:
        :return:
        """
        return QFileDialog.getSaveFileName(self, _('Save a document'), proposed_filename, "")[0]


    def _open_file_dialog(self):
        # This method exists to allow the test to avoid the file dialog.
        # Automating test of QFileDialog is super complex.

        mainlog.debug("__open_file_dialog")
        return QFileDialog.getOpenFileName(self, _('Add a document'), "", "")[0]


    @Slot()
    def save_a_copy_clicked(self,button_id):
        # self.model.object_at()
        #
        # doc_id, full_path_client, file_size, description = self.button_data[button_id]
        # doc = documents_service.find_by_id(doc_id)

        doc = self._button_id_to_doc(button_id)

        full_path_client = self._save_file_dialog(doc.filename)

        # The user might hit "cancel" !
        if full_path_client:
            new_path = self._download_on_button_id(button_id, full_path_client)

            # mainlog.debug(u"{} <- {}".format(new_path,full_path_client))
            if new_path and new_path != full_path_client:
                os.rename(new_path, full_path_client)

    @Slot()
    def add_template_dialog(self):
        dialog = TemplateSelectDialog(None)
        dialog.refresh_templates_list()
        dialog.exec_()

        if dialog.template_id:
            try:
                for tpl_id in dialog.template_id:
                    doc_id = instanciate_template(tpl_id)
                    doc = self.documents_service.find_by_id(doc_id)
                    self._add_one_document(doc.filename, doc.document_id, doc.file_size, doc.description)
                self._mark_changed()
            except Exception as exc:
                showErrorBox(_("There was a problem while uploading the template to the server"), ex=exc, object_name="template_upload_error")


    @Slot()
    def add_document_dialog(self):
        mainlog.debug("add_document_dialog")
        full_path_client = self._open_file_dialog()
        # The user might hit "cancel" !
        if full_path_client:
            self._add_file(full_path_client)
            # self.documents_changed = true

    @Slot()
    def open_clicked(self,button_id):
        filepath = self._download_on_button_id(button_id, None)
        if filepath:
            try:
                if sys.platform.startswith('darwin'):
                    subprocess.call(('open', filepath))
                elif os.name == 'nt':
                    os.startfile(filepath)
                elif os.name == 'posix':
                    subprocess.call(('xdg-open', filepath))
            except Exception as ex:
                showErrorBox(_("Can't open file"),_("I'm unable to open the file"),ex)

    # WARNING : This is overriden in TemplatesCollectionWidget !!!
    @Slot()
    def delete_remote_clicked(self,button_id):
        doc_id  = self.button_data[button_id]
        doc = self.model.locate_object( lambda obj: obj.document_id == doc_id)

        if confirmationBox(_("Deleting a document"),
                           _("Are you sure you want to remove {}").format(doc.filename)):
            try:
                self.model.delete_document(doc)
            except Exception as ex:
                showErrorBox(_("There was an error while deleting a document"),ex=ex)


    @Slot(str)
    def file_modified_slot(self, path):
        pass
        # print("file_modified_slot")


    def _mark_changed(self):
        """ That's rather primitive. Indeed if a new document
        is added and then removed, we can say that the list has
        *not* changed. But with mark_changed on add file, we'll
        never be able to see that...
        """

        self.documents_changed = True
        self.documents_list_changed.emit()


    @Slot(QPoint)
    def popup_menu(self,position):

        selected_row = self.view.rowAt(position.y())

        if selected_row >= 0 and self._used_categories and len(self._used_categories) > 1:
            category_menu = QMenu(_("Categories"))
            selected_doc = self.model.object_at(selected_row)

            category_actions = []
            for category in self._used_categories:
                a = QAction(category.full_name, category_menu)
                a.setData(category)

                a.setEnabled(selected_doc.document_category_id != category.document_category_id)

                category_menu.addAction(a)
                category_actions.append(a)

            action = category_menu.exec_(QCursor.pos())

            if action:
                new_category = action.data()

                if selected_doc.document_category_id != new_category.document_category_id:
                    selected_doc.document_category_id = new_category.document_category_id
                    self.model.signal_object_change(selected_doc)

                # direct mode
                #self.documents_service.set_document_category(doc.document_id, new_category.document_category_id)




class DocumentCollectionWidgetDialog(QDialog):

    def tab_changed(self, ndx):
        self.widget.setVisible( not self.widget.isVisible())

    def __init__(self,parent, doc_service):
        super(DocumentCollectionWidgetDialog,self).__init__(parent)

        # Hackish, helps testing

        self.documents_changed = False

        # self.view = QTableView()
        # self.view.setMinimumSize(300,100)

        self.widget = DocumentCollectionWidget(self, doc_service, show_description=False)

        # vsbw = VerticalSideBarLayout(self.view, [self.widget])

        layout = QHBoxLayout()
        layout.addWidget(self.widget)
        self.setLayout(layout)

        # vsbw.show_star_on_widget(self.widget)

        # self.buttons = QDialogButtonBox()
        # self.buttons.addButton( QDialogButtonBox.StandardButton.Cancel)
        # self.buttons.addButton( QDialogButtonBox.Ok)
        # #self.setLayout(top_layout)
        # self.buttons.accepted.connect(self.accept)
        # self.buttons.rejected.connect(self.reject)



if __name__ == "__main__":


    # download_document(upload_document(r"c:\temp\vd.ico"))
    # exit()

    # 000100847802



    app = QApplication(sys.argv)
    qss = open( os.path.join(resource_dir,"standard.qss"),"r")
    app.setStyleSheet(qss.read())
    qss.close()

    dialog = DocumentCollectionWidgetDialog(parent=None,doc_service=None)
    # dialog.widget.set_documents(documents_service.find_by_order_id(1000))

    dialog.exec_()

    # documents_service.associate_to_order(1000, dialog.widget.documents_ids())

    # dialog.widget.set_model_data( dialog.widget.model_data())
    # dialog.exec_()
