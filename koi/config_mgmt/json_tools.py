import enum
import zlib
from datetime import date,datetime
import base64
from decimal import Decimal
from json import JSONEncoder, loads
from koi.base_logging import mainlog
from koi.python3 import DeclEnum,EnumSymbol

class HorseJsonEncoder(JSONEncoder):
    """An encoder that's meant to convert from dict to json, with the
    additional hypothesis that the dict only contains python base
    objects (numbers, dates, dict, set, enums, etc. but no plain
    object).

    """

    def default(self, obj):
        """ As stated in Python's doc : implement a default() method
        that returns a serializable object for o.
        """

        if isinstance(obj, datetime):
            return { '__datetime__' : datetime.strftime( obj, "%Y-%m-%dT%H:%M:%S.%f" ) }
        elif isinstance(obj, date):
            return { '__date__' : obj.isoformat() }
        elif isinstance(obj,Decimal):
            return { '__dec__' : str(obj) }
        elif isinstance(obj,EnumSymbol):
            # Legacy enum's from Koi
            return { '__old_enum__' : (obj.value, obj.cls.__name__) }
        elif isinstance(obj,enum.Enum):
            # Python 3 enums are not regular classes (see "How are Enums
            # different?" in python's documentation)
            return { '__enum__' : ( str(obj.name), obj.__class__.__name__ ) }
        elif isinstance(obj,bytes): # Python 3
            return { '__bytes__' : base64.b64encode(obj).decode('ascii')}
        elif isinstance(obj,set):
            return list(obj)
        else:
            return super(HorseJsonEncoder, self).default(obj)

# Without this I must import all enums classes in this module.
# This result into a module tied to Koï.
_supported_enums = dict() # name -> Enum

def register_enumerations( l : list):
    global supported_enums
    for e in l:
        _supported_enums[ e.__name__] = e

def json_object_hook(d):
    """ From the library reference of Python : object_hook is an optional
    function that will be called with the result of any object literal
    decoded (a dict). The return value of object_hook will be used instead
    of the dict.
    """
    global _supported_enums

    if "__date__" in d:
        # mainlog.debug("json_object_hook : parsing a date : {}".format([int(x) for x in d['__date__'].split('-')]))
        return date( *([int(x) for x in d['__date__'].split('-')]) )

    elif "__dec__" in d:
        return Decimal(d["__dec__"])

    elif "__datetime__" in d:
        return datetime.strptime( d['__datetime__'], "%Y-%m-%dT%H:%M:%S.%f" )
        #return dateutil.parser.parse(d['__date__'])

    elif "__enum__" in d:
        v,enum_name = d['__enum__']
        assert enum_name in _supported_enums, "{} is not supported. not in : {}. Please use register_enumerations".format(enum_name, _supported_enums)
        return _supported_enums[enum_name][v]

    elif "__old_enum__" in d:
        v, enum_name = d['__old_enum__']
        assert enum_name in _supported_enums, "{} is not supported. not in : {}. Please use register_enumerations".format(enum_name, _supported_enums)
        return _supported_enums[enum_name].from_str(v)

    elif "__bytes__" in d:
        return base64.b64decode(d["__bytes__"])

    else:
        return d


# Instanciation here so that we don't have to instanciate it everywhere.
horse_json_encoder = HorseJsonEncoder()



def encode( d : dict):
    s = horse_json_encoder.encode(d)
    compressed = zlib.compress( bytes( s, "UTF-8"))
    return compressed

def decode( b : bytes):
    s = zlib.decompress( b)
    return loads( s.decode('UTF-8'), object_hook=json_object_hook)
