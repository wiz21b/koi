from PySide.QtGui import QColor
from PySide.QtCore import Qt,Signal,QAbstractTableModel,QModelIndex

from koi.base_logging import mainlog
from koi.gui.ProxyModel import TrackingProxyModel
from koi.gui.ProxyModel import IntegerNumberPrototype, FloatNumberPrototype, FutureDatePrototype,DurationPrototype,OperationDefinitionPrototype,TextAreaPrototype
from koi.datalayer.database_session import session
from koi.dao import dao
from koi.OperationDefinitionsCache import operation_definition_cache

#Qt,Slot,QModelIndex,QAbstractTableModel,, QPoint

# PrototypeController,IntegerNumberPrototype,FloatNumberPrototype,TextLinePrototype,DurationPrototype,OperationDefinitionPrototype,PrototypedTableView,ProxyTableView,OrderPartDisplayPrototype,TextAreaPrototype,TableViewSignaledEvents,TimestampPrototype,FutureDatePrototype


def order_part_row_protect(obj,row):
    # I don't access the object to prevent SQLA from reopening connections
    return obj is not None and row[5] > 0

def operation_row_protect(obj,row):
    # I don't access the object to prevent SQLA from reopening connections
    return obj is not None and row[4] > 0

def is_value_editable(ndx):
    op = ndx.model().index( ndx.row(),0).data(Qt.UserRole)
    if op:
        # op = operation_definition_cache.opdef_by_id(op)
        # By construction of the cache, all the operation definition
        # are at least "on operation", thus we don't have to test
        # for that.
        if not operation_definition_cache.imputable_by_id(op):
            return Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled
        else:
            return Qt.ItemIsSelectable | Qt.ItemIsEnabled
    else:
        return Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled

def are_planned_hours_editable(ndx):
    op = ndx.model().index( ndx.row(),0).data(Qt.UserRole)
    if op:
        #  op = operation_definition_cache.opdef_by_id(op)
        if operation_definition_cache.imputable_by_id(op):
            return Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled
        else:
            return Qt.ItemIsSelectable | Qt.ItemIsEnabled
    else:
        return Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled






class TModel(TrackingProxyModel):
    submodelCreated = Signal(QAbstractTableModel)

    def __init__(self,parent,prototype):
        super(TModel,self).__init__(parent,prototype)
        self.submodels = []


    def _makeSubModel(self,ndx):
        """ Make or load an "opertaion" model tied to a given order part (ndx-th row) """
        new_model = self.makeSubModel(ndx)
        self.submodelCreated.emit(new_model)
        return new_model

    def submodel(self,ndx):
        if ndx < 0 or ndx >= len(self.submodels):
            raise Exception("The index {} is out of range, maximum is {}".format(ndx, len(self.submodels)-1))

        if self.submodels[ndx] == None:
            self.submodels[ndx] = self._makeSubModel(ndx)

        return self.submodels[ndx] # but this model is not populated !!!!


    def insertRows(self, row, count, parentIndex):
        # mainlog.debug("TModel.insertRows : count={}".format(count))

        if row < 0:
            row = 0

        if self.rowCount() != len(self.objects):
            raise Exception(" insertRows() {} {}".format(self.rowCount(), len(self.objects)))

        if row < len(self.submodels):
            mainlog.debug("TModel.insertRows : len(submodels)={}".format(len(self.submodels)))
            for i in range(count):
                self.submodels.insert(row,None) # self._makeBlankOperationModel())
                mainlog.debug("TModel.insertRows : inserted at {} for the {}th time".format(row,i))
            mainlog.debug("TModel.insertRows : after insert, len(submodels)={}".format(len(self.submodels)))
        else:
            mainlog.debug("TModel.insertRows : appending, len(submodels)={}".format(len(self.submodels)))

            for i in range(count):
                self.submodels.append(None)

        r = super(TModel,self).insertRows(row, count, parentIndex)

        mainlog.debug("TModel = inserted {} rows at {}, model.rowCount = {} / current size is {} / len(submodels) {}".format(count,row,self.rowCount(), len(self.objects), len(self.submodels)))

        if self.rowCount() != len(self.objects):
            raise Exception(" insertRows() {} {}".format(self.rowCount(), len(self.objects)))

        return r




    def has_submodels(self):
        return len(self.submodels) > 0


    def removeRows(self, row, count, parentIndex = QModelIndex()):
        # mainlog.debug("TModel.removeRows() = removing {} rows from then {}th row, table row count = {} / object count = {}".format(count, row, self.rowCount(), len(self.objects)))

        if self.rowCount() != len(self.objects):
            raise Exception("TModel.removeRows() {} {}".format(self.rowCount(), len(self.objects)))

        r = super(TModel,self).removeRows(row, count, parentIndex = QModelIndex())

        if r:
            # mainlog.debug("TModel = removed rows, row count = {} / current size is {}".format(self.rowCount(), len(self.objects)))
            if count > 0 and row >= 0:
                del(self.submodels[row:(row+count)])
            # mainlog.debug("TModel.removeRows() = calling super")

        if self.rowCount() != len(self.objects):
            raise Exception("TModel.removeRows() {} {}".format(self.rowCount(), len(self.objects)))

        return r

    def _buildModelFromObjects(self,objects):
        # mainlog.debug("TModel._buildModelFromObjects calling parent")
        super(TModel,self)._buildModelFromObjects(objects)

        if objects is None or objects == []: # FIXME objects should never be None
            # mainlog.debug("TModel._buildModelFromObjects / no objects")
            self.submodels = [None] # Keep it in sync with parent class
        else:
            # mainlog.debug("TModel._buildModelFromObjects with {} objects".format(len(objects)))
            self.submodels = [None]*len(objects)

        # mainlog.debug("TModel._buildModelFromObjects at this point : {} / {}".format(self.rowCount(), len(self.submodels)))

        if self.rowCount() != len(self.objects):
            raise Exception(" _buildModelFromObjects() {} {}".format(self.rowCount(), len(self.objects)))


    def swap_row(self,ndx,ndx2):
        if self.rowCount() != len(self.objects):
            raise Exception(" swap_row() {} {}".format(self.rowCount(), len(self.objects)))

        if super(TModel,self).swap_row(ndx,ndx2):

            o = self.submodels[ndx2]
            self.submodels[ndx2] = self.submodels[ndx]
            self.submodels[ndx] = o

            if self.rowCount() != len(self.objects):
                raise Exception(" swap_row() {} {}".format(self.rowCount(), len(self.objects)))

            return True
        else:
            return False





class OperationsModel(TrackingProxyModel):


    def __init__(self,parent,prototype):
        super(OperationsModel,self).__init__(parent,prototype)
        self.set_row_protect_func(operation_row_protect)

        self.note = None
        self.quantity_to_produce = 1

    def update_quantity_to_produce(self,new_qty):
        self.quantity_to_produce = new_qty

        # Force refresh of the column (i.e. recomputation of coloured warnings)
        # indices are topLeft, BottomRight
        self.dataChanged.emit( self.index(0,4), self.index(self.rowCount()-1,4))

    def text_color_eval(self,index):
        row = index.row()

        # 3 = hourss/unit; 4=done hours
        if row >= 0 and index.column() == 4:
            # mainlog.debug("text_color_eval planned_hours={}".format(self.index(row,3).data(Qt.UserRole)))
            total_hours_to_do = self.quantity_to_produce * self.index(row,3).data(Qt.UserRole)
            # mainlog.debug("text_color_eval total_hours_to_do={}".format(total_hours_to_do))
            total_done_hours = self.index(row,4).data(Qt.UserRole)

            if total_done_hours > total_hours_to_do :
                return QColor(255,0,0)

        return None


    def set_on_order_part(self,order_part_id):
        # Reload the part (in case it was put out of the session)
        part = dao.order_part_dao.find_by_id(order_part_id)

        if part.production_file and len(part.production_file) >= 1:
            self._buildModelFromObjects(part.production_file[0].operations)
            self.note = part.production_file[0].note
            for op in part.production_file[0].operations:
                session().expunge(op)

        session().commit()


class OrderPartModel(TModel):

    def __init__(self,parent):
        self.prototype = [ TextAreaPrototype('description',_('Description'),nullable=False),
                           IntegerNumberPrototype('qty',_('Qty'),nullable=True),
                           IntegerNumberPrototype('tex2',_('Q.Ex'),editable=False),
                           FutureDatePrototype('deadline',_('D/line'),nullable=True),
                           DurationPrototype('total_estimated_time',_('Total\nH.Pl'),nullable=True,editable=False),
                           DurationPrototype('total_hours',_('Total\nH.Done'),editable=False),
                           FloatNumberPrototype('sell_price',_('Sell\nprice'),editable=True) ]

        self.sub_prototype = [ OperationDefinitionPrototype('operation_definition_id',_('Op.'),operation_definition_cache.all_on_order_part()),
                      TextAreaPrototype('description',_('Description'),nullable=True),
                      FloatNumberPrototype('value',_('Value'),nullable=True,editable=is_value_editable),
                      DurationPrototype('planned_hours',_('Planned time'),nullable=True,editable=are_planned_hours_editable),
                      DurationPrototype('done_hours',_('Imputations'),editable=False) ]

        super(OrderPartModel,self).__init__(parent,self.prototype)
        self.set_row_protect_func(order_part_row_protect)

    def makeSubModel(self,ndx):
        """ Make or load an "opertaion" model tied to a given order part (ndx-th row) """

        part = self.objects[ndx]

        op_model =  OperationsModel(None,self.sub_prototype)
        op_model.update_quantity_to_produce(self.data( self.index(ndx,1), Qt.UserRole))

        if part and part.order_part_id:
            op_model.set_on_order_part(part.order_part_id)

        return op_model

    def headerData(self,section,orientation,role):
        # For some reason, returning only DisplayRole is mandatory
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            if section < len(self.objects) and section >= 0 and self.objects[section]:
                return self.objects[section].label
            else:
                return "/"
        else:
            return None

    def index_for_order_part_id(self,order_part_id):
        mainlog.debug("Locating order_part_id {}".format(order_part_id))
        row = 0
        for o in self.objects:
            if o.order_part_id == order_part_id:
                mainlog.debug("Located order_part_id {} on row {}".format(order_part_id,row))
                return self.index(row,0)
            else:
                row = row + 1
        return self.index(0,0)
