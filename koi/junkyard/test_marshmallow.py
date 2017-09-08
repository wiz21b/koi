import json
from pprint import pprint

from marshmallow import fields, Schema, post_load
from marshmallow_sqlalchemy import ModelSchema

from koi.base_logging import init_logging, mainlog
init_logging()

from koi.Configurator import init_i18n,load_configuration,configuration
init_i18n()
load_configuration()

from koi.db_mapping import metadata
from koi.datalayer.database_session import init_db_session

init_db_session(configuration.database_url, metadata, False or configuration.echo_query)

from koi.datalayer.database_session import session
from koi.db_mapping import Employee, FilterQuery, Order, OrderPart, Customer, ProductionFile, Operation



class BaseSchema(ModelSchema):
    class Meta:
        sqla_session = session()



class OperationSchema(BaseSchema):
    class Meta(BaseSchema.Meta):
        model = Operation
        exclude = ['done_hours']


class ProductionFileSchema(BaseSchema):
    operations = fields.Nested( OperationSchema, many=True)
    class Meta(BaseSchema.Meta):
        model = ProductionFile


class OrderPartSchema(BaseSchema):
    production_file = fields.Nested( ProductionFileSchema, many=True)
    class Meta(BaseSchema.Meta):
        model = OrderPart
        exclude = ['total_sell_price','human_identifier','material_value','total_hours',
                   'estimated_time_per_unit', 'total_estimated_time', 'tex2',
                   're_order_part_identifier', 're_label_identifier', 'nb_non_conformities',
                   'state']

class OrderSchema(BaseSchema):
    parts = fields.Nested( OrderPartSchema, many=True)
    class Meta(BaseSchema.Meta):
        model = Order
        exclude = ['user_label', 'state']

class FilterQuerySchema(BaseSchema):
    class Meta(BaseSchema.Meta):
        model = FilterQuery

class EmployeeSchema(BaseSchema):
    filter_queries = fields.Nested(FilterQuerySchema, many=True)
    class Meta(BaseSchema.Meta):
        model = Employee
        exclude = ('password',)

class EmployeeQtSchema(Schema):
    class Meta:
        fields = ("fullname", "employee_id")

    @post_load
    def make_employee(self, data):
        employee = Employee()
        for fname in self.Meta.fields:
            setattr( employee, fname, data[fname])
        return employee



employee_schema = EmployeeSchema()
employee_qt_schema = EmployeeQtSchema()

employee = session().query(Employee).filter(Employee.employee_id == 114).one()

print( employee)
print( json.dumps( employee_schema.dump(employee).data, indent=4))

serialized = """{
    "fullname": "Daniel Dumont",
    "picture_data": null,
    "_roles": "modify_document_templates,modify_monthly_time_track_correction,modify_parameters,timetrack_modify,view_audit,view_financial_information,view_prices,view_timetrack",
    "employee_id": 114,
    "filter_queries": [
        {
            "family": "order_parts_overview",
            "filter_query_id": 1,
            "owner": 114,
            "name": "Finies ce mois",
            "shared": true,
            "query": "CompletionDate in CurrentMonth"
        },
        {
            "family": "order_parts_overview",
            "filter_query_id": 2,
            "owner": 114,
            "name": "Finies mois passe",
            "shared": true,
            "query": "CompletionDate in MonthBefore"
        },
        {
            "family": "order_parts_overview",
            "filter_query_id": 3,
            "owner": 114,
            "name": "En production",
            "shared": true,
            "query": "Status = ready_for_production"
        },
        {
            "family": "order_parts_overview",
            "filter_query_id": 4,
            "owner": 114,
            "name": "Devis",
            "shared": true,
            "query": "Status = preorder"
        },
        {
            "family": "order_parts_overview",
            "filter_query_id": 5,
            "owner": 114,
            "name": "Dormantes",
            "shared": true,
            "query": "Status = production_paused"
        },
        {
            "family": "order_parts_overview",
            "filter_query_id": 6,
            "owner": 114,
            "name": "offres en cours lachaussee",
            "shared": true,
            "query": "Status = preorder and client = lachaussee"
        },
        {
            "family": "order_parts_overview",
            "filter_query_id": 11,
            "owner": 114,
            "name": "suivi production 0.6 54321",
            "shared": false,
            "query": "Status = ready_for_production AND DoneHours > 0.6*PlannedHours"
        },
        {
            "family": "order_parts_overview",
            "owner": 114,
            "name": "ABNSOLUTELY TOTALLY NEW",
            "shared": false,
            "query": "Status = ready_for_production AND DoneHours > 0.9*PlannedHours"
        }
    ],
    "login": "dd",
    "is_active": true
}"""


# res = employee_schema.load( data=json.loads(serialized), session=session())
# employee = res.data
# print( len( employee.filter_queries))

# e = employee_qt_schema.load( data=employee_schema.dump(employee).data).data
# print(e.fullname)

# session().commit()


order_schema = OrderSchema()


# 2017/09/01 07:40:53 [ERROR]   name 'json' is not defined !!!
# timeit.timeit( "json.dumps( order_schema.dump( order).data, indent=4)" )

from datetime import datetime

for i in range(5):
    print()
    session().expunge_all()
    t = datetime.now()
    order = session().query(Order).filter(Order.order_id == 5266).one()
    s = 0
    for i in range(len(order.parts)):
        s += len(order.parts[i].operations)
        if(len(order.parts[i].operations) > 0):
            z = order.parts[i].operations[0].description
    print(s)
    delta = datetime.now() - t
    print( "SQLA {}".format(delta))

    t = datetime.now()
    marsh = order_schema.dump( order).data
    delta = datetime.now() - t
    print( "Marsh {}".format(delta))

    t = datetime.now()
    json.dumps(marsh)
    delta = datetime.now() - t
    print("Json {}".format(delta))


# print( json.dumps( order_schema.dump( order).data, indent=4))
