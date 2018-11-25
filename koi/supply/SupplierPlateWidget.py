from koi.base_logging import mainlog
from PySide.QtCore import Qt
from PySide.QtGui import QWidget,QHBoxLayout,QVBoxLayout,QLabel,QFrame
from Configurator import configuration


class SupplierPlateWidget(QFrame):
    def __init__(self,parent):
        super(SupplierPlateWidget,self).__init__(parent)

        # w.setMaximumWidth(600)
        # w.setMinimumWidth(600)
        self.setStyleSheet("background:white")
        self.setFrameShape(QFrame.Panel)
        self.setFrameShadow(QFrame.Sunken)


        self.supplier_name_label = QLabel()
        self.supplier_name_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.supplier_name_label.setObjectName("HorseCustomerPlateTitle")
        self.supplier_address1_label = QLabel()
        self.supplier_address2_label = QLabel()
        self.supplier_phone_label = QLabel(_("Phone : /"))
        self.supplier_phone2_label = QLabel()
        self.supplier_fax_label = QLabel(_("Fax : /"))
        self.supplier_notes_label = QLabel("")

        supplier_data_layout = QVBoxLayout()
        # supplier_data_layout.addWidget(self.supplier_address1_label)
        # supplier_data_layout.addWidget(self.supplier_address2_label)
        supplier_data_layout.addWidget(self.supplier_phone_label)
        supplier_data_layout.addWidget(self.supplier_phone2_label)
        supplier_data_layout.addWidget(self.supplier_fax_label)
        supplier_data_layout.addStretch()

        supplier_plate_hlayout = QHBoxLayout()
        self.supplier_notes_label.setAlignment(Qt.AlignTop)
        supplier_plate_hlayout.addLayout(supplier_data_layout)
        supplier_plate_hlayout.addWidget(self.supplier_notes_label)

        supplier_plate_layout = QVBoxLayout()
        supplier_plate_layout.addWidget(self.supplier_name_label)
        supplier_plate_layout.addLayout(supplier_plate_hlayout)

        self.setLayout(supplier_plate_layout)
        self.supplier_id = None

    def refresh_supplier(self):
        if self.supplier_id:
            global dao
            supplier = dao.supplier_dao.find_by_id(self.supplier_id)
            self.set_supplier(supplier)

    def set_supplier(self,supplier):
        if supplier:
            self.supplier_id = supplier.supplier_id

            self.supplier_name_label.setText(supplier.fullname)
            # self.supplier_address1_label.setText(supplier.address1)
            # self.supplier_address2_label.setText(supplier.address2)
            self.supplier_phone_label.setText(supplier.phone)
            self.supplier_phone2_label.setText(supplier.phone2)
            if supplier.fax:
                self.supplier_fax_label.setText(_("F: {}").format(supplier.fax))
            else:
                self.supplier_fax_label.setText("")

            self.supplier_notes_label.setText(supplier.notes)
        else:
            self.supplier_id = None

            self.supplier_name_label.setText("")
            # self.supplier_address1_label.setText("")
            # self.supplier_address2_label.setText("")
            self.supplier_phone_label.setText("")
            self.supplier_phone2_label.setText("")
            self.supplier_fax_label.setText("")
            self.supplier_notes_label.setText("")
