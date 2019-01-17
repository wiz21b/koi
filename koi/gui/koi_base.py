from PySide.QtGui import QAction

from koi.gui.horse_panel import HorsePanel

class KoiModuleBase:
    def wire(self, koi_base):
        pass


class KoiBase:

    INSTANCE_NAME_FIELD = "koi_instance_name"

    def __init__(self):
        self._instances = dict()

    def set_main_window(self, main_window):
        """ The koi base operates on a main window. That's where
        one can actually produce effects. """
        self._main_window = main_window

    def set_user_session(self, user_session):
        self._user_session = user_session

    def register_instance(self, obj, name):
        # Ensure each instance is uniquely named.
        assert isinstance( name, str)
        assert obj is not None
        assert name not in self._instances.keys()
        assert obj not in self._instances.values(), "{} of name {} is already in the tracked instances".format(obj, name)

        self._instances[name] = obj
        setattr( obj, KoiBase.INSTANCE_NAME_FIELD, name)


    def _locate_menu(self, location):
        for name, menu in self._main_window.menus:
            if name == location:
                return menu

        raise Exception("Menu location '{}' not found".format(location))

    def add_menu_item(self, location, widget_name, roles = []):

        widget = self._instances[widget_name]
        menu = self._locate_menu( location)

        if isinstance(widget, HorsePanel):
            title = widget.get_panel_title()
        else:
            title = "#UNSET TITLE#"

        # Set up the triggered signal so that it triggers the display of the panel

        # Make sure the method name is unique on self
        method_name = "_qaction_triggered_{}".format( getattr( widget, KoiBase.INSTANCE_NAME_FIELD))

        # Adding a method to the main windows. We do that to have callbacks.
        setattr( self._main_window, method_name, lambda: self._main_window.stack.add_panel(widget))
        action = QAction(title, self._main_window)
        action.triggered.connect(getattr( self._main_window, method_name))
        menu.addAction(action)

        if roles:
            action.setEnabled( self._user_session.has_any_roles(roles))