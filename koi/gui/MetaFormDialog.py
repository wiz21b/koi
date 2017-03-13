if __name__ == "__main__":
    import sys
    from PySide.QtGui import QApplication

    from koi.base_logging import init_logging
    from koi.Configurator import init_i18n,load_configuration, configuration
    init_logging()
    init_i18n()
    load_configuration()

    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session
    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)

from PySide.QtCore import Slot,Signal,QModelIndex,Qt
from PySide.QtGui import QDialog, QVBoxLayout, QDialogButtonBox, QFormLayout, QHBoxLayout, QPixmap, QPushButton, QItemSelectionModel, QMessageBox, QLineEdit, QWidget
from sqlalchemy.orm.collections import InstrumentedList

from koi.Configurator import mainlog
from koi.datalayer.database_session import session
from koi.gui.PrototypedModelView import PrototypedQuickView,PrototypedModelView
from koi.gui.dialog_utils import TitleWidget, SubFrame, showErrorBox, yesNoBox, showWarningBox
from koi.datalayer.generic_access import recursive_defrost_into, generic_delete, generic_load_all_frozen
from koi.gui.FilteringModel import FilteringModel


class FilterLineEdit(QLineEdit):

    key_down = Signal()

    def __init__(self):
        super(FilterLineEdit,self).__init__()

    def keyPressEvent(self,event):
        if event.key() == Qt.Key_Down:
            event.ignore()
            self.key_down.emit()

        return super(FilterLineEdit,self).keyPressEvent(event)


class MetaFormDialog(QDialog):

    def preselect_item(self,item):
        # Pay attention ! The selection implictely uses "__eq__" to find out
        # an object in the list of objects. So be careful with objects
        # that are outside sessions and which have no __eq__ operation : these
        # will be compared on basis of the python's Id which might defer for
        # 2 objects denoting the same thing. See Customer for an example.

        # mainlog.debug("Preselect item {}".format(item))
        # mainlog.debug("Preselect item in this list")
        # mainlog.debug(" -- ".join(sorted(map(lambda c:c.fullname,self.list_model.objects))))
        t = self.list_model.objects.index(item)
        # mainlog.debug("Preselect item index {}".format(t))
        self.list_view.setCurrentIndex(self.list_model.index(t,0))


    def __init__(self,parent,dialog_title,list_title,form_title,mapped_klass,table_prototype,form_prototype,sort_criterion,index_builder):

        """
        sort_criterion is a SQLAlchemy colum used when querying the list of edited objects to sort it.
        index_builder : a function that takes an object of the mapped class and returns a string
           suitable for index building.
        """
        super(MetaFormDialog,self).__init__(parent)

        self.index_builder = index_builder
        self.sort_criterion = sort_criterion
        self.form_prototype = form_prototype
        self.mapped_klass = mapped_klass
        # Locate the primary key
        # this will work only with a one-field PK
        pk_column = list(filter( lambda c:c.primary_key, self.mapped_klass.__table__.columns))[0]
        self.key_field = pk_column.name


        self.in_save = False

        # The current item is the one currently shown in the
        # form. If it's None, then the form contains data
        # for a soon-to-be created item. Else, it's a frozen
        # copy. Since we work on frozen stuff, we can carry
        # the object around safely

        self.current_item = None


        self.list_model = PrototypedModelView(table_prototype, self)

        self.list_model_filtered = FilteringModel(self)
        self.list_model_filtered.setSourceModel(self.list_model)

        self.line_in = FilterLineEdit()
        self.line_in.key_down.connect(self._focus_on_list)
        self.line_in.textChanged.connect(self._filter_changed)

        self.list_view = PrototypedQuickView(table_prototype, self)
        self.list_view.setTabKeyNavigation(False)


        self.setWindowTitle(dialog_title)
        self.title_widget = TitleWidget(dialog_title,self)

        self.list_view.setModel(self.list_model_filtered)
        self.list_view.horizontalHeader().hide()
        self.list_view.verticalHeader().hide()
        self.list_view.horizontalHeader().setStretchLastSection(True)


        blayout = QVBoxLayout()

        b = QPushButton(_("New"))
        b.setObjectName("newButton")

        b.clicked.connect(self.create_action)
        blayout.addWidget(b)

        b = QPushButton(_("Save"))
        b.setObjectName("saveButton")
        b.clicked.connect(self.save_action)
        blayout.addWidget(b)

        b = QPushButton(_("Delete"))
        b.setObjectName("deleteButton")
        b.clicked.connect(self.delete_action)
        blayout.addWidget(b)

        blayout.addStretch()

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.Ok)

        # BUG According to QLayout, the layout takes ownership of the widget
        # therefore, we have to pay attention when deleting...

        form_layout = QFormLayout()
        for p in self.form_prototype:
            w = p.edit_widget(self)
            w.setEnabled(p.is_editable)
            w.setObjectName("form_" + p.field)
            form_layout.addRow( p.title, w)

        top_layout = QVBoxLayout()
        top_layout.addWidget(self.title_widget)

        hl = QHBoxLayout()


        vlayout = QVBoxLayout()

        vlayout.addWidget(self.line_in)
        vlayout.addWidget(self.list_view)
        # gbox = QGroupBox(list_title,self)
        # gbox.setLayout(vlayout)
        gbox = SubFrame(list_title,vlayout,self)
        hl.addWidget(gbox)

        # gbox = QGroupBox(form_title,self)
        # gbox.setLayout(form_layout)
        gbox = SubFrame(form_title,form_layout,self)
        hl.addWidget(gbox)
        hl.addLayout(blayout)

        # hl.setStretch(0,0.3)
        # hl.setStretch(1,0.7)
        # hl.setStretch(2,0)

        top_layout.addLayout(hl)
        top_layout.addWidget(self.buttons)

        self.setLayout(top_layout) # QWidget takes ownership of the layout
        self.buttons.accepted.connect(self.reject)

        QWidget.setTabOrder(self.line_in, self.list_view)

        nb_objs = self._refresh_list()
        self.line_in.setFocus()
        self.list_view.selectionModel().currentChanged.connect(self.selected_item_changed) # FIXME Clear ownership issue
        if nb_objs > 0:
            self.list_view.selectRow(0)
        else:
            # Special case to automaticaly enter creation mode when
            # the list is empty
            self.create_action()

    @Slot()
    def _focus_on_list(self):
        """ When the user hits the down key on the filter, we transfer
        the focus to the filtered list
        """
        self.list_view.setFocus()
        self.list_view.selectionModel().setCurrentIndex(self.list_view.model().index(0,0), QItemSelectionModel.ClearAndSelect)


    def _filter_changed(self,s):
        self.list_model_filtered.setFilterFixedString(s)
        # self.list_view.selectRow(0)

        self.list_view.selectionModel().setCurrentIndex(self.list_view.model().index(0,0), QItemSelectionModel.ClearAndSelect)

    def _refresh_list(self):
        mainlog.debug("_refresh_list")
        self.current_item = None
        objs = self.objects_list()

        self.list_model.buildModelFromObjects(objs)
        self.list_model_filtered.setIndexData([self.index_builder(o) for o in objs])

        return len(objs)

    def _select_on_object_id(self,o_id,update_view_selection=True):
        objects = self.list_model.objects

        ndx = -1
        for i in range(self.list_model.rowCount()):
            obj = self.list_model.object_at(i)
            if getattr(obj,self.key_field) == o_id:
                ndx = i
                break

        mainlog.debug("_select_on_object_id: ndx={}".format(ndx))

        if update_view_selection:
            self.list_view.clearSelection()

            # Look where the selected object is in the *filtered* view

            filtered_ndx = self.list_model_filtered.mapFromSource( self.list_model.index(ndx,0))

            mainlog.debug("Filtered ndx isValid = {}".format(filtered_ndx.isValid()))

            if not filtered_ndx.isValid():
                # The object is not visible in the filtered list.
                # So we clear the filter to show everything

                # self.line_in.setText("") # This triggers a refresh of the list
                filtered_ndx = self.list_model_filtered.mapFromSource( self.list_model.index(ndx,0))

            mainlog.debug("Filtered ndx isValid = {}".format(filtered_ndx.isValid()))

            self.list_view.setCurrentIndex(filtered_ndx)
            self.list_view.selectionModel().setCurrentIndex(filtered_ndx, QItemSelectionModel.NoUpdate)
            self.list_view.setFocus()



    def _populate_form(self,obj):
        mainlog.debug("_populate_form with {}".format(obj))
        self.current_item = obj

        if obj:
            for p in self.form_prototype:
                mainlog.debug("   {} -> {}".format(p.field, getattr(obj,p.field)))
                p.set_edit_widget_data(getattr(obj,p.field))
        else:
            # Clear the form
            for p in self.form_prototype:
                p.set_edit_widget_data( p.default_value())


    def _load_forms_data(self):
        d = dict()

        for p in self.form_prototype:
            # mainlog.debug("_load_forms_data : {} = {}".format(p.field, p.edit_widget_data()))
            d[p.field] = p.edit_widget_data()

        if self.current_item:
            d[self.key_field] = getattr(self.current_item, self.key_field)
        else:
            mainlog.debug("_load_forms_data : no current item")
        return d



    def _data_changed(self, form_data, obj):
        """ True if the data in the hash form_data are different
        than what is in sqla_obj
        """

        def cmp_instrumented_list(a,b):
            # mainlog.debug("cmp_instrumented_list")

            if len(a) != len(b):
                return False

            # mainlog.debug("cmp_instrumented_list lengths are equal")

            for i in range(len(a)):
                if a[i] != b[i]:
                    # mainlog.debug(u"cmp_instrumented_list {} != {}".format(a[i],b[i]))
                    return False

            return True

        def pixmap_hash(pixmap):
            """ Compute a hash of the *content* of a picture.
            I've tried to use QPixmap.cacheKey() but somehow
            it's not dependent on content only (thus two
            Pixmap containing the same picture have different
            cacheKey() (and the documentation is not quite
            clear.
            """

            import hashlib
            # mainlog.debug("Hashing pixmap {} {}".format(id(pixmap),type(pixmap)))
            m = hashlib.md5()
            m.update(pixmap.toImage().bits())
            return m.digest()

        if obj:
            # Form data compared to actual object content
            for p in self.form_prototype:
                if not p.is_editable:
                    continue

                attr = getattr(obj,p.field)
                new_attr = form_data[p.field]

                # Be cool with spaces. Note that we can have surplus
                # spaces from database as well as from the form...

                if type(attr) == str:
                    attr = attr.strip() or None
                if type(new_attr) == str:
                    new_attr = new_attr.strip() or None

                # mainlog.debug(u"MetaFormDialog : field:{} : obj:{} - form:{}".format(p.field, attr, new_attr))

                if ( (type(attr) == QPixmap and pixmap_hash(attr) != pixmap_hash(new_attr)) or\
                     (type(attr) == InstrumentedList and not cmp_instrumented_list(attr,new_attr)) or\
                     (type(attr) != QPixmap and type(attr) != InstrumentedList and attr != new_attr)):
                    mainlog.debug(u"_data_changed2 : data are different on {} : '{}' != '{}'".format(p.field, attr, new_attr))
                    return True
            return False
        else:
            # Form data compared to empty object
            for p in self.form_prototype:
                new_attr = form_data[p.field]
                mainlog.debug("MetaFormDialog : empty ! {} : new_attr {}, default = {}".format(p.field, new_attr, p.default_value()))
                # We compare to a non filled object
                if new_attr and str(new_attr) != u"":
                    # That seems like a change, but we'll consider it
                    # only if we differ from the default value
                    # This helps in case we compare to fields which can
                    # not be None when empty (for example a combo box with
                    # a few values)
                    if new_attr != p.default_value():
                        return True
            return False


    def _validate_and_save(self, form_data):
        """ Returns saved object's id or False is save could not be
        completed (either because there are errors in the validation
        or because there are other technical errors).
        """

        errors = dict()
        for p in self.form_prototype:
            data = form_data[p.field]

            if p.is_editable:
                v = p.validate(data)
                if v != True:
                    errors[p.title] = v

        if len(errors) > 0:
            info_text = ""
            for field,error in errors.items():
                info_text += u"<li>{}</li>".format(error)

            showErrorBox(_("Some of the data you encoded is not right"),u"<ul>{}</ul>".format(info_text))
            return False


        # check = self.check_before_save(self.current_item)

        check = True

        if check == True:
            try:
                return self.save_object(form_data)
            except Exception as e:
                showErrorBox(_("There was an error while saving"),str(e),e)
                return False
        else:
            showErrorBox(_("There was an error while saving"),check)
            return False

    SAVE_DECLINED_BY_USER = -1
    SAVE_FAILED_BECAUSE_OF_ERRORS = -2

    def _save_if_necessary(self):
        """ Returns :
        - primary key if something was saved
        - True if the user choose to not save (for wahtever reason) or a save
          was not needed (no data changed)
        - False if there were errors during the save
        """

        form_data = self._load_forms_data()
        mainlog.debug("_save_if_necessary: form_data = {}".format(form_data))
        if self._data_changed(form_data, self.current_item):
            ynb = yesNoBox(_("Data were changed"),
                           _("You have changed some of the data in this. Do you want to save before proceeding ?"))

            if ynb == QMessageBox.Yes:
                saved_obj_id = self._validate_and_save(form_data)
                mainlog.debug("_save_if_necessary: saved object id  {}".format(saved_obj_id))
                if saved_obj_id != False:
                    mainlog.debug("_save_if_necessary: returning  {}".format(saved_obj_id))
                    return saved_obj_id
                else:
                    # There were errors while trying to save
                    return False

        return True


    @Slot(QModelIndex,QModelIndex)
    def selected_item_changed(self, current, previous):

        mainlog.debug("selected_item_changed old: {} new: {} in_save:{}".format(previous.row(),current.row(), self.in_save))

        # The test below avoids some recursion. It's a bit more clever
        # than it looks. What happens is this. The user modifies
        # some data then ask to change the edited object (in the left list)
        # Doing so it triggers this method. The program then save (if
        # necessary). But that save may trigger a reorganisation of the
        # list. So what the user has selected may be at a different
        # index than the "current" one we received as a parameter
        # of this method. To account for that we actually reselect
        # the item in the table. And this triggers the recursion we avoid
        # here. FIXME there is a recursion but the way we avoid
        # it is not 100% satisfactory, we should use a "semaphore"
        # for that.


        if current.isValid() and current.row() >= 0 and \
           current.row() != previous.row():

            ndx = self.list_model_filtered.mapToSource(self.list_model_filtered.index(current.row(),0))
            target = self.list_model.object_at(ndx.row())

            mainlog.debug("selected_item_changed: trying to save something")
            if (not self.in_save) and type(self._save_if_necessary()) is int:
                # Something was actually saved
                mainlog.debug("selected_item_changed : something was saved starting list refresh")
                self.in_save = True
                self._refresh_list()
                self._select_on_object_id(getattr(target,self.key_field))
                self.in_save = False
                # mainlog.debug("selected_item_changed : done list refresh")
            self._populate_form(target)



    # FIXME Qt Bug ??? Mismatch between the parameters of the signal in the doc
    # and what I really get (no param...)
    @Slot(bool)
    def create_action(self):
        self.list_view.clearSelection()
        self._populate_form(None)
        self.form_prototype[0].edit_widget(None).setFocus(Qt.OtherFocusReason)

    @Slot(bool)
    def save_action(self):
        # mainlog.debug("Current row is {}".format(self.list_view.currentIndex().row()))

        self.in_save = True
        form_data = self._load_forms_data()
        obj_id = self._validate_and_save(form_data)

        # Following a save, the position of the object in the
        # list might have changed. So we need to reload the
        # list to account for that and we also need to reselect
        # the object

        if obj_id != False:
            # mainlog.debug("Save action : refreshing")
            self._refresh_list()
            # mainlog.debug("Save action : selecting")
            self._select_on_object_id(obj_id)

        self.in_save = False


    @Slot(bool)
    def delete_action(self):
        if self.current_item:
            o_id = getattr( self.current_item, self.key_field)

            if o_id >= 0: # For some reason I have o_id = 0 somewhere...

                # mainlog.debug("About to delete {}".format(o_id))

                try:
                    if self.delete_object(o_id):
                        self.current_item = None # Do this only if delete was successful !
                        self.in_save = True
                        self._refresh_list()

                        # The current filter might lead to a 0-length list
                        # or we might delete the only item of the list
                        # In that case, we clear the form.

                        if self.list_view.model().rowCount() > 0:
                            self.list_view.selectRow(0)
                        else:
                            self._populate_form(None)

                        self.in_save = False

                except Exception as e:
                    showErrorBox(_("There was an error while deleting"),str(e),e)
                    return

            else:
                mainlog.error("The current object has no id => I can't delete it")
        else:
            showWarningBox(_("You have selected nothing for delete."),None)
            return


    def done(self,x):
        current_ndx = self.list_view.currentIndex().row()
        if self._save_if_necessary():
            super(MetaFormDialog,self).done(x)
        # here be dragons

    def check_before_save(self,obj):
        return True


    def save_object(self,form_data):
        """ Save object hook
        """

        c = recursive_defrost_into(form_data, self.mapped_klass)
        session().commit()
        return getattr(c, self.key_field)

    def delete_object(self,o_id):
        generic_delete(self.mapped_klass, o_id)
        return True

    def objects_list(self):
        """ Reload the objects from the database.
        :return: a list of DTO.
        """
        return generic_load_all_frozen(self.mapped_klass, self.sort_criterion)


if __name__ == "__main__":

    app = QApplication(sys.argv)
    # widget = EditCustomerDialog(None)
    # widget = EditEmployeeDialog(None,dao)
    # widget = EditUserDialog(None,dao)
    widget = EditOperationDefinitionsDialog(None)
    widget.show()

    app.exec_()
