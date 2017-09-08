class InstrumentedObject:
    def __init__(self):
        self.clear_changes()

    def has_changed(self):
        return len(self._changed) > 0

    def clear_changes(self):
        object.__setattr__(self, "_changed", set())

    def __setattr__(self, name, value):
        if name != '_changed':

            if getattr(self, name) != value:
                # Checking if value is actually different is really important
                # for some behaviours. In particular the
                # 'position' tracking. But it's not 100% correct.
                # Indeed if attribute X with initial value 9 becomes 1 then 3 then 9
                # then we should note it didn't change...

                self._changed.add(name)

            object.__setattr__(self, name, value)
        else:
            raise Exception("Forbidden access to _change ! This field is reserved for change tracking")



class InstrumentedRelation(list):
    """ This list is ordered. This is very important
        when serializing deltas.

        Although it is ordered, the order is not applied
        on the objects of the list (by way of a position
        field). So the order is enforced for purely
        technical reasons.
    """

    def __init__(self):
        self.clear_changes()
        self._loaded = False

        return super(InstrumentedRelation,self).__init__(self)

    def lazy_load(self):
        # Redefine this if you wan to enable lazy loading.

        pass

    def _check_lazy_load(self):
        mainlog.debug("echk lazy load")
        if not self._loaded:
            mainlog.debug("lazy load")
            self.lazy_load()
            self._loaded = True

    def clear_changes(self):
        object.__setattr__(self, "_changed", False)
        object.__setattr__(self, "_deleted", set())
        object.__setattr__(self, "_added", set())

    def has_changed(self):
        return self._changed


    def __setitem__(self, ndx, value):
        self._check_lazy_load()
        r = super(InstrumentedRelation,self).__setitem__(ndx, value)

        if value in self._deleted:
            self._deleted.remove(value)
        elif value not in self._added:
            self._added.add(value)

        self._changed = True
        return r

    def __getitem__(self, key):
        self._check_lazy_load()
        return super().__getitem__(key)

    def __delitem__(self, key):
        self._check_lazy_load()
        if isinstance(key, slice):
            # print(key.start, key.stop, key.step)

            if key.step is not None:
                r = range(key.start, key.stop, key.step)
            else:
                r = range(key.start, key.stop)

            for j in r:
                # FIXME, looks like a bug in case of a real range
                self._del_one_item(j)
        else:
            self._del_one_item(key)


    def _del_one_item(self, ndx):
        mainlog.debug("del item ndx={}".format(ndx))

        d = self.__getitem__(ndx)
        r = super(InstrumentedRelation,self).__delitem__(ndx)

        if d not in self._deleted:
            mainlog.debug("del item - we'll track")

            if d in self._added:
                self._added.remove(d)
            else:
                mainlog.debug("del item - we have a track !")
                self._deleted.add(d) # Therefore d won't be GC'ed as one could expect !!!
        self._changed = True
        return r

    def append(self, value):
        self._check_lazy_load()

        if value in self:
            raise Exception("The relation works as a set to prevent doubles. And you're trying to add a double...")
        r = super(InstrumentedRelation,self).append(value)
        self._added.add(value) # _added is a set => this will work if the same item is added,removed,added again.
        self._changed = True
        return r

    def insert(self, ndx, value):
        self._check_lazy_load()

        if value in self:
            raise Exception("This value is already in the list")

        r = super(InstrumentedRelation,self).insert(ndx, value) # Doesn't seem to use __setitem__ :(
        self._added.add(value)
        self._changed = True


    def __hash__(self):
        self._check_lazy_load()

        # BIG WARNING ! This object is mutable so hashing makes normally
        # no sense here. However, sometimes I put this list into
        # the key of a dict => I make it hashable
        return id(self)

    def __eq__(self,other):
        return id(self) == id(other)




class InstrumentedOrderedRelation(InstrumentedRelation):
    """ Collection of objects which we assume have a position field denoting their order.

    If you need to swap 2 items in the list, don't use a,b = b,a because
    it will trigger a situation where the same value appears twice
    in the array, which is forbidden. Use the swap method for that.
    """

    def __init__(self):
        super(InstrumentedOrderedRelation, self).__init__()

    def _reset_positions(self):
        pos = 1
        for item in self:
            if item.position != pos:
                item.position = pos
            pos += 1


    def swap( self, ndx1, ndx2):

        if ndx1 > ndx2:
            ndx1, ndx2 = ndx2, ndx1

        v1, v2 = self[ndx1], self[ndx2]

        # The whole idea is to make sure the array never contains
        # twice the same value at the same time. that's why we
        # del first.

        del self[ndx2] # I think this won't trigger insert or append, so no reset_position
        del self[ndx1]

        super(InstrumentedOrderedRelation,self).insert(ndx1, v2)
        super(InstrumentedOrderedRelation,self).insert(ndx2, v1)
        self._reset_positions()


    def __setitem__(self, ndx, value):
        super(InstrumentedOrderedRelation,self).__setitem__(ndx, value)

        # I do a full reset because I think in practice it will
        # not actually affect objects (see optimisation in change
        # tracked objects). The full reset has the advantage that
        # it is damn simple to code, so less error prone.
        # I think this way of doing things is competitive when then
        # number of items with a position is low (say < 20)

        self._reset_position()


    def insert(self, ndx, value):
        super(InstrumentedOrderedRelation,self).insert(ndx, value) # Doesn't seem to use __setitem__ :(
        self._reset_positions()

    def append(self, value):
        super(InstrumentedOrderedRelation,self).append(value) # Doesn't seem to use __setitem__ :(
        self._reset_positions()





import collections

class CheckedList(list, collections.MutableSequence):
    def _check_lazy_load(self):
        mainlog.debug("echk lazy load")
        if not self._loaded:
            mainlog.debug("lazy load")
            self.lazy_load()
            self._loaded = True

    def lazy_load(self):
        raise NotImplementedError()

    def __init__(self, iterator_arg=None):
        self._loaded = False
        if not iterator_arg is None:
            self.extend(iterator_arg) # This validates the arguments...

    def __getitem__(self, key):
        self._check_lazy_load()
        return super().__getitem__(key)

    def insert(self, i, v):
        self._check_lazy_load()
        return super(CheckedList, self).insert(i, v)

    def append(self, v):
        self._check_lazy_load()
        return super(CheckedList, self).append(v)

    def extend(self, t):
        self._check_lazy_load()
        return super(CheckedList, self).extend(t)

    def __add__(self, t): # This is for something like `CheckedList(validator, [1, 2, 3]) + list([4, 5, 6])`...
        self._check_lazy_load()
        return super(CheckedList, self).__add__(t)

    def __iadd__(self, t): # This is for something like `l = CheckedList(validator); l += [1, 2, 3]`
        self._check_lazy_load()
        return super(CheckedList, self).__iadd__(t)

    def __setitem__(self, i, v):
        self._check_lazy_load()
        if isinstance(i, slice):
            return super(CheckedList, self).__setitem__(i, v) # Extended slice...
        else:
            return super(CheckedList, self).__setitem__(i, v)

    def __delitem__(self, key):
        self._check_lazy_load()
        return super().__getitem__(key)

    def __setslice__(self, i, j, t): # NOTE: extended slices use __setitem__, passing in a tuple for i
        self._check_lazy_load()
        return super(CheckedList, self).__setslice__(i, j, t)


class TestArray(CheckedList):
    def __init__(self):
        super().__init__()

    def lazy_load(self):
        value=[1,2,4]
        mainlog.debug("Lazy load")

        super(CheckedList, self).__delitem__(slice( self.__len__()))
        super(CheckedList, self).extend(value)

        # for ndx in range(len(value)):
        #     mainlog.debug("{} -> {}".format(ndx, value[ndx]))
        #     r = super(CheckedList, self).__setitem__(ndx, value[ndx])


class MissingAttribute:
    def __getattr__(self, key):
        print("Missing attribute {}".format(key))
        self.__setattr__(key, 123)

if __name__ == '__main__':
    import logging
    global mainlog
    mainlog = logging.getLogger()
    ch = logging.StreamHandler()
    mainlog.addHandler(ch)
    mainlog.setLevel(logging.DEBUG)
    mainlog.debug("logging")
    a = TestArray()
    a[0] = 13
    mainlog.debug("logging-2")
    assert a[0] == 13
    assert a[1] == 2
    assert a[0] == 13

    a = MissingAttribute()
    print(a.test)
    print(a.test)
