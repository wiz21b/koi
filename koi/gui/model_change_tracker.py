from PySide.QtCore import QObject,Slot

class ModelChangeTracker(QObject):
    """ NEVER TESTED !!!

    Tracks whenever an object has been changed,removed, created.
    In that case the given signal is emitted.

    Note that if a row is added then removed, the model has actually
    not changed. This signal will not see that situation, so you'll
    see a change. """

    def __init__(self, model, signal_on_change):
        assert model
        assert signal_on_change

        self._signal_on_change = signal_on_change

        model.dataChanged.connect(self._data_changed)
        model.rowsInserted.connect(self._rows_changed)
        model.rowsRemoved.connect(self._rows_changed)
        model.rowsMoved.connect(self._row_moved)

    @Slot()
    def _row_moved(self, parent, start, end, destination, row):
        self._signal_on_change.emit()

    @Slot()
    def _data_changed(self,a,b):
        self._signal_on_change.emit()

    @Slot()
    def _row_changed(self,p,first,last):
        self._signal_on_change.emit()
