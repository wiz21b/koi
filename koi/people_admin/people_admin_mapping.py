from sqlalchemy import Column, Integer, Float, Date, ForeignKey, Sequence
from sqlalchemy.orm import relationship
from sqlalchemy.schema import CheckConstraint,UniqueConstraint


from koi.datalayer.sqla_mapping_base import Base, metadata
from koi.datalayer.SQLAEnum import DeclEnum
from koi.datalayer.employee_mapping import Employee


class DayEventType(DeclEnum):
    # Day on, day off
    holidays = 'holidays', _('Holidays')
    day_off = 'day_off', _('Day off')
    unpaid_day_off = 'unpaid_day_off', _('Unpaid day off')
    free_day = 'free_day', _('Free day')

    # Hours more, hours less
    overtime = 'overtime', _('Over time')
    recuperation = 'recuperation', _('Recuperation')

    # Unemployment
    unemployment = 'unemployment', _('Unemployment')
    unemployment_short = 'unemployment_short', _('Unemployment short')

    # Health
    work_accident = 'work_accident', _('Work accident')
    sick_leave = 'sick_leave', _('Sick leave')

    @classmethod
    def short_code(self, enum):
        if enum == self.holidays:
            return _('HOL')
        elif enum == self.day_off:
            return _('OFF')
        elif enum == self.unpaid_day_off:
            return _('UOFF')
        elif enum == self.free_day:
            return _('FRE')
        elif enum == self.overtime:
            return _('OVT')
        elif enum == self.recuperation:
            return _('REC')
        elif enum == self.unemployment:
            return _('UNE')
        elif enum == self.unemployment_short:
            return _('UNES')
        elif enum == self.work_accident:
            return _('ACC')
        elif enum == self.sick_leave:
            return _('SICK')
        else:
            return "???"

day_event_id_generator = Sequence('day_event_id_generator',start=1,metadata=metadata)


class DayEvent(Base):
    """
    We have several requirements :

    - be able to record holiday time
    - be able to report sick leave for a given period of time (bvb half a day)
    - be able to account overtime because without a baseline for the daily
      worktime, Hors cannot guess what is overtime or not. Remember that overtime
      is sometimes paid differently (for example paid twice).

    """

    __tablename__ = 'day_event'

    day_event_id = Column(Integer,day_event_id_generator,index=True,primary_key=True)


    # The day of the event
    date = Column('date',Date,unique=False,nullable=False)

    # The duration meaning is not 100% certain right now.
    # Right now, it is always 1 which means the "whole day" (and that
    # itself is rather contextual, it could a all the work hours or 24 hours).

    # Duration is expressed in "work day". So it can represent
    # 8 hours, or 7.5 hours or something else, depdending on the company
    duration = Column('duration',Float,nullable=True,default=None)

    # Ther is always a type.
    event_type = Column(DayEventType.db_type(),nullable=False)


    # For whom.
    employee_id = Column('employee_id',Integer,ForeignKey('employees.employee_id'),nullable=False,index=True)

    employee = relationship(Employee, primaryjoin=Employee.employee_id == employee_id)

    # The constraint indicates that one can have a given
    # event type only once on a given day.
    __table_args__ = (UniqueConstraint(date, employee_id, event_type, name='one_type_of_event_per_day'),
                      CheckConstraint( 'duration is null or duration > 0', name='duration_not_zero'))
