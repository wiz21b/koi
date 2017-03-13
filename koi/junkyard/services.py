import inspect

from koi.Configurator import configuration
from koi.base_logging import mainlog
from koi.charts.indicators_service import IndicatorsService
from koi.server.json_decorator import HorseJsonRpc
from koi.junkyard.dto_maker import JsonCaller

from koi.datalayer.filters_dao import FilterService
from koi.junkyard.employee_service import EmployeeService

class Services:
    def __init__(self):
        self.indicators = IndicatorsService()
        self.filters = FilterService()
        self.employees = EmployeeService()

    def _register_service_for_client(self, service):
        for m_name,m in inspect.getmembers(service):
            if hasattr(m,'_json_callable'):
                self._json_caller.register_client_http_call(m)

    def _register_service_for_server(self, service, rpc_dispatcher):
        for m_name,m in inspect.getmembers(service):
            if hasattr(m,'_json_callable'):
                rpc_dispatcher[ m.get_service_name()] = self._json_caller.make_func_rpc_server_callable( m)

    def _register_service_for_in_process(self, service):
        registered = 0
        for m_name,m in inspect.getmembers(service):
            if hasattr(m,'_json_callable'):
                self._json_caller.register_in_process_call(m)
                registered += 1

        if registered > 0:
            mainlog.info("Registered {} methods on {}".format(registered, service))
        else:
            mainlog.warn("Registered NO method for {}".format(service))


    def register_for_client(self, session_func, sqla_declarative_base):
        self._json_caller = JsonCaller(session_func, sqla_declarative_base, configuration.get("DownloadSite","base_url"))
        self._register_service_for_client( self.indicators)

    def register_for_server(self, session_func, sqla_declarative_base):
        self._json_caller = JsonCaller(session_func, sqla_declarative_base, configuration.get("DownloadSite","base_url"))
        self.rpc_dispatcher = HorseJsonRpc() # JsonRpc()
        self._register_service_for_server( self.indicators, self.rpc_dispatcher)

    def register_for_in_process(self, session_func, sqla_declarative_base):
        self._json_caller = JsonCaller(session_func, sqla_declarative_base, configuration.get("DownloadSite","base_url"))
        self._register_service_for_in_process( self.indicators)
        self._register_service_for_in_process( self.filters)
        self._register_service_for_in_process( self.employees)


services = Services()