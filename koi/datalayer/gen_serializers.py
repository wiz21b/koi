import os.path

if __name__ == "__main__":
    import logging
    from koi.base_logging import mainlog,init_logging
    from koi.Configurator import init_i18n
    init_logging()
    init_i18n()

from pyxfer.pyxfer import generated_code, USE, CodeWriter, SKIP, COPY
from pyxfer.sqla_autogen import SQLAAutoGen
from pyxfer.type_support import *

from koi.datalayer.sqla_mapping_base import Base
from koi.doc_manager.documents_mapping import Document
from koi.db_mapping import Order, OrderPart
from koi.datalayer.employee_mapping import Employee
from koi.config_mgmt.mapping import *


def find_sqla_mappers( mapper : 'class'):
    base_mapper_direct_children = [sc for sc in mapper.__subclasses__()]

    d = dict()

    for direct_child in base_mapper_direct_children:
        for c in _find_subclasses( direct_child):
            d[c] = {}

    return d

def _find_subclasses( cls):
    # Handle SQLA inherited entities definitions

    if cls.__subclasses__():
        results = [ cls ]
        for sc in cls.__subclasses__():
            results.extend( _find_subclasses(sc))
        return results
    else:
        return [cls]


def generate_serializers():
    additioanl_code_for_document_dto = """
def __str__(self):
   return self.filename
"""

    additioanl_code_for_article_configuration_dto = """@property
def current_configuration_status(self):
   c = ArticleConfiguration._current_configuration(self)

   if c and c.frozen:
      return "Frozen"
   else:
      return "Not frozen"

@property
def current_configuration_version(self):
   c = ArticleConfiguration._current_configuration(self)
   if c and c.version:
      return c.version
   else:
      return "-"
"""


    additional_code_for_version_status_dto ="""
@property
def version_status(self):
    if self.frozen:
        return "Rev. {}, frozen".format( self.version)
    else:
        return "Rev. {}".format( self.version)

@property
def is_baseline( self):
    return self.version == 0
"""

    additioanl_code_for_impact_line_dto ="""
@property
def approver_short(self):
    if self.approved_by:
        return self.approved_by.login.upper()
    else:
        return ""

@property
def owner_short(self):
    return self.owner.login.upper()

@property
def version(self):
    return ImpactLine._version(self)

@property
def date_upload(self):
    return ImpactLine._date_upload(self)
"""


    model_and_field_controls = find_sqla_mappers( Base)
    model_and_field_controls[Customer]['orders'] = SKIP
    model_and_field_controls[Document] = {
        'order' : SKIP,
        'order_part' : SKIP,
        'quality_event' : SKIP }
    model_and_field_controls[Employee] = {
        'picture_data' : SKIP,
        'filter_queries' : SKIP,
        'roles' : COPY}
    model_and_field_controls[Order] = {
        'parts' : SKIP,
        'tasks' : SKIP,
        'delivery_slip_parts' : SKIP,
        'delivery_slips' : SKIP,
    }
    model_and_field_controls[OrderPart] = {
        'human_position' : SKIP,
        'production_file' : SKIP,
        'operations' : SKIP,
        'delivery_slip_parts' : SKIP,
        'documents' : SKIP,
        'quality_events' : SKIP,
        'configuration' : SKIP }
    model_and_field_controls[ImpactLine] = {
        'article_configuration' : SKIP } #,


    global_cw = CodeWriter()
    global_cw.append_code("from koi.config_mgmt.mapping import ArticleConfiguration, ImpactLine")

    autogen = SQLAAutoGen( SQLADictTypeSupport, ObjectTypeSupport)

    autogen.type_support(ObjectTypeSupport, ArticleConfiguration).additional_global_code.append_code(additioanl_code_for_article_configuration_dto)
    autogen.type_support(ObjectTypeSupport, ImpactLine).additional_global_code.append_code(additioanl_code_for_impact_line_dto)
    autogen.type_support(ObjectTypeSupport, Document).additional_global_code.append_code(additioanl_code_for_document_dto)
    autogen.type_support(ObjectTypeSupport, Configuration).additional_global_code.append_code(additional_code_for_version_status_dto)

    serializers = autogen.make_serializers( model_and_field_controls)
    autogen.reverse()
    serializers2 = autogen.make_serializers( model_and_field_controls)


    #autogen = SQLAAutoGen( SQLATypeSupport, SQLADictTypeSupport)
    autogen.set_type_supports( SQLATypeSupport, SQLADictTypeSupport)
    serializers5 = autogen.make_serializers( model_and_field_controls)
    autogen.reverse()
    serializers6 = autogen.make_serializers( model_and_field_controls)

    # Just for testing

    model_and_field_controls2 = {
        Employee : model_and_field_controls[Employee],
        OrderPart : model_and_field_controls[OrderPart],
        Order : model_and_field_controls[Order],
        Document : model_and_field_controls[Document]
        }

    #pprint(model_and_field_controls2)
    autogen.set_type_supports(SQLATypeSupport, ObjectTypeSupport)
    serializers3 = autogen.make_serializers( model_and_field_controls)
    autogen.reverse()
    serializers4 = autogen.make_serializers( model_and_field_controls)

    # + serializers5 + serializers6
    return generated_code( serializers + serializers2 + serializers3 + serializers4+ serializers5 + serializers6, global_cw)


def write_code( gencode):
    d = os.path.join( os.path.dirname(__file__), "serializers.py")
    with open(d,"w") as fo:
        fo.write( gencode)


if __name__ == "__main__":

    logging.getLogger("pyxfer").setLevel(logging.DEBUG)
    write_code( generate_serializers())
    # Make sure it loads
    from koi.datalayer.serializers import *
