if __name__ == "__main__":
    import sys
    from PySide.QtGui import QApplication,QMainWindow

    from koi.base_logging import init_logging
    from koi.Configurator import init_i18n,load_configuration, configuration
    init_logging()
    init_i18n()
    load_configuration()

    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session
    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)

from PySide.QtCore import Qt
from PySide.QtGui import QWidget,QTableView,QStandardItemModel,QVBoxLayout,QLineEdit
from PySide.QtGui import QSortFilterProxyModel

from koi.translators import text_search_normalize


class FilteringModel(QSortFilterProxyModel):
    def __init__(self,parent):
        super(FilteringModel, self).__init__(parent)

        # The current filtering string
        self._filter_string = None

        # This filter will mark the filtered rows with a False boolean
        # Those marks are stored in the self._filter
        self._filter = None

        # The filtering will occur on a pre-indexed version of the
        # source data. So dynamic filtering is out of question.

        self._ndx_data = []

    def setIndexData(self,ndx_data):
        self._ndx_data = ndx_data

        if self._filter:
            self.setFilterFixedString(self._filter_string)

        self.invalidateFilter()

    def setFilterFixedString(self,s):
        if not s:
            # Empty string must disable filtering
            self._filter_string = None
            self._filter = None

        else:
            self._filter_string = text_search_normalize(s)

            max_row = max(len(self._ndx_data), self.rowCount())
            if not self._filter or len(self._filter) < max_row:
                self._filter = [False] * max_row

            # Filtering is done here so that filterAcceptsRow can be made
            # super fast

            for i in range(len(self._ndx_data)):
                self._filter[i] = self._filter_string in self._ndx_data[i]

        self.invalidateFilter()

    def filterAcceptsRow(self, sourceRow, sourceParent):
        # FIXME Can be optimized
        return (self._filter is None) or \
            (0 <= sourceRow < len( self._filter)) and self._filter[sourceRow]


class FilteredTableExample(QWidget):
    def __init__(self,parent):
        super(FilteredTable,self).__init__(parent)

        self.model = QStandardItemModel(600,600)
        for i in range(self.model.rowCount()):
            for j in range(self.model.columnCount()):
                self.model.setData(self.model.index(i,j), str(i*j),Qt.DisplayRole)


        self.m = FilteringModel(self)
        self.m.setSourceModel(self.model)

        d = ['a']*300 + ['b'] * 200 + ['c']*99 + ['d']
        self.m.setIndexData(d)


        t = QTableView(self)
        t.setModel(self.m)

        self.line_in = QLineEdit(self)
        self.line_in.textChanged.connect(self.m.setFilterFixedString)

        l = QVBoxLayout()
        l.addWidget(self.line_in)
        l.addWidget(t)
        self.setLayout(l)


if __name__ == "__main__":

    app = QApplication(sys.argv)
    mw = QMainWindow()

    # widget = EditCustomerDialog(None)
    # widget = EditEmployeeDialog(None,dao)
    widget = FilteredTableExample(None)
    mw.setCentralWidget(widget)
    mw.show()

    app.exec_()
