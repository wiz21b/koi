from koi.Configurator import mainlog
from koi.datalayer.database_session import session
from koi.datalayer.RollbackDecorator import RollbackDecorator
from sqlalchemy.orm.properties import ColumnProperty
from sqlalchemy.orm.collections import InstrumentedList, InstrumentedSet
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import class_mapper


class DictAsObj(object):
    """ Makes a dict looks like an *immutable* object.

    """
    def __init__(self, d):
        assert d.keys()
        # object.__setattr__(self, "_dict", d)
        object.__setattr__(self, "__dict__", d)

    # def __hasattr__(self,name):
    #     return name in self._dict

    # def __getattr__(self,name):
    #     return self._dict[name]

    # def __setattr__(self,name,value):
    #     self._dict[name] = value
    #     return None


class AsDict(object):
    def __init__(self,names):
        self._names = names # The name _names is used elsewhere !

    def __setattr__(self,name,value):
        # I make sure we only use the attributes of the
        # mapped class. Sort of type checking...

        if not hasattr(self,'_names') or name in self._names:
            object.__setattr__(self, name, value)
        else:
            raise Exception("Unknown field {}".format(name))

    def __getitem__(self,name):
        return getattr(self,name)

    def __setitem__(self,name,value):
        if hasattr(self, name):
            return setattr(self,name,value)
        else:
            raise Exception("Unknown field {}".format(name))

    def __contains__(self, name):
        return hasattr(self, name)

    def items(self):
        attrs_names = list(filter( lambda s: s[0] != '_', self.__class__.__dict__))
        return zip( attrs_names,
                    [self.__getattribute__(n) for n in attrs_names]).__iter__()

def blank_dto(klass):
    """ Makes a blank object that looks like a mapped one.
    That object will also behave like a dict.
    """

    mapper = klass.__mapper__

    d = dict()

    # Make sure I copy only attributes which are
    # visible to me and which are not relationships
    # FIXME What about hybrids ?

    for k,t in mapper.attrs.items():
        if not k.startswith('_') and isinstance(t,ColumnProperty):
            d[k] = None

    frozen_obj = type("Frozen"+klass.__name__, (AsDict,), d)(d.keys())

    return frozen_obj



def all_non_relation_columns(mapped_klass):
    """ Returns columns which are not relationship, that is, which
    can be accessed without trigering some easzy loading. This
    means that the columns, once read, will be available outside
    the SQLA session.
    """

    return [getattr(mapped_klass,n) for n in inspect(mapped_klass).column_attrs.keys()]


def _freeze(sqlaobj,additional_fields = None):
    if not sqlaobj:
        # Tricky ! This works for None (not very interesting)
        # but also for emtpy lists !
        return sqlaobj

    d = dict()
    if additional_fields:
        for f in additional_fields:
            d[f] = None

    # Make sure I copy only attributes which are
    # visible to me and which are not relationships

    # FIXME What about hybrids ?

    for k,t in sqlaobj.__mapper__.attrs.items():
        # We avoid relationships and stick onyl to attribute stored in DB
        if isinstance(t,ColumnProperty): # not k.startswith('_') and
            d[k] = getattr(sqlaobj,k)

    frozen_obj = type("Frozen"+type(sqlaobj).__name__, (object,), d)()

    return frozen_obj


def freeze(obj,commit = True, additional_fields = None):
    """ Creates a shallow copy of an SQLAlchemy object
    or a collection of SQLA objects. Shallow means
    we don't go into relationships.

    A commit can be done at the end of the copy to end
    an open transaction.

    The goal is to have an object that can be safely
    used outside the SQLAlchemy. session. That is an object
    that will not trigger a session access when we
    access its attributes.
    """

    frozen = None

    # The instrumented list part is to allow us to easily freeze
    # a relationship of an object : freeze(parent.children)

    if type(obj) in (list,InstrumentedList):
        # The order of the frozen elements is the same
        # as the order of the original elements.
        # We must guarantee that.

        frozen = []
        for o in obj:
            frozen.append( _freeze(o,additional_fields))
    elif type(obj) == InstrumentedSet:
        # The order of elements doesn't make sense because
        # we have a set => no guarantee here.
        frozen = set()
        for o in obj:
            frozen.add( _freeze(o,additional_fields))
    else:
        frozen = _freeze(obj,additional_fields)

    if commit:
        session().commit()

    return frozen



from sqlalchemy.inspection import inspect

def pk_column_for_class(klass):
    """ Returns the column corresponding to the PK. The column
    can be used in SQLA queries.
    This will only work on PK made of exactly one field.
    """

    # In case of inheritance, SQLA considers the parent's PK
    # as the child PK (see inheritance in SQLA's doc)

    mainlog.debug("pk_column_for_class for {}".format(klass))
    pk_fields = klass.__mapper__.primary_key
    assert len(pk_fields) == 1, "I won't work with composite primary keys or withou PK"
    pk_column = pk_fields[0]

    # Somehow, when I have the PK (column), it's not easy
    # to find out the name of the corresponding attribute
    # in the mapped class.

    key_column = inspect(klass).primary_key[0]
    return key_column, key_column.name

    pk_attr = None
    for name, a in klass.__mapper__.attrs.items():
        mainlog.debug("pk_column_for_class looking at attribute {}".format(name))
        if isinstance(a,ColumnProperty):
            # The for loop is here to take inheritance into account
            # FIXME but that's super hackish

            for c in a.columns:
                if isinstance(c,Column) and c.table == klass.__table__ and c.name == pk_column.name:
                    pk_attr = name
                    break

            if pk_attr:
                # escape from the inner loop :-)
                break

    if not pk_attr:
        raise Exception("Didn't find a PK while looking at class {}. The PK column was {}".format(klass.__name__, pk_column))

    return pk_column, pk_attr


@RollbackDecorator
def generic_delete(klass, o_id):
    """ Delete an object of a given type
    """

    pk_column,name = pk_column_for_class(klass)

    # mainlog.debug(u"Generic delete {} for id {} with pk {}".format(klass,o_id,pk_column))
    # mainlog.debug(session().query(klass).filter(pk_column == o_id).one())

    obj = session().query(klass).filter(pk_column == o_id).one()
    session().delete(obj) # You should have cascades if necessary...
    session().commit()

@RollbackDecorator
def generic_load_all_frozen(mapped_klass,sort_criterion=None):
    """ Loads all objects of a given type
    The objects are disconnected from the SQLA session
    """

    q = session().query(mapped_klass)
    if sort_criterion:
        q = q.order_by(sort_criterion)
    from sqlalchemy.orm.session import make_transient
    items = q.all()
    for i in items:
        make_transient(i)
    return items

    q = session().query(*mapped_klass.__table__.columns)
    if sort_criterion:
        q = q.order_by(sort_criterion)

    frozen_items = q.all()
    session().commit()
    # mainlog.debug("generic_load_all_frozen : returning {} items".format(len(frozen_items)))
    # for item in frozen_items:
    #     mainlog.debug(item)
    return frozen_items

def defrost_to_session(obj,klass):
    assert obj
    assert klass

    pk,name = pk_column_for_class(klass)

    oid = getattr(obj,name)
    if oid is not None:
        sqlaobj = session().query(klass).filter(pk == oid).one()
    else:
        sqlaobj = klass()
        session().add(sqlaobj)

    for k,t in klass.__mapper__.attrs.items():
        if isinstance(t,ColumnProperty) and hasattr(obj,k):
            setattr(sqlaobj,k,getattr(obj,k))

    return sqlaobj

@RollbackDecorator
def recursive_defrost_into(dikt, klass, fields_out = []):

    fields_out.append('_names') # For AsDict

    if not isinstance(dikt,dict):
        # raise Exception("Expected dict, got {} instead".format(type(dikt)))
        dikt = dikt.__dict__

    # FIXME Never tested recursive call more than one level deep

    pk_column,name = pk_column_for_class(klass)
    pk_name = pk_column.name

    sqlaobj = None
    if pk_name in dikt and dikt[pk_name] is not None:
        # The object seems to belong to the database
        # because it has a filled PK
        # so we guess it's an update (unless the object
        # has been removed from the database in the
        # meantime...)
        # mainlog.debug("recursive_defrost_into : Load object with pk: {}={}".format(pk_column, dikt[pk_name]))
        sqlaobj = session().query(klass).filter(pk_column == dikt[pk_name]).one()
    else:
        # mainlog.debug("recursive_defrost_into : brand new object (PK is {})".format(pk_name))

        # Brand new object
        sqlaobj = klass()
        session().add(sqlaobj)


    # mainlog.debug(u"recursive_defrost_into {}".format(dikt))

    for key,value in dikt.items() :

        if key in fields_out:
            # mainlog.debug(u"   defrost '{}' : field is left out".format(key))
            continue

        if type(value) == list:
            # mainlog.debug(u"   defrost *list* {} -> {}".format(key, value))

            # It's a one-to-many relationship
            subobj_class = class_mapper(type(sqlaobj)).get_property(key).mapper.entity
            # relationship = getattr(sqlaobj,key)
            # pk_column = filter( lambda c:c.primary_key, subobj_class.__table__.columns)[0]

            # So here, we *replace* all the children (it's not an
            # update because update is trickier and I don't need
            # that right now)
            relationship = []
            for child_value in value:

                # child_obj = None
                # for actual_child in relationship:
                #     if getattr(actual_child,pk_column) == getattr(child_value,pk_column):
                #         child_obj = actual_child
                #         break
                # if not actual_child:
                actual_child = subobj_class
                relationship.append( recursive_defrost_into(child_value, actual_child))

            # mainlog.debug("inejcting relationship attr {}".format(key))
            # mainlog.debug(relationship)

            setattr(sqlaobj,key,relationship)
        else:
            # A simple property
            #mainlog.debug(u"   defrost '{}' with value '{}'".format(key,value))
            setattr(sqlaobj,key,value)

    return sqlaobj


def as_dto(sqla_objects):
    # Pay attention to the relationships, they won't necessarily
    # be expunged (see expunge cascade rule)

    if not sqla_objects:
        return sqla_objects

    if type(sqla_objects) == list:
        for sqla_obj in sqla_objects:
            session().expunge(sqla_obj)
    else:
        session().expunge(sqla_objects)

    session().commit()
    return


def generic_update(dto):
    obj = session().merge(dto)
    session().commit()
    session().expunge(obj)
    return obj



class DTOFactory(object):
    def __init__(self):
        self._cache = dict()

    def dto_for_mapper(self, mapper_klass):
        if mapper_klass not in self._cache:
            d = dict()
            for k,t in mapper_klass.__mapper__.attrs.items():
                # We avoid relationships and stick only to attribute stored in DB
                if isinstance(t,ColumnProperty): # not k.startswith('_') and
                    d[k] = None

            self._cache[mapper_klass] = type("DTO" + mapper_klass.__name__, (object,), d)

        return self._cache[mapper_klass]() # We return an instance of the dto, hence "()"


dto_factory = DTOFactory()
