""" the idea is :

SQLA -> dict -> Json                  ---network---> json -> dict -> change tracker object
                                                     ... making changes tracked by the change tracker ...
SQLA <- apply changes <- dict <- json <---network--- json <- dict <- change tracker object

and then

change_tracking_dto -> serialized delta -> Json ---network---> deserialize delta and apply to SQLA

"""
__author__ = 'stc'

from sqlalchemy.orm.properties import ColumnProperty
from sqlalchemy.inspection import inspect
from sqlalchemy.orm.collections import InstrumentedList, InstrumentedSet, InstrumentedDict

from koi.base_logging import mainlog
from koi.datalayer.database_session import session

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
        return super(InstrumentedRelation,self).__init__(self)

    def clear_changes(self):
        object.__setattr__(self, "_changed", False)
        object.__setattr__(self, "_deleted", set())
        object.__setattr__(self, "_added", set())

    def has_changed(self):
        return self._changed


    def __setitem__(self, ndx, value):
        r = super(InstrumentedRelation,self).__setitem__(ndx, value)

        if d in self._deleted:
            self._deleted.remove(d)
        elif d not in self._added:
            self._added.add(d)

        self._changed = True
        return r

    def __delitem__(self, key):
        if isinstance(key, slice):
            # print(key.start, key.stop, key.step)

            if key.step is not None:
                r = range(key.start, key.stop, key.step)
            else:
                r = range(key.start, key.stop)

            for j in r:
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
        if value in self:
            raise Exception("The relation works as a set to prevent doubles. And you're trying to add a double...")
        r = super(InstrumentedRelation,self).append(value)
        self._added.add(value) # _added is a set => this will work if the same item is added,removed,added again.
        self._changed = True
        return r

    def insert(self, ndx, value):
        if value in self:
            raise Exception("This value is already in the list")

        r = super(InstrumentedRelation,self).insert(ndx, value) # Doesn't seem to use __setitem__ :(
        self._added.add(value)
        self._changed = True


    def __hash__(self):
        # BIG WARNING ! This object is mutable so hashing makes normally
        # no sense here. However, sometimes I put this list into
        # the key of a dict => I make it hashable
        return id(self)

    def __eq__(self,a):
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

attribute_analysis_cache = dict()

def attribute_analysis(model):
    global attribute_analysis_cache

    if model not in attribute_analysis_cache:
        mainlog.debug("Analysing model {}".format(model))
        # Warning ! Some column properties are read only !
        fnames = [prop.key for prop in inspect(model).iterate_properties
                  if isinstance(prop, ColumnProperty)]

        single_rnames = []
        rnames = []
        for key, relation in inspect(model).relationships.items():
            if relation.uselist == False:
                single_rnames.append(key)
            else:
                rnames.append(key)

        # Order is important to rebuild composite keys (I think, not tested so far.
        # See SQLA comment for query.get operation :
        # http://docs.sqlalchemy.org/en/rel_1_0/orm/query.html#sqlalchemy.orm.query.Query.get )
        knames = [key.name for key in inspect(model).primary_key]

        mainlog.debug("For model {}, I have these attributes : keys={}, fields={}".format(model, knames, fnames))

        attribute_analysis_cache[model] = (fnames, rnames, single_rnames, knames)

    return attribute_analysis_cache[model]


def make_change_tracking_dto(model, obj=None, recursive=set(), additional_fields = dict()):
    """ Build a DTO corresponding to a model. If an object is passed, it
    is assumed that this object is an instance of the model and the
    object's fields are copied into the DTO, maybe recursively.

    The goal of this method is in fact to copy a SQLA object into a DTO.
    That DTO will have intelligent change tracking (i.e. know what
    object was added/removed/changed in a relation or if a field of
    the object was changed or not).

    :param model: The model (class) of the object we want to build a DTO of.
    :param obj: If given, its fields will be copied in the DTO (optinally recursively)
    :param recursive: If given, says to follow the children of the object.
    :param additional_fields: Deprecated.
    :return:
    """
    assert model

    if isinstance( obj, list):
        return [ make_change_tracking_dto(model, one_obj, recursive, additional_fields) for one_obj in obj]

    mainlog.debug("make_change_tracking_dto : model={}, obj={}".format(model, obj))
    fnames, rnames, single_rnames, knames = attribute_analysis(model)

    if obj is not None:
        fvalues = [getattr(obj,fname) for fname in fnames]
    else:
        fvalues = [None] * len(fnames)

    rnames = []
    rclasses = []

    if recursive:
        mainlog.debug("Recursive set is {}".format(str(recursive)))
        for relation_name,relation in inspect(model).relationships.items():
            rnames.append(relation_name)

            mainlog.debug("Relation {} of type {}".format(relation_name, type(relation)))
            if not relation.uselist:
                mainlog.debug("relation doesn't use list")
                if obj is not None:
                    rclasses.append( getattr(obj,relation_name) )
                else:
                    rclasses.append( None)
            elif hasattr(relation.mapper.class_, 'position'):
                rclasses.append(InstrumentedOrderedRelation())
            else:
                relation_item_model = getattr(model, relation_name).property.mapper.class_
                container = InstrumentedRelation()
                rclasses.append( container)

                if obj:
                    mainlog.debug("For relation {}, relation_item_model is {} of type {}. It has {} items.".format(
                        relation_name, relation_item_model, type(relation_item_model), len(getattr(obj, relation_name))))

                    if type(recursive) == set and (relation_item_model in recursive):
                        mainlog.debug("Going recursive")
                        shortened_recursion = recursive - {relation_item_model}
                        for item in getattr(obj, relation_name):
                            container.append( make_change_tracking_dto( relation_item_model, item, recursive=shortened_recursion))
                        container.clear_changes()

    d = dict(zip(fnames  + rnames + [k for k in additional_fields.keys()],
                 fvalues + rclasses + [v for v in additional_fields.values()]))
    d['__model__'] = model

    # We inherit from instrumented object
    res = type("DTO_"+model.__name__, (InstrumentedObject,), d)()

    assert not res.has_changed(), "Object created here should be clean"
    return res


class ChangeTracker:
    def __init__(self, sqla_declarative_base):
        self._field_names_cache = dict()

        # Preload the cache
        self._mapped_classes = dict()

        for klass in self._find_subclasses(sqla_declarative_base):
            self._attributes_names(klass)
            self._mapped_classes[klass.__name__] = klass


    def _find_subclasses(self, cls):
        results = []
        for sc in cls.__subclasses__():
            results.append(sc)
        return results


    def _attributes_names(self, model):
        """
        :param model:
        :return: names of the fields (ColumnProperties)
                 names of the array/set base relationships
                 names of uselist=false relationshipe
                 names of the key fields
        """
        # We use a cache for an obvious performance improvement

        if model not in self._field_names_cache:
            self._field_names_cache[model] = attribute_analysis(model)

        return self._field_names_cache[model]


    # def send_changes_for_dto(self, dto):
    #
    #     delta = self.serialize_delta(dto)
    #     # network send
    #
    #     # server part
    #     self._apply_delta_on_database_objects_helper(delta)
    #     self._update_delta_with_sqla_keys_helper()
    #     session().commit()
    #
    #     # back from the server
    #     self.copy_delta_pk_in_dto_helper()
    #     self.clear_changes_recursively()


    def make_change_tracking_dto(self, model):
        assert model
        return make_change_tracking_dto(model, obj=None)



    def has_changed_recursive(self, inst):
        model = inst.__model__

        fnames, rnames, single_rnames, knames = self._attributes_names(model)

        if inst._changed:
            return True

        for n in single_rnames:
            relation = getattr(inst,n)
            if relation:
                return self.has_changed_recursive(relation)

        for n in rnames:
            if getattr(inst,n)._changed:
                return True
            else:
                for item in getattr(inst,n):
                    return self.has_changed_recursive(item)


    def clear_changes_recursively(self, inst):
        model = inst.__model__

        fnames, rnames, single_rnames, knames = self._attributes_names(model)

        inst.clear_changes()

        for n in single_rnames:
            relation = getattr(inst,n)

            if relation:
                # FIXME relation itself not clear_changed
                self.clear_changes_recursively(relation)

        for n in rnames:
            relation = getattr(inst,n)

            if relation:
                relation.clear_changes()
                for item in relation:
                    self.clear_changes_recursively(item)

    def _has_primary_key_set(self, knames, d):
        for key in knames:
            if key in d and d[key]:
                return True
                break
        return False


    def apply_delta_on_database_objects(self, deltas):
        for delta in deltas:
            self._apply_delta_on_database_objects_helper(delta)


    def _apply_delta_on_database_objects_helper(self, d):

        global session

        # mainlog.debug("apply_delta_on_database_objects : data are {}".format(d))
        # mainlog.debug("apply_delta_on_database_objects : model is {}".format(model))
        fnames, rnames, single_rnames, knames = self._attributes_names(self._mapped_classes[ d['__model__']])


        # Does the delta contains objects which have set keys ?
        # (those objects need update rather than creation)
        has_set_pk = self._has_primary_key_set(knames, d)
        model = self._mapped_classes[d['__model__']]

        if has_set_pk:
            key = tuple( [d[key] for key in knames])
            obj = session().query(model).get(key)
        else:
            obj = model()
            session().add(obj)

        # Copy changes on fields
        for n in fnames:
            if n in d:
                setattr( obj, n, d[n])

        # Will be used when returning keys in delta data.
        d['__sqla_obj__'] = obj

        for key, value in d.items():
            if key in single_rnames:
                item = value['__items__'][0]
                setattr(obj, key, self._apply_delta_on_database_objects_helper(item))
            elif key in rnames:
                # mainlog.debug("relation {} value = {}".format(key, value))
                rel_items = value['__items__']

                obj_rel = getattr(obj, key)
                for item in rel_items:
                    sub_obj = self._apply_delta_on_database_objects_helper(item)
                    if sub_obj not in obj_rel:
                        obj_rel.append(sub_obj)

        return obj


    def update_delta_with_sqla_keys(self, deltas):
        key_track = dict()
        for delta in deltas:
            self._update_delta_with_sqla_keys_helper(delta, key_track)
        return key_track


    def _update_delta_with_sqla_keys_helper(self, d, key_track):

        # mainlog.debug(d)

        sqla_inst = d['__sqla_obj__']
        del d['__sqla_obj__'] # That won't be necessary anymore
        model = type(sqla_inst)

        fnames, rnames, single_rnames, knames = self._attributes_names(model)
        has_set_pk = self._has_primary_key_set(knames, d)

        if not has_set_pk:
            # Copying keynames avoids us to memorize the object type here and there
            # That's a bit lazy because it's not a very efficient way to transmit data.

            key_track[ d['__object_id__']] = dict( [ (k, getattr(sqla_inst,k)) for k in knames])

        # for n in knames:
        #     d[n] = getattr(sqla_inst,n)

        for n in single_rnames:
            if n in d:
                # mainlog.debug("update_delta_with_sqla_keys : going down the rabbit single hole : {}".format(n))
                item = d[n]['__items__'][0]
                self._update_delta_with_sqla_keys_helper(item, key_track)

        for n in rnames:
            # We're updating a delta => some relations
            # of the model may be missing.
            if n in d:
                # mainlog.debug("update_delta_with_sqla_keys : going down the rabbit hole : {}".format(n))
                relation = d[n]
                for item in relation['__items__']:
                    self._update_delta_with_sqla_keys_helper(item, key_track)

        return d


    def copy_delta_pk_in_dto(self, deltas, obj_track):
        for delta in deltas:
            self.copy_delta_pk_in_dto_helper( delta, obj_track( delta['__object__id']))

    def copy_delta_pk_in_dto_helper(self, d, inst):
        mainlog.debug("copy_delta_keys_in_object : hello")
        mainlog.debug(d)

        fnames, rnames, single_rnames, knames = self._attributes_names(self._mapped_classes[ d['__model__']])

        for key, value in d.items():
            if key in knames:
                setattr(inst, key, value)

        for n in single_rnames:
            if n in d:
                relation = getattr(inst, n)
                delta_item = d[n]['__items__'][0]
                self.copy_delta_pk_in_dto_helper( delta_item, relation)

        for n in rnames:
            if n in d:
                relation = getattr(inst, n)
                mainlog.debug("copy_delta_keys_in_object : level {}, Following relationship {}. Object attr is of type {}".format(model, n, type(relation)))
                delta_items = d[n]['__items__']
                mainlog.debug("There are {} deltas and {} items in relation".format(len(delta_items), len(relation)))
                for i in range(len(delta_items)):
                    self.copy_delta_pk_in_dto_helper( delta_items[i], relation[i])


    def _serialize_object_identification(self, inst, obj_track):
        fnames, rnames, single_rnames, knames = self._attributes_names(inst.__model__)

        oid = id(inst)
        obj_track[oid] = inst

        s = dict()
        s['__object_id__'] = oid
        s['__model__'] = inst.__model__.__name__

        # Primary key
        for k in knames:
            s[k] = getattr(inst,k)
        return s



    def delta_serialize(self, obj, store, obj_track):
        model = obj.__model__
        fnames, rnames, single_rnames, knames = self._attributes_names(model)

        def serialize_fields(obj : InstrumentedObject):
            assert isinstance(obj, InstrumentedObject)
            d = dict()
            for n in obj._changed - set(single_rnames):
                # mainlog.debug("Delta-Serializing copying field {}".format(n))
                d[n] = getattr(obj,n)
            return d

        def has_changed(obj : InstrumentedObject):
            assert isinstance(obj, InstrumentedObject)
            return obj._changed


        mainlog.debug("Internal node {}".format(model))
        if has_changed(obj):
            mainlog.debug("Changed")
            d = self._serialize_object_identification(obj, obj_track)

            # Regular relationship (based on collections) are never marked as changed.
            # So no need to track them; that will be done through recursivity.
            # For example a.children = []. If one does a.children.add("Donald")
            # then the 'children' attribute won't be marked as changed in 'a'.
            # However, the array denoted by 'children' will be marked as changed.
            # Single relationship are different because they're represented
            # as object instead of list. Therefore, they can be marked as changed.

            for n in obj._changed - set(single_rnames):
                d[n] = getattr(obj,n)
        else:
            mainlog.debug("Not changed")
            d = dict()

        for relation_name in rnames:
            relation = getattr(obj, relation_name)

            mainlog.debug("Down the rabbit relation {} hole".format(relation_name))
            # Simple recursion to make sure we check all the
            # children. This also populates the store.

            for item in relation:
                self.delta_serialize(item, store, obj_track)

            # Here we assume that if a child is new, then
            # then it is necessarily added to a relation
            # then that relation is marked as changed.
            if relation.has_changed():
                mainlog.debug("Relation {} has changed".format(relation_name))
                r = []
                for item in relation:
                    if item in store:
                        r.append(store[item])
                        del store[item]
                    else:
                        r.append(self._serialize_object_identification(item, obj_track))

                mainlog.debug("Relation is {}".format(r))
                d[relation_name] = { '__items__' : r}

        for relation_name in obj._changed & set(single_rnames):
            item = getattr(obj, relation_name)
            mainlog.debug("Down the rabbit one-relation {} hole".format(relation_name))
            self.delta_serialize(item, store, obj_track)

            if item in store:
                d[relation_name] = { '__items__' : [store[item]]}
                del store[item]
            elif item:
                d[relation_name] = { '__items__' : [self._serialize_object_identification(item, obj_track)]}

        if d:
            s = self._serialize_object_identification(obj, obj_track)
            if has_changed(obj):
                for n in obj._changed - set(single_rnames):
                    s[n] = getattr(obj,n)
            s.update(d)

            mainlog.debug("Storing : {}".format(s))
            store[obj] = s


    def serialize_full(self, inst):
        if type(inst) == list:
            return [self._serialize_full_helper(item, []) for item in inst]
        else:
            return self._serialize_full_helper(inst, [])


    def _serialize_full_helper(self, inst, backtrack):
        # backtracking is used to prevent us to go back and forth between
        # a relation and its backref.

        # The backtracking is limited because it follows the run we do through
        # the object graph (so it's built recursively). To be 100% correct,
        # the backtrack should be built for the whole graph and not only
        # on depth-first paths.

        model = type(inst)

        backtrack.append(inst)
        mainlog.debug("Added {} to backtrack".format(inst))

        fnames, rnames, single_rnames, knames = self._attributes_names(model)

        d = dict()

        d['__model__'] = model.__name__

        # Always give the key values because I need to know
        # what object I'm talking about

        for n in fnames:
            d[n] = getattr(inst,n)

        for n in rnames + single_rnames:
            relation = getattr(inst,n)

            if type(relation) == InstrumentedDict:
                raise "Unsupported type of relationship"

            elif relation:
                if type(relation) not in (InstrumentedList, InstrumentedSet):
                    mainlog.debug("Relation {} is single element : {} of type {}".format(n, relation, type(relation)))
                    relation = [relation] # non-list relation

                r = dict()

                l = []
                for item in relation: # Works for sets and lists

                    if item not in backtrack:
                        # We go depth first because we need to contextualize
                        # each changes

                        s = self._serialize_full_helper( item, backtrack)
                        if s:
                            l.append(s)
                    else:
                        mainlog.debug("Backtrack worked! On {} of type {}".format(item, type(item)))
                        mainlog.debug(backtrack)
                        mainlog.debug( [type(i) for i in backtrack])
                        mainlog.debug(backtrack.index(item))
                        mainlog.debug(item in backtrack)

                if l:
                    # I need a separate __items__ tag because I may or may not
                    # have a __deleted__ tag.
                    r['__items__'] = l

                if r:
                    d[n] = r
            else:
                # Relation is empty, so is  a single item relation, but not set
                pass



        return d


    def merge_keys(self, obj_track, key_track):

        for oid, key_values in key_track.items():
            obj = obj_track[oid]

            for k,v in key_values.items():
                setattr(obj, k, v)

    def unserialize_full(self, items):
        """ Picks one ore more dicts and unserialize them tochange tracking DTO's.
        So this is expected to receive a dict from a server and make it a DTO
        for delivery_slips side procesing.

        :param items:
        :return:
        """
        if type(items) == list:
            return [self._unserialize_full_helper(d) for d in items]
        else:
            return self._unserialize_full_helper(items)

    def _unserialize_full_helper(self, d):

        model = self._mapped_classes[d['__model__']]
        dto = self.make_change_tracking_dto(model)
        fnames, rnames, single_rnames, knames = self._attributes_names(model)

        for name in fnames:
            mainlog.debug("unserialize_full: copying field {}".format(name))
            if name in d:
                setattr(dto,name, d[name])

        for name in rnames:
            relation = getattr(dto, name)

            if name in d:
                for item in d[name]['__items__']:
                    relation.append( self._unserialize_full_helper(item))

        for name in single_rnames:
            if name in d:
                item = d[name]['__items__'][0]
                setattr(dto, name, self._unserialize_full_helper(item))

        return dto

