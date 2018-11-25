from datetime import datetime,timedelta

from sqlalchemy import and_,or_

from koi.datalayer.database_session import session
from koi.datalayer.RollbackDecorator import RollbackDecorator
from koi.datalayer.audit_trail_mapping import AuditTrail
from koi.db_mapping import Employee,OrderPart, ProductionFile, Operation
from koi.session.UserSession import user_session


class AuditTrailService(object):

    def __init__(self):
        pass

    @RollbackDecorator
    def who_touched_order(self, order_id, not_me_id=None):

        if not not_me_id:
            not_me_id = user_session.user_id

        tlimit = datetime.now() - timedelta(hours=24*31)

        # The order_by clause will trigger the loading of
        # AuditTrail.when column. Because of that "distinct"
        # on employee_id won't work. Therefore I make that
        # with a subquery

        subq = session().query(AuditTrail.who_id).\
               join(OrderPart, OrderPart.order_id == order_id).\
               join(ProductionFile, ProductionFile.order_part_id == OrderPart.order_part_id).\
               join(Operation, Operation.production_file_id == ProductionFile.production_file_id).\
               filter(and_( AuditTrail.when > tlimit,
                            AuditTrail.who_id != not_me_id,
                            AuditTrail.who_id != None, # is not null
                            or_(and_(AuditTrail.target_id == order_id,
                                     AuditTrail.what.in_(["CREATE_ORDER","UPDATE_ORDER","ORDER_STATE_CHANGED"])),
                                and_(AuditTrail.target_id == Operation.operation_id,
                                     AuditTrail.what.in_(["CREATE_OPERATION", "UPDATE_OPERATION", "DELETE_OPERATION"])),
                                and_(AuditTrail.target_id == OrderPart.order_part_id,
                                     AuditTrail.what.in_(["CREATE_ORDER_PART","UPDATE_ORDER_PART","DELETE_ORDER_PART"])))
                            )).order_by(AuditTrail.when).subquery()

        res = session().query(Employee.fullname).\
              select_from(subq).\
              join(Employee, Employee.employee_id == subq.c.who_id).distinct().all()

        res = list(map(lambda row:row.fullname, res))

        session().commit()
        return res

    @RollbackDecorator
    def audit_trail_for_order(self,order_id):

        # We mix orders *and* order parts because we feel it makes
        # the audit trail more understandable for the user.

        res = session().query(AuditTrail.what,AuditTrail.detailed_what,AuditTrail.when,Employee.fullname).\
              join(Employee).\
              join(OrderPart, OrderPart.order_id == order_id). \
              join(ProductionFile, ProductionFile.order_part_id == OrderPart.order_part_id). \
              join(Operation, Operation.production_file_id == ProductionFile.production_file_id). \
            filter(
                or_(and_(AuditTrail.target_id == order_id,
                         AuditTrail.what.in_(["CREATE_ORDER", "UPDATE_ORDER", "ORDER_STATE_CHANGED"])),
                    and_(AuditTrail.target_id == Operation.operation_id,
                         AuditTrail.what.in_(["CREATE_OPERATION", "UPDATE_OPERATION", "DELETE_OPERATION"])),
                    and_(AuditTrail.target_id == OrderPart.order_part_id,
                         AuditTrail.what.in_(["CREATE_ORDER_PART", "UPDATE_ORDER_PART", "DELETE_ORDER_PART"])))
        ).order_by(AuditTrail.when).distinct().all()

        session().commit()
        return res

    @RollbackDecorator
    def record(self, what, detailed_what, target_id, who_id=None,who_else=None,commit=True):
        """ Record an audit trail entry. This function does 2 things
        automatically :

        1. It sets the time of the record.
        2. If nobody is set as the author of the recorder action (the "who"),
        then it is assumed that the current session's user is the one.

        This is done automatically to ensure some minimum quality standards
        on the audit trail.
        """

        global user_session

        assert target_id is not None # Reflect DB constraint

        a = AuditTrail()
        a.what = str(what or _("Unspecified"))
        a.target_id = target_id
        a.detailed_what = str(detailed_what or _("Unspecified"))

        if who_id is None and who_else is None:
            a.who_id = user_session.user_id
            if not a.who_id:
                a.who_else = "UNCLAIMED"
        else:
            a.who_id = who_id
            a.who_else = who_else


        a.when = datetime.now()

        session().add(a)

        # mainlog.debug(u"AUDIT: {} ({}) target:{} who:{}".format(a.what,a.detailed_what,a.target_id,a.who_id or a.who_else))

        if commit:
            session().commit()


audit_trail_service = AuditTrailService()
