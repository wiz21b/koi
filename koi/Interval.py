

class Interval(object):
    """ An inclusive, immutable interval. That is x belong to I iff x in [I.start,I.end]
    """

    def __init__(self, start, end):
        assert start
        assert end

        if start < end:
            self.start, self.end = start,end
        else:
            self.start, self.end = end, start

    def __eq__(self,i):
        return self.start == i.start and self.end == i.end

    def duration(self):
        return self.end - self.start

    def length(self):
        # This is fine for integer but might not work for other types.
        return self.end - self.start

    def contains(self,d):
        if isinstance(d,Interval):
            return self.contains(d.start) and self.contains(d.end)
        else:
            return self.start <= d <= self.end


    def intersects(self, i):
        return i.start <= self.end and i.end >= self.start

    def merge(self,i):
        if self.intersects(i):
            start = min(self.start, i.start)
            end = max(self.end, i.end)
            return Interval(start,end)
        else:
            return None

    def union(self,i):
        # FIXME Strange, very ill defined union
        if self.intersects(i):
            start = max(self.start, i.start)
            end = min(self.end, i.end)
            return Interval(start,end)
        else:
            return self

    def _sanitize(self,i):
        if i.length() > 0:
            return i
        else:
            return None

    def substract_from(self,i):

        if self.contains(i):
            return None

        if i.contains(self):
            i1 = self._sanitize(Interval(i.start,self.start))
            i2 = self._sanitize(Interval(self.end,i.end))

            if i1 and i2:
                return [i1,i2]
            elif i1:
                return [i1]
            elif i2:
                return [i2]
            else:
                return None # should not happen

        elif self.intersects(i):
            start = end = None
            if i.contains(self.start):
                return self._sanitize(Interval(i.start,self.start))
            elif i.contains(self.end):
                return self._sanitize(Interval(self.end,i.end))
            else:
                return None
        else:
            return None

    def __repr__(self):
        return "[{}-{}]".format(self.start,self.end)


class IntervalCollection(object):
    """ Ordered, disjoint intervals list.
    use .intervals to get the current list of intervals. It is maintained
    any time """

    def __init__(self, *intervals):
        self.intervals = []
        self.add_and_merge(intervals)

    def _sanitize(self):
        if len(self.intervals) < 2:
            return

        a = [ self.intervals[0] ]
        ndx_a = 0

        i = 1
        while i < len(self.intervals):
            interval = self.intervals[i]

            while len(a) > 0 and interval.intersects(a[-1]):
                interval = interval.merge(a.pop())

            a.append(interval)
            i += 1

        self.intervals= a


    def _add(self,interval):

        if len(self.intervals) == 0:
            self.intervals = [interval]
        else:

            for i in range(len(self.intervals)):
                if interval.start < self.intervals[i].start:
                    self.intervals.insert(i,interval)
                    return

            self.intervals.append(interval)


    def add_and_merge(self,i_in):
        if isinstance(i_in, list) or isinstance(i_in, tuple):
            for i in i_in:
                self._add(i)
        else:
            self._add(i_in)
        # print("add_and_merge._add => {}".format(self))
        self._sanitize()


    def intersects(self,i):
        for interval in intervals:
            if interval.intersects(i):
                return True
        return False


    def __eq__(self,other):
        return self.intervals == other.intervals

    def __repr__(self):
        return "{ " + ", ".join(map(str,self.intervals)) + " }"



if __name__ == '__main__':
    import unittest
    from unittest import skip

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

            ic = IntervalCollection(a,c,b)
            self.assertEqual(ic, IntervalCollection( Interval(9,16) ) )

            ic = IntervalCollection(b,a,c)
            self.assertEqual(ic, IntervalCollection( Interval(9,16) ) )
    unittest.main()
