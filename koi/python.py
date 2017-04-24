
# We don't import everything at the top to accelerate loading.
# This is necessary when this Koi version needs to chain load a
# more recent version. For example, in that case, if we don't
# take care we might load Qt libs twice (and that's slow).

#noinspection PyUnresolvedReferences
import os
# This is a bug fix for
# https://bitbucket.org/anthony_tuininga/cx_freeze/issue/138/cryptography-module
os.environ['OPENSSL_CONF'] = 'fix'

import sys
import locale
from urllib.request import urlopen
import argparse
import logging

from koi.Configurator import init_i18n,load_configuration, resource_dir

#noinspection PyUnresolvedReferences
from koi.Configurator import configuration

from koi.base_logging import init_logging,get_data_dir

#noinspection PyUnresolvedReferences
from koi.base_logging import mainlog
from koi.download_version import upgrade_process, RETURN_CODE_SUCCESS
from koi.legal import copyright, license_short



parser = argparse.ArgumentParser(description='Here are the command line arguments you can use :')
parser.add_argument('--finish-update', default=False, help='Continue the update process started by a previous instance')
#parser.add_argument('--reinstall', action='store_true', default=False, help='Reinstall the version of the version server')
parser.add_argument('--console', action='store_true', default=False, help='Activate console output')
parser.add_argument('--debug', action='store_true', default=False, help='Verbose debug output output')
parser.add_argument('--dev', action='store_true', default=False, help='Equals --console --debug --no-update')
parser.add_argument('--demo', action='store_true', default=False, help='Run as the demo')
parser.add_argument('--screenshots', action='store_true', default=False, help='Make a collection of screenshots')
parser.add_argument('--echo-sql', action='store_true', default=False, help='Show SQL statements')
parser.add_argument('--no-update', action='store_true', default=False, help='Run without trying to update')
# parser.add_argument('--watchdog-file', action='store_true', default="watchdog", help='Watch dog file')
args = parser.parse_args()

if args.dev:
    args.debug = args.console = args.no_update = True

init_logging( console_log=args.console)

if args.debug:
    mainlog.setLevel(logging.DEBUG)

mainlog.info(copyright())
mainlog.info(license_short())

init_i18n()
load_configuration()

upgrade_process(args)


# Help cx_freeze
#noinspection PyUnresolvedReferences
import reportlab.graphics.barcode.common
#noinspection PyUnresolvedReferences
import reportlab.graphics.barcode.code128
#noinspection PyUnresolvedReferences
import reportlab.graphics.barcode.code93
#noinspection PyUnresolvedReferences
import reportlab.graphics.barcode.code39
#noinspection PyUnresolvedReferences
import reportlab.graphics.barcode.usps
#noinspection PyUnresolvedReferences
import reportlab.graphics.barcode.usps4s
#noinspection PyUnresolvedReferences
import reportlab.graphics.barcode.fourstate
#noinspection PyUnresolvedReferences
import reportlab.graphics.barcode.eanbc
#noinspection PyUnresolvedReferences
import reportlab.graphics.barcode.lto
#noinspection PyUnresolvedReferences
import reportlab.graphics.barcode.qr





#noinspection PyUnresolvedReferences
from PySide.QtGui import QApplication, QPixmap, QSplashScreen, QIcon
#noinspection PyUnresolvedReferences
from PySide.QtCore import Qt

from koi.gui.dialog_utils import showErrorBox,showWarningBox, populate_menu

app = None
splash = None

def splash_msg(msg):
    splash.showMessage( u"{} - {}".format(configuration.this_version,msg),
                        Qt.AlignBottom | Qt.AlignCenter)
    splash.update()
    for xyzi in range(100): # Strange name to avoid defining local variable...
        app.processEvents()


mainlog.debug("Python {}".format(str(sys.version).replace('\n',' ')))
# mainlog.debug("SQLAlchemy {}".format(sqlalchemy.__version__))
# mainlog.debug("PySide {}".format(PySide.__version__))
# mainlog.debug("QtCore {}".format(PySide.QtCore.__version__))
# mainlog.debug("Console encoding : {}".format(sys.getdefaultencoding()))
mainlog.debug("Locale : {}".format(locale.getdefaultlocale()))
mainlog.debug("Config dir : {}".format(get_data_dir()))
mainlog.debug("Resource dir : {}".format(resource_dir))

app = QApplication(sys.argv)
app.setWindowIcon(QIcon(os.path.join(resource_dir,'win_icon.png')))

# Fix issues with combo box that gets cleared too fast
app.setEffectEnabled(Qt.UI_AnimateCombo, False)

if configuration.font_select == False:
    qss = open( os.path.join(resource_dir,"standard.qss"),"r")
else:
    qss = open( os.path.join(resource_dir,"bigfont.qss"),"r")

app.setStyleSheet(qss.read())
qss.close()

# from PySide.QtGui import QPainter, QBrush,QColor,QPen, QStyleOption, QStyle
# from PySide.QtCore import QTimer

# class SplashScreen(QSplashScreen):
#     def __init__(self,pixmap):
#         super(SplashScreen, self).__init__(pixmap)

#         self.timer = QTimer(self)
#         self.timer.timeout.connect(self.alpha_update) # timerUpdate)
#         self.timer.start(25) # -1 so we never miss a minute

#         self.alpha = 255


#     def alpha_update(self):
#         self.alpha -= 15
#         if self.alpha > 0:
#             self.repaint()

#         if self.alpha == 0:
#             self.timer.stop()
#             #self.close()

#     def paintEvent(self,pe):
#         super(SplashScreen, self).paintEvent(pe)
#         p = QPainter(self)
#         p.fillRect(0,0,self.width(),self.height(), QColor(255,255,255,self.alpha))


pixmap = QPixmap(os.path.join(resource_dir,"client_splash.png"))
splash = QSplashScreen(pixmap)
splash.setMask(pixmap.mask())
# splash.setWindowFlags(Qt.WindowStaysOnTopHint)
splash.show()

splash_msg( u"{} - ".format(configuration.this_version) + _("Contacting updates server"))

splash_msg( _("Loading database URL"))
try:
    configuration.load_database_param()
except Exception as e:
    mainlog.error(e)
    mainlog.error( "I was unable to get the DB URL from the server {}, so I'll continue with the file configuration".format(
        configuration.database_url_source))
    showErrorBox( _("Can't connect to the main server"),
                  _("I was unable to contact the main server (located here : {}). It is not 100% necessary to do so but that's not normal either. You should tell your administrator about that. I will now allow you to change the network address of the server I know in the preferences panel.").format(
                      configuration.database_url_source))

    splash.repaint()

from datetime import datetime

from PySide.QtCore import *
from PySide.QtGui import *
# from PySide.QtGui import QDesktopServices
# from PySide.QtCore import QUrl
# from PySide.QtTest import QTest

from koi.tools.chrono import *
from koi.datalayer.sqla_mapping_base import metadata
from koi.datalayer.database_session import init_db_session,session
from koi.datalayer.connection import check_db_connection

try:
    init_db_session(configuration.database_url, metadata, args.echo_sql)
except Exception as e:
    mainlog.error(e)
    showErrorBox( _("Can't initialize the database connection"),
                  _("I have tried this url : {}. And got this problem : {}").format(
                      configuration.database_url, str(e)))
    splash.repaint()

from koi.db_mapping import Order,OrderPart
from koi.datalayer.employee_mapping import RoleType
from koi.gui.AboutBox import AboutDialog
from koi.gui.AboutDemoBox import AboutDemoDialog
from koi.EditConfigurationDialog import EditConfigurationDialog

splash_msg(_("Checking DB connection"))
check_database = check_db_connection(configuration.database_url)

if (check_database is not True):
    showErrorBox( _("Can't connect to the database"),
                  _("<b>This program is not usable without a database and will therefore shut down now.</b> You should verify if the server is running because this situation can affect all the users of the system. It is a good idea to <b>call the system administrator now </b> because this error should not happen."))

    d = EditConfigurationDialog(None)
    d.exec_()
    # An "app must be restarted" message has been shown to the user
    sys.exit(RETURN_CODE_SUCCESS)

splash_msg( _("Loading additional data"))

mainlog.debug("Import dao")
from koi.dao import dao
dao.set_session(session())

mainlog.debug("Import query_parser")
from koi.datalayer.query_parser import initialize_customer_cache
initialize_customer_cache()

mainlog.debug("Import rest")



#from EditableTable import EditableTable
# from EmployeesEdit import EditEmployeeDialog
# from SuppliersEdit import EditSupplierDialog
# from CustomerEdit import EditCustomerDialog
from koi.delivery_slips.EditDeliverySlipDialog import handle_edit_delivery_slip
from koi.ReprintDeliverySlip import ReprintDeliverySlipDialog
from koi.EditOrderParts import EditOrderPartsWidget
# from CreateNewOrderDialog import CreateNewOrderDialog
from koi.ChangeCustomerDialog import ChangeCustomerDialog
from koi.EditCustomerDialog import EditCustomerDialog, EditEmployeeDialog
from koi.EditTaskActionReportsDialog import EditTaskActionReportsDialog
from koi.PostView import PostViewWidget
from koi.OrderOverview import OrderOverviewWidget
# from TimeTracksOverview import TimeTracksOverviewWidget
from koi.PresenceOverview import PresenceOverviewWidget

from koi.datalayer.supplier_service import supplier_service
from koi.supply.ChooseSupplierDialog import ChooseSupplierDialog
from koi.supply.EditSupplierDialog import EditSupplierDialog
from koi.supply.SupplyOrderOverview import SupplyOrderOverview
from koi.supply.EditSupplyOrderPanel import EditSupplyOrderPanel

from koi.reporting.rlab import print_employees_badges,print_non_billable_tasks,print_presence_tasks

from koi.reporting.production_status_detailed_report import print_production_status_detailed

from koi.EditTimeTracksDialog import EditTimeTracksDialog

from koi.EditOperationDefinition import EditOperationDefinitionsDialog
from koi.machine.EditMachinesDialog import EditMachinesDialog
from koi.FindOrder import FindOrderDialog
from koi.configuration.charts_config import IndicatorsModule
from koi.delivery_slips.DeliverySlipPanel import DeliverySlipPanel

from koi.gui.horse_panel import HorsePanelTabs, HorsePanel
from koi.session.LoginDialog import LoginDialog

from koi.junkyard.services import services
from koi.datalayer.sqla_mapping_base import Base

services.register_for_in_process(session, Base)

# noinspection PyUnresolvedReferences
from koi.session.UserSession import user_session
# noinspection PyUnresolvedReferences
from koi.service_config import remote_documents_service

class KoiBase:

    INSTANCE_NAME_FIELD = "koi_instance_name"

    def __init__(self):
        self._instances = dict()

    def set_main_window(self, main_window):
        self._main_window = main_window

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
            action.setEnabled( user_session.has_any_roles(roles))

_koi_base = KoiBase()


class MainWindow (QMainWindow, KoiBase):

    def __init__(self,dao):
        super(MainWindow,self).__init__()

        self.dao = dao
        self.menus = []

        self.monthly_financial_overview_widget = None
        self.monthly_production_overview_widget = None


    def closeEvent( self, event): # a QCloseEvent

        close_ok = self.stack.close_all_tabs()

        if not close_ok:
            event.ignore()
        else:
            event.accept()

    def _make_menu(self, instance_name, title,list_actions,target):
        global configuration

        menu = QMenu(title)
        # self._populate_menu(menu,list_actions)
        populate_menu(menu,target,list_actions)
        self.menuBar().addMenu(menu)
        self.menus.append( (instance_name, menu) )


    def get_post_view_widget(self):
        if self.post_view_widget is None:
            self.post_view_widget = PostViewWidget(None,self.order_overview_widget,self.find_order_slot) # FIXME is parent right ? see comment above
            self.post_view_widget.order_part_double_clicked.connect(self.order_overview_widget.set_on_order_part_slot)
            self.post_view_widget.addAction(self.find_order_action) # The ownership of action is not transferred to this QWidget.
        return self.post_view_widget

    def get_supply_order_overview_widget(self):
        if self.supply_order_overview_widget == None:

            # The QTabWidget documentation says we must not give a parent to
            # the widgets

            self.supply_order_overview_widget = SupplyOrderOverview(None)
            self.supply_order_overview_widget.supply_order_selected.connect(self._edit_supply_order)
        return self.supply_order_overview_widget


    def get_presence_overview_widget(self):
        if self.presence_overview_widget == None:
            self.presence_overview_widget = PresenceOverviewWidget(None,self.find_order_slot)
            self.presence_overview_widget.addAction(self.find_order_action) # The ownership of action is not transferred to this QWidget.
            self.presence_overview_widget.timetrack_changed.connect(self.order_overview_widget.refresh_panel)
            # self.presence_overview_widget.timetrack_changed.connect(self.get_monthly_production_overview_widget().refresh_panel)
            # self.presence_overview_widget.timetrack_changed.connect(self.module.financial_panel.refresh_panel)
        return self.presence_overview_widget


    def get_delivery_slip_widget(self):
        if self.delivery_slip_widget == None:
            self.delivery_slip_widget = DeliverySlipPanel(None)
            self.delivery_slip_widget.addAction(self.find_order_action) # The ownership of action is not transferred to this QWidget.
            self.delivery_slip_widget.delivery_slip_changed.connect(self.order_overview_widget.refresh_panel)
            # self.delivery_slip_widget.delivery_slip_changed.connect(self.get_monthly_production_overview_widget().refresh_panel)
            # self.delivery_slip_widget.delivery_slip_changed.connect(self.module.financial_panel.refresh_panel)

        return self.delivery_slip_widget

    # def get_monthly_production_overview_widget(self):
    #     if not self.monthly_production_overview_widget:
    #         self.monthly_production_overview_widget = MonthlyProductionReportOverviewWidget(None, remote_indicators_service)
    #
    #     return self.monthly_production_overview_widget


    def build(self):
        # self.edit_order_parts_widget = EditOrderPartsWidget(self,self.find_order_slot) # Ownership with stacked widget ?
        # self.edit_order_parts_widget.set_on_last_order_if_any()


        # self.action_consultation_order = self.menu_order.addAction("Consultation Commande")
        # self.action_consultation_order.triggered.connect(self.orderView)

        # qwa = QWidgetAction(self)
        # qwa.setDefaultWidget(QLabel(_("Edit")))
        # self.menu_order.addAction(qwa)
        # self.action_edit_order = qwa

        self.create_supply_order_action = QAction(_("Create supply order"),self)
        self.create_supply_order_action.triggered.connect( self.create_supply_order)
        self.create_supply_order_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_O))

        self.supply_order_overview_action = QAction(_("Supply order overview"),self)
        self.supply_order_overview_action.triggered.connect( self.show_supply_orders_overview)
        self.supply_order_overview_action.setShortcut(QKeySequence(Qt.Key_F7))

        list_actions = [ (_("Edit suppliers"),self.edit_suppliers,None,None),
                         (self.create_supply_order_action,None),
                         (self.supply_order_overview_action,None) ]

        self._make_menu( "/main_menu/supply", _("Supply"), list_actions, self)

        self.find_order_action = QAction(_('Find order'),self)
        self.find_order_action.triggered.connect( self.find_order_slot)
        self.find_order_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_F))

        self.show_order_overview_action = QAction(_('Show order overview'),self)
        self.show_order_overview_action.triggered.connect( self.show_order_overview)
        self.show_order_overview_action.setShortcut(QKeySequence(Qt.Key_F2))

        list_actions = [ (_("Edit customers"),self.editCustomers,None,None) ]
        self._make_menu( "/main_menu/customers", _("Customers"), list_actions, self)

        list_actions = [ # (_("Show order detail"),self.orderView,        QKeySequence(Qt.Key_F5),None),
                         (_("Create order"),self.orderCreate,             QKeySequence(Qt.CTRL + Qt.Key_N),None),
                         (self.find_order_action,None)]

        # (_("Find order"),self.find_order_slot, QKeySequence(Qt.CTRL + Qt.Key_F),None)]

        self._make_menu( "/main_menu/orders", _("Order"), list_actions, self)

        list_actions = [ (_("Show presence overview"),self.show_presence_overview,QKeySequence(Qt.Key_F3),[RoleType.view_timetrack]),
                         (_("Print badges"),self.print_employees_badges,None,None),
                         (_("Print non billable barcodes"),self.nonBillableTasksPrint,None,None),
                         (_("Print machines barcodes"),self.printMachinesBarcode,None,None),
                         (_("Print presence barcodes"),self.presenceTasksPrint,None,None)]

        self._make_menu( "/main_menu/time_tracking", _("Time tracking"), list_actions, self)

        # self.menu = QMenu(_("Time tracking"))
        # # self.a = self.menu.addAction(_("Edit prestations")) # FIXME  is "prestation" english ?
        # # self.a.triggered.connect(self.editPointage)
        # # self.b = self.menu.addAction(_("Edit time records"))
        # # self.b.triggered.connect(self.editRecords)
        # self.action_show_timetracks_overview = self.menu.addAction(_("Show timetracks overview"))
        # self.action_show_timetracks_overview.triggered.connect(self.show_timetracks_overview)
        # self.menuBar().addMenu(self.menu)

        self.create_delivery_slip_action = QAction(_("Create new delivery slip"),self)
        self.create_delivery_slip_action.triggered.connect( self.edit_delivery_slip)
        self.create_delivery_slip_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_D))

        self.show_delivery_slips_action = QAction(_("Show delivery slips"),self)
        self.show_delivery_slips_action.triggered.connect( self.show_delivery_slips_panel)
        self.show_delivery_slips_action.setShortcut(QKeySequence(Qt.Key_F6))

        # self.reprint_delivery_slip_action = QAction(_("Reprint old delivery slips"),self)
        # self.reprint_delivery_slip_action.triggered.connect( self.reprint_delivery_slip)

        if not user_session.has_any_roles(RoleType.view_prices):
            self.create_delivery_slip_action.setEnabled(False)
            self.create_delivery_slip_action.setVisible(False)
            self.show_delivery_slips_action.setEnabled(False)
            self.show_delivery_slips_action.setVisible(False)

        list_actions = [ (self.create_delivery_slip_action,None),
                         (self.show_delivery_slips_action,None)]
        self._make_menu( "/main_menu/delivery_slips", _("Delivery slips"), list_actions, self)

        # self.menu_production = QMenu(_("Delivery slips"))
        # self.action_edit_delivery_slip = self.menu_production.addAction(_("Create new delivery slip"))
        # self.action_edit_delivery_slip.triggered.connect(self.edit_delivery_slip)
        # self.action_edit_delivery_slip.setShortcut(QKeySequence(Qt.Key_F4))
        # self.action_reprint_delivery_slip = self.menu_production.addAction(_("Reprint delivery slip"))
        # self.action_reprint_delivery_slip.triggered.connect(self.reprint_delivery_slip)
        # self.menuBar().addMenu(self.menu_production)

        list_actions = [ (_("Show order overview"),self.show_order_overview,QKeySequence(Qt.Key_F2),None),
                         (_("Show posts view"),self.show_post_overview,QKeySequence(Qt.Key_F4),None),
                         (_("Print plant status"),self.print_plant_status,None,None)]



        self._make_menu( "/main_menu/production", _("Production"), list_actions, self)

        # self.menu_boards = QMenu(_("Production"))
        # self.action_show_order_overview = self.menu_boards.addAction(_("Show order overview"))
        # self.action_show_order_overview.triggered.connect(self.show_order_overview)
        # self.menuBar().addMenu(self.menu_boards)


        # self.menu_parameter = QMenu(_("Parameters"))
        # self.operation_definition_edit_action = self.menu_parameter.addAction(_("Edit operations"))
        # self.operation_definition_edit_action.triggered.connect(self.editOperationDefinitions)
        # self.customers_edit_action = self.menu_parameter.addAction(_("Edit customers"))
        # self.customers_edit_action.triggered.connect(self.editCustomers)
        # # self.suppliers_edit_action = self.menu_parameter.addAction(_("Suppliers"))
        # # self.suppliers_edit_action.triggered.connect(self.editSuppliers)
        # self.menuBar().addMenu(self.menu_parameter)

        list_actions = [ (_("Edit employees"),self.editEmployees,None,[RoleType.modify_parameters]) ]
        self._make_menu( "/main_menu/employees", _("Employees"), list_actions, self)

        # self.menu_employees = QMenu(_("Employees"))
        # self.employee_edit_action = self.menu_employees.addAction(_("Edit employees"))
        # self.employee_edit_action.triggered.connect(self.editEmployees)
        # self.print_employees_badges_action = self.menu_employees.addAction(_("Print badges"))
        # self.print_employees_badges_action.triggered.connect(self.print_employees_badges)
        # self.menuBar().addMenu(self.menu_employees)

        list_actions = [ (_("Edit operations"),self.editOperationDefinitions,None,[RoleType.modify_parameters]),
                         (_("Edit machines"),self.editMachines,None,[RoleType.modify_parameters]),
                         (_("Document templates"),self.editDocumentTemplates,None,None),
                         (_("Preferences"), self.editPreferences, None, None) ] # [RoleType.modify_document_templates]
        self._make_menu( "/main_menu/parameters", _("Parameters"), list_actions, self)

        self.tab_trail = []

        self.stack = HorsePanelTabs(None)

        self.detach_tab_action = QAction(_('Detach tab'),self.stack)
        self.detach_tab_action.triggered.connect( self.stack.detach_tab)
        self.detach_tab_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_F12))

        self.remove_tab_action = QAction(_('Remove tab'),self.stack)
        self.remove_tab_action.triggered.connect( self.stack.remove_tab)
        self.remove_tab_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_W))

        list_actions = [ (self.detach_tab_action,None),
                         (self.remove_tab_action,None) ]

        self._make_menu( "/main_menu/windows", _("Windows"), list_actions, self)

        list_actions = [ (_("Help page"),self.showHelpDialog,None,None),
                         (_("About {}").format(configuration.get("Globals","name")),self.showAboutDialog,None,None) ]
        self._make_menu( "/main_menu/help", _("Help"), list_actions, self)

        # self.menu_help = QMenu(_("Help"))
        # a = self.menu_help.addAction(_("Help page"))
        # a.triggered.connect(self.showHelpDialog)
        # a = self.menu_help.addAction(_("About Horse"))
        # a.triggered.connect(self.showAboutDialog)
        # self.menuBar().addMenu(self.menu_help)


        self.quit_action = QAction(_('Quit'),self)
        self.quit_action.triggered.connect( self.quit_program)
        self.quit_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_Q))
        self.addAction(self.quit_action)

        # The QTabWidget documentation says we must not give a parent to
        # the widgets

        self.supply_order_overview_widget = None
        # self.supply_order_overview_widget = SupplyOrderOverview(None)
        # self.supply_order_overview_widget.supply_order_selected.connect(self._edit_supply_order)

        self.order_overview_widget = OrderOverviewWidget(None,self.find_order_slot,
                                                         self.create_delivery_slip_action,
                                                         user_session.has_any_roles(RoleType.view_prices))
        self.order_overview_widget.order_part_activated_signal.connect(self.edit_order_part)
        self.order_overview_widget.order_parts_changed.connect(self.refresh_all_order_edits)
        self.order_overview_widget.addAction(self.find_order_action) # The ownership of action is not transferred to this QWidget.

        # self.monthly_production_overview_widget = None
        # self.monthly_production_overview_widget = MonthlyProductionReportOverviewWidget(None, remote_indicators_service)
        # self.monthly_financial_overview_widget = None
        # self.monthly_financial_overview_widget = MonthlyFinancialReportOverviewWidget(None, remote_indicators_service)
        # self.iso_indicators_overview_widget = ISOIndicatorsWidget(None, remote_indicators_service)

        self.post_view_widget = None

        # self.post_view_widget = PostViewWidget(None,self.order_overview_widget,self.find_order_slot) # FIXME is parent right ? see comment above
        # self.post_view_widget.order_part_double_clicked.connect(self.order_overview_widget.set_on_order_part_slot)
        # self.post_view_widget.addAction(self.find_order_action) # The ownership of action is not transferred to this QWidget.

        self.presence_overview_widget = None

        # self.presence_overview_widget = PresenceOverviewWidget(None,self.find_order_slot)
        # self.presence_overview_widget.addAction(self.find_order_action) # The ownership of action is not transferred to this QWidget.
        # self.presence_overview_widget.timetrack_changed.connect(self.order_overview_widget.refresh_panel)
        # self.presence_overview_widget.timetrack_changed.connect(self.monthly_production_overview_widget.refresh_panel)
        # self.presence_overview_widget.timetrack_changed.connect(self.monthly_financial_overview_widget.refresh_panel)



        self.delivery_slip_widget = None

        # self.delivery_slip_widget = DeliverySlipPanel(None)
        # self.delivery_slip_widget.addAction(self.find_order_action) # The ownership of action is not transferred to this QWidget.
        # self.delivery_slip_widget.delivery_slip_changed.connect(self.order_overview_widget.refresh_panel)
        # self.delivery_slip_widget.delivery_slip_changed.connect(self.monthly_production_overview_widget.refresh_panel)
        # self.delivery_slip_widget.delivery_slip_changed.connect(self.monthly_financial_overview_widget.refresh_panel)


        self.stack.addAction(self.detach_tab_action) # The ownership of action is not transferred to this QWidget.

        # self.show_delivery_slips_panel()
        self.show_order_overview()
        # self.stack.add_panel(self.presence_overview_widget, show=False)
        # self.stack.add_panel(self.post_view_widget, show=False)
        # self._add_edit_order_tab_on_last_order()

        self.stack.setCurrentIndex(0)
        self.setCentralWidget(self.stack)
        self.statusBar()
        self.setWindowTitle(configuration.get("User interface","company_name"))


    def _add_edit_order_tab_on_last_order(self):

        last_order = self.dao.order_dao.find_last_one()
        if last_order:
            self._add_edit_order_tab_if_necessary(last_order)

    def _update_order_tab_label(self,label,widget):
        ndx = self.stack.indexOf(widget)
        self.stack.setTabText(ndx,label)


    def _make_edit_order_parts_widget(self):
        global remote_documents_service

        edit_order_parts_widget = EditOrderPartsWidget(self,self.find_order_slot,user_session.has_any_roles(RoleType.view_prices,), remote_documents_service)
        # edit_order_parts_widget.order_shown_changed.connect(self._update_order_tab_label)
        # edit_order_parts_widget.order_changed_signal.connect(self.order_overview_widget.refresh_panel)

        # Usually the tab title is set by the edit order part compoenent
        # trhough _update_order_tab_label slot
        return edit_order_parts_widget

    def _add_edit_order_tab_if_necessary(self,order):
        chrono_start()

        h = (order.customer_id, order.order_id)
        mainlog.debug("New edit order panel : hash {}".format(h))
        chrono_click("_add_edit_order_tab_if_necessary : 0")
        p = self.stack.has_panel(EditOrderPartsWidget,h)
        chrono_click("_add_edit_order_tab_if_necessary : 1")

        if not p:
            chrono_click("_add_edit_order_tab_if_necessary : 2")

            try:
                p = self._make_edit_order_parts_widget()
            except Exception as ex:
                mainlog.exception(ex)
                showErrorBox(_("Unable to show the order"),ex=ex)
                return

            chrono_click("_add_edit_order_tab_if_necessary : 3")

            p.reset_order(order.order_id, overwrite=True)

        chrono_click("_add_edit_order_tab_if_necessary : 4")
        self.stack.add_panel(p) # Add or make it visible

        chrono_click("_add_edit_order_tab_if_necessary : done")
        return p

        # edit_order_parts_widget = self.stack.add_panel_if_necessary(EditOrderPartsWidget,order.order_id)
        # if w.current_order_id != order.order_id:
        #     edit_order_parts_widget.reset_order(order.order_id)

        # i = 0
        # edit_order_parts_widget = None
        # while True:
        #     w = self.stack.widget(i)
        #     if w and isinstance(w, EditOrderPartsWidget) and w.current_order_id == order.order_id:
        #         edit_order_parts_widget = w
        #         break
        #     elif not w:
        #         break
        #     else:
        #         i = i + 1

        # if not edit_order_parts_widget:
        #     edit_order_parts_widget = self._make_edit_order_parts_widget()
        #     edit_order_parts_widget.reset_order(order.order_id)
        # else:
        # self.stack.add_panel(edit_order_parts_widget)

        return edit_order_parts_widget




    def create_supply_order(self):
        if supplier_service.number_of_suppliers() > 0:

            d = ChooseSupplierDialog(self)
            if d.exec_() and d.result() == QDialog.Accepted:
                p = EditSupplyOrderPanel(None)
                p.supply_order_saved.connect(self.get_supply_order_overview_widget().refresh_action)
                self.stack.add_panel(p)
                p.edit_new(d.supplier)
        else:
            showWarningBox(_("No supplier defined"), _("Before creating an order, you must first create a supplier"))


    @Slot(object)
    def _edit_supply_order(self, supply_order):
        p = self.stack.has_panel(EditSupplyOrderPanel,
                                 (supply_order.supply_order_id, supply_order.supplier_id))

        if not p:

            p = EditSupplyOrderPanel(None)
            mainlog.debug("Connecting signal")
            p.supply_order_saved.connect(self.get_supply_order_overview_widget().refresh_action)
            self.stack.add_panel(p)
            p.edit(supply_order.supply_order_id)
        else:
            self.stack.show_panel(p)

    def orderCreate(self):
        if self.dao.customer_dao.number_of_customers() > 0:
            d = ChangeCustomerDialog(self)
            if d.exec_() and d.result() == QDialog.Accepted:
                edit_order_parts_widget = self._make_edit_order_parts_widget()
                edit_order_parts_widget.edit_new_order(d.customer_id)
                self.stack.add_panel(edit_order_parts_widget)
                self.order_overview_widget.refresh_panel()
        else:
            showWarningBox(_("No customer defined"), _("Before creating an order, you must first create a customer"))




    @Slot(OrderPart)
    def edit_order_part(self,order_part):
        w = self._add_edit_order_tab_if_necessary(order_part.order)
        w.select_order_part(order_part)

    @Slot()
    def find_order_slot(self):
        mainlog.debug("find order")
        d = FindOrderDialog(self)
        d.exec_()
        if d.result() == QDialog.Accepted:

            item = d.selected_item()

            if isinstance(item,Order):
                self._add_edit_order_tab_if_necessary(item)

            elif isinstance(item,OrderPart):
                self.edit_order_part(item)
                # edit_order_parts_widget.reset_order_part(item.order)


        d.deleteLater()

    @Slot()
    def quit_program(self):
        self.close()

    @Slot()
    def show_order_overview(self):
        self.stack.add_panel(self.order_overview_widget)

    @Slot()
    def show_presence_overview(self):
        self.stack.add_panel(self.get_presence_overview_widget())

    @Slot()
    def show_post_overview(self):
        self.stack.add_panel(self.get_post_view_widget())

    @Slot()
    def show_delivery_slips_panel(self):
        self.stack.add_panel(self.get_delivery_slip_widget())

    @Slot()
    def show_monthly_financial_overview(self):
        self.stack.add_panel( self.module.financial_panel)

    @Slot()
    def show_monthly_production_overview(self):
        self.stack.add_panel(self.get_monthly_production_overview_widget())

    @Slot()
    def show_iso_indicators_overview(self):
        self.stack.add_panel(self.iso_indicators_overview_widget)


    def productionFileView(self):
        self.stack.setCurrentIndex(0)


    @Slot(int)
    def customer_changed(self,customer_id):
        mainlog.debug("customer_changed")

        for i in range(self.stack.count()):
            w = self.stack.widget(i)

            if isinstance(w,EditOrderPartsWidget) and w.current_customer_id == customer_id:
                w.refresh_customer(customer_id)

    def showAboutDialog(self):
        d = AboutDialog(self)
        d.exec_()
        d.deleteLater()

    def showHelpDialog(self):

        mainlog.debug("Help {}".format(os.path.abspath( os.path.join(resource_dir,"manual.html"))))
        QDesktopServices.openUrl( QUrl( "file:///"+str( os.path.abspath( os.path.join(resource_dir,"manual.html")  )), QUrl.TolerantMode))
        return
        #
        # d = HelpDialog(self)
        # d.exec_()
        # d.deleteLater()

    def editPointage(self):
        d = EditTimeTracksDialog(self,self.dao)
        d.exec_()
        d.deleteLater()

    def editRecords(self):
        d = EditTaskActionReportsDialog(self,self.dao)
        d.exec_()
        d.deleteLater()


    @Slot()
    def edit_task_team(self):
        self.edit_task_team_dialog.show()


    # @Slot()
    # def editCustomerData(self):
    #     customer = None
    #     d = EditCustomerDialog(self,self.dao)
    #     d.preselect_item(self.edit_order_parts_widget.current_customer)
    #     d.show()

    @Slot()
    def editEmployees(self):
        d = EditEmployeeDialog(self,self.dao)
        d.exec_()
        d.deleteLater()

    @Slot()
    def edit_suppliers(self):

        d = EditSupplierDialog(self)
        d.exec_()
        d.deleteLater()

    @Slot()
    def show_supply_orders_overview(self):
        self.stack.add_panel(self.get_supply_order_overview_widget())


    @Slot()
    def refresh_all_order_edits(self):
        # mainlog.debug("refresh_all_order_edits")

        for i in range(self.stack.count()):
            panel = self.stack.widget(i)
            if isinstance(panel,EditOrderPartsWidget):
                panel.refresh_panel()

        # mainlog.debug("refresh_all_order_edits - done")


    @Slot()
    def editCustomers(self):
        d = EditCustomerDialog(self)

        w = self.stack.currentWidget()
        if isinstance(w,EditOrderPartsWidget):
            customer = self.dao.customer_dao.find_by_id(w.current_customer_id,True)
            if customer:
                d.preselect_item(customer)

        d.customer_changed.connect(self.customer_changed)
        d.exec_()
        d.deleteLater()

    @Slot()
    def editOperationDefinitions(self):
        d = EditOperationDefinitionsDialog(self)
        d.exec_()
        d.deleteLater()

    @Slot()
    def printMachinesBarcode(self):
        from koi.reporting.machine_barcodes import print_machines_barcodes
        print_machines_barcodes()

    @Slot()
    def editMachines(self):
        d = EditMachinesDialog(self)
        d.exec_()
        d.deleteLater()

    @Slot()
    def reprint_delivery_slip(self):
        d = ReprintDeliverySlipDialog(self,self.dao)
        d.exec_()
        d.deleteLater()

    @Slot()
    def edit_delivery_slip(self):
        order_id = None
        w = self.stack.currentWidget()

        if self.order_overview_widget == w:
            order_id = self.order_overview_widget.current_order_id()
        elif isinstance(w,EditOrderPartsWidget):
            if w._current_order.order_id and w.save_if_necessary():
                order_id = w._current_order.order_id

        if order_id:
            res = handle_edit_delivery_slip(order_id,self)
            if res:
                # self.edit_order_parts_widget.refresh_panel()
                # self.trigger_order_refresh()
                # pub.sendMessage('delivery_slip.insert')

                mainlog.debug("Refreshing panels")
                for panel in self.stack.panels():
                    mainlog.debug("Panel {} {} ".format(type(panel), isinstance(panel,EditOrderPartsWidget)))
                    if isinstance(panel,EditOrderPartsWidget) and panel.current_order_id == order_id:
                        mainlog.debug("Refreshing panel")
                        panel.refresh_panel()

                self.order_overview_widget.refresh_panel()
                self.get_monthly_production_overview_widget().refresh_panel()
                # self.module.financial_panel.refresh_panel()
                self.get_delivery_slip_widget().refresh_panel()

        else:
            showErrorBox(_("There's no selected order. We can't create a delivery slip without that."))
            return False

    @Slot()
    def editDocumentTemplates(self):
        global remote_documents_service
        from koi.doc_manager.templates_collection_widget import TemplatesCollectionWidgetDialog

        dialog = TemplatesCollectionWidgetDialog(None,remote_documents_service)
        dialog.widget.refresh_templates_list()
        dialog.exec_()


    @Slot()
    def editPreferences(self):
        d = EditConfigurationDialog(self)
        d.exec_()
        d.deleteLater()

    @Slot()
    def print_plant_status(self):
        # print_plant_intervention_sheet(self.dao)
        print_production_status_detailed(self.dao)

    def print_employees_badges(self):
        print_employees_badges(self.dao)

    def nonBillableTasksPrint(self):
        print_non_billable_tasks(self.dao)

    def presenceTasksPrint(self):
        print_presence_tasks(self.dao)





class StatusWidget2(QWidget):
    def __init__(self,parent,text):
        super(StatusWidget2,self).__init__(parent)
        self.base_text = text

        self.msg_label = QLabel()
        l = QHBoxLayout()
        l.addStretch()
        l.addWidget(self.msg_label)
        self.setLayout(l)

        self.updateMessage()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.updateMessage) # timerUpdate)
        self.timer.start(60*1000 - 1) # -1 so we never miss a minute


    @Slot()
    def updateMessage(self):

        # An attempt to prevent the router from closing an inactive
        # connection

        # NO commit so we don't risk closing ongoing transaction
        # although we don't do multithread right now

        if datetime.now().minute % 10 == 0:
            mainlog.debug("Reset connection")
            session().connection().execute("SELECT NULL");

        self.msg_label.setText(u"{}, {}".format(self.base_text, datetime.now().strftime("%A, %d %B %Y, %H:%M")))

# def force_session():
#     if self.base_configuration.has_section('Access'):
#         user_session = UserSession(self.base_configuration.get("Access","user_id"),
#                                    "Forced Administrator",
#                                    map(lambda s:s.strip(), self.base_configuration.get("Access","roles").split(',')))
#         UserSession.force_session(user_session)

def database_operational_error(ex):
    showErrorBox(_("There was a serious problem while accessing the database"),
                 _("This problem might require you to contact your local administrator"),
                 ex)

window = None

def timer_test():
    w = window.findChild(QMessageBox,"warning_box")
    if w and w.isVisible():
        w.accept()

def make_screenshot():
    global window


    from PySide.QtCore import QTimer
    from PySide.QtGui import QPixmap

    def screenshot_callback():
        screenshot = QPixmap.grabWidget(window)
        screenshot = QPixmap.grabWindow(QApplication.desktop().winId())
        screenshot.save("screenshot-main.png")

    def screenshot_callback2():
        window._qaction_triggered_FinancialKPIPanel()
        screenshot = QPixmap.grabWidget(window)
        screenshot.save("screenshot-financial.png")

    def screenshot_callback3a():
        window.show_presence_overview()
        window.presence_overview_widget.table_view.setCurrentIndex( window.presence_overview_widget.table_view.model().index(4,4))
        window.presence_overview_widget.table_view.setCurrentIndex( window.presence_overview_widget.table_view.model().index(5,5))

    def screenshot_callback3():
        window.show_presence_overview()
        window.presence_overview_widget.table_view.setCurrentIndex( window.presence_overview_widget.table_view.model().index(4,4))
        window.presence_overview_widget.table_view.setCurrentIndex( window.presence_overview_widget.table_view.model().index(5,5))

        screenshot = QPixmap.grabWidget(window)
        screenshot = QPixmap.grabWindow(QApplication.desktop().winId())
        screenshot.save("screenshot-presence.png")

    QTimer.singleShot(1000, screenshot_callback)
    QTimer.singleShot(3000, screenshot_callback2)
    QTimer.singleShot(4000, screenshot_callback2)
    QTimer.singleShot(6000, screenshot_callback3a)
    QTimer.singleShot(8000, screenshot_callback3)
    mainlog.info("Screenshots done")
    # screenshot_callback()


def all_systems_go():
    global user_session,configuration,window, args

    mainlog.debug("all_systems_go() : init dao")
    dao.set_session(session())
    mainlog.debug("all_systems_go() : call back")
    dao.set_callback_operational_error(database_operational_error)

    mainlog.debug("all_systems_go() : building mainwindow")
    window = MainWindow(dao)
    window.setMinimumSize(1024,768)
    splash.finish(window)


    mainlog.debug("all_systems_go() : login dialog")
    if not user_session.is_active(): # the configuration may have forced a user

        # Special case for demo

        from koi.datalayer.employee_mapping import Employee
        if 'koi-mes.net' in configuration.get("DownloadSite", "base_url") or args.demo:
            user_session.open(
                dao.employee_dao.authenticate(
                    "roba", Employee.hash_password("roba")))
            d = AboutDemoDialog(None)
            d.exec_()
        else:
            d = LoginDialog(window, user_session)
            d.exec_()

        # splash.repaint()

    # zzz = QWidget()
    # splash.finish(zzz)
    # splash.show()
    # splash.update()
    # from PySide.QtGui import QSound
    # snd = QSound(os.path.join(resource_dir,'logo_sound.wav'))
    # splash.timer.start(25)
    # splash.alpha = 255
    # snd.play()

    if user_session.is_active():
        # d = LoginDialog(window, user_session)
        # d.exec_()

        window.build()
        w = StatusWidget2(window, user_session.name)
        window.statusBar().addWidget(w,100000)
        window.statusBar().setSizeGripEnabled(False)

        _koi_base.set_main_window(window)
        window.module = IndicatorsModule()
        window.module.wire( _koi_base)

        # window.showMaximized() # If I maximize what happens to multiscreens ?
        window.showMaximized()
        # splash = SplashScreen(pixmap)

        if args.screenshots:
            make_screenshot()

        app.exec_()
    else:
        # User was no authorized
        showWarningBox(_("Not authorized"),_("You are not authorized to use this program. Please check with your system administrator."))

    dao.close()

def load_font(font_name):
    title_font_id  = QFontDatabase.addApplicationFont( os.path.join(resource_dir, font_name))
    if title_font_id == -1:
        raise Exception("Could not load font {}".format(font_name))
    return title_font_id

load_font("Roboto-Regular.ttf")
load_font("Roboto-Bold.ttf")
font_database = QFontDatabase()

#f = "Roboto"
#bigfontbold = font_database.font(f,"Bold",48)
# bigfontbold.setWeight(QFont.Bold)
#TitleWidget.font_title = bigfontbold

# freeze_support()
# Exceptions thrown should be caught by sys.excepthook
all_systems_go()
# I show this message to help in making the differnece between normal exits and segfaults
mainlog.info("Quitting normally")
sys.exit(RETURN_CODE_SUCCESS)
