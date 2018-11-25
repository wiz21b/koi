__author__ = 'stc'

from PySide.QtGui import QAction,QMenu
from PySide.QtCore import Qt
from koi.session.UserSession import user_session



class Action:
    def __init__(self, code, label, funktion, roles):
        self.code = code
        self.label = label
        self._function = funktion
        self._roles = roles

    def is_enabled(self):
        if self._roles is not None:
            return user_session.has_any_roles(self._roles)
        else:
            return True


    def as_QAction(self, parent):
        self._qaction = QAction(self.label, parent)
        self._qaction.triggered.connect( self._function)
        # self._qaction.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_PageUp))
        self._qaction.setShortcutContext(Qt.WidgetWithChildrenShortcut)


class Menu:
    def __init__(self, name):
        self.code = name

    def __repr__(self):
        return "Menu {}".format(self.code)

    def items(self):
        def _items_helper(root_name, items):
            r = dict()
            r[root_name] = self
            for item in items:
                if isinstance(item, Action):
                    r['.'.join([root_name, item.code])] = item
                elif isinstance(item, Menu):
                    r.update( _items_helper( '.'.join([root_name, item.code]), item._items))
            return r


        return _items_helper(self.code, self._items)

    def add_items(self, items):
        self._items = items

    def as_NavBar(self):
        pass

    def as_QMenu(self):
        menu = QMenu()
        for item in self._items:

            if isinstance(item, Action):
                a = item.as_QAction()
                a.setEnabled(item.is_enabled())
                menu.addAction(item)

            elif isinstance(item, Menu):
                menu.addMenu( item.as_QMenu())

        return menu


def f():
    pass

a1 = Action("alpha","The quick",f,None)
m1 = Menu("parts")
m1.add_items([a1])

a2 = Action("Beta","The quick",f,None)
m2 = Menu("main two")
m2.add_items([a2,m1])

menu_registry = dict()
menu_registry.update(m2.items())

a3 = Action("Gamma","The quick",f,None)
m3 = Menu("main three")
m3.add_items([a3])

menu_registry.update(m3.items())

# for k,v in menu_registry.items():
#     print(str(k) + " " + str(v))
