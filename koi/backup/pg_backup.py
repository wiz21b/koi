import sys
from urllib.parse import urlparse
from email.mime.text import MIMEText
import datetime
import subprocess
import shutil
import glob
import os
import os.path
import shlex
from shutil import copyfile
import re
# from smtplib import SMTP_SSL as SMTP       # this invokes the secure SMTP protocol (port 465, uses SSL)
from smtplib import SMTP                  # use this for standard SMTP protocol   (port 25, no encryption)
import platform
import tempfile
import argparse

from koi.base_logging import mainlog
from koi.datalayer.utils import _extract_db_params_from_url



def _run_shell(cmd, env, logger):

    logger.info("About to run : {}".format(" ".join(cmd)))

    if env and platform.system() == "Windows":

        # For some reason, on widnows, using enviro variables
        # disturbs popen when trying to connect to the DB via psql.
        # I suspect that's more a problem with postgresql authentification
        # scheme, but after playing a bit with PG's config files
        # I wasn't able to turn something up...

        logger.info("We're on Windows, I can't use environment variables...")
        env = None


    try:
        popen = subprocess.Popen( cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, universal_newlines=True)
    except Exception as ex:
        logger.error("Can't run the command because {}".format(ex))
        raise ex

    # I used "poll" to follow the command's execution
    # but there were many issues (Python's doc talks about
    # deadlocks, I think that's what I've seen)

    stdout_data, stderr_data = popen.communicate()

    logger.info(stdout_data)
    logger.info(stderr_data)

    logger.info("Returned {} ".format(int(popen.returncode)))
    return int(popen.returncode)



def size_to_str(s):
    assert s >= 0, "Expected number of bytes"
    units = ['bytes','KB','MB','GB']
    i = 0
    base = 1024
    while s / base > 1 and i < len(units):
        base = base * 1024
        i = i + 1
    return "{:.4} {}".format(float(s)/float(base/1024),units[i])


def dump_and_zip_database(base_configuration):

    # login, password, dbname, host, port = _extract_db_params_from_url(base_configuration.get("Backup","db_url"))

    error = False
    if not base_configuration.get('Commands','pg_dump_cmd'):
        mainlog.error("Missing Commands/pg_dump_cmd in configuration file")
        error = True
    if not base_configuration.get('Backup','db_url'):
        mainlog.error("Missing Backup/db_url in configuration file")
        error = True
    if not base_configuration.get('Backup','prefix'):
        mainlog.error("Missing Backup/prefix in configuration file")
        error = True
    if not base_configuration.get('Backup','backup_directory'):
        mainlog.error("Missing Backup/backup_directory in configuration file")
        error = True

    if error:
        raise Exception("Too many errors, I stop here")


    filename = base_configuration.get("Backup","prefix") + "_" + str(datetime.date.today()) + ".pgbackup"
    final_destination = os.path.join(base_configuration.get('Backup','backup_directory'),filename)

    # custom format will store more and is compressed
    command1 = [base_configuration.get('Commands','pg_dump_cmd'),
                '--format=custom',
                '--file={}'.format(final_destination),
                base_configuration.get("Backup","db_url")]

    mainlog.info("Creating backup : {}".format(" ".join(command1)))
    p1 = subprocess.Popen(command1)
    p1.communicate()
    p1.wait()

    if p1.returncode != 0:
        raise Exception("Unable to run the backup command")
    else:
        mainlog.info("Backup seems fine")

    bytes = os.path.getsize(final_destination)
    mainlog.info("Backup complete, {} bytes saved".format(bytes))

    return final_destination, bytes


def extract_database(dbName, filename, base_configuration):

    user = base_configuration.get('Database','user')
    pw = base_configuration.get('Database','password')
    db_name = base_configuration.get('Database','db_name')

    command1 = [base_configuration.get('Commands','pg_dump'),
                '--format=custom']
    if user:
        command1 += ['--username={}'.format(user)]

    # Password is supplied via .pgpass

    command1 += ['--file={}'.format(filename),db_name]

    command3 = None
    out = None

    if "aescrypt" in base_configuration.get('Commands','encrypt'):
        command3 = [base_configuration.get('Commands','encrypt'),
                    '-e',
                    '-p', base_configuration.get('Backup','encryption_key'),
                    filename]
        out = filename + ".aes"
    elif "gpg2" in base_configuration.get('Commands','encrypt'):
        out = filename + ".gpg"
        command3 = [base_configuration.get('Commands','encrypt'),
                    '-c', '--batch', '-o', out,
                    '--passphrase', base_configuration.get('Backup','encryption_key'),
                    filename]

    else:
        raise Exception("Unsupported encryption program")

    p1 = subprocess.Popen(command1)
    mainlog.info("Creating backup : {}".format(command1))
    p1.wait()

    try:
        os.remove(out)
    except OSError:
        pass

    mainlog.info("Encrypting backup")
    p3 = subprocess.Popen(command3)
    p3.wait()

    return out


def documents_copy_recurring(src_dir, dest_dir, base_configuration):
    """ This is a copy function :-) But it is optimized for recurring
    copy : copying several time from the same koi to the same
    destination. To do that it only copies file from the source
    directory if they are different than those in the backup
    directory
    """

    codename = base_configuration.get("Globals","codename")
    mainlog.info(u"Copying documents from {} to {}".format(src_dir, dest_dir))

    if not os.path.exists(src_dir):
        raise Exception("Source directory for documents doesn't exist")

    if not os.path.exists(dest_dir):
        raise Exception("Destination directory for documents doesn't exist")

    if os.path.abspath(src_dir) == os.path.abspath(dest_dir):
        raise Exception("The source and destination directories are the same")

    total_size = total_files = 0

    nb_files = 0
    for fn in glob.glob( os.path.join(src_dir, codename + "_*")):
        nb_files += 1
        # mainlog.info("Eval {}".format(type(fn)))
        # enc = fn.encode('ascii', 'backslashreplace')
        # mainlog.info("enc")
        # mainlog.info(u"Evaluating {}".format(enc))
        dest = os.path.join( dest_dir, os.path.basename(fn))

        # Copy only if necessary
        if not os.path.exists(dest) or (os.path.getsize(fn) != os.path.getsize(dest)):
            mainlog.info(u"Copying {}".format(fn.encode(sys.getfilesystemencoding(), 'ignore')))

            # Backup is critical so it must fail if something is
            # wrong. Therefore, no exception handling right now

            # Also, I let Python take care of the filename encoding issues

            copyfile(fn, dest)

            total_size += os.path.getsize(fn)
            total_files += 1

    mainlog.info("Scanned {} files".format(nb_files))
    return total_files, total_size, nb_files











from koi.datalayer.database_session import DATABASE_SCHEMA

def full_restore(configuration, backup_directory, backup_file, restore_documents : bool, logger):
    """
    The pgbackup file is read from the backup directory and then restored
    into the postgres database.

    If backup_file is None,  The most recent backup file is automatically
    read from the directory.

    :param backup_file: Full path to backup file
    :param restore_documents: True : restore documents after database;
                              False : do nothing with documents.
    :param logger:
    :return: True if restore successful; False else.
    """
    psql_path = configuration.get("Commands","psql")
    codename = configuration.get("Globals","codename")

    if not psql_path:
        logger.error("The Commands/psql path is not set in the server.cfg")
        logger.info("Please fix the configuration file (on the right)")
        return

    if not configuration.get("Commands","pg_restore"):
        logger.error("The Commands/pg_restore path is not set in the server.cfg")
        logger.info("Please fix the configuration file (on the right)")
        return

    login_clt, password_clt, dummy, dummy, dummy = _extract_db_params_from_url(configuration.get("Database","url"))
    login_adm, password_adm, dbname, host, port = _extract_db_params_from_url(configuration.get("Database","admin_url"))

    logger.info("Beginning restore procedure from this directory : {}".format(backup_directory))

    glob_path = os.path.join(backup_directory,"*.pgbackup")

    max_t = 0
    most_recent_backup = None

    if backup_file:
        most_recent_backup = backup_file
    else:
        for pgbackup in glob.glob(glob_path):
            t = os.path.getmtime(pgbackup)
            if t > max_t:
                max_t = t
                most_recent_backup = pgbackup

        logger.info("Most recent database backup in the directory is {}".format(most_recent_backup))

    logger.info("Restoring database... This may take a minute or two.")
    tmpfile = tempfile.mkstemp(prefix="restore_script", suffix='.psql')
    logger.info(tmpfile[1])

    f = os.fdopen(tmpfile[0],'w')
    sql = """DROP DATABASE IF EXISTS {0};
DROP ROLE IF EXISTS {3};
CREATE DATABASE {0};
CREATE ROLE {3} LOGIN PASSWORD '{4}';
ALTER DATABASE {0} SET search_path TO {9},public
\! {6} -h {7} -p {8} -U {1} --dbname {0} "{5}"
    """.format(dbname, login_adm, password_adm, login_clt, password_clt, most_recent_backup,
               configuration.get("Commands","pg_restore"), host, port, DATABASE_SCHEMA)
    logger.info("About to run this :")
    logger.info(sql)
    f.write(sql)
    f.close()

    cmd = [psql_path,"-h",host,"-p",port,"-U",login_adm,"-d","template1","-f",tmpfile[1]]
    env = { 'PGUSER' : login_adm, 'PGPASSWORD' : password_adm }
    r = _run_shell(cmd, env, logger)

    if r != 0:
        logger.error("Return code not null, something went wrong")
        return False



    if restore_documents:
        doc_root = configuration.get("DocumentsDatabase","documents_root")
        logger.info("Copying the documents database to {}".format(doc_root))

        if doc_root == backup_directory:
            logger.warn("Not copying anything because the documents are already in place")

        glob_path = os.path.join(backup_directory,codename + "_*")
        logger.info("Loading documents with pattern {}".format(glob_path))

        nb_doc = 0
        for document in glob.glob(glob_path):
            logger.info("Copying {} to {}".format(os.path.basename(document),
                                                  os.path.join(doc_root, os.path.basename(document))))
            try:
                # pass
                shutil.copy( document, os.path.join(doc_root, os.path.basename(document)))
                nb_doc += 1
            except Exception as ex:
                logger.error(ex)
                return False

        logger.info("{} document(s) restored.".format(nb_doc))

def send_mail(subject,content,cfg):
    # typical values for text_subtype are plain, html, xml
    text_subtype = 'plain'

    msg = MIMEText(content, text_subtype)
    msg['Subject'] = subject
    msg['From'] = cfg.get('Mail','sender') # some SMTP servers will do this automatically, not all

    if not cfg.get('Mail','SMTPServer'):
        mainlog.error("Mail configuration seems broken. Can't send email.")
        # Since this is backup, failing sending a mail should not stop
        # the execution => no exception thrown
        return

    conn = SMTP(cfg.get('Mail','SMTPServer'))
    conn.set_debuglevel(False)
    # conn.login(cfg.get('Mail','SMTPUser'), cfg.get('Mail','SMTPPassword'))
    try:
        conn.sendmail(cfg.get('Mail','sender'), cfg.get('Mail','destination'), msg.as_string())
    except Exception as ex:
        mainlog.error("Unable to send mail")

    finally:
        conn.close()

    mainlog.info("Mail sent")


def rsync_export_files(db_file, logger):
    """
    This function exports the backup files to another Koi server.

    :param db_file: The file in which the postgres backup was done.
    :param logger:
    :return:
    """

    rsync_cmd = configuration.get("Commands","rsync")
    codename = configuration.get("Globals","codename")

    errors = False
    if not rsync_cmd:
        logger.warn("Can't rsync because the rsync command is not configured")
        errors = True

    rsync_documents_destination = configuration.get("Backup","rsync_documents_destination")

    if not rsync_documents_destination:
        logger.error("Can't rsync because the rsync destination is not configured (so I don't know where to send files)")
        errors = True

    rsync_database_destination = configuration.get("Backup","rsync_database_destination")

    if not rsync_database_destination:
        logger.error("Can't rsync because the rsync database destination is not configured (so I don't know where to send files)")
        errors = True

    restore_backup = configuration.get("Backup","restore_backup")

    if not restore_backup:
        logger.error("Can't restore_backup because restore_backup is not configured")
        errors = True

    if errors:
        return errors


    # Now the database file
    cmd = shlex.split(rsync_database_destination.format(db_file))
    r = _run_shell(cmd, None, logger)
    if r != 0:
        logger.error("Failed shell command")
        errors = True

    # Sync the documents, we let rsync do the job of comparing files, knwooing
    # what to do, etc.
    doc_root = configuration.get("DocumentsDatabase","documents_root")

    cmd = shlex.split( rsync_documents_destination.format(
        os.path.join(doc_root,'{}_*'.format(configuration.get('Globals','codename')))))
    r = _run_shell(cmd, None, logger)
    if r != 0:
        logger.error("Failed shell command")
        errors = True


    r = _run_shell( shlex.split(restore_backup), None, logger)
    if r != 0:
        logger.error("Failed shell command")
        errors = True
    return errors


def restore_procedure():
    full_restore(configuration, configuration.get("Backup","restore_directory"), None, True, mainlog)
    send_mail("Restore SUCCESS",
              "restored",
              configuration)


def backup_procedure( configuration):
    if not configuration.get('Backup','backup_directory'):
        raise Exception("Missing Backup/backup_directory in configuration file")

    backup_dir = configuration.get('Backup','backup_directory')

    try:

        if not os.path.exists(backup_dir):
            os.mkdir(backup_dir)
            mainlog.info("Created backup directory because it was missing")

        mainlog.debug("Backup directory is {}".format(backup_dir))
        # We default to backup behaviour because when
        # this program is run as a scheduled task, we cannot
        # give parameters to it

        mainlog.info("Backing up the database")
        filename, bytes = dump_and_zip_database(configuration)

        mainlog.info("Backing up the documents")
        total_files, total_bytes, scanned_files = documents_copy_recurring(
            configuration.get('DocumentsDatabase', 'documents_root'),
            configuration.get('Backup', 'backup_directory'),
            configuration)
        mainlog.info("Documents copy done. {} files copied ({} bytes), {} files scanned.".format(total_files, size_to_str(total_bytes), scanned_files))

        mainlog.info("Syncing the back up remotely")
        rsync_export_files( filename, mainlog)

        send_mail("Backup SUCCESS",
                  "The backup of was done correctly DB:{}, files: {} / {} bytes.".format(size_to_str(bytes),
                                                                                         total_files,
                                                                                         total_bytes),
                  configuration)

    except Exception as ex:
        mainlog.error("Failed to complete backup")
        mainlog.exception(ex)
        send_mail("Backup FAILURE", "The backup of was *not* done correctly.", configuration)

from koi.backup.bitrot_shield import checksum_directory

if __name__ == "__main__":
    from koi.base_logging import init_logging, mainlog
    import logging
    mainlog.setLevel(logging.DEBUG)
    init_logging("backup.log")
    from koi.Configurator import load_configuration, configuration, get_data_dir
    configuration.load_server_configuration()

    parser = argparse.ArgumentParser(description='Here are the command line arguments you can use :')
    parser.add_argument('--backup',  action='store_true', default=False, help='Backup database and documents')
    parser.add_argument('--restore', action='store_true', default=False, help='Restore database and documents')
    parser.add_argument('--bitrot-shield', action='store_true', default=False, help='Check files in the backup directory against some checksums')

    args = parser.parse_args()

    if args.restore:
        restore_procedure()
    elif args.bitrot_shield:
        if not configuration.get('Backup', 'backup_directory'):
            raise Exception("Missing Backup/backup_directory in configuration file")
        checksum_directory(configuration.get('Backup', 'backup_directory'), mainlog)
    else:
        backup_procedure( configuration)

