if __name__ == "__main__":
    from PySide.QtGui import QApplication

    from koi.base_logging import init_logging
    from koi.Configurator import init_i18n,load_configuration

    init_logging()
    init_i18n()
    load_configuration()

import sys

from PySide.QtGui import QDialog, QDialogButtonBox,QFormLayout,QVBoxLayout,QLabel

from koi.db_mapping import copy_fields_to_object
from koi.dao import dao
from koi.Configurator import mainlog
from koi.gui.dialog_utils import TitleWidget,showErrorBox,showWarningBox
from koi.gui.ProxyModel import TimestampPrototype, SpecialActivityTypePrototype


class DialogManager(object):
    def __init__(self,prototype):
        self.form_prototype = prototype

    def quick_form(self):
        form_layout = QFormLayout()

        self.form_prototype = [ TimestampPrototype('start_time',_('Start time'),nullable=False),
                                TimestampPrototype('end_time',_('End time'),nullable=False) ]

        for p in self.form_prototype:
            form_layout.addRow( p.title, p.edit_widget(self))

        return form_layout

    def _load_forms_data(self):
        cache = dict()
        for p in self.form_prototype:
            cache[p.field] = p.edit_widget_data()
        return cache

    def setup_form(self,obj = None):
        if obj:
            for p in self.form_prototype:
                p.set_edit_widget_data(getattr(obj,p.field))
        else:
            for p in self.form_prototype:
                p.set_edit_widget_data(None)

    def validate(self,form_data):

        errors = dict()
        for p in self.form_prototype:
            data = form_data[p.field]

            v = p.validate(data)
            if v != True:
                errors[p.title] = v

        if len(errors) > 0:
            info_text = ""
            for field,error in errors.items():
                info_text += u"<li>{}</li>".format(error)

            showErrorBox(_("Some of the data you encoded is not right"),u"<ul>{}</ul>".format(info_text))
            return False
        else:
            return True





class HolidaysDialog(QDialog):

    def __init__(self,parent):
        super(HolidaysDialog,self).__init__(parent)

        title = _("Edit holidays")

        self.setWindowTitle(title)
        self.title_widget = TitleWidget(title,self)

        form_layout = QFormLayout()

        self.form_prototype = [ TimestampPrototype('start_time',_('Start time'),nullable=False),
                                TimestampPrototype('end_time',_('End time'),nullable=False),
                                SpecialActivityTypePrototype('activity_type',_('Type'),nullable=False)]

        for p in self.form_prototype:
            form_layout.addRow( p.title, p.edit_widget(self))


        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.Ok)
        self.buttons.addButton( QDialogButtonBox.Cancel)

        self.info_label = QLabel()

        top_layout = QVBoxLayout()
        top_layout.addWidget(self.title_widget)
        top_layout.addWidget(self.info_label)
        top_layout.addLayout(form_layout)
        top_layout.addWidget(self.buttons)

        self.setLayout(top_layout)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        self.dialog_manager = DialogManager(self.form_prototype)
        self.special_activity = None

    def setup(self,sa,employee_fullname):

        assert sa != None, "Must work on an object"

        self.info_label.setText(_("Editing holidays for {}").format(employee_fullname))
        self.special_activity = sa
        self.dialog_manager.setup_form(sa)


    def accept(self):
        sa = self._validate_and_save()
        mainlog.debug("Accept {}".format(sa))
        if sa != False:
            super(HolidaysDialog,self).accept()

    def _validate_specifics(self,data):

        if data['start_time'] >= data['end_time']:
            showErrorBox(_("The start time must be before than the end time"))
            return False
        else:
            return True

    def _validate_and_save(self):

        try:
            data = self.dialog_manager._load_forms_data()

            if self.dialog_manager.validate(data) != True or self._validate_specifics(data) != True:
                showWarningBox(_("Validation failed"))
                return False

            copy_fields_to_object(data, self.special_activity)
            dao.special_activity_dao.save(self.special_activity)
            return self.special_activity
        except Exception as e:
            showErrorBox(_("There was an error while saving"),str(e),e)
            return False




if __name__ == "__main__":

    from koi.db_mapping import SpecialActivity
    from koi.junkyard.services import services


    app = QApplication(sys.argv)
    # widget = EditCustomerDialog(None,dao)
    widget = HolidaysDialog(None)
    sa = SpecialActivity()
    sa.employee = services.employees.find_by_id(1)
    sa.reporter = services.employees.find_by_id(2)

    widget.setup(sa)
    # widget = EditUserDialog(None,dao)
    widget.exec_()
