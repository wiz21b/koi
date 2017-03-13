# http://www.qtcentre.org/archive/index.php/t-23518.html
import sys



# import sip
# sip.setapi('QString', 2)


# from PyQt4.QtCore import Qt,QEvent,pyqtSignal
from PySide.QtCore import Qt, Signal, QAbstractTableModel, Slot,QModelIndex
from PySide.QtGui import QTableView, QComboBox, QAbstractItemView, QAbstractItemDelegate


class TurboModel(QAbstractTableModel):
    def __init__(self,parent):
        super(TurboModel,self).__init__(parent)
        self.table = []
        self.references = []
        self.width = 0

    def clear(self):
        self.beginRemoveRows(QModelIndex(),0,self.rowCount()-1)
        self.beginRemoveColumns(QModelIndex(),0,self.width-1)
        self.table = []
        self.references = []
        self.endRemoveColumns()
        self.endRemoveRows()

    def parent(self):
        return QModelIndex()

    def index(self, row, column, parent = QModelIndex()):
        # print "Turbomodel: {} {}".format(row, self.hasIndex( row, column, parent))
        return self.createIndex(row, column)

    def row_of(self,ref):
        return self.references.index(ref)

    def rowCount(self,parent = None):
        # print "rowCount()={}".format(len(self.table))

        return len(self.table)

    def columnCount(self,parent = None):
        if self.rowCount() == 0:
            # print "columnCount 0"
            return 0
        else:
            # print "columnCount {}".format(self.width)
            return self.width

    def data(self, index, role):
        if index.row() < 0 or index.row() >= len(self.table):
            # print "TurboModel.data(). bad index {}".format(index.row())
            return None

        if role in (Qt.EditRole, Qt.DisplayRole):
            return self.table[index.row()][index.column()]
        elif role == Qt.UserRole:
            return self.references[index.row()]
        else:
            return None

    def flags(self, index):
      return Qt.ItemIsSelectable | Qt.ItemIsEnabled

    def _buildModelFromArray(self,array,references,width):
        # Pay attention, this is tricky.
        # I have the impression that Qt's views are really picky about this
        # so, if you remove all the rows of a table, it doesn't mean
        # that you also removed all the columns (from the view standpoint)
        # Therefore, to signal that we've cleared the model, we must
        # delete rows and columns.

        if len(self.table) > 0:
            self.clear()

        if array is not None:
            self.width = width
            self.beginInsertRows(QModelIndex(),0,len(array)-1)
            self.beginInsertColumns(QModelIndex(),0,width-1)

            for i in range(len(array)):
                self.table.append(array[i])
                self.references.append( references[i])

            self.endInsertColumns()
            self.endInsertRows()



class ListView(QTableView):
  # def sizeHint(self):
  #   print "size hint **"
  #   return QSize(0,150)

  itemSelected = Signal(QModelIndex)

  def currentChanged(self,cur_ndx,prev_ndx):
      if cur_ndx.isValid():
          # print cur_ndx.row()
          # print self.model().data(cur_ndx, Qt.UserRole)
          self.itemSelected.emit(cur_ndx)
      super(ListView,self).currentChanged(cur_ndx,prev_ndx)

  def __init__(self,dropdown,parent=None):
    super(ListView,self).__init__(parent)
    self.dropdown = dropdown

    # We make this QTableView look like a QListView

    self.setWordWrap(False)
    self.setSelectionBehavior(QAbstractItemView.SelectRows)
    self.verticalHeader().setVisible(False)
    self.horizontalHeader().setVisible(False)
    self.setShowGrid(False)

    # not useful self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    # self.setSizePolicy( QSizePolicy(QSizePolicy.Ignored,QSizePolicy.Maximum))

  def keyPressEvent(self,e): # void

    # Special trick to allow the QLineEdit to be edited while
    # browsing this list. This is useful to handle, for example,
    # the backspace

    if e.key() not in (Qt.Key_PageUp,Qt.Key_PageDown,Qt.Key_Down,Qt.Key_Up,Qt.Key_Return,Qt.Key_Enter,Qt.Key_Tab):

      # Basically, up & down keys control the dropdown whereas
      # all the other keys control the line edit
      # with a specific exception for enter/retrun (see below)

      self.dropdown.keyPressEvent(e)

    elif e.key() in (Qt.Key_Return,Qt.Key_Enter):

      # The following applies only if the dropdown is inside
      # a "edit next item" paradigm where one should go to
      # the next editable field if he its "enter".
      # We guess we're in such paradigm if the delegate
      # is there (FIXME which is not really a clean way of
      # guessing)

      # Here is the funky sh*t... The goal of the following lines
      # is to leave the combo box directly upon "enter/return".
      # That is not the usual behaviour. The usual behaviour
      # is that if you hit enter in the ListView then the
      # selection in the list is copied in the line edit. Then
      # you have to hit enter once again to confirm the combobox
      # content (that is, the conten of the line edit)

      # print("*** Enter/Return setCurrentIndex on dropdown at {}".format(self.currentIndex().row()))
      # self.dropdown.setCurrentIndex(self.currentIndex().row())
      self.dropdown.first_match = self.currentIndex().row()
      if self.dropdown.delegate:
        self.dropdown.delegate.commitData.emit(self.dropdown)
        self.dropdown.delegate.closeEditor.emit(self.dropdown,QAbstractItemDelegate.EditNextItem)

    else:
      return super(ListView,self).keyPressEvent(e)




def matcher(intext,modeltext):
    """ Look fo intext into modeltext. Based on the position
    of intext, gives a score. The higher score the most
    relevant modeltext is.
    """

    ndx = modeltext.find(intext)
    if ndx == -1:
        return False
    else:
        if ndx == 0:
            end = len(intext)
            if end < len(modeltext) and modeltext[end] == ' ':
                return 11000
        return 10000 - ndx



class AutoCompleteComboBox(QComboBox):
  """ This is an autocomplete combo box
  """

  # def setCurrentItem(self,item):
  #     for i in range(self.list_model.rowCount()):
  #         if item == self.list_model.data(self.list_model.index(i,0), Qt.UserRole):
  #             self.setCurrentIndex(i)
  #             return


  def setCurrentIndex(self,ndx):
      # print "*** setCurrentIndex called with {}".format(ndx)
      super(AutoCompleteComboBox,self).setCurrentIndex(ndx)

  def getCurrentItem(self):
      # print "getCurrentItem: {} out of {}".format(self.currentIndex(), len(self.list_model.table))
      # print self.currentText()
      return self.list_model.table[self.currentIndex()]

      # print "getCurrentItem: {} {} ".format(self.currentIndex(), self.list_view.currentIndex().row())

  def __init__(self,delegate = None, parent=None, sections = [100,300]):
    super(AutoCompleteComboBox,self).__init__(parent)

    self.section_width = sections

    # self.matcher = lambda intext,modeltext : intext.upper() in str(modeltext).upper()
    self.matcher = matcher

    self.delegate = delegate
    self.popup_shown = False
    self.first_match = None
    self.current_shown = 0
    self.first_hit = True
    self.list_view = ListView(self)
    # self.list_view.setMinimumWidth(500)

    # void QAbstractItemDelegate::closeEditor ( QWidget * editor, QAbstractItemDelegate::EndEditHint hint = NoHint )

    self.list_model = TurboModel(self) # The model will be destroyed by the QComboBox
    self.setModel(self.list_model)
    # self.list_view.setModel(self.list_model)
    self.setModelColumn(0)
    self.index = []

    self.setEditable(True)
    self.setInsertPolicy(QComboBox.NoInsert) # Don't let the user mess with our list
    self.setMaxVisibleItems(10)

    # Set up the list view after everything so that it gets properly connected
    # to th emodel. Without that I have strange artifacts such as a list
    # with as many empty lines added after the actual content lines :-(

    self.setView(self.list_view) # QComboBox takes ownership of the view BUG ??? But we also own it !

  def showPopup(self):
    if self.section_width is not None:
        self.list_view.setMinimumWidth(sum(self.section_width))
        for i in range(len(self.section_width)):
            self.list_view.horizontalHeader().resizeSection(i,self.section_width[i])
    else:
        # print self.sizeHint().width()

        self.list_view.setMinimumWidth( self.width())
        self.list_view.horizontalHeader().resizeSection(0,self.width())

    super(AutoCompleteComboBox,self).showPopup()

    # print("showPopup")
    # print(self.list_view.model().rowCount())


  # def matcher(self,intext,modeltext):
  #   return intext.upper() in str(modeltext).upper()


  def keyPressEvent(self,e):

    if e.key() in (Qt.Key_PageUp, Qt.Key_PageDown, Qt.Key_Up, Qt.Key_Escape, Qt.Key_Tab, Qt.Key_Backtab, Qt.Key_Select):

      # We don't touch anything related to navigation (except up & down which are special)

      return super(AutoCompleteComboBox,self).keyPressEvent(e)

    elif e.key() == Qt.Key_Down:

      # What we do here is to make sure that if the user types "down"
      # then the dropdown is shown (and the first of its element is
      # selected).

      # The catch here is that this has to be done only if the dropdown
      # is not already shown... Another catch is that we only want
      # that behaviour when the user hits the "down" key, not when
      # he uses the mouse.

      if not self.popup_shown:
        self.showPopup()
        self.view().setFocus(Qt.OtherFocusReason)
        return

      else:
        return super(AutoCompleteComboBox,self).keyPressEvent(e)

    elif e.key() in (Qt.Key_Enter,Qt.Key_Return) and self.first_match:

      # Secret sauce here !
      # With this we make sure that there's always something
      # selected properly (we don't let the user type in
      # something not in the list...)

      # print("*** leaving dropdown LABEL currentIndex = {}".format(self.currentIndex()))
      return super(AutoCompleteComboBox,self).keyPressEvent(e)


    # If we come here then it's because the user has typed
    # something meaningful for the line edit


    t = self.lineEdit().text()
    if self.first_hit:
      self.first_hit = False
      t = ''
    # print "current text = '{}' selection '{}'".format(t,self.lineEdit().selectedText())

    if e.key() == Qt.Key_Backspace:
      t = t[0:(len(t)-1)] # will work also if len(t) == 0 !
    elif e.text() == ' ' or len(e.text().strip()) == 1:
      t = t + e.text()


    current_shown,first_match,matches = self.filter(t,self.view())
    if len(matches) == 0:
      # The new key broke something => we cannot accept it
      return

    old_shown = self.current_shown
    self.current_shown = current_shown
    self.first_match = first_match
    self._fill_model(matches)
    # useless self.view().reset()

    if self.current_shown > 1 or e.key() == Qt.Key_Backspace:
      super(AutoCompleteComboBox,self).keyPressEvent(e)
      self.lineEdit().setText(t)

      if self.current_shown != old_shown:
        self.showPopup()
        self.view().setFocus(Qt.OtherFocusReason)

    elif self.current_shown == 1 and e.key() != Qt.Key_Backspace:
      # print "one match !!!"
      super(AutoCompleteComboBox,self).keyPressEvent(e)
      self.view().selectRow(self.first_match)
      self.setCurrentIndex(self.first_match)
      # self.hidePopup()

    if self.first_match:
      # print "First match selected is {}".format(  self.first_match)
      self.view().selectRow(self.first_match)
    else:
      # print "No first match..."
      self.view().selectRow(0)

  def make_str_model(self, strings, reference, model = None):
    if strings == None:
        string = []

    if reference == None:
        reference = []

    assert len(strings) == len(reference) # There more or less labels than references...

    self.make_model(strings, strings, reference, model)

  def make_model(self, view, index, reference, model = None):
    """ The view is what is going to be shown, it's an array of arrays
    (so that the displayed items can take the form of a table).
    The index is what will be searched against what the user types.
    The reference is what is denoted by each entry in the index.
    """

    # print "_make_model: {},{},{}".format(len(view),len(index),len(reference))

    self.view_items = view # What's displayed
    self.index = [str((x or "").upper()) for x in index] # string that will be used for search; tolerate None (just for ease of use)
    self.reference = reference # the real item

    self._fill_model(list(range(len(view))))


  def _fill_model(self,indices):

    if len(self.view_items) == 0:
      self.model().clear()
      return

    t = []
    ref = []

    if isinstance(self.view_items[0],list):
      width = len(self.view_items[0])
      for rowndx in indices:
        t.append(self.view_items[rowndx])
        ref.append(self.reference[rowndx])
    else:
      width = 1
      for rowndx in indices:
        t.append([self.view_items[rowndx]])
        ref.append(self.reference[rowndx])

    self.model()._buildModelFromArray(t,ref,width)
    # useless : self.view().reset()

    # print self.model().rowCount()

    # self.list_view.horizontalHeader().setResizeMode(QHeaderView.Fixed)
    if self.section_width is not None:
        self.list_view.setMinimumWidth(sum(self.section_width))
        for i in range(len(self.section_width)):
            self.list_view.horizontalHeader().resizeSection(i,self.section_width[i])
    else:
        # print self.sizeHint().width()

        self.list_view.setMinimumWidth( self.width())
        self.list_view.horizontalHeader().resizeSection(0,self.width())


  def filter(self,refstr,view):
      matches = []
      top_match_ndx, top_match_score = 0,0

      norm_refstr = refstr.upper()

      for i in range(len(self.index)):
          match = self.matcher(norm_refstr,self.index[i])
          if match is not False:
              # print "match at {}".format(i)
              matches.append(i)
              if match > top_match_score:
                  # mainlog.debug( u"TOP match at {}, score {}, chosen txt:{}".format(i,match,self.index[i]))
                  top_match_score = match
                  top_match_ndx = len(matches) - 1

              # Optimize things a bit. Without that the model
              # becomes too big and way too slow for interactive
              # use.

              if len(matches) == 100:
                  break


      # self._fill_model(matches)
      # print("filter nb_matches={}, top_ndx={}".format(len(matches),top_match_ndx))
      return len(matches),top_match_ndx,matches

    # nb_matches = 0
    # for i in range(len(self.index)):
    #   if self.matcher(refstr,self.index[i]):
    #     sitem = QStandardItem()
    #     sitem.setData(self.index[i], Qt.DisplayRole)
    #     sitem.setData(self.index[i], Qt.UserRole)
    #     self.model().setItem(nb_matches,0,sitem) # Model takes ownership of item
    #     nb_matches = nb_matches + 1

    # # if nb_matches == 0:
    # #   self.hidePopup()
    # # else:
    # #   self.showPopup()

    # print("nb_matches = {}".format(nb_matches))
    # self.model().setRowCount(nb_matches)
    # return nb_matches,0

  # def filter2(self,refstr,view):
  #   nr_matches = 0
  #   firs_match = None
  #   for i in range(len(self.index)):
  #     if self.matcher(refstr,self.index[i]):
  #       nr_matches = nr_matches + 1
  #       if view:
  #         view.setRowHidden( i, False)
  #       if first_match == None:
  #         first_match = i
  #     else:
  #       if view:
  #         view.setRowHidden( i, True)
  #   return nr_matches,first_match



@Slot(QModelIndex)
def index_changed(ndx):
    # print "index_changed {}".format(ndx)
    pass

if __name__ == "__main__":
    from koi.base_logging import init_logging
    from koi.Configurator import init_i18n,load_configuration

    init_logging("completer.log")
    init_i18n()
    load_configuration("config.cfg")
    from koi.Configurator import configuration # Why should I do this here ? I don't get it :-(

    from koi.datalayer.sqla_mapping_base import metadata
    from koi.datalayer.database_session import init_db_session

    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)


    from PySide.QtGui import QApplication, QMainWindow, QWidget, QHBoxLayout
    from koi.dao import dao

    app=QApplication(sys.argv)
    window=QMainWindow()


    from koi.machine.machine_service import machine_service
    machines = machine_service.find_machines_for_operation_definition(8)
    editor = AutoCompleteComboBox(window)
    editor.section_width = [400]
    labels = []
    items = []
    for m in machines:
        labels.append(m.fullname + " AAA BBB ccc ddd eee fff ggg hhh")
        items.append(m.machine_id)
    editor.make_str_model(labels, items)
    editor.make_str_model(labels, items)


    widget = QWidget()
    layout = QHBoxLayout()
    layout.addWidget(editor)
    layout.addStretch()
    widget.setLayout(layout)
    window.setCentralWidget(widget)
    window.show()
    app.exec_()




    items = ['alpha','beta','omega','omikron','kjsdhf ksjfh skfjh sdfksdfh sdkfjsf ksd fsdf THE END'] * 10 + ['hyper','this is what ya might need this is what america needs']
    items = list(map(lambda p,i : p + " | " + str(i), items, list(range(len(items)))))

    box = AutoCompleteComboBox()
    # box.make_model( items, items, items)
    # box.setCurrentIndex(3)
    box.section_width = [400]




    view = []
    keys = []
    ref = []
    for order in dao.order_dao.all():
        if order.customer:
            cname = order.customer.fullname
        else:
            cname = ""

        view.append([order.order_id,cname])
        keys.append("{}{}".format(order.order_id,cname))
        ref.append(order)

    # box.make_model([ ['1234','Techspace'], ['15','Alcyon'] ],
    #                [ '1234TECHSPACE'     , '15ALCYON'],
    #                [ None,                 None] )

    box.make_str_model(items,
                       items )

    # box.make_model( view, keys, ref )

    window.setCentralWidget(box)
    window.show()
    app.exec_()
