import unittest
import tempfile
from unittest import skip

from PySide.QtGui import QApplication,QMainWindow
from PySide.QtTest import QTest

from PySide.QtCore import Qt,QTimer,Slot



from koi.test.test_base import TestBase
from koi.db_mapping import *
from koi.dao import *
from koi.server.server import ClockServer,ServerException
from koi.BarCodeBase import BarCodeIdentifier
from koi.EditOrderParts import EditOrderPartsWidget,operation_definition_cache
from koi.OrderOverview import OrderOverviewWidget
from koi.server.clock_service import ClockService
from koi.server.json_decorator import ServerException,JsonCallWrapper, ServerErrors


class TestEditOrderParts(TestBase):

    @classmethod
    def setUpClass(cls):
        super(TestEditOrderParts,cls).setUpClass()
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        # Fix issues with combo box that gets cleared too fast
        app.setEffectEnabled(Qt.UI_AnimateCombo, False)
        cls.app = app

        operation_definition_cache.refresh()
        cls.mw = QMainWindow()
        cls.mw.setMinimumSize(1024,768)
        cls.widget = EditOrderPartsWidget(None,None,True,cls.remote_documents_service)
        cls.order_overview_widget = OrderOverviewWidget(None,None,
                                                        None,
                                                        True)
        cls.mw.setCentralWidget(cls.widget)
        cls.mw.show()
        QTest.qWaitForWindowShown(cls.mw)


        cls.app.processEvents()

    @classmethod
    def tearDownClass(cls):
        # cls.mw.setCentralWidget(None)
        cls.mw.close()
        cls.widget.close()
        cls.app.processEvents()
        #cls.widget.deleteLater()
        #cls.mw.deleteLater()
        cls.app.processEvents()
        cls.app.closeAllWindows()
        # cls.app.exit()
        cls.app = None

    def setUp(self):
        super(TestEditOrderParts,self).setUp()
        operation_definition_cache.refresh()


    def _encode_imputable_operation(self,description="Description op 1, TOurnage", pause=False):
        widget = self.widget
        app = self.app

        widget.controller_operation.view.setFocus(Qt.OtherFocusReason)


        mainlog.debug("*** Activating operation selection")

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Down) # modifier, delay
        app.processEvents()

        # Operation defintion
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_T) # modifier, delay
        app.processEvents()
        ed = app.focusWidget()
        for i in range(10000):
            app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_O) # modifier, delay
        app.processEvents()

        if pause:
            app.exec_()

        mainlog.debug("*** Selecting operation selection")

        for i in range(10000):
            app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()
        for i in range(10000):
            app.processEvents()

        mainlog.debug("*** Entering description")
        mainlog.debug(app.focusWidget())
        # Operation's description
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_8) # modifier, delay
        app.processEvents()
        QTest.keyClicks(app.focusWidget(), description) # modifier, delay        print(app.focusWidget())
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Uacute) # modifier, delay
        app.processEvents()

        mainlog.debug("*** hitting enter")
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()
        mainlog.debug(app.focusWidget())

        mainlog.debug("*** entering number of hours")

        # Value/price (skipped because TO is not a fixed price)

        # Number of hours
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_8) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()

        # Leave auto edit to give focus back to parent
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Escape) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Escape) # modifier, delay
        app.processEvents()
        app.processEvents()

    def _encode_not_imputable_operation(self):
        widget = self.widget
        app = self.app

        widget.controller_operation.view.setFocus(Qt.OtherFocusReason)
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Down) # modifier, delay

        # Operation defintion
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_M) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_A) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()

        # Operation's description
        QTest.keyClicks(app.focusWidget(), "Not imputable task") # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Uacute) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()

        # Value/price

        QTest.keyClicks(app.focusWidget(), "123.66") # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()

        # Number of hours (skipped because TO is not a fixed price)

        # Leave auto edit to give focus back to parent
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Escape) # modifier, delay
        app.processEvents()
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Escape) # modifier, delay
        app.processEvents()
        app.processEvents()


    def _make_basic_preorder(self):
        app = self.app
        widget = self.widget
        mw = self.mw

        widget.edit_new_order(self.customer.customer_id)


        widget.customer_order_name.setText(u"AKZO123"+ chr(233))

        QTest.keyEvent(QTest.Click, widget.controller_part.view, Qt.Key_Down) # modifier, delay
        app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_1) # modifier, delay
        app.processEvents()
        QTest.keyClicks(app.focusWidget(), "Order part one") # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Uacute) # modifier, delay
        app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_1) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_0) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()
        app.processEvents()

        # deadline
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Tab) # modifier, delay
        app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_1) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_1) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_1) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()

        self._encode_imputable_operation()

        # Leave auto edit to give focus back to parent
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Escape) # modifier, delay
        app.processEvents()
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Escape) # modifier, delay
        app.processEvents()
        app.processEvents()


    def test_create_order_and_report_on_order(self):

        # python test_integration.py TestEditOrderParts.test_create_order_and_report_on_order

        app = self.app
        widget = self.widget
        mw = self.mw
        clock_server = ClockServer(dao)

        self._make_basic_preorder()
        app.processEvents()

        widget._set_state(OrderStatusType.order_ready_for_production)
        self.prepare_to_click_dialog("confirm_estimate_sent")

        # Save
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()
        app.processEvents()
        app.processEvents()

        self.assertTrue( widget._current_order.order_id > 0)


        order = dao.order_dao.find_by_id(widget._current_order.order_id)
        bc = BarCodeIdentifier.code_for(order,self.opdef_order)

        employee_id = dao.employee_dao.any().employee_id
        d1 = datetime(2013,0o5,26,8)
        # clock_server.recordPointage(bc,employee_id, datetime.strftime(d1, "%Y%m%dT%H:%M:%S"),"Nostromo")
        d2 = datetime(2013,0o5,26,10,54)
        # clock_server.recordPointage(bc,employee_id, datetime.strftime(d2, "%Y%m%dT%H:%M:%S"),"Nostromo")

        self.server = JsonCallWrapper( ClockService(), JsonCallWrapper.IN_PROCESS_MODE)
        self.server.record_pointage_on_order(order.order_id,
                                             self.opdef_order.operation_definition_id,
                                             employee_id,
                                             d1,
                                             "nostromo",
                                             TaskActionReportType.start_task,
                                             None)

        self.server.record_pointage_on_order(order.order_id,
                                             self.opdef_order.operation_definition_id,
                                             employee_id,
                                             d2,
                                             "nostromo",
                                             TaskActionReportType.stop_task,
                                             None)


        order = dao.order_dao.find_by_id(widget._current_order.order_id)

        widget.edit_new_order(self.customer.customer_id) # Force the order reset below
        app.processEvents()
        widget.reset_order(order.order_id, overwrite=True)
        app.processEvents()

        # app.exec_()

        # m = widget.indirects
        # self.assertEqual(2.9, m.data( m.index(0,2), Qt.DisplayRole))


    def test_new_order_is_a_preorder(self): # passes
        app = self.app
        widget = self.widget
        mw = self.mw

        mainlog.debug(str(self.customer))

        widget.edit_new_order(self.customer.customer_id)

        #app.exec_()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()

        order = dao.order_dao.find_by_id(widget._current_order.order_id)

        assert order.state == OrderStatusType.preorder_definition
        assert order.preorder_label is not None
        assert order.accounting_label == None



    def test_new_order_is_not_a_preorder(self): # passes
        app = self.app
        widget = self.widget
        mw = self.mw


        widget.edit_new_order(self.customer.customer_id)
        widget.order_state_label.set_value(OrderStatusType.order_ready_for_production)
        self.prepare_to_click_dialog("confirm_estimate")

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()

        order = dao.order_dao.find_by_id(widget._current_order.order_id)

        assert order.state == OrderStatusType.order_ready_for_production
        assert order.preorder_label is None
        assert order.accounting_label is not None


    def test_create_order_and_report_on_operation(self):

        app = self.app
        widget = self.widget
        mw = self.mw
        self._make_basic_preorder()
        # add some more operation
        self._encode_not_imputable_operation()

        widget._set_state(OrderStatusType.order_ready_for_production)
        self.prepare_to_click_dialog("confirm_estimate_sent")

        # Save
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()


        order = dao.order_dao.find_by_id(widget._current_order.order_id)

        mainlog.debug(order)
        mainlog.debug(order.parts[0])
        mainlog.debug(order.parts[0].production_file[0])

        operation = order.parts[0].production_file[0].operations[0]
        employee_id = dao.employee_dao.any().employee_id
        d1 = datetime(2013,0o5,26,8)

        self.server = JsonCallWrapper( ClockService(), JsonCallWrapper.IN_PROCESS_MODE)
        self.server.record_pointage_on_operation(operation.operation_id,
                                                 employee_id,
                                                 d1,
                                                 "nostromo",
                                                 TaskActionReportType.start_task,
                                                 None)


        d2 = datetime(2013,5,26,10,54)
        self.server.record_pointage_on_operation(operation.operation_id,
                                                 employee_id,
                                                 d2,
                                                 "nostromo",
                                                 TaskActionReportType.stop_task,
                                                 None)


        order = dao.order_dao.find_by_id(widget._current_order.order_id)
        operation = order.parts[0].production_file[0].operations[0]

        widget.edit_new_order(self.customer.customer_id) # Force the order reset below
        app.processEvents()
        widget.reset_order(order.order_id, overwrite=True)
        widget.refresh_action()

        m = widget.controller_operation.model
        self.assertEqual(2.9, m.data( m.index(0,4), Qt.UserRole))

        m = widget.controller_part.model
        self.assertEqual(80, m.data( m.index(0,4), Qt.UserRole))
        self.assertEqual(111, m.data( m.index(0,6), Qt.UserRole))

        # app.exec_()



    def _fill_order_part(self,description):
        app = self.app

        # Part's description
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_0) # modifier, delay
        app.processEvents()
        QTest.keyClicks(app.focusWidget(), description) # modifier, delay
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()

        # Part's quantity
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_9) # modifier, delay
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()

        # deadline, skip it
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Tab) # modifier, delay
        app.processEvents()

        # Unit price
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_1) # modifier, delay
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter) # modifier, delay
        app.processEvents()

    def test_edit_order(self):

        app = self.app
        widget = self.widget
        mw = self.mw
        self._make_basic_preorder()

        m = widget.controller_part.view.model()
        widget.controller_part.view.setCurrentIndex( m.index(0,0))

        widget.controller_part.view.setFocus(Qt.OtherFocusReason)
        QTest.keyEvent(QTest.Click, widget.controller_part.view, Qt.Key_Up) # modifier, delay
        QTest.keyEvent(QTest.Click, widget.controller_part.view, Qt.Key_F5) # modifier, delay
        app.processEvents()

        self._fill_order_part("Order part zero")

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Escape) # modifier, delay
        QTest.keyEvent(QTest.Click, widget.controller_part.view, Qt.Key_F5, Qt.ShiftModifier) # modifier, delay
        app.processEvents()

        self._fill_order_part("Order part two")

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()

        # app.exec_()

    def _save(self):
        app = self.app
        # Save
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()

    def test_interrupted_order_update(self):
        # python test_integration.py TestEditOrderParts.test_interrupted_order_update

        app = self.app
        widget = self.widget
        mw = self.mw
        self._make_basic_preorder()

        widget._set_state(OrderStatusType.order_ready_for_production)
        self.prepare_to_click_dialog("confirm_estimate_sent")

        self._save()

        self._encode_imputable_operation()
        self._encode_imputable_operation()
        self._encode_imputable_operation()

        # Interrupt the encoding
        session().commit()


        # Encode some more
        self._encode_imputable_operation()
        self._encode_imputable_operation()

        # And save again
        self._save()


        # app.exec_()



    def test_edit_order_change_state_and_add_part(self):
        # python test_integration.py TestEditOrderParts.test_edit_order_change_state_and_add_part

        app = self.app
        widget = self.widget
        mw = self.mw
        self._make_basic_preorder()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()

        m = widget.controller_part.view.model()
        widget.controller_part.view.setCurrentIndex( m.index(0,0))

        widget.controller_part.view.setFocus(Qt.OtherFocusReason)
        QTest.keyEvent(QTest.Click, widget.controller_part.view, Qt.Key_Up) # modifier, delay
        QTest.keyEvent(QTest.Click, widget.controller_part.view, Qt.Key_F5) # modifier, delay
        app.processEvents()

        self._fill_order_part("Order part zero")

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Escape) # modifier, delay
        QTest.keyEvent(QTest.Click, widget.controller_part.view, Qt.Key_F5, Qt.ShiftModifier) # modifier, delay
        app.processEvents()

        self._fill_order_part("Order part two")

        widget.order_state_label.set_value(OrderStatusType.order_ready_for_production)
        # Because we're moving from a preorder to production directly,
        # skipping the "estimate sent" state.
        self.prepare_to_click_dialog("confirm_estimate_sent")
        # app.exec_()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()

        order = dao.order_dao.find_by_id(widget._current_order.order_id)
        assert order.state == OrderStatusType.order_ready_for_production
        assert order.preorder_label is not None
        assert order.accounting_label is not None
        self.assertEqual(OrderPartStateType.ready_for_production,order.parts[0].state)
        assert order.parts[1].state == OrderPartStateType.ready_for_production
        assert order.parts[2].state == OrderPartStateType.ready_for_production



    def test_edit_order_no_change_state_and_add_part(self):
        # python test_integration.py TestEditOrderParts.test_edit_order_change_state_and_add_part

        app = self.app
        widget = self.widget
        mw = self.mw
        self._make_basic_preorder()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()

        m = widget.controller_part.view.model()
        widget.controller_part.view.setCurrentIndex( m.index(0,0))

        widget.controller_part.view.setFocus(Qt.OtherFocusReason)
        QTest.keyEvent(QTest.Click, widget.controller_part.view, Qt.Key_Up) # modifier, delay
        QTest.keyEvent(QTest.Click, widget.controller_part.view, Qt.Key_F5) # modifier, delay
        app.processEvents()

        self._fill_order_part("Order part zero")

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Escape) # modifier, delay
        QTest.keyEvent(QTest.Click, widget.controller_part.view, Qt.Key_F5, Qt.ShiftModifier) # modifier, delay
        app.processEvents()

        self._fill_order_part("Order part two")

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()

        order = dao.order_dao.find_by_id(widget._current_order.order_id)
        assert order.state == OrderStatusType.preorder_definition
        assert order.preorder_label is not None
        assert order.accounting_label is None
        self.assertEqual(OrderPartStateType.preorder,order.parts[0].state)
        assert order.parts[1].state == OrderPartStateType.preorder
        assert order.parts[2].state == OrderPartStateType.preorder




    def test_edit_add_then_delete(self):
        # python test_integration.py TestEditOrderParts.test_edit_add_then_delete

        app = self.app
        widget = self.widget
        mw = self.mw
        self._make_basic_preorder()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()

        m = widget.controller_part.view.model()
        widget.controller_part.view.setCurrentIndex( m.index(0,0))

        widget.controller_part.view.setFocus(Qt.OtherFocusReason)
        QTest.keyEvent(QTest.Click, widget.controller_part.view, Qt.Key_Up) # modifier, delay
        QTest.keyEvent(QTest.Click, widget.controller_part.view, Qt.Key_F5) # modifier, delay
        app.processEvents()

        self._fill_order_part("Order part zero")

        # Skip a line, effectively creating a bloank order part
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Escape) # modifier, delay
        QTest.keyEvent(QTest.Click, widget.controller_part.view, Qt.Key_F5, Qt.ShiftModifier) # modifier, delay
        app.processEvents()

        self._fill_order_part("Order part two")

        # Save will compress the blank order part
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()

        # Go up. We are now on top of a couple order parts list.
        QTest.keyEvent(QTest.Click, widget.controller_part.view, Qt.Key_Up) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, widget.controller_part.view, Qt.Key_Up) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, widget.controller_part.view, Qt.Key_Up) # modifier, delay
        app.processEvents()


        QTest.keyEvent(QTest.Click, widget.controller_part.view, Qt.Key_F8) # modifier, delay
        app.processEvents()

        # app.exec_()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()


        order = dao.order_dao.find_by_id(widget._current_order.order_id)
        assert len(order.parts) == 2



    def test_save_preserve_order(self):
        # python test_integration.py TestEditOrderParts.test_save_preserve_order

        app = self.app
        widget = self.widget
        mw = self.mw
        self._make_basic_preorder()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()

        m = widget.controller_part.view.model()
        widget.controller_part.view.setCurrentIndex( m.index(0,0))

        widget.controller_part.view.setFocus(Qt.OtherFocusReason)
        QTest.keyEvent(QTest.Click, widget.controller_part.view, Qt.Key_Up) # modifier, delay
        QTest.keyEvent(QTest.Click, widget.controller_part.view, Qt.Key_F5) # modifier, delay
        app.processEvents()

        self._fill_order_part("Order part zero")

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Escape) # modifier, delay
        QTest.keyEvent(QTest.Click, widget.controller_part.view, Qt.Key_F5, Qt.ShiftModifier) # modifier, delay
        app.processEvents()

        self._fill_order_part("Order part two")

        # app.exec_()

        # We'll save several times to give to dict a chance
        # to mess keys around

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()

        order = dao.order_dao.find_by_id(widget._current_order.order_id)
        self.assertEqual( "0Order part zero", order.parts[0].description)
        self.assertEqual( "0Order part two", order.parts[2].description)


        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()

        order = dao.order_dao.find_by_id(widget._current_order.order_id)
        self.assertEqual( "0Order part zero", order.parts[0].description)
        self.assertEqual( "0Order part two", order.parts[2].description)


    def test_save_preserve_operation_order2(self):
        order = self._make_order()
        order_id = order.order_id

        for i in range(10):
            operation = self._operation_dao.make()
            operation.production_file = order.parts[0].production_file[0]
            operation.description = "," + str(i+1)
            operation.operation_model = self.opdef_op
            operation.planned_hours = (i+10)*10
            operation.position = 11 - i
            session().add(operation)

        self._order_dao.recompute_position_labels(order)

        session().commit()

        descriptions = [op.description for op in order.parts[0].operations]

        mainlog.debug(order)
        self.widget._panel_visible = True
        self.widget.reset_order(order_id, overwrite=True)

        # Edit superficially
        self.widget.controller_operation.view.setFocus(Qt.OtherFocusReason)

        for i in range(5):
            QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_Down) # modifier, delay
            self.app.processEvents()

        # set on description
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_Right) # modifier, delay
        self.app.processEvents()

        # change the description
        QTest.keyClicks(self.app.focusWidget(), "Zulu")
        self.app.processEvents()
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_Enter) # modifier, delay
        self.app.processEvents()

        # Another one
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_Escape) # stop current editing
        self.app.processEvents()
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_Tab, Qt.ShiftModifier)
        self.app.processEvents()
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_Tab, Qt.ShiftModifier)
        self.app.processEvents()

        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_Down) # modifier, delay
        self.app.processEvents()
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_Down) # modifier, delay
        self.app.processEvents()
        QTest.keyClicks(self.app.focusWidget(), "Zulu")
        self.app.processEvents()
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_Enter) # modifier, delay
        self.app.processEvents()

        # Save
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        self.app.processEvents()


        mainlog.debug(descriptions)
        mainlog.debug([op.description for op in order.parts[0].operations])

        order = dao.order_dao.find_by_id(order_id)
        operations = order.parts[0].operations

        for i in range(1,len(descriptions)): # Skip the first one
            self.assertEqual(descriptions[i].split(',')[1], operations[i].description.split(',')[1])

        # self.app.exec_()


    def test_save_preserve_operation_order(self):
        # python test_integration.py TestEditOrderParts.test_save_preserve_order

        app = self.app
        widget = self.widget
        mw = self.mw
        self._make_basic_preorder()


        widget.controller_operation.view.setFocus(Qt.OtherFocusReason)
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_F5, Qt.ShiftModifier )
        app.processEvents()

        # self._encode_imputable_operation("Description1")
        self._encode_imputable_operation("Description2")

        self._fix_focus(widget, widget.controller_operation.view)

        mainlog.debug("Second row " * 10)
        self._encode_imputable_operation("Description3")

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()

        # Go at the end of the table

        widget.controller_operation.view.setFocus(Qt.OtherFocusReason)

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Down) # modifier, delay
        app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Down) # modifier, delay
        app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Down) # modifier, delay
        app.processEvents()

        # app.exec_()

        # Now we reverse the operations order

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_F6, Qt.ShiftModifier ) # modifier, delay
        app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_F6, Qt.ShiftModifier ) # modifier, delay
        app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Down) # modifier, delay
        app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Down) # modifier, delay
        app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_F6, Qt.ShiftModifier ) # modifier, delay
        app.processEvents()

        # app.exec_()

        # Save

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()


        # Check the operations order
        order = dao.order_dao.find_by_id(widget._current_order.order_id)
        mainlog.debug(order.parts[0].operations[0].description)
        mainlog.debug(order.parts[0].operations[1].description)
        mainlog.debug(order.parts[0].operations[2].description)

        assert "3" in order.parts[0].operations[0].description
        assert "2" in order.parts[0].operations[1].description
        assert "1" in order.parts[0].operations[2].description


    @Slot()
    def _lookup(self):
        QTest.keyEvent(QTest.Click, self.app.activeModalWidget(), Qt.Key_Enter)

    @Slot()
    def _accept_dialog(self):
        QTest.keyEvent(QTest.Click, self.app.activeModalWidget(), Qt.Key_Enter)

    @Slot()
    def _cancel_dialog(self):
        QTest.keyEvent(QTest.Click, self.app.activeModalWidget(), Qt.Key_Escape)

    def test_change_order_customer(self):
        customer2 = self._customer_dao.make("AAAA") # Name chosen so it happens first int he customer dialog
        self._customer_dao.save(customer2)

        app = self.app
        widget = self.widget
        mw = self.mw
        self._make_basic_preorder()


        self._encode_imputable_operation("Description2")
        self._encode_imputable_operation("Description3")

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()

        # Make sure the test is set up correctly
        preorder = self.order_dao.find_by_id_frozen(widget._current_order.order_id)
        assert preorder.customer_id == self.customer.customer_id

        # We're going to have a modal dialog for the new
        # customer name. So we prepare to click on it.

        timer = QTimer()
        timer.timeout.connect(self._lookup)
        timer.setSingleShot(True)
        timer.start(1000)

        widget.change_customer()
        # app.exec_() # Wait for the timer to shoot

        mainlog.debug("test_change_order_customer" * 10)
        mainlog.debug(app.focusWidget())

        widget.setFocus(Qt.OtherFocusReason) # This refocus was introduced for linux
        app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()

        mainlog.debug("test_change_order_customer")

        preorder = self.order_dao.find_by_id_frozen(widget._current_order.order_id)
        assert preorder.customer_id == customer2.customer_id

        mainlog.debug("test_change_order_customer")

        
        self.order_dao.delete(preorder.order_id)
        self.dao.customer_dao.delete(customer2.customer_id)



    def test_change_order_customer_cancelled(self):
        customer2 = self._customer_dao.make("AAAA") # Name chosen so it happens first int he customer dialog
        self._customer_dao.save(customer2)

        app = self.app
        widget = self.widget
        mw = self.mw
        self._make_basic_preorder()


        self._encode_imputable_operation("Description2")
        self._encode_imputable_operation("Description3")

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()

        # Make sure the test is set up correctly
        preorder = self.order_dao.find_by_id_frozen(widget._current_order.order_id)
        assert preorder.customer_id == self.customer.customer_id

        # We're going to have a modal dialog for the new
        # customer name. So we prepare to click on it.

        timer = QTimer()
        timer.timeout.connect(self._cancel_dialog)
        timer.setSingleShot(True)
        timer.start(1000) # Had 250, my linux seems to prefer 1000

        widget.change_customer() # blocks
        app.processEvents()
        # app.exec_() # Wait for the timer to shoot

        widget.setFocus(Qt.OtherFocusReason) # This refocus was introduced for linux

        for i in range(1000):
            app.processEvents() # Linux needs a break
        

        mainlog.debug("Pressing ctrl-S on this widget : {}".format(app.focusWidget()))
        # app.exec_()
        
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()

        preorder = self.order_dao.find_by_id_frozen(widget._current_order.order_id)
        assert preorder.customer_id == self.customer.customer_id

        self.order_dao.delete(preorder.order_id)
        self.dao.customer_dao.delete(customer2.customer_id)


    def test_delete_order_happy(self):
        app = self.app
        widget = self.widget
        mw = self.mw
        self._make_basic_preorder()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()

        deleted_order_id = widget._current_order.order_id

        # We're going to have a modal dialog for the new
        # customer name. So we prepare to click on it.

        timer = QTimer()
        timer.timeout.connect(self._accept_dialog)
        timer.setSingleShot(True)
        timer.start(250)

        widget.delete_button_clicked()

        assert not self.order_dao.find_by_id_frozen(deleted_order_id,resilient=True)


    def test_delete_unsaved_order(self):
        app = self.app
        widget = self.widget
        mw = self.mw
        # self._make_basic_preorder()
        widget.edit_new_order(self.customer.customer_id)

        self.prepare_to_click_dialog("delete_only_saved_order")
        widget.delete_button_clicked()
        assert self.dialog_test_result


    def _fill_preorder_print_dialog(self):
        d = self.app.activeModalWidget()
        d.message_text_area.setText("ZuluHeader")
        d.message_text_area_footer.setText("ZuluFooter")

        QTest.keyEvent(QTest.Click, d, Qt.Key_Enter)


    def test_print_preorder(self):
        # python test_integration.py TestEditOrderParts.test_print_preorder

        app = self.app
        widget = self.widget
        self._make_basic_preorder()
        self._encode_imputable_operation("Description2")
        self._encode_imputable_operation("Description3")
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()

        # We're going to have a modal dialog for the
        # preorder print. So we prepare to click on it.

        timer = QTimer()
        timer.timeout.connect(self._fill_preorder_print_dialog)
        timer.setSingleShot(True)
        timer.start(250)

        self.prepare_to_click_dialog("set_preorder_sent_state", 3)
        widget.preorderPrint()

        order = dao.order_dao.find_by_id(widget._current_order.order_id)
        self.assertEqual("ZuluHeader",order.preorder_print_note)
        self.assertEqual("ZuluFooter",order.preorder_print_note_footer)


    def test_delete_an_operation(self):
        # python test_integration.py TestEditOrderParts.test_delete_an_operation

        order = self._make_order()
        order_id = order.order_id

        app = self.app
        widget = self.widget
        widget.reset_order(order.order_id, overwrite=True)
        widget.refresh_action()

        session().close()

        widget.controller_operation.view.setFocus(Qt.OtherFocusReason)
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_F8) # modifier, delay
        app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        app.processEvents()

        order = dao.order_dao.find_by_id(order_id)
        self.assertTrue( not order.parts[0].operations)




if __name__ == "__main__":
    unittest.main()
