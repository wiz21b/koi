from koi.configuration.charts_config import MonthlyProductionReportOverviewWidget

if __name__ == "__main__":
    import sys
    from PySide.QtGui import QApplication,QMainWindow

    from koi.base_logging import init_logging
    from koi.Configurator import init_i18n,load_configuration,configuration

    init_logging()
    init_i18n()
    load_configuration()

    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session

    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)

from koi.business_charts import *

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # widget = MonthlyFinancialReportOverviewWidget(None)
    # widget = MonthlyProductionReportOverviewWidget(None)

    global remote_indicators_service
    from koi.charts.indicators_service import IndicatorsService
    from koi.server.json_decorator import JsonCallWrapper

    remote_indicators_service = JsonCallWrapper(IndicatorsService(), JsonCallWrapper.DIRECT_MODE)

    import logging
    mainlog.setLevel(logging.DEBUG)

    dao.set_session( session())
    begin, end = month_before(date.today(),12), date.today()
    remote_indicators_service.clear_caches()

    # widget = ISOIndicatorsWidget(None, remote_indicators_service) # Done
    # widget = FinancialIndicatorsWidget(None, remote_indicators_service) # DONE
    widget = MonthlyProductionReportOverviewWidget(None, remote_indicators_service)

    widget.refresh_action()

    mw = QMainWindow()
    mw.setMinimumSize(1024,768)
    mw.setCentralWidget(widget)
    mw.show()
    app.exec_()
