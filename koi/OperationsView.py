if __name__ == "__main__":
    import sys
    from PySide.QtGui import QApplication,QMainWindow

    from koi.base_logging import mainlog,init_logging
    from koi.Configurator import init_i18n,load_configuration

    init_logging()
    init_i18n()
    load_configuration()

from PySide.QtGui import QWidget,QHBoxLayout,QHeaderView,QAction,QKeySequence,QAbstractItemView
from PySide.QtCore import Qt,Slot

from koi.dao import dao
from koi.Configurator import mainlog
from koi.gui.ProxyModel import OperationDefinitionPrototype,TextAreaPrototype,FloatNumberPrototype,DurationPrototype
from koi.gui.CopyPasteManager import copy_paste_manager
from koi.gui.PrototypedModelView import PrototypedModelView, PrototypedQuickView
from koi.OperationDefinitionsCache import operation_definition_cache


class OperationsOverviewWidget(QWidget):
    def __init__(self,parent=None):
        super(OperationsOverviewWidget,self).__init__(parent)

        self.operation_prototype = []
        self.operation_prototype.append( OperationDefinitionPrototype('operation_definition_id',_('Op.'),operation_definition_cache.all_on_order_part(), editable=False))
        self.operation_prototype.append( TextAreaPrototype('description',_('Description'),nullable=True,editable=False))
        self.operation_prototype.append( FloatNumberPrototype('value',_('Value'),nullable=True,editable=False))
        self.operation_prototype.append( DurationPrototype('planned_hours',_('Planned time'),nullable=True,editable=False))
        # operation_prototype.append( DurationPrototype('t_reel',_('Used time'),nullable=False,editable=False))
        self.operation_prototype.append( DurationPrototype('done_hours',_('Imputations'),editable=False))
        # operation_prototype.append( TextLinePrototype('note',_('Note'),editable=True,nullable=True,hidden=True))


        self.model = PrototypedModelView(self.operation_prototype,self)
        self.view = PrototypedQuickView(self.operation_prototype,self)
        self.view.setModel(self.model)
        self.view.verticalHeader().hide()
        self.view.horizontalHeader().setResizeMode(QHeaderView.ResizeToContents) # Description column wide enough
        self.view.horizontalHeader().setResizeMode(1,QHeaderView.Stretch)
        self.view.setWordWrap(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.ExtendedSelection)

        # self.controller_operation = PrototypeController(self,
        #                                                 self.operation_prototype,
        #                                                 ProxyTableView(None,self.operation_prototype))
        # self.controller_operation.view.verticalHeader().hide()
        # # self.controller_operation.setModel(TrackingProxyModel(None,operation_prototype))
        # self.controller_operation.setModel(TrackingProxyModel(self,self.operation_prototype))

        # self.controller_operation.view.horizontalHeader().setResizeMode(QHeaderView.ResizeToContents) # Description column wide enough
        # self.controller_operation.view.horizontalHeader().setResizeMode(1,QHeaderView.Stretch)

        # self.controller_operation.view.setSelectionBehavior(QAbstractItemView.SelectRows)

        layout = QHBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.view)
        self.setLayout(layout)

        self.copy_operations_action = QAction(_("Copy operations"),self.view)
        self.copy_operations_action.triggered.connect( self.copy_operations_slot)
        self.copy_operations_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_C))
        self.copy_operations_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.view.addAction(self.copy_operations_action)


    def fill_order_part(self, order_part_id):
        """ Fill with order part's data.
        Doesn't keep any reference to the order part.
        """

        if order_part_id:
            mainlog.debug("fill_order_part : triggered !")
            operations = dao.operation_dao.find_by_order_part_id_frozen(order_part_id)
            mainlog.debug("fill_order_part : build model !")
            self.model.buildModelFromObjects(operations)
            mainlog.debug("fill_order_part : build model complete !")
            self.view.verticalHeader().setResizeMode(QHeaderView.ResizeToContents)
        else:
            self.model.clear()

        ndx = self.model.index(0,0)
        mainlog.debug("fill_order_part : setCurrentIndex !")
        self.view.setCurrentIndex(ndx)
        mainlog.debug("fill_order_part : setCurrentIndex done!")

    @Slot()
    def copy_operations_slot(self):
        mainlog.debug("copy_operations_slot")

        view = self.view
        model = self.model

        # Collect the rows indices

        rows = set()
        for ndx in view.selectedIndexes():
            if ndx.row() >= 0:
                rows.add(ndx.row())

        # There are no guarantee on the selectedIndexes order
        rows = sorted(list(rows))


        # Copy for elsewhere in Horse

        if len(rows):
            operations = []
            for row_ndx in rows:
                operation = model.object_at(row_ndx)
                mainlog.debug(operation)
                operations.append(operation)
            copy_paste_manager.copy_operations(operations)
        else:
            # If nothing to copy then we leave the copy/paste clipboard
            # as it is. So one could paste again what he copied before.
            pass




if __name__ == "__main__":
    # from db_mapping import Employee
    # employee = dao.employee_dao.any()

    app = QApplication(sys.argv)

    window = QMainWindow()
    window.setMinimumSize(1024,768)
    widget = OperationsOverviewWidget(window)
    window.setCentralWidget(widget)
    window.show()
    # presence.refresh_action()

    widget.set_order_part_id(10250)

    app.exec_()
