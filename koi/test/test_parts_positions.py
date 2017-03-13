import logging
import unittest
from unittest import skip

import datetime
from datetime import date
import hashlib
from collections import OrderedDict
from sqlalchemy.sql.expression import desc

# from koi.test.test_base import TestBase
# from koi.db_mapping import *
# from koi.dao import *
from koi.datalayer.letter_position import _letters_to_order, position_to_letters, label_to_key
# from koi.Configurator import mainlog



class TestPartsPosition(unittest.TestCase):

    def test_letter_columns(self):
        assert 'A' == position_to_letters(0)
        assert 'B' == position_to_letters(1)
        assert 'Z' == position_to_letters(25)

        assert 'AA' == position_to_letters(26)
        assert 'AB' == position_to_letters(27)
        assert 'AZ' == position_to_letters(51)

        assert 'BA' == position_to_letters(52)

    def test_ordering(self):

        assert _letters_to_order('A') == _letters_to_order('A')
        assert _letters_to_order('A') > _letters_to_order('B')
        assert _letters_to_order('A') > _letters_to_order('Z')

        assert _letters_to_order('A') > _letters_to_order('BB')
        assert _letters_to_order('A') > _letters_to_order('AB')

        assert _letters_to_order('A') > _letters_to_order('AA')
        assert _letters_to_order('A') > _letters_to_order('AAA')

        assert _letters_to_order('AA') > _letters_to_order('AB')
        assert _letters_to_order('AA') > _letters_to_order('BA')

        assert _letters_to_order('AA') > _letters_to_order('AAA')
        assert _letters_to_order('AA') > _letters_to_order('ZZZ')

        assert _letters_to_order('ZA') > _letters_to_order('ZB')

        try:
            _letters_to_order('AAAA')
            self.fail()
        except:
            pass

        assert label_to_key('1A') > label_to_key('1B')
        assert label_to_key('1A') > label_to_key('1Z')
        assert label_to_key('1A') > label_to_key('1AA')
        assert label_to_key('1A') < label_to_key('2A')
        assert label_to_key('1Z') < label_to_key('2A')
        assert label_to_key('1A') < label_to_key('2Z')

        assert label_to_key('1AA') < label_to_key('2A')
        assert label_to_key('1ZZ') < label_to_key('2A')

if __name__ == '__main__':
    unittest.main()
