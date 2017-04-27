# From http://stackoverflow.com/questions/2676133/best-way-to-do-enum-in-sqlalchemy

"""
For example :

class RleType(DeclEnum):
    timetrack_modify = 'TimeTrackModify',_("Modify time tracks")

    name             = value,            description

"""



import koi.datalayer.DeclEnumP3 as enum_stuff

EnumSymbol = enum_stuff.EnumSymbol
DeclEnum = enum_stuff.DeclEnum
DeclEnumMeta = enum_stuff.DeclEnumMeta
DeclEnumType = enum_stuff.DeclEnumType
