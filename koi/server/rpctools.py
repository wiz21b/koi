from datetime import datetime
import sys
if sys.version[0] == '3':
    import xmlrpc.client as xmlrpclib
else:
    import xmlrpclib
import sqlalchemy # .dialects.postgresql.base.TIMESTAMP

from koi.datalayer.SQLAEnum import DeclEnumType
from koi.db_mapping import Task,Employee,TaskActionReport,TaskOnOperation,TaskActionReportType,TaskOnNonBillable,TaskOnOrder

def sqla_to_hash(arg):
    if isinstance(arg,list):
        l = arg
    else:
        l = [arg]

    r = []
    for instance in l:
        hash = {}
        klass = instance.__class__

        for key in klass.__mapper__.columns.keys():
            t = type(klass.__mapper__.columns[key].type)
            # print "{} is a {}".format(key, t)
            if t == sqlalchemy.types.LargeBinary:
                if sys.version[0] == '3':
                    hash[key] = xmlrpclib.Binary(getattr(instance,key))
                else:
                    hash[key] = xmlrpclib.Binary(str(getattr(instance,key)))
            elif t == DeclEnumType:
                hash[key] = getattr(instance,key).value
            else:
                hash[key] = getattr(instance,key)

        hash['__klass__'] = klass.__name__
        hash['__pk__'] = klass.__mapper__.primary_key_from_instance(instance)

        r.append(hash)

    if isinstance(arg,list):
        return r
    else:
        return r[0]


def hash_to_sqla(hash):
    klass = globals()[hash['__klass__']]

    pk = hash['__pk__']
    instance = None

    if pk is None:
        instance = klass()
    else:
        if len(klass.__mapper__.primary_key) != 1:
            raise Exception("I can only work on 1-field long primary key")
        pk_name = klass.__mapper__.primary_key[0].name

        instance = session().query(klass).filter(getattr(klass,pk_name) == pk[0]).one()

    column_names = klass.__table__.columns
    for key,value in hash.items():
        if key in column_names:
            t = klass.__mapper__.columns[key].type
            if t == sqlalchemy.types.LargeBinary:
                if value is not None:
                    value = value.data
            elif t == sqlalchemy.dialects.postgresql.base.TIMESTAMP:
                # print "TIMESTAMP"
                if value is not None:
                    value = datetime.strptime(str(value), "%Y%m%dT%H:%M:%S")
            elif t == DeclEnumType:
                if value is not None:
                    value = DeclEnumType.enum.from_str(value)

            setattr(instance,key,value)

        elif key not in ('__klass__','__pk__'):
            raise Exception("The field {} is not part of {}".format(key,klass))

    return instance


class Mapped:
    def __init__(self, **entries):

        # FIXME Not enough, one shoudl create the object with the type
        # rather than identifying the type with "klass".
        # But I'm tired now, so I'll leave it this way for now.

        if '__klass__' not in entries:
            # Anonymous object
            for key in entries:
                setattr(self,key,entries[key])
            return

        # print("__klass__ = {}".format(entries['__klass__']))
        self.klass = globals()[entries['__klass__']]
        # print klass

        for key in self.klass.__mapper__.columns.keys():
            t = type(self.klass.__mapper__.columns[key].type)
            # print("DB {} -> {} / ".format(key,entries[key]),t)
            v = entries[key]

            if t == sqlalchemy.types.LargeBinary:
                if v is not None:
                    v = v.data
            elif t == sqlalchemy.dialects.postgresql.base.TIMESTAMP:
                # print "TIMESTAMP"
                if v is not None:
                    v = datetime.strptime(str(v), "%Y%m%dT%H:%M:%S")
            elif t == DeclEnumType:
                if v is not None:
                    v = self.klass.__mapper__.columns[key].type.enum.from_str(v)
            setattr(self,key,v)

        # Orphans...
        for key in entries:
            if key not in self.klass.__mapper__.columns:
                setattr(self,key,entries[key])

        # self.__dict__.update(entries)

def hash_to_object(arg):
    """ XMLRPC to Python object """
    if arg is None:
        # print "hash_to_object(arg) called one None !!!"
        return None
    elif isinstance(arg, list):
        # print "hash_to_object(LIST) : {}".format(arg)
        return [Mapped(**x) for x in arg]
    else:
        # print "hash_to_object(object) : {}".format(arg)
        return Mapped(**arg)



if __name__ == "__main__":
    from db_mapping import *

    offer = session().query(Offer).filter(Offer.offer_id == 200).one()
    print(offer)

    hash = sqla_to_hash(offer)
    print(hash)

    offer =  hash_to_sqla(hash)
    print(offer)

    print(hash_to_object(dict(a=13,b=13)))
    print(hash_to_object(dict(a=13,b=13)).__dict__)
