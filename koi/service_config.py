__author__ = 'stc'

from koi.Configurator import configuration
from koi.server.json_decorator import JsonCallWrapper
from koi.charts.indicators_service import IndicatorsService
from koi.doc_manager.documents_service import DocumentsService

if False:
    remote_indicators_service = JsonCallWrapper(IndicatorsService(), JsonCallWrapper.HTTP_MODE)
    remote_documents_service = JsonCallWrapper(DocumentsService(), JsonCallWrapper.HTTP_MODE)
else:
    # remote_indicators_service = JsonCallWrapper(IndicatorsService(), JsonCallWrapper.IN_PROCESS_MODE)
    remote_indicators_service = IndicatorsService()
    # remote_documents_service = DocumentsService()
    remote_documents_service = JsonCallWrapper(DocumentsService(), JsonCallWrapper.HTTP_MODE)

__all__ = ['remote_documents_service', 'remote_indicators_service']


