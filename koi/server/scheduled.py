__author__ = 'stc'

from datetime import date

from koi.base_logging import init_logging
from koi.Configurator import init_i18n,load_configuration,configuration

init_logging()
init_i18n()
# load_configuration()
load_configuration("server.cfg","server_config_check.cfg")

from koi.base_logging import mainlog, log_stacktrace

from koi.db_mapping import metadata
from koi.datalayer.database_session import init_db_session
init_db_session(configuration.database_url, metadata, False or configuration.echo_query)


from koi.charts.indicators_service import IndicatorsService
from koi.server.json_decorator import JsonCallWrapper
from koi.date_utils import month_before

def refresh_indicators():
    remote_indicators_service = JsonCallWrapper(IndicatorsService(), JsonCallWrapper.DIRECT_MODE)
    begin, end = month_before(date.today(),12), date.today()
    remote_indicators_service.refresh_cached_indicators(begin, end)


from koi.backup.pg_backup import documents_copy_recurring, send_mail, size_to_str, dump_and_zip_database

def backup_database():
    try:
        db_size = dump_and_zip_database(configuration)
        mainlog.info("The backup of Horse was done correctly for the database : {}".format(size_to_str(db_size)), configuration)

        total_files, total_bytes, scanned_files = documents_copy_recurring(
            configuration.get('DocumentsDatabase','documents_root'),
            configuration.get('Backup','backup_directory'))

        mainlog.info("Documents copy done. {} files copied, {} bytes, {} scanned.".format(total_files, total_bytes, scanned_files))
        send_mail("Backup SUCCESS","The backup of Horse was done correctly DB:{}, copied files: {} for a total of {} bytes.".format(size_to_str(db_size),total_files, size_to_str(total_bytes)), configuration)
        mainlog.info("Backup successful")
        exit()
    except Exception as ex:
        mainlog.error("Failed to complete backup")
        mainlog.exception(ex)
        log_stacktrace()
        send_mail("Backup FAILURE","The backup of Horse was *not* done correctly.", configuration)
        exit()


#refresh_indicators()

backup_database()