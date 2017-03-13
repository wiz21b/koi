from PySide.QtCore import Signal,Slot,QObject
from PySide.QtGui import QLineEdit,QComboBox,QValidator

from koi.Configurator import mainlog
from koi.QuickComboModel import QuickComboModel
from koi.configuration.business_functions import business_computations_service
from koi.gui.ComboDelegate import TimestampValidator,DurationValidator
from koi.gui.ProxyModel import OrderPartIdentifierValidator
from koi.translators import time_to_timestamp,duration_to_hm


class StandardEditInstrumentation(object):

    # We use an instrumentation paradigm rather than inheritance
    # This is done so to allow maximum flexibility on the
    # usage of the Qt components. For example, if one of our editor TimeEditor
    # was inherited from QLineEdit, it'd be difficult to to use
    # it in Qt Quick because Qt Quick doesn't know about TimeEditor.
    # The price to pay is that we need a little more code
    # when not using Qt Quick (one line to create the editor, and a second
    # one to add the associated Qt widget to, say, a QLayout).

    def __init__(self, field_name, user_name, nullable, widget):
        assert widget is not None
        assert nullable in (True,False)

        self._widget = widget
        self._field_name = field_name
        self._user_name = user_name
        self._nullable = nullable
        self._original_value = None

    @property
    def field_name(self):
        return self._field_name

    @property
    def user_name(self):
        """ The user name is used to denote this instance of the editor when
        communicating with a user. Most commonly in error messages.
        """

        return self._user_name

    @property
    def nullable(self):
        return self._nullable

    @property
    def widget(self):
        return self._widget


    @property
    def value(self):
        """ Current value of the widget. If that value is
        not valid according to check(), then we return
        None (we could have raised an exception instead
        but in some places, like tables, we sometimes
        need """

        raise Exception("StandardEditInstrumentation.value() method not implemented")

    # @value.setter FIXME For some reason, this disrputs things a lot
    def set_value(self,value):
        self._original_value = value


    def check(self):
        """ True if current value is OK. A string describing the error else.
        """
        raise Exception("Not implemented")


    def mark_current_as_original(self):
        self._original_value = self.value

    def changed(self):
        return self.value != self._original_value




class TimeStampEdit(StandardEditInstrumentation):
    def __init__(self, field_name, user_name,nullable=False, widget=None, parent=None):
        if widget is None:
            widget = QLineEdit(parent)

        super(TimeStampEdit,self).__init__(field_name, user_name, nullable, widget)

        self.timestamp_validator = TimestampValidator()
        self.timestamp_validator.set_nullable(nullable)

        self.widget.setValidator(self.timestamp_validator)
        self.base_date = None

    def set_base_date(self,base_date):
        self.timestamp_validator.set_base_date(base_date)
        self.base_date = base_date

    def set_value(self,ts):
        super(TimeStampEdit,self).set_value(ts)

        if ts:
            self.widget.setText(time_to_timestamp(ts,self.base_date))
        else:
            self.widget.setText(None)

    @property
    def value(self):
        s = self.widget.text()
        if self.timestamp_validator.full_check(s) == True:
            if s is None or s.strip() == '':
                return None
            else:
                return self.timestamp_validator.parser.parse(s)
        else:
            raise Exception("Trying to read a value that doesn't pass the validation")


    def check(self):
        # Just a shortcut to avoid exposing the validator
        # and the way we use it
        return self.timestamp_validator.full_check(self.widget.text()) == True




class DurationEdit(QLineEdit):
    def __init__(self,parent,nullable=False):
        super(DurationEdit,self).__init__(parent)
        self.validator = DurationValidator()
        self.setValidator(self.validator)

    def setValue(self,v):
        self.setText(duration_to_hm(v))

    def value(self):
        return self.validator.parser.parse(self.text())

    def check(self):

        errors = []

        if self.validator.validate(self.text()) == QValidator.Acceptable:
            v = self.validator.parser.parse(self.text())
        else:
            errors.append(_("Invalid syntax"))

        return errors == [] or errors



class TaskActionReportTypeComboBox(StandardEditInstrumentation):
    def __init__(self,field_name, user_name, nullable=False, widget=None):
        if widget is None:
            widget = QComboBox()
        super(TaskActionReportTypeComboBox,self).__init__(field_name, user_name, nullable, widget)

    def set_model(self,tars):
        self.model = QuickComboModel(None)
        self.model.buildModelFromArray([c.description for c in tars],tars) # user strings, references
        self.widget.setModel(self.model)

    @property
    def value(self):
        return self.widget.itemData(self.widget.currentIndex())

    def check(self):
        return True

    def get_current_type(self):
        # FIXME Obsolete, use value() instead
        return self.itemData(self.currentIndex())



class OrderPartIdentifierEdit(StandardEditInstrumentation):
    def __init__(self, field_name, user_name,nullable=False, widget=None, parent=None):
        if widget is None:
            widget = QLineEdit(parent)

        super(OrderPartIdentifierEdit,self).__init__(field_name, user_name, nullable, widget)

        self.validator = OrderPartIdentifierValidator()
        self.widget.setValidator(self.validator)

    # def set_value(self,ts):
    #     super(OrderPartIdentifierEdit,self).set_value(ts)

    #     if ts:
    #         self.widget.setText(ts)
    #     else:
    #         self.widget.setText(None)

    @property
    def value(self):
        if self.check() == True:
            s = self.widget.text().strip()
            if s is None or s == '':
                return None
            else:
                return s.upper()
        else:
            raise Exception("Trying to read an invalid value")


    def set_value(self,value):
        mainlog.debug(u"OrderPartIdentifierEdit.set_value : {}".format(value))
        super(OrderPartIdentifierEdit, self).set_value(value)
        self.widget.setText(value)


    def check(self):
        t = self.widget.text()

        mainlog.debug(u"OrderPartIdentifierEdit : check() : {}".format(t))

        if not t or not t.strip():
            return True
        else:
            return self.validator.validate(t,0) == QValidator.Acceptable


class OrderStateEdit(QObject,StandardEditInstrumentation): # StandardEditInstrumentation

    signal_state_changed = Signal()

    def __init__(self, field_name, user_name,nullable=False, widget=None, parent=None):
        if widget is None:
            widget = QComboBox(parent)

        widget.activated.connect(self.state_changed_slot)
        self.last_index = 0

        StandardEditInstrumentation.__init__(self,field_name, user_name, nullable, widget)
        QObject.__init__(self)

    @Slot(int)
    def state_changed_slot(self,ndx):
        mainlog.debug("State changed {} - {}".format(ndx, self.widget.currentIndex()))
        if self.last_index != self.widget.currentIndex():
            self.last_index = self.widget.currentIndex()
            self.signal_state_changed.emit()

    def set_model(self,original_state):

        # This first state is the current one so that it
        # is properly displayed

        states = []
        states.append(original_state)
        for s in business_computations_service.order_possible_next_states(original_state):
            if s != original_state:
                states.append(s)

        self.model = QuickComboModel(None)
        self.model.buildModelFromArray( [c.description for c in states],states) # user strings, references
        self.widget.setModel(self.model)

    @property
    def value(self):
        return self.widget.itemData(self.widget.currentIndex())

    def set_state(self, state, next_states):
        self.model = QuickComboModel(None)

        all_states = [state]

        if next_states:
            # Convert from tuple to array
            all_states += [s for s in next_states]

        self.model.buildModelFromArray( [c.description for c in all_states], all_states) # user strings, references
        self.widget.setModel(self.model)

    def set_value(self,value):
        """ Sets the combo to the given state. The other possibilities
        in the combo are the states reachable from the given one.
        """

        super(OrderStateEdit,self).set_value(value)
        self.set_model(value)
        self.widget.setCurrentIndex(0)
        self.last_index = 0

    def check(self):
        return True

    def get_current_type(self):
        # FIXME Obsolete, use value() instead
        return self.itemData(self.currentIndex())



class ConstrainedMachineEdit(QObject, StandardEditInstrumentation):
    def __init__(self, field_name, user_name,nullable=False, widget=None, parent=None):
        if widget is None:
            widget = QComboBox(parent)

        StandardEditInstrumentation.__init__(self,field_name, user_name, nullable, widget)
        QObject.__init__(self)

        self.model = QuickComboModel(None)

    def set_model(self,machines):
        refs = [None] + machines
        label = [None] + [m.fullname for m in machines]
        self.model.buildModelFromArray(label, refs) # user strings, references
        self.widget.setModel(self.model)

    @property
    def value(self):
        # Somehow, using itemData transforms some KeyedTupel reference into
        # simple list... FIXME !

        row = self.widget.currentIndex() # an int
        r = self.model.references[row]

        mainlog.debug("ConstrainedMachineEdit.value:{}".format(type(r)))
        return r

    def check(self):
        return True

    def set_value(self,value):
        super(ConstrainedMachineEdit, self).set_value(value)
