import sys

from PySide.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide.QtGui import QAbstractItemView
from koi.qtableviewfixed import QTableView

from koi.gui.ComboDelegate import AutoComboDelegate, TextAreaTableDelegate

class PrototypedQuickView(QTableView):

    def __init__(self, prototype, parent, line_selection=True):
        super(PrototypedQuickView,self).__init__(parent)
        self.prototype = prototype

        # The prototype will say if the table's cells are editable or not

        # Not editable but don't dim the lines
        # self.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.verticalHeader().setVisible(False)

        if line_selection:
            self.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.setSelectionMode(QAbstractItemView.SingleSelection)


    def setModel(self,model):

        # Pay attention ! This ensures that the seleciotn model will be deleted
        # See QTableView.setModel() documentation for an explanation
        super(PrototypedQuickView,self).setModel(model)

        if model:
            self._setup_delegates()


    def rowsInsertedInModel(self,parent,start,end):
        # Pay attention, if one completely clears the model
        # then the view forgets that it has delegates set
        # for the columns. Therefore, if one adds rows again to
        # to the model then the delegates won't be set
        # at all => all the rows inserted won't display/edit
        # correctly

        if start == 0 and (end + 1) == self.model().rowCount():
            self._setup_delegates()

        self.resizeColumnsToContents()

    def _setup_delegates(self):

        i = 0
        for p in self.prototype:
            d = p.delegate()
            # mainlog.debug("_setup_delegates column {} -> delegate {}".format(i,d))
            self.setItemDelegateForColumn(i, d)

            # Pay attention, some delegates need additional setup
            # but since we're just using this table for view *only*

            if isinstance(d,AutoComboDelegate) or isinstance(d,TextAreaTableDelegate):
                d.set_table(self) # FIXME unclean

            i = i + 1


class PrototypedModelView(QAbstractTableModel):
    """ A simple model for prototyped objects.
    The model data are stored in the objects themselves (no additional data structure)
    Therefore this model is best suited to view objects (rather than editing them)
    It is a lighter version of the TrackingProxyModel
    """

    def __init__(self, prototype, parent):
        super(PrototypedModelView,self).__init__(parent)
        assert prototype

        self.prototype = prototype
        self._clear_data()

    def find_index(self, finder):
        for row in range(len(self.objects)):
            if finder(self.objects[row]):
                return self.index(row,0)
        return None

    def object_at(self, row_ndx):
        if 0 <= row_ndx < len(self.objects):
            return self.objects[row_ndx]
        else:
            return None


    def _clear_data(self):
        self.objects = []
        self.table_backgrounds = []

    def headerData(self,section,orientation,role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and section >= 0 and section < len(self.prototype) and role == Qt.DisplayRole:
            return self.prototype[section].title
        else:
            return None

    def parent(self):
        return QModelIndex()

    def index(self, row, column, parent = QModelIndex()):
        return self.createIndex(row, column)

    def rowCount(self,parent = None):
        return len(self.objects)

    def columnCount(self,parent = None):
        return len(self.prototype)

    def data(self, index, role):
        if index.row() < 0 or index.row() >= self.rowCount() or index.column() < 0 or index.column() >= self.columnCount():
            # print "TurboModel.data(). bad index {}".format(index.row())
            return None

        if role in (Qt.EditRole, Qt.DisplayRole):
            p = self.prototype[index.column()]

            if p.field:
                return str(getattr( self.objects[index.row()], p.field) or "")
            else:
                return ""

        elif role == Qt.BackgroundRole:
            return None
            return self.table_backgrounds[index.row()][index.column()]

        elif role == Qt.UserRole:
            p = self.prototype[index.column()]

            if p.field:
                return getattr( self.objects[index.row()], p.field)
            else:
                return None

        else:
            return None

    def flags(self, index):
        column = index.column()

        if 0 <= column < len(self.prototype):
            if self.prototype[column].is_editable:
                return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable

        return Qt.ItemIsSelectable | Qt.ItemIsEnabled

    def clear(self):
        if self.rowCount() > 0:
            self.beginRemoveRows(QModelIndex(),0,max(0,self.rowCount()-1))
            self._clear_data()
            self.endRemoveRows()

    def buildModelFromObjects(self,array):
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
            self.objects = array
            self.table_backgrounds = [None] * len(self.objects)
            self.endInsertRows()


    def setData(self, index, value, role):
        if role == Qt.UserRole:

            f = self.prototype[index.column()].field
            o = self.object_at(index.row())
            setattr(o,f,value)

            # mainlog.debug("set data(r={},c={},role={})".format(index.row(),index.column(),role))
            # FIXME need to extend the table if it is too small !
            self.dataChanged.emit(index,index)
            return True
        else:
            raise Exception("Can't work without UserRole")
