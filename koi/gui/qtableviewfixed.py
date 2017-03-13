from PySide.QtGui import QTableView

class QTableView(QTableView):
    def __init__(self,parent=None):
        super(QTableView,self).__init__(parent)
        self._selection_model = None

    def setModel(self,model):
        super(QTableView,self).setModel(model)
        self._selection_model = super(QTableView,self).selectionModel()

    def selectionModel(self):
        return self._selection_model
