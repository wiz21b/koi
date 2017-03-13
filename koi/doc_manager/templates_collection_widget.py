import os
import os.path

from PySide.QtCore import Qt, Slot,QModelIndex,QSignalMapper
from PySide.QtGui import QHBoxLayout,QVBoxLayout, QDialogButtonBox,QDialog,QLabel,QWidget,QTableView,QStandardItemModel,QStandardItem, \
    QToolButton, QHeaderView
from PySide.QtGui import QFileDialog,QMessageBox
from PySide.QtGui import QPixmap,QIcon

from koi.Configurator import mainlog,configuration

if __name__ == "__main__":
    import sys
    from PySide.QtGui import QApplication

    from koi.base_logging import init_logging
    from koi.Configurator import init_i18n,load_configuration
    init_logging()
    init_i18n()
    load_configuration()

    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session
    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)


from koi.Configurator import resource_dir
from koi.doc_manager.client_utils import download_document, upload_template, remove_document
from koi.gui.dialog_utils import showErrorBox,confirmationBox, make_progress,place_dialog_on_screen
from koi.portability import open_a_file_on_os
from koi.gui.dialog_utils import TitleWidget,confirmationBox
from koi.doc_manager.documents_service import documents_service
from koi.gui.PrototypedModelView import PrototypedQuickView, PrototypedModelView
from koi.gui.ProxyModel import TextLinePrototype, PrototypeArray

resources_cache = dict()

def make_tool_button(filename):

    res_path = os.path.join(resource_dir,filename)
    if filename not in resources_cache:
        if not os.path.exists(res_path):
            raise Exception("Can't find resource {}".format(res_path))

        pixmap = QPixmap(res_path)
        icon = QIcon(pixmap)
        resources_cache[filename] = (pixmap, icon)

    pixmap, icon = resources_cache[filename]
    b = QToolButton()
    b.setIcon(icon)
    b.setIconSize(pixmap.rect().size())
    b.setMaximumWidth(pixmap.rect().width() + 6)

    return b


from koi.doc_manager.docs_collection_widget import DocumentCollectionWidget, PrototypeArray

from koi.gui.ProxyModel import FilenamePrototype, EmptyPrototype
from koi.datalayer.types import DBObjectActionTypes

class TemplatesCollectionWidget(DocumentCollectionWidget):

    prototype = PrototypeArray([
        FilenamePrototype('filename',_("Filename")),
        TextLinePrototype('description',_("Description"),editable=True),
        TextLinePrototype('reference',_("Horse Ref."),editable=False),
        EmptyPrototype(_("Actions"))
    ])

    def __init__(self,parent=None, doc_service=None):
        super(TemplatesCollectionWidget,self).__init__(parent, doc_service, used_category_short_name=None, prototype=self.prototype)

    def categories(self):
        return []

    def _apply_pending_changes(self):
        """ As the edit widget delays its modification, we have to add a function
        that will commit the modifications ASAP. I do it this way so that
        all the modification management is done at the same place.
        :return:
        """

        actions = self.model.export_objects_as_actions()
        for action_type, document, op_ndx in actions:
            if action_type == DBObjectActionTypes.TO_DELETE:
                remove_document(document.document_id)
            elif action_type == DBObjectActionTypes.TO_CREATE:
                pass # Creation is done directly
            elif action_type == DBObjectActionTypes.TO_UPDATE:
                self.documents_service.update_name_and_description(document.document_id, document.filename, document.description)

        self.refresh_templates_list()


    def refresh_templates_list(self):

        documents = sorted( list(self.documents_service.all_templates()),
            key=lambda d:( ("B" if d.reference else "A")  + d.filename))

        self.model.load_documents(documents)


    @Slot(QModelIndex,QModelIndex)
    def _data_edited(self, top_left, bottom_right):
        super(TemplatesCollectionWidget,self)._data_edited(top_left, bottom_right)
        if self.track_edits:
            self._apply_pending_changes()

    @Slot()
    def model_reset(self):
        mainlog.debug("model reset")
        for row in range(self.model.rowCount()):
            self._set_widget_buttons(row)

        # Make the buttons as small as possible
        self.view.resizeColumnToContents( self.model.columnCount()-1)
        self.view.resizeRowsToContents()

        self.view.horizontalHeader().setResizeMode(0, QHeaderView.Stretch)
        self.view.horizontalHeader().setResizeMode(1, QHeaderView.Stretch)
        self.view.resizeColumnToContents(3)
        self.view.resizeColumnToContents(2)



    @Slot()
    def delete_remote_clicked(self,button_id):
        doc_id  = self.button_data[button_id]
        doc = self.model.locate_object( lambda obj: obj.document_id == doc_id)

        if doc.reference and \
            not confirmationBox(_("Confirmation for deleting reference template"),
                                _("You're about to delete a reference template document. These documents are used by some parts of this program. Deleting them will break those parts. So you should immediately upload another template with the same reference. OK to proceed ?")):
                return

        elif not confirmationBox(_("Deleting a template"),
                                 _("Are you sure you want to remove {}").format(doc.filename)):
            return

        try:
            self.model.delete_document(doc)
            self._apply_pending_changes()
        except Exception as ex:
            showErrorBox(_("There was an error while deleting a document"),ex=ex)


    def _add_file(self, full_path_client):

        """ Adds a file to the templates. First it is uploaded
        and then it is added to the list of files.
        """

        if self._test_file_access(full_path_client):

            progress_bar = make_progress(_("Uploading"),100)
            def progress_tracker(percent):
                progress_bar.setValue( int(percent))

            try:
                doc_id = upload_template( full_path_client, progress_tracker, 0)

            except Exception as exc:
                progress_bar.close()
                showErrorBox(_("There was a problem while uploading the file {} to the server").format(os.path.basename(full_path_client)), ex=exc, object_name="file_upload_error")
                return

            self.refresh_templates_list()


    def _replace_file(self, full_path_client, document):

        if self._test_file_access(full_path_client):

            progress_bar = make_progress(_("Replacing"),100)
            def progress_tracker(percent):
                progress_bar.setValue( int(percent))

            try:
                doc_id = upload_template(full_path_client, progress_tracker, document.document_id)
                self.refresh_templates_list()

            except Exception as exc:
                progress_bar.close()
                showErrorBox(_("There was a problem while uploading the file to the server"), ex=exc, object_name="file_upload_error")
                return


    #def dropEvent(self, e):
    def animated_drop_event_handler(self, e, selected_drop_zone):

        if len(e.mimeData().urls()) > 1:
            return super(TemplatesCollectionWidgetDialog,self).dropEvent(e)
        elif len(e.mimeData().urls()) == 1:
            # Pay attention, the vent we got here is tied to the view, not to this
            # widget. So mapToGlobal has to be called on the view too...
            z = self.view.viewport().mapFromGlobal( self.view.mapToGlobal(e.pos()))
            drop_row = self.view.rowAt(z.y())

            # mainlog.debug("mapped y {} -> {} -> {}".format(e.pos().y(), glo.y(), z.y()))
            mainlog.debug( "row at {} for y {}".format(drop_row,z.y()))

            full_path_client = e.mimeData().urls()[0].toString().replace('file:///','')

            if drop_row == -1:
                mainlog.debug("Adding a template on drag/drop event")
                self._add_file(full_path_client)
            else:
                document = self.model.object_at(drop_row)
                # button_id = self.model.index( drop_row,0 ).data(Qt.UserRole + 1)
                # doc_id, dummy_path, file_size, description = self.button_data[button_id]
                #
                mainlog.debug("Replacing {} with doc_id={}".format(full_path_client, document.document_id))

                if document.reference:

                    if not confirmationBox(_("Replacing a Horse reference document"),
                                           _("You're about to replace a reference document ({}, {}). "
                                             "This can potentially break the program. You should make "
                                             "a copy of the current version of that document before "
                                             "proceeding. Do you still want to go on ?").format(document.description, document.reference)):
                        return

                self._replace_file(full_path_client, document)
























# class OLDTemplatesCollectionWidget(QWidget):
#
#     @Slot(QModelIndex,QModelIndex)
#     def _data_edited2(self, top_left, bottom_right):
#         if self.track_edits:
#             mainlog.debug("Row edited {} {}".format(top_left.row(), bottom_right.row()))
#
#             document = self._model.object_at( top_left.row())
#             if document:
#                 try:
#                     documents_service.update_template_description(document.document_id, document.description, document.filename.strip(), document.reference)
#                 except Exception as ex:
#                     showErrorBox(_("There was an error while updating the information of the template document"),None,ex)
#         else:
#             mainlog.debug("self.track_edits false")
#
#     @Slot()
#     def _delete_remote_clicked(self,row_ndx):
#         document = self._model.object_at(row_ndx)
#
#         if document:
#
#             if document.reference:
#                 ynb = confirmationBox(_("Confirmation for deleting reference document"),
#                                       _("You're about to delete a reference template document. These documents are used by some parts of Horse. Deleting them will break those parts. So you should immediately upload another template with the same reference. OK to proceed ?"))
#
#                 if not ynb:
#                     return
#                 else:
#                     mainlog.debug("Destroying {}".format(document.reference))
#
#             try:
#                 remove_document(document.document_id)
#             except Exception as exc:
#                 showErrorBox(_("There was a problem while deleting the file from the server"), ex=exc, object_name="file_delete_error")
#                 return
#
#         self.refresh_templates_list()
#
#
#     @Slot()
#     def _save_a_copy_clicked(self,row_ndx):
#         document = self._model.object_at(row_ndx)
#
#         full_path_client = QFileDialog.getSaveFileName(self, _('Save a document'), document.filename , "")[0]
#         # The user might hit "cancel" !
#         if full_path_client:
#             new_path = self._download_document(document, full_path_client)
#
#             mainlog.debug(u"{} <- {}".format(new_path,full_path_client))
#             if new_path != full_path_client:
#                 os.rename(new_path, full_path_client)
#
#             open_a_file_on_os(new_path)
#
#
#     def _download_document(self,document, destination):
#
#         progress_bar = make_progress(_("Downloading"),100)
#         def progress_tracker(percent):
#             progress_bar.setValue( int(percent))
#
#         try:
#             path = download_document(document.document_id, progress_tracker, destination)
#             progress_bar.close()
#             return path
#         except Exception as exc:
#             progress_bar.close()
#             showErrorBox(_("There was a problem while downloading the file from the server"), ex=exc, object_name="file_download_error")
#
#
#
#     def _make_control_buttons(self, document, row_ndx):
#
#         mainlog.debug("_make_control_buttons : *********************************************************** ")
#
#         p_download = make_tool_button("appbar.page.download.png")
#         p_download.clicked.connect(self.signal_mapper_save_a_copy_button.map)
#         self.signal_mapper_save_a_copy_button.setMapping(p_download, row_ndx)
#         # self.view.setIndexWidget( self.model.index(self.model.rowCount()-1,2), p_download)
#
#         # if not document.reference:
#         #p = QPushButton()
#         p_delete = make_tool_button("appbar.page.delete.png")
#
#         if document.reference:
#             p_delete.setDisabled(True)
#         else:
#             # p.setText(_('Delete'))
#             p_delete.clicked.connect(self.signal_mapper_delete_button.map)
#             self.signal_mapper_delete_button.setMapping(p_delete, row_ndx)
#             #self.view.setIndexWidget( self.model.index(self.model.rowCount()-1,3), p_delete)
#
#         # A bit complicated, but that's the simplest way
#         # to tie an in-table button to some data
#         self.button_data[self.button_id] = document
#         self.button_id += 1
#
#
#         z = QWidget()
#         z.setObjectName("zeroBorder")
#         layout = QHBoxLayout()
#         layout.setSpacing(0)
#         layout.setContentsMargins(0,0,0,0)
#         # layout.addWidget(p_open)
#         layout.addWidget(p_download)
#         # if not document.reference:
#         layout.addWidget(p_delete)
#         # else:
#         #     layout.addStretch()
#         # z.setMinimumHeight(64)
#         layout.addStretch()
#
#         z.setLayout(layout)
#         return z
#
#     def _make_model_and_view(self):
#
#         proto = [TextLinePrototype('filename',_("File name"),editable=True,nullable=False,non_empty=True),
#                  TextLinePrototype('description',_("Description"),editable=True),
#                  TextLinePrototype('reference',_("Horse Ref."),editable=False),
#                  TextLinePrototype(None,_("Action"),editable=False)]
#
#         self._model = PrototypedModelView(proto, None)
#         self._view = PrototypedQuickView(proto,self,line_selection=False)
#         self._view.setModel(self._model)
#
#         self._view.horizontalHeader().setResizeMode(0, QHeaderView.Stretch)
#         self._view.horizontalHeader().setResizeMode(1, QHeaderView.Stretch)
#         self._view.horizontalHeader().setResizeMode(2, QHeaderView.Stretch)
#
#         self._model.dataChanged.connect(self._data_edited2)
#
#     def refresh_templates_list(self):
#
#         documents = sorted( list(documents_service.all_templates()),
#             key=lambda d:( ("B" if d.reference else "A")  + d.filename))
#
#         mainlog.debug("refresh_templates_list")
#         mainlog.debug(documents)
#
#         self._model.buildModelFromObjects(documents)
#
#         for i in range(len(documents)):
#             d = documents[i]
#             w = self._make_control_buttons(d,i)
#             self._view.setIndexWidget( self._model.index( i, self._model.columnCount()-1),
#                                        w)
#
#     # def refresh_templates_list(self):
#     #
#     #     documents = documents_service.all_templates()
#     #
#     #     self.refresh_templates_list()
#     #
#     #     self.model.removeRows(0, self.model.rowCount())
#     #
#     #     if documents:
#     #         for doc in sorted(list(documents),key=lambda d:( ("B" if d.reference else "A")  + d.filename)):
#     #             self._add_one_document( doc.filename, doc.template_document_id, doc.file_size, doc.description, doc.reference)
#     #
#     #     self.documents_changed = False
#     #
#     #     self.model.setHeaderData(0,Qt.Horizontal,_("Name"),Qt.DisplayRole)
#     #     self.model.setHeaderData(1,Qt.Horizontal,_("Description"),Qt.DisplayRole)
#     #     self.model.setHeaderData(2,Qt.Horizontal,_("Horse ref."),Qt.DisplayRole)
#     #     self.model.setHeaderData(3,Qt.Horizontal,"",Qt.DisplayRole) # Actions buttons
#
#
#
#
#     def __init__(self,parent=None):
#         super(TemplatesCollectionWidget,self).__init__(parent)
#
#         self._make_model_and_view()
#
#         self.documents_changed = False
#         self.track_edits = True
#
#         l = QVBoxLayout()
#
#         hb = QHBoxLayout()
#         hb.addWidget(QLabel(u"<h3>{}</h3>".format(_("Documents Templates"))))
#         pb = make_tool_button("appbar.page.upload.png")
#         pb.clicked.connect(self.add_document_dialog)
#         hb.addWidget(pb)
#
#         # I remove the double click because it must lead to a text edit
#         # rather than open file (in this template library)
#         # self.view.doubleClicked.connect(self._doubleClicked)
#
#         l.addLayout(hb)
#         l.addWidget(self._view)
#         self.setLayout(l)
#         self.setAcceptDrops(True)
#
#         # self.signal_mapper_open_button = QSignalMapper()
#         # self.signal_mapper_open_button.mapped.connect(self._open_clicked)
#         self.signal_mapper_delete_button = QSignalMapper()
#         self.signal_mapper_delete_button.mapped.connect(self._delete_remote_clicked)
#         self.signal_mapper_save_a_copy_button = QSignalMapper()
#         self.signal_mapper_save_a_copy_button.mapped.connect(self._save_a_copy_clicked)
#
#         self.button_data = dict()
#         self.button_id = 1
#
#
#     def _add_file(self, full_path_client):
#         mainlog.debug("template widget : _addfile ************************************************************")
#
#         """ Adds a file to the templates. First it is uploaded
#         and then it is added to the list of files.
#         """
#
#         file_size = 0
#         # Test the file access
#         try:
#             t = open(full_path_client,'rb')
#             t.close()
#
#             file_size = os.path.getsize(full_path_client)
#             if file_size == 0:
#                 raise Exception("Empty file ?")
#
#         except Exception as exc:
#             showErrorBox(_("Can't open the file located at {}").format(full_path_client), ex=exc, object_name="drag_drop_error")
#             return
#
#         progress_bar = make_progress(_("Uploading"),100)
#         def progress_tracker(percent):
#             progress_bar.setValue( int(percent))
#
#         try:
#             doc_id = upload_template( full_path_client, 0, progress_tracker)
#
#         except Exception as exc:
#             progress_bar.close()
#             showErrorBox(_("There was a problem while uploading the file to the server"), ex=exc, object_name="file_upload_error")
#             return
#
#         self.refresh_templates_list()
#
#     def dragEnterEvent(self, e):
#         # necessary to allow drop events...
#         e.acceptProposedAction()
#
#     def dropEvent(self, e):
#
#         z = self._view.viewport().mapFromGlobal( self.mapToGlobal(e.pos()))
#         drop_row = self._view.rowAt(z.y())
#
#         # mainlog.debug("mapped y {} -> {} -> {}".format(e.pos().y(), glo.y(), z.y()))
#         mainlog.debug( "row at " + str(drop_row))
#
#         full_path_client = e.mimeData().urls()[0].toString().replace('file:///','')
#
#         if drop_row == -1:
#             mainlog.debug("Adding a template")
#             self._add_file(full_path_client)
#         else:
#             document = self._model.object_at(drop_row)
#             # button_id = self.model.index( drop_row,0 ).data(Qt.UserRole + 1)
#             # doc_id, dummy_path, file_size, description = self.button_data[button_id]
#             #
#             mainlog.debug("Replacing {} with doc_id={}".format(full_path_client, document.document_id))
#
#
#             if document.reference:
#                 if not confirmationBox(_("Replacing a Horse reference document"),
#                                        _("You're about to replace an Horse reference document ({}, {}). "
#                                          "This can potentially break Horse. You should make "
#                                          "a copy of the current version of that document before "
#                                          "proceeding. Do you still want to go on ?").format(document.description, document.reference)):
#                     return
#
#             progress_bar = make_progress(_("Replacing"),100)
#             def progress_tracker(percent):
#                 progress_bar.setValue( int(percent))
#
#             try:
#                 doc_id = upload_template(full_path_client, document.document_id, progress_tracker)
#                 self.refresh_templates_list()
#
#             except Exception as exc:
#                 progress_bar.close()
#                 showErrorBox(_("There was a problem while uploading the file to the server"), ex=exc, object_name="file_upload_error")
#                 return
#


class TemplatesCollectionWidgetDialog(QDialog):
    def __init__(self,parent,doc_service):
        super(TemplatesCollectionWidgetDialog,self).__init__(parent)
        layout = QVBoxLayout()

        self.setWindowTitle(_("Templates library"))

        tw = TitleWidget(_("Templates library"),self)
        layout.addWidget(tw)
        l = QLabel(_("Here you can add or remove templates documents from the library. "
                     "If needed, you can change their name and add a description. "
                     "If you want to replace a reference document (one with a special "
                     "Horse reference, then simply drag and drop the document on "
                     "the appropriate row"))

        l.setWordWrap(True)
        layout.addWidget(l)

        self.widget = TemplatesCollectionWidget(self, doc_service)
        layout.addWidget(self.widget)


        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.Ok)
        self.buttons.accepted.connect(self.accept)
        layout.addWidget(self.buttons)

        self.setLayout(layout)
        place_dialog_on_screen(self,0.5,0.7)

if __name__ == "__main__":

    # from koi.doc_manager.documents_mapping import Document
    # d = Document()
    #
    # print(Document.__dict__)
    # print(d.__dict__)
    #
    # exit()

    app = QApplication(sys.argv)
    qss = open( os.path.join(resource_dir,"standard.qss"),"r")
    app.setStyleSheet(qss.read())
    qss.close()

    dialog = TemplatesCollectionWidgetDialog(parent=None, doc_service=None)
    dialog.widget.refresh_templates_list()
    dialog.exec_()
