if __name__ == "__main__":
    import sys
    from PySide.QtGui import QApplication,QMainWindow

    from koi.base_logging import init_logging
    from koi.Configurator import init_i18n,load_configuration

    init_logging()
    init_i18n()
    load_configuration()

from PySide.QtGui import QWidget,QHBoxLayout,QHeaderView

from koi.gui.ProxyModel import IntegerNumberPrototype
from koi.gui.ProxyModel import TextLinePrototype
from koi.gui.PrototypedModelView import PrototypedModelView, PrototypedQuickView

class DeliverySlipViewWidget(QWidget):
    def __init__(self,parent=None):
        super(DeliverySlipViewWidget,self).__init__(parent)

        self.delivery_slip_part_proto = []
        # self.delivery_slip_part_proto.append( OrderPartDisplayPrototype('order_part',_('Part'), editable=False))
        self.delivery_slip_part_proto.append( TextLinePrototype('part_label',_('Part'), editable=False))
        self.delivery_slip_part_proto.append( TextLinePrototype('description',_('Description'), editable=False))
        self.delivery_slip_part_proto.append( IntegerNumberPrototype('quantity_out',_('Q. out'), editable=False))


        # self.controller_operation = PrototypeController(self,
        #                                                 self.delivery_slip_part_proto,
        #                                                 ProxyTableView(None,self.delivery_slip_part_proto))
        # # self.controller_operation.view.verticalHeader().hide()
        # self.controller_operation.setModel(TrackingProxyModel(self,self.delivery_slip_part_proto))


        self.model = PrototypedModelView(self.delivery_slip_part_proto, self)
        self.view = PrototypedQuickView(self.delivery_slip_part_proto, self)
        self.view.setModel(self.model)
        self.view.horizontalHeader().setResizeMode(QHeaderView.ResizeToContents) # Description column wide enough
        self.view.horizontalHeader().setResizeMode(1,QHeaderView.Stretch)
        self.view.verticalHeader().hide()

        layout = QHBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        # layout.addWidget(self.controller_operation.view)
        layout.addWidget(self.view)
        self.setLayout(layout)



    def set_delivery_slip_parts(self, parts):
        """ Fill with order part's data.
        Doesn't keep any reference to the order part.
        """

        if parts:
            self.model.buildModelFromObjects(parts)
        else:
            self.model.clear()

        ndx = self.model.index(0,0)
        self.view.setCurrentIndex(ndx)
        self.view.resizeRowsToContents()


if __name__ == "__main__":
    # from db_mapping import Employee
    # employee = dao.employee_dao.any()

    app = QApplication(sys.argv)

    window = QMainWindow()
    window.setMinimumSize(1024,768)
    widget = DeliverySlipViewWidget(window)
    window.setCentralWidget(widget)
    window.show()
    # presence.refresh_action()

    widget.set_order_part_id(10250)

    app.exec_()
