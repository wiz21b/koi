from datetime import date,datetime
import calendar

from sqlalchemy import and_
from sqlalchemy.sql.expression import asc
from PySide.QtGui import QWidget,QStandardItemModel,QVBoxLayout,QTableView, QColor,QHeaderView, QAbstractItemView, \
    QHBoxLayout, QDialog, QBrush,QItemSelectionModel
from PySide.QtCore import Qt,Slot,QModelIndex

from koi.dao import dao
from koi.session.UserSession import user_session
from koi.db_mapping import TimeTrack,Operation,ProductionFile,OrderPart, TaskOnOperation,Order,TaskOnOrder,TaskOnNonBillable,OperationDefinition
from koi.gui.ProxyModel import PrototypeController, DurationPrototype, TimestampPrototype,TrackingProxyModel,TextLinePrototype,TaskOnOrderPartPrototype,OrderPartOnTaskPrototype,TaskActionTypePrototype,TaskDisplayPrototype,DatePrototype
from koi.gui.dialog_utils import TitleWidget,SubFrame,NavBar,showWarningBox
from koi.EditTimeTracksDialog import EditTimeTracksDialog
from koi.EditTaskActionReportsDialog import EditTaskActionReportsDialog
from koi.translators import duration_to_s,date_to_my,date_to_s


class ActionReportModel(TrackingProxyModel):
    def __init__(self,parent,prototype):
        super(ActionReportModel,self).__init__(parent,prototype)
        self.current_timetrack = None

    def background_color_eval(self,ndx):
        # print self.current_timetrack,self.objects[ndx.row()]
        if self.isIndexValid(ndx) and ndx.row() < len(self.objects) and self.objects[ndx.row()] and self.objects[ndx.row()].timetrack == self.current_timetrack:
            return QBrush(Qt.GlobalColor.green)
        else:
            return None


class TimeTracksOverviewWidget(QWidget):

    @Slot(QModelIndex)
    def cell_entered(self,ndx):
        chrono = datetime.now()

        employee = self.employees[ndx.row()]

        a = max(1,ndx.column())
        d = date(self.base_date.year,self.base_date.month,min(calendar.monthrange(self.base_date.year,self.base_date.month)[1], max(1,ndx.column())))
        # print employee, d

        # Fill in the timetracks report panel ----------------------------

        # First we read the timetrackss and their associated OrderPart

        t_start = datetime(d.year,d.month,d.day,0,0,0,0)
        t_end = datetime(d.year,d.month,d.day,23,59,59,999999)

        # FIXME not abstract enough
        # FIXME This should be in the DAO

        tt = session().query(TimeTrack,OrderPart).\
            join(TaskOnOperation).join(Operation).join(ProductionFile).join(OrderPart).\
            filter(and_(TimeTrack.employee == employee,
                        TimeTrack.start_time >= t_start,
                        TimeTrack.start_time <= t_end)).order_by(asc(TimeTrack.start_time)).all()

        tt += session().query(TimeTrack,Order).join(TaskOnOrder).join(Order).filter(and_(TimeTrack.employee == employee, TimeTrack.start_time >= t_start, TimeTrack.start_time <= t_end)).order_by(asc(TimeTrack.start_time)).all()

        tt += session().query(TimeTrack,OperationDefinition).join(TaskOnNonBillable).join(OperationDefinition).filter(and_(TimeTrack.employee == employee, TimeTrack.start_time >= t_start, TimeTrack.start_time <= t_end)).order_by(asc(TimeTrack.start_time)).all()


        # Fill in the report panel ---------------------------------------

        self.hours_on_day_subframe.set_title(_("Hours worked on the {} by {}").format(date_to_s(d,True),employee.fullname))
        self.controller.model._buildModelFromObjects(map(lambda o : o[0],tt)) #     dao.timetrack_dao.all_for_employee(employee))

        # self.controller.model.row_protect_func = lambda obj,row: obj is not None and obj.managed_by_code

        ndx = 0
        for row in self.controller.model.table:
            if row[1]:
                row[0] = tt[ndx][1] # First column becomes the order
            ndx += 1

        self.controller.view.resizeColumnsToContents()


        # Fill in the time report panel ---------------------------------

        self.pointage_timestamp_prototype.set_fix_date(d)
        self.controller_actions.model._buildModelFromObjects(
            dao.task_action_report_dao.get_reports_for_employee_on_date(employee,d))


    @Slot()
    def refresh_action(self):
        global dao

        self.title_box.set_title(_("Time Records Overview - {}").format(date_to_my(self.base_date,True)))


        self.employees = dao.employee_dao.all()
        day_max = calendar.monthrange(self.base_date.year,self.base_date.month)[1]
        t_start = datetime(self.base_date.year,self.base_date.month,1)
        t_end   = datetime(self.base_date.year,self.base_date.month,day_max,23,59,59,999999)


        self._table_model.setRowCount( len(self.employees))
        self._table_model.setColumnCount( 1+day_max)

        headers = QStandardItemModel(1, 1+day_max)
        headers.setHeaderData(0, Qt.Orientation.Horizontal, _("Employee"))
        for i in range(day_max):
            headers.setHeaderData(i+1, Qt.Orientation.Horizontal, "{}".format(i+1))
        self.headers_view.setModel(headers) # qt's doc : The view does *not* take ownership
        self.header_model = headers

        row = 0
        for employee in self.employees:
            # mainlog.debug(u"refresh action employee {}".format(employee))

            self._table_model.setData(self._table_model.index(row,0),employee.fullname,Qt.DisplayRole) # FIXME Use a delegate
            self._table_model.setData(self._table_model.index(row,0),employee,Qt.UserRole) # FIXME Use a delegate

            tracks = session().query(TimeTrack).filter(and_(TimeTrack.employee_id == employee.employee_id, TimeTrack.start_time >= t_start,TimeTrack.start_time <= t_end)).all()

            # One bucket per day
            buckets = [0] * day_max
            for t in tracks:
                mainlog.debug("Bucket {}".format(t))
                buckets[t.start_time.day - 1] += t.duration

            for b in range(len(buckets)):
                if buckets[b] != 0:
                    self._table_model.setData(self._table_model.index(row,b+1),duration_to_s(buckets[b]),Qt.DisplayRole)
                else:
                    self._table_model.setData(self._table_model.index(row,b+1),None,Qt.DisplayRole)

                if buckets[b] >= 0:
                    # Clear the background
                    self._table_model.setData(self._table_model.index(row,b+1),None,Qt.BackgroundRole)
                else:
                    self._table_model.setData(self._table_model.index(row,b+1),QBrush(QColor(255,128,128)),Qt.TextColorRole)

                self._table_model.setData(self._table_model.index(row,b+1),Qt.AlignRight,Qt.TextAlignmentRole)
            row += 1


        # Compute all mondays indices
        monday = 0
        if t_start.weekday() > 0:
            monday = 7 - t_start.weekday()
        all_mondays = []

        while monday < day_max:
            all_mondays.append(monday)
            monday += 7

        today = date.today()

        for row in range(len(self.employees)):
            # Mark mondays
            for col in all_mondays:
                # col + 1 to account for the employee column
                self._table_model.setData(self._table_model.index(row,col + 1),QBrush(QColor(230,230,255)),Qt.BackgroundRole)

            # Mark today
            if today.month == self.base_date.month and today.year == self.base_date.year:
                self._table_model.setData(self._table_model.index(row,today.day),QBrush(QColor(255,255,128)),Qt.BackgroundRole)

        #for i in range(len(all_mondays)):
        self.table_view.resizeColumnsToContents()

        # mainlog.debug("Reset selection")
        ndx = self.table_view.currentIndex()

        self.table_view.selectionModel().clear()
        # self.table_view.selectionModel().clearSelection()
        # self.table_view.selectionModel().select( self.table_view.model().index(ndx.row(),ndx.column()), QItemSelectionModel.Select)
        # self.table_view.selectionModel().select( self.table_view.model().index(ndx.row(),ndx.column()), QItemSelectionModel.Select)
        self.table_view.selectionModel().setCurrentIndex( self.table_view.model().index(ndx.row(),ndx.column()), QItemSelectionModel.Select)

        # self.cell_entered(self.table_view.currentIndex())


    @Slot()
    def month_today(self):
        self.base_date = date.today()
        self.refresh_action()


    @Slot()
    def month_before(self):
        m = self.base_date.month

        if m > 1:
            self.base_date = date(self.base_date.year,m - 1,self.base_date.day)
        else:
            self.base_date = date(self.base_date.year - 1,12,self.base_date.day)
        self.refresh_action()

    @Slot()
    def month_after(self):
        m = self.base_date.month

        if self.base_date.year < date.today().year or m < date.today().month:
            if m < 12:
                self.base_date = date(self.base_date.year,m + 1,self.base_date.day)
            else:
                self.base_date = date(self.base_date.year + 1,1,self.base_date.day)
            self.refresh_action()

    @Slot()
    def edit_timetrack_no_ndx(self):
        ndx = self.table_view.currentIndex()
        if ndx.isValid() and ndx.column() >= 0 and ndx.row() >= 0:
            self.edit_timetrack(ndx)
        else:
            showWarningBox(_("Can't edit"),_("You must first select a day/person."))


    @Slot(QModelIndex)
    def edit_timetrack(self,ndx):
        global dao
        global user_session

        if not user_session.has_any_roles(['TimeTrackModify']):
            return

        m = self.base_date.month
        edit_date = date(self.base_date.year,m,ndx.column()) # +1 already in because of employee's names
        employee = self._table_model.data(self._table_model.index(ndx.row(),0),Qt.UserRole) # FIXME Use a delegate
        d = EditTimeTracksDialog(self,dao,edit_date)
        d.set_employee_and_date(employee,edit_date)
        d.exec_()
        if d.result() == QDialog.Accepted:
            self.refresh_action()
        d.deleteLater()


    @Slot()
    def editTaskActionReports(self):
        if not user_session.has_any_roles(['TimeTrackModify']):
            return

        m = self.base_date.month
        ndx = self.table_view.currentIndex()

        if ndx.isValid() and ndx.column() >= 0 and ndx.row() >= 0:
            edit_date = date(self.base_date.year,m,ndx.column()) # +1 already in because of employee's names
            employee = self._table_model.data(self._table_model.index(ndx.row(),0),Qt.UserRole) # FIXME Use a delegate

            d = EditTaskActionReportsDialog(dao,self,edit_date)
            d.set_employee_date(employee, edit_date)
            d.exec_()
            if d.result() == QDialog.Accepted:
                self.refresh_action()
            d.deleteLater()
        else:
            showWarningBox(_("Can't edit"),_("You must first select a day/person."))


    @Slot(QModelIndex)
    def timetrack_changed(self,ndx):

        selected_timetrack = self.controller.model.object_at(ndx)

        # Update the colors in the timetrack views
        # to show what action reports correspond to the
        # selected timetrack

        self.controller_actions.model.current_timetrack = selected_timetrack
        self.controller_actions.model.beginResetModel()
        self.controller_actions.model.endResetModel()

        # Make sure the first of the action reports is shown in the
        # table

        action_reports = self.controller_actions.model.objects
        for i in range(len(action_reports)-1,-1,-1):
            if action_reports[i] and action_reports[i].timetrack == selected_timetrack:
                self.controller_actions.view.scrollTo(self.controller_actions.model.index(i,0))
                break


    def __init__(self,parent):
        super(TimeTracksOverviewWidget,self).__init__(parent)

        self.base_date = date.today()

        headers = QStandardItemModel(1, 31 + 1)
        headers.setHeaderData(0, Qt.Orientation.Horizontal, _("Employee"))
        for i in range(31):
            headers.setHeaderData(i+1, Qt.Orientation.Horizontal, "{}".format(i+1))

        self._table_model = QStandardItemModel(1, 31+1, None)


        self.headers_view = QHeaderView(Qt.Orientation.Horizontal,self)
        self.header_model = headers
        self.headers_view.setResizeMode(QHeaderView.ResizeToContents)
        self.headers_view.setModel(self.header_model) # qt's doc : The view does *not* take ownership

        self.table_view = QTableView(None)
        self.table_view.setModel(self._table_model)
        self.table_view.setHorizontalHeader(self.headers_view)
        self.table_view.verticalHeader().hide()
        self.table_view.setAlternatingRowColors(True)
        # self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)


        navbar = NavBar(self, [ (_("Month before"), self.month_before),
                                (_("Today"),self.month_today),
                                (_("Month after"), self.month_after)])

        self.title_box = TitleWidget(_("Time Records Overview"),self,navbar)
        self.vlayout = QVBoxLayout(self)
        self.vlayout.setObjectName("Vlayout")
        self.vlayout.addWidget(self.title_box)


        self.setLayout(self.vlayout)


        self.hours_per_pers_subframe = SubFrame(_("Hours worked per person"), self.table_view, self)

        self.vlayout.addWidget(self.hours_per_pers_subframe)


        hlayout = QHBoxLayout()

        prototype = []
        prototype.append( OrderPartOnTaskPrototype(None, _('Order Part')))
        prototype.append( TaskOnOrderPartPrototype('task', _('Task'),on_date=date.today()))
        prototype.append( DurationPrototype('duration',_('Duration')))
        prototype.append( TimestampPrototype('start_time',_('Start time'),fix_date=date.today()))
        prototype.append( DatePrototype('encoding_date',_('Recorded at'),editable=False))

        self.controller = PrototypeController(self,prototype)
        self.controller.setModel(TrackingProxyModel(self,prototype))
        self.controller.view.setColumnWidth(1,300)
        self.controller.view.horizontalHeader().setResizeMode(QHeaderView.ResizeToContents)
        self.controller.view.horizontalHeader().setResizeMode(1,QHeaderView.Stretch)

        navbar = NavBar(self, [ (_("Edit"), self.edit_timetrack_no_ndx)])
        self.hours_on_day_subframe = SubFrame(_("Total times on day"), self.controller.view, self,navbar)
        hlayout.addWidget(self.hours_on_day_subframe)


        prototype = []
        # prototype.append( EmployeePrototype('reporter', _('Description'), dao.employee_dao.all()))

        prototype.append( TaskDisplayPrototype('task', _('Task')))
        self.pointage_timestamp_prototype = TimestampPrototype('time',_('Hour'),editable=False,fix_date=date.today())
        prototype.append( self.pointage_timestamp_prototype)
        prototype.append( TaskActionTypePrototype('kind',_('Action')))
        prototype.append( TextLinePrototype('origin_location',_('Origin')))
        prototype.append( TextLinePrototype('editor',_('Editor'),editable=False,default='master'))


        self.controller_actions = PrototypeController(self,prototype)
        self.controller_actions.setModel(ActionReportModel(self,prototype))

        navbar = NavBar(self, [ (_("Edit"), self.editTaskActionReports)])
        hlayout.addWidget(SubFrame(_("Time records"),self.controller_actions.view,self,navbar))
        self.controller_actions.view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.controller_actions.view.doubleClicked.connect(self.editTaskActionReports)

        self.controller_actions.view.horizontalHeader().setResizeMode(0,QHeaderView.Stretch)
        self.controller_actions.view.horizontalHeader().setResizeMode(3,QHeaderView.ResizeToContents)
        self.controller_actions.view.horizontalHeader().setResizeMode(4,QHeaderView.ResizeToContents)

        self.vlayout.addLayout(hlayout)

        self.vlayout.setStretch(0,0)
        self.vlayout.setStretch(1,300)
        self.vlayout.setStretch(2,200)

        # self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        #self.table_view.entered.connect(self.cell_entered)

        self.table_view.selectionModel().currentChanged.connect(self.cell_entered)
        self.table_view.doubleClicked.connect(self.edit_timetrack)
        self.controller.view.selectionModel().currentChanged.connect(self.timetrack_changed)
        self.controller.view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.refresh_action()
