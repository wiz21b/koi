import sys
import PySide.QtWebKit
from PySide.QtGui import QDialog, QHBoxLayout, QApplication, QVBoxLayout, QLineEdit, QLabel,QListWidget, QPushButton


def vbox( widgets):
    layout = QVBoxLayout()
    for w in widgets:
        if type(w) in (QHBoxLayout, QVBoxLayout):
            layout.addLayout(w)
        else:
            layout.addWidget(w)

    return layout


def hbox( widgets):
    layout = QHBoxLayout()
    for w in widgets:
        if type(w) in (QHBoxLayout, QVBoxLayout):
            layout.addLayout(w)
        else:
            layout.addWidget(w)
    return layout


def field( name, _type, label):
    layout = QHBoxLayout()
    layout.addWidget( QLabel(label))
    if _type == str:
        layout.addWidget( QLineEdit())
    return layout

from collections import OrderedDict

class OneLineRenderedWidget(QLineEdit):
    def __init__(self):
        QLineEdit.__init__(self)

    def set_value(self, v):
        self.setText( str(v))

    def value(self):
        return self.text()


class ListRenderedWidget(QListWidget):
    def __init__(self):
        QListWidget.__init__(self)

    def set_value(self, v):
        self.setText( str(v))

    def value(self):
        return self.text()

class ButtonRenderedWidget(QPushButton):
    def __init__(self, label):
        QPushButton.__init__(self)
        self.setText(label)

    def set_value(self, v):
        pass

class LabelRenderedWidget(QLabel):
    def __init__(self, text):
        QLabel.__init__(self)
        self.setText( text)

    def set_value(self, v):
        pass

class DataWidget:
    """ A widget that is meant to display data.
    Such a widget is a leaf in the GUI tree. It means its
    data is fully handled by itself.
    """

    def __init__(self, name):
        self._name = name

    @property
    def name(self):
        return self._name

    def render(self):
        """
        :return: An object that is ready for data display and exchange.
        The data display can be HTML or Qt.
        """
        raise "Not defined"


class ButtonWidget(DataWidget):
    def __init__(self, label, action ):
        super().__init__(None)
        self._action = action
        self._label = label

    def render(self):
        return ButtonRenderedWidget(self._label)

class LabelWidget(DataWidget):
    def __init__(self, label):
        self._label = label
        super().__init__(None)

    def render(self):
        return LabelRenderedWidget(self._label)

class Widget(DataWidget):
    def __init__(self, name, _type):
        super().__init__(name)
        self._type = type

    def render(self):
        return RenderedWidget()

class OneLineWidget(DataWidget):
    def __init__(self,name, type_def):
        super().__init__(name)
        self._type_def = type_def

    def render(self):
        return OneLineRenderedWidget()

class ListWidget(DataWidget):
    def __init__(self, name, list_of, load_function):
        super().__init__(name)
        self._list_of = list_of
        self._load_function = load_function

    def render(self):
        return ListRenderedWidget()


class Layout:
    def __init__(self, components):
        self._components = components

    def widget_by_name(self, name):
        for c in self._components:
            if type(c) == Layout:
                return c.widget_by_name(name)
            elif c.name == name:
                return c

    def render(self, field_map = dict()):
        layout = QHBoxLayout()
        for c in self._components:

            if isinstance(c, Layout):
                w = c.render(field_map)
            else:
                w = c.render()
                if c.name:
                    field_map[c.name] = w

            if type(w) in (QHBoxLayout, QVBoxLayout):
                layout.addLayout(w)
            else:
                layout.addWidget(w)

        return layout

class Form(Layout):
    def __init__(self, form_of, layout):
        self._form_of = form_of
        Layout.__init__(layout)


class Render:
    """ Render object contains one instance of the declared UI.
    It can be reused.
    """

    def __init__(self, form):
        self._field_map = dict()
        self._render = form.render(self._field_map)

    def render(self):
        return self._render

    def set_all_values(self, data):
        for key in self._field_map.keys():
            self._field_map[key].set_value( getattr(data,key))

    def read_all_values(self, data):
        for key in self._field_map.keys():
            setattr( data, key, self._field_map[key].value())

class EmployeeModel:
    name = str
    is_active = str

class Employee:
    def __init__(self,name):
        self.name = name

def employee_load_function():
    return [ Employee("John"),Employee("Donald"),Employee("Edgar") ]

app = QApplication(sys.argv)

"""
How to validate
When to validate

"""

list_form = Layout( [ ListWidget(name='list',
                                   list_of=Employee, # This means : there must be an employee PK on each line.
                                   load_function=employee_load_function()) ] )

""" A form is a group of fields that will be used to set
values in an object of a given type.

Fileds can be comibined in layout.
Forms can be combined to address several types of objects (eg a dynamic list of forms)
"""

form_employee = Layout( [ LabelWidget("Fullname"), OneLineWidget('fullname', EmployeeModel.name),
                          LabelWidget("Active ?"), OneLineWidget('is_active', EmployeeModel.is_active) ] )

class Action:
    def __init__(self, name):
        self._name = name

save_action = Action("Save")
new_action = Action("New")

form = Layout( [ list_form,
                 form_employee,
                 ButtonWidget("Save", save_action),
                 ButtonWidget("New", new_action) ] )

def event_loop(action):
    if action == list_form.item_selected:
        form_rendered.set_all_values( list_form.current_selected )

    elif action == save_action:
        employee_service.save( form_rendered.current_object )
        list_widget.reload()

    elif action == new_action:
        form_employee.clear_all_fields()
        list_widget.disable()






class Data:
    def __init__(self, name, price):
        self.name = name
        self.price = price
        self.fullname = "ze full name"
        self.is_active = "lklk"

    def __str__(self):
        return "{} {}".format(self.name, self.price)

# form_rendered._field_map['name'].set_value("king")
# form_rendered._field_map['price'].set_value("1337")

data = Data( name="King Kong", price=123)

d = { 'list' : [ 'alpha', 'beta', 'gamma'],
      'group' : data }

form_rendered = Render(form)
form_rendered.set_all_values(data)
form_rendered.read_all_values(data)
print(data)


d = QDialog()
view = PySide.QtWebKit.QWebView(d)
view.setZoomFactor(1.5)
# view.setHtml("Hello world <a href='eulu.html'>Link</a>")
# view.setUrl('file:///Users/stc/Dropbox/index.html')
view.setUrl('file:///PORT-STC/PRIVATE/SlickGrid-2.2.6/examples/example14-highlighting.html')
top_layout = QHBoxLayout()
top_layout.addWidget(view)
top_layout.addLayout(form_rendered.render())
d.setLayout(top_layout)
d.show()


d.exec_()

