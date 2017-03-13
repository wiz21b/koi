from koi.gui.ComboDelegate import AutoComboDelegate
from koi.gui.ProxyModel import Prototype
from koi.gui.completer import AutoCompleteComboBox


class TaskComboDelegate2(AutoComboDelegate):
    """ The task combo delegate, if used as an editor, it must be
    located on a column at the *right* of an 'order part' column.
    """

    def __init__(self,items,on_date,section_width = None,parent=None):
        super(TaskComboDelegate2,self).__init__(parent)
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

        mainlog.debug("TaskComboDelegate : get_displayed_data -- commit")

        return res

    def setModelData(self,editor,model,index):
        ndx = editor.currentIndex()

        if ndx < 0:
            ndx = 0

        data = editor.itemData( ndx, Qt.UserRole)
        model.setData(index,data,Qt.UserRole)


# FIXME Name is bad : this actually work with all kinds of tasks

class TaskFromIdentifierPrototype(Prototype):
    def __init__(self,field,title,on_date,editable=True,nullable=False):
        super(TaskFromIdentifierPrototype,self).__init__(field, title,editable,nullable)
        global dao

        if on_date is None:
            raise "Invalid date"

        self.set_delegate(TaskComboDelegate2(None,on_date,None))

    def set_task_cache(self,cache):
        self.delegate().set_task_cache(cache)
