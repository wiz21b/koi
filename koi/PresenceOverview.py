from datetime import timedelta

#from pubsub import pub
I = 1

if __name__ == "__main__":
    import sys
    from PySide.QtGui import QMainWindow

    from koi.base_logging import mainlog,init_logging
    from koi.Configurator import init_i18n,load_configuration,configuration

    init_logging()
    init_i18n()
    load_configuration()

    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session
    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)


from koi.dao import dao
from koi.Configurator import mainlog
from koi.db_mapping import SpecialActivity
from koi.datalayer.employee_mapping import RoleType

from koi.datalayer.database_session import session

from PySide.QtGui import QApplication, QKeySequence, QItemSelection
from PySide.QtGui import QWidget,QStandardItemModel,QVBoxLayout, QColor,QHeaderView, QAbstractItemView, QHBoxLayout,QLabel,QDialog, \
    QBrush, QMenu,QItemSelectionModel,QCursor, QActionGroup, QAction, QTableView, QPalette, QGridLayout, QFrame
from PySide.QtCore import Qt,Slot,Signal, QModelIndex, QPoint
from datetime import date,datetime
import calendar

from koi.gui.ProxyModel import TrackingProxyModel, TableViewSignaledEvents

from koi.gui.horse_panel import HorsePanel


from koi.EditTimeTracksDialog import EditTimeTracksDialog
from koi.EditTaskActionReportsDialog import EditTaskActionReportsDialog
from koi.TimeReportView import TimeReportView
from koi.TimeReportingScanner import TimeReportingScannerDialog
from koi.MonthTimeCorrectionDialog import MonthTimeCorrectionDialog
from koi.SpecialActivityDialog import HolidaysDialog

from koi.gui.dialog_utils import TitleWidget,SubFrame, showWarningBox,NavBar,populate_menu, showErrorBox
from koi.translators import date_to_my, duration_to_hm, nice_round, date_to_dmy

from koi.tools import chrono

from koi.people_admin.people_admin_service import people_admin_service
from koi.people_admin.people_admin_mapping import DayEventType, DayEvent
from koi.server.json_decorator import ServerException

class LabeledValue(QWidget):
    def set_value(self, value):
        self.value_label.setText(str(value))

    def __init__(self, label, parent=None):
        super(LabeledValue, self).__init__(parent)

        hbl = QHBoxLayout()

        self.value_label = QLabel()
        hbl.addWidget(QLabel(label))
        hbl.addWidget(self.value_label)

        self.setLayout(hbl)


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


class PresenceOverviewWidget(HorsePanel):

    @Slot(QModelIndex)
    def cell_entered(self,ndx):
        employee_id = self._employee_id_on_row(ndx)

        if employee_id:
            chrono.chrono_start()

            employee = None
            for i in self.employees:
                if i.employee_id == employee_id:
                    employee = i
                    break

            self.detail_subframe.set_title(employee.fullname)
            self._show_totals_day_off(employee_id)

            d = date(self.base_date.year,
                     self.base_date.month,
                     min( calendar.monthrange(self.base_date.year,self.base_date.month)[1],
                          max(1,ndx.column())))


            tars = dao.task_action_report_dao.get_reports_for_employee_id_on_date(employee_id,d)
            work_timetracks = dao.timetrack_dao.all_work_for_employee_date_manual(employee_id, d)
            presence_timetracks = dao.timetrack_dao.all_presence_for_employee_date_managed_by_code_full(employee_id, d)
            # employee = dao.employee_dao.find_by_id(employee_id)

            special_activities = dao.special_activity_dao.find_on_day(employee_id, d)

            chrono.chrono_click("Redrawing")
            self.time_report_view.redraw(datetime(d.year,d.month,d.day,6,0),tars,employee_id,work_timetracks,presence_timetracks,special_activities,
                                         view_title=_("Work on {}").format(date_to_dmy(d, full_month=True)))
            session().close() # FIXME Put his one line above; but that's tough ! SQLA doesn't help us much here !
            chrono.chrono_click("Session closed")

            # for event_type, duration in self.day_event_totals[employee_id].items():
            #     mainlog.debug("{}{}".format(event_type, duration))


        self._toggle_days_off_actions()

    def _employee_id_on_row(self,row_or_ndx):
        r = row_or_ndx
        if type(r) != int:
            r = row_or_ndx.row()

        return self._table_model.data(self._table_model.index(r,0),
                                      Qt.UserRole)

    DAY_EVENT_PALETTE= {
        DayEventType.holidays       : (Qt.GlobalColor.white, Qt.GlobalColor.red),
        DayEventType.day_off        : (Qt.GlobalColor.white, Qt.GlobalColor.darkRed),
        DayEventType.unpaid_day_off : (Qt.GlobalColor.black, Qt.GlobalColor.magenta),
        DayEventType.free_day       : (Qt.GlobalColor.white, Qt.GlobalColor.darkMagenta),
        DayEventType.overtime       : (Qt.GlobalColor.black, Qt.GlobalColor.green),
        DayEventType.recuperation   : (Qt.GlobalColor.white, Qt.GlobalColor.darkGreen),
        DayEventType.unemployment   : (Qt.GlobalColor.white, Qt.GlobalColor.blue),
        DayEventType.unemployment_short: (Qt.GlobalColor.white, Qt.GlobalColor.darkBlue),
        DayEventType.work_accident  : (Qt.GlobalColor.black, Qt.GlobalColor.yellow),
        DayEventType.sick_leave     : (Qt.GlobalColor.white, Qt.GlobalColor.darkYellow)

    }

    MONTH_EVENT_COLUMN = 2
    YEAR_EVENT_COLUMN = 3


    def _make_total_days_off_panel(self):

        widget = QFrame()
        widget.setObjectName('HorseRegularFrame')

        widget.setFrameShape(QFrame.Panel)
        widget.setFrameShadow(QFrame.Sunken)
        layout = QVBoxLayout()

        #layout.addWidget(QLabel(_("Days off to date")))
        self.day_off_total_duration_labels = dict()
        self.day_off_month_duration_labels = dict()
        self.day_off_labels = dict()

        self._day_off_table_model = QStandardItemModel(10,3)
        self._day_off_table_model.setHorizontalHeaderLabels([None,None,_("This\nmonth"), _("Before")])
        self.day_off_table_view = QTableView(None)
        self.day_off_table_view.setModel(self._day_off_table_model)

        # self.day_off_table_view.setHorizontalHeader(self.headers_view)
        self.day_off_table_view.verticalHeader().hide()
        self.day_off_table_view.setAlternatingRowColors(True)
        self.day_off_table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.day_off_table_view.hide()

        row = 0
        for det in DayEventType.symbols():
            ndx = self._day_off_table_model.index(row,0)
            self._day_off_table_model.setData(ndx,det.description, Qt.DisplayRole)

            ndx = self._day_off_table_model.index(row,1)
            fg, bg = self.DAY_EVENT_PALETTE[det]
            self._day_off_table_model.setData(ndx, QBrush(bg), Qt.BackgroundRole)
            self._day_off_table_model.setData(ndx, QBrush(fg), Qt.TextColorRole)
            self._day_off_table_model.setData(ndx, DayEventType.short_code(det), Qt.DisplayRole)

            row += 1

        layout.addWidget(self.day_off_table_view)

        grid = QGridLayout()
        self.days_off_layout = grid
        grid.setColumnStretch(3,1)
        row = 0

        grid.addWidget(QLabel(_('Year')), row, self.YEAR_EVENT_COLUMN)
        grid.addWidget(QLabel(_('Month')), row, self.MONTH_EVENT_COLUMN)
        row += 1

        for det in DayEventType.symbols():
            self.day_off_total_duration_labels[det] = QLabel("-")
            self.day_off_month_duration_labels[det] = QLabel("-")
            self.day_off_labels[det] = QLabel(det.description)

            hlayout = QHBoxLayout()

            sl = QLabel()
            fg, bg = self.DAY_EVENT_PALETTE[det]

            def to_html_rgb(color):
                i = color.red()*256*256 + color.green() * 256 + color.blue()
                return "#{:06X}".format(i)

            p = QPalette()
            p.setColor(QPalette.Window, QColor(bg))
            p.setColor(QPalette.WindowText, QColor(fg))
            sl.setPalette(p)
            sl.setAlignment(Qt.AlignCenter)
            sl.setStyleSheet("border: 2px solid black; background: {}".format( to_html_rgb(QColor(bg))));

            t = DayEventType.short_code(det)
            mainlog.debug(t)
            sl.setAutoFillBackground(True)
            sl.setText( t)

            grid.addWidget(sl,row,0)
            grid.addWidget(self.day_off_labels[det], row, 1)
            grid.addWidget(self.day_off_total_duration_labels[det], row, self.YEAR_EVENT_COLUMN)
            grid.addWidget(self.day_off_month_duration_labels[det], row, self.MONTH_EVENT_COLUMN)

            hlayout.addStretch()

            row += 1

        layout.addLayout( grid)
        layout.addStretch()

        self.day_off_table_view.resizeColumnsToContents()
        # self.day_off_table_view.setMinimumWidth( self.day_off_table_view.width())
        # self.day_off_table_view.resize( self.day_off_table_view.minimumWidth(),
        #                                 self.day_off_table_view.minimumHeight(),)

        widget.setLayout(layout)
        return widget


    def _show_totals_day_off(self, employee_id):
        def form_layout_row_set_visible(layout, row_ndx, is_visible):
            for i in range(layout.columnCount()):
                l = layout.itemAtPosition(row_ndx, i)
                if l and l.widget():
                    l.widget().setVisible(is_visible)

        row = 0
        for det in DayEventType.symbols():

            yearly = 0
            if employee_id in self.all_events_in_year:
                if det in self.all_events_in_year[employee_id]:
                    yearly = nice_round(self.all_events_in_year[employee_id][det])

            monthly = 0
            if employee_id in self.day_event_totals:
                if det in self.day_event_totals[employee_id]:
                    monthly = nice_round(self.day_event_totals[employee_id][det])

                # ndx = self._day_off_table_model.index(row,self.YEAR_EVENT_COLUMN)
                # self._day_off_table_model.setData(ndx, v, Qt.DisplayRole)

            if not yearly and not monthly:
                form_layout_row_set_visible(self.days_off_layout, row+1, False)
            else:
                form_layout_row_set_visible(self.days_off_layout, row+1, True)

                self.day_off_total_duration_labels[det].setText(yearly or '-')
                self.day_off_month_duration_labels[det].setText(monthly or '-')

            row += 1

        # self.day_off_table_view.resizeColumnsToContents()

        self.days_off_panel.parent().update()

    @Slot()
    def refresh_action(self):
        global dao

        # mainlog.debug("refresh action started")
        self.hours_per_pers_subframe.set_title(date_to_my(self.base_date,True))


        chrono.chrono_start()
        all_events_in_month = people_admin_service.events_for_month(self.base_date)

        employee_with_events = [ event.employee_id for event in all_events_in_month ]
            
        # mainlog.debug(all_events_in_month)
        
        self.all_events_in_year = people_admin_service.events_for_year(self.base_date.year)
        self.all_presences = all_presences = dao.employee_dao.presence_overview_for_month(self.base_date)

        all_correction_times = dict()
        for s in dao.month_time_synthesis_dao.load_all_synthesis(self.base_date.year,self.base_date.month):
            all_correction_times[s.employee_id] = s.correction_time

        special_activities = dao.special_activity_dao.find_on_month(self.base_date)

        
        employees = list( filter( lambda e: e.is_active
                                  or e.employee_id in all_presences
                                  or e.employee_id in all_correction_times
                                  or e.employee_id in special_activities
                                  or e.employee_id in employee_with_events,
                                  dao.employee_dao.list_overview()))
        self.employees = employees

        chrono.chrono_click()

        day_max = calendar.monthrange(self.base_date.year,self.base_date.month)[1]
        t_start = datetime(self.base_date.year,self.base_date.month,1)
        t_end   = datetime(self.base_date.year,self.base_date.month,day_max,23,59,59,999999)


        self._table_model.setRowCount( len(employees))
        self._table_model.setColumnCount( 1+day_max+3)

        headers = QStandardItemModel(1, 1+day_max+3)

        headers.setHeaderData(0, Qt.Orientation.Horizontal, _("Employee"))
        for i in range(day_max):
            headers.setHeaderData(i+1, Qt.Orientation.Horizontal, "{}".format(i+1))
        headers.setHeaderData(day_max+1, Qt.Orientation.Horizontal, _("Correction"))
        headers.setHeaderData(day_max+2, Qt.Orientation.Horizontal, _("Total"))
        headers.setHeaderData(day_max+3, Qt.Orientation.Horizontal, _("Days off"))

        self.headers_view.setModel(headers) # qt's doc : The view does *not* take ownership
        self.header_model = headers
        self.headers_view.setModel(self.header_model) # qt's doc : The view does *not* take ownership



        # Compute all mondays indices
        monday = 0
        if t_start.weekday() > 0:
            monday = 7 - t_start.weekday()
        all_mondays = []

        while monday < day_max:
            all_mondays.append(monday)
            monday += 7

        today = date.today()

        # mainlog.debug("Running on employees")
        for row in range(self._table_model.rowCount()):

            # Clear the line
            for col in range(0,32):
                ndx = self._table_model.index(row,col)
                self._table_model.setData(ndx,None,Qt.BackgroundRole)
                self._table_model.setData(ndx,QBrush(Qt.GlobalColor.black),Qt.TextColorRole)
                self._table_model.setData(ndx,None,Qt.DisplayRole)
                self._table_model.setData(ndx,None,Qt.UserRole)
                self._table_model.setData(ndx,None,Qt.UserRole+1)
                            #     else:
                #         self._table_model.setData(ndx,None,Qt.BackgroundRole)

                # else:
                #     self._table_model.setData(ndx,None,Qt.DisplayRole)
                #     self._table_model.setData(ndx,None,Qt.BackgroundRole)

            # Mark mondays
            for col in all_mondays:
                # col + 1 to account for the employee column
                self._table_model.setData(self._table_model.index(row,col + 1),QBrush(QColor(230,230,255)),Qt.BackgroundRole)

            # Mark today
            if today.month == self.base_date.month and today.year == self.base_date.year:
                self._table_model.setData(self._table_model.index(row,today.day),QBrush(QColor(255,255,128)),Qt.BackgroundRole)



        row = 0
        for employee in employees: # employees are sorted

            self._table_model.setData(self._table_model.index(row,0),employee.fullname,Qt.DisplayRole) # FIXME Use a delegate
            self._table_model.setData(self._table_model.index(row,0),employee.employee_id,Qt.UserRole) # FIXME Use a delegate

            correction = 0
            if employee.employee_id in all_correction_times:
                correction = all_correction_times[employee.employee_id]
                self._table_model.setData(self._table_model.index(row,day_max+1),
                                          duration_to_hm(correction,short_unit=True),
                                          Qt.DisplayRole)
            else:
                self._table_model.setData(self._table_model.index(row,day_max+1),
                                          None,
                                          Qt.DisplayRole)

            presence = 0
            if employee.employee_id in all_presences and len(all_presences[employee.employee_id]) > 0:
                import functools
                presence = functools.reduce(lambda acc,s:acc+s, all_presences[employee.employee_id], 0)
            presence += correction

            if presence != 0:
                self._table_model.setData(ndx,QBrush(Qt.GlobalColor.black),Qt.TextColorRole)
                self._table_model.setData(self._table_model.index(row,day_max+2),
                                          duration_to_hm(presence,short_unit=True),
                                          Qt.DisplayRole)
            else:
                self._table_model.setData(self._table_model.index(row,day_max+2),
                                          None,
                                          Qt.DisplayRole)


            if employee.employee_id in all_presences and len(all_presences[employee.employee_id]) > 0:
                for b in range(len(all_presences[employee.employee_id])):
                    ndx = self._table_model.index(row,b+1)

                    p = all_presences[employee.employee_id][b]

                    if p > 0:
                        self._table_model.setData(ndx,duration_to_hm(p,short_unit=True),Qt.DisplayRole)
                        self._table_model.setData(ndx,p,Qt.UserRole)

                        if p >= 4 and p <= 8:
                            # Regular work load
                            self._table_model.setData(ndx,QBrush(QColor(192,255,192)),Qt.BackgroundRole)
                        elif p > 8 or (p < 4 and p > 0):
                            # Problematic work load
                            self._table_model.setData(ndx,QBrush(QColor(255,192,192)),Qt.BackgroundRole)


            if employee.employee_id in special_activities:
                sa_of_employee = special_activities[employee.employee_id]

                for sa in sa_of_employee:
                    start = max(t_start, sa.start_time)
                    end = min(t_end, sa.end_time)

                    for i in range(start.day, end.day + 1):
                        ndx = self._table_model.index(row,i)
                        self._table_model.setData(ndx,QBrush(QColor(255,128,0)),Qt.BackgroundRole)


                # self._table_model.setData(self._table_model.index(row,b+1),Qt.AlignRight | Qt.AlignVCenter,Qt.TextAlignmentRole)
            row += 1


        # Display day events

        employee_id_to_row = dict() # little accelerator
        for row in range(len(employees)):
            employee_id_to_row[employees[row].employee_id] = row


        # Compute days off totals and show them

        self.day_event_totals = dict( [ (e.employee_id, dict() ) for e in employees ] )
        for day_event in all_events_in_month:
            # mainlog.debug("employee_id = {}".format(day_event.employee_id))
            # if day_event.employee_id not in self.day_event_totals:
            #    mainlog.debug(self.day_event_totals)
                
            t = self.day_event_totals[day_event.employee_id]
            if day_event.event_type not in t:
                t[day_event.event_type] = day_event.duration
            else:
                t[day_event.event_type] += day_event.duration

        for employee in employees: # employees are sorted
            t = self.day_event_totals[employee.employee_id]
            mainlog.debug(t)
            total_off = sum( t.values())
            mainlog.debug(total_off)
            row = employee_id_to_row[employee.employee_id]
            mainlog.debug(row)
            if total_off:
                self._table_model.setData(self._table_model.index(row,day_max+3),
                                          nice_round(total_off),
                                          Qt.DisplayRole)
            else:
                self._table_model.setData(self._table_model.index(row,day_max+3),
                                          None,
                                          Qt.DisplayRole)

        # Show days off

        for day_event in all_events_in_month:
            row = employee_id_to_row[day_event.employee_id]
            col = day_event.date.day

            fg = bg = None
            if day_event.event_type in self.DAY_EVENT_PALETTE:
                fg, bg = self.DAY_EVENT_PALETTE[day_event.event_type]
            else:
                fg, bg = Qt.GlobalColor.red, Qt.GlobalColor.gray

            ndx = self._table_model.index(row,col)

            self._table_model.setData(ndx,
                                      day_event.day_event_id,
                                      Qt.UserRole + 1)


            # The problem here is to nicely blend the fact
            # that you can have a day event mixed with actual work
            # the very same day. Here's a poor man solution.

            active_time = self._table_model.data(ndx, Qt.UserRole)
            if not active_time:
                self._table_model.setData(ndx,
                                          DayEventType.short_code(day_event.event_type),
                                          Qt.DisplayRole)

                self._table_model.setData(ndx,QBrush(fg),Qt.TextColorRole)
                self._table_model.setData(ndx,QBrush(bg),Qt.BackgroundRole)
            else:
                self._table_model.setData(ndx,QBrush(fg),Qt.TextColorRole)
                self._table_model.setData(ndx,QBrush(bg),Qt.BackgroundRole)

                self._table_model.setData(ndx,
                                          duration_to_hm(active_time,short_unit=True) + DayEventType.short_code(day_event.event_type),
                                          Qt.DisplayRole)

        chrono.chrono_click()

        #for i in range(len(all_mondays)):
        self.table_view.resizeColumnsToContents()

        # mainlog.debug("Reset selection")
        ndx = self.table_view.currentIndex()

        self.table_view.selectionModel().clear()
        # self.table_view.selectionModel().clearSelection()
        # self.table_view.selectionModel().select( self.table_view.model().index(ndx.row(),ndx.column()), QItemSelectionModel.Select)
        # self.table_view.selectionModel().select( self.table_view.model().index(ndx.row(),ndx.column()), QItemSelectionModel.Select)
        self.table_view.selectionModel().setCurrentIndex( self.table_view.model().index(ndx.row(),ndx.column()), QItemSelectionModel.Select)

        self.cell_entered(self.table_view.currentIndex())


    @Slot()
    def edit_tars(self):

        employee_id = self._employee_id_on_row(self.table_view.currentIndex())

        d = date(self.base_date.year,self.base_date.month,min(calendar.monthrange(self.base_date.year,self.base_date.month)[1], max(1,ndx.column())))

        dialog = TimeReportingScannerDialog(self)
        dialog.set_data(datetime(d.year,d.month,d.day,6,0),employee_id)
        dialog.exec_()

        if dialog.result() == QDialog.Accepted:
            # pub.sendMessage('time_report.changed')
            self.timetrack_changed.emit()
            self.refresh_action()

    @Slot()
    def show_actions(self):
        button = self.action_menu.parent()
        p = button.mapToGlobal(QPoint(0,button.height()))
        self.action_menu.exec_(p)

    @Slot()
    def delete_holidays(self):
        ndx = self.table_view.currentIndex()
        employee_id = self._employee_id_on_row(ndx)
        d = date( self.base_date.year, self.base_date.month, ndx.column())

        if dao.special_activity_dao.delete_by_employee_and_date(employee_id,d):
            self.refresh_panel()

    @Slot()
    def create_holidays(self):
        employee_id = self._employee_id_on_row(self.table_view.currentIndex())

        left_col = 1000
        right_col = 0
        for ndx in self.table_view.selectionModel().selectedIndexes():
            c = ndx.column()
            left_col = min(c, left_col)
            right_col = max(c, right_col)


        d_start = date(self.base_date.year,
                       self.base_date.month,
                       min(calendar.monthrange(self.base_date.year,self.base_date.month)[1], max(1,left_col)))

        d_end = date(self.base_date.year,
                     self.base_date.month,
                     min(calendar.monthrange(self.base_date.year,self.base_date.month)[1], max(1,right_col)))

        dialog = HolidaysDialog(self)

        sa = SpecialActivity()
        sa.employee_id = employee_id
        sa.reporter_id = user_session.user_id
        sa.encoding_date = date.today()
        sa.start_time = datetime( d_start.year, d_start.month, d_start.day, 6, 0)
        sa.end_time = datetime( d_end.year, d_end.month, d_end.day, 14, 0)

        dialog.setup(sa,dao.employee_dao.find_by_id(employee_id).fullname)

        # dialog.set_data(employee,self.base_date,c)
        dialog.exec_()
        if dialog.result() == QDialog.Accepted:
            dao.special_activity_dao.save(sa)
            self.refresh_action()

    @Slot()
    def edit_month_correction(self):
        employee_id = self._employee_id_on_row(self.table_view.currentIndex())

        if employee_id:
            employee = dao.employee_dao.find_by_id(employee_id)
            c = dao.month_time_synthesis_dao.load_correction_time(employee_id,self.base_date.year,self.base_date.month)


            dialog = MonthTimeCorrectionDialog(self)
            dialog.set_data(employee.fullname,self.base_date,c)
            dialog.exec_()
            if dialog.result() == QDialog.Accepted:
                c = dao.month_time_synthesis_dao.save(employee_id,self.base_date.year,self.base_date.month,dialog.correction_time)
                self.refresh_action()

    @Slot()
    def month_today(self):
        self.base_date = date.today()
        self.refresh_action()


    @Slot()
    def month_before(self):
        m = self.base_date.month

        if m > 1:
            self.base_date = date(self.base_date.year,m - 1,1)
        else:
            self.base_date = date(self.base_date.year - 1,12,1)
        self.refresh_action()

    @Slot()
    def month_after(self):
        m = self.base_date.month

        if self.base_date.year < date.today().year + 1 \
                or m < date.today().month:
            if m < 12:
                self.base_date = date(self.base_date.year,m + 1,1)
            else:
                self.base_date = date(self.base_date.year + 1,1,1)
            self.refresh_action()


    @Slot()
    def edit_timetrack_no_ndx(self):
        ndx = self.table_view.currentIndex()
        if ndx.isValid() and ndx.column() >= 0 and ndx.row() >= 0:
            self.edit_timetrack(ndx)
        else:
            showWarningBox(_("Can't edit"),_("You must first select a day/person."))


    timetrack_changed = Signal()

    @Slot(QModelIndex)
    def edit_timetrack(self,ndx):
        global dao
        global user_session

        if ndx.column() >= 1:
            edit_date = date(self.base_date.year,self.base_date.month,ndx.column()) # +1 already in because of employee's names
            employee_id = self._employee_id_on_row(ndx)

            tars = dao.task_action_report_dao.get_reports_for_employee_id_on_date(employee_id, edit_date)

            if len(tars) == 0:

                d = EditTimeTracksDialog(self,dao,edit_date)
                d.set_employee_and_date(employee_id,edit_date)
                d.exec_()
                if d.result() == QDialog.Accepted:
                    self.refresh_action()
                    self.timetrack_changed.emit()
                d.deleteLater()

            else:
                edit_date = datetime(self.base_date.year,self.base_date.month,ndx.column(), hour=6)
                from koi.TimeReportingScanner import TimeReportingScannerDialog
                d = TimeReportingScannerDialog(self)
                d.set_data(edit_date,employee_id) # or 16
                d.exec_()
                if d.result() == QDialog.Accepted:
                    self.refresh_action()
                    self.timetrack_changed.emit()
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


    # @Slot(QModelIndex)
    # def timetrack_changed(self,ndx):

    #     selected_timetrack = self.controller.model.object_at(ndx)

    #     # Update the colors in the timetrack views
    #     # to show what action reports correspond to the
    #     # selected timetrack

    #     self.controller_actions.model.current_timetrack = selected_timetrack
    #     self.controller_actions.model.beginResetModel()
    #     self.controller_actions.model.endResetModel()

    #     # Make sure the first of the action reports is shown in the
    #     # table

    #     action_reports = self.controller_actions.model.objects
    #     for i in range(len(action_reports)-1,-1,-1):
    #         if action_reports[i] and action_reports[i].timetrack == selected_timetrack:
    #             self.controller_actions.view.scrollTo(self.controller_actions.model.index(i,0))
    #             break



    def _make_table_header(self):
        pass

    def __init__(self,parent,find_order_action_slot):
        super(PresenceOverviewWidget,self).__init__(parent)

        self.set_panel_title(_("Presence overview"))
        self.base_date = date.today()

        headers = QStandardItemModel(1, 31 + 3)
        self._table_model = QStandardItemModel(1, 31+3, None)


        self.headers_view = QHeaderView(Qt.Orientation.Horizontal,self)
        self.header_model = headers
        self.headers_view.setResizeMode(QHeaderView.ResizeToContents)
        self.headers_view.setModel(self.header_model) # qt's doc : The view does *not* take ownership

        self.table_view = TableViewSignaledEvents(None)
        self.table_view.setModel(self._table_model)

        self.table_view.setHorizontalHeader(self.headers_view)
        self.table_view.verticalHeader().hide()
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.popup_context_menu)

        self.copy_action = QAction(_("Copy order parts"),self.table_view)
        self.copy_action.triggered.connect( self.copy_slot)
        self.copy_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_C))
        self.copy_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.table_view.addAction(self.copy_action)

        self.select_all_action = QAction(_("Select all"),self.table_view)
        self.select_all_action.triggered.connect( self.select_all_slot)
        self.select_all_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_A))
        self.select_all_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.table_view.addAction(self.select_all_action)

        # self.table_view.setSelectionBehavior(QAbstractItemView.SelectItems)
        # self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)

        navbar = NavBar(self, [ (_("Month before"), self.month_before),
                                (_("Today"),self.month_today),
                                (_("Action"),self.show_actions),
                                (_("Month after"), self.month_after),
                                (_("Find"), find_order_action_slot)])

        self.action_menu = QMenu(navbar.buttons[2])
        navbar.buttons[2].setObjectName("specialMenuButton")
        navbar.buttons[4].setObjectName("specialMenuButton")

        self._make_days_off_menu_and_action_group()

        list_actions = [ # (_("Edit"),self.edit_tars, None, None),
            (_("Edit"),self.edit_timetrack_no_ndx, None, None),
            (_("Month correction"),self.edit_month_correction, None, [RoleType.modify_monthly_time_track_correction]),
            (self.days_off_menu, None),
            (self.copy_action, None),
            (self.select_all_action, None)
        ]

            # (_("Insert holidays"),self.create_holidays, None, None),
            # (_("Delete holidays"),self.delete_holidays, None, None) ]

        populate_menu(self.action_menu, self, list_actions)

        # mainlog.debug("tile widget")
        self.title_box = TitleWidget(_("Presence Overview"),self,navbar)
        self.vlayout = QVBoxLayout(self)
        self.vlayout.setObjectName("Vlayout")
        self.vlayout.addWidget(self.title_box)

        self.hours_per_pers_subframe = SubFrame(_("Overview"), self.table_view, self)
        self.vlayout.addWidget(self.hours_per_pers_subframe)

        self.time_report_view = TimeReportView(self)

        self.days_off_panel = self._make_total_days_off_panel()
        vbox = QVBoxLayout()
        vbox.addWidget(self.days_off_panel)
        vbox.addStretch()
        vbox.setStretch(0,0)
        vbox.setStretch(1,1)


        hlayout = QHBoxLayout()
        hlayout.addWidget( self.time_report_view )
        hlayout.addLayout( vbox)
        hlayout.setStretch(0,1)
        self.detail_subframe = SubFrame(_("Day"), hlayout, self)

        self.vlayout.addWidget(self.detail_subframe)

        self.setLayout(self.vlayout)

        # dbox = QVBoxLayout()
        # dbox.addWidget(QLabel("kjkljkj"))

        # self.total_active_hours = LabeledValue(_("Total activity"))
        # dbox.addWidget(self.total_active_hours)

        # hbox = QHBoxLayout()
        # hbox.addWidget(self.table_view)
        # hbox.addLayout(dbox)




        # self.selection_model = self.table_view.selectionModel()
        # mainlog.debug(m)
        #sm = QItemSelectionModel(self.table_view.model())
        #sm.setModel(self.table_view.model())
        # self.table_view.setSelectionModel(self.selection_model)

        self.table_view.selectionModel().currentChanged.connect(self.cell_entered)


        self.table_view.doubleClickedCell.connect(self.edit_timetrack)


    def _selection_to_period(self):
        left_col = 1000
        right_col = 0
        for ndx in self.table_view.selectionModel().selectedIndexes():
            c = ndx.column()
            left_col = min(c, left_col)
            right_col = max(c, right_col)


        d_start = date(self.base_date.year,
                       self.base_date.month,
                       min(calendar.monthrange(self.base_date.year,self.base_date.month)[1], max(1,left_col)))

        d_end = date(self.base_date.year,
                     self.base_date.month,
                     min(calendar.monthrange(self.base_date.year,self.base_date.month)[1], max(1,right_col)))

        return d_start, d_end


    def _toggle_days_off_actions(self):
        day_max = calendar.monthrange(self.base_date.year,self.base_date.month)[1]

        ndx = self.table_view.currentIndex()

        can_add = can_remove = False

        if ndx.column() >= 1 and ndx.column() <= day_max:

            day_event_id = ndx.data(Qt.UserRole+1)

            can_add = True

            # if not day_event_id:
            #     day = ndx.column() - 1
            #
            #     employee_id = self._employee_id_on_row(ndx)
            #     if employee_id in self.all_presences:
            #         if not self.all_presences[employee_id][day]:
            #             can_add = True
            #         else:
            #             can_add = True
            #     else:
            #         can_add = True

            can_remove = day_event_id is not None

        self.days_off_add_submenu.setEnabled(can_add)
        for actions in self.days_off_action_group.actions():
            actions.setEnabled(can_add)

        self.day_off_remove_action.setEnabled(can_remove)


    def _add_day_off(self, action):

        if action.data() != 'Remove':

            day_event_type, day_event_duration = action.data()
            day_event_type = DayEventType.from_str(day_event_type)

            mainlog.debug("selected action {} {}".format(day_event_type, day_event_duration))

            ndx = self.table_view.currentIndex()
            day_event_id = ndx.data(Qt.UserRole+1)

            # if day_event_id:
            #     showWarningBox(_("There's already a day off here"))
            #     return

            employee_id = self._employee_id_on_row(ndx)
            if employee_id in self.all_presences:
                day = ndx.column() - 1
                mainlog.debug("_add_day_off : employee_id={}, day={}".format(employee_id, day))
                mainlog.debug(self.all_presences[employee_id])
                mainlog.debug(type(self.all_presences[employee_id]))

                # if self.all_presences[employee_id][day]:
                #     showWarningBox(_("One can't add day off where there is activity"))
                #     return
            else:
                mainlog.debug("_add_day_off : employee_id={} not yet known".format(employee_id))

            day_event = DayEvent()
            day_event.employee_id = employee_id
            day_event.event_type = day_event_type

            day, last_day = self._selection_to_period()

            if day_event_duration in (0.5, 1):
                days_durations = [ (day, day_event_duration) ]
            else:
                days_durations = []
                day, last_day = self._selection_to_period()
                while day <= last_day:
                    days_durations.append( (day, 1) ) # One full work day on the day
                    day += timedelta(1)

            # mainlog.debug(days_durations)
            mainlog.debug("Creating day event of type {}".format(day_event.event_type))

            try:
                people_admin_service.set_event_on_days( day_event, days_durations)
            except ServerException as ex:
                showErrorBox(ex.translated_message)

            self.refresh_action()


    def _remove_day_off(self):
        # Grab all the selected events

        event_ids = []
        for ndx in self.table_view.selectionModel().selectedIndexes():
            day_event_id = ndx.data(Qt.UserRole+1)
            if day_event_id:
                mainlog.debug("Removing event: {}".format(day_event_id))
                event_ids.append(day_event_id)

        # Remove them

        if event_ids:
            people_admin_service.remove_events(event_ids)
            self.refresh_action()


    def _make_days_off_menu_and_action_group(self):
        # We use a action group to be able to use the data() of actions
        # when action is tigerred

        # Call this ONLY ONCE because there are signal/slot connections.

        self.days_off_menu = QMenu(_("Day off"))
        self.days_off_add_submenu = QMenu(_("Set day off"))
        self.days_off_action_group = QActionGroup(self)

        for det in DayEventType.symbols():
            a_one = QAction(_("Set one day"), self.days_off_action_group)
            a_one.setData( (det.value,1) )

            a_half = QAction(_("Set half day"), self.days_off_action_group)
            a_half.setData( (det.value,0.5) )

            a_period = QAction(_("Set period"), self.days_off_action_group)
            a_period.setData( (det.value,2) )

            self.days_off_action_group.addAction(a_one)
            self.days_off_action_group.addAction(a_half)
            self.days_off_action_group.addAction(a_period)

            m = QMenu(_("Set time off for {}").format(det.description) )
            m.addAction(a_one)
            m.addAction(a_half)
            m.addAction(a_period)
            self.days_off_add_submenu.addMenu(m)

        self.days_off_action_group.triggered.connect(self._add_day_off)

        self.day_off_remove_action = QAction(_("Remove day off"), self)
        self.day_off_remove_action.triggered.connect(self._remove_day_off)

        # Now we have the actions, we build the menu

        self.days_off_menu.addMenu(self.days_off_add_submenu)
        self.days_off_menu.addAction(self.day_off_remove_action)


    @Slot(QPoint)
    def popup_context_menu(self,position):
        self.days_off_menu.exec_(QCursor.pos())


    @Slot()
    def select_all_slot(self):
        m = self.table_view.model()
        all = QItemSelection(m.index(0,0), m.index(m.rowCount()-1, m.columnCount()-1))
        self.table_view.selectionModel().select(all,QItemSelectionModel.Select)

    @Slot()
    def copy_slot(self):

        # Collect the rows indices

        indices = self.table_view.selectedIndexes()

        if not indices:
            return

        min_row = max_row = indices[0].row()
        min_col = max_col = indices[0].column()

        def min_max(minimum, v, maximum):
            if v < minimum:
                return v, maximum
            elif v > maximum:
                return minimum, v
            else:
                return minimum, maximum


        for ndx in self.table_view.selectedIndexes():
            min_row, max_row = min_max(min_row, ndx.row(), max_row)
            min_col, max_col = min_max(min_col, ndx.column(), max_col)

        mainlog.debug("Copy from {},{} to {},{}".format(min_row, min_col, max_row, max_col))

        day_max = calendar.monthrange(self.base_date.year,self.base_date.month)[1]

        s = ""
        for r in range(min_row, max_row+1):
            d = []
            for c in range(min_col, max_col+1):
                ndx = self._table_model.item(r,c)

                if c == 0 or c > day_max:
                    d.append( ndx.data(Qt.DisplayRole) or "")
                else:
                    t = ndx.data(Qt.UserRole+1) # Day off
                    if t:
                        t = ndx.data(Qt.DisplayRole)
                    else:
                        hours = ndx.data(Qt.UserRole) # Activity hours
                        if hours is not None:
                            t = str(hours).replace('.',',')
                        else:
                            t = ""

                    d.append( t)


            s += "\t".join(d) + u"\n"

        QApplication.clipboard().setText(s)




if __name__ == "__main__":
    from koi.session.UserSession import user_session
    user_session.invalidate()
    user_session._roles = set(RoleType.symbols())
    user_session._active = True

    # dao.session.query(DayTimeSynthesis).delete()
    # for employee in dao.session.query(Employee).all():
    #     for daynr in range(1,28):
    #         day = date(2013,5,daynr)
    #         if random.random() > 0.1:
    #             z = 5 + random.random()*4
    #             p = 0.7
    #         else:
    #             z = random.random()*4
    #             p = 0.7
    #         dao.day_time_synthesis_dao.save(employee,day,z,p)


    app = QApplication(sys.argv)

    window = QMainWindow()
    window.setMinimumSize(1024,768)
    presence = PresenceOverviewWidget(window,None)
    window.setCentralWidget(presence)
    window.show()
    presence.refresh_action()
    app.exec_()
