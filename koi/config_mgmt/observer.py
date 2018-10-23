import enum
from datetime import date, datetime

# Based on code from https://stackoverflow.com/questions/22878220/looking-for-a-solution-to-detect-value-change-in-class-attribute-with-a-list-and

dbg_document = 0

class ChangeTracker:
    def __init__(self):
        self._dirty = False
        self._cache = dict()

    def set_dirty(self, d):
        self._dirty = d

    def is_dirty(self):
        return self._dirty

    def wrap_in_change_detector( self, obj : object):
        if obj is None or type(obj) in (str, int, float, date, datetime) or isinstance(obj,enum.Enum):
            return obj

        # so we can cache list and objects WARNING Only works because
        # the cache keeps the objects alive (read CPYthon
        # implementation detail : two objects at different times can
        # have the same id())
        key = id(obj)

        key_in_cache = key in self._cache

        if key_in_cache:
            # print("using cache for {}".format(key))
            return self._cache[key]

        # print("making change detector for {}".format(type(obj)))

        if isinstance( obj, ChangeDetector):
            assert obj._internals['change_tracker'] == self, "we have two concurrent change trackers !"
            return obj

            # key = id(obj._internals['observed'])

            # if key not in self._cache:
            #     self._cache[key] = obj._internals['observed']
            # return obj
        elif isinstance( obj, list):

            #print("wrapping list")
            c = list_observer( obj, self)
            self._cache[key] = c
            return c

        elif obj and isinstance( obj, object) and type(obj) not in (str, int, float, date, datetime):
            #print("Wrapping {} in a change detector".format(obj))

            # if key == 'document':
            #     dbg_document += 1
            #     print(dbg_document)
            #     if dbg_document == 30:
            #         import pdb; pdb.set_trace()

            # str is not wrapped  because if it is, then as a ChangeDetector instance,
            # it's not recognized anymore by PySide (which expects 'str' and not a
            # derivative of it). Remeber str, int and float are immutable in python.

            # Test on obj too because : isinstance( None, object) == True !!!
            # (but isinstance( None, A) == True !!!! even more bizarre)
            c = ChangeDetector( obj, self)
            self._cache[key] = c
            return c
        else:
            # no wrap necessary
            return obj

class ChangeDetector:

    # This class won't work under sqlalchemy because sqlalchemy
    # check the type of the objet it manages. You can alleviate
    # that problem by setting "enable_typechecks=False" on relationships
    # declaration in the SQLA mappings, but that's not that good
    # because this implies changing the datamodel by something it's
    # not concerned about.

    def __init__(self, observed : object, change_tracker : ChangeTracker):

        # print("{} wraps {} / {}".format( hex(id(self)), observed, type(observed)))
        assert change_tracker
        assert not isinstance( observed, ChangeDetector)

        self._internals = { 'observed' : observed,
                            'change_tracker' : change_tracker }

    def __getattr__(self, key):
        if key == '_internals':
            # print(key)
            return super().__getattribute__( key)
        elif key in ('__dict__','__str__'):
            return self._internals['observed'].__getattribute__(key)
        else:

            value = self._internals['observed'].__getattribute__( key)
            #return value

            # if isinstance( value, list):
            #     print( "Wrapping a list {}.{} in a change detector : {}".format( self, key,
            #         value ) )

            r = self._internals['change_tracker'].wrap_in_change_detector(value)

            # if r != value:
            #     print("wrapped field {}".format(key))
            #     if key == 'document':
            #         print("{} <> {}".format( type(r), type(value)))

            return r

    def __setattr__(self, key, value):
        if key != '_internals':
            # print("set attr {} := {}".format( key, value))
            self._internals['change_tracker'].set_dirty(True)
            return self._internals['observed'].__setattr__(key,value)
        else:
            return super().__setattr__( key, value)


    # Problem with magic methods (__xxx___) is that some
    # *may* be defined in class. So one can define them in this
    # ChangeDetector only if the class of the observed object
    # has them. Problem is that those methods can only
    # be decalred at class creation. Second problem is
    # if one of these method is defined here (but not one
    # the observed object), then the caller may change
    # its behaviour according to the existence of the
    # method...

    def __str__(self):
        return self._internals['observed'].__str__()

    # These four are requested by SQLAlchemy, even when you ask
    # it to disable typechecks on relationshids.

    def __call__(self, *args, **kwargs):
        return self._internals['observed'].__call__( *args, **kwargs)

    def __getitem__( self, key):
        return self._internals['observed'].__getitem__(key)

    def __contains__( self, key):
        return self._internals['observed'].__contains__(key)

    def __iter__( self):
        return self._internals['observed'].__iter__()


    # These might be necessary in the future. I leave them here
    # to remember.

    # def __dict__(self):
    #     return self._internals['observed'].__dict__()

    # def __dir__(self):
    #     return self._internals['observed'].__dir__()

    # def __set__(self, instance, value):
    #     return self._internals['observed'].__set__( instance, value)

    # def __get__(self, instance, owner):
    #     return self._internals['observed'].__get__( instance, owner)




class list_observer(list):
    """
    Send all changes to an observer.
    """

    def __init__(self, value, observer):
        list.__init__(self, value)

        self.observer = observer

    def index( self, obj):
        # This handles a tricky issue. That is :
        # 1. one picks an object o out of the list
        # 2. The list_observer sees that and
        # returns that object wrapped in a ChangeDetector : o'.
        # 3. one asks if o' is in the list, and it isn't because the
        # observer inherits from the original list.  So we check the
        # index with the origianl object instead of o'.
        if isinstance( obj, ChangeDetector):
            assert obj._internals['observed'] in self, "Missing {} (type: {}) \n in {}, \n types={}".format(obj._internals['observed'], type(obj._internals['observed']), self, [type(t) for t in self])
            return super().index( obj._internals['observed'])
        else:
            return super().index( obj)

    def __getitem__( self, key):
        #print("__getitem__ {}".format(key))
        return self.observer.wrap_in_change_detector( super().__getitem__(key))

    def __setitem__(self, key, value):
        #raise Exception("Set item unexpected")
        r = super().__setitem__( key, value)
        self.observer.set_dirty(True)
        return r

    def __delitem__(self, key):
        #raise Exception("delitem item unexpected")
        r = super().__delitem__( key, value)
        self.observer.set_dirty(True)
        return r

    def __setslice__(self, i, j, sequence):
        r = super().__setslice__( i, j, sequence)
        self.observer.set_dirty(True)
        return r

    def __delslice__(self, i, j):
        r = super().__delslice__( i, j)
        self.observer.set_dirty(True)
        return r

    def append(self, value):
        #raise Exception("append item unexpected")
        r = super().append( value)
        self.observer.set_dirty(True)
        return r

    def pop(self):
        r = super().pop()
        self.observer.set_dirty(True)
        return r

    def extend(self, value):
        #raise Exception("extend item unexpected")
        r = super().extend( value)
        self.observer.set_dirty(True)
        return r

    def insert(self, i, value):
        #raise Exception("insert item unexpected")
        r = super().insert( i, value)
        self.observer.set_dirty(True)
        return r

    def remove(self, element):
        r = super().extend( element)
        self.observer.set_dirty(True)
        return r

    def reverse(self):
        r = super().reverse()
        self.observer.set_dirty(True)
        return r

    def sort(self, cmpfunc=None):
        r = super().sort( cmpfunc)
        self.observer.set_dirty(True)
        return r


if __name__ == '__main__':

    class Foo:
        def __init__(self):
            self.z = "zero"
            self.l = [ 12 ]
            self.lrec = [ ]

    ct = ChangeTracker()
    inst = Foo()
    inst.lrec.append( Foo())
    f = ChangeDetector(inst, ct)

    assert not ct.is_dirty()
    f.z = "one"
    assert ct.is_dirty()

    ct.set_dirty(False)
    assert not ct.is_dirty()
    f.l[0]
    assert not ct.is_dirty()
    f.l[0] = 23
    assert ct.is_dirty()

    ct.set_dirty(False)
    f.lrec[0].l[0] = 23
    assert ct.is_dirty()
