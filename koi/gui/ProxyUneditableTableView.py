from koi.base_logging import mainlog
from PySide.QtGui import QTableView, QStandardItemModel, QHeaderView, QAbstractItemView
from PySide.QtCore import Qt


class ProxyUneditableTableView(QTableView):
    def _setup_delegates(self,prototype):
        i = 0
        for p in prototype:
            d = p.delegate()
            self.setItemDelegateForColumn(i, d)

            # Pay attention, some delegates need additional setup
            # but since we're just using this table for view *only*
            # we don't set those up (AutoComboDelegate, TextAreaTableDelegate)

            i = i + 1


    def _setup_horizontal_header(self, prototype):
        if self.model():
            i = 0
            for p in prototype:
                self.model().setHeaderData(i, Qt.Orientation.Horizontal, p.title)
                i = i + 1

        self.horizontalHeader().setResizeMode(QHeaderView.ResizeToContents)


    def rowsInsertedInModel(self,parent,start,end):
        # Pay attention, if one completely clears the model
        # then the view forgets that it has delegates set
        # for the columns. Therefore, if one adds rows again to
        # to the model then the delegates won't be set
        # at all => all the rows inserted won't display/edit
        # correctly

        if start == 0 and (end + 1) == self.model().rowCount():
            self._setup_delegates(self.prototype)

        self.resizeColumnsToContents()


    def setModel(self,model):

        # Pay attention ! This ensures that the seleciotn model will be deleted
        # See QTableView.setModel() documentation for an explanation
        super(ProxyUneditableTableView,self).setModel(model)

        if model:
            self._setup_horizontal_header(self.prototype)
            self._setup_delegates(self.prototype)

            # Although this table is for viewing a model only,
            # the model can of course change outside of the view

            # FIXME This is not right. Setting several times the
            # same model will connect it several time and we know
            # PySide doesn't handle multiple commits very well.
            model.rowsInserted.connect( self.rowsInsertedInModel)


    def __init__(self,prototype,parent=None):
        super(ProxyUneditableTableView,self).__init__(parent)

        self.prototype = prototype

        # Not editable but don't dim the lines
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
