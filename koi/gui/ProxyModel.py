import os
import hashlib
import sys
import re

"""
Prototypes are dual : they live in the model and in the view worlds.

For example :
- A model needs a prototype to know which of its cells are editable
- A view needs a prototype to know which delegates to use while editing cells

Prototype gives a delegate and the delegate is signal-connected to the view.
Therefore a prototype is connected to a view and therefore a prototype
cannot be shared between several views.
Since a a prototype also lives in the model world, a prototype cannot
be shared between several models.
Consequently, a prototype can only exists between one and only one
model and one and only one view. That's aproblem because one should
be able to change the model of a view several times during the life
of the view.


View makes new delegates
if the model changes, the delegates stays

"""

from inspect import isfunction

from PySide.QtCore import Qt, QAbstractTableModel, QModelIndex, Slot, Signal, QObject, QEvent, QRect
from PySide.QtGui import QStandardItemModel, QHeaderView, QAbstractItemDelegate, QColor, QLineEdit, QValidator, QAction, QKeySequence,QBrush, \
    QFrame, QLayout, QLabel
from PySide.QtGui import QWidget,QPushButton,QHBoxLayout,QPixmap,QIcon
from sqlalchemy import event

from koi.qtableviewfixed import QTableView

from koi.Configurator import mainlog,resource_dir

from koi.gui.ComboDelegate import TimestampDelegate,StandardTableDelegate,NumbersTableDelegate,FloatTableDelegate,AutoComboDelegate,DurationDelegate,OrderPartDisplayDelegate,PictureDelegate,BooleanDelegate,TextAreaTableDelegate,FutureDateDelegate,DateDelegate,TaskDisplayDelegate,EuroDelegate,FilenameDelegate,NotEmptyStringDelegate,DocumentCategoryDelegate
from koi.db_mapping import Order,OrderPart,Task,TaskOnOrder,TaskOnOperation,OrderStatusType,TaskActionReportType,TaskOnNonBillable,SpecialActivityType
from koi.dao import dao
from koi.datalayer.types import DBObjectActionTypes
from koi.gui.completer import AutoCompleteComboBox

from koi.gui.dialog_utils import showWarningBox
from koi.datalayer.database_session import session
from koi.datalayer.quality import QualityEventType
from koi.db_mapping import OperationDefinition
from koi.translators import date_to_dm

class PrototypeArray:
    """ Use this to store prototypes instance
    """

    def __init__(self, prototypes : list):
        """

        :param prototypes: list of Prototype
        :type prototypes: list[Prototype]
        :return:
        """
        assert prototypes

        self._prototypes = prototypes
        """:type self._prototypes : list[Prototype]"""

    def index_of(self, field : str):

        assert field

        for i in range(len(self._prototypes)):
            if self._prototypes[i].field == field:
                return i

        raise Exception("Field '{}' not found".format(field))

    def append( self, item):
        self._prototypes.append( item)

    def __len__(self):
        return len(self._prototypes)

    def __getitem__(self, index):
        if type(index) == int:
            return self._prototypes[index]
        elif type(index) == str:
            for p in self._prototypes:
                if p.field == index:
                    return p
        else:
            raise Exception("unsupported type, I accept int and str only")

        raise Exception("Index '{}' not found in prototype".format(index))


class Prototype(object):

    def __init__(self,field,title,editable=True,nullable=False,hidden=False):
        """ Creates a prototype that defines how a given ''field'' of an object
        is to be displayed in a table. The title of the column that will hold
        the values of the field is given a 'title'.

        If two data fields (i.e that can be edited altogether) have
        the same kind of prototype then, two instances of the prototype must
        be created; one for each of the field.

        If the field is "None", it means a prototype for a value that
        won't be copied into or read from an actual object. It is useful
        in case you need to validate some input in a table that is not
        tied to an object or to a field of an object.
        """

        self.field = field
        # is_editable is a function that returns True or False
        self.is_editable = editable
        self.is_nullable = nullable
        self.is_hidden = hidden
        self.title = title
        self._widget = None

    def make_delegate(self):
        raise Exception("Abstract method must be defined in concrete class")

    def set_delegate(self,delegate):
        self._delegate = delegate

    def delegate(self):
        return self._delegate

    def validate(self,value):
        if (not self.is_nullable) and ((value is None) or (type(value) == str and len(value.strip()) == 0)):
            return _("{} can't be empty").format(self.title)
        else:
            return True

    def default_value(self):
        """ Default value is used when the user didn't enter anything in an
        editable field or cleared such a field (in that case the idea of
        "default" is a bit misleading). Defaults are applied only when
        copying the model/view into the object. Therefore the default
        is not intended to be shown at the user. For example, the default
        values are stored in the appropriate fields after the user
        has hit a Save button.

        A None default value means : no default applicable. Therefore
        one cannot have  "None" as a valid default value.
        """

        return None

    def edit_widget(self,parent):
        """ Creates an edit widget (instead of a delegate) for this prototype.
        This should be used only when using the prototype outside
        its "regular" table delegate scenario (for example in a form
        layout).

        An edit widget, is always in edit mode (contrary to the standard
        delegate which can be either iin display mode or in edit mode)

        This prototype will make exactly one widget. So if you need
        the same widget several times, you'll need to instanciate
        the *prototype* as many times...
        """

        if not self._widget:
            if hasattr(self._delegate, "editWidgetFactory"):
                self._widget = self._delegate.editWidgetFactory(parent)
            else:
                self._widget = self._delegate.createEditor(parent,None,None)

        return self._widget

    def enable_edit_widget(self,b):
        return self._widget.setEnabled(b)

    def set_edit_widget_data(self,data):
        # Create a dummy model to be able to use the standard Horse delegate
        # interface. That's totally hackish :-(

        m = QStandardItemModel(1,1)
        index = m.index(0,0)
        m.setData( index, data, Qt.UserRole)
        self._delegate.setEditorData(self._widget,index)

    def edit_widget_data(self):
        # Create a dummy model to be able to use the standard Horse delegate
        # interface. That's totally hackish :-(

        m = QStandardItemModel(1,1)
        index = m.index(0,0)
        # Copies from the editor back to our local model
        self._delegate.setModelData(self._widget,m,index)
        return index.data(Qt.UserRole)




    def __repr__(self):
        return "Field {} as '{}', nullable? {}, editable? {}, hidden? {}".format(self.field, self.title.encode(sys.getdefaultencoding(),'ignore'), self.is_nullable, self.is_editable, self.is_hidden)



class EmptyPrototype(Prototype):
    """ Prototype to reveal an empty column (or a column that one wants
    total control on) in a model.

    This should be used carefully as it is a general bypass for everything...
    """

    def __init__(self,title):
        super(EmptyPrototype,self).__init__(field=None,title=title,editable=False,nullable=True,hidden=False)
        self.set_delegate(None)

    def validate(self,value):
        return True


# class SpecialActivityTypeDelegate(AutoComboDelegate):

#     def __init__(self,field,title,editable=True,nullable=False):
#         super(SpecialActivityTypeDelegate,self).__init__(field,title,editable,nullable)
#         # WARNING Pay attention, those objects have no parent => they
#         # must be kept alive for the whole duration of the program, else,
#         # you'll have ownership issues with Qt bindings



class MachineZonePrototype(Prototype):
    def __init__(self,field,title,editable=True,nullable=False):
        super(MachineZonePrototype,self).__init__(field,title,editable,nullable)
        # WARNING Pay attention, those objects have no parent => they
        # must be kept alive for the whole duration of the program, else,
        # you'll have ownership issues with Qt bindings

        # d = AutoComboDelegate(None,None)
        # d.items = TaskActionReportType.symbols()
        # d.labels = TaskActionReportType.labels()

        zones = [None] + [ _("Zone {}").format(i) for i in range(1,16)]

        self.set_delegate(AutoComboDelegate(None,None)) # items, sizes
        self.delegate().items = zones
        self.delegate().labels = zones



class SpecialActivityTypePrototype(Prototype):
    def __init__(self,field,title,editable=True,nullable=False):
        super(SpecialActivityTypePrototype,self).__init__(field,title,editable,nullable)
        # WARNING Pay attention, those objects have no parent => they
        # must be kept alive for the whole duration of the program, else,
        # you'll have ownership issues with Qt bindings

        # d = AutoComboDelegate(None,None)
        # d.items = TaskActionReportType.symbols()
        # d.labels = TaskActionReportType.labels()

        self.set_delegate(AutoComboDelegate(None,None)) # items, sizes
        self.delegate().items = SpecialActivityType.symbols()
        self.delegate().labels = SpecialActivityType.descriptions()

        # mainlog.debug(u"SpecialActivityTypePrototype : {}".format(SpecialActivityType.descriptions()))
        mainlog.debug(u"SpecialActivityTypePrototype : items = {}, labels ={}".format(self.delegate().items, self.delegate().labels))


from koi.gui.ComboDelegate import EnumComboDelegate


class QualityEventTypePrototype(Prototype):
    def __init__(self,field,title,editable=True,nullable=False):
        super(QualityEventTypePrototype,self).__init__(field,title,editable,nullable)
        # WARNING Pay attention, those objects have no parent => they
        # must be kept alive for the whole duration of the program, else,
        # you'll have ownership issues with Qt bindings

        self.set_delegate(EnumComboDelegate(QualityEventType)) # items, sizes


class ActionReportTypeComboDelegate(AutoComboDelegate):
    def __init__(self,items,section_width = None,parent=None):
        super(ActionReportTypeComboDelegate,self).__init__(parent)

    def createEditor(self,parent,option,index):
        global dao

        left_side = index.model().index(index.row(),index.column()-1).data(Qt.UserRole)

        self.items = []
        if left_side is None:
            self.items = [TaskActionReportType.day_in,TaskActionReportType.day_out]
        elif isinstance(left_side,Task):
            self.items = [TaskActionReportType.start_task,TaskActionReportType.stop_task]
        else:
            raise Exception("Unsupported type")

        self.labels = [t.description for t in self.items]

        editor = AutoCompleteComboBox(self,parent)
        editor.section_width = [400]
        editor.make_str_model(self.labels, self.items)

        if option:
            editor.setGeometry(option.rect)

        return editor

    def get_displayed_data(self,index):
        t = index.model().data( index,Qt.UserRole)
        if t:
            return t.description
        else:
            return None

    def setModelData(self,editor,model,index):
        ndx = editor.currentIndex()

        if ndx < 0:
            ndx = 0

        data = editor.itemData( ndx, Qt.UserRole)
        model.setData(index,data,Qt.UserRole)







class TaskActionTypePrototype(Prototype):
    def __init__(self,field,title,editable=True,nullable=False):
        super(TaskActionTypePrototype,self).__init__(field,title,editable,nullable)
        # WARNING Pay attention, those objects have no parent => they
        # must be kept alive for the whole duration of the program, else,
        # you'll have ownership issues with Qt bindings

        # d = AutoComboDelegate(None,None)
        # d.items = TaskActionReportType.symbols()
        # d.labels = TaskActionReportType.labels()

        d = ActionReportTypeComboDelegate(None,None)
        self.set_delegate(d)



class OrderPartDisplayPrototype(Prototype):
    """ Displays a short description of an order part, that
    is the human identifier and the description.
    """

    def __init__(self,field,title,editable=True,nullable=False):
        super(OrderPartDisplayPrototype,self).__init__(field,title,editable,nullable)
        self.set_delegate(OrderPartDisplayDelegate(None))

class PicturePrototype(Prototype):
    def __init__(self,field,title,editable=True,nullable=False):
        super(PicturePrototype,self).__init__(field,title,editable,nullable)
        self.set_delegate(PictureDelegate(None))

class BooleanPrototype(Prototype):
    def __init__(self,field,title,editable=True,nullable=False, default=False):
        super(BooleanPrototype,self).__init__(field,title,editable,nullable)
        self.set_delegate(BooleanDelegate(None))
        self._default = default

    def default_value(self):
        return self._default

class TextAreaPrototype(Prototype):
    def __init__(self,field,title,editable=True,nullable=False,hidden=False):
        super(TextAreaPrototype,self).__init__(field,title,editable,nullable)
        self.set_delegate(TextAreaTableDelegate(None))




class EmployeePrototype(Prototype):
    def __init__(self,field,title,employees,editable=True,nullable=False):
        super(EmployeePrototype,self).__init__(field,title,editable,nullable)
        # WARNING Pay attention, those objects have no parent => they
        # must be kept alive for the whole duration of the program, else,
        # you'll have ownership issues with Qt bindings

        self.set_delegate(AutoComboDelegate(None,None))
        self.set_employees(employees)

    def set_employees(self,employees):
        self.delegate().items = employees
        self.delegate().labels = [e.fullname for e in employees]


class DocumentCategoryPrototype(Prototype):
    def __init__(self,field,title,editable=True,nullable=False):
        super(DocumentCategoryPrototype,self).__init__(field,title,editable,nullable)
        # WARNING Pay attention, those objects have no parent => they
        # must be kept alive for the whole duration of the program, else,
        # you'll have ownership issues with Qt bindings

        self.set_delegate(DocumentCategoryDelegate())

    def set_categories(self,categories : list): # list of categories

        # This shall work without categories
        if not categories:
            categories = []
        else:
            categories = dict( [(c.document_category_id, c.short_name) for c in categories] )

        self.delegate().set_categories(categories)



class OperationDefinitionComboDelegate(AutoComboDelegate):

    def __init__(self,items,section_width = None,parent=None):
        super(OperationDefinitionComboDelegate,self).__init__(items,section_width,parent)

        self._set_operation_definitions(
            dao.operation_definition_dao.all_on_order_part())

        self._operations_reload_flag = False
        event.listen(OperationDefinition, 'after_insert', self._operations_definitions_changed)
        event.listen(OperationDefinition, 'after_update', self._operations_definitions_changed)
        event.listen(OperationDefinition, 'after_delete', self._operations_definitions_changed)

    def _operations_definitions_changed(self, mapper, connection, target):
        self._operations_reload_flag = True

    def createEditor(self,parent,option,index):
        # This is called each time an editor is requested
        # to edit something (so if on edit a cell several
        # times iin a row, then this method will be called
        # the same amount of times).

        mainlog.debug("OperationDefinitionComboDelegate.createEditor")

        if self._operations_reload_flag:
            mainlog.debug("OperationDefinitionComboDelegate.createEditor : reloading operations")
            self._set_operation_definitions(
                dao.operation_definition_dao.all_on_order_part())
            self._operations_reload_flag = False
        return super(OperationDefinitionComboDelegate, self).createEditor(parent, option, index)

    def _set_operation_definitions(self, operation_definitions):
        self.display_map = dict( [(opdef.operation_definition_id, opdef.short_id) for opdef in operation_definitions])
        self.items = [opdef.operation_definition_id for opdef in operation_definitions]
        self.labels = [u"{} {}".format(e.short_id,e.description) for e in operation_definitions] # ,e.description

    def get_displayed_data(self,index):
        d = index.model().data( index,Qt.UserRole)
        if d and d in self.display_map:
            # Depending on the state of the list of operation, this
            # might be desynchronized with database...
            return self.display_map[d]
        else:
            return None


class OperationDefinitionPrototype(Prototype):
    def __init__(self,field,title,operation_definitions,editable=True,nullable=False):
        global event

        super(OperationDefinitionPrototype,self).__init__(field,title,editable,nullable)
        # WARNING Pay attention, those objects have no parent => they
        # must be kept alive for the whole duration of the program, else,
        # you'll have ownership issues with Qt bindings

        d = OperationDefinitionComboDelegate(None,[300],None)
        self.set_delegate(d)
        # self.set_operation_definitions(operation_definitions)
        # self.operation_definitions = operation_definitions


    # def set_operation_definitions(self,operation_definitions):
    #     self.delegate().set_operation_definitions(operation_definitions)

    # def make_delegate(self):
    #     d = OperationDefinitionComboDelegate(None,[300],None)
    #     d.set_prototype(self)

    def default_value(self):
        return None



class TaskDisplayPrototype(Prototype):
    """ Prototype for simple display of taks's description.
    For editable stuff, see TaskPrototype
    """
    def __init__(self,field,title,editable=False,nullable=False):
        super(TaskDisplayPrototype,self).__init__(field, title,editable,nullable)

        if editable:
            raise Exception("This is a read-only protoype !")

        self.set_delegate(TaskDisplayDelegate())


class TaskPrototype(Prototype):
    """ Prototype for task selection.
    For simple display, see TaskDisplayPrototype
    """
    def __init__(self,field,title,tasks,editable=True,nullable=False):
        super(TaskPrototype,self).__init__(field, title,editable,nullable)
        # WARNING Pay attention, those objects have no parent => they
        # must be kept alive for the whole duration of the program, else,
        # you'll have ownership issues with Qt bindings

        self.set_delegate(AutoComboDelegate(None,None))
        self.set_tasks(tasks)

    def set_tasks(self,tasks):
        self.delegate().items = tasks
        self.delegate().labels = [e.description for e in tasks]


# FIXME Deprecated
# def configure_combo_box_on(editor, s, on_date):
#     global dao

#     tasks = dao.task_dao.potential_imputable_tasks_for(s, on_date)
#     labels = []
#     for t in tasks:
#         if isinstance(t,TaskOnOrder):
#             labels.append(t.operation_definition.description)
#         elif isinstance(t,TaskOnOperation):
#             labels.append( u"{}: {}".format(t.operation.operation_model.short_id, t.description or u""))
#         elif isinstance(t,TaskOnNonBillable):
#             labels.append(t.operation_definition.description)
#         else:
#             raise Exception("Unknown TaskOnXxx type : {}".format(type(t)))
#     editor.make_str_model(labels, self.tasks)


class TaskComboDelegate(AutoComboDelegate):
    """ The task combo delegate, if used as an editor, it must be
    located on a column at the *right* of an 'order part' column.
    """

    def __init__(self,items,on_date,section_width = None,parent=None):
        super(TaskComboDelegate,self).__init__(parent)
        if on_date is None:
            raise Exception("Invalid date")

        self.on_date = on_date
        self.task_cache = None

    def set_task_cache(self,cache):
        self.task_cache = cache

    def createEditor(self,parent,option,index):
        mainlog.debug("TaskComboDelegate : createEditor")
        global dao

        left_side = index.model().index(index.row(),index.column()-1).data(Qt.UserRole)

        editor = AutoCompleteComboBox(self,parent)
        editor.section_width = [400]

        tasks = []
        if self.task_cache:
            mainlog.debug(u"Identifier is {}".format(left_side))
            tasks = self.task_cache.tasks_for_identifier(left_side)
        else:
            # BUG This is bug ! If one calls this twice for the
            # same "left_side" and if the object denoted by the
            # has no task associated to it in the database,
            # then two tasks objects will be created, for the same
            # identifier. This is a bug because the datamodel
            # only allows one task per object (e.g. for Operation
            # objects, see TaskOnOperation unique constraints)

            # tasks = filter(is_task_imputable_for_admin,
            tasks =  dao.task_dao.potential_imputable_tasks_for(left_side, self.on_date)

            mainlog.debug("Filtered tasks")

        self.labels = []
        for t in tasks:
            mainlog.debug(t)
            mainlog.debug(t.description)

            if isinstance(t,TaskOnOrder):
                self.labels.append(t.operation_definition.description)
            elif isinstance(t,TaskOnOperation):
                # self.labels.append( u"{}: {}".format(t.operation.operation_model.short_id, t.description or u""))
                self.labels.append(t.description or "")
            elif isinstance(t,TaskOnNonBillable):
                self.labels.append(t.description or "")
            else:
                raise Exception("Unknown TaskOnXxx type : {}".format(type(t)))
        self.items = tasks

        editor.make_str_model(self.labels, self.items)

        if option:
            editor.setGeometry(option.rect)

        # FIXME bad presentation/dao mix !
        session().commit()
        return editor

    def get_displayed_data(self,index):
        mainlog.debug("TaskComboDelegate : get_displayed_data")
        d = index.model().data( index,Qt.UserRole)
        if d:
            res = d.description
        else:
            res = None

        # FIXME bad presentation/dao mix !
        session().commit()
        mainlog.debug("TaskComboDelegate : get_displayed_data -- commit")

        return res

    def setModelData(self,editor,model,index):
        ndx = editor.currentIndex()

        if ndx < 0:
            ndx = 0

        data = editor.itemData( ndx, Qt.UserRole)
        model.setData(index,data,Qt.UserRole)


# FIXME Name is bad : this actually work with all kinds of tasks

class TaskOnOrderPartPrototype(Prototype):
    def __init__(self,field,title,on_date,editable=True,nullable=False):
        super(TaskOnOrderPartPrototype,self).__init__(field, title,editable,nullable)
        global dao

        if on_date is None:
            raise Exception("Invalid date")

        self.set_delegate(TaskComboDelegate(None,on_date,None))

    def set_task_cache(self,cache):
        self.delegate().set_task_cache(cache)


# FIXME Works also for Order => name should be changed

class OrderPartIdentifierValidator(QValidator):
    def __init__(self):
        QValidator.__init__(self)
        self.matcher = re.compile("^ *[0-9]+[A-Za-z]* *$")

    def validate(self,intext,pos):
        if self.matcher.match(intext) or len(intext) == 0:
            return QValidator.Acceptable
        else:
            return QValidator.Invalid


# FIXME Name not right, should be xxxOnTask

class OrderPartOnTaskDelegate(StandardTableDelegate):

    def __init__(self,parent=None):
        super(OrderPartOnTaskDelegate,self).__init__(parent)
        self.identifier_validator = OrderPartIdentifierValidator()

    def setModelData(self,editor,model,index):
        # FIXME A proper way to do this is to use a regex
        # to know what kind of query to make.

        # Pay attention, we only look on accounting_labels
        # So preorder won't show up here

        if editor.text() and len(editor.text()) > 0:
            # If the user didn't enter anything in the cell
            # then we won't check anything. This is to handle
            # the case where one starts editing a cell and
            # then stop editing by clicking out of the table.

            # We look for order_parts, those are named like '1234A'
            t = dao.order_part_dao.find_by_full_id(editor.text())

            mainlog.debug("Found order part {}".format(t))
            if t:

                # Pay attention ! This component is being used
                # on the administrative side. It is expected to
                # be use at times where the order may be closed
                # Therefore, the following code allows time reporting
                # more or less at any time. For example, we allow
                # time reporting (by admin) after an order have been closed.
                # This will give some flexibility to the users.

                if t.order.state not in (OrderStatusType.preorder_definition, OrderStatusType.preorder_sent):
                    model.setData(index,t,Qt.UserRole)
                    # FIXME session access has nothing to do in the ProxyModel
                    # module. Move this away.
                    session().commit()
                    return
                else:
                    showWarningBox(_("Time reporting is not possible on preorders"),"")
            else:
                # No part were found, so we look for an order
                # whose name is like '1234' (no X part)

                try:
                    oid = int(editor.text())
                    t = dao.order_dao.find_by_accounting_label(oid,True)
                except ValueError as ex:
                    pass

                if t:
                    if t.state not in (OrderStatusType.preorder_definition, OrderStatusType.preorder_sent):
                        model.setData(index,t,Qt.UserRole)
                        session().commit()
                        return
                    else:
                        showWarningBox(_("Time reporting is not possible on preorders"),"")
                else:
                    showWarningBox(_("The order or order part with number {} doesn't exist.").format(editor.text()),"")

            # FIXME bad presentation/dao mix !
            session().commit()

        model.setData(index,None,Qt.UserRole)


    def get_displayed_data(self,index):

        # mainlog.debug("OrderPartOnTaskDelegate : get_displayed_data")

        if not index.isValid():
            return None

        res = None

        if index.data(Qt.UserRole) is not None:
            r = index.data(Qt.UserRole) # Why r ? :-)
            if isinstance(r,OrderPart):
                res = str(r.human_identifier)
            elif isinstance(r,Order):
                res = str(r.accounting_label)
            else:
                res = ""
        else:
            # FIXME why this ? Looks useless
            ndx = index.model().index(index.row(),index.column()+1) # Beware! Looking on the column on the right!
            task = ndx.data(Qt.UserRole)
            if not task:
                res = None
            elif isinstance(task,TaskOnOperation):
                res = task.operation.production_file.order_part.human_identifier
            elif isinstance(task,TaskOnOrder):
                res =  str(task.order.accounting_label)
            elif isinstance(task,TaskOnNonBillable):
                res = "" # Non billable stuff is not atached to any part #FIXME thus the name of this class is not good
            else:
                raise Exception("Unsupported type {} ".format(type(task)))

        # FIXME Most of the business logic in this method must be
        # be moved to the DAO to avoid this terrible commit()
        session().commit()
        # mainlog.debug("OrderPartOnTaskDelegate : get_displayed_data -- commit")
        return res

    def createEditor(self,parent,option,index):
        mainlog.debug("OrderPartOnTaskDelegate : createEditor")

        editor = super(OrderPartOnTaskDelegate,self).createEditor(parent,option,index)
        editor.setValidator(self.identifier_validator)
        return editor

    def setEditorData(self,editor,index):
        editor.setText(self.get_displayed_data(index))


class OrderPartOnTaskPrototype(Prototype):
    def __init__(self,field,title,editable=True,nullable=False):
        super(OrderPartOnTaskPrototype,self).__init__(field, title,editable,nullable)
        self.set_delegate(OrderPartOnTaskDelegate(None))


class IntegerNumberPrototype(Prototype):
    def __init__(self,field,title,mini=0,maxi=9999999,editable=True,nullable=False,default=0):
        super(IntegerNumberPrototype,self).__init__(field, title,editable,nullable)
        self.mini = mini
        self.maxi = maxi

        self._default = default

        # WARNING Pay attention, those objects have no parent => they
        # must be kept alive for the whole duration of the program, else,
        # you'll have ownership issues with Qt bindings

        self.set_delegate(NumbersTableDelegate(mini,maxi,None))

    def default_value(self):
        return self._default

class FloatNumberPrototype(Prototype):
    def __init__(self,field,title,mini=0,maxi=9999999,editable=True,nullable=False,default=0):
        super(FloatNumberPrototype,self).__init__(field, title,editable,nullable)
        self.mini = mini
        self.maxi = maxi
        self._default = default

        # WARNING Pay attention, those objects have no parent => they
        # must be kept alive for the whole duration of the program, else,
        # you'll have ownership issues with Qt bindings

        self.set_delegate(FloatTableDelegate(mini,maxi,None))

    def default_value(self):
        return self._default


class MoneyPrototype(Prototype):
    def __init__(self,field,title,editable=True,nullable=False,default=0):
        super(MoneyPrototype,self).__init__(field, title,editable,nullable)
        self._default = default

        # WARNING Pay attention, those objects have no parent => they
        # must be kept alive for the whole duration of the program, else,
        # you'll have ownership issues with Qt bindings

        self.set_delegate(EuroDelegate(None))

    def default_value(self):
        return self._default


class TimestampPrototype(Prototype):
    def __init__(self,field,title,editable=True,nullable=False,fix_date = None):
        super(TimestampPrototype,self).__init__(field, title,editable,nullable)
        # WARNING Pay attention, those objects have no parent => they
        # must be kept alive for the whole duration of the program, else,
        # you'll have ownership issues with Qt bindings
        self.fix_date = fix_date
        self.set_delegate(TimestampDelegate(None,fix_date)) # FIXME !!! not the right delegate ?

    def set_fix_date(self,d):
        self.delegate().set_fix_date(d)

    def default_value(self):
        return self.fix_date


class FutureDatePrototype(Prototype):
    def __init__(self,field,title,editable=True,nullable=False):
        super(FutureDatePrototype,self).__init__(field, title,editable,nullable)
        # WARNING Pay attention, those objects have no parent => they
        # must be kept alive for the whole duration of the program, else,
        # you'll have ownership issues with Qt bindings

        self.set_delegate(FutureDateDelegate(None))


class DatePrototype(Prototype):
    def __init__(self,field,title,editable=True,nullable=False):
        super(DatePrototype,self).__init__(field, title,editable,nullable)
        # WARNING Pay attention, those objects have no parent => they
        # must be kept alive for the whole duration of the program, else,
        # you'll have ownership issues with Qt bindings

        self.set_delegate(DateDelegate())

    def display_widget(self):
        if not hasattr( self, '_display_widget'):
            self._display_widget = QLabel()
        return self._display_widget

    def set_display_widget_data(self, data):
        self._display_widget.setText( date_to_dm(data))


class FilenamePrototype(Prototype):
    """ Standard filename prototype.
    """
    def __init__(self,field,title,default = None,editable=True,nullable=False,hidden=False,non_empty=False):
        super(FilenamePrototype,self).__init__(field, title,editable,nullable,hidden)
        # WARNING Pay attention, those objects have no parent => they
        # must be kept alive for the whole duration of the program, else,
        # you'll have ownership issues with Qt bindings

        if non_empty and nullable == True:
            raise Exception("Incoherent parameters")

        self.set_delegate(FilenameDelegate())

        self._non_empty = non_empty




class TextLinePrototype(Prototype):
    """ Standard line edit, no bells, no whistles.
    """
    def __init__(self,field,title,default = None,editable=True,nullable=False,hidden=False,non_empty=False, empty_string_as_None=False):
        super(TextLinePrototype,self).__init__(field, title,editable,nullable,hidden)
        # WARNING Pay attention, those objects have no parent => they
        # must be kept alive for the whole duration of the program, else,
        # you'll have ownership issues with Qt bindings

        if non_empty and nullable == True:
            raise Exception("Incoherent parameters")

        if non_empty:
            self.set_delegate(NotEmptyStringDelegate())
        else:
            self.set_delegate(StandardTableDelegate(None))

        self._default_value = default
        self._non_empty = non_empty
        self._empty_string_as_None = empty_string_as_None

    def default_value(self):
        return self._default_value

    def validate(self,value):
        # t = self.edit_widget().text()
        t = value

        if t:
            t = t.strip()
        else:
            t = ""

        if t == "" and not self.is_nullable:
            return _("{} can't be empty").format(self.title)
        else:
            return True

    def edit_widget_data(self):
        data = super(TextLinePrototype,self).edit_widget_data()
        if self._empty_string_as_None and not data:
            return None
        else:
            return data

    def display_widget(self):
        if not hasattr( self, '_display_widget'):
            self._display_widget = QLabel()
        return self._display_widget

    def set_display_widget_data(self, data):
        self._display_widget.setText( str( data))

class PasswordPrototype(Prototype,QObject):
    def __init__(self,field,title,editable=True):
        super(PasswordPrototype,self).__init__(field, title,editable,nullable=False,hidden=False)
        QObject.__init__(self)

        # WARNING Pay attention, those objects have no parent => they
        # must be kept alive for the whole duration of the program, else,
        # you'll have ownership issues with Qt bindings

        self.set_delegate(StandardTableDelegate(None))
        self._widget = None

    def eventFilter(self,obj,event):
        # This event filter allows the line edit to be cleared
        # when a key is first hit. This makes sure the user
        # doesn't edit an MD5 value.
        if event.type() == QEvent.KeyPress and self.first_hit:
            self.first_hit = False
            self._widget.setText("")
        return False

    def validate(self,value):
        # t = self.edit_widget().text()
        t = value

        if t:
            t = t.strip()
        else:
            t = ""

        if t == "":
            return _("{} can't be empty").format(self.title)
        else:
            return True

    def edit_widget(self,parent):
        if self._widget is None:
            w = super(PasswordPrototype,self).edit_widget(parent)
            w.setEchoMode(QLineEdit.Password)
            self._widget = w
            self.first_hit = True
            w.installEventFilter(self)
        return self._widget

    def edit_widget_data(self):
        if self._widget and self._widget.isModified():
            h = hashlib.md5()
            h.update(self._widget.text().encode('utf-8'))
            pw = h.hexdigest()

            return pw
        else:
            if not self._widget or len(self._widget.text()) == 0:
                return None
            else:
                return self._widget.text() # Password not changed => don't apply md5


class DurationPrototype(Prototype):
    def __init__(self,field,title,editable=True,nullable=False,default=0, format_as_float=True):
        super(DurationPrototype,self).__init__(field, title,editable,nullable)

        self._default = default
        # WARNING Pay attention, those objects have no parent => they
        # must be kept alive for the whole duration of the program, else,
        # you'll have ownership issues with Qt bindings

        self.set_delegate(DurationDelegate(None, format_as_float))

    def default_value(self):
        return self._default

from PySide.QtGui import QUndoCommand,QUndoStack
class UndoProxyEdit(QUndoCommand):
    def __init__(self, old_value, new_value, proxy_model, index):
        super(UndoProxyEdit,self).__init__()
        self._old_value, self._new_value, self._proxy_model, self._index = old_value, new_value, proxy_model, index
        self.setText("Undo")

    def undo(self):
        self._proxy_model._directSetData(self._index, self._old_value)

    def redo(self):
        self._proxy_model._directSetData(self._index, self._new_value)


class ProxyModel(QAbstractTableModel):
    """ This model has several functionalities that make it best suited
    for the editing of typed python data :
    - It maps onto a Python table.
    - It can make use of ''prototypes'' which allow to set each column
      a particular data type and the appropriate delegate (see Delegates in Qt).
    - allow to make some column editable or not, based on the ''prototype''
    - use the ''prototypes'' to easily convert objects to rows and vice versa

    Pay attention, this model doesn't honour the roles. But one
    can achieve role-like stuff using text_color_eval, etc.
    """

    def __init__(self,parent,width):
        super(ProxyModel,self).__init__(parent)
        self.table = []
        self.edit_mask = None
        self.width = width
        self.debug = True
        self.highligthted_line = None
        self.cell_flag_function = None
        self.headers = []

        self._undo_stack = QUndoStack()

    def setHeaderData(self,section,orientation,value,role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and section >= 0 and role == Qt.DisplayRole:
            if section > len(self.headers) - 1:
                self.headers += [None] * (section - (len(self.headers) - 1))
            self.headers[section] = value

    def headerData(self,section,orientation,role=Qt.DisplayRole):
        # mainlog.debug("headerData {} / {}".format(section, role))
        if orientation == Qt.Horizontal and section >= 0 and section < len(self.headers) and role == Qt.DisplayRole:
            return self.headers[section]

    def change_highlighted_line(self,ndx):
        if ndx.isValid():
            self.highligthted_line = ndx.row()
        return

        # if ndx.isValid():
        #     top = ndx.row()
        #     bottom = self.highligthted_line
        #     if bottom is None:
        #         bottom = top

        #     if top > bottom:
        #         top,bottom = bottom,top
        #     self.highligthted_line = ndx.row()
        #     self.dataChanged.emit(self.index(top,0),self.index(bottom,self.columnCount()-1))

        # elif self.highligthted_line is not None:
        #     top,bottom = self.highligthted_line
        #     self.dataChanged.emit(self.index(top,0),self.index(bottom,self.columnCount()-1))

    def parent(self):
        return QModelIndex()

    def isIndexValid(self,ndx):
        return ndx.isValid() and ndx.row() >= 0 and ndx.row() < self.rowCount() and ndx.column() >= 0 and ndx.column() < self.columnCount()

    def index(self, row, column, parent = QModelIndex()):
        # When one reads Qt's doc, nothing indicates that an
        # index is invalid if it points outside the model.
        # So I add that behaviour.

        if row < self.rowCount() and column < self.columnCount():
            # if row/col are negative, this will create an invalid
            # index anyway.
            return self.createIndex(row, column)
        else:
            return self.createIndex(-1, -1)

    def rowCount(self,parent = None):
        # print "rowCount {}".format(len(self.table))
        return len(self.table)

    def columnCount(self,parent = None):
        if self.rowCount() == 0:
            # print "columnCount 0"
            return 0
        else:
            # print "columnCount {}".format(len(self.table[0]))
            return len(self.table[0])

    def text_color_eval(self,index):
        pass

    def background_color_eval(self,index):
        if index.row() == self.highligthted_line:
            return QBrush(QColor(210, 255, 210))
        else:
            return None
        pass

    def data(self, index, role):
        # Role 32 == UserRole
        # 8 = BackgroundRole
        # mainlog.debug("data(r={},c={},role={})".format(index.row(),index.column(),role))

        if index.row() < 0 or index.row() >= len(self.table):
            # mainlog.warning("Index row ({}) out of bounds".format(index.row()))
            return None

        elif index.column() < 0 or index.column() >= len(self.table[index.row()]):
            # mainlog.warning("Index column ({}) out of bounds".format(index.column()))
            return None

        if role == Qt.DisplayRole and self.table[index.row()][index.column()] is not None:
            # Pay attention, my current hypothesis is this.
            # Since this model is made to work *only* with prototypes
            # (delegates) then all the display must be made through them
            # therefore, requesting the Qt.DisplayRole should never happen
            # However, this happens : Qt does it. And when it does, it
            # seems it forgets the delegates (or my delegates are not
            # set at the right time...). When I use "unicode" to convert
            # objects to displayable string, then Python calls __repr__
            # But the problem is that 1/ this repr is not exactly
            # what I want to display 2/ At ends up using it to compute
            # the size of the cell => although my delegate is, in the end
            # called to display the data, the cell size was not computed
            # according to the delegate's display but to the __repr__
            # one. And this breaks everything. So I decide to return
            # None. I tried to be clean with the setup of the delegate
            # That is, makes sure the delegates are in place before
            # the model changes (so that if Qt wants to recompute
            # the size of the cells, it finds the proper delegate to
            # do so and doesn't revert to this data(Qt.DisplayRole...
            # function) but so far I've failed...

            # print type(self.table[index.row()][index.column()])
            return None
            # return str(self.table[index.row()][index.column()]) # this doesn't leak
        elif role == Qt.UserRole:
            return self.table[index.row()][index.column()]
        elif role == Qt.TextColorRole:
            return self.text_color_eval(index)
        elif role == Qt.BackgroundRole:
            # mainlog.debug("calling self.background_color_eval(index)")
            return self.background_color_eval(index)
        else:
            return None

    def refreshData(self,index):
        self.dataChanged.emit(index,index)

    def _directSetData(self,index, value):
        self.table[index.row()][index.column()] = value
        self.dataChanged.emit(index,index)

    def setData(self, index, value, role):
        if role == Qt.UserRole:

            undo = UndoProxyEdit( self.table[index.row()][index.column()], value, self, index)
            self._undo_stack.push(undo)
            # self._directSetData(self,index, value)

            # mainlog.debug("set data(r={},c={},role={})".format(index.row(),index.column(),role))
            # FIXME need to extend the table if it is too small !
            # self.table[index.row()][index.column()] = value
            # self.dataChanged.emit(index,index)
            return True
        else:
            raise Exception("Can't work without UserRole")

    def flags(self, index):
        # print("flags(r={},c={})".format(index.row(),index.column()))

        if self.edit_mask:
            if index.column() >= len(self.edit_mask):
                mainlog.warning("Index out of range ({} but max is {})".format(index.column(),len(self.edit_mask)))
                return Qt.ItemIsEnabled

            m = self.edit_mask[index.column()]
            if isfunction(m): # hasattr(m,'__call__'):
                return m(index)
            else:
                return m
        else:
            return Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled

    def clear(self):
        if self.rowCount() > 0:
            self.removeRows(0,self.rowCount())

    def defaultRow(self):
        return [None]*self.width

    def insertRows(self, row, count, parentIndex = QModelIndex()):
        if count > 0:
            self.beginInsertRows(parentIndex,row,row+count-1)

            # Not exactly optimized but at least, with this, I'm sure
            # to guess the right width for the row

            if row < 0:
                row = 0

            for c in range(count):
                # pay attention, each row must be distinct (I cannot insert
                # count times the same row)
                self.table.insert( row, self.defaultRow())

            self.endInsertRows()
        return True

    def removeRows(self, row, count, parentIndex = QModelIndex()):
        if count > 0 and row >= 0:
            self.beginRemoveRows(parentIndex,row,row+count-1)
            del(self.table[row:(row+count)])
            self.endRemoveRows()
            return True
        else:
            return False

    def removeColumns(self, col, count, parentIndex = QModelIndex()):
        if count > 0 and col >= 0:
            self.beginRemoveColumns(parentIndex,row,row+count-1)
            del(self.table[row:(row+count)])
            self.endRemoveColumnss()
            return True
        else:
            return False

    def set_edit_mask(self,prototype):
        self.edit_mask = []
        for k in prototype:
            if k.is_editable == True:
                # mainlog.debug("set_edit_mask: {} editable".format(k))
                self.edit_mask.append(Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            elif isfunction(k.is_editable): # hasattr(k.is_editable,'__call__'):
                self.edit_mask.append(k.is_editable)
            else:
                # mainlog.debug("set_edit_mask: {} NOT editable".format(k))
                self.edit_mask.append(Qt.ItemIsEnabled | Qt.ItemIsSelectable )


    def object_to_row(self,o,prototype):
        row = []
        for k in prototype:
            if k.field:
                v = None
                try:
                    # mainlog.debug("object_to_row {}".format(k.field))
                    v = getattr(o,k.field)
                    # v = None

                    # mainlog.debug("Row append {} {}".format(k.field,v))
                except AttributeError as e:
                    mainlog.error("The field {} was not found in the object {}".format(k.field,o).encode(sys.getdefaultencoding(),'ignore'))
                    mainlog.exception(e)

                except Exception as e:
                    mainlog.error("I had a problem while accessing the field {} in the object {}".format(k.field,o).encode(sys.getdefaultencoding(),'ignore'))
                    mainlog.exception(e)

                row.append(v)

            else:
                # mainlog.debug("Skipping {}".format(k))
                row.append(None)
        return row

    def add_objects_to_model_helper(self,objects,prototype):
        if objects is not None or objects == []:
            # Fill in the table
            for o in objects:
                row = self.object_to_row(o,prototype)
                self.table.append( row)


    def _buildModelFromObjectsHelper(self,objects,prototype):
        self.set_edit_mask(prototype)

        # The following can accept list, array, iterator or None for
        # the "objects" parameter"
        self.table = [self.object_to_row(o,prototype) for o in objects or []]

        if not self.table:
            self.table = [  [None]*len(prototype) ]


    def _buildModelFromObjects(self,objects,prototype):
        self.beginResetModel()
        self._buildModelFromObjectsHelper(objects,prototype)
        self.endResetModel()

    def extract_rows_as_objects(self, begin, end, prototype):
        rows = self.extract_rows(begin, end)
        objs = []

        for row in rows:
            d = dict( list(zip( [p.field for p in prototype], row)))
            obj = type("ProxyModelCopy", (object,), d)()
            objs.append(obj)

        return objs


    def extract_rows(self,begin,end):
        if begin < 0 or begin >= len(self.table):
            raise Exception("Begin index out of range ({})".format(begin))

        if end < 0 or end >= len(self.table):
            raise Exception("End index out of range ({})".format(begin))

        if begin > end:
            raise Exception("Begin index ({}) after end index ({}) ".format(begin,end))

        # We give a copy of the table, not the table
        # itself. That's defensive programming.

        # print "extract_rows : {} to {}".format(begin,end)
        t = []

        for y in range(begin,end+1):
            t.append(list(self.table[y]))

        return t

    def extract_all_rows(self):
        return self.extract_rows(0,len(self.table)-1)

    def insert_data(self,row_ndx,data):
        """ Insert a set of rows at row_ndx
        """

        if not data or len(data) == 0:
            return

        if row_ndx < 0:
            row_ndx = 0

        parentIndex = QModelIndex()
        self.beginInsertRows(parentIndex,row_ndx,row_ndx+len(data)-1)
        for c in range(len(data)):

            inserted_data = []
            for i in range(len(self.prototype)):
                if not self.prototype[i].is_editable:
                    inserted_data.append(None)
                else:
                    inserted_data.append(data[c][i])

            self.table.insert(row_ndx+c,inserted_data)

        self.endInsertRows()


class TrackingProxyModel(ProxyModel):
    """ A ProxyModel that associates an object to each of its row.
    The association is made when the model is built (see
    _buildModelFromObjects). This allows to *buffer* the changes
    to the model before committing them.

    After that, either :
    - one removes a row and the object that was associated to it
      is marked as deleted (and remembered)
    - one adds a row and that row is assumed to be blank and
      consequently, the object associated to it is None

    An additional feature is the row protection function that
    allows to protect a row under user-defined circumstances.
    """

    def __init__(self,parent,prototype):
        super(TrackingProxyModel,self).__init__(parent,len(prototype))
        self.prototype = prototype

        # The objects field is public. Be very careful with it, because
        # None's can be there (when a new row was added in the model)

        self.objects = []
        self.deleted_objects = []
        self.row_protect_announce = self.row_protect_func = None
        self.row_update_protect_announce = self.row_update_protect_func = None

    def clear_column(self,field_name):
        # FIXME not exactly fast
        ndx = map(lambda p : p.field, self.prototype).index(field_name)

        for r in range(self.rowCount()):
            self.setData(self.index(r,ndx), None,Qt.UserRole)

    def set_row_protect_func(self,func,announce = None):
        """ func takes two parameters, an object and a row (array).
        The function will allow to decide to protect a row against
        deletion (not against update!). The function returns True
        if the row must be protected.
        """

        self.row_protect_func = func
        self.row_protect_announce = announce

    def flags(self, index):

        f = super(TrackingProxyModel,self).flags(index)

        row = index.row()
        if self.row_update_protect_func:
            if index.isValid() and row >= 0 and row < len(self.objects) and self.row_update_protect_func(self.objects[row], self.table[row]):
                f = f & ~Qt.ItemIsEditable & ~Qt.ItemIsEnabled
            else:
                f = f | Qt.ItemIsEditable

        return f

    def object_index(self, obj):
        return self.index( self.objects.index(obj), 0)

    def object_field_updated(self, obj, proto_field):
        """

        :param obj:
        :param proto_field:
        :param value:
        :return:
        """
        mainlog.debug("object_field_updated : {}".format(proto_field))
        row = self.objects.index(obj)
        value = getattr( obj, proto_field)
        self.row_field_updated(row, proto, value)

        # col = self.prototype.index_of(proto_field)
        # ndx_begin = self.index( row, col)
        # ndx_end = self.index( row, col)
        # self.table[row][col] = getattr( obj, proto_field)
        # self.dataChanged.emit( ndx_begin, ndx_end)
        # mainlog.debug("object_field_updated : done")


    def row_field_updated(self, row, proto_field, value):
        """

        :param obj:
        :param proto_field:
        :param value:
        :return:
        """
        mainlog.debug("row_field_updated : {}".format(proto_field))
        col = self.prototype.index_of(proto_field)

        self.table[row][col] = value

        ndx_begin = self.index( row, col)
        ndx_end = self.index( row, col)
        self.dataChanged.emit( ndx_begin, ndx_end)

        mainlog.debug("row_field_updated : done")


    def row_field_value(self, row_number, proto_field):
        col = self.prototype.index_of(proto_field)
        return self.table[row_number][col]

    def object_changed(self, obj):

        # Mark the row
        ndx_begin = self.index( self.objects.index(obj), 0)
        ndx_end = self.index( ndx_begin.row(), self.columnCount() - 1)

        self.beginResetModel()
        mainlog.debug("Reset model Reset model Reset model Reset model Reset model Reset model Reset model ")
        self.endResetModel()

        self.dataChanged.emit( ndx_begin, ndx_end)

    def value_at(self, row : int, column_label : str, role = Qt.UserRole):
        # We suppose the prototype is of type PrototypeArray
        c = self.prototype.index_of(column_label)
        return self.data( self.index( row, c), role)


    def object_at(self,ndx):
        """ The object on the same row as the passed index.
        The index can be either an int (in this case it's a row number)
        or a QModelIndex (and in this case, we'll usse ndx.row())
        """

        if isinstance(ndx,QModelIndex):
            if ndx.isValid() and ndx.row() >= 0 and ndx.row() < len(self.objects):
                return self.objects[ndx.row()]
            else:
                raise Exception("Invalid QModelIndex")
        else:
            if ndx >= 0 and ndx < len(self.objects):
                return self.objects[ndx]
            else:
                raise Exception("Invalid index {}".format(ndx))


    def columnCount(self,parent = None):
        # print "columnCount"

        # Pay attention. This is not quite coherent with what happens
        # in the model in case one clears the whole model (i.e. so
        # there are zero columns in it). We do this because if a
        # model has a row count of 0 then Qt's view concludes that
        # there are no header to show. In that case, the header in the
        # view is not shown and it's not very nice from the user
        # point of view. So count this as a slight hack.
        # However, we can do this because we know the prototype
        # dictates the width of the model, so this number is actually
        # valid except when we rebuild the model. In that case,
        # since we begin by clearing the model, this column count
        # is wrong until the first row of data is added to the model.

        return len(self.prototype)


    # def headerData(self, section, orientation, role = Qt.DisplayRole ):
    #     # Pay attention, for some reason, the test on the role value
    #     # is absolutely mandatory

    #     if orientation == Qt.Orientation.Horizontal and role == Qt.DisplayRole and section < len(self.prototype):
    #         return self.prototype[section].title
    #     elif orientation == Qt.Orientation.Vertical and role == Qt.DisplayRole:
    #         return str(section+1)
    #     else:
    #         return None

    def insertRows(self, row, count, parentIndex = QModelIndex()):
        if row < 0:
            row = 0

        for i in range(count):
            self.objects.insert(row,None)

        r = super(TrackingProxyModel,self).insertRows(row, count, parentIndex)
        # print("TrackingModel = inserted {} rows at {}, model.rowCount = {} / current size is {}".format(count,row,self.rowCount(), len(self.objects)))
        return r




    def insert_data(self,row_ndx,data):

        if not data or len(data) == 0:
            return

        if row_ndx < 0:
            row_ndx = 0

        for i in range(len(data)):
            self.objects.insert(row_ndx,None)

        return super(TrackingProxyModel,self).insert_data(row_ndx, data)



    def are_rows_protected(self,row, count = 1):
        if count <= 0 or row < 0 or (self.rowCount() > 0 and row >= self.rowCount()):
            raise Exception("Invalid row/count : {}/{}. Must be < {}".format(row,count,self.rowCount()))

        if self.row_protect_func:
            for i in range(row,row+count):
                if self.row_protect_func(self.objects[i], self.table[row]):
                    return True

        return False


    def clear(self):
        """ Completely clears the model. Be careful ! This will *not* apply row
        protection. Will also forget the deleted objects.
        So use this function only to completely reset the model.
        """

        # Temporarily disable row protection
        rpf = self.row_protect_func
        self.row_protect_func = None

        r = super(TrackingProxyModel,self).clear()
        self.objects = []
        self.deleted_objects = []

        # Restore row protection
        self.row_protect_func = rpf



    def removeRows(self, row, count, parentIndex = QModelIndex()):
        if self.rowCount() != len(self.objects):
            raise Exception("TrackingProxyModel.removeRows() The rowCount and objects array length  now disagree : {} {}".format(self.rowCount(), len(self.objects)))

        if self.are_rows_protected(row, count):
            if self.row_protect_announce:
                self.row_protect_announce()
            mainlog.debug("removeRows : delete was prevented by row protection")
            return False

        # super first, it's crucial because of :
        # https://bugreports.qt-project.org/browse/QTBUG-11406

        r = super(TrackingProxyModel,self).removeRows(row, count, parentIndex = QModelIndex())

        if count > 0 and row >= 0:
            for o in self.objects[row:(row+count)]:
                if o is not None:
                    self.deleted_objects.append(o)

            del(self.objects[row:(row+count)])

        # print("TrackingModel = removed rows, row count = {} / current size is {}".format(self.rowCount(), len(self.objects)))

        if self.rowCount() != len(self.objects):
            raise Exception("TrackingProxyModel.removeRows() {} {}".format(self.rowCount(), len(self.objects)))

        return r

    def swap_row(self,ndx,ndx2, emit=True):
        mainlog.debug("TrackingProxyModel: swap_row")

        if ndx >= 0 and ndx2 >= 0 and ndx < self.rowCount() and ndx2 < self.rowCount() and ndx != ndx2:
            # FIXME use rowsAboutToBeMoved ???
            t = self.table[ndx2]
            o = self.objects[ndx2]
            self.table[ndx2] = self.table[ndx]
            self.objects[ndx2] = self.objects[ndx]
            self.table[ndx] = t
            self.objects[ndx] = o

            if emit:
                self.dataChanged.emit(self.index(ndx,0),self.index(ndx,self.columnCount()-1))
                self.dataChanged.emit(self.index(ndx2,0),self.index(ndx2,self.columnCount()-1))
            return True
        else:
            return False

    # def flags(self, index):
    #     if not index.isValid():
    #         # mainlog.warning("index({}) for flags is not right. Max is {}".format(index.row(),len(self.objects)))
    #         return Qt.NoItemFlags

    #     if self.are_rows_protected(index.row()):
    #         mainlog.debug("flags() : row {} protected".format(index.row()))
    #         return Qt.ItemIsSelectable | Qt.ItemIsEnabled  # Qt.NoItemFlags
    #     else:
    #         return super(TrackingProxyModel,self).flags(index)

    def add_objects_to_model(self,objects,prototype):
        if objects and len(objects) > 0:
            self.beginResetModel()
            self.add_objects_to_model_helper(objects,prototype)
            self.objects += objects
            self.endResetModel()


    def _buildModelFromObjects(self,objects,copy_objects=True,delete_current=False):

        if objects and not isinstance(objects,list):
            raise Exception("Expected a list (you gave {})".format(type(objects)))

        self.beginResetModel()

        if not delete_current:
            self.deleted_objects = []
        else:
            self.deleted_objects += [obj for obj in self.objects if obj is not None]

        self.objects = []

        self._buildModelFromObjectsHelper(objects,self.prototype)

        for o in objects or []:
            if copy_objects:
                self.objects.append(o)
            else:
                self.objects.append(None)

        # mainlog.debug(u"TrackingProxyModel._buildModelFromObjects -- added {} objects".format(len(self.objects)))
        # for o in self.objects:
        #     mainlog.debug(u"TrackingProxyModel._buildModelFromObjects -- added {}".format(o))

        if not self.objects:
            self.objects.append(None)


        self.endResetModel()
        #mainlog.debug("TrackingProxyModel._buildModelFromObjects -- END ({}s to compute)".format((datetime.now() - chrono).total_seconds()))


    def isRowEmpty(self,row_ndx):
        """ A row is empty if the user has not typed anything in the
        editable cells (which is slightly different than saying
        that all its cells are "None") """

        for ic in range(len(self.prototype)):
            item = self.data( self.index(row_ndx,ic), Qt.UserRole)
            p = self.prototype[ic]
            if item is not None and p.is_editable:
                return False
        return True


    def validate(self):
        """ Validate the table. Returns a dict of errors (line number -> list of errors) if any or None. """

        errors = dict()

        for ir in range(self.rowCount()):

            row = []
            row_empty = True

            for ic in range(len(self.prototype)):
                item = self.data( self.index(ir,ic), Qt.UserRole)
                p = self.prototype[ic]
                # print p

                # Figure out if the table cell we're looking
                # at was filled in by the user.
                # A row is deemed "empty" if all of its cells
                # are either None or not editable...

                if item is not None and p.is_editable:
                    row_empty = False

                row.append(item)

            if not row_empty:

                # The row appear to be changed so we validate
                # its content

                row_errors = []
                for ic in range(len(self.prototype)):
                    p = self.prototype[ic]
                    # mainlog.debug("validate row:{}/col:{} : proto={}".format(ir,ic,p))

                    if p.is_editable: # only validate columns that are editable
                        validation_result = p.validate(row[ic]) # FIXME BUG use row[ic] or the edit widget in the prototype

                        if validation_result is not True:
                            # mainlog.debug(u"validate result {}".format(validation_result).encode(sys.getdefaultencoding(),'ignore'))
                            row_errors.append(validation_result)

                if len(row_errors) > 0:
                    errors[ir] = row_errors

        if len(errors) > 0:
            # mainlog.debug(u"validate result. errors are {}".format(errors).encode(sys.getdefaultencoding(),'ignore'))
            return errors
        else:
            return None

    def _extract_row(self,ndx):
        # mainlog.debug("model_to_objects : starting evaluation of row {}".format(ir))
        row = []
        row_empty = True

        for ic in range(len(self.prototype)):
            item = self.data( self.index(ndx,ic), Qt.UserRole)
            p = self.prototype[ic]

            # Figure out if the table cell we're looking
            # at was filled in by the user.
            # A row is deemed "empty" if all of its cells
            # are either None or not editable...

            # FIXME "is_editable" is not right because what we
            # really mean is that some columns are nto tied
            # to an object. Therefore, they must not
            # be taken into account when evaluating if the
            # row is to be deleted. It's different than saying
            # "editable" or not. Because a column can be
            # represent an editable attribute of an object
            # which is made not editable in the table.
            if item is not None and p.is_editable:
                row_empty = False

            row.append(item)

        if row_empty:
            return None
        else:
            return row



    def is_changed(self):
        """ Return True if the data that were originally fed into the
        table have been changed.

        Pay attention ! This function will check the whole table and
        also will access the objects it knows about (which may trigger
        data loads) """


        if len(self.deleted_objects) > 0:
            return True

        for ir in range(self.rowCount()):
            row = self._extract_row(ir)

            if row is None and self.objects[ir] is not None:
                return True # Row cleared
            elif row and self.objects[ir] is None:
                return True # Row added
            elif row and self.objects[ir]: # maybe updated

                for ic in range(len(self.prototype)):
                    if self.prototype[ic].field and self.prototype[ic].is_editable:
                        value = row[ic]
                        if value is None:
                            value = self.prototype[ic].default_value()

                        original_value = getattr(obj,self.prototype[ic].field)
                        # mainlog.debug(u"Comparing : {} == {}".format(v, value))

                        if original_value != value:
                            return True

        return False

    # def row_to_object(self,row_ndx,factory):
    #     if row_ndx < 0 or row_ndx >= len(self.rowCount()):
    #         return None

    #     for ic in range(len(self.prototype)):
    #         if self.prototype[ic].field and self.prototype[ic].is_editable:
    #             value = self.data( self.index(ir,ic), Qt.UserRole)
    #             if value is None:
    #                 value = self.prototype[ic].default_value()
    #             setattr(obj,self.prototype[ic].field,value)


    def model_to_objects(self,factory,defaults=None):
        """ Will return an array representing what to do with
        the objects in the table. Each row of the array is a
        tuple : (action, object, index).

        Object is the associated object. The fields of that
        object may have been updated if the action is TO_UPDATE.
        If the action is TO_CREATE then the fields of the object
        reflect the input of the user (i.e. the content of the
        table).

        Index is the position of the object in the table. For a
        TO_DELETE action, the index is None (as the associated
        object is not represented in the table anymore)

        Action is as follow :
        * TO_CREATE objects are those represented by lines that were
          added to/inserted into the table
        * TO_UPDATE objects are those represented by lines that were
          updated into the table
        * TO_DELETE objects are those represented by lines that were
          deleted from the table. Note that if a line is added and
          afterwards removed, then it won't show up as deleted because
          that line was never associated  to an object.
        * UNCHANGED objects are those that were not changed.

        Warning! If lines of the table are shuffled, the are still
        reported as "UNCHANGED". But for that we report an index
        of the object in the table.

        Principle one : several call to this method will not change the
        content of the _table_ nor its links with actual objects. However
        it may change the objects.

        Principle two : objects may be created or *updated* by this method
        /regardless/ of the fact that there are errors or not in the
        data. Therefore, it is the caller's responsibility to ensure
        that if a row of the table is invalid then he has to
        discard the object associated to it.

        """

        # to_create = []
        # to_update = []
        # to_delete = []
        results = []

        # mainlog.debug("model_to_objects : {} rows".format(self.rowCount()))
        # mainlog.debug("model_to_objects : {} objects".format(len(self.objects)))

        for ir in range(self.rowCount()):

            # mainlog.debug("model_to_objects : starting evaluation of row {}".format(ir))
            row = []
            row_empty = True

            for ic in range(len(self.prototype)):
                item = self.data( self.index(ir,ic), Qt.UserRole)
                p = self.prototype[ic]

                # Figure out if the table cell we're looking
                # at was filled in by the user.
                # A row is deemed "empty" if all of its cells
                # are either None or not editable...

                # FIXME "is_editable" is not right because what we
                # really mean is that some columns are nto tied
                # to an object. Therefore, they must not
                # be taken into account when evaluating if the
                # row is to be deleted. It's different than saying
                # "editable" or not. Because a column can be
                # represent an editable attribute of an object
                # which is made not editable in the table.
                if item is not None and p.is_editable:
                    row_empty = False

                row.append(item)

            if row_empty:
                # mainlog.debug("model_to_objects : row {} is empty.".format(ir))

                # It was therefore either never filled by the
                # user or completely blanked, column by column per
                # the user.

                if self.objects[ir] is not None:

                    # There's an object associated to the row
                    # Therefore we guess the intention of the user
                    # was to delete the object (by clearing the row)

                    # to_delete.append(objects[ir])
                    mainlog.debug("model_to_objects : about to delete object {} because row is empty and object is not.".format(ir))
                    results.append( (DBObjectActionTypes.TO_DELETE, self.objects[ir], ir))
                else:

                    # There's no object. So the row is a blank
                    # row that was inserted and, maybe, filled and
                    # then emptied again. In any case, it means
                    # we can discard it.

                    # results.append( (DBObjectActionTypes.UNCHANGED,None,ir))
                    pass
            else:
                # mainlog.debug("model_to_objects : row {}/rowCount {}/objects count {} is not empty".format(ir,self.rowCount(),len(self.objects)))
                # mainlog.debug("model_to_objects : row {} is not empty; associated object is {}".format(ir,self.objects[ir]))

                obj = None

                if self.objects[ir] is None:
                    # It's a new object

                    # ATTENTION ! Since we use an object's validate() method
                    # to validate it, it is quite possible that we create
                    # an object and then come to the conclusion that that
                    # object is not valid. Therefore object may be created
                    # for nothing and thus, the object creation process
                    # must be light (no DB access...)

                    self.objects[ir] = obj = factory()
                    for ic in range(len(self.prototype)):
                        if self.prototype[ic].field and self.prototype[ic].is_editable:
                            # print("Set : {} := {}".format(prototype[ic].field,row[ic]))

                            value = row[ic]
                            if value is None:
                                value = self.prototype[ic].default_value()

                            try:
                                setattr(obj,self.prototype[ic].field,value)
                            except Exception as e:
                                mainlog.error("Can't set attribute {} on a new object".format(self.prototype[ic].field))
                                mainlog.exception(e)

                    # mainlog.debug("model_to_objects : placing object to TO_CREATE : {}".format(obj))
                    results.append( (DBObjectActionTypes.TO_CREATE,obj,ir))
                else:
                    # We're (maybe) updating an existing object
                    obj = self.objects[ir]

                    # Optimize a bit so we report TO_UPDATE only if there are actually
                    # changes (between the object's field and what is
                    # in the table)

                    updated = False
                    for ic in range(len(self.prototype)):
                        if self.prototype[ic].field and self.prototype[ic].is_editable:

                            value = row[ic]
                            if value is None:
                                value = self.prototype[ic].default_value()

                            v = getattr(obj,self.prototype[ic].field)
                            # mainlog.debug(u"Comparing : {} == {}".format(v, value))

                            if v != value:
                                try:
                                    # mainlog.debug("Set : {} := {}".format(self.prototype[ic].field,row[ic]))
                                    setattr(obj,self.prototype[ic].field,value)
                                    updated = True
                                except Exception as e:
                                    mainlog.error("Can't update attribute {} [col:{}] on {}".format(self.prototype[ic].field,obj,row[ic]))
                                    mainlog.exception(e)
                                    raise e

                    if updated:
                        # to_update.append(obj)
                        results.append( (DBObjectActionTypes.TO_UPDATE,obj,ir))
                    else:
                        # No field was updated
                        results.append( (DBObjectActionTypes.UNCHANGED,obj,ir))

        # The following accounts for the rows that were explicitely deleted by
        # the user. Explicitely means that the user used a command
        # to delete a row, rather than clearing each of its fields
        # one by one.

        for do in self.deleted_objects:
            results.append( (DBObjectActionTypes.TO_DELETE,do,None) )

        # return self.deleted_objects,to_create,to_update
        return results



    @classmethod
    def filter_db_updates(cls,db_updates):
        """ Return a triple of objects to delete, create and update
        based on a list of objects returned by model_to_objects.
        model_to_objects returns a list of objects sorted
        like on screen so that if an error occurs during one
        creation or update, we can show the user on which
        line of the table there's a problem.
        """

        res = {DBObjectActionTypes.TO_CREATE : [], DBObjectActionTypes.TO_UPDATE : [], DBObjectActionTypes.TO_DELETE:[] }

        if db_updates is None:
            return res

        for r in db_updates:
            t,obj,ndx = r
            if t is not DBObjectActionTypes.UNCHANGED:
                res[t].append(obj)

        return res[DBObjectActionTypes.TO_DELETE],res[DBObjectActionTypes.TO_CREATE],res[DBObjectActionTypes.TO_UPDATE]


class TableViewSignaledEvents(QTableView):
    """ The goal of this table view is to add some signal
    over the existing event. This allows to connect
    to the events through the signal mechanism and avoids
    the need to inherit from a QTableView to have access
    to events.

    But, I suppose there's a good reason in Qt to
    separated events from signals. Therefore handle
    with care...
    """

    def __init__(self,parent=None):
        return super(TableViewSignaledEvents,self).__init__(parent)

    focusIn = Signal()
    doubleClickedCell = Signal(QModelIndex)

    def focusInEvent( self, event ):
        self.focusIn.emit()
        return super(TableViewSignaledEvents,self).focusInEvent(event)

    def mouseDoubleClickEvent( self, event): #QMouseEvent
        super(TableViewSignaledEvents,self).mouseDoubleClickEvent(event)
        # mainlog.debug("mouseDoubleClickEvent {}-{}".format(self.currentIndex().row(),self.currentIndex().column()))
        self.doubleClickedCell.emit( self.currentIndex())



class PrototypedTableView(TableViewSignaledEvents):

    def __init__(self,parent,prototype):
        super(PrototypedTableView,self).__init__(parent)
        self.prototype = prototype
        self.allow_grow_table = True

        # import traceback
        # print "\n"
        # mainlog.debug("-------------------------")
        # print "\n"
        # traceback.print_stack()

        i = len(self.prototype) - 1
        for p in reversed(self.prototype):
            # mainlog.debug("_setup_delegates column {} -> looking is editable".format(i))
            if p.is_editable is not False: # True or a function
                # mainlog.debug(self.prototype)
                # mainlog.debug("setup_delegates : commitData {}.{} on column {}".format(id(self),id(p.delegate()),i))
                p.delegate().commitData.connect(self.delegate_commit_data)
                if p.is_editable == True: # And therefore it's not a function
                    break
            i = i - 1

        # print "\n"
        # mainlog.debug("------------------------- ////////////// ")
        # print "\n"

    def _lastEditableIndex(self, editedRow, columnIndexes=None):
        """Returns the first editable index in `originalIndex`'s row or None.

        If `columnIndexes` is not None, the scan for an editable index will be
        limited to these columns.
        """
        model = self.model()
        h = self.horizontalHeader()
        # editedRow = originalIndex.row()
        if columnIndexes is None:
            # We use logicalIndex() because it's possible the columns have been
            # re-ordered.
            columnIndexes = [h.logicalIndex(i) for i in range(h.count())]
        create = lambda col: model.createIndex(editedRow, col, None)
        scannedIndexes = [create(i) for i in columnIndexes if not h.isSectionHidden(i)]
        isEditable = lambda index: (model.flags(index) & Qt.ItemIsEditable) and self.prototype[index.column()].is_editable
        editableIndexes = list(filter(isEditable, scannedIndexes))
        return editableIndexes[-1] if editableIndexes else None

    @Slot(QWidget)
    def delegate_commit_data(self,editor):
        """ Automatically append a blank line to the model when editing
        reaches the end of the table.

        The trick is to make sure we append that line only when the
        user commits data in the last ediatble cell of the last row.
        (well, after lots of trials/errors I think that's the most
        user friendly way of doing this...)
        """

        if not self.allow_grow_table:
            return

        # mainlog.debug(type(editor))
        # mainlog.debug(type(self))
        # mainlog.debug(self.currentIndex())
        # mainlog.debug("Closing editor on COL last_ndx={}, current={}".format(self._lastEditableIndex(self.currentIndex().row()).column(),self.currentIndex().column()))

        # FIXME if I access the editor, I have :
        # Traceback (most recent call last):
        #   File "C:\Users\stefan\horse\horse\koi\ProxyModel.py", line 1673, in delegate_commit_data
        #     mainlog.debug("Closing editor on COL last_ndx={}, current={}, editor={}".format(self._lastEditableIndex(
        # x().column(),editor))
        # RuntimeError: Internal C++ object (ProxyTableView) already deleted.
        # Edit operation's description by double clicking on it, hit enter directly
        # close editor
        # do same operation


        if self.currentIndex().column() == self._lastEditableIndex(self.currentIndex().row()).column():
            last_ndx = self.model().rowCount()-1

            if self.currentIndex().row() == last_ndx and not self.model().isRowEmpty( last_ndx):
                self.model().insertRow(self.model().rowCount())

    def _setup_delegates(self):

        i = 0
        for p in self.prototype:
            d = p.delegate()
            # mainlog.debug("_setup_delegates column {} -> delegate {}".format(i,d))
            self.setItemDelegateForColumn(i, d)
            if isinstance(d,AutoComboDelegate) or isinstance(d,TextAreaTableDelegate):
                d.set_table(self) # FIXME unclean
            i = i + 1


    def rowsInsertedInModel(self,parent,start,end):
        # Pay attention, if one completely clears the model
        # then the view forgets that it has delegates set
        # for the columns. Therefore, if one adds rows again
        # to the model then the delegates won't be set
        # at all => all the rows inserted won't display/edit
        # correctly

        if start == 0 and (end + 1)  == self.model().rowCount():
            self._setup_delegates()

    def setModel(self,model):
        # Pay attention ! This ensures that the seleciotn model will be deleted
        # See QTableView.setModel() documentation for an explanation
        super(PrototypedTableView,self).setModel(model)

        if model:
            # FIXME This is not right. Setting several times the
            # same model will connect it several time and we know
            # PySide doesn't handle multiple commits very well.

            # print "settinug delegates !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            self._setup_delegates()
            model.rowsInserted.connect( self.rowsInsertedInModel)

    def selected_rows(self):
        s = set()
        for ndx in self.selectedIndexes():
            if ndx.row() >= 0:
                s.add( ndx.row())
        return s

class EditPanel(QFrame):
    def __init__(self,parent):
        super(EditPanel,self).__init__(parent)
        self.setObjectName("NavigationBar")

        self.add_pixmap = QPixmap(os.path.join(resource_dir,"plusplus_icon.png"))
        self.add_icon = QIcon(self.add_pixmap)
        self.row_add_button = QPushButton()
        self.row_add_button.setIcon(self.add_icon);
        self.row_add_button.setIconSize(self.add_pixmap.rect().size());
        self.row_add_button.setMaximumWidth(self.add_pixmap.rect().width() + 6)

        self.delete_pixmap = QPixmap(os.path.join(resource_dir,"minus_icon.png"))
        self.delete_icon = QIcon(self.delete_pixmap)
        self.row_delete_button = QPushButton()
        self.row_delete_button.setIcon(self.delete_icon);
        self.row_delete_button.setIconSize(self.delete_pixmap.rect().size());
        self.row_delete_button.setMaximumWidth(self.delete_pixmap.rect().width() + 6)

        self.insert_pixmap = QPixmap(os.path.join(resource_dir,"plus_icon.png"))
        self.insert_icon = QIcon(self.insert_pixmap)
        self.row_insert_button = QPushButton()
        self.row_insert_button.setIcon(self.insert_icon);
        self.row_insert_button.setIconSize(self.insert_pixmap.rect().size());
        self.row_insert_button.setMaximumWidth(self.insert_pixmap.rect().width() + 6)

        self.swap_pixmap = QPixmap(os.path.join(resource_dir,"up_icon.png"))
        self.swap_icon = QIcon(self.swap_pixmap)
        self.row_swap_button = QPushButton()
        self.row_swap_button.setContentsMargins(0,0,0,0)
        self.row_swap_button.setIcon(self.swap_icon);
        self.row_swap_button.setIconSize(self.swap_pixmap.rect().size());
        self.row_swap_button.setMaximumWidth(self.swap_pixmap.rect().width() + 6)

        l = QHBoxLayout()
        l.setSizeConstraint(QLayout.SetMinimumSize)
        l.setContentsMargins(0,0,0,0)
        self.setContentsMargins(0,0,0,0)
        l.addWidget(self.row_add_button)
        l.addWidget(self.row_insert_button)
        l.addWidget(self.row_delete_button)
        l.addWidget(self.row_swap_button)
        self.setLayout(l)

        self.row_delete_button.clicked.connect(self.delete_row)
        self.row_add_button.clicked.connect(self.add_row)
        self.row_insert_button.clicked.connect(self.insert_row)
        self.row_swap_button.clicked.connect(self.swap_row)



    def set_delete_action(self, action):
        self.delete_action = action

    def set_add_action(self, action):
        self.add_action = action

    def set_insert_action(self, action):
        self.insert_action = action

    def set_swap_action(self, action):
        self.swap_action = action

    @Slot()
    def delete_row(self):
        self.delete_action.trigger()

    @Slot()
    def add_row(self):
        self.add_action.trigger()

    @Slot()
    def insert_row(self):
        self.insert_action.trigger()

    @Slot()
    def swap_row(self):
        mainlog.debug("EditPanel : swap_row")
        self.swap_action.trigger()


class ProxyTableView(PrototypedTableView):

    def enable_edit_panel(self,enable=True):
        self.edit_panel_enabled = enable
        self.edit_panel.hide()

    def enterEvent(self,event):
        if self.edit_panel_enabled:
            self.edit_panel.show()
        return super(ProxyTableView,self).enterEvent(event)

    def leaveEvent(self,event):
        if self.edit_panel_enabled:
            self.edit_panel.hide()
        return super(ProxyTableView,self).leaveEvent(event)

    def resizeEvent(self,event):

        # So all the tables will have this behaviour (ie
        # no space wandering in the table after a resize)

        self.resizeRowsToContents()

        if self.edit_panel_enabled:

            r = self.edit_panel.geometry()

            # print "{}x{} {}x{}".format(event.size().width(), event.size().height(), self.zelabel.size().width(),self.zelabel.size().height())
            dx = 5
            dy = 5
            if self.horizontalScrollBar().isVisible():
                dy = dy + self.horizontalScrollBar().height()

            if self.verticalScrollBar().isVisible():
                dx = dx + self.verticalScrollBar().width()

            s = self.edit_panel.sizeHint()
            self.edit_panel.setGeometry( QRect(self.size().width() - s.width() - dx,
                                               self.size().height() - s.height() - dy,
                                               s.width(),
                                               s.height()))

        return super(ProxyTableView,self).resizeEvent(event)




    def __init__(self,parent,prototype):
        super(ProxyTableView,self).__init__(parent,prototype)
        self.controller = None
        self._last_edited_index = None

        self.edit_panel_enabled = False
        self.edit_panel = EditPanel(self)
        self.edit_panel.hide()



    def setModel(self,model):
        super(ProxyTableView,self).setModel(model)
        self._last_edited_index = None

    def last_edited_index(self):
        if self._last_edited_index:
            return self._last_edited_index
        else:
            return self.currentIndex()


    def keyPressEvent(self,event):
        super(ProxyTableView,self).keyPressEvent(event)
        index = self.currentIndex()

        if self.controller and index.isValid():
            if event.key() == Qt.Key_Delete:
                self.controller.delete_cell(index)
        else:
            # We can receive key event in the view even if the model
            # is empty.
            pass




    def _firstEditableIndex(self, editedRow, columnIndexes=None):
        """Returns the first editable index in `originalIndex`'s row or None.

        If `columnIndexes` is not None, the scan for an editable index will be
        limited to these columns.
        """
        model = self.model()
        h = self.horizontalHeader()
        # editedRow = originalIndex.row()
        if columnIndexes is None:
            # We use logicalIndex() because it's possible the columns have been
            # re-ordered.
            columnIndexes = [h.logicalIndex(i) for i in range(h.count())]
        create = lambda col: model.createIndex(editedRow, col, None)
        scannedIndexes = [create(i) for i in columnIndexes if not h.isSectionHidden(i)]
        isEditable = lambda index: (model.flags(index) & Qt.ItemIsEditable) and self.prototype[index.column()].is_editable
        editableIndexes = list(filter(isEditable, scannedIndexes))
        return editableIndexes[0] if editableIndexes else None

    def _previousEditableIndex(self, originalIndex):
        """Returns the first editable index at the left of `originalIndex` or None.
        """
        h = self.horizontalHeader()
        myCol = originalIndex.column()
        columnIndexes = [h.logicalIndex(i) for i in range(h.count())]
        # keep only columns before myCol
        columnIndexes = columnIndexes[:columnIndexes.index(myCol)]
        # We want the previous item, the columns have to be in reverse order
        columnIndexes = reversed(columnIndexes)
        return self._firstEditableIndex(originalIndex.row(), columnIndexes)

    def _nextEditableIndex(self, originalIndex):
        """Returns the first editable index at the right of `originalIndex` or None.
        """
        mainlog.debug("_nextEditableIndex : orignal = ({},{})".format(originalIndex.row(), originalIndex.column()))

        h = self.horizontalHeader()
        myCol = originalIndex.column()
        rawIndexes = [h.logicalIndex(i) for i in range(h.count())]

        # mainlog.debug(myCol)
        # mainlog.debug(str(rawIndexes))

        # keep only columns after myCol
        columnIndexes = rawIndexes[rawIndexes.index(myCol)+1:]
        n = self._firstEditableIndex(originalIndex.row(), columnIndexes)
        if n is not None:
            mainlog.debug("_nextEditableIndex : return ({},{})".format(n.row(), n.column()))
            return n
        else:
            # print("_nextEditableIndex() : no next. Trying next row. Row" +
            #       " is {}, count is {} ".format(originalIndex.row(),self.model().rowCount()))
            if originalIndex.row() < self.model().rowCount() - 1:
                n = self._firstEditableIndex(originalIndex.row() + 1, rawIndexes)
                mainlog.debug("_nextEditableIndex : return ({},{})".format(n.row(), n.column()))
                return n
            else:
                mainlog.debug("_nextEditableIndex : returning None")
                # print("no next row")
                return None

    def closeEditor(self, editor, hint):
        # We remind the last edited index because of a specific scenario
        # That is, in case the user hits "Ctrl-S" (or triggers any other
        # "edit leave" that is not an "enter" (enter means leave the current
        # edit and start editing the next cell, the "raions d'etre of this
        # very method), then we'd like to put he cursor back where
        # the user left it...

        self._last_edited_index = self.currentIndex()

        # mainlog.debug("entering closeEditor.Current index is {}/{}".format(self.currentIndex().row(),self.currentIndex().column()))

        # The code below was copied from a web page about MoneyGuru.
        # We thank the author for publishing it because without him
        # it would have taken us ages to figure it out.

        # The problem we're trying to solve here is the edit-and-go-away problem.
        # When ending the editing with submit or return, there's no problem, the
        # model's submit()/revert() is correctly called. However, when ending
        # editing by clicking away, submit() is never called. Fortunately,
        # closeEditor is called and, AFAIK, it's the only case where it's called
        # with NoHint (0). So, in these cases, we want to call model.submit()

        if hint == QAbstractItemDelegate.NoHint:
            # mainlog.debug("calling closeEditor-0")
            super(ProxyTableView,self).closeEditor(editor,
                QAbstractItemDelegate.SubmitModelCache)

        # And here, what we're trying to solve is the problem with editing
        # next/previous lines. If there are no more editable indexes, stop
        # editing right there. Additionally, we are making tabbing step over
        # non-editable cells
        elif hint in (QAbstractItemDelegate.EditNextItem,
                      QAbstractItemDelegate.EditPreviousItem):

            if hint == QAbstractItemDelegate.EditNextItem:
                editableIndex = self._nextEditableIndex(self.currentIndex())
            else:
                editableIndex = self._previousEditableIndex(self.currentIndex())

            # print "closeEditor(): {} / {}".format(self.currentIndex().row(), self.model().rowCount())
            if editableIndex is None:
                # mainlog.debug("calling closeEditor-1")
                super(ProxyTableView,self).closeEditor(editor,
                    QAbstractItemDelegate.SubmitModelCache)
            else:
                # mainlog.debug("calling closeEditor-2")
                super(ProxyTableView,self).closeEditor(editor, QAbstractItemDelegate.NoHint)
                self.setCurrentIndex(editableIndex)
                self.edit(editableIndex)
        else:
            # mainlog.debug("calling closeEditor-3")
            super(ProxyTableView,self).closeEditor(editor, hint)


def make_header_model( prototype) -> QStandardItemModel:
    headers = QStandardItemModel(1, len(prototype))
    i = 0
    for p in prototype:
        #print(i, p.title)
        headers.setHeaderData(i, Qt.Orientation.Horizontal, p.title)
        i = i + 1
    return headers


class PrototypeController(object):

    def paste_rows(self,begin_row,rows):
        if rows == None or len(rows) == 0:
            return

        self.model.insertRows(begin_row, len(rows), QModelIndex()) # BUG ??? QmodeIndex() should be optional

        for y in range(len(rows)):
            for x in range(len(rows[y])):
                self.model.setData(self.model.index(begin_row+y,x),rows[y][x],Qt.UserRole)

        self.view.clearSelection()
        self.view.setCurrentIndex( self.model.index(begin_row,0))
        # self.model_data_changed = True


    def insert_row(self,row,update_selection=False):
        if self.model:
            if row == -1 and self.model.rowCount() > 0:
                row = 0

            # Insert a blank row

            self.model.insertRows(row, 1, QModelIndex()) # BUG ??? QmodeIndex() should be optional
            # self.model_data_changed = True

            if update_selection and row >= 0:
                self.view.clearSelection()
                self.view.setCurrentIndex( self.model.index(row,0))

    def delete_row(self,row):
        self.model.removeRows(row, 1)
        # if self.model.removeRows(row, 1):
        #     self.model_data_changed = True

    def swap_row(self,ndx,ndx2):
        self.model.swap_row(ndx,ndx2)
        # if self.model.swap_row(ndx,ndx2):
        #     self.model_data_changed = True

    def delete_cell(self,index):
        if self.prototype[index.column()].is_editable and self.model.data(index, Qt.UserRole):
            self.model.setData(index, None, Qt.UserRole)
            # self.model_data_changed = True


    def setModel(self,model):
        if model == self.model:
            return

        # if model == None:
        #     raise Exception("You cannot set a null model")


        self.model = model

        # i = 0
        # for p in self.prototype:
        #     self.model.setHeaderData(i, Qt.Orientation.Horizontal, p.title, Qt.DisplayRole)
        #     i = i + 1

        # self.model_data_changed = False

        sm = self.view.selectionModel()

        # print self.view.selectionModel()
        # print "setting model to {}".format(self.model)

        self.view.setModel(self.model)
        # print self.view.selectionModel()

        if sm:
            # Pay attention, only do this if the old selection
            # model is actually different than this one !
            sm.setParent(None) # See bug 1041 in PySide
            # gc.collect()
            # print len(gc.get_objects())


        # When the view's model is changed (w/ setModel) one has to call
        # the update method. One also has to refresh the header
        # (I'm under the impression that changeing the model
        # actually chanages the header's view model...)

        sm = self.headers_view.selectionModel() # See below, this is Qt's leak...
        self.headers_view.setModel(self.header_model) # qt's doc : The view does *not* take ownership (bt there's something with the selecion model)
        if sm:
            pass
            # This crashes my code, maybe 1041 again ?
            # sm.setParent(None)

        # mainlog.debug("PrototypeController.setModel hiding sections with {}".format(self.prototype))
        for j in range(len(self.prototype)):
            if self.prototype[j].is_hidden:
                # mainlog.debug("hiding {}".format(j))
                self.headers_view.hideSection(j)
                self.view.hideColumn(j)

        self.view.update()

        self.view.selectionModel().currentChanged.connect(self.selection_changed)


    def _reload_row(self, row):
        if self.model and row >= 0 and row < self.model.rowCount():
            for col in range(self.model.columnCount()):
                self.view.update(self.model.index(row,col))

    @Slot(QModelIndex,QModelIndex)
    def selection_changed(self,current,previous):
        self.model.change_highlighted_line(current)
        self._reload_row(previous.row())
        self._reload_row(current.row())
        return

        # top=bottom=0
        # if current.isValid():
        #     top = current.row()
        #     bottom = self.model.highligthted_line
        #     if bottom is None:
        #         bottom = top

        #     if top > bottom:
        #         top,bottom = bottom,top
        #     self.model.change_highlighted_line(current)

        # elif self.highligthted_line is not None:
        #     top,bottom = self.model.highligthted_line

        # mainlog.debug("rereshing {} {}".format(top,bottom))
        # for row in range(top,bottom+1):
        #     for col in range(self.model.columnCount()):
        #         self.view.update(self.model.index(row,col))

    @Slot()
    def insert_row_slot(self):
        if self.model:
            ndx = self.view.currentIndex()
            if ndx.isValid():
                self.insert_row(ndx.row())
                self.view.setCurrentIndex( self.model.index(ndx.row(),ndx.column()))
            else:
                self.append_row_slot()

    @Slot()
    def append_row_slot(self):
        if self.model:
            ndx = self.view.currentIndex()
            self.insert_row(self.model.rowCount())
            self.view.selectionModel().clearSelection()

            if ndx.isValid():
                self.view.setCurrentIndex( self.model.index(self.model.rowCount()-1,ndx.column()))
            else:
                self.view.setCurrentIndex( self.model.index(self.model.rowCount()-1,0))


    @Slot()
    def delete_row_slot(self):
        if self.model and self.view.currentIndex().isValid():
            ndx = self.view.currentIndex()

            # Sometimes, the user can trigger a delete with a
            # current index that is actually outside the
            # cells of the table.

            if ndx.row() < self.model.rowCount():

                self.delete_row(ndx.row())

                # Move the current index
                row = min(ndx.row(),self.model.rowCount()-1)
                if row >= 0:
                    self.view.setCurrentIndex( self.model.index(row,ndx.column()))

    @Slot()
    def move_row_up_slot(self):
        ndx = self.view.currentIndex()
        if self.model and ndx.isValid() and ndx.row() > 0:
            self.swap_row(ndx.row(),ndx.row()-1)
            self.view.setCurrentIndex( self.model.index(ndx.row()-1,ndx.column()))
        else:
            mainlog.debug("move_row_up_slot : can't do it")

    @Slot()
    def move_row_down_slot(self):
        ndx = self.view.currentIndex()
        if self.model and ndx.isValid() and ndx.row() < self.model.rowCount() - 1:
            self.swap_row(ndx.row(),ndx.row()+1)
            self.view.setCurrentIndex( self.model.index(ndx.row()+1,ndx.column()))
        else:
            mainlog.debug("move_row_down_slot : can't do it")

    @Slot()
    def delete_cell_slot(self):
        ndx = self.view.currentIndex()
        if ndx.isValid():
            self.delete_cell(ndx)


    def prototype_at(self,ndx):
        if isinstance(ndx,str):
            for p in self.prototype:
                if p.field == ndx:
                    return p
            raise ValueError("The given index ({}) doesn't match any protoype field name".format(ndx))
        else:
            return self.prototype[ndx]


    def __init__(self,parent,prototype,view=None,freeze_row_count=False):
        self.prototype = prototype
        self.model = None
        # self.model_data_changed = False

        if view is None:
            self.view = ProxyTableView(parent,prototype)
            self.view.allow_grow_table = not freeze_row_count
        else:
            self.view = view



        if not freeze_row_count:
            self.insert_row_action = QAction(_('Insert row'),view)
            self.insert_row_action.triggered.connect( self.insert_row_slot)
            self.insert_row_action.setShortcut(QKeySequence(Qt.Key_F5))
            self.insert_row_action.setShortcutContext(Qt.WidgetShortcut)
            self.view.addAction(self.insert_row_action) # The ownership of action is not transferred to this QWidget.

            self.append_row_action = QAction(_('Append row'),view)
            self.append_row_action.triggered.connect( self.append_row_slot)
            self.append_row_action.setShortcut(QKeySequence(Qt.SHIFT + Qt.Key_F5))
            self.append_row_action.setShortcutContext(Qt.WidgetShortcut)
            self.view.addAction(self.append_row_action) # The ownership of action is not transferred to this QWidget.

            self.delete_row_action = QAction(_('Delete row'),view)
            self.delete_row_action.triggered.connect( self.delete_row_slot)
            self.delete_row_action.setShortcut(QKeySequence(Qt.Key_F8))
            self.delete_row_action.setShortcutContext(Qt.WidgetShortcut)
            self.view.addAction(self.delete_row_action) # The ownership of action is not transferred to this QWidget.

        self.move_row_up_action = QAction(_('Move row up'),view)
        self.move_row_up_action.triggered.connect( self.move_row_up_slot)
        self.move_row_up_action.setShortcut(QKeySequence(Qt.SHIFT + Qt.Key_F6))
        self.move_row_up_action.setShortcutContext(Qt.WidgetShortcut)
        self.view.addAction(self.move_row_up_action) # The ownership of action is not transferred to this QWidget.

        self.move_row_down_action = QAction(_('Move row down'),view)
        self.move_row_down_action.triggered.connect( self.move_row_down_slot)
        self.move_row_down_action.setShortcut(QKeySequence(Qt.Key_F6))
        self.move_row_down_action.setShortcutContext(Qt.WidgetShortcut)
        self.view.addAction(self.move_row_down_action) # The ownership of action is not transferred to this QWidget.

        self.delete_cell_action = QAction(_('Delete cell'),view)
        self.delete_cell_action.triggered.connect( self.delete_cell_slot)
        self.delete_cell_action.setShortcut(QKeySequence(Qt.Key_Delete))
        self.delete_cell_action.setShortcutContext(Qt.WidgetShortcut)
        self.view.addAction(self.delete_cell_action) # The ownership of action is not transferred to this QWidget.


        self.view.controller = self # FIXME too much of an hack

        if isinstance(self.view,ProxyTableView):
            if not freeze_row_count:
                self.view.edit_panel.set_delete_action(self.delete_row_action)
                self.view.edit_panel.set_add_action(self.append_row_action)
                self.view.edit_panel.set_insert_action(self.insert_row_action)
            self.view.edit_panel.set_swap_action(self.move_row_up_action)

        self.headers_view = QHeaderView(Qt.Orientation.Horizontal)
        self.header_model = make_header_model(self.prototype)
        self.view.setHorizontalHeader(self.headers_view)
        self.headers_view.setModel(self.header_model) # qt's doc : The view does *not* take ownership (bt there's something with the selecion mode
        # self.view.resizeRowsToContent()
        self.view.verticalHeader().setResizeMode(QHeaderView.ResizeToContents)

        # self.timer = QTimer(None)
        # self.timer.timeout.connect(self.test_bug)
        # self.timer.start(200)
