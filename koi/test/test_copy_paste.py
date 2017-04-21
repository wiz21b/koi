import unittest

from PySide.QtGui import QApplication,QMainWindow,QTabWidget
from PySide.QtTest import QTest
from PySide.QtCore import Qt,QTimer,Slot

from koi.test.test_base import TestBase
from koi.db_mapping import *
from koi.dao import *
from koi.server.server import ClockServer,ServerException
from koi.EditOrderParts import EditOrderPartsWidget,operation_definition_cache
from koi.OrderOverview import OrderOverviewWidget



class TestCopyPaste(TestBase):

    @classmethod
    def setUpClass(cls):
        super(TestCopyPaste,cls).setUpClass()

        # operation_definition_cache.refresh()

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
            # Fix issues with combo box that gets cleared too fast
            app.setEffectEnabled(Qt.UI_AnimateCombo, False)
            cls.app = app

        cls.mw = QMainWindow()
        cls.mw.setMinimumSize(1024,768)
        cls.edit_order_widget = EditOrderPartsWidget(None,None,True,cls.remote_documents_service)
        cls.edit_order_widget._show_blank_order( cls.customer.customer_id)

        # -TRACE-
        cls.order_overview_widget = OrderOverviewWidget(None,None,
                                                        None,
                                                        True)
        cls.stack = QTabWidget(None)
        cls.stack.addTab(cls.edit_order_widget, "Edit order")
        # -TRACE-
        cls.stack.addTab(cls.order_overview_widget, "Orders overview")

        cls.mw.setCentralWidget(cls.stack)
        cls.mw.show()
        QTest.qWaitForWindowShown(cls.mw)
        cls.app.processEvents()

    @classmethod
    def tearDownClass(cls):

        cls.mw.close()
        cls.edit_order_widget.close()
        cls.order_overview_widget.close()
        # cls.mw.setCentralWidget(None)
        cls.app.processEvents()
        #
        # cls.edit_order_widget.deleteLater()
        # cls.order_overview_widget.deleteLater()
        # cls.mw.deleteLater()
        # cls.app.processEvents()
        cls.app.closeAllWindows()


    def setUp(self):
        super(TestCopyPaste,self).setUp()
        # operation_definition_cache.refresh()
        # self.edit_order_widget._show_blank_order( self.customer.customer_id)
        #exit()

    def test_copy_paste_from_order_overview_to_order_edit(self):
        order = self._make_order() # An order with one part
        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 2"
        order_part.notes = "Notes 2"
        order_part.position = 2
        self._order_part_dao.save(order_part)
        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 3"
        order_part.notes = "Notes 3"
        order_part.position = 3
        self._order_part_dao.save(order_part)

        self._order_dao.change_order_state(order.order_id,OrderStatusType.order_ready_for_production)
        # self._order_dao.recompute_position_labels(order)

        ops = self.dao.operation_dao.operations_for_order_parts_frozen([1011,1014,1013])
        assert ops[1011]
        assert 1013 not in ops
        assert 1014 not in ops

        self.stack.setCurrentWidget(self.order_overview_widget)
        # self.order_overview_widget.month_today()
        self.order_overview_widget.refresh_action()
        self.order_overview_widget.retake_focus()

        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_A, Qt.ControlModifier ) # modifier, delay
        self.app.processEvents()

        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_C, Qt.ControlModifier ) # modifier, delay
        self.app.processEvents()

        # Now that we have copied, we'd like to paste !

        self.stack.setCurrentWidget(self.edit_order_widget)
        self.edit_order_widget.edit_new_order(self.customer.customer_id)
        self.edit_order_widget.controller_part.view.setFocus(Qt.OtherFocusReason)


        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_V, Qt.ControlModifier ) # modifier, delay
        self.app.processEvents()

        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        self.app.processEvents()


        order = self.order_dao.find_by_id(order.order_id)
        self.assertEqual(3,len(order.parts))
        self.assertEqual(1,len(order.parts[0].operations))
        self.assertEqual(0,len(order.parts[1].operations))

        self.assertEqual(u"Notes 2",order.parts[1].notes)
        self.assertEqual(u"Notes 3", order.parts[2].notes)

    #@unittest.skip("memory leak tracing")
    def test_copy_paste_operations_to_new_part(self):
        order = self._make_order()
        order_part = order.parts[0]
        order_part.notes = "A note"

        pf = order_part.production_file[0]

        operation = self._operation_dao.make()
        operation.position = 1
        operation.production_file = pf
        operation.description = "Alpha"
        operation.operation_model = self.opdef_op
        operation.planned_hours = 1
        session().add(operation)

        operation = self._operation_dao.make()
        operation.position = 2
        operation.production_file = pf
        operation.description = "Beta"
        operation.operation_model = self.opdef_op
        operation.planned_hours = 2
        session().add(operation)
        session().commit()


        self.edit_order_widget.reset_order(order.order_id, overwrite=True)
        self.edit_order_widget.refresh_action() # The panel is outside the panel manager => I force the refresh

        # Copy the operations of this order part
        
        self.edit_order_widget.controller_operation.view.setFocus(Qt.OtherFocusReason)


        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_A, Qt.ControlModifier ) # modifier, delay
        self.app.processEvents()

        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_C, Qt.ControlModifier ) # modifier, delay
        self.app.processEvents()



        # Add a new order part
        
        self.edit_order_widget.controller_part.view.setFocus(Qt.OtherFocusReason)

        QTest.keyEvent(QTest.Click, self.edit_order_widget.controller_part.view, Qt.Key_F5, Qt.ShiftModifier) # modifier, delay
        self.app.processEvents()

        QTest.keyClicks(self.app.focusWidget(), "O") # Start edit
        self.app.processEvents()
        QTest.keyClicks(self.app.focusWidget(), "rder part tWO") # complete edit
        self.app.processEvents()
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_Enter) # modifier, delay
        self.app.processEvents()

        # quantity
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_1) # modifier, delay
        self.app.processEvents()
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_Enter) # modifier, delay
        self.app.processEvents()


        # skip deadline
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_Tab) # modifier, delay
        self.app.processEvents()

        # Price
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_1) # modifier, delay
        self.app.processEvents()
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_1) # modifier, delay
        self.app.processEvents()
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_1) # modifier, delay
        self.app.processEvents()


        
        # Now paste operations
        
        self.edit_order_widget.controller_operation.view.setFocus(Qt.OtherFocusReason)
        # self.app.exec_()

        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_V, Qt.ControlModifier ) # modifier, delay
        self.app.processEvents()

        #self.app.exec_()

        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        self.app.processEvents()

        order = session().query(Order).filter(Order.order_id == order.order_id).one()


        for op in order.parts[1].operations:
            mainlog.debug(op)

        # self.app.exec_()
        
        assert "desc" in order.parts[1].operations[0].description

    #@unittest.skip("memory leak tracing")
    def test_copy_paste_from_order_edit_to_order_edit(self):
        order = self._make_order()
        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 2"
        order_part.notes = "Notes 2"
        order_part.position = 2
        self._order_part_dao.save(order_part)
        order_part = self._order_part_dao.make(order)
        order_part.description = u"Part 3"
        order_part.notes = "Notes 3"
        order_part.position = 3
        self._order_part_dao.save(order_part)

        self._order_dao.change_order_state(order.order_id,OrderStatusType.order_ready_for_production)
        # self._order_dao.recompute_position_labels(order)
        session().commit()

        mainlog.debug("About to edit {} - {}".format(order.order_id, order.state))
        self.edit_order_widget.reset_order(order.order_id, overwrite=True)
        self.edit_order_widget.refresh_action() # The panel is outside the panel manager => I force the refresh


        # Now we copy

        self.stack.setCurrentWidget(self.edit_order_widget)
        self.edit_order_widget.controller_part.view.setFocus(Qt.OtherFocusReason)

        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_A, Qt.ControlModifier ) # modifier, delay
        self.app.processEvents()

        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_C, Qt.ControlModifier ) # modifier, delay
        self.app.processEvents()


        # Now that we have copied, we'd like to paste !

        order = self._make_order()
        order_part = self._order_part_dao.make(order)
        order_part.description = u"ZuuPart 2"
        order_part.position = 2
        self._order_part_dao.save(order_part)
        order_part = self._order_part_dao.make(order)
        order_part.description = u"ZuuPart 3"
        order_part.position = 3
        self._order_part_dao.save(order_part)


        self.stack.setCurrentWidget(self.edit_order_widget)
        self.edit_order_widget.reset_order(order.order_id, overwrite=True)
        self.edit_order_widget.refresh_action() # The panel is outside the panel manager => I force the refresh
        #self.edit_order_widget.controller_part.view.setFocus(Qt.OtherFocusReason)


        # PAste
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_V, Qt.ControlModifier ) # modifier, delay
        self.app.processEvents()

        # Save
        QTest.keyEvent(QTest.Click, self.app.focusWidget(), Qt.Key_S, Qt.ControlModifier ) # modifier, delay
        self.app.processEvents()

        # self.app.exec_()

        order = self.order_dao.find_by_id(order.order_id)
        self.assertEqual(6,len(order.parts))
        self.assertEqual(u"Part 3",order.parts[2].description)
        self.assertEqual(u"Notes 3",order.parts[2].notes)
        self.assertEqual(u"Part 2",order.parts[1].description)
        self.assertEqual(u"Notes 2",order.parts[1].notes)
        self.assertEqual(0,len(order.parts[1].operations))
        self.assertEqual(1,len(order.parts[0].operations))

if __name__ == "__main__":
    unittest.main()
