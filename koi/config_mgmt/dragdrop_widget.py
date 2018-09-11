import platform
import os.path
from PySide.QtCore import Qt,Signal
from PySide.QtGui import QDragEnterEvent, QDragEnterEvent,QDragMoveEvent,QWidget,QVBoxLayout

class DragDropWidget(QWidget):

    filesDropped = Signal( list ) # A list of pairs. a pair is (full path to file, filename)

    def __init__( self, parent : QWidget, wrapped_widget : QWidget, accept_multiple_files = True):
        # This widget will wrap the wrapped widget in an invisible way.
        super(DragDropWidget,self).__init__(parent)
        self.setContentsMargins(0,0,0,0)
        self._layout = QVBoxLayout()
        self._layout.setContentsMargins(0,0,0,0)
        self.setLayout( self._layout)
        self._layout.addWidget( wrapped_widget)
        self.setAcceptDrops(True)
        self._accept_multiple_files = accept_multiple_files

    def dragEnterEvent(self, e : QDragEnterEvent):
        """ Only accept what looks like a file drop action
        :param e:
        :return:
        """

        if e.mimeData() and e.mimeData().hasUrls() and e.mimeData().urls()[0].toString().startswith("file://") and e.proposedAction() == Qt.DropAction.CopyAction:

            # Attention ! The actual drop area is smaller
            # than the dragEnter area !

            l = len( e.mimeData().urls())
            if (l == 1 and self._accept_multiple_files == False) or ( l >= 1 and self._accept_multiple_files):
                e.acceptProposedAction()
                e.accept()
                return

        e.ignore()


    def dragMoveEvent(self, e: QDragMoveEvent):
        e.accept()

    def dragLeaveEvent(self, e):
        e.accept()

    def dropEvent(self, e):

        paths = []
        for url in e.mimeData().urls():
            if platform.system() == "Windows":
                full_path_client = url.toString().replace('file:///','')
            else:
                full_path_client = url.toString().replace('file://','')

            filename = os.path.split( full_path_client)[-1]
            paths.append( (full_path_client, filename) )

        self.filesDropped.emit( paths)
        e.accept()
