import re

from sqlalchemy.types import SchemaType, TypeDecorator, Enum
from sqlalchemy.util import set_creation_order, OrderedDict
from sqlalchemy.dialects.postgresql import ENUM


class EnumSymbol(object):
    """Define a fixed symbol tied to a parent class.
    A symbol has a value (the enum value) and
    a description. The description is used, well,
    for displaying information, it should not be
    used as the basis for computation. """

    def __init__(self, value, description=None):
        self.value = value
        self.description = description
        set_creation_order(self)

    def bind(self, cls, name):
        """Bind symbol to a parent class."""
        self.cls = cls
        self.name = name
        setattr(cls, name, self)

    def __reduce__(self):
        """Allow unpickling to return the symbol linked to the DeclEnum class."""
        return getattr, (self.cls, self.name)

    def __iter__(self):
        return iter([self.value, self.description])

    def __repr__(self):
        # Pay attention, this repr may be used to go from
        # enum to str and from str to enum
        return "%s" % self.name

class DeclEnumMeta(type):
    """Generate new DeclEnum classes."""

    def __init__(cls, classname, bases, dict_):
        reg = cls._reg = cls._reg.copy()
        for k in sorted(dict_):
            if k.startswith('__'):
                continue
            v = dict_[k]
            if isinstance(v, str):
                v = EnumSymbol(v)
            elif isinstance(v, tuple) and len(v) == 2:
                v = EnumSymbol(*v)
            if isinstance(v, EnumSymbol):
                v.bind(cls, k)
                reg[k] = v
        reg.sort(key=lambda k: reg[k]._creation_order)
        return type.__init__(cls, classname, bases, dict_)

    def __iter__(cls):
        return iter(cls._reg.values())

class DeclEnum(object):
    """Declarative enumeration.

    Attributes can be strings (used as values),
    or tuples (used as value, description) or EnumSymbols.
    If strings or tuples are used, order will be alphabetic,
    otherwise order will be as in the declaration.

    """

    __metaclass__ = DeclEnumMeta
    _reg = OrderedDict()

    @classmethod
    def names(cls):
        """ names of the symbols  of the enumeration.
        """

        return cls._reg.keys()

    @classmethod
    def symbols(cls):
        """ symbols of the enumeration.
        """
        return cls._reg.values()

    @classmethod
    def descriptions(cls):
        """ Description of all the symbols of
        the enumeration, in the same order as
        the symbols themselves."""

        return [v.description for v in cls._reg.values()]

    @classmethod
    def db_type(cls):
        # return ENUM(*cls.names(), name=cls.__name__)
        return DeclEnumType(cls)

    @classmethod
    def from_str(cls,s):
        # Will work with something else than str => FIXME Rename the function

        if s in cls._reg:
            return cls._reg[s]

        for k,v in cls._reg.items(): # iteritems():
            if v.value == s:
                return cls._reg[k]

        raise Exception(u"Token {} (type {}) is not recognized as a valid enum name. Should be in {}".format(s,str(type(s)),list(cls._reg.keys())))





class DeclEnumType(SchemaType, TypeDecorator):
    """DeclEnum augmented so that it can persist to the database."""

    def __init__(self, enum):
        self.enum = enum
        self.impl = ENUM(*enum.names(), name=self._sql_type_name(), create_type=True, schema="horse")
        # self.impl = Enum(*enum.names(), name=self._sql_type_name())

    def _sql_type_name(self):
        return "ck%s" % re.sub(
            '([A-Z])', lambda m: '_' + m.group(1).lower(), self.enum.__name__)
    
    def drop(self,bind=None,checkfirst=False):
        # print("drop "*10)
        z =  self.impl.drop(bind, checkfirst)
        # print("drop "*10)
        return z

    
        return "DROP TYPE IF EXISTS {}".format( self._sql_type_name())

    # def create(self, schema):
    #     return "CREATE TYPE {} AS ENUM ({})".format(
    #         schema,
    #         ','.join([ "'{}'".format(n) for n in self.enum.names()]))
    
    def _set_table(self, table, column):
        self.impl._set_table(table, column)

    def copy(self):
        return DeclEnumType(self.enum)

    def process_bind_param(self, value, dialect):
        if isinstance(value, EnumSymbol):
            value = value.name
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return getattr(self.enum, value.strip())
