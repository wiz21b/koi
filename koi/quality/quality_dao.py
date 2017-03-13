from datetime import datetime

from sqlalchemy.orm.session import make_transient
from sqlalchemy.orm import joinedload

from koi.datalayer.database_session import session
from koi.datalayer.RollbackDecorator import RollbackDecorator
from koi.session.UserSession import user_session

from koi.datalayer.quality import QualityEvent, QualityEventType
from koi.db_mapping import Order, OrderPart
from koi.doc_manager.documents_mapping import Document
from koi.datalayer import generic_access
from koi.datalayer.quality import re_non_conformity_label

class QualityDao:

    @RollbackDecorator
    def find_by_id(self, quality_event_id, commit=True):
        res = session().query(QualityEvent).filter(QualityEvent.quality_event_id == quality_event_id).one()

        if commit:
            session().commit()

        return res


    @RollbackDecorator
    def find_by_label(self, label):
        if not label:
            return None

        m = re_non_conformity_label.match(label)
        ignored_order_part_label, quality_event_id = m.groups()[0], m.groups()[1]

        r = self.find_by_id(quality_event_id)
        make_transient(r)
        return r

    @RollbackDecorator
    def find_by_order_id(self, order_id : int):

        res = session().query(QualityEvent).join(OrderPart).join(Order).filter(Order.order_id == order_id).options(joinedload('who')).all()

        for qe in res:
            make_transient(qe)
            make_transient(qe.who)

        session().commit()

        return res


    @RollbackDecorator
    def find_by_order_part_id(self, order_part_id):

        res = session().query(QualityEvent).filter(QualityEvent.order_part_id == order_part_id).all()

        for qe in res:
            make_transient(qe)

        session().commit()

        return res


    @RollbackDecorator
    def make(self, kind, order_part_id : int, commit = True):

        qe = QualityEvent()
        qe.kind = kind
        qe.order_part_id = order_part_id
        qe.when = datetime.now()
        qe.who_id = user_session.user_id

        session().add(qe)

        if commit:
            session().commit()

        return qe


    @RollbackDecorator
    def save_or_update(self, qe_dto, commit = True):
        qe_session = generic_access.defrost_to_session(qe_dto, QualityEvent)

        for doc_dto in qe_dto.documents:
            doc_session = generic_access.defrost_to_session(doc_dto, Document)
            if doc_session not in qe_session.documents:
                qe_session.documents.add(doc_session)

        deleted_ids = [doc.document_id for doc in qe_dto.documents._deleted]
        if deleted_ids:
            for doc in session().query(Document).filter( Document.document_id.in_(deleted_ids)).all():
                # I do this to allow SQLAclhemy to update relationships.
                # useing a  query(...).delete() won't work (see caveats in SQLAlchemy's doc)
                session().delete(doc)


        if commit:
            session().commit()
