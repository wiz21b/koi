from PySide.QtCore import Qt,QAbstractTableModel,QModelIndex

class QuickComboModel(QAbstractTableModel):
    def __init__(self,parent):
        super(QuickComboModel,self).__init__(parent)
        self.table = []
        self.references = []

    def parent(self):
        return QModelIndex()

    def index(self, row, column, parent = QModelIndex()):
        return self.createIndex(row, column)

    def rowCount(self,parent = None):
        return len(self.table)

    def columnCount(self,parent = None):
        if self.rowCount() == 0:
            # print "columnCount 0"
            return 0
        else:
            # print "columnCount {}".format(len(self.table[0]))
            return 1

    def data(self, index, role):
        if index.row() < 0 or index.row() >= len(self.table):
            # print "TurboModel.data(). bad index {}".format(index.row())
            return None

        if role in (Qt.EditRole, Qt.DisplayRole):
            return self.table[index.row()]
        elif role == Qt.UserRole:
            # print("QuickModel : picking {}".format(type(self.references[index.row()])))
            return self.references[index.row()]
        else:
            return None

    def flags(self, index):
      return Qt.ItemIsSelectable | Qt.ItemIsEnabled

    def row_of(self,ref):
        return self.references.index(ref)

    def clear(self):
        self.beginRemoveRows(QModelIndex(),0,self.rowCount()-1)
        self.beginRemoveColumns(QModelIndex(),0,0)
        self.table = []
        self.references = []
        self.endRemoveColumns()
        self.endRemoveRows()

    def buildModelFromArray(self,array,references=None):
        # Pay attention, this is tricky.
        # I have the impression that Qt's views are really picky about this
        # so, if you remove all the rows of a table, it doesn't mean
        # that you also removed all the columns (from the QTableView standpoint)
        # Therefore, to signal that we've cleared the model, we must
        # delete rows *and* columns.

        if len(self.table) > 0:
            self.clear()

        if array is not None:
            self.beginInsertRows(QModelIndex(),0,len(array)-1)
            self.beginInsertColumns(QModelIndex(),0,0)
            self.table = array
            self.references = references
            self.endInsertColumns()
            self.endInsertRows()
