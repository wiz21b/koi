import sqlalchemy
from datetime import datetime
from datetime import date
from pprint import pprint
import logging
import inspect
import timeit

from koi.Configurator import init_i18n
init_i18n()

from koi.base_logging import init_logging, mainlog
init_logging()

from koi.Configurator import init_i18n,load_configuration,configuration
init_i18n()
load_configuration()

from koi.db_mapping import metadata
from koi.datalayer.database_session import init_db_session

init_db_session(configuration.database_url, metadata, False or configuration.echo_query)


from koi.datalayer.database_session import session
from koi.db_mapping import Employee, FilterQuery, Order, OrderPart, Customer, ProductionFile
from koi.junkyard.dto_maker import JsonCaller, JsonCallable, Tuple, Sequence
from koi.datalayer.sqla_mapping_base import Base
from koi.junkyard.services import Services


""" When one wants to store an SQLA object, he needs to get the PK in return.
If the object has relationships, then PK should be set down each the relationships.
Therefore, in that case, it is natural that in_recursion == out_recursion.

"""


@JsonCallable( in_recursion= { Order.customer, Order.parts, OrderPart.production_file, ProductionFile.operations },
               out_recursion= { Order.customer, Order.parts, OrderPart.production_file, ProductionFile.operations  })
def save_or_update_order( order : Order) -> Order:
    session().commit()
    return order

@JsonCallable( in_recursion= { FilterQuery.owner }, out_recursion= { FilterQuery.owner })
def store_filter_query( filter_query : FilterQuery = None) -> FilterQuery:
    mainlog.debug("store_filter_query type={}".format(type(filter_query)))
    mainlog.debug("store_filter_query {}".format(filter_query.query))
    session().commit()
    # session().rollback()
    return filter_query

@JsonCallable( out_recursion= { FilterQuery.owner })
def load_customer( customer_id : int, id2 : int) -> Tuple( Customer, FilterQuery):
    customer = Customer()
    customer.fullname = "hhhh"

    employee = Employee()
    employee.fullname = 'Dijkstra'
    fq = FilterQuery()
    fq.owner = employee

    return (customer, fq)

@JsonCallable()
def check_base_types( d : date, f : float, s : str) -> Tuple(date, float, str):
    return d,f*2,s+s

@JsonCallable()
def all_customers() -> Sequence(sqlalchemy.util._collections.KeyedTuple):
    res = session().query(Employee.fullname, Employee.login).all()
    session().commit()
    return res


class TestService:

    @JsonCallable()
    def check_base_types( self, d : date, f : float, s : str) -> Tuple(date, float, str):
        return d,f*2,s+s



if __name__ == '__main__':

    from koi.junkyard.dto_maker import SQLAMetaData, keyed_tuple_sequence_to_jsonable, KeyedTuplesSequence, jsonable_to_keyed_tuple_sequence
    from koi.charts.indicators_service import indicators_service

    sqla_metadata = SQLAMetaData(session, Base)
    json_caller = JsonCaller( session, Base, configuration.get("DownloadSite","base_url"))
    from jsonrpc2 import JsonRpc
    rpc = JsonRpc()

    from koi.dao import dao

    # Testing Keyed tuples sequence serialization ----------------------------

    from sqlalchemy.util import KeyedTuple

    data = [ KeyedTuple( ['a', date.today(), 123], ['name','birthdate','age']),
             KeyedTuple( ['b', date.today(), 99],  ['name','birthdate','age']) ]

    kts= KeyedTuplesSequence( [str, date, int], ['name','birthdate','age'] )
    res = keyed_tuple_sequence_to_jsonable(sqla_metadata, set(), kts, data)
    pprint(res)
    res = jsonable_to_keyed_tuple_sequence(sqla_metadata, set(), kts, res)
    pprint(res)
    exit()


    # Testing the simple RollbackDecorator -----------------------------------

    dao.operation_definition_dao.all_on_order_part()


    # Testing a service in process -------------------------------------------

    services = Services()
    services.register_for_in_process(session, Base)


    employee = Employee()
    employee.fullname = "Sussman"
    employee = services.employees.save(employee)

    mainlog.debug("Employee ID = {}".format(employee.employee_id))
    filter_query = FilterQuery()
    filter_query.query = "all the stuff"
    filter_query.owner = employee
    filter_query.owner_id = employee.employee_id
    filter_query.shared = True
    filter_query.family = "public"
    filter_query.name = "QueryOne" + str(datetime.now().timestamp()) # avoid unique constraints violation

    services.filters.save(filter_query)


    services.filters.is_name_used("jjj", 12, "kkk")
    services.filters.usable_filters(1,"public")
    exit()

    # Testing fields types analyser ------------------------------------------
    # print(sqla_metadata.fields_converters(OrderPart))
    # exit()


    # Testing real call ------------------------------------------------------
    #mainlog.setLevel( logging.ERROR)

    # mainlog.debug("id1 : {}".format(id(JsonCaller)))
    #
    # services = Services()
    # services.register_for_client(session, Base)
    # services.indicators.number_of_customer_non_conformity_chart(date(2016,1,1), date(2017,1,1))
    #
    # exit()

    services = Services()
    services.register_for_client(session, Base)

    # Destructured call ------------------------------------------------------

    # json_req = json_caller.build_client_side_rpc_request(indicators_service.number_of_customer_non_conformity_chart, date(2016,1,1), date(2017,1,1) )
    # pprint(json_req)
    # rpc['service.number_of_customer_non_conformity_chart'] = json_caller.make_func_rpc_server_callable( indicators_service.number_of_customer_non_conformity_chart)
    # res = rpc(json_req)
    # pprint(res)
    #
    # mainlog.debug("id2 : {}".format(id(JsonCaller)))
    # json_caller.register_in_process_call( indicators_service.number_of_customer_non_conformity_chart)
    # res = indicators_service.number_of_customer_non_conformity_chart(date(2016,1,1), date(2017,1,1))
    #
    # mainlog.debug("res = {}".format(res.data))
    #
    # json_caller.register_client_http_call( indicators_service.number_of_customer_non_conformity_chart)
    # res = indicators_service.number_of_customer_non_conformity_chart(date(2016,1,1), date(2017,1,1))
    #
    # exit()


    rpc = JsonRpc()
    rpc['service.load_customer'] = json_caller.make_func_rpc_server_callable(load_customer)
    rpc['service.check_base_types'] = json_caller.make_func_rpc_server_callable( check_base_types)
    rpc['service.all_customers'] = json_caller.make_func_rpc_server_callable( all_customers)
    rpc['service.store_filter_query'] = json_caller.make_func_rpc_server_callable( store_filter_query)

    test_service = TestService()
    rpc['test_service.check_base_types'] = json_caller.make_func_rpc_server_callable( test_service.check_base_types)

    # Test a function call with various data types
    pprint( check_base_types(date.today(), 42.3, "éléonore" ))

    # Test calling a method (not a function)
    pprint( json_caller.build_client_side_rpc_request(test_service.check_base_types, date.today(), 42.3, "éléonore" ) )

    # Test SQLA keyed tuples as returned values
    json_caller.register_in_process_call( all_customers)
    pprint( all_customers() )

    # Build a json rpc request
    json_req = json_caller.build_client_side_rpc_request(check_base_types, date.today(), 42.3, "éléonore" )
    pprint(json_req)

    # Test JsonRpc dispatcher with a JSON request (mimics cherrypy's behaviour)
    pprint(rpc(json_req))


    # Test with SQLA entities
    filter_query = FilterQuery()
    employee = Employee()
    employee.fullname = "Sussman"
    filter_query.query = "all the stuff"
    filter_query.owner = employee
    filter_query.shared = True
    filter_query.family = "public"
    from datetime import datetime
    filter_query.name = "QueryOne" + str(datetime.now().timestamp()) # avoid unique constraints violation


    json_caller.register_in_process_call( store_filter_query)

    mainlog.debug(" -"*100)
    json_req = json_caller.build_client_side_rpc_request(store_filter_query, filter_query )
    res = rpc(json_req)
    pprint(res)

    mainlog.setLevel( logging.ERROR)
    print( "Time per call = {} sec.".format(
        timeit.timeit(
            lambda : rpc(
                json_caller.build_client_side_rpc_request(store_filter_query, filter_query )), number=100) / 100))

    # # Actual HTTP call
    # json_caller.register_client_http_call( check_base_types)
    # pprint(check_base_types(date.today(), 42.35, "éléonore" ))

    exit()

    # customer = Customer()
    # order = Order()
    # order.customer = customer
    #
    # for i in range(100):
    #     order_part = OrderPart()
    #     order_part.description = "Lorem ipsum dolor blah blah " + " test " * i
    #     order_part.position = i
    #     order.parts.append(order_part)
    #
    #     pf = ProductionFile()
    #     order_part.production_file.append(pf)
    #     for j in range(10):
    #         operation = Operation()
    #         operation.description = order_part.description + str(j)
    #         pf.operations.append(operation)
    #
    # import  logging
    # mainlog.setLevel( logging.ERROR)
    # import timeit
    #
    # res = timeit.timeit(lambda : json_test_harness(save_or_update_order, order), number=10)
    #
    # mainlog.setLevel( logging.DEBUG)
    # mainlog.debug("Execution {:.3} second".format(res))
    # exit()

    filter_query = FilterQuery()
    employee = Employee()
    employee.fullname = "Sussman"
    filter_query.query = "all the stuff"
    filter_query.owner = employee
    filter_query.family = "public"
    filter_query.name = "QueryOne"

    assert filter_query.filter_query_id == None
    res_filter_query = json_test_harness(store_filter_query, filter_query)
    assert res_filter_query.filter_query_id >= 0

    mainlog.debug("Recalling with owner : {}".format(res_filter_query.owner))
    res2 = json_test_harness(store_filter_query, res_filter_query)
    assert res2.filter_query_id == res_filter_query.filter_query_id, "We were updating so PK's should not have changed"
    assert res2.owner.employee_id== res_filter_query.owner.employee_id, "We were updating so PK's should not have changed"
    exit()

    customer = Customer()
    customer.fullname = "hhhh"

    c1,fq= json_test_harness(load_customer, 123, 456)
    pprint(fq.owner.fullname)
    exit()

    func = load_customer
    func_params = [123, 456]
    proto_params = signature(func._original_func).parameters
    return_proto_params = signature(func._original_func).return_annotation

    intermediate = params_to_jsonable( proto_params, func_params)
    mainlog.debug("intermediate : {}".format(intermediate))

    p = jsonable_to_params( proto_params, intermediate)
    mainlog.debug("Result : {}".format(p))

    intermediate = jsonable_to_json(return_values_to_jsonable(return_proto_params, (customer, customer, filter_query)))
    mainlog.debug("intermediate : {}".format(intermediate))
    rp = jsonable_to_return_values(return_proto_params, json_to_jsonable(intermediate))
    mainlog.debug("Result return : {}".format(rp))

    exit()



    # dispatch_server_side_call(load_customer, [10])
    # exit()

    filter_query = FilterQuery()
    employee = Employee()
    filter_query.owner = employee

    customer = Customer()
    customer.fullname = "hhhh"

    session().add(customer)

    order = Order()
    order.customer = customer
    session().add(order)
    session().commit()

    order = session().query(Order).first()
    pprint(order)


    pprint(sqla_to_dict(metadata,Customer, customer, recursive=set()))

    pprint(
        dict_to_sqla(
            metadata,
            Customer,
            sqla_to_dict(metadata, Customer, customer, recursive=set())))



    pprint(sqla_to_dict(metadata, Order, order))
    print( json.dumps(
        sqla_to_dict(metadata, Order, order, recursive=set(['customer'])),
        default=default_encoder,
        sort_keys=True, indent=4))

    mainlog.debug("Order in/out")
    mainlog.debug(
        dict_to_sqla(metadata, Order,
            sqla_to_dict(metadata, Order, order, recursive=set(['customer']))))

