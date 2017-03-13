import unittest

from koi.test.test_base import TestBase
from koi.Configurator import mainlog

from koi.translators import duration_to_s
from koi.date_parser import *

from koi.gui.ComboDelegate import DurationValidator
from PySide.QtGui import QValidator

class TestDurationParser(unittest.TestCase):

    def test_validator(self):
        v = DurationValidator()

        self.assertEqual( QValidator.Intermediate, v.validate("",0))
        self.assertEqual( QValidator.Intermediate, v.validate(":",0))
        self.assertEqual( QValidator.Acceptable, v.validate(":1",0))

        self.assertEqual( QValidator.Acceptable, v.validate("1",0))
        self.assertEqual( QValidator.Acceptable, v.validate("1:",0))
        self.assertEqual( QValidator.Acceptable, v.validate("1.",0))
        self.assertEqual( QValidator.Acceptable, v.validate("1m",0))
        self.assertEqual( QValidator.Acceptable, v.validate("1h",0))
        self.assertEqual( QValidator.Acceptable, v.validate("1h1m",0))
        self.assertEqual( QValidator.Acceptable, v.validate("1:1",0))

        self.assertEqual( QValidator.Intermediate, v.validate(".",0))
        self.assertEqual( QValidator.Acceptable, v.validate(".1",0))

        self.assertEqual( QValidator.Invalid, v.validate("x",0))
        self.assertEqual( QValidator.Invalid, v.validate("m",0))
        self.assertEqual( QValidator.Invalid, v.validate("m1",0))

    def test(self):

        parser = DurationParser()

        self.assertEqual(0,parser.parse('0'))

        try:
            self.assertEqual(0,parser.parse('.'))
            self.fail(". is not a valid duration")
        except ValueError as ex:
            pass
        self.assertEqual(.1,parser.parse('.1'))

        self.assertEqual(0,parser.parse(':'))
        self.assertEqual(1,parser.parse('1:')) # Allow to type unfinished strings

        self.assertEqual(1.0/60,parser.parse(':1'))
        self.assertEqual(1.0/60,parser.parse(':001'))
        self.assertEqual(10/60,parser.parse(':10'))
        self.assertEqual(1.0/60,parser.parse('1m'))
        self.assertEqual(1.0/60*0.5,parser.parse('0.5m'))
        self.assertEqual(1.0/60*2,parser.parse('2m'))

        self.assertEqual(1,parser.parse('1h'))
        self.assertEqual(1.0/2,parser.parse('0.5h'))
        self.assertEqual(2,parser.parse('2.h'))

        self.assertEqual(24,parser.parse('1j'))
        self.assertEqual(12,parser.parse('0.5j'))
        self.assertEqual(48,parser.parse('2.j'))

        self.assertEqual((24 + 1 + 1.0/60),parser.parse('1j1h1m'))

        self.assertEqual(2,parser.parse('2'))
        self.assertEqual(-2.5,parser.parse('-2.5'))

        self.assertEqual( 1.1, parser.parse('1h6'))
        self.assertEqual( 1.1, parser.parse('1h06'))
        self.assertEqual( 0.5, parser.parse('0h30'))
        self.assertEqual( 1.5, parser.parse('1h30'))
        self.assertEqual( 1.5, parser.parse('1H30')) # upper case H
        self.assertEqual( 1.5, parser.parse('1:30'))
        self.assertEqual( 11.25, parser.parse('11h15'))

        parser.parse('1h00')
        parser.parse('1h59')
        self.assertEqual( 11, parser.parse('1h600')) # A bit awkward isn't it ? But fixing itt is more complicated that it seems


    def test_accuracy_transfer(self):
        # Test convertion from string to string back and forth
        parser = DurationParser()

        # Had rounding issues here
        self.assertEqual('2.1',duration_to_s(parser.parse('2.1')))
        self.assertEqual('2.11',duration_to_s(parser.parse('2.11')))
        self.assertEqual('2.19',duration_to_s(parser.parse('2.19')))

        self.assertEqual('2.2',duration_to_s(parser.parse('2.2')))
        self.assertEqual('2.21',duration_to_s(parser.parse('2.21')))
        self.assertEqual('2.22',duration_to_s(parser.parse('2.22')))
        self.assertEqual('2.23',duration_to_s(parser.parse('2.23')))

        self.assertEqual('',duration_to_s(parser.parse('0')))
        self.assertEqual('',duration_to_s(parser.parse('0.0')))
        self.assertEqual('0',duration_to_s(parser.parse('0.001')))
        self.assertEqual('0.01',duration_to_s(parser.parse('0.009')))
        self.assertEqual('0.01',duration_to_s(parser.parse('0.014999999')))
        self.assertEqual('0.33',duration_to_s(1.0/3.0))
        self.assertEqual('0.67',duration_to_s(2.0/3.0))


        # So the duration can be expressed in a nice way
        # but they're always rendered as hours

        self.assertEqual('50.4',duration_to_s(parser.parse('2.1j')))
        self.assertEqual('0.04',duration_to_s(parser.parse('2.1m')))

    def test_errors(self):
        parser = DurationParser()
        try:
            parser.parse('2.2.2.j')
            self.fail()
        except ValueError as e:
            pass

class TestDateParser(unittest.TestCase):
    def test(self):

        d = DateTimeParser()
        self.assertEqual('2009-02-28 00:00:00', str(d.parse('28/2/2009')))

        self.assertEqual('2009-02-28 23:59:59', str(d.parse('28/2/2009 23:59:59')))
        self.assertEqual('2009-02-28 23:59:00', str(d.parse('28/2/2009 23:59')))
        self.assertEqual('2009-02-28 23:59:00', str(d.parse('28/2/2009 23:59:00')))
        self.assertEqual('2009-02-28 23:00:00', str(d.parse('28/2/2009 23:00')))
        self.assertEqual('2009-02-28 00:00:00', str(d.parse('28/2/2009 00:00')))
        self.assertEqual('2009-02-28 00:00:00', str(d.parse('28/2/2009 0:0')))

        self.assertFalse(d.parse(None))
        self.assertFalse(d.parse('28/2/2009 23'))
        self.assertFalse(d.parse('28/2/20X09 23:59:1'))
        self.assertFalse(d.parse('28/2/2009 23:59:A'))
        self.assertFalse(d.parse('28/2 23:59'))
        self.assertFalse(d.parse('29/2/2009 23:59:59'))
        self.assertFalse(d.parse('28/2/2009 24:59:59'))
        self.assertFalse(d.parse('28/2/2009 23:61:59'))
        self.assertFalse(d.parse('28/13/2009 23:59:59'))
        self.assertFalse(d.parse('x28/12/2009 23:59:59'))
        self.assertFalse(d.parse('32/2/2009 23:59:59'))
        self.assertEqual('2009-02-14 23:59:59',str(d.parse('    14/2/2009    23:59:59   ')))


class TestTimeParser(unittest.TestCase):
    def test(self):

        p = TimeParser( date(2012,10,12))

        self.assertEqual('2012-10-12 23:59:59',str(p.parse('    23:59:59   ')))
        self.assertEqual('2012-10-12 23:59:00',str(p.parse('    23:59:00   ')))
        self.assertEqual('2012-10-12 23:59:00',str(p.parse('    23:59:0   ')))
        self.assertEqual('2012-10-12 23:59:00',str(p.parse('    23:59   ')))
        self.assertEqual('2012-10-12 23:00:00',str(p.parse('    23h   ')))
        self.assertEqual('2012-10-12 23:00:00',str(p.parse('23')))

class TestFutureDateParser(unittest.TestCase):
    def test(self):
        p = FutureDateParser(date(2012,10,10))
        self.assertEqual(p.parse('1/12'), date(2012,12,1))
        self.assertEqual(p.parse('10/10'),date(2013,10,10))
        self.assertEqual(p.parse('1/1'),  date(2013,1,1))
        self.assertEqual(p.parse('29/2'),False) # bissextile


if __name__ == '__main__':
    unittest.main()
