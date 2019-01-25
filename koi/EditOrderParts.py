# TEST 2733A, 3716

#noinspection PyUnresolvedReferences
import sys
from functools import reduce
import copy
import traceback
from datetime import date
from collections import OrderedDict

from PySide.QtCore import Qt,Slot,QModelIndex,QAbstractTableModel,Signal, QPoint
from PySide.QtCore import QTimer
from PySide.QtGui import QHBoxLayout,QVBoxLayout,QLineEdit,QLabel,QGridLayout, QColor, QDialog, QMessageBox,QHeaderView,QAbstractItemView, \
    QKeySequence, QStandardItem,QComboBox, QAction,QMenu,QWidget,QCursor, QSizePolicy

if __name__ == "__main__":
    from PySide.QtGui import QApplication,QMainWindow

    from koi.base_logging import mainlog,init_logging
    from koi.Configurator import init_i18n,load_configuration,configuration

    init_logging()
    init_i18n()
    load_configuration()

    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session,session

    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)


from koi.gui.CopyPasteManager import copy_paste_manager
from koi.datalayer.employee_mapping import RoleType
from koi.gui.ProxyModel import PrototypeController,IntegerNumberPrototype,FloatNumberPrototype, DurationPrototype,TrackingProxyModel,OperationDefinitionPrototype,PrototypedTableView,ProxyTableView,OrderPartDisplayPrototype,TextAreaPrototype, \
    FutureDatePrototype,PrototypeArray
from koi.datalayer.types import DBObjectActionTypes

from koi.gui.dialog_utils import makeErrorBox, TitleWidget,confirmationBox, yesNoBox, showErrorBox,NavBar,populate_menu,DescribedTextEdit, SubFrame,showWarningBox, FlexiLabel
from koi.gui.horse_panel import HorsePanel
from koi.db_mapping import Order, OrderPart, Operation, OrderPartStateType
# from OrderPartEdit import order_number_title

from koi.db_mapping import OrderStatusType

from PySide.QtGui import QStandardItemModel
from koi.configuration.business_functions import operation_unit_cost
from koi.CustomerPlateWidget import PoppingCustomerPlateWidget
from koi.gui.Arrow import BigArrow
from koi.OrderWorkflowDialog import OrderWorkflowDialog

from koi.PrintPreorderDialog import PrintPreorderDialog
from koi.ChangeCustomerDialog import ChangeCustomerDialog

from koi.tools.chrono import *

from koi.reporting.order_activity_report import print_iso_status
from koi.reporting.order_report import print_order_report, print_bill_of_operations_report
from koi.reporting.preorder_report import print_preorder
from koi.reporting.audit_order_report import print_order_audit_report

from koi.translators import duration_to_s, EURO_SIGN, date_to_s

from koi.base_logging import log_stacktrace

from koi.gui.editors import OrderStateEdit
from koi.datalayer.audit_trail_service import audit_trail_service
from koi.OperationDefinitionsCache import operation_definition_cache
from koi.gui.inline_sub_frame import InlineSubFrame

from koi.doc_manager.docs_collection_widget import DocumentCollectionWidget, documents_model_factory

from koi.datalayer.quality import QualityEvent
from koi.junkyard.sqla_dict_bridge import InstrumentedRelation, InstrumentedObject, make_change_tracking_dto, InstrumentedOrderedRelation
from koi.doc_manager.documents_mapping import Document

def quality_events_model_factory():
    return InstrumentedRelation()

from koi.machine.machine_service import machine_service
from koi.reporting.order_confirmation.order_confirmation_report2 import print_order_confirmation_report
from koi.reporting.preorder.preorder_report import print_preorder_report

from koi.gui.vertical_side_bar import VerticalSideBarLayout
from koi.quality.NonConformityDialog import NonconformitiesWidget
from koi.gui.ask_date import DatePick

from koi.dao import dao
from koi.configuration.business_functions import business_computations_service
from koi.gui.ObjectModel import ObjectModel
from koi.datalayer.generic_access import dto_factory

# from server import ClockServer,ServerException
# from BarCodeBase import BarCodeIdentifier

# class OrderStateLabel(QLabel):
#     def __init__(self,parent=None):
#         super(OrderStateLabel,self).__init__(parent)
#         self.set_state(None)

#     def set_state(self, state):
#         if state:
#             self.state = state
#             self.setText(_("State : {}").format(state.description))
#         else:
#             self.state = None
#             self.setText("")


def order_number_title(preorder_number, order_number, customer_number):
    t = []

    if order_number:
        t.append(u"<span style='color:red; font-style:normal;'>{}</span>".format( _("Cde: {}").format(order_number)))

    if preorder_number:
        t.append(u"<span style='color:green; font-style:normal;'>{}</span>".format(_("Dev.: {}").format(preorder_number)))

    if customer_number:
        t.append(u"<span style='color:black; font-style:normal;'>{}</span>".format(customer_number))

    return u" / ".join(t)



def is_value_editable(ndx):
    # mainlog.debug(" --- is_value_editable")

    op = ndx.model().index( ndx.row(),0).data(Qt.UserRole)
    if op:
        # op = operation_definition_cache.opdef_by_id(op)
        # By construction of the cache, all the operation definition
        # are at least "on operation", thus we don't have to test
        # for that.
        if not operation_definition_cache.imputable_by_id(op):
            return Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled
        else:
            return Qt.ItemIsSelectable | Qt.ItemIsEnabled
    else:
        return Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled


def are_planned_hours_editable(ndx):
    # mainlog.debug(" --- are_planned_hours_editable")

    op = ndx.model().index( ndx.row(),0).data(Qt.UserRole)
    if op:
        #  op = operation_definition_cache.opdef_by_id(op)
        if operation_definition_cache.imputable_by_id(op):
            return Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled
        else:
            return Qt.ItemIsSelectable | Qt.ItemIsEnabled
    else:
        return Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled


class EuroLabel(QLabel):
    def __init__(self,parent=None,flags=0):
        super(EuroLabel,self).__init__("--",parent,flags)

    def amount_to_str(self, amount):
        if amount is None:
            return u"/ " + EURO_SIGN
        else:
            # Display an amount in the french/belgian way
            t = u"<b>{:,.2f}</b>".format(amount).replace(u",",u" ").replace(u".",u",")
            return t + EURO_SIGN

    def setValue(self,f):
        self.value = f

        if f is None:
            self.setText("--")
        else:
            self.setText(self.amount_to_str(f))


def zerofloat(f):
    if not f:
        return 0

    try:
        return float(f)
    except ValueError as e:
        return 0

def zeroint(f):
    if not f:
        return 0

    try:
        return int(f)
    except ValueError as e:
        return 0

def make_header_model(titles):
    headers = QStandardItemModel(1, len(titles))
    i = 0
    for p in titles:
        headers.setHeaderData(i, Qt.Orientation.Horizontal, p)
        i = i + 1
    return headers





def operations_synthesis( operations):
    planned_hours = 0
    for op in operations:
        planned_hours += op.planned_hours or 0 # FIXME Should really be 0 by default, not None
    return planned_hours

# class OperationsModel(TrackingProxyModel):
class OperationsModel(ObjectModel):

    estimated_hours_changed = Signal()

    def blank_operation(self):
        return dto_factory.dto_for_mapper(Operation)

    def setData(self, index, value, role):
        super(OperationsModel, self).setData(index, value, role)

        # Planned time to produce has been updated
        # So we have to update the order part view as well
        if index and index.column() == 3:

            self.estimated_hours_changed.emit()
            return

            # planned_hours = operations_synthesis(self.read_only_objects())
            #
            # self.order_part.total_estimated_time = planned_hours * self.order_part.qty
            #
            # # self.order_parts_model.update_cell( )
            # self.order_parts_model.object_field_updated(self.order_part, 'total_estimated_time')
            #
            # # self.estimated_hours_changed.emit()
            # # ndx = self.order_parts_model.object_index( self.order_part)
            # # self.order_parts_model.dataChanged(ndx, ndx)

    def __init__(self,parent,prototype, parts_model : TrackingProxyModel):
        """

        :param parent:
        :param prototype:
        :param parts_model: The "parent" order parts model
        :param order_part: Object representing an OrderPart (to be located inside parts_model)
        :return:
        """
        assert parts_model, "There must be a model because we'll access its data"

        super(OperationsModel,self).__init__(parent,prototype,self.blank_operation)
        self.quantity_to_produce = 1
        self.order_parts_model = parts_model

        self.documents = documents_model_factory()
        self.notes = None # Notes associated to this part
        self.notes_changed = False
        self.quality_events = quality_events_model_factory()

        # self.documents = None
        # self.quality_events = None

    def set_notes(self, notes, track_change=True):
        if track_change and not self.notes_changed:
            self.notes_changed = self.notes != notes

        self.notes = notes

    def update_quantity_to_produce(self,new_qty):
        self.quantity_to_produce = new_qty

        # Force refresh of the column (i.e. recomputation of coloured warnings)
        # indices are topLeft, BottomRight

        # Highlight the hours done on the operation to show if there are too much
        self.dataChanged.emit( self.index(0,4), self.index(self.rowCount()-1,4))

    def text_color_eval(self,index):
        row = index.row()

        # 3 = hourss/unit; 4=done hours
        if row >= 0 and index.column() == 4:
            # mainlog.debug("text_color_eval planned_hours={}".format(self.index(row,3).data(Qt.UserRole)))
            total_hours_to_do = self.quantity_to_produce * self.index(row,3).data(Qt.UserRole)
            # mainlog.debug("text_color_eval total_hours_to_do={}".format(total_hours_to_do))
            total_done_hours = self.index(row,4).data(Qt.UserRole)

            if total_done_hours > total_hours_to_do :
                return QColor(255,0,0)

        return None


def order_part_row_protect(obj,row):
    # I don't access the object to prevent SQLA from reopening connections
    return obj is not None and row[5] > 0

def operation_row_protect(obj):
    # I don't access the object to prevent SQLA from reopening connections
    return obj.done_hours # Actually I test > 0, but since it can be None (when adding a row), then I write it this way...
    # return obj is not None and row[4] > 0


# class PartDataChangeTracker(InstrumentedObject):
#     """ Represents an order part, with its operations """
#     def __init__(self, order_part_id, operation_prototype, parts_model):
#         super(InstrumentedObject, self).__init__()
#
#         self.submodels = self._makeOperationsModel(order_part_id, operation_prototype, parts_model)
#         self.documents = documents_model_factory()
#         self.comment = None # Comment associated to this part
#         self.quality_events = quality_events_model_factory()
#
#         self.submodelCreated.emit( self.submodels)
#         self.submodels.update_quantity_to_produce(self.data(self.index(ndx, 1), Qt.UserRole))
#
#     def _makeOperationsModel(self, order_part_id, operation_prototype, parts_model):
#         """ Make or load an "opertaion" model tied to a given order part (ndx-th row) """
#
#         op_model = OperationsModel(None, operation_prototype, parts_model)
#         op_model.set_row_protect_func(operation_row_protect)
#
#
#         # model_set = False
#
#         if order_part_id:
#             # Reload the part (in case it was put out of the session)
#             # part = dao.order_part_dao.find_by_id_frozen(part.order_part_id)
#             # chrono_click("_makeSubModel : 1 : DB query")
#
#             operations = dao.operation_dao.find_by_order_part_id_frozen( order_part_id)  # TODO Freeze ?
#
#             # chrono_click("_makeSubModel : 2")
#
#             if operations:
#                 op_model._buildModelFromObjects(operations)
#                 # op_model.note = part.production_file[0].note
#                 # model_set = True
#                 # chrono_click("_makeSubModel : 3")
#
#         if op_model.rowcount() == 0:
#             # op_model.note = None  # FIXME this field is not there anymore ?!
#             # op_model._buildModelFromObjects(None)
#             op_model.insertRows(0, 1)
#
#         #op_model.debug = False
#
#         return op_model


class TModel(TrackingProxyModel):
    """ This will represent a list of order parts
    """

    submodelCreated = Signal(QAbstractTableModel)


    def __init__(self,parent,prototype,subprototype):
        super(TModel,self).__init__(parent,prototype)

        self.parts_data = InstrumentedOrderedRelation()

        self.submodels = []
        self.documents = []
        self.comments = [] # array of pairs : (comment, was comment changed ? )
        self.quality_event_models = []

        self.operation_prototype = subprototype
        self.set_row_protect_func(order_part_row_protect)



    def _makeSubModel(self,ndx):
        """ Make or load an "opertaion" model tied to a given order part (ndx-th row) """

        # if not self.objects[ndx]:
        #     self.objects[ndx] = OrderPart()

        part = self.objects[ndx]

        op_model =  OperationsModel(None,self.operation_prototype, self)
        op_model.set_row_protect_func(operation_row_protect)
        op_model.update_quantity_to_produce(self.data( self.index(ndx,1), Qt.UserRole))

        model_set = False


        if part and part.order_part_id:
            # Reload the part (in case it was put out of the session)
            # part = dao.order_part_dao.find_by_id_frozen(part.order_part_id)
            # chrono_click("_makeSubModel : 1 : DB query")

            operations = dao.operation_dao.find_by_order_part_id_frozen(part.order_part_id) # TODO Freeze ?


            #chrono_click("_makeSubModel : 2")

            if operations:
                op_model._buildModelFromObjects(operations)
                # op_model.note = part.production_file[0].note
                model_set = True
            #chrono_click("_makeSubModel : 3")

        if not model_set:
            op_model.note = None # FIXME this field is not there anymore ?!
            # op_model._buildModelFromObjects(None)
            op_model.insertRows(0, 1)


        op_model.debug = False
        self.submodelCreated.emit(op_model)
        return op_model


    def submodel(self,ndx):
        if ndx < 0 or ndx >= len(self.submodels):
            raise Exception("The index {} is out of range, maximum is {}".format(ndx, len(self.submodels)-1))

        if self.submodels[ndx] == None:
            self.submodels[ndx] = self._makeSubModel(ndx)

        return self.submodels[ndx] # but this model is not populated !!!!


    # def _makeBlankOperationModel(self):
    #     op_model =  OperationsModel(None,self.operation_prototype)
    #     op_model._buildModelFromObjects(None)
    #     op_model.note = None
    #     return op_model

    def _insert_blank_sub_models(self, row, count):
        if self.rowCount() != len(self.objects):
            raise Exception(" insertRows() {} {}".format(self.rowCount(), len(self.objects)))

        if row < len(self.submodels):
            mainlog.debug("TModel.insertRows : len(submodels)={}".format(len(self.submodels)))
            for i in range(count):
                self.submodels.insert(row,None) # self._makeBlankOperationModel())
                self.documents.insert(row,documents_model_factory())
                self.comments.insert(row,("",True))
                self.quality_event_models.insert(row,quality_events_model_factory())
                mainlog.debug("TModel.insertRows : inserted at {} for the {}th time".format(row,i))
            mainlog.debug("TModel.insertRows : after insert, len(submodels)={}".format(len(self.submodels)))
        else:
            mainlog.debug("TModel.insertRows : appending sub models, len(submodels)={}".format(len(self.submodels)))

            for i in range(count):
                self.submodels.append(None)
                self.documents.append(documents_model_factory())
                self.comments.append(("",True))
                self.quality_event_models.append(quality_events_model_factory())

    def insertRows(self, row, count, parentIndex):
        # mainlog.debug("TModel.insertRows : count={}".format(count))

        if row < 0:
            row = 0

        self._insert_blank_sub_models(row, count)
        r = super(TModel,self).insertRows(row, count, parentIndex)

        mainlog.debug("TModel = inserted {} rows at {}, model.rowCount = {} / current size is {} / len(submodels) {}".format(count,row,self.rowCount(), len(self.objects), len(self.submodels)))

        # self.documents = self.documents[0:row] + [None] * count + self.documents[row:len(self.documents)-1]

        if self.rowCount() != len(self.objects):
            raise Exception(" insertRows() {} {}".format(self.rowCount(), len(self.objects)))

        return r



    def headerData(self,section,orientation,role):
        # For some reason, returning only DisplayRole is mandatory
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            if section < len(self.objects) and section >= 0 and self.objects[section]:
                return self.objects[section].label
            else:
                return "/"
        else:
            return None

    def has_submodels(self):
        return len(self.submodels) > 0

    def removeRows(self, row, count, parentIndex = QModelIndex()):
        # mainlog.debug("TModel.removeRows() = removing {} rows from then {}th row, table row count = {} / object count = {}".format(count, row, self.rowCount(), len(self.objects)))

        if self.rowCount() != len(self.objects):
            raise Exception("TModel.removeRows() {} {}".format(self.rowCount(), len(self.objects)))

        r = super(TModel,self).removeRows(row, count, parentIndex = QModelIndex())

        if r:
            # mainlog.debug("TModel = removed rows, row count = {} / current size is {}".format(self.rowCount(), len(self.objects)))
            if count > 0 and row >= 0:
                del(self.submodels[row:(row+count)])
                del(self.documents[row:(row+count)])
                del(self.comments[row:(row+count)])
                del(self.quality_event_models[row:(row+count)])

            # mainlog.debug("TModel.removeRows() = calling super")

        if self.rowCount() != len(self.objects):
            raise Exception("TModel.removeRows() {} {}".format(self.rowCount(), len(self.objects)))

        return r

    def _buildModelFromObjects(self,objects):
        # mainlog.debug("TModel._buildModelFromObjects calling parent")

        super(TModel,self)._buildModelFromObjects(objects)

        if objects is None or objects == []: # FIXME objects should never be None
            # mainlog.debug("TModel._buildModelFromObjects / no objects")
            self.submodels = [None] # Keep it in sync with parent class
            self.documents = [documents_model_factory()]
            self.comments = [ ("",True) ]
            self.quality_event_models = [quality_events_model_factory()]

        else:
            # mainlog.debug("TModel._buildModelFromObjects with {} objects".format(len(objects)))
            self.submodels = [None]*len(objects)
            self.documents = [None]*len(objects)
            self.comments = [ ("",True) ]*len(objects)
            self.quality_event_models = [None]*len(objects)

            # At this point, "objects" are actually order parts
            for i in range(len(objects)):

                # Documents related to the order part
                self.documents[i] = documents_model_factory()

                self.documents[i].load_documents(
                    sorted(list(objects[i].documents),
                           key=lambda d:str(d.document_category_id) + d.filename)) # data model for documents list is actually a set

                # Quality events associated to the order part
                qe_model = quality_events_model_factory()
                for qe in objects[i].quality_events:
                    mainlog.debug("Loading a quality event (id={}), it has {} documents associated.".format(qe.quality_event_id, len(qe.documents)))
                    qe_dto = make_change_tracking_dto(QualityEvent, obj=qe, recursive= {Document})
                    # qe_dto._documents_model.load_documents( list(qe.documents)) # data model for documents list is actually a set
                    qe_model.append(qe_dto)

                    mainlog.debug("Setting quality events to {} of type {}".format(qe, type(qe)))
                qe_model.clear_changes()

                self.quality_event_models[i] = qe_model
                self.comments[i] = ( objects[i].notes, False )

                #self.submodels[i].set_notes(objects[i].notes, track_change=False)

        # mainlog.debug("TModel._buildModelFromObjects at this point : {} / {}".format(self.rowCount(), len(self.submodels)))

        if self.rowCount() != len(self.objects):
            raise Exception(" _buildModelFromObjects() {} {}".format(self.rowCount(), len(self.objects)))


    def swap_row(self,ndx,ndx2):
        mainlog.debug("TModel : swap_row")

        if super(TModel,self).swap_row(ndx,ndx2, emit=False):

            def swap(array, ndx, ndx2):
                o = array[ndx2]
                array[ndx2] = array[ndx]
                array[ndx] = o

            swap(self.submodels, ndx, ndx2)
            swap(self.documents, ndx, ndx2)
            swap(self.comments, ndx, ndx2)
            swap(self.quality_events_models, ndx, ndx2)

            self.dataChanged.emit(self.index(ndx, 0), self.index(ndx, self.columnCount() - 1))
            self.dataChanged.emit(self.index(ndx2, 0), self.index(ndx2, self.columnCount() - 1))

            return True
        else:
            return False




class EditOrderPartsWidget(HorsePanel):

    # order_changed_signal = Signal()
    """ Sent when the data of a given order has been changed.
    """

    def resizeEvent(self, event):
        self.controller_part.view.resizeRowsToContents()
        self.controller_operation.view.resizeRowsToContents()

    def set_on_last_order_if_any(self):
        global dao

        last_order = dao.order_dao.find_last_one()
        if last_order:
            self.reset_order(last_order.order_id)
        else:
            self._show_blank_order(self.current_customer_id)
            # self.reset_order(None)

    def refresh_customer(self,customer_id):
        # mainlog.debug(u"refresh_customer {}".format(customer))
        if customer_id:
            customer = dao.customer_dao.find_by_id_frozen(customer_id)
            self.customer_plate_widget.set_contact_data(customer)
            return customer


    def __scroll_to_part(self):
        self.controller_part.view.scrollTo(self.controller_part.model.index(self.__scroll_to_index,0))

    def select_order_part(self, order_part):
        i = 0
        for part in self.controller_part.model.objects:
            if order_part.order_part_id == part.order_part_id:
                mainlog.debug("select_order_part {}, at index {}".format(part.order_part_id,i))
                self.controller_part.view.setCurrentIndex(self.controller_part.model.index(i,0))
                self.controller_part.view.setFocus(Qt.OtherFocusReason)
                self.__scroll_to_index = i

                # Dirty hack to make sure scrollTo works as expected
                # Test with 5050H
                self.__scroll_to_part_timer.start(500) # -1 so we never miss a minute

                return
            else:
                i += 1

        return



    def edit_new_order(self,customer_id):
        self.current_customer_id = customer_id

        self.target_order_id = None

        self._show_blank_order(customer_id)
        self.refresh_panel()


    def reset_order(self,order_id, overwrite=False):
        chrono_click("reset_order 1, order_id : {}".format(order_id))

        if not order_id:
            raise Exception("Can't work on an order without id")

        if self._current_order.order_id == order_id:
            mainlog.debug("Not resetting order because there's no need to")
            return

        chrono_click("reset_order 2")

        if not overwrite:
            if not self.save_if_necessary():
                return

        chrono_click("reset_order 3")

        self.target_order_id = order_id

        # self._show_order(order_id)
        # self.controller_part.view.setCurrentIndex(self.controller_part.model.index(0,0))
        self.refresh_panel()

        chrono_click("reset_order 4")


    def refresh_action(self):
        chrono_click("EditOrderParts.refresh_action : 0")
        if self.target_order_id != self._current_order.order_id or not self._current_order.order_id:

            # self.current_order_id = self.target_order_id

            if self.target_order_id:
                self._show_order( self.target_order_id)
            else:
                self._show_blank_order( self._current_order.customer_id)

            chrono_click("EditOrderParts.refresh_action : 1")
            self.controller_part.view.setCurrentIndex(self.controller_part.model.index(0,0))
        chrono_click("EditOrderParts.refresh_action : 2")

    def refresh_order(self):
        if self._current_order.order_id:
            cur_sel = self._push_current_selection()
            self._show_order( self._current_order.order_id)
            self._pop_current_selection(cur_sel)


    def _set_state(self, state_to_select):
        #self.order_state_label.set_value(state_to_select)

        # TODO bring in the order so we can check other fiesl to properly compute next states
        self.order_state_label.set_state(
            state_to_select,
            business_computations_service.order_possible_next_states( state_to_select))

        # return

        # for i in range(self.order_state.count()):
        #     self.order_state.removeItem(0)

        # current_ndx = ndx = 0
        # for o in states :
        #     self.order_state.addItem(o.description,o)
        #     if o == state_to_select:
        #         current_ndx = ndx
        #     ndx += 1

        # self.order_state.setCurrentIndex(current_ndx)


    def _show_blank_order(self,customer_id):

        operation_definition_cache.set_on_day(date.today())

        order = Order()
        order.customer_id = customer_id
        order.customer = dao.customer_dao.find_by_id_frozen( order.customer_id)
        self._show_order( order)
        operation_definition_cache.set_on_day( date.today())
        return



        # self._current_order = Order()
        # self._current_order.customer_id = customer_id
        # order = self._current_order
        #
        #
        # # self.current_order_id = order.order_id
        # # self.current_order_state = order.state
        # #self.current_comments = ""
        # #self.preorder_label = order.preorder_label
        # #self.sent_as_preorder = order.sent_as_preorder
        #
        # # self.low_pane2.set_model(None)
        # customer = self.refresh_customer(order.customer_id)
        # self.set_panel_title(u"New order\n{}".format(customer.fullname))
        #
        # # res = dao.operation_definition_dao.all_on_date(order.creation_date)
        # # self.controller_operation.prototype_at('operation_model').set_operation_definitions(res)
        # self.reset_indirects_view(None)
        # self.customer_order_name.setText(order.customer_order_name)
        # self.customer_preorder_name.setText(order.customer_preorder_name)
        # self.edit_comment_widget.setText(self._current_order.description)
        #
        # self.estimate_sent_date_label.setValue( order.sent_as_preorder)
        #
        # self.controller_part.model.clear()
        # self.controller_part.model.insertRows(0,1,QModelIndex())
        #
        # self._set_state(OrderStatusType.preorder_definition)
        # self.show_operations_for_part(0)
        #
        #
        # customer_name = ""
        # if order.customer_order_name:
        #     customer_name = order.customer_order_name.text()
        # elif order.customer_preorder_name:
        #     customer_name = order.customer_preorder_name.text()
        #
        # self.big_order_number.setText( order_number_title( order.preorder_label, order.accounting_label, customer_name))
        #
        # self.controller_part.view.setFocus(Qt.OtherFocusReason)
        # self.controller_part.view._setup_delegates()
        # self.controller_part.view.resizeRowsToContents()
        #
        #
        # sm = self.controller_operation.view.selectionModel()
        # if sm:
        #     sm.clearSelection()
        #
        # if self.controller_operation.model:
        #     self.controller_operation.view.setCurrentIndex(self.controller_operation.model.index(0,0))
        #
        # self.controller_part.view.selectionModel().clearSelection()
        # self.controller_part.view.setCurrentIndex(self.controller_part.model.index(0,0))
        # self.big_arrow.connect_to_left(self.controller_part.view)
        #
        # self.model_data_changed = False
        #
        #
        # self.controller_operation.view.horizontalHeader().setResizeMode(QHeaderView.ResizeToContents)
        # self.controller_operation.view.horizontalHeader().setResizeMode(1, QHeaderView.Stretch)



    def _show_order(self,order_id):


        chrono_click("EditOrderParts._show_order : 1 : query order {}".format(order_id))
        # sleep(1)

        if type(order_id) == int:
            # 0.80
            self._current_order = dao.order_dao.find_by_id_full_frozen(order_id)
        else:
            assert isinstance( order_id, Order)
            self._current_order = order_id

        order = self._current_order

        # self.edit_comment_widget.setText( order.description)
        self._current_order.description = order.description

        # if order.description:
        #     self.vsb_widget.show_widget(self.ecw)

        order_parts = order.parts
        self.customer_plate_widget.set_contact_data(order.customer)
        employees = audit_trail_service.who_touched_order(order.order_id, -1)
        # employees = []

        # 0.312
        #order = dao.order_dao.find_by_id_frozen(order_id)
        #order_parts = dao.order_part_dao.find_by_order_id_frozen(order_id)
        # self.refresh_customer(order.customer_id)
        # employees = audit_trail_service.who_touched_order(order.order_id, -1)
        # audit_trail_service.record("VIEW_ORDER", None, order.order_id)

        chrono_click("EditOrderParts._show_order : 2 : queried customers")

        self.current_customer_id = order.customer_id

        operation_definition_cache.set_on_day(order.creation_date)
        chrono_click("EditOrderParts._show_order : 3")
        # sleep(1)

        # self.current_order = order
        # self.current_order_id = order.order_id
        self._current_order.state = order.state
        self.model_data_changed = False

        # self.low_pane2.set_model(None)
        chrono_click("EditOrderParts._show_order : 4")

        # Makes sure we have the right operation models

        # res = dao.operation_definition_dao.all_on_date(order.creation_date)
        # self.controller_operation.prototype_at('operation_model').set_operation_definitions(res)
        # mainlog.debug("reload operations took {}".format(chrono_sec()))

        order_id = order.order_id
        # self.order_select.setText(str(order_id))
        #self.reset_indirects_view(order.order_id)
        chrono_click("EditOrderParts._show_order : 5")
        # sleep(1)

        # mainlog.debug("took {}".format(chrono_sec()))
        # self.controller_delivery_slip_part.model._buildModelFromObjects(self.current_order.delivery_slip_parts)
        self.customer_order_name.setText(order.customer_order_name)
        self.customer_preorder_name.setText(order.customer_preorder_name)


        self.estimate_sent_date_label.setValue(order.sent_as_preorder)

        self.last_edit_label.setText(_("Last edit by : {}").format(",".join(employees)))
        chrono_click("EditOrderParts._show_order : 6")

        # self.order_active.setChecked(order.active == True)

        # mainlog.debug("took {}".format(chrono_sec()))

        self.controller_part.model._buildModelFromObjects( order_parts)


        chrono_click("EditOrderParts._show_order : 7")
        # sleep(1)

        self._set_state(order.state)

        # self.accounting_label = order.accounting_label
        #self.preorder_label = order.preorder_label
        # self.sent_as_preorder = order.sent_as_preorder

        if order.accounting_label:
            order_number = _("Cde: {}").format(order.accounting_label)
        if order.preorder_label:
            preorder_number = _("Dev.: {}").format(order.preorder_label)

        self.estimate_sent_date_label.setValue(order.sent_as_preorder)
        self.order_title = order_number_title(order.preorder_label, order.accounting_label, self.customer_order_name.text())

        chrono_click("EditOrderParts._show_order : 8")
        # sleep(1)

        self.big_order_number.setText(u"<h1>{}</h1".format(self.order_title))
        self.title_widget.set_modified_flag(False)
        self.controller_part.view._setup_delegates()
        # self.controller_part.view.resizeColumnsToContents()
        self.controller_part.view.resizeRowsToContents()

        # sm = self.controller_operation.view.selectionModel()
        # if sm:
        #     sm.clearSelection()

        # if self.controller_operation.model:
        #     self.controller_operation.view.setCurrentIndex(self.controller_operation.model.index(0,0))

        # self.controller_part.view.selectionModel().clearSelection()

        self.big_arrow.connect_to_left(self.controller_part.view)

        self.set_panel_title( self._make_order_tab_label(order))
        chrono_click("EditOrderParts._show_order : 9 audit trail record")
        chrono_click("EditOrderParts._show_order : 10")

        # sleep(1)

    def _make_order_tab_label(self,order):
        labels = []
        if order.preorder_label and not order.accounting_label:
            labels.append(str(order.preorder_label))
        if order.accounting_label:
            labels.append(str(order.accounting_label))
        if order.customer_order_name:
            labels.append(order.customer_order_name)

        label = " / ".join(labels)

        # Label are expected to be show on tabs. Therefore, we
        # have to keep them small.

        MAX_TAB_TITLE_LENGTH = 23

        customer_name = order.customer.fullname or ""


        if len(label) > MAX_TAB_TITLE_LENGTH:
            label = label[0:(MAX_TAB_TITLE_LENGTH-3)] + "..."

        if len(customer_name) > MAX_TAB_TITLE_LENGTH:
            customer_name = customer_name[0:(MAX_TAB_TITLE_LENGTH-3)] + "..."

        label += "\n " + customer_name

        return str(label)


    @Slot(QModelIndex,QModelIndex)
    def order_part_selection_changed(self, current, previous):
        mainlog.debug("order_part_selection_changed : cur.row = {}".format(current.row()))
        # The cursor has moved in the left part (the order part)
        # So we may want to change the list of operations in the right
        # part

        if not current.isValid() or self.controller_part.model.rowCount() == 0:
            self.controller_operation.setModel(None)
            # self.controller_operation.view.setEditTriggers(QAbstractItemView.NoEditTriggers)

        elif not previous.isValid() or (current.row() != previous.row()):

            r = min( max(0,current.row()), self.controller_part.model.rowCount() - 1)
            mainlog.debug("order_part_selection_changed : row is {}".format(r))
            self.show_operations_for_part(r)
            if self.controller_operation.model:
                self.controller_operation.view.setCurrentIndex(self.controller_operation.model.index(0,0))

            mainlog.debug("showing {} documents".format(self.controller_part.model.documents[r]))

            self.documents_widget.set_model(self.controller_part.model.documents[r])
            self.quality_widget.set_quality_events( self.controller_part.model.quality_event_models[r])

            # mainlog.debug("Setting comments widget, new value is : {}".format( self.controller_part.model.comments[r]))

            self.edit_comment_widget.blockSignals(True)
            # Avoid recursive loop with the signal "textChanged" that will trigger an update here.

            cmt, cmt_changed = self.controller_part.model.comments[r]
            self.edit_comment_widget.setText( cmt)

            # self.edit_comment_widget.setText(self.controller_part.model.object_at(r).notes)

            self.edit_comment_widget.blockSignals(False)

            # self.vsb_widget.show_star_on_widget(self.documents_widget,show=(len(order.documents) > 0))

    @Slot()
    def estimated_hours_on_operation_changed(self):

        mainlog.debug("estimated_hours_on_operation_changed !")
        ndx = self.controller_part.view.currentIndex()
        operations_model = self.controller_part.model.submodels[ndx.row()]

        planned_hours = operations_synthesis( operations_model.read_only_objects())

        qty = self.controller_part.model.row_field_value(ndx.row(), "qty")

        if qty is None:
            self.controller_part.model.row_field_updated( ndx.row(), 'total_estimated_time', None)
        else:
            self.controller_part.model.row_field_updated( ndx.row(), 'total_estimated_time', qty*planned_hours)

        #
        # self.order_part.total_estimated_time = planned_hours * self.order_part.qty
        #
        # # self.order_parts_model.update_cell( )
        # self.order_parts_model.object_field_updated(self.order_part, 'total_estimated_time')

        pass
        # print("estimated_hours_on_operation_changed")
        # self.controller_part.model

    @Slot()
    def cannot_delete_row(self):
        showWarningBox(_("Hours reported on operation"),
                       _("You cannot delete this operation because there is work reported on it."))

    def show_operations_for_part(self,ndx):

        chrono_click("show_operations_for_part : ndx is {}".format(ndx))
        # mainlog.debug("objects is {} items long".format(len(self.controller_part.model.objects)))
        # mainlog.debug("objects is {}".format(self.controller_part.model.objects))


        order_part = self.controller_part.model.objects[ndx]
        if order_part and order_part.state:
            # newly added part have no objects assocaited to them (that's strange)
            self.order_part_state_label.setText("<b>{}</b>".format(order_part.state.description))
        else:
            self.order_part_state_label.setText("/")

        # FIXME This may be run more than once, and that's not 100% right !

        if not self.controller_part.model.has_submodels():
            # mainlog.debug("Disconnecting model for operations")
            self.controller_operation.setModel(None)
        else:
            # mainlog.debug("Showing model for operations {}".format(ndx))
            # QAbstractItemView::PositionAtCenter

            # chrono_click("show_operations_for_part : 1")
            op_model = self.controller_part.model.submodel(ndx)

            # op_model.documents = documents_service.find_by_order_part_id(part.order_part_id)

            # chrono_click("show_operations_for_part : 2")

            # mainlog.debug("Have we got a model ? {}".format(op_model is not None))
            self.controller_operation.setModel(op_model)
            if op_model not in self.signalled_operation_models:
                self.signalled_operation_models.add(op_model)
                op_model.estimated_hours_changed.connect(self.estimated_hours_on_operation_changed)

                op_model.rowsInserted.connect( self.estimated_hours_on_operation_changed)
                op_model.rowsRemoved.connect( self.estimated_hours_on_operation_changed)
                op_model.row_protected.connect( self.cannot_delete_row)

            # chrono_click("show_operations_for_part : 3")

            # mainlog.debug("Connecting edit triggers")

            self.controller_operation.view.setEditTriggers(QAbstractItemView.EditKeyPressed | QAbstractItemView.AnyKeyPressed | QAbstractItemView.DoubleClicked)

            # Since I change the model, I must reconnect the selection model as well
            self.controller_operation.view.selectionModel().currentChanged.connect(self.operation_selection_changed) # FIXME Clear ownership issue




        # self.controller_operation.view.resizeRowsToContents()
        # self.controller_operation.view.resizeColumnsToContents()

        self.big_arrow.connect_to_right(self.controller_operation.view)
        self.compute_cost()




    def amount_to_str(self, amount):
        if amount is None:
            return u"/ " + EURO_SIGN
        else:
            # Display an amount in the french/belgian way
            t = u"<b>{:,.2f}</b>".format(amount).replace(u",",u" ").replace(u".",u",")
            return t + EURO_SIGN

    SELL_PRICE_COLUMN = 6

    def compute_cost(self):
        # mainlog.debug("Comput ecost")
        m = self.controller_operation.model

        if m is None:
            self.value_label.setValue(None)
            self.unit_cost_label.setValue(None)
            # self.actual_cost_label.setValue(None)
            # self.total_selling_price_label.setValue(None)
            # self.benefit_label.setValue(None)
            return

        total_hours_cost = 0
        total_values = 0
        total_planned_hours_cost = 0
        total_unit_cost = 0

        for r in range(m.rowCount()):

            value = zerofloat(m.index(r,2).data(Qt.UserRole))
            time_planned = zerofloat(m.index(r,3).data(Qt.UserRole))
            time_consumed = zerofloat(m.index(r,4).data(Qt.UserRole))

            op = None
            op_id = m.index(r,0).data(Qt.UserRole)
            if op_id:
                op = operation_definition_cache.opdef_by_id(op_id)

            if op: # The data is an OperationDefinition
                # BUG cost must be on order.creation_date (date.today() now for code simplication)
                cost = operation_definition_cache.cost_by_id(op_id)
            else:
                cost = 0

            # mainlog.debug("value={},time_planned={},time_consumed={},cost={}".format(value,time_planned,time_consumed,cost))
            total_values += value
            # total_planned_hours_cost += cost * time_planned
            total_planned_hours_cost += operation_unit_cost(value, time_planned, cost)

            total_hours_cost += float(cost) * time_consumed

        # mainlog.debug("Compute cost {}".format(total_values))

        self.value_label.setValue(total_values)
        self.unit_cost_label.setValue(total_planned_hours_cost)
        # self.actual_cost_label.setValue(total_values + total_hours_cost)

        if not self.controller_part.view.currentIndex().isValid():
            return

        # Quantity on the order (target quantity)

        r = self.controller_part.view.currentIndex().row()


        quantity = zeroint(self.controller_part.model.index(r,1).data(Qt.UserRole))
        sell_price_unit = zerofloat(self.controller_part.model.index(r,self.SELL_PRICE_COLUMN).data(Qt.UserRole)) # FIXME Hardcoded index !

        self.part_price_label.setValue(quantity*sell_price_unit)

        # Global computations for the whole order

        m = self.controller_part.model

        total_selling_price = 0
        total_hours_done = 0
        total_hours_planned = 0
        for i in range(m.rowCount()):
            total_selling_price += zerofloat(m.index(i,self.SELL_PRICE_COLUMN).data(Qt.UserRole)) * zerofloat(m.index(i,1).data(Qt.UserRole))
            total_hours_done += zerofloat(m.index(i,5).data(Qt.UserRole))
            total_hours_planned += zerofloat(m.index(i,4).data(Qt.UserRole))
            # mainlog.debug(total_selling_price)

        # self.selling_price_label.setValue(sell_price_unit)
        # self.quantity_label.setText("<b>{}</b>".format(quantity))
        self.total_selling_price_label.setValue(total_selling_price)
        self.total_hours_planned_label.setText("<b>" + (duration_to_s(total_hours_planned) or "0"))
        self.total_hours_done_label.setText("<b>" + (duration_to_s(total_hours_done) or "0"))
        return

    @Slot()
    def _quality_issues_changed(self):
        # If the quality issues list has changed, then so has the order
        self.data_changed_slot(None)

    @Slot()
    def documents_updated_slot(self):
        # If the documents list has changed, then so has the order
        self.data_changed_slot(None)

        # We attach the updated documents list to the part.
        # It's a full copy of it (not very model oriented...)
        row_ndx = self.controller_part.view.currentIndex().row()
        mainlog.debug("EditOrderParts.documents_updated_slot row {}".format(row_ndx))
        if row_ndx >= 0:
            self.controller_part.model.documents[row_ndx] = self.documents_widget.model

            if self.documents_widget.model.rowCount() > 0 and \
               self.controller_part.model.isRowEmpty(row_ndx):

                showWarningBox( _("The documents are associated to an empty order part."),
                                _("If you leave the part empty, they won't be saved"))

            # self.vsb_widget.show_star_on_widget(self.documents_widget,show=(len(order.documents) > 0))


    @Slot()
    def part_comment_changed(self):

        part_ndx = self.controller_part.view.currentIndex().row()
        new_comment = self.edit_comment_widget.toPlainText()
        mainlog.debug("Getting comments widget, it is : {}, part_ndx = {}".format( new_comment, part_ndx))
        self.controller_part.model.comments[ part_ndx] = ( new_comment, True )
        self.data_changed_slot(None)

        # self.controller_part.model.submodels[self.controller_part.view.currentIndex().row()].set_notes(new_comment)

    @Slot()
    def state_changed_slot(self):
        self.data_changed_slot(None)

    @Slot(QStandardItem)
    def data_changed_slot(self,item):
        self.model_data_changed = True
        if item:
            self.compute_cost()
        self.title_widget.set_modified_flag(True)

        # order_part_ndx = item.index()


    def reset_indirects_view(self,order_id):
        return

        # global  db_engine

        # if order_id is None:
        #     self.indirects.setRowCount(0)
        #     return

        # chrono_start()

        # # FIXME Super dirty
        # c = db_engine().connect()

        # s = select([OperationDefinition.description,
        #             Employee.fullname,
        #             func.sum(TimeTrack.duration),
        #             OperationDefinition.operation_definition_id,
        #             Employee.employee_id],
        #            from_obj=TaskOnOrder.__table__.join(Task.__table__).join(TimeTrack.__table__).join(Employee.__table__).join(OperationDefinition.__table__)).\
        #            where(TaskOnOrder.order_id == order_id).\
        #            group_by(OperationDefinition.operation_definition_id,
        #                     OperationDefinition.description,
        #                     Employee.fullname,
        #                     Employee.employee_id)

        # res = c.execute(s).fetchall()
        # self.indirects.setRowCount(len(res))

        # row_ndx = 0
        # for row in res:
        #     # mainlog.debug("{} {}-{}".format(row,row_ndx,len(row)))
        #     for col_ndx in range(0,len(row)):
        #         self.indirects.setData(self.indirects.index(row_ndx,col_ndx),row[col_ndx],Qt.DisplayRole)
        #         if col_ndx == 4:
        #             self.indirects.setData(self.indirects.index(row_ndx,0),row[col_ndx],Qt.UserRole)
        #     row_ndx += 1

        # # mainlog.debug("Time to read indirects : {}s".format( chrono_sec()))


    def panel_content_hash(self):

        # So we won't be able to open two tabs for the same order/customer
        # nor two tabs with two new orders for the same customer

        h = (self._current_order.customer_id, self._current_order.order_id)

        # h = id(self._current_order)
        mainlog.debug("This edit order panel : hash {}".format(h))

        return h

    def __init__(self,parent,find_order_slot,show_price_values : bool, remote_documents_service):
        """

        :param parent: Usual Qt parent.
        :param find_order_slot:
        :param show_price_values: Should we show price values (useful to hide information)
        :param remote_documents_service: The documents service to use. Passed in so that tests
               can use mocks.
        :return:
        """

        super(EditOrderPartsWidget,self).__init__(parent)

        self.signalled_operation_models = set()
        self.remote_documents_service = remote_documents_service
        self.cloned = None
        self._current_order = Order()
        #self.current_comments = ""
        #self.sent_as_preorder = None
        self.reenter = False

        self.customer_plate_widget = PoppingCustomerPlateWidget(self)
        self.big_order_number = QLabel('ORDER')

        navigation = NavBar( self,
                             [ (_("< cust"), self.show_previous_customer_order),
                               (_("< active"),self.show_previous_active_order),
                               (_("<"),self.show_previous_order),
                               (_("Action"),self.show_actions),
                               (_(">"),self.show_next_order),
                               (_("> active"),self.show_next_active_order),
                               (_("> cust"),self.show_next_customer_order),
                               (_("Find"), find_order_slot)] )


        navigation.buttons[3].setObjectName("specialMenuButton")
        navigation.buttons[7].setObjectName("specialMenuButton")

        self.title_widget = TitleWidget(_("Order status"),self,navigation)

        head_layout = QHBoxLayout()
        head_layout.addWidget(self.big_order_number)
        head_layout.addStretch()
        head_layout.addWidget(self.customer_plate_widget)


        self.order_state_label = OrderStateEdit("order_state",_("State")) # OrderStateLabel()
        self.order_state_label.signal_state_changed.connect(self.state_changed_slot)

        # hlayout.addWidget(QLabel(_("Order ID :")))
        # self.order_select = OrderNumberLineEdit("new",self)
        # hlayout.addWidget(self.order_select)

        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel(_("Customer order ID :")))
        self.customer_order_name = QLineEdit("",self)
        self.customer_order_name.textEdited.connect(self.customer_order_name_edited)
        hlayout.addWidget(self.customer_order_name)

        # hlayout.addWidget(QLabel(_("Customer preorder ID :")))

        self.customer_preorder_name = QLineEdit("",self)
        self.customer_preorder_name.textEdited.connect(self.customer_preorder_name_edited)
        self.customer_preorder_name.setEnabled(False)
        self.customer_preorder_name.setVisible(False)

        hlayout.addWidget(self.customer_preorder_name)
        hlayout.addWidget(QLabel(_("State ")))
        hlayout.addWidget(self.order_state_label.widget)

        self.estimate_sent_date_label = FlexiLabel(converter=lambda v: _("Estimate sent on {}").format(date_to_s(v)) if v else _("Estimate not sent."))
        hlayout.addWidget(self.estimate_sent_date_label)

        hlayout.addStretch()
        self.last_edit_label = QLabel(_("Last edit by : {}").format(""))
        hlayout.addWidget(self.last_edit_label)

        top_layout = QVBoxLayout()
        top_layout.addWidget(self.title_widget)

        head_layout.setContentsMargins(4,0,4,0)
        top_layout.addWidget(InlineSubFrame(head_layout,None))
        top_layout.addLayout(hlayout) # Takes ownership^of the layout

        self.current_customer_id = None
        #self.current_order_id = None
        self.target_order_id = None
        self.current_order = None
        self.current_customer = None
        #self.current_order_state = None
        self.new_order = None
        self.model_data_changed = False
        self.customer_changed = False

        #self.indirects = QStandardItemModel(1,3)

        chrono_click("__init__ : 0")

        # htext = [_("Indirect"),_("Employee"),_("Hours")]
        # headers = QStandardItemModel(1, len(htext))
        # i = 0
        # for h in htext:
        #     headers.setHeaderData(i, Qt.Orientation.Horizontal, h)
        #     i = i + 1
        #
        # # Indirects
        #
        # self.headers_view = QHeaderView(Qt.Orientation.Horizontal,self)
        # self.header_model = headers
        # self.headers_view.setModel(self.header_model) # qt's doc : The view does *not* take ownership

        # self.indirects_view = TableViewSignaledEvents(self) # QTableView()
        # self.indirects_view.setModel(self.indirects)
        # self.indirects_view.setHorizontalHeader(self.headers_view)
        # self.indirects_view.horizontalHeader().setResizeMode(QHeaderView.ResizeToContents)
        # self.indirects_view.setVerticalHeader(None)
        # self.indirects_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        # self.indirects_view.setSelectionMode(QAbstractItemView.SingleSelection)
        # self.indirects_view.selectionModel().currentRowChanged.connect(self.indirect_current_row_changed)
        # self.indirects_view.focusIn.connect(self.indirects_focus_in)
        # self.indirects_view.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # self.indirects_view.

        # self.reset_indirects_view(None)

        delivery_slip_part_prototype = []
        delivery_slip_part_prototype.append( IntegerNumberPrototype('delivery_slip_id',_('Slip number'),editable=False))
        delivery_slip_part_prototype.append( OrderPartDisplayPrototype('order_part',_('Order part'),editable=False))
        delivery_slip_part_prototype.append( FloatNumberPrototype('quantity_out',_('Quantity'),editable=False))

        v = PrototypedTableView(None,delivery_slip_part_prototype)
        self.controller_delivery_slip_part = PrototypeController(self,delivery_slip_part_prototype,v)
        self.controller_delivery_slip_part.setModel(TrackingProxyModel(None,delivery_slip_part_prototype))

        order_part_prototype = []
        # order_part_prototype.append( TextLinePrototype('human_position',_('ID'),editable=False))
        order_part_prototype.append( TextAreaPrototype('description',_('Description'),nullable=False))
        order_part_prototype.append( IntegerNumberPrototype('qty',_('Qty'),nullable=True))
        # order_part_prototype.append( IntegerNumberPrototype('total_delivered_quantity_this_month',_('Q Ex'),editable=False))
        order_part_prototype.append( IntegerNumberPrototype('tex2',_('Q.Ex'),editable=False))
        order_part_prototype.append( FutureDatePrototype('deadline',_('D/line'),nullable=True))
        # order_part_prototype.append( FloatNumberPrototype('eff',_('Effective'),nullable=True))
        # order_part_prototype.append( FloatNumberPrototype('qa',_('QA'),nullable=True,editable=False))
        order_part_prototype.append( DurationPrototype('total_estimated_time',_('Total\nH.Pl'),nullable=True,editable=False))
        self.ndx_column_total_hours = len(order_part_prototype)
        order_part_prototype.append( DurationPrototype('total_hours',_('Total\nH.Done'),editable=False))

        self.SELL_PRICE_COLUMN = len(order_part_prototype)

        self.show_price_values = show_price_values

        if self.show_price_values:
            order_part_prototype.append( FloatNumberPrototype('sell_price',_('Sell\nprice'),editable=True))


        order_part_prototype = PrototypeArray(order_part_prototype)

        chrono_click("__init__ : 1")

        operation_prototype = []
        operation_prototype.append( OperationDefinitionPrototype('operation_definition_id',_('Op.'),operation_definition_cache.all_on_order_part()))
        operation_prototype.append( TextAreaPrototype('description',_('Description'),nullable=True))
        if self.show_price_values:
            operation_prototype.append( FloatNumberPrototype('value',_('Value'),nullable=True,editable=is_value_editable))
            self.value_price_column = len(operation_prototype) - 1
        else:
            self.value_price_column = -1
        operation_prototype.append( DurationPrototype('planned_hours',_('Planned time'),nullable=True,editable=are_planned_hours_editable))
        self.planned_hour_column = len(operation_prototype) - 1
        # operation_prototype.append( DurationPrototype('t_reel',_('Used time'),nullable=False,editable=False))
        operation_prototype.append( DurationPrototype('done_hours',_('Imputations'),editable=False))
        # operation_prototype.append( TextLinePrototype('note',_('Note'),editable=True,nullable=True,hidden=True))

        operation_prototype = PrototypeArray(operation_prototype)

        self.controller_part = PrototypeController(self,
                                                   order_part_prototype,
                                                   ProxyTableView(None,order_part_prototype))

        m = TModel(None,order_part_prototype,operation_prototype)
        m.submodelCreated.connect(self.submodelCreated)

        self.controller_part.setModel(m)
        self.controller_part.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.controller_part.view.customContextMenuRequested.connect(self.show_order_parts_popup)

        # self.controller_part.model.rowsInserted.connect(self.order_part_rows_inserted)

        self.controller_operation = PrototypeController(self,
                                                        operation_prototype,
                                                        ProxyTableView(None,operation_prototype))

        self.controller_operation.view.focusIn.connect(self.operations_focus_in)
        self.controller_operation.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.controller_operation.view.customContextMenuRequested.connect(self.show_operations_popup)

        # FIXME Clear ownership issues if any

        # order_layout = QHBoxLayout()
        # order_layout.addWidget(self.controller_part.view)
        # order_layout.addWidget(self.controller_operation.view)

        chrono_click("__init__ : 1b")

        self.opinfo_layout = QHBoxLayout()
        self.opinfo_layout.setSpacing(10)

        self.opinfo_layout.addWidget( QLabel(_("Values")))
        self.value_label = EuroLabel()
        self.opinfo_layout.addWidget( self.value_label)


        self.opinfo_layout.addWidget( QLabel(_("Unit cost")))
        self.unit_cost_label = EuroLabel()
        self.opinfo_layout.addWidget( self.unit_cost_label)

        self.opinfo_layout.addWidget( QLabel(_("Order part state")))
        self.order_part_state_label = QLabel()
        self.opinfo_layout.addWidget( self.order_part_state_label)

        # self.opinfo_layout.addWidget( QLabel(_("Unit price")))
        # self.selling_price_label = EuroLabel()
        # self.opinfo_layout.addWidget( self.selling_price_label)


        self.opinfo_layout.addStretch()

        self.opinfo2_layout = QHBoxLayout()
        self.opinfo2_layout.setSpacing(10)

        self.opinfo2_layout.addWidget( QLabel(_("Total selling price")))
        self.total_selling_price_label = EuroLabel()
        self.opinfo2_layout.addWidget( self.total_selling_price_label)

        self.opinfo2_layout.addWidget( QLabel(_("Part price")))
        self.part_price_label = EuroLabel()
        self.opinfo2_layout.addWidget( self.part_price_label)

        self.opinfo2_layout.addWidget( QLabel(_("H. planned")))
        self.total_hours_planned_label = QLabel()
        self.opinfo2_layout.addWidget( self.total_hours_planned_label)

        self.opinfo2_layout.addWidget( QLabel(_("H. done")))
        self.total_hours_done_label = QLabel()
        self.opinfo2_layout.addWidget( self.total_hours_done_label)

        # self.opinfo2_layout.addWidget( QLabel(_("Quantity")))
        # self.quantity_label = QLabel()
        # self.opinfo2_layout.addWidget( self.quantity_label)

        # self.opinfo2_layout.addWidget( QLabel(_("Actual cost")))
        # self.actual_cost_label = EuroLabel()
        # self.opinfo2_layout.addWidget( self.actual_cost_label)

        # self.opinfo2_layout.addWidget( QLabel(_("Benefit")))
        # self.benefit_label = EuroLabel()
        # self.opinfo2_layout.addWidget( self.benefit_label)

        self.opinfo2_layout.addStretch()
        chrono_click("__init__ : 1c")

        # self.note_label = QLabel("Note")
        # self.opinfo_layout.addWidget( self.note_label)
        # self.opinfo_layout.addStretch()

        self.opinfo3_layout = QVBoxLayout()
        self.opinfo3_layout.addLayout(self.opinfo_layout)

        self.partinfo_layout = QVBoxLayout()
        self.partinfo_layout.addLayout(self.opinfo2_layout)

        # detail_layout = QHBoxLayout()
        # self.low_pane2 = EditableEmployeeFacesViewSimple(self)
        # self.low_pane2.set_model(None)
        # self.low_pane2.setMinimumHeight(165) # The super minimum
        # self.low_pane2.setMaximumHeight(165)
        # self.low_pane2.setMaximumWidth(800)

        # self.controller_part.view.setMinimumWidth(950)
        # self.controller_part.view.setColumnWidth(0,200)
        # self.controller_operation.view.setMinimumWidth(500)
        # self.controller_operation.view.setColumnWidth(1,250)

        chrono_click("__init__ : 2 : building more UI")

        # splitter = QSplitter(Qt.Vertical,self)

        self.big_arrow = BigArrow(self)


        self.op_traits_widget = OperationTraitsEditWidget()
        self.op_traits_widget.hide()

        ops_layout = QVBoxLayout()
        ops_layout.addWidget(self.controller_operation.view)
        ops_layout.addWidget(self.op_traits_widget)

        gridlayout = QGridLayout()
        gridlayout.setHorizontalSpacing(0)
        gridlayout.addWidget(self.controller_part.view,0,0)
        gridlayout.addWidget(self.big_arrow,0,1)
        # gridlayout.addWidget(self.controller_operation.view,0,2)
        gridlayout.addLayout(ops_layout,  0,2)
        gridlayout.addLayout(self.partinfo_layout,  1,0)
        gridlayout.addLayout(self.opinfo3_layout,   1,2)

        # self.gridlayout.setContentsMargins(0,0,0,0)

        # hlayout = QHBoxLayout()
        # hlayout.setSpacing(0)
        # hlayout.addWidget(self.controller_part.view)
        # hlayout.addWidget(self.big_arrow)
        # hlayout.addWidget(self.controller_operation.view)

        # self.parts_operation = QWidget(splitter)

        chrono_click("__init__ : 2 : building more UI - a")

        # self.documents_widget = QWidget()

        self.documents_widget = DocumentCollectionWidget(self, self.remote_documents_service, used_category_short_name=[])
        self.documents_widget.documents_list_changed.connect(self.documents_updated_slot)
        self.documents_widget.show_description = False
        # self.documents_widget.layout().setContentsMargins(0,0,0,0)

        self.edit_comment_widget = DescribedTextEdit(_("No comments"))
        self.edit_comment_widget.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Preferred)
        self.edit_comment_widget.textChanged.connect(self.part_comment_changed)

        ecw_layout = QVBoxLayout()
        ecw_layout.addWidget(QLabel(u"<h3>{}</h3>".format(_("Comments"))))
        ecw_layout.addWidget(self.edit_comment_widget)
        ecw_layout.setStretch(0,0)
        ecw_layout.setStretch(1,1)

        # self.ecw = QWidget()
        # self.ecw.setLayout(l)

        # mainlog.debug("__init__ 7 {}".format(sleep(1)))


        side_layout = QVBoxLayout()
        side_layout.addLayout(ecw_layout)
        side_layout.addWidget(self.documents_widget)
        side_frame = SubFrame(None,side_layout,None)

        # Old Horse
        # hl = QHBoxLayout()
        # hl.addLayout(gridlayout)
        # hl.addWidget(side_frame)
        # hl.setStretch(0,1)
        # hl.setStretch(1,0)
        # top_layout.addLayout(hl)

        # ------------------------------------------
        chrono_click("__init__ : 2 : building more UI - b")

        # from koi.datalayer.quality import Comment

        self.quality_widget = NonconformitiesWidget(self, self.remote_documents_service)
        self.quality_widget.issues_changed.connect(self._quality_issues_changed)

        chrono_click("__init__ : 2 : building more UI - f")
        # sleep(5)

        self.vsb_widget = VerticalSideBarLayout(gridlayout,[side_frame,self.quality_widget],parent=self)
        top_layout.addWidget(self.vsb_widget)

        # -TRACE- Doesn't remove the crash :
        # test_layout = QHBoxLayout()
        # test_layout.addLayout(gridlayout)
        # test_layout.addWidget(side_frame)
        # test_layout.addWidget(self.quality_widget)
        # top_layout.addLayout(test_layout)

        chrono_click("__init__ : 2 : building more UI - f")
        #sleep(5)

        self.setLayout(top_layout) # top_layout)

        top_layout.setStretch(0,1)
        top_layout.setStretch(1,1)
        top_layout.setStretch(2,1)
        top_layout.setStretch(3,1000)


        # ------------------------------------------
        chrono_click("__init__ : 3 shadow...")

        self.controller_part.model.dataChanged.connect(self.data_changed_slot)
        self.controller_part.model.rowsInserted.connect(self.data_changed_slot)
        self.controller_part.model.rowsRemoved.connect(self.data_changed_slot)
        self.controller_part.model.dataChanged.connect(self.order_part_data_changed)

        self.controller_part.view.horizontalHeader().setResizeMode(QHeaderView.ResizeToContents)
        self.controller_part.view.horizontalHeader().setResizeMode(0, QHeaderView.Stretch)
        self.controller_part.view.verticalHeader().setResizeMode(QHeaderView.ResizeToContents)

        self.controller_operation.view.horizontalHeader().setResizeMode(QHeaderView.ResizeToContents)
        self.controller_operation.view.horizontalHeader().setResizeMode(1, QHeaderView.Stretch)
        # self.controller_operation.view.verticalHeader().setResizeMode(QHeaderView.ResizeToContents)
        # self.controller_operation.view.verticalHeader().hide()

        self.controller_part.view.enable_edit_panel()
        self.controller_operation.view.enable_edit_panel()


        self.controller_part.view.setWordWrap(True)
        self.controller_operation.view.setWordWrap(True)

        self.controller_part.view.selectionModel().currentChanged.connect(self.order_part_selection_changed) # FIXME Clear ownership issue

        self.previous_order_action = QAction(_("Previous order"),self)
        self.previous_order_action.triggered.connect( self.show_previous_order)
        self.previous_order_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_PageUp))
        self.previous_order_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.addAction(self.previous_order_action)

        self.next_order_action = QAction(_("Next order"),self)
        self.next_order_action.triggered.connect( self.show_next_order)
        self.next_order_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_PageDown))
        self.next_order_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.addAction(self.next_order_action)


        self.previous_customer_order_action = QAction(_("Previous order"),self)
        self.previous_customer_order_action.triggered.connect( self.show_previous_customer_order)
        self.previous_customer_order_action.setShortcut(QKeySequence(Qt.SHIFT + Qt.Key_PageUp))
        self.previous_customer_order_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.addAction(self.previous_customer_order_action)

        self.next_customer_order_action = QAction(_("Next order"),self)
        self.next_customer_order_action.triggered.connect( self.show_next_customer_order)
        self.next_customer_order_action.setShortcut(QKeySequence(Qt.SHIFT + Qt.Key_PageDown))
        self.next_customer_order_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.addAction(self.next_customer_order_action)

        self.previous_active_order_action = QAction(_("Previous order"),self)
        self.previous_active_order_action.triggered.connect( self.show_previous_active_order)
        self.previous_active_order_action.setShortcut(QKeySequence(Qt.ALT + Qt.Key_PageUp))
        self.previous_active_order_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.addAction(self.previous_active_order_action)

        self.next_active_order_action = QAction(_("Next order"),self)
        self.next_active_order_action.triggered.connect( self.show_next_active_order)
        self.next_active_order_action.setShortcut(QKeySequence(Qt.ALT + Qt.Key_PageDown))
        self.next_active_order_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.addAction(self.next_active_order_action)



        self.copy_parts_action = QAction(_("Copy order parts"),self.controller_part.view)
        self.copy_parts_action.triggered.connect( self.copy_parts_slot)
        self.copy_parts_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_C))
        self.copy_parts_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.controller_part.view.addAction(self.copy_parts_action)

        self.paste_parts_action = QAction(_("Paste order parts"),self.controller_part.view)
        self.paste_parts_action.triggered.connect( self.paste_parts_slot)
        self.paste_parts_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_V))
        self.paste_parts_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.controller_part.view.addAction(self.paste_parts_action)

        self.find_operations_action = QAction(_("Copy operations"),self.controller_operation.view)
        self.find_operations_action.triggered.connect( self.copy_operations_slot)
        self.find_operations_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_C))
        self.find_operations_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.controller_operation.view.addAction(self.find_operations_action)

        self.paste_operations_action = QAction(_("Paste operations"),self.controller_operation.view)
        self.paste_operations_action.triggered.connect( self.paste_operations_slot)
        self.paste_operations_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_V))
        self.paste_operations_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.controller_operation.view.addAction(self.paste_operations_action)


        self.action_menu = QMenu(navigation.buttons[3])

        # self.state_menu = QMenu("Change state")
        # self.state_menu.addAction("alpha")
        # self.state_menu.addAction("beta")


        self._print_bill_of_operations_menu = QMenu(_("Print operations"))

        bop_actions = [ (_("Print all"), self.orderPrint,        QKeySequence(Qt.CTRL + Qt.Key_P),None),
                        (_("Print selected"), self.print_bill_of_operations_selected,
                         QKeySequence("Ctrl+Shift+P"),None) ]

        populate_menu( self._print_bill_of_operations_menu, self, bop_actions, context=Qt.WidgetWithChildrenShortcut)

        list_actions = [ (_("Save order"),self.save_button_clicked,        QKeySequence(Qt.CTRL + Qt.Key_S),None),
                         ( self._print_bill_of_operations_menu, None, None ),
                         #(_("Print operations"),self.orderPrint,           QKeySequence(Qt.CTRL + Qt.Key_P),None),
                         (_("Print as preorder"),self.preorderPrint,       None,[RoleType.view_prices]),
                         (_("Print as preorder 2"),self.preorder_report,       None,[RoleType.view_prices]),
                         (_("Activity report"),self.activity_report,       None,None),
                         (_("Order confirmation report"),self.order_confirmation_report,       None,None),
                         # (self.find_operations_action,None),
                         # (self.paste_operations_action,None),
                         (_("Delete"),self.delete_button_clicked, None,None),
                         # (self.state_menu,None,       None,None),
                         (_("Change customer"),self.change_customer,       None,None),
                         (_("Change estimate date"),self.change_estimate_sent_date,       None,None),
                         (_("Audit report"),self.audit_report,       None,[RoleType.view_audit]) ]


        populate_menu(self.action_menu, self, list_actions, context=Qt.WidgetWithChildrenShortcut)

        self.__scroll_to_part_timer = QTimer(self)
        self.__scroll_to_part_timer.setSingleShot(True)
        self.__scroll_to_part_timer.timeout.connect(self.__scroll_to_part) # timerUpdate)

    def data_changed(self):
        mainlog.debug("data_changed: {}".format(self.model_data_changed))
        mainlog.debug("data_changed: {} =? {}".format(self.order_state_label.value, self._current_order.state))
        # mainlog.debug("data_changed: {} =? {}".format(self.edit_comment_widget.toPlainText(), self._current_order.description))
        mainlog.debug("data_changed: {}".format(self.customer_changed))
        mainlog.debug("data_changed: {} =? {}".format(self.estimate_sent_date_label.value(), self._current_order.sent_as_preorder))

        for cmt, changed in self.controller_part.model.comments:
            if changed:
                mainlog.debug("data_changed: some notes have changed")
                return True

        # (self.edit_comment_widget.toPlainText() or "") != (self._current_order.description or "") or \
        return self.model_data_changed or \
               self.order_state_label.value != self._current_order.state or \
               self.customer_changed or \
               self.estimate_sent_date_label.value() != self._current_order.sent_as_preorder


    def needs_close_confirmation(self):
        return self.data_changed()

    def confirm_close(self):
        return self.save_if_necessary()

    def _force_save(self):
        if self.save() != False:  # FIXME defensive, make sure it's True
            # Because when I save, although the order definition is
            # not meant to change, the order numbers (accounting label,
            # etc.) might actually change.
            self.refresh_order()
            return True
        else:
            return False

    def save_if_necessary(self):
        """ True if the user has either said he doesn't want to save or
        he saved successufly. False if the user has cancelled (no save, no "no save")
        or the save operation has failed """

        # mainlog.debug("save_if_necessary : customer_changed = {}".format(self.customer_changed))
        # mainlog.debug("save_if_necessary : selected state = {}".format(self.order_state.itemData(self.order_state.currentIndex())))
        # mainlog.debug("save_if_necessary : state on opening = {}".format(self.current_order_state))

        if self.data_changed():
            ynb = yesNoBox(_("Data were changed"),
                           _("You have changed some of the data in this. Do you want to save before proceeding ?"))
            if ynb == QMessageBox.Yes:
                return self._force_save()
            elif ynb == QMessageBox.No:
                return True
            elif ynb == QMessageBox.Cancel:
                return False
        else:
            return True

    @Slot()
    def delete_button_clicked(self):
        global dao

        if not self._current_order.order_id:
            showErrorBox(_("No order or non-saved order selected"),
                         _("You can only delete an order that has already been saved"),
                         object_name="delete_only_saved_order")
            return
        else:
            # Make sure we have up to date information
            # This is necessary in case the current_order object
            # is dirty (e.g. because of a previously failed
            # transaction)

            check = dao.order_dao.check_delete(self._current_order.order_id)

            if check == True:

                s = None

                if self._current_order.accounting_label:
                    s = _("About to delete order {}").format( self._current_order.accounting_label)
                else:
                    s = _("About to delete preorder {}").format( self._current_order.preorder_label)

                if confirmationBox(s,_("Are you sure ?")):
                    try:
                        dao.order_dao.delete(self._current_order.order_id)
                    except Exception as ex:
                        makeErrorBox(_("There was an error while deleting the order"),str(ex)).exec_()
                        return

                    self.set_on_last_order_if_any()
                    # self.order_changed_signal.emit()

            elif check == dao.order_dao.CANNOT_DELETE_BECAUSE_ORDER_HAS_TIMETRACKS:
                makeErrorBox(_("A part of the order already have time reported on it"),
                             _("You can only delete an order if none of its parts has time reported on it")).exec_()
            elif check == dao.order_dao.CANNOT_DELETE_BECAUSE_ORDER_IS_NOT_LAST:
                makeErrorBox(_("You can only delete an order if it is the last one."),
                             _("Orders have an order number which cannot be remove because of accounting rules")).exec_()



    def _push_current_selection(self):
        ndx = self.controller_part.view.currentIndex() # self.controller_part.view.last_edited_index().column()
        part_row = ndx.row()
        part_col = ndx.column()
        part_has_focus = self.controller_part.view.hasFocus()

        ndx = self.controller_operation.view.currentIndex()
        op_row = ndx.row()
        op_col = ndx.column()
        op_has_focus = self.controller_part.view.hasFocus()

        return part_row,part_col,part_has_focus,op_row,op_col,op_has_focus

    def _pop_current_selection(self,cur_sel):
        part_row,part_col,part_has_focus,op_row,op_col,op_has_focus = cur_sel

        # The "min" is necessary for the cases where the cursor
        # was on a blank line at the end of the table. Since
        # during the save the blank line will be removed (and
        # we can't put the cursor back on it :-))

        part_row = min(part_row, max(0,self.controller_part.model.rowCount() - 1))
        self.controller_part.view.setCurrentIndex(self.controller_part.model.index(part_row,part_col))

        # The following to make sure there's actually a model
        # to show. This happens when one completely removes
        # all the parts of an order (and thus all the mode op)
        if self.controller_operation.model:
            op_row = min(op_row, max(0,self.controller_operation.model.rowCount() - 1))
            self.controller_operation.view.setCurrentIndex(self.controller_operation.model.index(op_row,op_col))

        if part_has_focus or not op_has_focus:
            self.controller_part.view.setFocus(Qt.OtherFocusReason)
        elif op_has_focus:
            self.controller_operation.view.setFocus(Qt.OtherFocusReason)


    @Slot()
    def save_button_clicked(self):
        order = self.save()
        if order:
            cur_sel = self._push_current_selection()
            self._show_order(order.order_id)
            self._pop_current_selection(cur_sel)


    def save(self):
        global dao,mainlog

        text = u""

        model = self.controller_part.model

        errors = model.validate()
        if errors is None:
            errors = dict()

        for line in sorted(errors.keys()):

            part_title = model.data( model.index(line,0), Qt.UserRole)
            if part_title is None:
                part_title = line+1

            text += u"<li>" + _("In order part description <b>{}</b>").format(part_title)
            text += u" : "
            text += u"{}".format(reduce(lambda a,b:a+b+u", ", errors[line], u"")[0:-2])
            text += u"</li>"

        text += u"<ul>"

        # FIXME completely useless messages :-) need more error tracking
        submodel_ndx = 0
        for submodel in model.submodels:

            # Since the submodels are computed only when they are
            # represented on screen, it is quite possible that
            # some of them are not init'd at this point.

            if submodel:

                # Clear out lines that don't have an operation definition
                # associated. That's a request of the user.

                for i in reversed(range(submodel.rowCount())):
                    if submodel.index(i,0).data(Qt.UserRole) == None:
                        submodel.removeRow(i)

                # Make first validation with prototypes
                v = submodel.validate()

                if v is None:
                    v = dict()

                for i in range(submodel.rowCount()):

                    operation = submodel.object_at(i)

                    op = operation.operation_definition_id
                    mat = operation.value or 0
                    hours = operation.planned_hours or 0

                    err = []

                    # We allow for operations without planned hours nor price
                    # This is OK because the data model doesn't allow "null"
                    # for those, it defaults to zero

                    if op:
                        op = operation_definition_cache.opdef_by_id(op)
                        if not op:
                            mainlog.error("Didn't find this op def in the cache: {}".format(operation.operation_definition_id))
                            err.append( _("An operation definition is not valid anymore (it was deleted by someone)"))
                    elif mat > 0  or hours > 0:
                        err.append( _("Can't set material price or planned hours when no operation is chosen"))

                    if op:
                        if not op.imputable and hours:
                            err.append( _("Planned hours can only be set for imputable operations"))
                        elif op.imputable and mat:
                            err.append( _("Material price can only be set for material operations"))

                    if len(err) > 0:
                        if i in v:
                            v[i] += err
                        else:
                            v[i] = err


                if v:
                    has_error = True

                    part_title = model.data( model.index(submodel_ndx,0), Qt.UserRole)
                    if part_title is None:
                        part_title = submodel_ndx+1

                    text += u"<li>" + _("In order part operational <b>{}</b>").format(part_title)
                    text += u"<ul>"

                    for line in sorted(v.keys()):
                        errors[u'{} in {}'.format(line+1, part_title)] = v[line]
                        text += "<li>"

                        text += _("On line <b>{}</b> : {}").format(line+1, reduce(lambda a,b:a+b+u", ", v[line], u"")[0:-2])
                        text += u"</li>"
                        # mainlog.debug(text.encode(sys.getdefaultencoding(),'ignore'))

                    text += u"</ul>"
                    text += u"</li>"

            submodel_ndx = submodel_ndx + 1
        text += u"</ul>"

        if len(errors) > 0:
            errorBox = makeErrorBox(_("Some of the data you entered are not valid"), text)
            errorBox.exec_()

        if len(errors) > 0:
            # showTableEntrySudModelsErrorBox(errors)
            return False


        from koi.configuration.business_functions import business_computations_service
        from koi.db_mapping import Order
        old_order = Order()
        old_order.preorder_label = self._current_order.preorder_label
        old_order.state = self._current_order.state
        old_order.sent_as_preorder = self._current_order.sent_as_preorder

        if business_computations_service.check_order_state_transition( old_order,
                                                                       self.order_state_label.value):

            order = self._save_to_db2(self._current_order.order_id)

            if order != False:
                self._current_order.order_id = order.order_id
                self._current_order.state = order.state

            return order
        else:
            return False


    def _save_to_db2(self,order_id):

        mainlog.debug("_save_to_db2() : start")

        model = self.controller_part.model
        order = None

        try:

            # The following dict actually represents a tree.
            # The top nodes are the keys (so a tree with several rrots)
            # the values are leaves below the roots.

            actions = OrderedDict()
            parts_results = model.model_to_objects(lambda : OrderPart(), None)

            for i in range(len(parts_results)):
                action_type, order_part, op_ndx = parts_results[i]

                if action_type == DBObjectActionTypes.TO_UPDATE:
                    if order_part.qty > order_part.tex2 and order_part.state == OrderPartStateType.completed:
                        showWarningBox(_("Quantity to do increased for a completed part ({})").format(order_part.description),
                                       _("You have increased a quantity to do above a done quantity. Therefore the order part's state might not be \"completed\" anymore. You should review its state"))

                if action_type != DBObjectActionTypes.TO_DELETE:
                    mainlog.debug("getting comment {} out of {}.".format(op_ndx, len(model.comments)))
                    cmt, cmt_modified = model.comments[op_ndx]

                    if cmt_modified:
                        order_part.notes = cmt
                        mainlog.debug("Comment modified : {}, action_type is {}".format(cmt, action_type))
                        if action_type == DBObjectActionTypes.UNCHANGED:
                            # If deleted, we can fogrtget; if created, then creation
                            # will do the rest, if updated, well, it's ok.
                            action_type = DBObjectActionTypes.TO_UPDATE

                # Having documents may imply saving them. So we update the
                # actions to do that.

                # If the part has to be deleted, then we just
                # have nothing to do (the documents will be erased)
                if action_type != DBObjectActionTypes.TO_DELETE:

                    docs_model_of_part = self.controller_part.model.documents[op_ndx]
                    if docs_model_of_part:
                        mainlog.debug("Setting {} documents for save at ndx {} of part (type={})".format(len(docs_model_of_part.documents()),op_ndx, type(order_part)))
                        order_part.documents = docs_model_of_part.documents()

                        docs_model_of_part.apply_delayed_renames(self.remote_documents_service)

                        if docs_model_of_part.has_changed() and action_type != DBObjectActionTypes.TO_CREATE:
                            # We must avoid to change TO_CREATE because when saving
                            # order parts, a TO_CREATE means that we can't rely
                            # on the order_part_id. So if I change that to
                            # TO_UPDATE, the code will expect order_part_id when
                            # there's none...
                            mainlog.debug("Marking order_part at ndx {} as TO_UPDATE because model has changed".format(op_ndx))
                            action_type = DBObjectActionTypes.TO_UPDATE

                    quality_events_of_part = self.controller_part.model.quality_event_models[op_ndx]
                    # order_part.quality_events = quality_events_of_part
                    if quality_events_of_part.has_changed() and action_type != DBObjectActionTypes.TO_CREATE:
                        action_type = DBObjectActionTypes.TO_UPDATE
                        mainlog.debug("about to save {} quality events of type {}".format(len(quality_events_of_part), type(quality_events_of_part)))
                    else:
                        mainlog.debug("{} quality events of type {} have not changed".format(len(quality_events_of_part), type(quality_events_of_part)))

                else:
                    quality_events_of_part = None

                parts_results[i] = (action_type, order_part, op_ndx, quality_events_of_part)

            actions = []

            for part_result in parts_results:

                # Each result is tied to its model representation
                # with the op_ndx below. order_part is always
                # an order part but it may or may not be
                # part of the sqlalchemy session

                action_type, order_part, op_ndx, quality_events_of_part = part_result

                # Some of the models may not have been realised
                # because the user has never visited them.
                # An UNCHANGED order_part doesn't mean its operations are
                # unchanged.

                if op_ndx is not None and model.submodels[op_ndx] is not None\
                   and (action_type is not DBObjectActionTypes.TO_DELETE)\
                   and not (action_type is DBObjectActionTypes.UNCHANGED and order_part is None):

                    submodel = model.submodels[op_ndx]
                    operations_results = submodel.model_to_objects(lambda : Operation(), None)

                    mainlog.debug(u"Operations actions ready : {}".format(operations_results))

                    actions.append( (part_result, operations_results) )
                else:
                    actions.append( (part_result, None) )


            order = dao.order_dao.update_order(order_id, self.current_customer_id, self.customer_order_name.text(),
                                               self.customer_preorder_name.text() or "",
                                               self.order_state_label.value,
                                               self.edit_comment_widget.toPlainText(),
                                               self.estimate_sent_date_label.value(),
                                               actions)


            # mainlog.debug("Association to order {}".format(order.order_id))
            # from koi.doc_manager.client_utils import documents_service
            # documents_service.associate_to_order( order.order_id, self.documents_widget.documents_ids(), commit=False)

            from koi.datalayer.database_session import session
            session().commit() # FIXME change update_order so that it returns order_id


            # Handle deletion of documents
            # There are two kinds of deletion.
            # 1. The documents are deleted because the order part is deleted
            #    In that case the association between parts and documents will
            #    be removed via cascades. However the actual documents will
            #    remain => so we need to remove them.
            # 2. The documents are deleted but the order parts they were attached
            #    to remains.
            # At this is point, the documents have been de-associated from the orders, order parts, etc.

            from koi.doc_manager.client_utils import remove_documents
            docs_to_remove = []
            for action_type, order_part, op_ndx, quality_events_of_part in parts_results:
                mainlog.debug("Delete at ndx {}".format(op_ndx))
                # If action = DELETE, then we won't get the op_ndx...
                if op_ndx is not None:
                    docs_model_of_part = self.controller_part.model.documents[op_ndx]
                    if docs_model_of_part:
                        mainlog.debug("Delete at ndx {} : there is a model with {} docs to remove".format(op_ndx,len(docs_model_of_part.documents_to_remove())))
                        docs_to_remove += [d.document_id for d in docs_model_of_part.documents_to_remove()]

            # Remove all the document from the documents database (but this
            # doesn't update the order parts links to these document)
            remove_documents(docs_to_remove)

            self.model_data_changed = False
            self.customer_changed = False

            # progress.close()



            return order

        except Exception as e:
            mainlog.exception(e)
            log_stacktrace()

            msgBox = makeErrorBox(_("There was an error while saving your data"),str(e))
            msgBox.exec_()
            return False




    @Slot(QModelIndex,QModelIndex)
    def operation_selection_changed(self, current, previous):

        if current.row() >= 0:

            op = current.model().object_at(current.row())
            mainlog.debug("operation_selection_changed : {}".format(op))
            self.op_traits_widget.set_trait(op)

            # op_id = op.operation_definition_id
            # if op_id:
            #     user_selected_operation = operation_definition_cache.opdef_by_id(op_id)
            #     self.op_traits_widget.set_trait(user_selected_operation)

        return # BUG debug

        # mainlog.debug("operation_selection_changed ndx={}, is model ? {}".format(current.row(), self.controller_operation.model.objects is not None))

        # if self.controller_operation.model and current.isValid() and current.row() < len(self.controller_operation.model.objects):
        #     mainlog.debug("operation_selection_changed len(objects)={}".format(len(self.controller_operation.model.objects)))

        #     op = self.controller_operation.model.objects[current.row()]

        #     if op and op.operation_id:
        #         global dao
        #         op = dao.operation_dao.find_by_id(op.operation_id)
        #         if op.task:
        #             self.low_pane2.set_model(dao.task_dao.employees_on_task(op.task))
        #         session().commit()
        #         return

        # self.low_pane2.set_model(None)


    @Slot(QModelIndex,QModelIndex)
    def indirect_current_row_changed(self,current,previous):
        return # BUG Disabled for debugging purposes

        # if current.isValid():
        #     global dao
        #     row = current.row()
        #     # mainlog.debug("indirect_current_row_changed")
        #     employee_id = self.indirects.data(self.indirects.index(row,0),Qt.UserRole)
        #     self.low_pane2.set_model([dao.employee_dao.find_by_id(employee_id)])
        #     session().commit()

    @Slot()
    def indirects_focus_in(self):
        self.indirect_current_row_changed(self.indirects_view.currentIndex(), None)


    @Slot(QModelIndex, int, int)
    def order_part_rows_inserted(self,parent,start,end):
        # mainlog.debug("Part row inserted. start={} end={}".format(start,end))
        self.show_operations_for_part( start)
        # mainlog.debug("Part row inserted. done with new row")


    @Slot(str)
    def customer_order_name_edited(self, text):
        self.data_changed_slot(None)

    @Slot(str)
    def customer_preorder_name_edited(self, text):
        self.data_changed_slot(None)

    @Slot()
    def operations_focus_in(self):
        self.operation_selection_changed(self.controller_operation.view.currentIndex(), None)

        # ndx = self.controller_part.view.currentIndex()
        # if ndx.isValid():
        #     row = ndx.row()
        #     empty = self.controller_part.model.isRowEmpty( row)

        #     if not empty:
        #         self.controller_operation.view.setEditTriggers(QAbstractItemView.EditKeyPressed | QAbstractItemView.AnyKeyPressed | QAbstractItemView.DoubleClicked)
        #         return

        # mainlog.debug("Disconnecting edit triggers")
        # self.controller_operation.view.setEditTriggers(QAbstractItemView.NoEditTriggers)


    @Slot(QAbstractTableModel)
    def submodelCreated(self,submodel):
        # All of this to avoid multiple connect on the same model
        # PySide doesn't handle very well (if one connects 10 times
        # a signal to a slot, then if the signal is raised then
        # the slots will be called 10 times instead of one)

        # mainlog.debug("submodelCreated")
        submodel.dataChanged.connect(self.data_changed_slot)
        submodel.rowsInserted.connect(self.data_changed_slot)
        submodel.rowsRemoved.connect(self.data_changed_slot)


    copy_buffer_parts = None




    @Slot()
    def copy_operations_slot(self):
        m = self.controller_operation.model
        ndx = self.controller_operation.view.currentIndex()

        s = self.controller_operation.view.selectedIndexes()
        max_row = 0
        min_row = 9999999
        for i in s:
            max_row = max(i.row(),max_row)
            min_row = min(i.row(),min_row)

        copied_operations = []
        for o in m.export_objects(min_row,max_row):
            c = copy.copy(o)
            c.operation_id = None
            c.done_hours = 0
            copied_operations.append(c)

        copy_paste_manager.copy_operations(copied_operations)
        copy_paste_manager.copy_table_view_to_csv(self.controller_operation.view)


    @Slot(QPoint)
    def show_operations_popup(self, position):
        menu = QMenu()
        menu.addAction(self.find_operations_action)
        menu.addAction(self.paste_operations_action)
        action = menu.exec_(QCursor.pos())

    @Slot(QPoint)
    def show_order_parts_popup(self, position):
        menu = QMenu()
        menu.addAction(self.copy_parts_action)
        menu.addAction(self.paste_parts_action)
        action = menu.exec_(QCursor.pos())


    @Slot()
    def copy_parts_slot(self):
        m = self.controller_part.model
        ndx = self.controller_part.view.currentIndex()

        s = self.controller_part.view.selectedIndexes()
        max_row = 0
        min_row = 9999999
        for i in s:
            max_row = max(i.row(),max_row)
            min_row = min(i.row(),min_row)

        # Make it clear we wont copy full parts
        copy_paste_manager.parts_id = []

        # We'll copy rows
        EditOrderPartsWidget.copy_buffer_parts = []

        mainlog.debug("copy_parts_slot: min {} max {}".format(min_row,max_row))
        rows = m.extract_rows(min_row,max_row)

        for ndx in range(min_row,max_row+1):
            # mainlog.debug("Pasting {}/{}".format(ndx - min_row,len(rows)))
            operations_model = m.submodel(ndx)

            EditOrderPartsWidget.copy_buffer_parts.append(
                ( rows[ndx - min_row],
                  operations_model.extract_all_rows(),
                  m.comments[ndx][0] ))

        copy_paste_manager.copy_table_view_to_csv(self.controller_part.view)

    @Slot()
    def paste_parts_slot(self):
        mainlog.debug("paste_parts_slot. Start pasting")

        operations_model = self.controller_operation.model
        parts_model = self.controller_part.model

        ndx = self.controller_part.view.currentIndex()

        if EditOrderPartsWidget.copy_buffer_parts:

            mainlog.debug("paste_parts_slot: starting at ndx {}".format(ndx.row()))

            for i in range(len(EditOrderPartsWidget.copy_buffer_parts)):
                part,ops,comment = EditOrderPartsWidget.copy_buffer_parts[i]
                parts_model.insert_data(ndx.row() + i, [part])
                parts_model._insert_blank_sub_models(ndx.row() + i, 1)
                mainlog.debug("paste_parts_slot: pasting operations ndx {}".format(ndx.row() + i))
                parts_model.submodel(ndx.row() + i).insert_data(0,ops)
                parts_model.comments[ndx.row() + i] = (comment, True)

        elif copy_paste_manager.parts_id:

            mainlog.debug("Pasting from copy_paste_manager")

            order_parts = dao.order_part_dao.find_by_ids_frozen(copy_paste_manager.parts_id)
            operations = dao.operation_dao.operations_for_order_parts_frozen(copy_paste_manager.parts_id)
            mainlog.debug("Available operations are")
            mainlog.debug(operations)

            row_part_ndx = max(0,ndx.row())

            for order_part in order_parts:
                r = parts_model.object_to_row(order_part, parts_model.prototype)

                parts_model.insert_data(row_part_ndx, [r])
                parts_model._insert_blank_sub_models(row_part_ndx, 1)
                parts_model.comments[row_part_ndx] = (order_part.notes, True)

                if order_part.order_part_id in operations:
                    operations_model = parts_model.submodel(row_part_ndx)
                    rops = []

                    for op in operations[order_part.order_part_id]:
                        r = operations_model.object_to_row(op, operations_model.prototype)
                        rops.append(r)
                    parts_model.submodel(row_part_ndx).insert_data(0,rops)

                row_part_ndx += 1


    @Slot()
    def paste_operations_slot(self):

        if copy_paste_manager.operations:

            operations_model = self.controller_operation.model
            op_part_ndx = max(0, self.controller_operation.view.currentIndex().row())

            operations_model.insert_objects( op_part_ndx, copy_paste_manager.operations)

            # rops = []
            # for op in copy_paste_manager.operations:
            #     r = operations_model.object_to_row(op, operations_model.prototype)
            #     rops.append(r)

            # operations_model.insert_data(op_part_ndx,rops)



    @Slot()
    def show_previous_active_order(self):
        global dao

        if self._current_order.order_id:
            order_id = dao.order_dao.active_order_before( self._current_order.order_id)
            if order_id:
                self.reset_order(order_id)

    @Slot()
    def show_next_active_order(self):
        global dao

        if self._current_order.order_id:
            order_id = dao.order_dao.active_order_after( self._current_order.order_id)
            if order_id:
                self.reset_order(order_id)


    @Slot()
    def show_previous_customer_order(self):
        global dao

        order_id = None
        if self._current_order.order_id:
            order_id = dao.order_dao.customer_order_before(self._current_order.order_id, self._current_order.customer_id)
        else:
            order = dao.order_dao.last_customer_order(self._current_order.customer_id)
            if order:
                order_id = order.order_id

        if order_id:
            self.reset_order(order_id)

    @Slot()
    def show_next_customer_order(self):
        global dao

        order_id = None
        if self._current_order.order_id:
            order_id = dao.order_dao.customer_order_after(self._current_order.order_id, self._current_order.customer_id)
        else:
            order = dao.order_dao.last_customer_order(self._current_order.customer_id)
            if order:
                order_id = order.order_id

        if order_id:
            self.reset_order(order_id)


    @Slot()
    def show_previous_order(self):
        global dao

        if self._current_order.order_id:
            order_id = dao.order_dao.order_before( self._current_order.order_id)
            if order_id:
                self.reset_order(order_id)

    @Slot()
    def show_next_order(self):
        global dao

        if self._current_order.order_id:
            order_id = dao.order_dao.order_after( self._current_order.order_id)
            if order_id:
                self.reset_order(order_id)

    @Slot()
    def show_actions(self):
        button = self.action_menu.parent()
        p = button.mapToGlobal(QPoint(0,button.height()))
        self.action_menu.exec_(p)


    @Slot()
    def change_order_state(self):
        d = OrderWorkflowDialog(self)
        d.set_selected_state( self.order_state_label.state, self._current_order.state)
        d.exec_()
        if d.result() == QDialog.Accepted and d.selected_state:
            self.order_state_label.set_state(d.selected_state)

        d.deleteLater()

    def print_bill_of_operations_selected( self):

        if self.save_if_necessary():
            selected_row_indices = self.controller_part.view.selected_rows()

            if not selected_row_indices:
                showWarningBox( _("Nothing selected"), _("You have selected no parts to print."))

            mainlog.debug("print_bill_of_operations_selected selected_row_indices:{}".format( selected_row_indices))

            m = self.controller_part.model
            parts = [m.object_at(n) for n in selected_row_indices if m.object_at(n)] # Skipping empty lines

            operations_counts = []
            # o = dao.order_dao.find_by_id(order_id)
            # for part in o.parts:

            # Lots of fiddling because when one creates a new operation
            # it migh be totally blank.
            for n in selected_row_indices:
                sm =  self.controller_part.model.submodel(n)
                if sm:
                    valid_ops = 0
                    for i in range(sm.rowCount()):
                        if sm.object_at(i).operation_definition_id:
                            valid_ops += 1

                    operations_counts.append( valid_ops )
                else:
                    operations_counts.append( 0)

            mainlog.debug("print_bill_of_operations_selected operations_counts={}".format(operations_counts))
            if sum( operations_counts) == 0:
                showWarningBox(_("Empty order parts"),_("All the parts you have selected have no operations. There's nothing to print."))
                return

            # The test on 0 operation above must be done firsst.

            bad_state = [ part.label for part in parts if part.state not in (OrderPartStateType.ready_for_production, OrderPartStateType.production_paused, OrderPartStateType.non_conform,)]

            if bad_state:
                if not confirmationBox( _("Order part not ready for production"),
                                        _("Some order parts you selected ({}) are not ready for prodution. Are you sure you want to print their bill of operations ? Are you sure you want to proceed ?").format(",".join(sorted(bad_state)))):
                    return

            part_ids = [p.order_part_id for p in parts]
            print_bill_of_operations_report( dao, self._current_order.order_id, part_ids)


    def orderPrint(self):
        global dao

        if self.save_if_necessary():

            if self._current_order.order_id is None:

                # When an order is brand new and empty, it is not marked
                # as "modified" (this to allow to close the order editing without
                # a warning from Horse). since it is not marked as modified,
                # the save_as_necessary will do nothing, leaving the
                # current_order_id as None.

                showWarningBox(_("Empty order"),_("You can't print the bill of operations if the order is empty"))
                return

            if dao.order_dao.nb_operations_on_order( self._current_order.order_id) == 0:
                showWarningBox(_("Empty order"),_("You can't print the bill of operations if the order has no operations"))
                return

            if self.order_state_label.value in (OrderStatusType.preorder_definition, OrderStatusType.preorder_sent, OrderStatusType.order_definition, OrderStatusType.order_completed):
                if not confirmationBox(_("Printing a bill of operations for a part in non appropriate state"),
                    _("The order seems to not be ready for production, are your sure you want to print its bill of operations ?")):
                    return


            try:
                print_order_report( dao, self._current_order.order_id)
            except Exception as e:
                mainlog.exception(e)
                makeErrorBox(str(e)).exec_()

    def order_confirmation_report(self):
        global dao

        try:
            print_order_confirmation_report( self._current_order.order_id)
        except Exception as e:
            for l in traceback.format_tb(sys.exc_info()[2]):
                mainlog.error(l)

            makeErrorBox(str(e)).exec_()


    def preorder_report(self):

        should_save = self.data_changed()
        print_affects_state = self._check_preorder_sent_on_print()

        if should_save:
            save_successful = self.save_if_necessary()
        elif print_affects_state:
            save_successful = self._force_save()
        else:
            save_successful = True

        if save_successful:
            try:
                print_preorder_report( self._current_order.order_id)
            except Exception as e:
                mainlog.exception(e)
                makeErrorBox(str(e)).exec_()


    def activity_report(self):
        global dao

        try:
            print_iso_status( dao, self._current_order.order_id)
        except Exception as e:
            for l in traceback.format_tb(sys.exc_info()[2]):
                mainlog.error(l)

            makeErrorBox(str(e)).exec_()

    def audit_report(self):
        global dao

        try:
            print_order_audit_report( self._current_order.order_id)
        except Exception as e:
            for l in traceback.format_tb(sys.exc_info()[2]):
                mainlog.error(l)

            makeErrorBox(str(e)).exec_()

    def _check_preorder_sent_on_print(self):

        state = self.order_state_label.value
        mainlog.debug("_check_preorder_sent: state={}, date={}".format( state, self.estimate_sent_date_label.value()))

        if state == OrderStatusType.preorder_definition and not self.estimate_sent_date_label.value():
            if yesNoBox(_("State change on printing"),
                        _("If you intend to send this estimate to the customer, I can switch its state to \"{}\". If you disagree, we'll leave the state as it is.").format(OrderStatusType.preorder_sent.description),
                          "set_preorder_sent_state") == QMessageBox.Yes:
                self._set_state( OrderStatusType.preorder_sent)
                self.estimate_sent_date_label.setValue( date.today())
                return True

        elif state != OrderStatusType.order_aborted and not self.estimate_sent_date_label.value():
            if yesNoBox(_("Set estimate sent date on printing"),
                        _("If you intend to send this estimate to the customer, I can give it today as the send date"),
                          "set_preorder_sent_date") == QMessageBox.Yes:
                self.estimate_sent_date_label.setValue( date.today())
                return True

        return False

    def preorderPrint(self):

        d = PrintPreorderDialog(None)
        d.set_preorder( self._current_order.order_id)
        d.exec_()

        if d.result() == QDialog.Accepted:

            should_save = self.data_changed()
            print_affects_state = self._check_preorder_sent_on_print()

            if should_save:
                save_successful = self.save_if_necessary()
            elif print_affects_state:
                save_successful = self._force_save()
            else:
                save_successful = True

            if save_successful:

                note,footer = d.get_print_notes()
                dao.order_dao.update_preorder_notes( self._current_order.order_id, note, footer)

                try:
                    print_preorder( self._current_order.order_id)
                except Exception as e:
                    mainlog.exception(e)
                    for l in traceback.format_tb(sys.exc_info()[2]):
                        mainlog.error(l)

                    makeErrorBox(str(e)).exec_()

    @Slot(QModelIndex)
    def order_part_data_changed(self,index):
        mainlog.debug("order_part_data_changed on row/col {}/{}".format(index.row(),index.column()))
        if index.column() == 1:
            # The quantity to produce has changed
            row = index.row()

            submodels = self.controller_part.model.submodels
            mainlog.debug("order_part_data_changed {} submodels".format(len(submodels)))
            # Make sure the index corresponds to a submodel
            # (that's purely defensive programming)
            if row >= 0 and row < len(submodels) and submodels[row] is not None:

                operation_model = submodels[row]
                operation_model.update_quantity_to_produce(index.data(Qt.UserRole))

        # Do some more stuff
        self.data_changed_slot(index)

        self.controller_part.view.horizontalHeader().setResizeMode(QHeaderView.ResizeToContents)
        self.controller_part.view.horizontalHeader().setResizeMode(0, QHeaderView.Stretch)
        # self.controller_part.view.resizeColumnsToContents()

        mainlog.debug("order_part_data_changed done with row/col {}/{}".format(index.row(),index.column()))


    def change_customer(self):
        mainlog.debug("change_customer. Current customer is {}".format(self.current_customer_id))
        d = ChangeCustomerDialog(self)
        d.exec_()
        if d.result() == QDialog.Accepted and self.current_customer_id != d.customer_id:
            self.current_customer_id = d.customer_id
            self.refresh_customer(d.customer_id)
            self.customer_changed = True
            self.title_widget.set_modified_flag(True)
            mainlog.debug("change_customer : changed to {}".format(self.current_customer_id))
        else:
            mainlog.debug("change_customer : customer left unchanged")

        d.deleteLater()


    @Slot()
    def change_estimate_sent_date(self):

        if self.order_state_label.value != OrderStatusType.preorder_sent:
            d= DatePick(_("Please pick a date corresponding to the moment which you sent the estimate to your customer. Choose no date if you want to tell that then estimate was not sent."),
                        True)
        else:
            d= DatePick(_("Please pick a date corresponding to the moment which you sent the estimate to your customer. You must set a valid date because the current state of the order is {}.").format(OrderStatusType.preorder_sent),
                        False)
        d.exec_()
        if d.result() == QDialog.Accepted:
            self.estimate_sent_date_label.setValue( d.accepted_date)
            self.data_changed_slot(None)

class OperationTraitsEditWidget(QWidget):

    def set_trait(self, operation):
        """ Adapt the widget content to the operation.
        The operation data object is expected to come from an ObjectModel, so it's not
        an actual Operation object, but something that "duck types" it
        """

        mainlog.debug(operation)
        self._current_operation = operation

        assignee_ndx = self.qb_employee.findData( operation.assignee_id) # Will work for None too (because I set the first element of the combobox to None data)
        mainlog.debug("Setting assignee id to {} at ndx {}".format(operation.assignee_id, assignee_ndx))
        self.qb_employee.setCurrentIndex(assignee_ndx) # so -1 becomes 0 :-)

        if operation.operation_definition_id is not None:
            operation_definition = operation_definition_cache.opdef_by_id(operation.operation_definition_id)

            if not operation_definition:
                #untested code
                return

            mainlog.debug("Looking for machines tied to op def {}".format(operation_definition.operation_definition_id))
            machines = machine_service.find_machines_for_operation_definition(operation_definition.operation_definition_id)
            self.qb_machine.clear()
            if machines:
                self.qb_machine.addItem("", None)
                for m in machines:
                    self.qb_machine.addItem(m.fullname)
            else:
                mainlog.debug("No machine")


            # from PySide.QtGui import QApplication
            # focus = QApplication.focusWidget()
            # mainlog.debug("Focus widget : {}".format(focus))

            if operation_definition.short_id == 'MA':
                self.ma_widget.setVisible( True )
                self.op_traits_widget.setVisible( False)
            elif operation_definition.short_id == 'CQ':
                self.ma_widget.setVisible( False )
                self.op_traits_widget.setVisible( False)
            else:
                self.ma_widget.setVisible( False )
                self.op_traits_widget.setVisible( True)

            # focus = QApplication.focusWidget()
            # mainlog.debug("Focus widget : {}".format(focus))

    def __init__(self, parent=None):
        super(OperationTraitsEditWidget,self).__init__(parent)


        qcb_supply_order = QLineEdit("800a")
        qcb_supply_order_desc = QLabel("lorem ipsum dolor")

        self.ma_widget = QWidget()

        ma_layout = QHBoxLayout()
        ma_layout.addWidget(qcb_supply_order)
        ma_layout.addWidget(qcb_supply_order_desc)
        self.ma_widget.setLayout(ma_layout)

        self.qb_employee = QComboBox()
        self.qb_employee.clear()
        self.qb_employee.addItem("", None)
        for employee in dao.employee_dao.list_overview():
            if employee.is_active:
                self.qb_employee.addItem(employee.fullname, employee.employee_id)

        self.qb_machine = QComboBox()
        self.qb_machine.clear()
        self.qb_machine.addItem("Fraiseuse",12345)

        self.op_traits_widget = QWidget()
        op_layout = QHBoxLayout()
        op_layout.addWidget(self.qb_employee)
        op_layout.addWidget(self.qb_machine)
        self.op_traits_widget.setLayout(op_layout)

        row_layout = QVBoxLayout()
        row_layout.addWidget(self.ma_widget)
        row_layout.addWidget(self.op_traits_widget)


        self.setLayout(row_layout)

        self.qb_employee.activated.connect(self.assignee_activated_slot)

    @Slot()
    def assignee_activated_slot(self, index):
        mainlog.debug("assignee_activated_slot : {} -> {}".format(self.qb_employee.itemData(index), self._current_operation))
        self._current_operation.assignee_id = self.qb_employee.itemData(index)


if __name__ == "__main__":
    from koi.service_config import remote_documents_service
    import logging

    mainlog.setLevel(logging.DEBUG)

    dao.set_session( session())
    app = QApplication(sys.argv)
    mw = QMainWindow()
    mw.setMinimumSize(1024,768)
    widget = EditOrderPartsWidget(mw,None,True,remote_documents_service)


    #widget.reset_order(3998)
    widget._show_blank_order( dao.customer_dao.all()[0].customer_id)
    # widget.edit_new_order(dao.customer_dao.all()[1])
    mw.setCentralWidget(widget)
    mw.show()
    widget.set_visibility(True)

    app.exec_()
