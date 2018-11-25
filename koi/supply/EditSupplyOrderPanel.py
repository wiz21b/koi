if __name__ == "__main__":
    import sys
    from PySide.QtGui import QApplication,QMainWindow

    from koi.base_logging import mainlog,init_logging

    init_logging()
    init_i18n()
    load_configuration()

    from koi.db_mapping import metadata

    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)

from datetime import date

from PySide.QtCore import Qt,Slot,QPoint,QModelIndex,Signal
from PySide.QtGui import QVBoxLayout,QHBoxLayout,QMenu,QAction,QKeySequence,QStandardItem,QMessageBox, QLabel,QSizePolicy, \
    QHeaderView, QApplication

from koi.gui.horse_panel import HorsePanel
from koi.Configurator import mainlog
from koi.gui.dialog_utils import TitleWidget,NavBar,populate_menu,yesNoBox,showErrorBox, DescribedTextEdit,formatErrorsOnLine,confirmationBox
from koi.gui.ProxyModel import PrototypeController,FloatNumberPrototype, TextAreaPrototype,ProxyTableView, \
    FutureDatePrototype
from koi.datalayer.generic_access import blank_dto
from koi.datalayer.supplier_service import supplier_service
from koi.datalayer.supply_order_service import supply_order_service
from koi.datalayer.supply_order_mapping import SupplyOrder,SupplyOrderPart

#from SupplierPlateWidget import SupplierPlateWidget
from koi.CustomerPlateWidget import SupplierPlateWidget

from koi.reporting.supply_order_report import print_supply_order

from PySide.QtGui import QLineEdit, QValidator
from koi.gui.ComboDelegate import FutureDateValidator
from koi.gui.ProxyModel import TrackingProxyModel
from koi.gui.inline_sub_frame import InlineSubFrame
from koi.translators import date_to_dmy

class DateEntryWidget(QLineEdit):
    def __init__(self, parent=None, base_date = None):
        super(DateEntryWidget,self).__init__(parent)
        self._validator = FutureDateValidator(base_date)
        self.setValidator(self._validator)
        self.date_format = "{:%d/%m/%Y}"

    def is_valid(self):
        mainlog.debug("is_valid ; {} {} ".format(self.text(), self.validator().validate(self.text(), 0)))
        return self.validator().validate(self.text(), 0) == QValidator.Acceptable

    def set_value(self, v):
        # mainlog.debug("Setting text {}".format(v))
        if v:
            self.setText(self.date_format.format(v))
        else:
            self.setText(None)

    def value(self):
        if not self.text():
            return None
        elif self.is_valid():
            return self._validator.parser.parse(self.text())
        else:
            raise Exception("Date input is not valid")




class SupplyOrderPartsModel(TrackingProxyModel):

    def __init__(self,parent,prototype):
        super(SupplyOrderPartsModel,self).__init__(parent,prototype)


    def headerData(self,section,orientation,role):
        # For some reason, returning only DisplayRole is mandatory
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            if section < len(self.objects) and section >= 0 and self.objects[section]:
                return self.objects[section].label
            else:
                return "/"
        else:
            return None

class EditSupplyOrderPanel(HorsePanel):

    supply_order_saved = Signal()

    def panel_content_hash(self):
        return (self.current_supply_order_id, self.current_supplier.supplier_id)

    def needs_close_confirmation(self):
        return self.model_data_changed

    def confirm_close(self):
        return self._save_if_necessary()

    @Slot()
    def change_supplier(self):
        from koi.supply.ChooseSupplierDialog import ChooseSupplierDialog
        from PySide.QtGui import QDialog

        d = ChooseSupplierDialog(self)
        if d.exec_() and d.result() == QDialog.Accepted and d.supplier_id != self.current_supplier.supplier_id:
            mainlog.debug("Supplier chosen {}".format(d.supplier))
            self.current_supplier = d.supplier
            self.supplier_plate_widget.set_contact_data(self.current_supplier)
            self.data_changed2_slot()


    @Slot()
    def print_supply_order(self):
        if self._save_if_necessary():
            try:
                print_supply_order(self.current_supply_order_id)
            except Exception as e:
                showErrorBox(str(e))



    def _save_if_necessary(self):
        """ True if the user has either said he doesn't want to save or
        he saved successufly. False if the user has cancelled (no save, no "no save")
        or the save operation has failed """

        if self.model_data_changed:
            ynb = yesNoBox(_("Data were changed"),
                           _("You have changed some of the data in this. Do you want to save before proceeding ?"))
            if ynb == QMessageBox.Yes:
                if self.save() != False:  # FIXME defensive, make sure it's True
                    # Because when I save, although the order definition is
                    # not meant to change, the order numbers (accounting label,
                    # etc.) might actually change.
                    self.reload()
                    return True
                else:
                    return False
            elif ynb == QMessageBox.No:
                return True
            elif ynb == QMessageBox.Cancel:
                return False
        else:
            return True


    def edit_new(self, supplier):
        """ Start editing a brand new order
        """

        self.current_supplier = supplier
        self.current_supply_order_id = None
        self.edit_comment_widget.setText(None)
        self.delivery_date_widget.set_value(None)
        self.creation_date_widget.setText("")
        self.controller_part.model.clear()
        self.controller_part.model.insertRows(0,1,QModelIndex())
        self.accounting_label = None
        self._set_view(None,True)

        mainlog.debug("edit_new : supplier : {}".format(self.current_supplier.supplier_id))

    def edit(self, supply_order_id):
        """ Start editing an existing order
        """

        self._fill_view_with_order_data(supply_order_id)
        self._set_view(None,False)

    def reload(self):
        ndx = self.controller_part.view.currentIndex()
        self._fill_view_with_order_data(self.current_supply_order_id)
        self._set_view(ndx,False)

    def _fill_view_with_order_data(self, order_id):
        sorder, sorder_parts = supply_order_service.find_by_id(order_id)

        self.edit_comment_widget.setText(sorder.description)
        self.delivery_date_widget.set_value(sorder.expected_delivery_date)
        self.creation_date_widget.setText(date_to_dmy(sorder.creation_date))
        self.supplier_reference_widget.setText(sorder.supplier_reference)
        self.current_supplier = supplier_service.find_by_id(sorder.supplier_id)
        self.current_supply_order_id = sorder.supply_order_id
        self.model._buildModelFromObjects(sorder_parts)
        self.accounting_label = sorder.accounting_label

    def _set_view(self,ndx = None, start_editing = False):
        """ Once the data and models are prepared, one comes
        here to start the editing...
        """

        self.supplier_plate_widget.set_contact_data(self.current_supplier)
        self.controller_part.view.setFocus()

        if not ndx:
            ndx = self.controller_part.model.index(0,0)
        # Somehow, editing a cell doesn't set up the currentIndex automatically...
        self.controller_part.view.setCurrentIndex(ndx)

        if start_editing:
            self.controller_part.view.edit(ndx)

        self.model_data_changed = False
        self.title_widget.set_modified_flag(False)


        ref = self.accounting_label or self.supplier_reference_widget.text()

        if ref:
            self.set_panel_title( u"{}\n{}".format(ref, self.current_supplier.fullname))
        else:
            self.set_panel_title(_("Supply order") + u"\n" + self.current_supplier.fullname)

        refs = []
        if self.accounting_label:
            refs.append(u"<span style='color:orange; font-style:normal;'>{}</span>".format(self.accounting_label))

        if self.supplier_reference_widget.text():
            refs.append(u"<span style='color:black; font-style:normal;'>{}</span>".format(self.supplier_reference_widget.text()))

        self.in_title_label.setText(_("<h1>Ref. : {}</h1>").format(u" / ".join(refs)))

    def _validate(self):
        errs = self.model.validate()
        if errs:
            errs = [formatErrorsOnLine(errs)]
        else:
            errs = []

        if not self.delivery_date_widget.is_valid():
            errs.append(_('The date is not valid'))

        return errs or True



    def save(self):
        if self.model_data_changed:

            focused_widget = QApplication.focusWidget()
            if isinstance( focused_widget, QLineEdit) and focused_widget.parent() != self:
                focused_widget.clearFocus()
                focused_widget = QApplication.focusWidget()

            validation_results = self._validate()
            if validation_results != True:
                showErrorBox(_("The data are not correct"), "<br>-" + "<br>-".join(validation_results))
                return False

            mainlog.debug("save : supplier_id : {}".format(self.current_supplier.supplier_id))

            obj = blank_dto(SupplyOrder)
            obj.supply_order_id = self.current_supply_order_id
            obj.creation_date = date.today()
            obj.description = self.edit_comment_widget.toPlainText()
            obj.supplier_id = self.current_supplier.supplier_id
            obj.expected_delivery_date = self.delivery_date_widget.value()
            obj.supplier_reference = self.supplier_reference_widget.text()
            obj.accounting_label = self.accounting_label

            def factory():
                return blank_dto(SupplyOrderPart)

            parts_actions = self.model.model_to_objects( factory )

            try:
                mainlog.debug("Saving")
                self.current_supply_order_id = supply_order_service.save(obj, parts_actions)
                # Reload the data
                self.reload()
                mainlog.debug("Emitting change signal")
                self.supply_order_saved.emit() # self.current_supply_order_id)

            except Exception as ex:
                showErrorBox(_("Error while saving"),_("There was an unexpected error while saving your data"),ex,object_name="saveError")

            if focused_widget:
                focused_widget.setFocus(Qt.OtherFocusReason)


    @Slot()
    def delete(self):
        if self.current_supply_order_id:

            s = _("About to delete order {}").format(self.accounting_label)

            if confirmationBox(s,_("Are you sure ?")):

                try:
                    supply_order_service.deactivate(self.current_supply_order_id)
                except Exception as ex:
                    showErrorBox("I could not delete the order",ex=ex)
                    return

                rep = supply_order_service.find_last_order_id(self.current_supplier.supplier_id)
                if rep:
                    self.edit(rep)
                else:
                    self.edit_new(self.current_supplier)
        else:
            showErrorBox(_("No order or non-saved order selected"),
                         _("You can only delete an order that has already been saved"),
                         object_name="delete_only_saved_order")
            return

    @Slot()
    def show_actions(self):
        button = self.action_menu.parent()
        p = button.mapToGlobal(QPoint(0,button.height()))
        self.action_menu.exec_(p)

    @Slot(QStandardItem)
    def data_changed_slot(self,item):
        self.model_data_changed = True
        self.title_widget.set_modified_flag(self.model_data_changed)

    @Slot()
    def data_changed2_slot(self):
        self.model_data_changed = True
        self.title_widget.set_modified_flag(self.model_data_changed)

    @Slot()
    def next_order_for_supplier(self):
        if self._save_if_necessary():
            # This could find nothing if there's no order for the supplier :-)
            oid = supply_order_service.find_next_for_supplier(self.current_supply_order_id, self.current_supplier.supplier_id)
            if oid:
                self.edit(oid)

    @Slot()
    def previous_order_for_supplier(self):
        if self._save_if_necessary():
            oid = supply_order_service.find_previous_for_supplier(self.current_supply_order_id, self.current_supplier.supplier_id)
            if oid:
                self.edit(oid)

    def __init__(self,parent):
        super(EditSupplyOrderPanel,self).__init__(parent)

        self.current_supply_order_id = None

        self.proto = []
        self.proto.append( TextAreaPrototype('description',_('Description'), editable=True,nullable=False))
        self.proto.append( FloatNumberPrototype('quantity',_('Quantity'), editable=True,nullable=False))
        self.proto.append( FloatNumberPrototype('unit_price',_('Unit price'), editable=True,nullable=True))

        self.delivery_date_prototype = FutureDatePrototype('description',('Description'),editable=True,nullable=False)

        self.model = SupplyOrderPartsModel(self,self.proto)

        self.controller_part = PrototypeController(self,
                                                   self.proto,
                                                   ProxyTableView(None,self.proto))

        self.controller_part.setModel(self.model)
        # self.controller_part.view.verticalHeader().hide()
        self.controller_part.view.horizontalHeader().setResizeMode(0, QHeaderView.Stretch)

        self.print_supply_order_action = QAction(_("Print supply order"),self) # , parent
        self.print_supply_order_action.triggered.connect( self.print_supply_order)
        self.print_supply_order_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_P))
        self.print_supply_order_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.addAction(self.print_supply_order_action)

        self.save_supply_order_action = QAction(_("Save supply order"),self) # , parent
        self.save_supply_order_action.triggered.connect( self.save)
        self.save_supply_order_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_S))
        self.save_supply_order_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.addAction(self.save_supply_order_action)

        self.delete_supply_order_action = QAction(_("Deactivate supply order"),self) # , parent
        self.delete_supply_order_action.triggered.connect( self.delete)
        self.addAction(self.delete_supply_order_action)

        self.next_order_for_supplier_action = QAction(_("Next supplier's order"),self) # , parent
        self.next_order_for_supplier_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_PageDown))
        self.next_order_for_supplier_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.next_order_for_supplier_action.triggered.connect( self.next_order_for_supplier)
        self.addAction(self.next_order_for_supplier_action)

        self.previous_order_for_supplier_action = QAction(_("Previous supplier's order"),self) # , parent
        self.previous_order_for_supplier_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_PageDown))
        self.previous_order_for_supplier_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.previous_order_for_supplier_action.triggered.connect( self.next_order_for_supplier)
        self.addAction(self.previous_order_for_supplier_action)

        self.change_supplier_action = QAction(_("Change supplier"),self) # , parent
        self.change_supplier_action.triggered.connect( self.change_supplier)
        self.addAction(self.change_supplier_action)

        # self.controller_operation.view.addAction(self.reprint_delivery_slip)
        self.controller_part.view.addAction(self.print_supply_order_action)
        self.controller_part.view.addAction(self.save_supply_order_action)
        self.controller_part.view.addAction(self.delete_supply_order_action)

        navigation = NavBar( self,
                             [ (self.next_order_for_supplier_action.text(), self.next_order_for_supplier),
                               (self.previous_order_for_supplier_action.text(), self.previous_order_for_supplier),
                               (_("Action"),self.show_actions) ] )
        navigation.buttons[2].setObjectName("specialMenuButton")

        self.action_menu = QMenu(navigation.buttons[2])
        list_actions = [ (self.print_supply_order_action, None),
                         (self.save_supply_order_action, None),
                         (self.delete_supply_order_action, None),
                         (self.change_supplier_action, None )]

        populate_menu(self.action_menu, self, list_actions, context=Qt.WidgetWithChildrenShortcut)

        self.title_widget = TitleWidget(_("Supply order"),self,navigation)
        self.supplier_plate_widget = SupplierPlateWidget(self)
        self.edit_comment_widget = DescribedTextEdit(_("Comments"))
        self.edit_comment_widget.setMinimumHeight(20)
        self.edit_comment_widget.setMinimumWidth(600)
        self.edit_comment_widget.setMaximumHeight(60)
        self.edit_comment_widget.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Preferred)

        self.supplier_reference_widget = QLineEdit()

        self.delivery_date_widget = DateEntryWidget()
        self.delivery_date_widget.setMaximumWidth(100)

        self.creation_date_widget = QLabel()

        self.in_title_label = QLabel()

        top_layout1 = QHBoxLayout()
        top_layout1.addWidget(self.in_title_label)
        top_layout1.addStretch()
        top_layout1.addWidget(self.supplier_plate_widget)

        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel(_("Delivery date")))
        hlayout.addWidget(self.delivery_date_widget)
        hlayout.addStretch()

        hlayout3 = QHBoxLayout()
        hlayout3.addWidget(QLabel(_("Creation date")))
        hlayout3.addWidget(self.creation_date_widget)
        hlayout3.addStretch()

        hlayout2 = QHBoxLayout()
        hlayout2.addWidget(QLabel(_("Supplier's reference")))
        hlayout2.addWidget(self.supplier_reference_widget)
        hlayout2.addStretch()

        vlayout = QVBoxLayout()
        vlayout.addLayout(hlayout) # delivery date
        vlayout.addLayout(hlayout3) # creation date
        vlayout.addLayout(hlayout2) # reference
        vlayout.addStretch()

        top_layout2 = QHBoxLayout()
        top_layout2.addLayout(vlayout)
        top_layout2.addWidget(self.edit_comment_widget)
        top_layout2.addStretch()
        top_layout2.setStretch(0,0)
        top_layout2.setStretch(1,0)
        # For some reason, the stretch added above is not enough
        # to push the whole layout to the left. I have to set
        # it's stretch factor too...
        top_layout2.setStretch(2,100)

        vhead_layout = QVBoxLayout()
        vhead_layout.addWidget(self.title_widget)
        top_layout1.setContentsMargins(4,0,4,0)
        # vhead_layout.addLayout(top_layout1)
        vhead_layout.addWidget(InlineSubFrame(top_layout1,None))

        vhead_layout.addLayout(top_layout2)
        # top_layout2.setContentsMargins(4,4,4,4)
        #vhead_layout.addWidget(InlineSubFrame(top_layout2,None))

        vhead_layout.addWidget(self.controller_part.view)
        vhead_layout.setStretch(0,0)
        vhead_layout.setStretch(1,0)
        vhead_layout.setStretch(2,0)
        vhead_layout.setStretch(3,10)

        self.setLayout(vhead_layout)

        self.controller_part.view.enable_edit_panel()

        # Handling changes in the model (helpful to know if saving
        # is necessary)

        self.model_data_changed = False
        self.model.rowsInserted.connect(self.data_changed_slot)
        self.model.rowsRemoved.connect(self.data_changed_slot)
        self.model.dataChanged.connect(self.data_changed_slot)
        self.supplier_reference_widget.textChanged.connect(self.data_changed2_slot)
        self.edit_comment_widget.textChanged.connect(self.data_changed2_slot)
        self.delivery_date_widget.textChanged.connect(self.data_changed2_slot)

if __name__ == "__main__":

    app = QApplication(sys.argv)
    mw = QMainWindow()
    mw.setMinimumSize(1024,768)
    widget = EditSupplyOrderPanel(mw)

    widget.edit_new(supplier_service.find_all()[0])
    #widget.edit(8)

    # widget.reset_order(3998)
    # widget.edit_new_order(dao.customer_dao.all()[1])
    mw.setCentralWidget(widget)
    mw.show()

    app.exec_()
