import os.path
from datetime import date

from koi.Configurator import mainlog,configuration

from koi.datalayer.RollbackDecorator import RollbackDecorator
from koi.datalayer.database_session import session
from koi.datalayer.generic_access import all_non_relation_columns, defrost_to_session, as_dto
from koi.datalayer.audit_trail_service import audit_trail_service
from koi.db_mapping import Order,OrderPart
from koi.doc_manager.documents_mapping import *

from koi.server.json_decorator import JsonCallable, ServerErrors, ServerException

from sqlalchemy.orm.session import make_transient
from sqlalchemy.orm import with_polymorphic

class DocumentsService(object):
    def __init__(self):
        pass

    @JsonCallable([str])
    def find_category_by_short_name(self, short_name : str):
        r = session().query( *all_non_relation_columns(DocumentCategory)).filter(DocumentCategory.short_name == short_name).one()
        session().commit()
        return r

    @JsonCallable([])
    def categories(self):
        r = session().query( *all_non_relation_columns(DocumentCategory)).order_by(DocumentCategory.short_name).all()
        session().commit()
        mainlog.debug("categories() : {}".format(r))
        return r

    @JsonCallable([int, int])
    def set_document_category(self, document_id : int, category_id : int):
        category = session().query(DocumentCategory).filter(DocumentCategory.document_category_id == category_id).one()
        """@type : DocumentCategory"""

        doc = session().query(Document).filter(Document.document_id == document_id).one()
        """@type : Document"""

        doc.document_category_id= category.document_category_id
        session().commit()


    @JsonCallable([str])
    def reference_to_document_id(self, horse_reference : str):

        # Only the document with a non-empty reference can be matched (because of
        # the unique constraint)
        assert horse_reference

        doc_id = session().query(TemplateDocument.document_id).filter(TemplateDocument.reference == horse_reference).scalar()
        session().commit()
        return doc_id

    @JsonCallable([int])
    @RollbackDecorator
    def find_by_id(self, document_id : int):
        # Polymorphic !!!
        q = with_polymorphic(Document,[TemplateDocument])
        doc = session().query(q).filter(Document.document_id == document_id).one()
        make_transient(doc)
        session().commit()
        return doc


        # c = all_non_relation_columns(Document)
        #
        # # Outer join because a document might not be tied to
        # # to an order.
        #
        # doc = session().query(Order.order_id, *c).outerjoin(Document.order).filter(Document.document_id == document_id).one()
        # session().commit()
        # return doc


    @RollbackDecorator
    def path_to_file(self, document_id):
        """ The file system path to a document stored in our database
        """

        filename = session().query(Document.filename).filter(Document.document_id == document_id).scalar()
        path = self._make_path_to_document(document_id, filename)
        # path = session().query(Document.server_location).filter(Document.document_id == document_id).scalar()
        session().commit()
        mainlog.debug(u"path_to_file for document id {} is {}".format(document_id, path))
        return path

    @JsonCallable([int])
    @RollbackDecorator
    def delete(self, document_id : int):
        # This is expected to work polymorphically on Documents' children.
        # So you can delete anything that inherits from Document.

        mainlog.debug("delete document id {}".format(document_id))

        doc = session().query(Document).filter(Document.document_id == document_id).one()

        self._remove_file_from_storage(doc.document_id)

        session().delete(doc) # Cascade to order_part / order <-> document association table
        audit_trail_service.record("DOCUMENT_DELETED","", document_id, commit=False)
        session().commit()


    @JsonCallable([int, str, str])
    @RollbackDecorator
    def update_name_and_description(self, document_id : int, name : str, description : str):

        if not name:
            raise ServerException(ServerErrors.file_name_cannot_be_empty)
            # file_name_cannot_be_empty
            # raise Exception("Name cannot be empty")

        mainlog.debug('Renaming doc:{} to:{} with description:{}'.format(document_id, name, description))
        try:
            self._rename_file_in_storage(document_id, name)
        except Exception as ex:
            mainlog.error("Could not rename document {}".format(document_id))
            mainlog.exception(ex)

        doc = session().query(Document).filter(Document.document_id == document_id).one()
        doc.description = description or ""
        doc.filename = name
        audit_trail_service.record("DOCUMENT_RENAMED","", document_id, commit=False)
        session().commit()


    @RollbackDecorator
    def update_description(self, document_id, description):
        doc = session().query(Document).filter(Document.document_id == document_id).one()
        doc.description = description or ""
        session().commit()



    @RollbackDecorator
    def save(self, document_id, file_handle, file_name, description):
        """ If document id is None (or 0), a new document is added to our database.
        Else an old one is overwritten.

        We ask for a file handle because we expect the file to
        come from the web server (that's the way cherrypy does it).
        """

        mainlog.debug(u"save(): id:{} fh:{} fn:{} d:{}".format(document_id, file_handle, file_name, description))

        c = all_non_relation_columns(Document)
        document = None
        if document_id:
            document = session().query(*c).filter(Document.document_id == document_id).one()
            session().commit()
        else:
            document = Document()
            session().add(document)

        document.filename = file_name
        document.upload_date = date.today()
        document.description = description or ""

        # I need the id to store on the file system.
        # But to get the server_location, I need to store on the filesystem
        # => catch 22

        document.server_location = "DUMMY"
        document.file_size = 666

        if not document.document_id:
            session().flush() # get an id

        document.server_location, document.file_size = self._copy_file_to_storage(file_handle, document.document_id, file_name)
        doc_id = document.document_id
        audit_trail_service.record("DOCUMENT_CREATED","", document.document_id, commit=False)
        session().commit()

        mainlog.debug("Saved to document {}".format(doc_id))
        return doc_id

    @RollbackDecorator
    def associate_to_order_part( self, order_part_id, documents_ids):
        if not isinstance(documents_ids,list):
            documents_ids = [documents_ids]

        opart = session().query(OrderPart).filter(OrderPart.order_part_id == order_part_id).one()
        documents = session().query(Document).filter(Document.document_id.in_(documents_ids)).all()
        opart.documents.clear()
        opart.documents.update(documents)
        session().commit()


    @JsonCallable([])
    @RollbackDecorator
    def all_templates(self):
        # docs = session().query(TemplateDocument).order_by(TemplateDocument.reference).all()
        # return as_dto(docs)

        c = all_non_relation_columns(TemplateDocument)
        r = session().query(*c).select_from(TemplateDocument).order_by(TemplateDocument.reference).all()
        # if r:
        #     mainlog.debug("all_templates : keys={}".format(str(r[0].keys())))
        #     mainlog.debug("all_templates : {}".format(str(r)))
        session().commit()
        return r

    @RollbackDecorator
    def all_documents(self):
        """
        :return: All documents, templates included (so this is polymorphic)
        """
        r = session().query(Document).all()

        for d in r:
            make_transient(d)

        session().commit()
        return r

    @RollbackDecorator
    def save_template(self, file_handle, file_name):
        """ A new template document is added to our database.

        We ask for a file handle because we expect the file to
        come from the web server (that's the way cherrypy does it).

        :returns the doc id of the file
        """

        mainlog.debug(u"save_template(): fh:{} fn:{}".format(file_handle, file_name))

        document = TemplateDocument()
        document.filename = file_name
        document.upload_date = date.today()
        document.server_location = "DUMMY"
        document.file_size = 666

        session().add(document)
        session().flush() # get an id

        document.server_location, document.file_size = self._copy_file_to_storage(file_handle, document.document_id, file_name)
        doc_id = document.document_id
        audit_trail_service.record("TEMPLATE_CREATED","", document.document_id, commit=False)
        session().commit()

        mainlog.debug("Saved to template doc_id={}, bytes={}".format(doc_id, document.file_size))
        return doc_id


    @RollbackDecorator
    def replace_template(self, template_id, file_handle, file_name):
        """ A new template document replaces an old one in our database.

        We ask for a file handle because we expect the file to
        come from the web server (that's the way cherrypy does it).
        """

        mainlog.debug(u"replace_template(): doc_id:{}, fh:{} fn:{}".format(template_id, file_handle, file_name))

        document = session().query(TemplateDocument).filter(TemplateDocument.template_document_id == template_id).one()
        document.filename = file_name
        document.upload_date = date.today()
        document.server_location = "DUMMY"
        document.file_size = 666

        document.server_location, document.file_size = self._copy_file_to_storage(file_handle, document.document_id, file_name)
        doc_id = document.document_id # save for use after session's flushed
        audit_trail_service.record("TEMPLATE_REPLACED","", document.document_id, commit=False)
        session().commit()

        mainlog.debug("Replaced template {}".format(doc_id))
        return doc_id


    @RollbackDecorator
    def copy_template_to_document(self, template_id):
        tpl = session().query(TemplateDocument).filter(TemplateDocument.template_document_id == template_id).one()
        doc_id = None
        with open(tpl.server_location,'rb') as f:
            doc_id = self.save(None, f, tpl.filename, tpl.description)

        audit_trail_service.record("TEMPLATE_INSTANCIATED","", template_id, commit=False)
        session().commit()

        return doc_id

    @RollbackDecorator
    def update_template_description(self, template_id, description, filename, reference):
        """

        :param template_id:
        :param description:
        :param reference:
        :return:
        """

        if not filename:
            raise Exception("Filename can't be empty")

        tpl = session().query(TemplateDocument).filter(TemplateDocument.template_document_id == template_id).one()
        tpl.description = description or ""
        tpl.filename = filename or None # See comments in mapping
        tpl.reference = reference or None # See comments in the data model
        session().commit()

    @RollbackDecorator
    def associate_to_order( self, order_id, documents_ids, commit=True):
        """ Associate the order to the documents. Previous associations
        are discarded.
        """

        order = session().query(Order).filter(Order.order_id == order_id).one()
        order.documents.clear()

        if documents_ids:
            if not isinstance(documents_ids,list):
                documents_ids = [documents_ids]

            documents = session().query(Document).filter(Document.document_id.in_(documents_ids)).all()
            order.documents.update(documents)

        if commit:
            session().commit()

    @RollbackDecorator
    def find_by_order_id(self, order_id):
        docs = session().query(Document.document_id, Document.filename, Document.file_size, Document.description).join(documents_orders_table).filter(documents_orders_table.c.order_id == order_id).all()

        session().commit()
        return docs

    @RollbackDecorator
    def find_by_order_part_id(self, order_id):
        docs = session().query(Document.document_id, Document.filename, Document.file_size, Document.description).join(documents_orders_table).filter(documents_order_parts_table.c.order_part_id == order_part_id).all()

        session().commit()
        return docs

    def _rename_file_in_storage(self, doc_id, new_name):
        full_path = self.path_to_file(doc_id)
        new_path = self._make_path_to_document(doc_id, new_name)
        os.rename(full_path, new_path)

    def _remove_file_from_storage(self, doc_id):
        # full_path = self._make_path_to_document(doc_id)
        full_path = self.path_to_file(doc_id)
        os.remove(full_path)


    def _copy_file_to_storage(self, file_handle, doc_id, filename):

        self._ensure_document_storage()
        full_path = self._make_path_to_document(doc_id, filename)

        out = open(full_path,'wb')
        total_size = 0
        while True:
            d = file_handle.read(8192)
            total_size += len(d)
            if len(d) > 0:
                out.write(d)
            else:
                break
        out.close()

        file_handle.close()
        return full_path, total_size


    def _ensure_document_storage(self):
        doc_root = configuration.get("DocumentsDatabase","documents_root")

        if not os.path.exists(doc_root) or not os.path.isdir(doc_root):
            raise Exception("The storage path {} is not a directory")

    def _make_path_to_document(self, doc_id, filename):
        # The path must be absolute because CherryPy likes it
        # when it serves files.

        doc_root = configuration.get("DocumentsDatabase","documents_root")
        if not doc_root:
            raise Exception("Can't find the document root directory in the configuration, so I'll be unable to locate documents..")

        fs_encoding = 'ISO-8859-1' # FIXME Put that in the server config file
        if os.path.supports_unicode_filenames:
            fs_encoding = 'UTF-8'
        else:
            mainlog.warning("File system doesn't support unicode...")

        fn = u"{}_{}_{}".format(configuration.get("Globals","codename"),doc_id,filename)
        fn = fn.encode(fs_encoding,'replace').decode(fs_encoding).replace('?','_')
        fn = fn.replace( os.sep, '_')
        fn = fn.replace( ' ', '_')

        return os.path.join(doc_root, fn)




documents_service = DocumentsService()
