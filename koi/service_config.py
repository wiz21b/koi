__author__ = 'stc'

from koi.Configurator import configuration
from koi.server.json_decorator import JsonCallWrapper
from koi.charts.indicators_service import IndicatorsService
from koi.doc_manager.documents_service import DocumentsService
from koi.datalayer.filters_dao import FilterService

if False:
    remote_indicators_service = JsonCallWrapper(IndicatorsService(), JsonCallWrapper.HTTP_MODE)
    remote_documents_service = JsonCallWrapper(DocumentsService(), JsonCallWrapper.HTTP_MODE)
    filters_service = JsonCallWrapper( FilterService(), JsonCallWrapper.HTTP_MODE)
else:
    remote_indicators_service = JsonCallWrapper(IndicatorsService(), JsonCallWrapper.IN_PROCESS_MODE)
    # remote_indicators_service = IndicatorsService()
    # remote_documents_service = DocumentsService()
    remote_documents_service = JsonCallWrapper(DocumentsService(), JsonCallWrapper.IN_PROCESS_MODE)
    filters_service = JsonCallWrapper( FilterService(), JsonCallWrapper.IN_PROCESS_MODE)

# The services to actually import on import *
__all__ = ['remote_documents_service', 'remote_indicators_service', 'filters_service']

def request_service( service_name):
    if service_name == 'remote_documents_service':
        return remote_documents_service

