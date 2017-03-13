import os
from PySide.QtCore import Slot
from PySide.QtGui import QWidget,QTabWidget,QMainWindow,QIcon
from koi.base_logging import mainlog
from koi.Configurator import resource_dir


import sys

class HorsePanelTabs(QTabWidget):

    def __init__(self,parent):
        super(HorsePanelTabs,self).__init__(parent)
        self._registered_panels = []
        self.detached_windows = []
        self.tab_trail = []

        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self.close_tab)
        self.currentChanged.connect(self.tab_shown)

    def panels(self):
        """ List of all the managed panels (be they actual panels
        or detached windows; visible or not).
        """

        return self._registered_panels + [dw.centralWidget() for dw in self.detached_windows]

    def has_panel(self, klass, content_hash):
        """ Returns the panel of class klass with content_hash if it exists,
        or None if it doesn't.
        """

        for panel in self.panels():
            if isinstance(panel, klass) and panel.panel_content_hash() == content_hash:
                return panel
        return None

    def _panel_is_shown_in_tab(self,ndx):

        # When a tab is shown, we know it. But what we
        # don't know is what tab is hidden because of that.
        # QTabWidget doesn't say it. Therefore, I have
        # to mark all "other" tabs as inivisble (that's
        # a poor man solution, but tracking wich tab is
        # closed is a bit difficult)

        # mainlog.debug("_panel_is_shown_in_tab : ndx={}".format(ndx))

        for i in range(len(self._registered_panels)):
            widget = self._registered_panels[i]
            if i != ndx and widget._panel_visible:
                widget.set_visibility(False)

        if 0 <= ndx < len(self._registered_panels):
            widget = self._registered_panels[ndx]
            # mainlog.debug("_panel_is_shown_in_tab : widget appears : {}".format(widget))
            widget.set_visibility(True)
        else:
            mainlog.error("Could not show a tabbed panel (ndx={} of {})".format(ndx, len(self._registered_panels)))

    @Slot(int)
    def tab_shown(self,ndx):
        """ Called when the user bring up a tab.
        """

        if ndx != -1:
            # mainlog.debug("tab_shown ndx={} {}".format(ndx,self.widget(ndx)))
            # ndx is the new index
            self._panel_is_shown_in_tab(ndx)


    @Slot()
    def detach_tab(self):

        # Is there at least one tab to detach ?
        if self.count() > 0:
            widget = self.currentWidget()
            old_ndx = self.currentIndex()
            tab_title = self.tabText( old_ndx)

            self._untabify_panel(old_ndx,widget)

            nw = DetachedTabWindow(widget,tab_title,old_ndx,self)
            nw.show()
            self.detached_windows.append(nw)
            widget.show()
            widget.set_visibility(True)



    def _reattach_tab(self,widget,title):
        """ Called when a detached (in a window) tab must be
        reattached to the tab stack.
        """

        # mainlog.debug("_reattach_tab. current index = {}".format(self.currentIndex()))
        self.addTab(widget,title)
        self._registered_panels.append(widget)

        # mainlog.debug("_reattach_tab. current index = {}".format(self.currentIndex()))

        if self.currentIndex() == self.count() - 1:
            self._panel_is_shown_in_tab(self.currentIndex())
        else:
            widget.set_visibility( False)


    def _untabify_panel(self,ndx,panel):
        """ Remove a panel from the tabs and unregister it.
        The tab manager actually forgets the tab.
        """

        mainlog.debug("Untabifying {} {}".format(ndx,panel))
        if 0 <= ndx < len(self._registered_panels):
            if self._registered_panels[ndx] == panel:
                mainlog.debug("Untabified {} {}".format(ndx,panel))

                del self._registered_panels[ndx]

                if ndx > 0:
                    self.setCurrentIndex(ndx-1)

                self.removeTab(ndx) # QTabWidget has no ownership on the widget
                panel.close() # Important if we detach the panel from a tab to a window

                return
        mainlog.error("Unable to properly unregister panel")

    @Slot()
    def remove_tab(self):
        """ Called on user keyboard shortcut
        """

        i = self.currentIndex()
        if i >= 0:
            self.close_tab(i)

    @Slot(int)
    def close_tab(self,ndx):
        """ Called when user hits the close button on a tab.
        That is, when the user wants to close a tab.
        The index is the index that should be removed.
        Before closing we make sure the user actually
        wants to close the tab.
        """

        panel = self.widget(ndx)
        mainlog.debug("Closing tab {} {}".format(ndx,panel))
        if panel.confirm_close():
            panel.set_visibility(False)
            self._untabify_panel(ndx,panel)
            panel.close_panel()
            # self._pop_tab()
            return True
        else:
            return False # close aborted


    def close_all_tabs(self):
        """ Close all tabs and make sure the user confirm each
        tab closing as needed.

        Returns True if all the tabs where successfuly closed.
        False if at least one was not closed.
        """

        for ndx in range(len(self._registered_panels)):
            if self._registered_panels[ndx].needs_close_confirmation():
                self.setCurrentIndex(ndx)
                self._panel_is_shown_in_tab(ndx)

                if not self._registered_panels[ndx].confirm_close():
                    return False

        # At this point, we know that all the tabs can be closed.

        for panel in self._registered_panels:
            panel.close_panel()

        # When I close a tab, another one appears
        # and i don't want that because it makes
        # the screen flicker

        for ndx in range(self.currentIndex()):
            self.removeTab(0)

        while self.count() > 0:
            self.removeTab(self.count()-1)

        self._registered_panels = []

        return True



    # def _push_current_tab(self):
    #     i = self.currentIndex()
    #     if i >= 0:
    #         self.tab_trail.append(self.widget(i))

    def _pop_tab(self):
        while len(self.tab_trail) > 0:
            widget = self.tab_trail.pop()

            i = 0
            while True:
                w = self.widget(i)
                if w == widget:
                    self.setCurrentIndex(i)
                    widget.set_visibility(True)
                    return
                elif not w:
                    break
                else:
                    i = i + 1




    @Slot(QWidget,str)
    def _tab_title_changed(self,widget,new_title):
        if widget in self._registered_panels:
            ndx = self.indexOf(widget)
            self.setTabText(ndx, new_title)
        else:
            for window in self.detached_windows:
                if widget == window.centralWidget():
                    window.setWindowTitle(_("The company") + " - " + new_title.replace('\n','') )
                    break


    def show_panel(self, panel):

        i = 0
        for w in self._registered_panels:
            if w == panel:
                self._panel_is_shown_in_tab(i)
                self.setCurrentIndex(i)
                return w
            else:
                i += 1

        # Check if the panel doesn't belong to a currently
        # detached window

        i = 0
        for win in self.detached_windows:
            w = win.centralWidget()
            if w == panel:
                return w
            else:
                i += 1

        mainlog.error("Trying to show a panel that is not managed")

    def add_panel(self, panel, show=True):
        """ Add the panel to the panel manager (if it's not alreay added).
        The panel will be shown to the user immediately unless invisible is True.
        The panel is added as a tab (not as a detached window).
        """

        i = 0
        for w in self._registered_panels:
            if w == panel:
                if show:
                    self._panel_is_shown_in_tab(i)
                    self.setCurrentIndex(i)
                return w
            else:
                i += 1

        # Check if the panel doesn't belong to a currently
        # detached window

        i = 0
        for win in self.detached_windows:
            w = win.centralWidget()
            if w == panel:
                return w
            else:
                i += 1

        # We've never seen that panel before

        panel._panel_manager = self

        ndx = self.currentIndex()

        if self.count() == 0 or ndx >= self.count():
            # Append the first tab  or append after the existing tabs.
            self._registered_panels.append(panel)
            self.addTab(panel,panel._panel_title)
            ndx = self.count()
        else:
            # Inserting a tab
            self._registered_panels.insert(ndx+1,panel)
            self.insertTab(ndx+1,panel,panel._panel_title)
            ndx = ndx + 1

        # Check if we need to show the panel or not
        # this is useful when we add several tabs
        # at the same time (only one otf them is to be visible)
        if show:
            self._panel_is_shown_in_tab(ndx)
            self.setCurrentIndex(ndx)


class HorsePanel(QWidget):

    def __init__(self,parent):
        super(HorsePanel,self).__init__(parent)
        self._needs_refresh = True
        self._panel_visible = False
        self._panel_manager = None # Will be set when the panel is registerd in the panel manager
        self._panel_title = None # Title of the panel to be shown to the user, use the setter
        mainlog.debug( "HorsePanel.__init__()")


    def panel_content_hash(self):
        """ The content hash represents the content displayed on the panel.
        It is used to decide if a new instance of an existing panel
        must be show (e.g. if you have a CustomerPanel showing IBM's data
        then it is useless to open another panel with IBM).

        So the rule is : we don't open two panels of the same class
        with the same content_hash()

        The hash doesn't necessary have to be "hash". A primary key
        usually makes more sense.

        Finally, if the content hash is None, it means we must not
        check for the displayed content (in our example, it will
        lead to 2 tabs displaying IBM's data)
        """

        return None

    def refresh_action(self):
        """ This will be called by the panel manager (not you!) whenever
        this panel becomes visible. The goal of this mode
        is to draw the panel, display its data.

        This method should be reimplemented in child class.

        *** NEVER CALL THIS DIRECTLY, use refresh_panel instead ***
        """

        mainlog.warning( "HorsePanel.refresh_action() : Not implemented !")

    def confirm_close(self):
        """ This method should ask the user if he really wants to close
        the panel (if it is necessary to ask).

        Will return True if the closing of the panel was confirmed by the user.
        This should be reimplemented.
        """
        return True

    def needs_close_confirmation(self):
        """ True if the closing of the panel will request the user
        to confirm (e.g. save what you were doing). This is used
        to show the panel to the user when asking its confirmation.
        This should be reimplemented.
        """

        return False

    def set_visibility(self, visible):
        if self._panel_visible != visible:
            self._panel_visible = visible
            if self._panel_visible and self._needs_refresh:
                mainlog.debug("Panel is being refreshed now")
                self.refresh_action()
                self._needs_refresh = False

    @Slot()
    def refresh_panel(self):
        """ Connect to this slot to infom the panel that it
        needs to refresh its data. It will do so if the
        panel is currently visible or whenever
        it becomes visible. This is very important performance
        wise as panels will register on change events but
        we don't want them to be refreshed each time the
        data changes but only when it is necessary to show
        the data that changed.

        So wen you need the panel to refresh, that's the
        slot to call.
        """

        if self._panel_visible:
            self.refresh_action()
            self._needs_refresh = False
        else:
            mainlog.debug("Panel invisible => I don't refresh")
            self._needs_refresh = True

    def set_panel_title(self,title):
        """ Changes the visible title of this panel.
        """
        self._panel_title = title
        if self._panel_manager:
            self._panel_manager._tab_title_changed(self,self._panel_title)

    def get_panel_title(self):
        return self._panel_title

    def close_panel(self):
        # Called each time a panel is closed
        pass

class DetachedTabWindow(QMainWindow):
    def closeEvent( self, event): # a QCloseEvent
        mainlog.debug("Closing detached window")

        if self.tab_on_close:
            mainlog.debug("Retabbing detached window")
            w = self.centralWidget()
            w.close()
            w.setParent(None) # detach the widget ('cos setCentralWidget took ownership)
            self.setCentralWidget(None) # FIXME is this really necessary ? (provided we've cleared w's parent)

            self.base_window._reattach_tab(w,self.widget_name)

        super(DetachedTabWindow,self).closeEvent(event)
        self.base_window.detached_windows.remove(self) # Not quite nice


    def __init__(self,widget,widget_name,old_ndx,base_window):
        super(DetachedTabWindow,self).__init__()
        self.setWindowTitle(_("The company") + " - " + widget_name.replace('\n','') )
        self.base_window = base_window
        self.widget_name = widget_name
        self.old_ndx = old_ndx
        self.tab_on_close = True
        self.setCentralWidget(widget) # takes ownership
        self.setWindowIcon(QIcon(os.path.join(resource_dir,'win_icon.png')))

    def terminate(self):
        """ Closes a window without putting it back into the QTabWidget """
        self.tab_on_close = False
        self.close()
