# raise Exception("skljlskjflksjdklfsdjf")
def cmp(a,b):
    if a < b:
        return -1
    elif a > b:
        return + 1
    else:
        return 0

import builtins
builtins.cmp = cmp

import sys
# if sys.version[0] == '3':
#     import builtins
#     # builtins.unicode = lambda o: str(o)
#     builtins.chr = lambda p:chr(p)
#     builtins.cmp = cmp
#     import koi.datalayer.DeclEnumP3 as enum_stuff
# else:
#     import koi.datalayer.DeclEnumP2 as enum_stuff

import koi.datalayer.DeclEnumP3 as enum_stuff


EnumSymbol = enum_stuff.EnumSymbol
DeclEnum = enum_stuff.DeclEnum
DeclEnumType = enum_stuff.DeclEnumType
