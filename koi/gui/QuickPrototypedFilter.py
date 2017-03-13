from PySide.QtCore import Signal,Slot,QModelIndex
from PySide.QtGui import QVBoxLayout,QLineEdit,QWidget,QItemSelectionModel
from koi.gui.PrototypedModelView import PrototypedQuickView,PrototypedModelView
from koi.gui.MetaFormDialog import FilterLineEdit
from koi.gui.FilteringModel import FilteringModel

class QuickPrototypedFilter(QWidget):

    selected_object_changed = Signal(object) # passes an object

    @Slot()
    def _focus_on_list(self):
        """ When the user hits the down key on the filter, we transfer
        the focus to the filtered list
        """
        self.list_view.setFocus()
        self.list_view.selectionModel().setCurrentIndex(self.list_view.model().index(0,0), QItemSelectionModel.ClearAndSelect)

    @Slot(str)
    def _filter_changed(self,s):
        self.list_model_filtered.setFilterFixedString(s)
        self.list_view.selectionModel().setCurrentIndex(self.list_view.model().index(0,0), QItemSelectionModel.ClearAndSelect)

    @Slot(QModelIndex,QModelIndex)
    def _selected_item_changed(self, current, previous):

        # The test below avoids some recursion. It's a bit more clever
        # than it looks. What happens is this. The user modify
        # some data then ask to change the edited object (in the left list)
        # Doing so it triggers this method. The program then save (if
        # necessary). But that save may trigger a reorganisation of the
        # list. So what the user has selected may be at a different
        # index than the "current" one we received as a parameter
        # of this method. To account for that we actually reselect
        # the item in the table. And this trigger a recursion we avoid
        # here. FIXME there is a recursion but the way we avoid
        # it is not 100% satisfactory, we should use a "semaphore"
        # for that.


        if current.isValid() and current.row() >= 0 and \
           current.row() != previous.row():

            ndx = self.list_model_filtered.mapToSource(self.list_model_filtered.index(current.row(),0))
            self.last_selected_object = self.list_model.object_at(ndx.row())

            self.selected_object_changed.emit(self.last_selected_object)


    def set_data(self,objs,index_builder):
        self.list_model.buildModelFromObjects(objs)
        self.list_model_filtered.setIndexData([index_builder(x) for x in objs])
        self.list_view.setCurrentIndex( self.list_view.model().index(0,0))

    def __init__(self,table_prototype,parent):
        super(QuickPrototypedFilter,self).__init__(parent)

        self.list_model = PrototypedModelView(table_prototype, self)

        self.list_model_filtered = FilteringModel(self)
        self.list_model_filtered.setSourceModel(self.list_model)

        self.line_in = FilterLineEdit()
        self.line_in.key_down.connect(self._focus_on_list)
        self.line_in.textChanged.connect(self._filter_changed)

        self.list_view = PrototypedQuickView(table_prototype, self)
        self.list_view.setTabKeyNavigation(False)
        self.list_view.horizontalHeader().hide()
        self.list_view.verticalHeader().hide()
        self.list_view.horizontalHeader().setStretchLastSection(True)

        self.list_view.setModel(self.list_model_filtered)

        vlayout = QVBoxLayout()
        vlayout.setContentsMargins(0,0,0,0)
        vlayout.addWidget(self.line_in)
        vlayout.addWidget(self.list_view)
        self.setLayout(vlayout)

        self.list_view.selectionModel().currentChanged.connect(self._selected_item_changed) # FIXME Clear ownership issue

        self.last_selected_object = None
        self.line_in.setFocus()
        QWidget.setTabOrder(self.line_in, self.list_view)
