from PySide.QtCore import Qt
from PySide.QtGui import QSizePolicy,QCursor
from PySide.QtGui import QWidget,QHBoxLayout,QVBoxLayout,QLabel,QFrame

from koi.gui.AutoHideLabel import AutoHideLabel
from koi.gui.PopupWidget import PopupWidget


class ContactDataPlateWidget(QWidget):

    def _make_layout(self):
        self.customer_name_label = AutoHideLabel()
        self.customer_name_label.setObjectName("HorseCustomerPlateTitle")
        self.customer_address1_label = AutoHideLabel()
        self.customer_address2_label = AutoHideLabel()
        self.customer_phone_label = AutoHideLabel()
        self.customer_phone2_label = AutoHideLabel()
        self.customer_fax_label = AutoHideLabel()
        self.customer_notes_label = AutoHideLabel()


        contact_data_frame = QFrame()
        contact_data_layout = QVBoxLayout()
        # contact_data_layout.setContentsMargins(2,0,2,0)
        contact_data_layout.addWidget(self.customer_phone_label)
        contact_data_layout.addWidget(self.customer_phone2_label)
        contact_data_layout.addWidget(self.customer_fax_label)
        contact_data_layout.addStretch()
        contact_data_frame.setLayout(contact_data_layout)

        self.address_data_frame = QFrame()
        self.address_data_frame.setObjectName("leftBorderFrame")
        self.address_data_frame.setStyleSheet("#leftBorderFrame { border-left: 1px solid black; }")
        address_data_layout = QVBoxLayout()
        # address_data_layout.setContentsMargins(2,0,2,0)
        address_data_layout.addWidget(self.customer_address1_label)
        address_data_layout.addWidget(self.customer_address2_label)
        address_data_layout.addStretch()
        self.address_data_frame.setLayout(address_data_layout)

        self.note_frame = QFrame()
        self.note_frame.setObjectName("topBorderFrame")
        self.note_frame.setStyleSheet("#topBorderFrame { border-top: 1px solid black; }")
        layout = QVBoxLayout()
        # layout.setContentsMargins(2,0,2,0)
        self.customer_notes_label.setAlignment(Qt.AlignTop)
        layout.addWidget(self.customer_notes_label)
        layout.addStretch()
        self.note_frame.setLayout(layout)

        data1_layout = QHBoxLayout()
        data1_layout.addWidget(contact_data_frame)
        data1_layout.addWidget(self.address_data_frame)
        data1_layout.addStretch()

        data_layout = QVBoxLayout()
        data_layout.addWidget(self.customer_name_label)
        sep = QFrame()
        sep.setFrameStyle(QFrame.HLine)
        data_layout.addWidget(sep)
        data_layout.addLayout(data1_layout)
        data_layout.addWidget(self.note_frame)
        data_layout.setStretch(0,0)
        data_layout.setStretch(1,1)

        self.setLayout(data_layout)

        # top_frame = QFrame()
        # top_frame.setFrameShape(QFrame.NoFrame)
        # top_frame.setMinimumSize(300,100)
        # top_frame.setLayout(data_layout)

        # scroll_area = QScrollArea()
        # scroll_area.setWidget(top_frame)
        # scroll_area.setWidgetResizable(True)


        # self.setStyleSheet("background:white")
        # self.setFrameShape(QFrame.Panel)
        # self.setFrameShadow(QFrame.Sunken)

        self.setMinimumSize(300,80)
        self.setMaximumSize(600,400)
        self.setSizePolicy(QSizePolicy.MinimumExpanding,QSizePolicy.MinimumExpanding)


    def __init__(self,parent):
        super(ContactDataPlateWidget,self).__init__(parent)

        self._make_layout()
        self.customer_id = None


    def _clear_data(self):
        self.customer_name_label.setText("")
        self.customer_address1_label.setText("")
        self.customer_address2_label.setText("")
        self.customer_phone_label.setText("")
        self.customer_phone2_label.setText("")
        self.customer_fax_label.setText("")
        self.customer_notes_label.setText("")


    def _set_data(self,data):
        self.customer_name_label.setText(data.fullname)
        self.address_data_frame.setHidden(not data.address1 and not data.address2)

        self.customer_address1_label.setText(data.address1)
        self.customer_address2_label.setText(data.address2)

        if data.phone:
            self.customer_phone_label.setText(_("P: {}").format(data.phone))
        else:
            self.customer_phone_label.setText("")

        if data.phone2:
            self.customer_phone2_label.setText(_("P: {}").format(data.phone2))
        else:
            self.customer_phone2_label.setText("")

        if data.fax:
            self.customer_fax_label.setText(_("F: {}").format(data.fax))
        else:
            self.customer_fax_label.setText("")

        self.note_frame.setHidden(not data.notes)
        self.customer_notes_label.setText(data.notes)




class CustomerContactDataWidget(ContactDataPlateWidget):
    def __init__(self,parent=None):
        super(CustomerContactDataWidget,self).__init__(parent)
        self.customer_id = None

    def refresh_customer(self):
        if self.customer_id:
            global dao
            customer = dao.customer_dao.find_by_id(self.customer_id)
            self.set_customer(customer)

    def set_contact_data(self,customer):
        if customer:
            self.customer_id = customer.customer_id
            self._set_data(customer)
        else:
            self.customer_id = None
            self._clear_data()


class SupplierContactDataWidget(ContactDataPlateWidget):
    def __init__(self,parent=None):
        super(SupplierContactDataWidget,self).__init__(parent)
        self.supplier_id = None

    def refresh_supplier(self):
        if self.supplier_id:
            global dao
            supplier = dao.customer_dao.find_by_id(self.supplier_id)
            self.set_supplier(supplier)

    def set_contact_data(self,supplier):
        if supplier:
            self.supplier_id = supplier.supplier_id
            self._set_data(supplier)
        else:
            self.supplier_id = None
            self._clear_data()


class PoppingContactDataPlateWidget(QLabel):

    def leaveEvent(self,event):
        r = self.edit_panel.geometry()
        # Tested this, but it doesn't work : if self.edit_panel.underMouse() == False:
        if not self.edit_panel.rect().contains(self.edit_panel.mapFromGlobal(QCursor.pos())):
            self.edit_panel.hide()

        return super(PoppingContactDataPlateWidget,self).leaveEvent(event)

    def enterEvent(self,event):

        # pop up the contact data
        s = self.edit_panel.sizeHint()
        pos = self.parent().mapToGlobal(self.pos())
        self.edit_panel.move(pos.x() + self.width() - max(self.width(), s.width()), pos.y())
        self.edit_panel.show()

        return super(PoppingContactDataPlateWidget,self).enterEvent(event)


    def _make_layout(self,popup_widget):
        self.popping_plate = popup_widget
        self.popup_shown = False

        self.edit_panel = PopupWidget(popup_widget, self) # No parent => top level window
        self.setFrameShape(QFrame.NoFrame)

        self.setTextInteractionFlags(Qt.TextSelectableByMouse)
        # self.setObjectName("HorseCustomerPlateTitle")
        # self.setStyleSheet("#HorseCustomerPlateTitle { border: 1px solid black; }")

    def _set_name(self,name):
        self.setText(u"<h1>{}".format(name))

    def set_contact_data(self,contact_data):
        if contact_data:
            self._set_name(contact_data.fullname)
            self.popping_plate.set_contact_data(contact_data)

    def __init__(self,parent):
        super(PoppingContactDataPlateWidget,self).__init__(parent)


class SupplierPlateWidget(PoppingContactDataPlateWidget):

    def __init__(self,parent):
        super(SupplierPlateWidget,self).__init__(parent)
        self._make_layout(SupplierContactDataWidget())

class PoppingCustomerPlateWidget(PoppingContactDataPlateWidget):

    def __init__(self,parent):
        super(PoppingCustomerPlateWidget,self).__init__(parent)
        self._make_layout(CustomerContactDataWidget())
