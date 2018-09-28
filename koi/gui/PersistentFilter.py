#noinspection PyUnresolvedReferences
import sys

from koi.base_logging import mainlog
from PySide.QtCore import Qt,Signal,Slot
from PySide.QtGui import QWidget,QPushButton, QAction, QHBoxLayout, QLabel, QComboBox, QCheckBox, QDialog, QVBoxLayout, QDialogButtonBox

#noinspection PyUnresolvedReferences
from PySide.QtGui import QLineEdit

from koi.gui.dialog_utils import showErrorBox, showWarningBox
from koi.dao import dao
from koi.session.UserSession import user_session
from koi.gui.QueryLineEdit import QueryLineEdit


class FiltersCombo(QComboBox):
    filter_query_selected = Signal(object)

    def __init__(self, parent, family):
        super(FiltersCombo,self).__init__(parent)

        self._family = family
        self._filters = []
        self.activated.connect( self.emit_filter_query_selected)

    def current_filter(self):
        if 0 <= self.currentIndex() < len(self._filters):
            return self._filters[self.currentIndex()]
        else:
            return None

    def preselect(self, fq_id: int, emit_selection_signal: bool = True):
        if not self._filters:
            self.reload()

        for i in range( len( self._filters)):
            if self._filters[i].filter_query_id == fq_id:
                self.setCurrentIndex(i)
                if emit_selection_signal:
                    self.filter_query_selected.emit(self._filters[i])
                return

        # If the filter has been removed, then the configuration file
        # is not correct anymore. I could warn the user, but the problem
        # is that if I do it from here, then the warning might be
        # out of context (gui wise). So I prefer to fail silently.

        mainlog.warning("Unable to preselect filter id {}".format(fq_id))
        if self._filters:
            self.setCurrentIndex(0)
            if emit_selection_signal:
                self.filter_query_selected.emit(self._filters[0])


    @Slot()
    def reload(self):
        global dao
        global user_session

        mainlog.debug("Reloading filters for family {}".format(self._family))
        self._filters = dao.filters_dao.usable_filters(user_session.user_id, self._family)

        self.clear()
        for fq in self._filters:
            mainlog.debug("Filter : {} {}".format(fq.name, fq.filter_query_id))
            self.addItem( fq.name, fq.filter_query_id)


    @Slot(int)
    def emit_filter_query_selected(self, ndx):
        self.filter_query_selected.emit( self._filters[ndx])



class GiveNewNameDialog(QDialog):
    def __init__(self,parent):
        super(GiveNewNameDialog,self).__init__()

        self.setWindowTitle(_("Choose filter's name"))
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(_("Please give a name to the filter")))

        self.line_edit = QLineEdit()

        layout.addWidget(self.line_edit)

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.StandardButton.Cancel)
        self.buttons.addButton( QDialogButtonBox.Ok)
        layout.addWidget(self.buttons)

        self.setLayout(layout)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    @Slot()
    def accept(self):
        if self.line_edit.text().strip():
            return super(GiveNewNameDialog,self).accept()

    @Slot()
    def reject(self):
        return super(GiveNewNameDialog,self).reject()



class PersistentFilter(QWidget):

    CONFIG_SECTION = "Filters"

    apply_filter = Signal(str)
    """ Will be emitted when the user signals he wants to apply the
    current filter (the filter is passed as a unicode string to the signal).
    The filter is read from the filter_edit_widget passed in the constructor.
    """

    @Slot()
    def _emit_apply_filter(self):
        self.apply_filter.emit( self.super_filter_entry.text())


    def current_filter(self):
        return self.super_filter_entry.text()

    def remember_current_selection( self, config):
        f = self.get_filters_combo().current_filter()
        config.set( self.CONFIG_SECTION, f.family, f.filter_query_id)
        config.save()

    def load_last_filter(self, config):
        """ Loads last save filter (save inf configuration). If
        no filter found in configuration then we shall take a default
        one (arbitrarily) """

        if config.is_set( self.CONFIG_SECTION, self._filter_family):
            filter_query_id = int(config.get( self.CONFIG_SECTION, self._filter_family))
            mainlog.debug("load_last_filter : there is a saved filter id={}".format(filter_query_id))
            self.get_filters_combo().preselect(filter_query_id)
        else:
            mainlog.debug("load_last_filter : no saved filter, defaulting to one")
            self.filter_name.preselect( None)

    @Slot()
    def _filters_selected_from_combo_box(self,fq):
        self._show_filter(fq)
        self._emit_apply_filter()

    def get_filters_combo(self):
        if not self.filter_name:
            self.filter_name = FiltersCombo(self, self._filter_family)
            self.filter_name.filter_query_selected.connect( self._filters_selected_from_combo_box)

        return self.filter_name

    def select_default_filter(self):
        self.filter_name.preselect(None, emit_selection_signal=True)


    def __init__(self, filter_family : str, suggestion_finder = None, parent=None):

        super(PersistentFilter,self).__init__(parent)

        self.filter_name = None
        self._filter_family = filter_family

        self.apply_filter_action = QAction(_("Filter"),self)
        self.apply_filter_action.triggered.connect( self._emit_apply_filter)

        self.save_filter_action = QAction(_("Save filter"),self)
        self.save_filter_action.triggered.connect( self.save_filter_action_slot)

        self.save_filter_as_action = QAction(_("Save filter as"),self)
        self.save_filter_as_action.triggered.connect( self.save_filter_as_action_slot)

        self.delete_filter_action = QAction(_("Delete filter"),self)
        self.delete_filter_action.triggered.connect( self.delete_filter_action_slot)

        def action_to_button(action):
            b = QPushButton(action.text())
            b.clicked.connect(action.trigger)
            return b

        hlayout_god_mode = QHBoxLayout()
        hlayout_god_mode.addWidget(QLabel(_("Filter :")))


        self.query_label = QLabel()
        hlayout_god_mode.addWidget(self.query_label)

        hlayout_god_mode.addWidget(QLabel(_("Query :")))

        if suggestion_finder:
            self.super_filter_entry = QueryLineEdit( suggestion_finder)
        else:
            self.super_filter_entry = QLineEdit()

        hlayout_god_mode.addWidget(self.super_filter_entry)

        # self.completion.setParent(self.super_filter_entry)
        # self.super_filter_entry.cursorPositionChanged.connect(self.cursorPositionChanged_slot)
        self.super_filter_entry.editingFinished.connect(self.completEditFinished_slot)
        self.super_filter_entry.returnPressed.connect(self._emit_apply_filter)

        self.share_filter = QCheckBox(_("Shared"))
        hlayout_god_mode.addWidget(self.share_filter)


        self.super_filter_button = action_to_button( self.apply_filter_action)
        hlayout_god_mode.addWidget(self.super_filter_button)

        self.save_filter_button = action_to_button(self.save_filter_action)
        hlayout_god_mode.addWidget(self.save_filter_button)

        hlayout_god_mode.addWidget(action_to_button(self.save_filter_as_action))

        self.delete_filter_button = action_to_button(self.delete_filter_action)
        hlayout_god_mode.addWidget(self.delete_filter_button)

        self.setLayout(hlayout_god_mode)
        # self._load_available_queries()



    def _populate_dto(self,dto):

        fq_query = self.super_filter_entry.text()
        if not fq_query or not fq_query.strip():
            showWarningBox(_("The filter's query can't be empty"),None,parent=self,object_name="empty_filter_query")
            return False

        dto.owner_id = user_session.user_id
        dto.shared = self.share_filter.checkState() == Qt.Checked
        dto.query = fq_query
        dto.family = self._filter_family
        return True

    @Slot()
    def _show_filter(self,fq):
        if fq:
            mainlog.debug("_show_filter : {}".format(fq.query))

            if fq.owner_id == user_session.user_id:
                self.query_label.setText("<b>{}</b>".format(fq.name))
            else:
                self.query_label.setText("<b>{}</b> ({})".format(fq.name, fq.owner.fullname))

            self.super_filter_entry.setText(fq.query)
            self.save_filter_button.setEnabled(fq.owner_id == user_session.user_id)
            self.delete_filter_button.setEnabled(fq.owner_id == user_session.user_id)

            if fq.shared:
                self.share_filter.setCheckState(Qt.Checked)
            else:
                self.share_filter.setCheckState(Qt.Unchecked)
        else:
            mainlog.debug("_show_filter : {}".format(None))

            self.super_filter_entry.setText("")
            self.share_filter.setCheckState(Qt.Unchecked)
            self.save_filter_button.setEnabled(True)
            self.delete_filter_button.setEnabled(True)

    # @Slot()
    # def filter_activated_slot(self,ndx):
    #
    #     fq_id = self.filter_name.itemData(self.filter_name.currentIndex())
    #
    #     if fq_id:
    #         try:
    #             fq = dao.filters_dao.find_by_id(fq_id)
    #             self._show_filter(fq)
    #             self._apply_filter()
    #         except Exception as e:
    #             showErrorBox(_("There was a problem while loading the filter. It may have been deleted by its owner"),None,e,object_name="missing_filter")
    #             # MAke sure the filter doesn't appear anymore
    #             self.filter_name.reload()
    #             self.filter_name.preselect(None)
    #             return
    #     else:
    #         self._show_filter(None)

    @Slot()
    def delete_filter_action_slot(self):
        try:
            fq_id = None
            if self.filter_name.currentIndex() >= 0:
                fq_id = self.filter_name.itemData(self.filter_name.currentIndex())

            if not fq_id:
                showWarningBox(_("The filter you want to delete was never saved"),None,parent=self,object_name="no_need_to_delete_filter")
                return

            fq = dao.filters_dao.find_by_id(fq_id)
            if fq.owner_id != user_session.user_id:
                showWarningBox(_("You can't delete the filter because it doesn't belong to you."),None,parent=self,object_name="not_my_filter")
                return

            dao.filters_dao.delete_by_id(fq_id,user_session.user_id)

            self.filter_name.reload()
            self.filter_name.preselect(None)

        except Exception as e:
            mainlog.error("Can't delete fq_id = {}".format(fq_id))
            showErrorBox(_("There was a problem while deleting the filter."),None,e,object_name="delete_filter_fatal")
            self.filter_name.reload()
            self.filter_name.preselect(None)


    @Slot()
    def save_filter_as_action_slot(self):
        d = GiveNewNameDialog(self)
        d.exec_()

        if d.result() == QDialog.Accepted:
            new_name = d.line_edit.text()
            if not dao.filters_dao.is_name_used(new_name, user_session.user_id, self._filter_family):
                fq = dao.filters_dao.get_dto(None)
                if self._populate_dto(fq):
                    fq.name = new_name
                    fq_id = dao.filters_dao.save(fq)
                    self.filter_name.reload()
                    self._show_filter(fq)
                    self.filter_name.preselect(fq_id, emit_selection_signal=False)
            else:
                showErrorBox(_("There is already a filter with that name. You must delete it first if you want to use that name."),None,None,object_name="filter_with_same_name")

    @Slot()
    def save_filter_action_slot(self):

        ndx = self.filter_name.currentIndex()
        fq_id = None

        if ndx >= 0:
            fq_id = self.filter_name.itemData(ndx)
            fq_dto = dao.filters_dao.get_dto(fq_id)

            if fq_dto.owner_id == user_session.user_id:
                if self._populate_dto(fq_dto):
                    fq_dto.name = self.filter_name.itemText(ndx)
                    fq_id = dao.filters_dao.save(fq_dto)
            else:
                if yesNoBox(_("This is not your filter !"), _("OK to save it under another name ?")) == QMessageBox.Yes:
                    self.save_filter_as_action_slot()
        else:
            mainlog.debug("save_filter_action_slot ndx={}".format(ndx))
            self.save_filter_as_action_slot()

    @Slot()
    def completEditFinished_slot(self):
        # self.super_filter_entry.completion.hide()
        self.nofocuslost = False
