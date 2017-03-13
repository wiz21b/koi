import hashlib
from sqlalchemy import Column, String, LargeBinary, Boolean, Integer, Sequence
from sqlalchemy.orm import reconstructor

from koi.Configurator import mainlog

try:
    from PySide.QtGui import QPixmap,QImage
    from PySide.QtCore import Qt,QByteArray,QBuffer,QIODevice
except:
    # All of this because on some  platform (such as Raspberry) it's hard to get a
    # working versin of PySide with painful recompilation.
    mainlog.warning("Could not import PySide. This is tolerated as a fix to be able to deploy the server because it doesn't need Qt")

from koi.datalayer.SQLAEnum import DeclEnum
from koi.datalayer.sqla_mapping_base import metadata,Base,DATABASE_SCHEMA

try:
    _('')
except:
    _ = lambda x:x


class RoleType(DeclEnum):
    view_timetrack = 'view_timetrack',_("View time tracks")
    timetrack_modify = 'TimeTrackModify',_("Modify time tracks")
    modify_parameters = 'ModifyParameters',_("Modify parameters")

    modify_monthly_time_track_correction = 'modify_monthly_time_track_correction',_("Change monthly timetracks correction")
    view_financial_information = 'view_financial_information',_('View financial information')
    view_prices = 'view_prices',_('View prices')
    view_audit = 'view_audit',_('View audit trail')
    modify_document_templates = 'modify_document_templates', _('Modify the documents templates')

employee_id_generator = Sequence('employee_id_generator',100,None,None,False,None,metadata)


class Employee(Base):
    """ The information about an employee. This information is like an
    identity card for the employee. For example, this class shouldn't
    link directly to the task an employee has accomplished.
    """

    __tablename__ = 'employees'

    # employee_id = Column(Integer,autoincrement=True,primary_key=True)
    employee_id = Column('employee_id',Integer,employee_id_generator,nullable=False,primary_key=True)

    fullname = Column(String)
    """ The full name of the employee, e.g. Charles Baudelaire. """

    picture_data = Column(LargeBinary)

    is_active = Column(Boolean,default=True,nullable=False)
    """ An inactive employee don't show up in Horse (except in the employee
    edit screen) """

    # ALTER TABLE employees ADD COLUMN login varchar(64) unique;
    # ALTER TABLE employees ADD COLUMN password varchar(64);
    # ALTER TABLE employees ADD COLUMN roles varchar(1024);
    # INSERT INTO employees (employee_id,login,password,fullname,roles) VALUES ( (select nextval('employee_id_generator')),'dd',md5('dd'),'Daniel Dumont','TimeTrackModify,ModifyParameters');

    login = Column('login',String(length=64),nullable=True,unique=True)
    password = Column('password',String(length=64),nullable=True)

    _roles = Column('roles',String(length=1024),nullable=True)

    possible_roles = ['TimeTrackModify','ModifyParameters']


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

    def __init__(self):
        self._image_as_pixmap = None

    @reconstructor
    def reset_cache(self):
        self._image_as_pixmap = None

    def __repr__(self):
        return u"<{}>".format(self.fullname)

    @property
    def image(self):
        if self._image_as_pixmap is None and self.picture_data:
            # Caution ! QImage and stuff work only if QApplication has been initialized !
            image = QImage.fromData(QByteArray(self.picture_data))
            self._image_as_pixmap = QPixmap.fromImage(image.convertToFormat(QImage.Format_RGB16, Qt.MonoOnly).scaledToHeight(128))

        return self._image_as_pixmap

    @image.setter
    def image(self,pixmap):
        if pixmap == None:
            self._image_as_pixmap = None
            self.picture_data = None
        else:

            byte_array = QByteArray()
            qbuffer = QBuffer(byte_array)
            qbuffer.open(QIODevice.WriteOnly)
            pixmap.toImage().save(qbuffer, "PNG")

            self._image_as_pixmap = None
            self.picture_data = memoryview(byte_array.data()) # memory view to support python 2 and 3

    @classmethod
    def hash_password(self, unencrypted):
        h = hashlib.md5()
        h.update(unencrypted.encode(encoding='utf-8'))
        return h.hexdigest()

    def set_encrypted_password(self, unencrypted : str):
        self.password = self.hash_password( unencrypted)
