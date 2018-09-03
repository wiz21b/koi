from inspect import isfunction
from PySide.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal
from koi.datalayer.types import DBObjectActionTypes
from koi.Configurator import mainlog


class ObjectModel(QAbstractTableModel):
    """ To each row of the model corresponds one and only one object.
    When new rows are inserted, new objects are created using a factory
    If objects have more fields than those displayed (see prototypes), those
    fields will be left untouched.
    """

    row_protected = Signal()

    def __init__(self,parent,prototypes, blank_object_factory):
        super(ObjectModel,self).__init__(parent)
        self._prototypes = prototypes
        self._col_to_attr = [ getattr( p, 'field', None) for p in self._prototypes]
        self._blank_object_factory = blank_object_factory

        # Provide a default array, the user of this class might provide
        # his own array (see reset_objects so set it up)

        self._objects = []
        self._clear_dynamic_data()

        self._table_width = len(self._col_to_attr)
        self.highligthted_line = None
        # self.edit_mask= None

        self.row_protect_func = None

    def headerData(self, section : int, orientation : Qt.Orientation, role : int = Qt.DisplayRole):
        # This seems like the most sensible way of making headers.
        # Without that, I need to create special header view, etc.
        if orientation == Qt.Orientation.Horizontal and role == Qt.DisplayRole:
            return self._prototypes[section].title

    def read_only_objects(self):
        return self._objects

    def _clear_dynamic_data(self):

        # We don't clear the objects array because it might be managed
        # outside of this class

        # Normally, at any time,
        # the intersection of deleted, changed and created objects set is empty

        # Objects that were passed to this model and deleted during edit.
        self._deleted_objects = []

        # Objects that were passed to this model and modified during edit.
        self._changed_objects = set()

        # Objects that were create during edit
        self._created_objects = set()



        if self._prototypes:
            self.set_edit_mask(self._prototypes)


    def set_row_protect_func(self,f):
        self.row_protect_func = f

    def _buildModelFromObjects(self, objects):
        self.reset_objects(objects, None)

    def change_highlighted_line(self, line_no):
        self.highligthted_line = line_no

    def model_to_objects(self, factory, defaults = None):
        # FIXME Replace this with export_objects...
        return self.export_objects_as_actions(defaults)

    def export_objects( self, row_min=None, row_max=None):
        """ The objects returned are those of the model. If you change
        them you must refresh the model !!! Pay attention not to modify
        deleted objects (it'd be useless).
        """

        if (row_min and row_max is None) or (row_min is None and row_max):
            raise ValueError("row_min and row_max must be set together or not at all")

        if row_min is None and row_max is None:
            return self._objects
        else:
            return self._objects[row_min:row_max+1]

    def export_objects_as_actions(self, defaults = None):
        """ The objects returned are those of the model. If you change
        them you must refresh the model !!! Pay attention not to modify
        deleted objects (it'd be useless).
        """

        results = []
        ndx = 0

        for obj in self._objects:

            # The way this is built ensure that an object that is reported
            # TO_CREATE won't show up in TO_UPDATE.

            if obj in self._created_objects:
                # We discard "empty" objects, we make the assumption that
                # empty == not filled in by the user
                for field in self._col_to_attr:
                    if getattr( obj, field) != None : # False is not None !
                        results.append( (DBObjectActionTypes.TO_CREATE,obj,ndx))
                        break # Stop on first non None
            elif obj in self._changed_objects:
                results.append( (DBObjectActionTypes.TO_UPDATE,obj,ndx))
            else:
                # We store unchanged to leave a trace for indexing/position/ordering
                # Note that the delted object ar not part of the self._objects
                results.append( (DBObjectActionTypes.UNCHANGED,obj,ndx))

            ndx += 1

        for obj in self._deleted_objects:
            results.append( (DBObjectActionTypes.TO_DELETE,obj,ndx))

        return results



    def isIndexValid(self,ndx):
        return ndx.isValid() and ndx.row() >= 0 and ndx.row() < self.rowCount() and ndx.column() >= 0 and ndx.column() < self.columnCount()

    def index(self, row : int, column : int, parent = QModelIndex()):
        # When one reads Qt's doc, nothing indicates that an
        # index is invalid if it points outside the model.
        # So I add that behaviour.

        # mainlog.debug(row)
        # mainlog.debug(column)
        # mainlog.debug(self.columnCount())
        # mainlog.debug(self.rowCount())

        if row < self.rowCount() and column < self.columnCount():
            # if row/col are negative, this will create an invalid
            # index anyway.
            return self.createIndex(row, column)
        else:
            return self.createIndex(-1, -1)

    def rowCount(self,parent = None):
        # print "rowCount {}".format(len(self.table))
        return len(self._objects)

    def columnCount(self,parent = None):
        return self._table_width

        # Note sure this is the right way to compute columns
        # however, things tend to work better when i do that...

        # if self.rowCount() == 0:
        #     # Make sure we behave as Qt (FIXME double check)
        #     return 0
        # else:
        #     return self._table_width

    def text_color_eval(self,index : QModelIndex):
        """

        :param index: model index
        :return: QColor
        """
        pass

    def background_color_eval(self,index):
        if index.row() == self.highligthted_line:
            return QBrush(QColor(210, 255, 210))
        else:
            return None

    def locate_object(self, func):
        for obj in self._objects:
            if func(obj):
                return obj

        return None

    def remove_object(self, obj):
        if obj not in self._objects:
            raise Exception("The object is not in the model")

        ndx = self._objects.index(obj)
        self.removeRow(ndx)

    def signal_object_change(self, obj):
        """ When an object proxied by this model changes, the model can't know
        it (there's no change listening mechanism right now, it'd a bit too hard
        to write and the ROI would be low).

        So if you change an object, call this
        method. All the row of the object will be marked as changed, this allows
        us to forget about the field or fields that have actually changed.

        :param obj:
        :return:
        """
        row = self._objects.index(obj)
        self._changed_objects.add(obj)
        self.dataChanged.emit(self.index(row,0), self.index(row, self.columnCount()-1))

    def object_at(self,ndx):
        """ The object on the same row as the passed index.
        The index can be either an int (in this case it's a row number)
        or a QModelIndex (and in this case, we'll use ndx.row())
        This never ever returns None.

        :param ndx : an int or a QModelIndex
        """

        if isinstance(ndx,QModelIndex):
            if ndx.isValid() and ndx.row() >= 0 and ndx.row() < len(self._objects):
                return self._objects[ndx.row()]
            else:
                raise Exception("Invalid QModelIndex")
        else:
            if ndx >= 0 and ndx < len(self._objects):
                return self._objects[ndx]
            else:
                raise Exception("Invalid index {}".format(ndx))


    def data(self, index, role):
        # Role 32 == UserRole
        # 8 = BackgroundRole
        # mainlog.debug("data(r={},c={},role={})".format(index.row(),index.column(),role))

        if index.row() < 0 or index.row() >= len(self._objects):
            # mainlog.warning("Index row ({}) out of bounds".format(index.row()))
            return None

        elif index.column() < 0 or index.column() >= self._table_width:
            # mainlog.warning("Index column ({}) out of bounds".format(index.column()))
            return None

        if role == Qt.DisplayRole:
            # Pay attention, my current hypothesis is this.
            # Since this model is made to work *only* with prototypes
            # (delegates) then all the display must be made through them
            # therefore, requesting the Qt.DisplayRole should never happen.
            # However, this happens : Qt does it. And when it does, it
            # seems it forgets the delegates (or my delegates are not
            # set at the right time...). When I use "unicode" to convert
            # objects to displayable string, then Python calls __repr__
            # But the problem is that 1/ this repr is not exactly
            # what I want to display 2/ Qt ends up using it to compute
            # the size of the cell => although my delegate is, in the end
            # called to display the data, the cell size was not computed
            # according to the delegate's display but to the __repr__
            # one. And this breaks everything. So I decide to return
            # None. I tried to be clean with the setup of the delegate
            # That is, makes sure the delegates are in place before
            # the model changes (so that if Qt wants to recompute
            # the size of the cells, it finds the proper delegate to
            # do so and doesn't revert to this data(Qt.DisplayRole...
            # function) but so far I've failed...

            # print type(self.table[index.row()][index.column()])
            return None
            # return str(self.table[index.row()][index.column()]) # this doesn't leak
        elif role == Qt.UserRole:
            attr_name = self._col_to_attr[index.column()]
            # mainlog.debug("col:{} attr:{}".format(index.column(), attr_name))
            if attr_name:
                return getattr( self._objects[index.row()], attr_name)
            else:
                return None
        elif role == Qt.TextColorRole:
            return self.text_color_eval(index)
        elif role == Qt.BackgroundRole:
            # mainlog.debug("calling self.background_color_eval(index)")
            return self.background_color_eval(index)
        else:
            return None

    def refreshData(self,index):
        self.dataChanged.emit(index,index)

    def setData(self, index, value, role):
        if role == Qt.UserRole:
            # FIXME need to extend the table if it is too small !
            setattr( self._objects[index.row()], self._col_to_attr[index.column()], value)
            self._changed_objects.add(self._objects[index.row()])
            self.dataChanged.emit(index,index)
            return True
        else:
            raise Exception("Can't work without Qt.UserRole")

    def flags(self, index):
        # mainlog.debug("flags(r={},c={}) mask={}".format(index.row(),index.column(),self.edit_mask))

        if self.edit_mask:
            # mainlog.debug("edit_mask")
            if index.column() >= len(self.edit_mask):
                mainlog.warning("Index out of range ({} but max is {})".format(index.column(),len(self.edit_mask)))
                return Qt.ItemIsEnabled

            m = self.edit_mask[index.column()]
            if isfunction(m): # hasattr(m,'__call__'):
                return m(index)
            else:
                return m
        else:
            return Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled

    def clear(self):
        if self.rowCount() > 0:
            self.removeRows(0,self.rowCount())


    def append_objects(self, objects):
        self.insert_objects( self.rowCount(), objects)

    def insert_objects(self, row_ndx, objects, parentIndex = QModelIndex()):
        """ Insert new objects in the model. We assume those objects
        will *need* to be saved in the database (unless deleted first)
        """

        if not objects or len(objects) == 0:
            return

        if row_ndx < 0:
            row_ndx = 0

        self.beginInsertRows(parentIndex,row_ndx,row_ndx + len(objects) - 1)

        for obj in objects:

            assert obj, "If you need blank objects, use insertRows"
            if obj in self._objects:
                mainlog.error("Trying to add the same object twice into object model.")

            self._created_objects.add(obj)

            # mainlog.debug("insert_objects: inserting object {} at row {}".format(obj, row_ndx))
            self._objects.insert(row_ndx,obj)
            row_ndx += 1

        self.endInsertRows()


    def insertRows(self, row, count, parentIndex = QModelIndex()):
        if count > 0:
            blanks = []
            for i in range(count):
                o = self._blank_object_factory()
                assert o is not None, "Objects model works on objects, even blank objects"
                blanks.append(o)

            self.insert_objects( row, blanks)

        return True



    def removeRows(self, row, count, parentIndex = QModelIndex()):

        if count <= 0 or row < 0:
            return False

        if self.are_rows_protected(row, count):
            self.row_protected.emit()
            return False

        self.beginRemoveRows(parentIndex,row,row+count-1)

        for o in self._objects[row:(row+count)]:
            if o not in self._created_objects:
                # If we created the object, then it makes no sense
                # to delete them (see report as actions)
                self._deleted_objects.append(o)
            else:
                self._created_objects.remove(o)

        del(self._objects[row:(row+count)])

        self.endRemoveRows()

        return True




    def set_edit_mask(self,prototype):
        self.edit_mask = []
        for k in prototype:
            if k.is_editable == True:
                # mainlog.debug("set_edit_mask: {} editable".format(k))
                self.edit_mask.append(Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            elif isfunction(k.is_editable): # hasattr(k.is_editable,'__call__'):
                self.edit_mask.append(k.is_editable)
            else:
                # mainlog.debug("set_edit_mask: {} NOT editable".format(k))
                self.edit_mask.append(Qt.ItemIsEnabled | Qt.ItemIsSelectable )


    def reset_objects(self,objects,prototype=None): # FIXME useless parameter
        """ Sets the object in the model. The object will NOT be marked
        as new objects. They're seen as the "base" list. From that list,
        the code will mark new object as such.

        All previous objects' update memory is lost.

        :param objects:
        :param prototype:
        :return:
        """

        self.beginResetModel()

        self._clear_dynamic_data()

        if objects is not None:
            self._objects = objects
        else:
            self._objects = []

        self.endResetModel()



    def are_rows_protected(self,row, count = 1):
        if count <= 0 or row < 0 or (self.rowCount() > 0 and row >= self.rowCount()):
            raise Exception("Invalid row/count : {}/{}. Must be < {}".format(row,count,self.rowCount()))

        if self.row_protect_func:
            for i in range(row,row+count):
                if self.row_protect_func(self._objects[i]):
                    return True

        return False



    def swap_row(self,ndx,ndx2):
        if ndx >= 0 and ndx2 >= 0 and ndx < self.rowCount() and ndx2 < self.rowCount() and ndx != ndx2:

            mainlog.debug("ObjectModel : swap_row {} {}".format(ndx, ndx2))

            p = QModelIndex()
            if self.beginMoveRows(p, ndx, ndx,
                                  p, ndx2):

                mainlog.debug("ObjectModel : swap_row Done")

                # FIXME use rowsAboutToBeMoved

                o = self._objects[ndx2]
                self._objects[ndx2] = self._objects[ndx]
                self._objects[ndx] = o

                # The order change is a also change !
                self._changed_objects.add(self._objects[ndx])
                self._changed_objects.add(self._objects[ndx2])

                self.endMoveRows()


                self.dataChanged.emit(self.index(ndx,0),self.index(ndx,self.columnCount()-1))
                self.dataChanged.emit(self.index(ndx2,0),self.index(ndx2,self.columnCount()-1))

                return True
            else:
                mainlog.debug("beginMoveRows didn't want to work :-(")
        return False



    # def validate(self):
    #     """ Validate the table. Returns a dict of errors (line number -> list of errors) if any or None. """

    #     errors = dict()

    #     for ir in range(self.rowCount()):

    #         row = []
    #         row_empty = True

    #         for ic in range(len(self.prototype)):
    #             item = self.data( self.index(ir,ic), Qt.UserRole)
    #             p = self.prototype[ic]
    #             # print p

    #             # Figure out if the table cell we're looking
    #             # at was filled in by the user.
    #             # A row is deemed "empty" if all of its cells
    #             # are either None or not editable...

    #             if item is not None and p.is_editable:
    #                 row_empty = False

    #             row.append(item)

    #         if not row_empty:

    #             # The row appear to be changed so we validate
    #             # its content

    #             row_errors = []
    #             for ic in range(len(self.prototype)):
    #                 p = self.prototype[ic]
    #                 # mainlog.debug("validate row:{}/col:{} : proto={}".format(ir,ic,p))

    #                 if p.is_editable: # only validate columns that are editable
    #                     validation_result = p.validate(row[ic]) # FIXME BUG use row[ic] or the edit widget in the prototype

    #                     if validation_result is not True:
    #                         # mainlog.debug(u"validate result {}".format(validation_result).encode(sys.getdefaultencoding(),'ignore'))
    #                         row_errors.append(validation_result)

    #             if len(row_errors) > 0:
    #                 errors[ir] = row_errors

    #     if len(errors) > 0:
    #         # mainlog.debug(u"validate result. errors are {}".format(errors).encode(sys.getdefaultencoding(),'ignore'))
    #         return errors
    #     else:
    #         return None



    def validate( self):

        errors = []
        active_prototypes = [p for p in self._prototypes if p.is_editable]

        for row_ndx in range(len(self._objects)):
            obj = self._objects[row_ndx]

            row_errors = []
            for p in active_prototypes:
                validation_result = p.validate( getattr( obj, p.field))
                if validation_result is not True:
                    row_errors.append(validation_result)

            if len(row_errors) > 0:
                errors[row_ndx] = row_errors

        if len(errors) > 0:
            # mainlog.debug(u"validate result. errors are {}".format(errors).encode(sys.getdefaultencoding(),'ignore'))
            return errors
        else:
            return None


    def isRowEmpty(self,row_ndx):
        """ A row is empty if the user has not typed anything in the
        editable cells (which is slightly different than saying
        that all its cells are "None") """

        for ic in range(len(self._prototypes)):
            item = self.data( self.index(row_ndx,ic), Qt.UserRole)
            p = self._prototypes[ic]
            if item is not None and p.is_editable:
                return False
        return True

    def extract_rows(self,begin,end):
        """ Extracts some rows from the table.

        The view is not taken into
        account. Therefore, if a column is inivisble, then it might be in the
        extracted data...

        :param begin: first row (inclusive)
        :param end: last row (inclusive)
        :return:
        """

        if begin < 0 or begin >= self.rowCount():
            raise Exception("Begin index out of range ({})".format(begin))

        if end < 0 or end >= self.rowCount():
            raise Exception("End index out of range ({})".format(begin))

        if begin > end:
            raise Exception("Begin index ({}) after end index ({}) ".format(begin,end))

        # We give a copy of the table, not the table
        # itself. That's defensive programming.

        # print "extract_rows : {} to {}".format(begin,end)
        t = []

        for y in range(begin,end+1):
            t.append( [ getattr( self._objects[y], self._col_to_attr[x])
                        for x in range(self._table_width) ] )

        return t

    def extract_all_rows(self):
        return self.extract_rows(0,self.rowCount()-1)



    def insert_data(self,base_row_ndx,data):
        """ Insert a set of rows at row_ndx.
        Each row is an array, so data is a 2D array
        """

        # mainlog.debug("ObjectModel.insert_data at row {} ".format(base_row_ndx))

        if not data or len(data) == 0:
            return

        if base_row_ndx < 0:
            base_row_ndx = 0

        objects = []

        for row_ndx in range(len(data)):
            o = self._blank_object_factory()

            for col_ndx in range(self._table_width):
                proto = self._prototypes[col_ndx]
                if proto.is_editable:
                    setattr( o, proto.field, data[row_ndx][col_ndx])

            objects.append(o)

        # mainlog.debug("ObjectModel.insert_data inserting {} objects at row {} ".format(len(objects), base_row_ndx))
        self.insert_objects( base_row_ndx, objects)
