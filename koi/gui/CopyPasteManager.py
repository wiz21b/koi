from koi.base_logging import mainlog


from PySide.QtCore import Qt
from PySide.QtGui import QTableView, QApplication

from koi.translators import remove_crlf, decimal_point, format_csv

class CopyPasteManager(object):
    def __init__(self):
        self.parts_id = None
        self.operations = None

    def copy_parts_by_id(self, parts_id):
        self.parts_id = parts_id

    def copy_operations(self, operations):
        """ operations stored here are meant be duck type compatible
        with their definition in the database mapping.
        """
        self.operations = operations


    def _selected_rows(self, indices):
        ndx = set()
        for i in indices:
            ndx.add( i.row())

        return sorted( [i for i in ndx])


    def _line_to_csv(self, items):
        s = u"\t".join(["\"{}\"".format( (x or "").replace("\n"," ").replace("\t","").replace("\"","''") ) for x in items])
        s += u"\n"
        return s


    def copy_table_view_to_csv(self, view : QTableView, special_headers = [], special_formatters = dict()):
        """ Copies the selected rows in the view to the clipboard

        Will use the Horse delegates if any (because they display information in a different way).

        :param view:
        :return:
        """

        rows_ndx = self._selected_rows( view.selectedIndexes())

        model = view.model()
        visible_cols = []
        for c in range( model.columnCount()):
            if not view.isColumnHidden(c):
                visible_cols.append(c)

        s = ""

        if special_headers:
            h = special_headers
        else:
            h = []
            mh = view.horizontalHeader().model()
            for col in visible_cols:
                h.append(  mh.headerData(col, Qt.Horizontal, Qt.DisplayRole))

        s += self._line_to_csv(h)

        for row in rows_ndx:

            r = []
            for col in visible_cols:

                model_index = model.index(row, col)

                if col in special_formatters:
                    formatted = special_formatters[col](model_index)

                    if type(formatted) in (list,tuple):
                        r += list( formatted)
                    elif type(formatted) == float:
                        r.append( format_csv(formatted))
                    else:
                        r.append( str( formatted))
                else:
                    d = view.itemDelegateForColumn(col)
                    if d:
                        displayed_data = d.get_displayed_data(model_index)
                    else:
                        displayed_data = model_index.data(Qt.DisplayRole)

                    if displayed_data and type(model_index.data(Qt.UserRole)) == float:
                        # FIXME This a hack to convert float representations to
                        # the convert decimal format for CSV pasting. Rmemeber that MS Excel
                        # might have different decimal point, based on the locale...
                        # This is sub optimal because a float might not always be represented
                        # as a float... But it's not the case for now => not a problem.
                        r.append( displayed_data.replace(u".",decimal_point))
                    else:
                        r.append( displayed_data)

            s += self._line_to_csv(r)

        mainlog.debug("copy_table_view: {}".format(s))
        QApplication.clipboard().setText(s)

copy_paste_manager = CopyPasteManager()
