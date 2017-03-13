import os
from PySide.QtCore import Slot,Qt,QRectF
from PySide.QtGui import QGraphicsPixmapItem,QGraphicsScene,QHBoxLayout,QGraphicsView,QWidget,QDialog,QDialogButtonBox,QVBoxLayout,QGraphicsTextItem,QPixmap
from koi.Configurator import mainlog,resource_dir

from koi.dao import dao
from koi.datalayer.database_session import session

class EmployeePictureItem(QGraphicsPixmapItem):
    def __init__(self,image,employee,text = u""):
        super(EmployeePictureItem,self).__init__(image)

        self.employee = employee

        # FIXME Clear ownership issues if any
        name = QGraphicsTextItem(self.employee.fullname + u" " + text,self)
        if image:
            name.setPos((image.width() - name.boundingRect().width()) / 2, image.height())
            self.boundingBox = QRectF(0,0,image.width(),180)
        else:
            self.boundingBox = QRectF(0,0,name.boundingRect().width(),name.boundingRect().height())

        # Using the selection stuff provided by Qt doesn't work very well
        # The colors are not really nice
        # self.setFlags( self.flags() | QGraphicsItem.ItemIsSelectable)


    def boundingRect(self):
        return self.boundingBox



"""Represent an employee face thumbnail. When selected
   its shade changes.
"""

class SelectableEmployeePictureItem(EmployeePictureItem):
    def __init__(self,image,employee):
        super(SelectableEmployeePictureItem,self).__init__(image,employee)

        # Using the selection stuff provided by Qt doesn't work very well
        # The colors are not really nice
        # self.setFlags( self.flags() | QGraphicsItem.ItemIsSelectable)

        self.deselect()


    def select(self):
        self.setOpacity(1.0)
        self.selected = True

    def deselect(self):
        self.setOpacity(0.3)
        self.selected = False

    # FIXME decide : is_selected or selected
    def is_selected(self):
        return self.opacity() > 0.5

    def mousePressEvent(self,event):
        if self.is_selected():
            self.deselect()
        else:
            self.select()



class EmployeePicturePlanScene(QGraphicsScene):

    def __init__(self,parent):
        super(EmployeePicturePlanScene,self).__init__(parent)
        self.items_ordered = []

    def order_scene(self,max_width):

        spacer = 8
        x = y = spacer
        x_max = y_max = 0

        for item in self.items_ordered:
            if isinstance(item,EmployeePictureItem):
                w = item.boundingRect().width()
                h = item.boundingRect().height()

                if x + w > max_width:
                    x = spacer
                    y += h + spacer

                item.setPos(x,y)

                x_max = max(x_max,x + w + spacer)
                y_max = max(y_max,y + h + spacer)

                x += w + spacer


    def addItem(self,item):
        super(EmployeePicturePlanScene,self).addItem(item) # The scene takes ownership of the item
        self.items_ordered.append(item)


    def items(self):
        return self.items_ordered

    def detach_scene_items(self):
        self.items_ordered = []

        # First, we clear the scene (the ownership of the items is given back to python)
        for i in super(EmployeePicturePlanScene,self).items():

            # FIXME If I don't check for None parent, then, the child
            # items are removed form their parent... At worst, they should
            # be removed twice from the scene, but not from their parents...

            if i.parentItem() is None: # children will be handled recursively by removeItem
                self.removeItem(i)
                # mainlog.debug("detaching {}".format(i))







class EditTaskTeamDialog(QDialog):

    @Slot()
    def accept(self):
        #self.detach_scene_items(self.team_out_scene)
        super(EditTaskTeamDialog,self).accept()

    @Slot()
    def reject(self):
        super(EditTaskTeamDialog,self).reject()

    def resizeEvent(self,event):
        self.team_out_scene.order_scene(self.width())
        self.team_out_view.setSceneRect(self.team_out_scene.itemsBoundingRect())
        super(EditTaskTeamDialog,self).resizeEvent(event)


    def exec_(self):
        self.team_out_scene.order_scene(987)
        r = self.team_out_scene.itemsBoundingRect()
        self.team_out_view.setMinimumSize(r.width() + 5 , r.height() + 5) # FIXME Why 5 ?
        super(EditTaskTeamDialog,self).show()

    def selection(self):
        s = []
        for item in self.team_out_scene.items():
            if isinstance(item,EmployeePictureItem) and item.selected:
                s.append( item.employee)
        return s

    def preselect(self,employees):
        if employees:
            for item in self.team_out_scene.items():
                if isinstance(item,EmployeePictureItem):
                    if item.employee in employees:
                        item.select()
                    else:
                        item.deselect()

    def __init__(self,parent,dao):
        super(EditTaskTeamDialog,self).__init__(parent)

        self.setModal(True)

        self.team_out_scene = EmployeePicturePlanScene(self)
        for employee in dao.all():
            self.team_out_scene.addItem( SelectableEmployeePictureItem( employee.picture(),employee)) # Scene takes ownership of the item

        self.team_out_view = QGraphicsView(self.team_out_scene,self)
        self.team_out_view.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        buttons = QDialogButtonBox(self)
        buttons.addButton( QDialogButtonBox.StandardButton.Cancel)
        buttons.addButton( QDialogButtonBox.Ok)

        top_layout = QVBoxLayout(self)
        top_layout.addWidget( self.team_out_view)
        top_layout.addWidget(buttons)
        self.setLayout(top_layout)

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

    def set_model(self,gui_model):
        self.gui_model = gui_model
        self.preselect(gui_model.employees)








class EditableEmployeeFacesView(QGraphicsView):
    def __init__(self,parent,employee_dao):
        super(EditableEmployeeFacesView,self).__init__(parent)
        self.setScene(EmployeePicturePlanScene(self))

        self.dialog = EditTaskTeamDialog(self,employee_dao)
        self.dialog.finished.connect(self.dialogFinished)


    def set_model(self,gui_model):
        self.gui_model = gui_model
        self.redraw()

    def dialogFinished(self,result):
        self.gui_model.employees = self.dialog.selection()
        self.redraw()

    def mouseReleaseEvent(self,qevent):
        super(EditableEmployeeFacesView,self).mouseReleaseEvent(qevent)
        self.dialog.set_model(self.gui_model)
        self.dialog.exec_()

    def resizeEvent(self, resize_event):
        self.scene().order_scene(resize_event.size().width())

    def redraw(self):
        self.scene().detach_scene_items()
        if self.gui_model is not None and self.gui_model.employees is not None: # FIXME gui_model is unclear, must make more doc or change type
            for employee in self.gui_model.employees:
                self.scene().addItem( EmployeePictureItem( employee.picture(),employee))
            self.scene().order_scene(self.width())

    def reset(self,gui_model):
        self.set_model(gui_model)
        self.redraw()





class EditableEmployeeFacesViewSimple(QGraphicsView):

    def __init__(self,parent):
        super(EditableEmployeeFacesViewSimple,self).__init__(parent)

        # Class member init'ed here because if done at the class
        # level it will require a instanciated QApplication to
        # complete.

        self.default_picture = QPixmap(os.path.join(resource_dir,"man.png"))

        self.setScene(EmployeePicturePlanScene(self)) # FIXME Check ownership

        self.employee_cache = dict()
        for employee in dao.employee_dao.all():
            self.employee_cache[employee.employee_id] = employee
            x = employee.picture_data # force load
            session().expunge(employee)

    def set_model(self,employees_data):
        """ employees_data is an array of pairs. Each pair is made
        of an employee entity and a small text that will be attached
        to its picture. """

        # employees = map(lambda eid: self.employee_cache[eid],employee_ids)
        self.gui_model = employees_data
        self.redraw()

    def resizeEvent(self, resize_event):
        self.scene().order_scene(resize_event.size().width())

    def redraw(self):
        self.scene().detach_scene_items()
        if self.gui_model is not None: # FIXME gui_model is unclear, must make more doc or change type
            for employee,data in self.gui_model:
                img = employee.image
                if not img:
                    img = self.default_picture
                self.scene().addItem( EmployeePictureItem( img, employee, str(data)))
            self.scene().order_scene(self.width())
        # mainlog.debug("EditableEmployeeFacesViewSimple.redraw() - done")
