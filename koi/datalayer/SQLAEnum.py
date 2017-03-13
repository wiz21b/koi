import re

from sqlalchemy.types import SchemaType, TypeDecorator, Enum
from sqlalchemy.util import set_creation_order, OrderedDict

# From http://stackoverflow.com/questions/2676133/best-way-to-do-enum-in-sqlalchemy

"""
For example :

class RleType(DeclEnum):
    timetrack_modify = 'TimeTrackModify',_("Modify time tracks")

    name             = value,            description

"""



import sys
if sys.version[0] == '3':
    import koi.datalayer.DeclEnumP3 as enum_stuff
else:
    import koi.datalayer.DeclEnumP2 as enum_stuff

EnumSymbol = enum_stuff.EnumSymbol
DeclEnum = enum_stuff.DeclEnum
DeclEnumMeta = enum_stuff.DeclEnumMeta
DeclEnumType = enum_stuff.DeclEnumType
