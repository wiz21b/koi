from sqlalchemy import or_,and_
from sqlalchemy.sql.expression import desc


from koi.db_mapping import FilterQuery,Employee,freeze,dto,dto_to_mapped
from koi.datalayer.database_session import session
from koi.datalayer.RollbackDecorator import RollbackDecorator

import sqlalchemy
from koi.junkyard.dto_maker import JsonCallable, Sequence
from koi.junkyard.sqla_dict_bridge import make_change_tracking_dto


class FilterService:

    @JsonCallable()
    @RollbackDecorator
    def save(self, fq : FilterQuery) -> int:
        session().commit()
        return fq.filter_query_id

    @JsonCallable()
    @RollbackDecorator
    def is_name_used(self, name : str, owner_id : int, family : str) -> bool:
        q = session().query(FilterQuery).filter(and_(FilterQuery.family == family, FilterQuery.owner_id == owner_id, FilterQuery.name == name)).count()
        session().commit()
        return q > 0 # Normally it should always be 0 or 1, nothin else.


    @JsonCallable()
    @RollbackDecorator
    def delete_by_id(self, fq_id : int,owner_id : int):
        fq = session().query(FilterQuery).filter(and_(FilterQuery.filter_query_id == fq_id,FilterQuery.owner_id == owner_id)).delete()
        session().commit()

    @JsonCallable()
    @RollbackDecorator
    def find_by_id(self, fq_id : int) -> FilterQuery:
        res = session().query(FilterQuery).filter(FilterQuery.filter_query_id == fq_id).one()
        session().commit()
        return res

    @JsonCallable()
    @RollbackDecorator
    def usable_filters(self, employee_id : int, family : str) -> Sequence( sqlalchemy.util._collections.KeyedTuple):
        """ List of filters usable by someone, this includes
        the shared filters.
        """

        q = session().query(FilterQuery.filter_query_id,
                            FilterQuery.owner_id,
                            FilterQuery.name,
                            FilterQuery.shared,
                            FilterQuery.query,
                            Employee.fullname,
                            (FilterQuery.owner_id != employee_id).label("srt")).join(Employee, Employee.employee_id == FilterQuery.owner_id).filter(and_(FilterQuery.family == family,or_(FilterQuery.owner_id == employee_id, FilterQuery.shared == True))).order_by("srt", FilterQuery.name).all()
        session().commit()
        return q



class FilterQueryDAO:

    def make(self):
        return dto(FilterQuery)

    def get_dto(self,fq_id):
        if fq_id:
            return self.find_by_id(fq_id)
        else:
            return self.make()

    @RollbackDecorator
    def save(self,fq):

        if type(fq) != FilterQuery:
            if fq.filter_query_id:
                sfq = session().query(FilterQuery).filter(FilterQuery.filter_query_id == fq.filter_query_id).one()
            else:
                sfq = FilterQuery()
                session().add(sfq)

            dto_to_mapped(fq, sfq)

            fq = sfq
        else:
            session().add(fq)

        session().commit()

        return fq.filter_query_id

    @RollbackDecorator
    def delete_by_id(self,fq_id,owner_id):
        fq = session().query(FilterQuery).filter(and_(FilterQuery.filter_query_id == fq_id,FilterQuery.owner_id == owner_id)).delete()
        session().commit()

    @RollbackDecorator
    def find_by_id(self,fq_id):
        return make_change_tracking_dto(
            FilterQuery,
            session().query(FilterQuery).filter(FilterQuery.filter_query_id == fq_id).one(),
            recursive=set([Employee]), additional_fields = dict())

        return freeze(session(),
                      session().query(FilterQuery).filter(FilterQuery.filter_query_id == fq_id).one())

    @RollbackDecorator
    def is_name_used(self, name, owner_id, family):
        q = session().query(FilterQuery).filter(and_(FilterQuery.family == family, FilterQuery.owner_id == owner_id, FilterQuery.name == name)).count()
        session().commit()
        return q > 0 # Normally it should always be 0 or 1, nothin else.


    @RollbackDecorator
    def usable_filters(self, employee_id, family):
        """ List of filters usable by someone, this includes
        the shared filters.
        """

        q = session().query( FilterQuery,
                             (FilterQuery.owner_id != employee_id).label("srt")).\
            join(Employee,
                 Employee.employee_id == FilterQuery.owner_id).\
            filter(and_(FilterQuery.family == family,
                        or_( FilterQuery.owner_id == employee_id,
                             FilterQuery.shared == True))).order_by("srt", FilterQuery.name).all()

        r = make_change_tracking_dto(
                FilterQuery,
                [fq[0] for fq in q],
                recursive=set([Employee]))

        session().commit()
        return r

