from sqlalchemy import Column, String, Boolean, Integer, Sequence
from koi.datalayer.sqla_mapping_base import metadata,Base, DATABASE_SCHEMA
from koi.Configurator import mainlog
from koi.datalayer.employee_mapping import RoleType

user_class_id_generator = Sequence('user_class_id_generator',start=1, schema=DATABASE_SCHEMA,metadata=metadata)

class UserClass(Base):
    __tablename__ = 'user_classes'

    user_class_id = Column('user_class_id',Integer,nullable=True,primary_key=True)

    # machine_id = Column('machine_id',Integer,machine_id_generator,nullable=False,primary_key=True)

    name = Column(String,unique=True,nullable=False)
    """ The full name of the user class"""

    is_active = Column(Boolean,default=True,nullable=False)
    """ An inactive machine don't show up in Horse (except in the machine
    edit screen) """

    _roles = Column('roles',String(length=2048),nullable=True)

    @property
    def roles(self):
        if not self._roles:
            return set()
        else:
            ret = set()
            for r in self._roles.split(','):
                try:
                    ret.add(RoleType.from_str(r))
                except Exception as ex:
                    mainlog.error(u"Unrecognized role : {}, skipping.".format(r))

            return ret

    @roles.setter
    def roles(self,new_roles):
        # mainlog.debug("set_roles {}".format(new_roles))

        if new_roles is None or len(new_roles) == 0:
            self._roles = None
        else:
            for r in new_roles:
                if r not in RoleType.symbols():
                    raise Exception("The role '{}' does not exist.".format(r))

            self._roles = ','.join(map(lambda r:r.name,new_roles))
