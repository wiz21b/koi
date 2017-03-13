from PySide.QtCore import Qt, QAbstractTableModel, QModelIndex


class PrototypedModelView(QAbstractTableModel):

    def __init__(self, prototype, parent):
        super(PrototypedModelView,self).__init__(parent)
        self.prototype = prototype
        self.clear()

    def headerData(self,section,orientation,role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and section >= 0 and section < len(prototype) and role == Qt.DisplayRole:
            return prototype[section].title
        else:
            return None

    def parent(self):
        return QModelIndex()

    def index(self, row, column, parent = QModelIndex()):
        return self.createIndex(row, column)

    def rowCount(self,parent = None):
        return len(self.objects)

    def columnCount(self,parent = None):
        return len(prototype)

    def data(self, index, role):
        if index.row() < 0 or index.row() >= self.rowCount() or index.column() < 0 or index.column() >= self.columnCount():
            # print "TurboModel.data(). bad index {}".format(index.row())
            return None

        if role in (Qt.EditRole, Qt.DisplayRole):
            field = self.prototype(index.column()).field
            return str(getattr( objects[index.row()], field))

        elif role == Qt.BackgroundRole:
            return self.table_backgrounds[index.row()][index.column()]

        elif role == Qt.UserRole:
            field = self.prototype(index.column()).field
            return getattr( objects[index.row()], field)

        else:
            return None

    def flags(self, index):
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled

    def clear(self):
        if self.rowCount() == 0:
            return

        self.beginRemoveRows(QModelIndex(),0,max(0,self.rowCount()-1))
        self.beginRemoveColumns(QModelIndex(),0,max(0,self.columnCount()-1))
        self.objects = []
        self.table_backgrounds = []
        self.endRemoveColumns()
        self.endRemoveRows()

    def buildModelFromArray(self,array):
        # Pay attention, this is tricky.
        # I have the impression that Qt's views are really picky about this
        # so, if you remove all the rows of a table, it doesn't mean
        # that you also removed all the columns (from the QTableView standpoint)
        # Therefore, to signal that we've cleared the model, we must
        # delete rows *and* columns.

        self.clear()

        # Be very carefull not to beginInsert if you actually
        # don't insert anything. This makes Qt crazy.

        if array:
            self.beginInsertRows(QModelIndex(),0,len(array)-1)
            self.beginInsertColumns(QModelIndex(),0,8-1)

            self.objects = array

            self.table_backgrounds = [None] * len(array)
            
            self.endInsertColumns()
            self.endInsertRows()




