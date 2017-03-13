import sys

from urllib.request import build_opener,ProxyHandler,HTTPHandler,HTTPSHandler
from http.client import HTTPConnection
from io import StringIO

from PySide.QtCore import Qt, Slot,QModelIndex
from PySide.QtGui import QVBoxLayout, QDialogButtonBox,QDialog,QLabel, QTableView,QStandardItemModel,QStandardItem, \
    QHeaderView, QAbstractItemView

from koi.Configurator import mainlog,configuration


if __name__ == "__main__":
    import sys
    from PySide.QtGui import QApplication

    from koi.base_logging import init_logging
    from koi.Configurator import init_i18n,load_configuration,resource_dir
    init_logging()
    init_i18n()
    load_configuration()

    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session
    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)

from koi.doc_manager.documents_service import documents_service


import os


class TemplateSelectDialog(QDialog):


    def refresh_templates_list(self):

        documents = documents_service.all_templates()

        self.model.removeRows(0, self.model.rowCount())

        if documents:
            for doc in sorted(list(documents),key=lambda d:d.filename):
                self._add_one_document( doc.filename, doc.template_document_id, doc.file_size, doc.description)


    def __init__(self,parent=None):
        super(TemplateSelectDialog,self).__init__(parent)

        self.setWindowTitle(_("Select a template"))

        self.template_id = []

        self.model = QStandardItemModel()
        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.verticalHeader().setVisible(False)
        self.view.horizontalHeader().setVisible(False)
        self.view.setMinimumSize(500,200)
        self.view.setShowGrid(True)
        self.view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)

        l = QVBoxLayout()

        l.addWidget(QLabel(_("Please select one or more template.")))
        self.view.doubleClicked.connect(self._doubleClicked)

        l.addWidget(QLabel(u"<h3>{}</h3>".format(_("Documents Templates"))))
        l.addWidget(self.view)

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.StandardButton.Cancel)
        self.buttons.addButton( QDialogButtonBox.Ok)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        l.addWidget(self.buttons)

        self.setLayout(l)

    def _add_one_document(self, file_name, doc_id, file_size, description):
        """ Adds a document to the list
        """

        # file_name is either an absolute path or just a file name
        # If it is an absolute path, then the file is expected
        # to exist locally (at it absolute path location of course).
        # If not, then the file is expected to be a remote file
        # and shall be downloaded before opening.

        mainlog.debug(u"{} {} {} {}".format(file_name, doc_id, file_size, description))
        short_name = file_name
        if os.path.isabs(file_name):
            short_name = os.path.basename(file_name)
            if not os.path.isfile(file_name):
                raise Exception(u"The file {} doesn't exist".format(file_name))

        items = [QStandardItem(short_name)]
        items.append( QStandardItem(description))

        self.model.appendRow(items)
        self.model.setData(self.model.index( self.model.rowCount()-1,0 ), doc_id, Qt.UserRole + 1)

        self.view.horizontalHeader().setResizeMode(0, QHeaderView.Stretch)
        self.view.horizontalHeader().setResizeMode(1, QHeaderView.Stretch)
        self.view.resizeRowsToContents()


    @Slot()
    def accept(self):
        selected_rows = self.view.selectionModel().selectedRows()
        if selected_rows:
            self.template_id = []
            for row in selected_rows:
                ndx_row = row.row()
                self.template_id.append( self.model.data( self.model.index( ndx_row,0 ), Qt.UserRole + 1))
        else:
            self.template_id = []
        return super(TemplateSelectDialog,self).accept()

    @Slot()
    def reject(self):
        return super(TemplateSelectDialog,self).reject()

    @Slot(QModelIndex)
    def _doubleClicked(self, ndx):
        self.accept()


if __name__ == "__main__":


    # download_document(upload_document(r"c:\temp\vd.ico"))
    # exit()

    # 000100847802




    app = QApplication(sys.argv)
    qss = open( os.path.join(resource_dir,"standard.qss"),"r")
    app.setStyleSheet(qss.read())
    qss.close()

    dialog = TemplateSelectDialog(None)
    dialog.refresh_templates_list()
    dialog.exec_()

    mainlog.debug("TemplateId = {}".format(dialog.template_id))
