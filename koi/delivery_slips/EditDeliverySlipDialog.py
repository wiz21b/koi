from datetime import datetime

from PySide.QtCore import Qt,Slot
from PySide.QtGui import QLabel, QHeaderView, QDialog, QDialogButtonBox
from PySide.QtGui import QVBoxLayout, QDesktopWidget, QCheckBox # , QHBoxLayout, QLineEdit, QGroupBox

from koi.gui.dialog_utils import TitleWidget, showErrorBox,showWarningBox,confirmationBox
from koi.gui.ProxyModel import PrototypeController,IntegerNumberPrototype, TextLinePrototype, TrackingProxyModel
from koi.datalayer.database_session import session
from koi.db_mapping import OrderPartStateType
from koi.dao import dao,DataException
from koi.Configurator import mainlog
from koi.reporting.delivery_slip_report import print_delivery_slip


def handle_edit_delivery_slip(order_id,parent):
    """ Returns True if a delivery slip was actually produced. """

    # We only allow reporting quantities on part where
    # an actual work was produced.


    order = dao.order_dao.find_by_id(order_id)
    parts_with_qty_left = list(filter(lambda p:p.tex2<p.qty and p.state not in (OrderPartStateType.aborted,OrderPartStateType.completed), order.parts))
    parts_with_hours_done = list(filter(lambda p:p.total_hours>0, parts_with_qty_left))
    session().commit()

    # mainlog.debug("handle_edit_delivery_slip : parts_with_qty_left:{}, parts_with_hours_done:{}".format(
    #    len(parts_with_qty_left), len(parts_with_hours_done)))

    if not order.accounting_label:
        showWarningBox(_("Order has never been in production"),
                       _("This order has never been in production, so there can't be units to report on it"), parent)
        return

    if not order.parts:
        showWarningBox(_("Empty order"),
                       _("There's nothing to report on a delivery slip !"), parent)
        return

    if not parts_with_qty_left:
        showWarningBox(_("All parts completed"),
                       _("All the parts of the order are already completed (either because one explictely marked them as completed/aborted or because the quantities out are equal to the planned quantities), making a delivery slip is not needed"), parent)
        return

    if not parts_with_hours_done:
        showWarningBox(_("No work done"),
                       _("You're trying to create a delivery slip for parts of an order where no work was actually done.\nI'll let you do it although it doesn't make much sense."),
                       parent)

    # if order.state in (OrderStatusType.preorder_definition, OrderStatusType.order_definition):
    #     showWarningBox(_("Order not ready for production"),
    #                    _("You're trying to create a delivery slip for an order that is not yet in production. This is not possible"), parent)
    #     return


    d = EditDeliverySlipDialog(parent)
    d.set_data(order_id)
    d.exec_()
    r = d.result() == QDialog.Accepted

    if r:
        print_delivery_slip(dao,d.slip_id)

    d.deleteLater()
    return r


class DeleteLastDeliverySlipDialog(QDialog):
    def __init__(self,parent):
        global dao
        super(DeleteLastDeliverySlipDialog,self).__init__(parent)

        title = _("Delete the last delivery slip")
        self.setWindowTitle(title)

        top_layout = QVBoxLayout()
        self.title_widget = TitleWidget(title,self)
        top_layout.addWidget(self.title_widget)

        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        top_layout.addWidget(self.info_label)

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.StandardButton.Cancel)
        self.buttons.addButton( QDialogButtonBox.Ok)

        top_layout.addWidget(self.buttons)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        self.setLayout(top_layout)



    def set_last_id(self,last_id):
        self.last_id = dao.delivery_slip_part_dao.find_last_slip_id()
        self.info_label.setText(_("You're about to delete the delivery slip number {}. Do you confirm ?").format(self.last_id))

    @Slot()
    def accept(self):
        try:
            dao.delivery_slip_part_dao.delete_last(self.last_id)
            super(DeleteLastDeliverySlipDialog,self).accept()
        except DataException as ex:
            showErrorBox(_("Unable to delete the last delivery slip"),
                         str(ex))
            super(DeleteLastDeliverySlipDialog,self).reject()


def handle_delete_last_slip(parent):
    last_id = dao.delivery_slip_part_dao.find_last_slip_id()
    if last_id:
        d = DeleteLastDeliverySlipDialog(parent)
        d.set_last_id(last_id)
        d.exec_()
        return d.result() == QDialog.Accepted
    else:
        showWarningBox(_("No delivery slip to delete !"),
                       _("There are no delivery slip to delete"))
        return False

class EditDeliverySlipDialog(QDialog):

    # def _make_units_qaulifications_gui(self):
    #     hlayout = QHBoxLayout()
    #     for qualif in [_("Good"), _("Bad"), _("Test")]:
    #         hlayout.addWidget( QLabel(qualif))
    #         hlayout.addWidget( QLineEdit())
    #
    #     f = QGroupBox(_("Qualification of units"))
    #     f.setLayout(hlayout)
    #     return f

    def __init__(self,parent):
        global dao
        super(EditDeliverySlipDialog,self).__init__(parent)

        title = _("Create delivery slip")
        self.setWindowTitle(title)

        top_layout = QVBoxLayout()
        self.title_widget = TitleWidget(title,self)
        top_layout.addWidget(self.title_widget)

        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        top_layout.addWidget(self.info_label)

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.StandardButton.Cancel)
        self.buttons.addButton( QDialogButtonBox.Ok)

        order_part_prototype = []
        order_part_prototype.append( TextLinePrototype('human_identifier',_('Part n.'),editable=False))
        order_part_prototype.append( TextLinePrototype('description',_('Description'),editable=False))
        order_part_prototype.append( IntegerNumberPrototype('qty',_('Qty plan.'),editable=False))
        order_part_prototype.append( IntegerNumberPrototype('tex2',_('Qty so far'),editable=False))
        order_part_prototype.append( IntegerNumberPrototype(None,_('Qty out now'),nullable=True))
        self.qty_out_column = len(order_part_prototype) - 1

        # order_part_prototype.append( IntegerNumberPrototype(None,_('Reglages'),nullable=True))
        # order_part_prototype.append( IntegerNumberPrototype(None,_('Derogation'),nullable=True))
        # order_part_prototype.append( IntegerNumberPrototype(None,_('Rebus'),nullable=True))


        self.controller_part = PrototypeController(self, order_part_prototype,None,freeze_row_count=True)
        self.controller_part.view.horizontalHeader().setResizeMode(QHeaderView.ResizeToContents)
        self.controller_part.view.horizontalHeader().setResizeMode(1,QHeaderView.Stretch)


        self.controller_part.setModel(TrackingProxyModel(self,order_part_prototype))
        self.close_order_checkbox = QCheckBox(_("Close the order"))

        top_layout.addWidget(self.controller_part.view) # self.time_tracks_view)
        # top_layout.addWidget(self._make_units_qaulifications_gui())
        top_layout.addWidget(self.close_order_checkbox)
        top_layout.addWidget(self.buttons)
        self.setLayout(top_layout)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        sg = QDesktopWidget().screenGeometry()
        self.setMinimumWidth(0.5*sg.width())
        self.setMinimumHeight(0.3*sg.height())

        self.slip_id = None

    def set_data(self,order_id):
        self.slip_id = None
        self.order_id = order_id

        order = dao.order_dao.find_by_id(order_id)
        parts = list(filter(lambda part:part.qty > 0 and part.tex2 < part.qty, order.parts))
        self.controller_part.model._buildModelFromObjects(parts)

        cn = ""
        if order.customer_order_name:
            cn = u" " + _("(customer number <b>{}</b>)").format(order.customer_order_name)

        self.info_label.setText(_("Creating a new delivery slip for order <b>{}</b>{} of customer <b>{}</b>").format(order.accounting_label,cn,order.customer.fullname))

        for p in parts:
            x = p.order_part_id # Force attribute load
            session().expunge(p)

        session().commit() # FIXME let the locks go

    def _start_edit(self):
        # Out to allow testing
        ndx = self.controller_part.model.index(0,self.qty_out_column)
        self.controller_part.view.setCurrentIndex( ndx)
        self.controller_part.view.edit( ndx)

    def exec_(self):
        # Start editing the table when showing the dialog
        self._start_edit()
        super(EditDeliverySlipDialog,self).exec_()

    def save(self):
        return True

    @Slot()
    def accept(self):
        # I do this to make sure that if the user was editing some data
        # in the table, those data will actually be commited once he
        # pushed the button

        ndx = self.controller_part.view.currentIndex()
        self.controller_part.view.setCurrentIndex(self.controller_part.model.index(0,0))
        self.controller_part.view.setCurrentIndex(ndx)

        if self.make_delivery_slip() == True:
            super(EditDeliverySlipDialog,self).accept()

    @Slot()
    def reject(self):
        super(EditDeliverySlipDialog,self).reject()


    def _check_unpriced_part(self):
        t = self.controller_part.model

        parts = dict()
        for p in dao.order_part_dao.find_by_order_id(self.order_id):
            parts[p.order_part_id] = p

        for i in range(t.rowCount()):
            if t.objects[i]:
                qty = t.data( t.index(i,self.qty_out_column), Qt.UserRole) or 0
                order_part_id = t.objects[i].order_part_id
                if qty > 0 and parts[order_part_id].sell_price == 0:
                    return True


    def _check_for_quantities_too_big(self):
        t = self.controller_part.model
        too_big = False
        order = dao.order_dao.find_by_id(self.order_id)
        for i in range(t.rowCount()):
            if t.objects[i]:
                qty = t.data( t.index(i,self.qty_out_column), Qt.UserRole) or 0
                order_part_id = t.objects[i].order_part_id
                for part in order.parts:
                    if part.order_part_id == order_part_id:
                        if part.tex2 + qty > part.qty:
                            too_big = True
                            break
        session().commit()

        return too_big




    def make_delivery_slip(self):
        global dao

        t = self.controller_part.model

        # mainlog.debug(u"make_delivery_slip() {}".format(t.objects))

        # Extract the quantities to get out from the order part table

        parts_ids_quantities = dict()

        info = u""
        for i in range(t.rowCount()):
            qty = t.data( t.index(i,self.qty_out_column), Qt.UserRole) or 0
            order_part = t.objects[i]

            mainlog.debug("Line {} qty = {}, order part={} ".format(i,qty, order_part is not None))

            if order_part and qty > 0:

                if order_part.order_part_id not in parts_ids_quantities:
                    parts_ids_quantities[order_part.order_part_id] = 0
                parts_ids_quantities[order_part.order_part_id] += qty

                info = info + ("<li>" + _("For {} {}, quantity {}")\
                               + "</li>").format(t.data( t.index(i,0), Qt.UserRole),
                                                 t.data( t.index(i,1), Qt.UserRole),
                                                 qty)

        info = u"<ul>{}</ul>".format(info)


        mainlog.debug("edit_dialog : checking for missing quantities")
        if len(parts_ids_quantities) == 0:
            showWarningBox(_("You requested to create a new delivery slip. However, you didn't encode any quantities"),None,None,"quantity_missing")
            return False

        mainlog.debug("edit_dialog : checking for quantities")
        if self._check_for_quantities_too_big():
            showErrorBox(_("One quantity is too big"), _("Pay attention ! On some parts, you gave a quantity out that will make the total quantity out bigger than what was ordered. You must either change the quantity out or change the planned quantity."),None,"quantityTooBig")
            return False

        if self._check_unpriced_part():
            showWarningBox(_("Some of the parts you want to make a delivery slip for have a null sell price. This is not an error but you may want to double check that situation."),None,None,"unpriced_part")

        mainlog.debug("edit_dialog : confirmationBox to be opened order_id is {}".format(self.order_id))

        if confirmationBox(u"<font color='red'><b>{}</b></font>".format(_("<b>You're about to make a new delivery slip. This can't be reversed, please confirm.\n Here are the quantities you're going to record")),info,"confirmDSCreation"):
            mainlog.debug("confirmationBox was OK")
            try:
                self.slip_id = dao.delivery_slip_part_dao.make_delivery_slip_for_order(
                    self.order_id,
                    parts_ids_quantities,
                    datetime.now(),
                    self.close_order_checkbox.checkState() == Qt.Checked)

                mainlog.debug("A delivery slip was created {}".format(self.slip_id))

                return True
            except Exception as ex:
                showErrorBox(_("Error while creating the delivery slip"),
                             _("The delivery slip was not created due to an unexpected error."),ex)
                return False
