import unittest
import datetime

from PySide.QtGui import QApplication,QMainWindow, QDialogButtonBox
from PySide.QtTest import QTest
from PySide.QtCore import QTimer, Qt



from koi.test.test_base import TestBase
from koi.db_mapping import *
from koi.dao import *
from koi.EditTimeTracksDialog import EditTimeTracksDialog


class TestEditTimetracks(TestBase):

    @classmethod
    def setUpClass(cls):
        super(TestEditTimetracks,cls).setUpClass()
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        cls.app = app

        # cls.mw = QMainWindow()
        # cls.mw.setMinimumSize(1024,768)

        cls.widget = EditTimeTracksDialog(None, dao, date.today())

    @classmethod
    def tearDownClass(cls):
        cls.widget.close()
        # cls.app.exit()

    def setUp(self):
        super(TestEditTimetracks,self).setUp()
        #operation_definition_cache.reload()
        self._order = self._make_order()
        mainlog.debug("Accoutnig label {}".format(self._order.accounting_label))
        self.dao.order_dao.recompute_position_labels(self._order)
        session().commit()

        self.widget.show()
        QTest.qWaitForWindowShown(self.widget)
        self.app.processEvents()

    def tearDown(self):
        super(TestEditTimetracks,self).tearDown()
        self.widget.hide()
        self.app.processEvents()


    def _encode_imputable_operation(self,nb_hours = 2):

        mainlog.debug("_encode_imputable_operation")
        
        # print("_encode_imputable_operation")
        # # widget = self.widget
        # print("_encode_imputable_operation")

        # self.app.processEvents()
        # self.app.processEvents()

        # print("active window : {}".format(self.app.activeWindow()))
        # print("_encode_imputable_operation : {}".format(self.app.focusWidget()))

        widget = self.app.focusWidget()

        # If you get an assert on QWidget, it probably means that
        # no widget has the focus or, that the widget that has the
        # focus is not the one you think. So double check (for ex.
        # widget is not widget.controller.view)

        # Also, rememebr that when you start typing, an editor is created
        # and therefore, the widget of the editor gets the focus... So the
        # focused widget may have changed between calls to keyEvent !
        
        app = self.app
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_1) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_0) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_1) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_A) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter)
        app.processEvents()

        # Choose the first operation
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter)
        app.processEvents()


        # Work 2 hours on it.
        k = [Qt.Key_0,Qt.Key_1,Qt.Key_2,Qt.Key_3,Qt.Key_4,Qt.Key_5,Qt.Key_6,Qt.Key_7,Qt.Key_8,Qt.Key_9][nb_hours]
        QTest.keyEvent(QTest.Click, app.focusWidget(), k)
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter)
        app.processEvents()

        # Skip machine part
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter)
        app.processEvents()

    def _encode_imputable_on_order(self,nb_hours = 2):
        widget = self.widget
        app = self.app

        print("_encode_imputable_on_order")
        print(app.focusWidget())
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_1) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_0) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_1) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter)
        app.processEvents()

        # Choose the first operation

        print(app.focusWidget())
        print(app.activePopupWidget())
        
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter)
        app.processEvents()


        # Work 2 hours on it.
        k = [Qt.Key_0,Qt.Key_1,Qt.Key_2,Qt.Key_3,Qt.Key_4,Qt.Key_5,Qt.Key_6,Qt.Key_7,Qt.Key_8,Qt.Key_9][nb_hours]
        QTest.keyEvent(QTest.Click, app.focusWidget(), k)
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter)
        app.processEvents()

        # Skip machine part
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter)
        app.processEvents()

    def _encode_imputable_non_billable(self,nb_hours = 2):
        widget = self.widget
        app = self.app

        # Non billable have no identifier
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Tab)
        app.processEvents()

        # Choose the first operation
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Space) # activate combo box
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter)
        app.processEvents()

        # Work some hours on it.
        k = [Qt.Key_0,Qt.Key_1,Qt.Key_2,Qt.Key_3,Qt.Key_4,Qt.Key_5,Qt.Key_6,Qt.Key_7,Qt.Key_8,Qt.Key_9][nb_hours]
        QTest.keyEvent(QTest.Click, app.focusWidget(), k)
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter)
        app.processEvents()

        # Skip machine part
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter)
        app.processEvents()


    def test_encode_zero_timetracks(self):
        self._pg_locks("on start")
        app = self.app
        widget = self.widget
        widget.set_employee_and_date(self.employee.employee_id, date.today())
        widget.buttons.button(QDialogButtonBox.Ok).click()

        # Now we reopen the dialog and make sure our work still appears
        # there.

        widget.set_employee_and_date(self.employee.employee_id, date.today())

        self._pg_locks("after set employee and before show")
        widget.show()
        self._pg_locks("After second show")

        app.processEvents()


    def test_encode_on_different_dates(self):

        app = self.app
        widget = self.widget
        self._pg_locks("before init ")
        today = date.today()
        widget.set_employee_and_date(self.employee.employee_id, today)

        widget.show()

        # So there is a row in the table, but this row is just
        # the *empty* row we prepare for the user to encode somethign
        # in.
        self.assertEqual(None, widget.controller.model.objects[0])


        self._encode_imputable_operation(nb_hours = 9)
        widget.buttons.button(QDialogButtonBox.Ok).click()
        app.processEvents()


        # What I test is that two successive invocation of
        # the dialog for different dates don't accidentally
        # mix data

        yesterday = date.today() + timedelta(-1)
        widget.set_employee_and_date(self.employee.employee_id, yesterday)
        widget.show()
        widget.setFocus(Qt.OtherFocusReason)
        app.processEvents()

        self.assertEqual(None, widget.controller.model.objects[0])
        
        app.setActiveWindow(widget)
        app.processEvents()
        widget.controller.view.setFocus(Qt.OtherFocusReason)
        app.processEvents()

        print("* "*10)
        print(app.topLevelWidgets())
        print(widget)

        self._encode_imputable_operation(nb_hours = 8)

        # app.exec_()
        widget.buttons.button(QDialogButtonBox.Ok).click()

        
        # Now I check that what was saved is OK.

        tt = self.dao.timetrack_dao.all_work_for_employee_date_manual(self.employee.employee_id,today)
        self.assertEqual(9,tt[0].duration)

        tt = self.dao.timetrack_dao.all_work_for_employee_date_manual(self.employee.employee_id,yesterday)
        self.assertEqual( 1, len(tt))
        self.assertEqual(8,tt[0].duration)



    def test_encode_and_remove_and_encode(self):
        app = self.app
        widget = self.widget
        self._pg_locks("before init ")
        today = date.today()
        widget.set_employee_and_date(self.employee.employee_id, today)

        widget.controller.view.setFocus(Qt.OtherFocusReason)
        self._encode_imputable_operation(nb_hours = 1)
        widget.controller.view.setFocus(Qt.OtherFocusReason)
        self._encode_imputable_operation(nb_hours = 2)
        widget.controller.view.setFocus(Qt.OtherFocusReason)
        self._encode_imputable_operation(nb_hours = 4)
        app.processEvents()

        widget.buttons.button(QDialogButtonBox.Ok).click()
        app.processEvents()

        widget.show()
        widget.set_employee_and_date(self.employee.employee_id, date.today())


        self._fix_focus(widget, widget.controller.view) 

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_F8) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_F8) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_F8) # modifier, delay
        app.processEvents()

        widget.buttons.button(QDialogButtonBox.Ok).click()
        app.processEvents()

        tts = dao.timetrack_dao.all_work_for_employee_date(self.employee.employee_id,today)
        self.assertEqual(0.0, sum([tt.duration for tt in tts]))
        self.assertEqual(0,len(tts))

        widget.set_employee_and_date(self.employee.employee_id, today)
        widget.show()

        self._fix_focus(widget, widget.controller.view)
        
        self._encode_imputable_operation(nb_hours = 9)
        app.processEvents()

        widget.buttons.button(QDialogButtonBox.Ok).click()
        app.processEvents()

        tts = dao.timetrack_dao.all_work_for_employee_date(self.employee.employee_id,today)
        self.assertEqual(9.0, sum([tt.duration for tt in tts]))
        self.assertEqual(1,len(tts))

    def test_encode_and_remove(self):
        app = self.app
        widget = self.widget
        self._pg_locks("before init ")
        today = date.today()
        widget.set_employee_and_date(self.employee.employee_id, today)

        self._encode_imputable_operation(nb_hours = 1)
        self._encode_imputable_operation(nb_hours = 2)
        self._encode_imputable_operation(nb_hours = 4)
        app.processEvents()
        # app.exec_()

        widget.buttons.button(QDialogButtonBox.Ok).click()
        app.processEvents()

        tts = dao.timetrack_dao.all_work_for_employee_date(self.employee.employee_id,today)
        self.assertEqual(7.0, sum([tt.duration for tt in tts]))
        self.assertEqual(3,len(tts))

        self.assertEqual(7.0, dao.day_time_synthesis_dao.monthly_presence(self.employee,today.year,today.month))
        # Just for fun, we check presence on other montsh
        self.assertEqual(0, dao.day_time_synthesis_dao.monthly_presence(self.employee,today.year + 1,today.month))
        self.assertEqual(0, dao.day_time_synthesis_dao.monthly_presence(self.employee,today.year - 1,today.month))


        # Remove the first timetrack at this point there are three)

        widget.show()
        widget.set_employee_and_date(self.employee.employee_id, today)

        self._fix_focus(widget, widget.controller.view)
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_F8) # modifier, delay
        app.processEvents()

        widget.buttons.button(QDialogButtonBox.Ok).click()
        app.processEvents()

        tts = dao.timetrack_dao.all_work_for_employee_date(self.employee.employee_id,today)

        for a in tts:
            mainlog.debug(a)

        self.assertEqual(2,len(tts))
        self.assertEqual(2+4, sum([tt.duration for tt in tts]))

        self.assertEqual(2+4, dao.day_time_synthesis_dao.monthly_presence(self.employee,today.year,today.month))

        # Remove all timetracks

        widget.show()
        widget.set_employee_and_date(self.employee.employee_id, today)

        self._fix_focus(widget, widget.controller.view)
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_F8) # modifier, delay
        app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_F8) # modifier, delay
        app.processEvents()

        widget.buttons.button(QDialogButtonBox.Ok).click()
        app.processEvents()

        tts = dao.timetrack_dao.all_work_for_employee_date(self.employee.employee_id,today)
        self.assertEqual(0,len(tts))
        self.assertEqual(0, sum([tt.duration for tt in tts]))
        self.assertEqual(0, dao.day_time_synthesis_dao.monthly_presence(self.employee,today.year,today.month))


    def test_encode_and_remove_unbillable(self):
        app = self.app
        widget = self.widget
        self._pg_locks("before init ")
        today = date.today()
        widget.set_employee_and_date(self.employee.employee_id, today)

        self._fix_focus(widget, widget.controller.view)
        self._encode_imputable_non_billable(nb_hours = 1)
        self._encode_imputable_non_billable(nb_hours = 2)
        self._encode_imputable_non_billable(nb_hours = 4)
        app.processEvents()

        widget.buttons.button(QDialogButtonBox.Ok).click()
        app.processEvents()

        tts = dao.timetrack_dao.all_work_for_employee_date(self.employee.employee_id,today)
        self.assertEqual(7.0, sum([tt.duration for tt in tts]))
        self.assertEqual(3,len(tts))

        widget.show()
        widget.set_employee_and_date(self.employee.employee_id, date.today())

        self._fix_focus(widget, widget.controller.view)
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_F8) # modifier, delay
        app.processEvents()

        widget.buttons.button(QDialogButtonBox.Ok).click()
        app.processEvents()

        tts = dao.timetrack_dao.all_work_for_employee_date(self.employee.employee_id,today)
        self.assertEqual(6.0, sum([tt.duration for tt in tts]))
        self.assertEqual(2,len(tts))




    def test_two_timetracks_on_same_order(self):
        app = self.app
        widget = self.widget

        today = date.today()
        widget.set_employee_and_date(self.employee.employee_id, today)

        self._fix_focus(widget, widget.controller.view)
        self._encode_imputable_on_order(1)
        self._encode_imputable_on_order(2)
        app.processEvents()

        widget.buttons.button(QDialogButtonBox.Ok).click()
        widget.hide()

        # Again, but on another day

        yesterday = date.today() - timedelta(1)
        widget.set_employee_and_date(self.employee.employee_id, yesterday)
        widget.show()

        # app.exec_()

        print("1"*30)
        self._fix_focus(widget, widget.controller.view)
        self._fix_focus(widget, widget.controller.view)
        print("2"*30)
        print(app.focusWidget())
        
        self._encode_imputable_on_order(4)
        print("3"*30)
        self._fix_focus(widget, widget.controller.view)
        print("4"*30)
        self._encode_imputable_on_order(8)

        widget.buttons.button(QDialogButtonBox.Ok).click()
        self._pg_locks("after dialog ok ")

        # Now we check what we entered

        tts = dao.timetrack_dao.all_work_for_employee_date(self.employee.employee_id,today)
        self.assertEqual(3.0, sum([tt.duration for tt in tts]))
        self.assertEqual(2,len(tts))

        tts = dao.timetrack_dao.all_work_for_employee_date(self.employee.employee_id,yesterday)
        self.assertEqual(12.0, sum([tt.duration for tt in tts]))
        self.assertEqual(2,len(tts))


    def test_two_timetracks_on_same_non_billable(self):
        app = self.app
        widget = self.widget

        today = date.today()
        widget.set_employee_and_date(self.employee.employee_id, today)

        self._fix_focus(widget, widget.controller.view)
        self._encode_imputable_non_billable(1)
        self._encode_imputable_non_billable(2)
        widget.buttons.button(QDialogButtonBox.Ok).click()
        self._pg_locks("after dialog ok ")
        widget.hide()

        # Again, but on another day

        yesterday = date.today() - timedelta(1)
        widget.set_employee_and_date(self.employee.employee_id, yesterday)
        widget.show()

        self._fix_focus(widget, widget.controller.view)
        self._encode_imputable_non_billable(4)
        self._fix_focus(widget, widget.controller.view)
        self._encode_imputable_non_billable(8)
        widget.buttons.button(QDialogButtonBox.Ok).click()
        self._pg_locks("after dialog ok ")

        # Now we check what we entered

        tts = dao.timetrack_dao.all_work_for_employee_date(self.employee.employee_id,today)
        self.assertEqual(3.0, sum([tt.duration for tt in tts]))
        self.assertEqual(2,len(tts))

        tts = dao.timetrack_dao.all_work_for_employee_date(self.employee.employee_id,yesterday)
        self.assertEqual(12.0, sum([tt.duration for tt in tts]))
        self.assertEqual(2,len(tts))


    def test_encode_a_few_timetracks(self):

        # python test_integration.py TestEditTimetracks.test_create_order_and_report_on_order

        app = self.app
        widget = self.widget
        self._pg_locks("before init ")
        widget.set_employee_and_date(self.employee.employee_id, date.today())

        self._encode_imputable_operation(5)

        self._pg_locks("after encoding a row")

        widget.buttons.button(QDialogButtonBox.Ok).click()

        self._pg_locks("after OK click")

        # Now we check the time was actually reported

        session().refresh(self._order)
        self.assertEqual( 5.0, self._order.parts[0].total_hours)

        session().commit()
        self._pg_locks("after commit")

        # Now we reopen the dialog and make sure our work still appears
        # there.

        widget.set_employee_and_date(self.employee.employee_id, date.today())

        self._pg_locks("after set employee and before show")
        widget.show()
        self._pg_locks("After second show")

        app.processEvents()

        self._pg_locks("After process events")
        app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_F5, Qt.ShiftModifier) # modifier, delay
        app.processEvents()
        self._encode_imputable_operation()
        app.processEvents()

        widget.buttons.button(QDialogButtonBox.Ok).click()

        # app.exec_()

        self._pg_locks("when test finished")

    def test_mix_with_timetracks_managed_by_code(self):

        today = date.today()
        tt = dao.timetrack_dao.create(self.nb_task,self.employee,12,datetime.now(),today)
        tt.managed_by_code = True
        dao.timetrack_dao._recompute_presence_on_timetracks(self.employee.employee_id,today,[tt])
        session().commit()

        app = self.app
        widget = self.widget
        self._pg_locks("before init ")
        widget.set_employee_and_date(self.employee.employee_id, today)

        self._fix_focus(widget, widget.controller.view) 
        
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_F5, Qt.ShiftModifier) # modifier, delay
        app.processEvents()
        self._encode_imputable_operation(5)
        widget.buttons.button(QDialogButtonBox.Ok).click()

        tts = dao.timetrack_dao.all_work_for_employee_date(self.employee.employee_id,today)
        self.assertEqual(12.0 + 5.0, sum([tt.duration for tt in tts]))
        self.assertEqual(2,len(tts))

    def _click_order_inexistant_box(self):
        QTest.keyEvent(QTest.Click, self.app.activeModalWidget(), Qt.Key_Enter)
        self.test_sucess = True


    def test_encode_wrong_order_part_id(self):
        # python test_edit_timetracks.py TestEditTimetracks.test_encode_wrong_order_id
        app = self.app
        widget = self.widget
        today = date.today()
        widget.set_employee_and_date(self.employee.employee_id, today)
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_F5, Qt.ShiftModifier) # modifier, delay
        app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_9) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_9) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_9) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Z) # modifier, delay
        app.processEvents()

        timer = QTimer()
        timer.timeout.connect(self._click_order_inexistant_box)
        timer.setSingleShot(True)
        timer.start(250)
        self.test_sucess = False

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter)
        app.processEvents()

        assert self.test_sucess


    def test_encode_wrong_order_id(self):
        # python test_edit_timetracks.py TestEditTimetracks.test_encode_wrong_order_id
        app = self.app
        widget = self.widget
        today = date.today()
        widget.set_employee_and_date(self.employee.employee_id, today)
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_F5, Qt.ShiftModifier) # modifier, delay
        app.processEvents()

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_9) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_9) # modifier, delay
        app.processEvents()
        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_9) # modifier, delay
        app.processEvents()

        timer = QTimer()
        timer.timeout.connect(self._click_order_inexistant_box)
        timer.setSingleShot(True)
        timer.start(250)
        self.test_sucess = False

        QTest.keyEvent(QTest.Click, app.focusWidget(), Qt.Key_Enter)
        app.processEvents()

        assert self.test_sucess


if __name__ == "__main__":
    unittest.main()
