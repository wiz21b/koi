import unittest
from koi.Interval import *

class TestInterval(unittest.TestCase):
    def test_merge(self):
        a = Interval(10,12)
        b = Interval(12,14)

        d = a.merge(b)

        self.assertEqual(d,Interval(10,14))
        self.assertEqual(a.substract_from(d)[0], Interval(12,14))
        self.assertEqual(b.substract_from(d)[0], Interval(10,12))
        self.assertEqual(a.substract_from(b.substract_from(d)[0]),None)

    def test_collection_add(self):
        a = Interval(10,12)
        b = Interval(12,14)

        ic = IntervalCollection()
        ic.add_and_merge(a)
        self.assertEqual(ic, IntervalCollection( a ) )
        ic.add_and_merge(a)
        self.assertEqual(ic, IntervalCollection( a ) )

    def test_collection_merge(self):
        a = Interval(10,12)
        b = Interval(12,14)
        c = Interval(14,16)

        self.assertNotEqual(a,b)

        ic = IntervalCollection(c,a)
        self.assertEqual(ic, IntervalCollection( Interval(10,12),Interval(14,16) ) )

        ic.add_and_merge(b)
        self.assertEqual(ic, IntervalCollection( Interval(10,16) ) )

    def test_collection_merge2(self):
        a = Interval(10,13)
        b = Interval(12,14)
        c = Interval(9,16)

        ic = IntervalCollection(c,a,b)
        self.assertEqual(ic, IntervalCollection( Interval(9,16) ) )

        ic = IntervalCollection(c,b,a)
        self.assertEqual(ic, IntervalCollection( Interval(9,16) ) )

        ic = IntervalCollection(a,c,b)
        self.assertEqual(ic, IntervalCollection( Interval(9,16) ) )

        ic = IntervalCollection(b,c,a)
        self.assertEqual(ic, IntervalCollection( Interval(9,16) ) )

        ic = IntervalCollection(b,a,c)
        self.assertEqual(ic, IntervalCollection( Interval(9,16) ) )

        ic = IntervalCollection(a,b,c)
        self.assertEqual(ic, IntervalCollection( Interval(9,16) ) )

    def test_collection_merge3(self):
        a = Interval(10,12)
        b = Interval(13,14)
        c = Interval(9,16)

        ic = IntervalCollection(c,a,b)
        self.assertEqual(ic, IntervalCollection( Interval(9,16) ) )

        ic = IntervalCollection(c,b,a)
        self.assertEqual(ic, IntervalCollection( Interval(9,16) ) )

        ic = IntervalCollection(a,c,b)
        self.assertEqual(ic, IntervalCollection( Interval(9,16) ) )

        ic = IntervalCollection(b,c,a)
        self.assertEqual(ic, IntervalCollection( Interval(9,16) ) )

        ic = IntervalCollection(b,a,c)
        self.assertEqual(ic, IntervalCollection( Interval(9,16) ) )

        ic = IntervalCollection(a,b,c)
        self.assertEqual(ic, IntervalCollection( Interval(9,16) ) )

if __name__ == '__main__':
    unittest.main()
