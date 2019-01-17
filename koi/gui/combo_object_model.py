from PySide.QtCore import Qt,QModelIndex,QAbstractTableModel

class ObjectComboModel(QAbstractTableModel):
    """A model that will dispay only one field (named field_name) or
    function evaluation from each of the object that it manages.
    """

    def __init__(self,parent,field_name_or_func):
        super(ObjectComboModel,self).__init__(parent)
        self._objects = []

        if type(field_name_or_func) == str:
            self._func = lambda obj: getattr( obj, field_name_or_func)
        else:
            self._func = field_name_or_func

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
            return self._func( self._objects[index.row()]) # getattr( self._objects[index.row()], self._field_name)
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
