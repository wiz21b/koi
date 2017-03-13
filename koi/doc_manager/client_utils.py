import tempfile
import os.path
import re
import sys
if sys.version[0] == "2":
    from urllib2 import build_opener,ProxyHandler,HTTPHandler,HTTPSHandler
    from httplib import HTTPConnection
else:
    from urllib.request import build_opener,ProxyHandler,HTTPHandler,HTTPSHandler
    from http.client import HTTPConnection, OK

from pymediafire import MultiRead

from koi.base_logging import mainlog
from koi.Configurator import configuration


class Wrap(MultiRead):
    def __init__(self,progress_tracker):
        super(Wrap,self).__init__()
        self.progress_tracker = progress_tracker
        self.total_bytes_read = 0

    def read(self, size=0):
        z = super(Wrap,self).read(size)
        # print("read {}".format(self.total_bytes_read))
        self.total_bytes_read += len(z)
        # mainlog.debug("Wrap: Total bytes read : {}  total_size to send : {} ".format(self.total_bytes_read, self.total_size()))
        self.progress_tracker(self.total_bytes_read / self.total_size() * 100.0)
        return z

def extract_host_port(url):
    from urllib.parse import urlparse
    import re
    p = re.compile(':[0-9]*')
    h = re.compile('.*:')
    netloc = urlparse(url).netloc
    return p.sub( '', netloc), h.sub( '', netloc)



def upload_document(path, progress_tracker=None, file_id = 0, post_url = '/upload_file3'):

    mr = None
    if progress_tracker:
        mr = Wrap(progress_tracker)
    else:
        mr = MultiRead()

    mr.add_field('file_id',str(file_id)) # 0 == It's a new document, > 0 == overwrite

    # We store the filename here 'cos the one encoded in the file part
    # must be ASCII (IETF, RFC 2183, section 2.3 : Current [RFC 2045] grammar
    # restricts parameter values (and hence Content-Disposition filenames)
    # to US-ASCII. We recognize the great desirability of allowing
    # arbitrary character sets in filenames, but it is beyond the
    # scope of this document to define the necessary mechanisms.

    mr.add_field('encoding_safe_filename',os.path.split(path)[-1])
    mr.add_file_part(path)
    mr.close_parts()

    host,port = extract_host_port(configuration.get("DownloadSite","base_url"))
    mainlog.debug(u"Upload to {}:{}{} (determined from DownloadSite/base_url : {})".format(host,port,post_url,configuration.get("DownloadSite","base_url")))
    h = HTTPConnection(host,port)
    h.putrequest('POST', post_url)

    h.putheader('content-type', mr.content_type())
    h.putheader('content-length', str(mr.total_size()))
    h.putheader('x-filesize', str(mr.total_size()))
    h.endheaders()

    mr.open()
    h.send(mr)
    mr.close()

    server_response = h.getresponse()
    if server_response.status == OK:
        server_response.getheaders() # Skip headers (is this really necessary ?)
        t = server_response.read()
        file_id = int(t)
        mainlog.debug("Successfully uploaded {} bytes".format(mr.total_size()))
    else:
        mainlog.error("Unable to upload, server response status was {}".format(server_response.status))
    h.close()

    return file_id

def upload_template(path, progress_tracker, doc_id):
    mainlog.debug("Uploading template (delivery_slips utils)")
    return upload_document(path, progress_tracker=progress_tracker, file_id = doc_id, post_url = '/upload_template_document4')

def instanciate_template(tpl_id):
    urlopener = build_opener(
        HTTPHandler(),
        HTTPSHandler())
    url = configuration.get("DownloadSite","base_url") + "/instanciate_template?tpl_id={}".format(tpl_id)
    op = urlopener.open(url)
    doc_id = int(op.read().decode())
    op.close()
    return doc_id



def remove_document(doc_id):
    urlopener = build_opener(
        HTTPHandler(),
        HTTPSHandler())
    url = configuration.get("DownloadSite","base_url") + "/remove_file?file_id={}".format(doc_id)
    urlopener.open(url)

def remove_documents(doc_ids):
    mainlog.debug("Deleting document {} from server".format(str(doc_ids)))
    urlopener = build_opener(
        HTTPHandler(),
        HTTPSHandler())

    for doc_id in doc_ids:
        mainlog.debug("Deleting document {} from server".format(doc_id))
        url = configuration.get("DownloadSite","base_url") + "/remove_file?file_id={}".format(doc_id)
        urlopener.open(url)

def download_document(doc_id, progress_tracker = None, destination = None):
    """ Download document to a given or temporary file. The temporary file
    name reflects the original name and extension.

    :param progress_tracker: a progress tacker
    :param destination: Where to store the file (full path, with filename).
    :return: the full path to the downloaded file. You'll have to delete that
    file if you need to.
    """

    urlopener = build_opener(
        HTTPHandler(),
        HTTPSHandler())

    url = configuration.get("DownloadSite","base_url") + "/download_file?file_id={}".format(doc_id)
    mainlog.debug(u"Downloading from {}".format(url))
    datasource = urlopener.open(url)

    content_disposition_download_regex = re.compile("attachment; +filename=\"([^\"]+)\"")

    server_filename = content_disposition_download_regex.match(datasource.info()['Content-Disposition']).group(1)

    if not server_filename:
        raise Exception("Missing file name in download")

    # FIXME there's a nasty encoding issue here...
    # The filename is expected to be unicode, but I've doubts on that...

    # try:
    #     server_filename = server_filename.decode('utf-8')
    # except Exception as ex:
    #     mainlog.exception(ex)
    #     try:
    #         server_filename = server_filename.decode('iso-8859-1')
    #     except Exception as ex:
    #         # Pray it works :-)
    #         pass

    if destination:
        outfile_name = destination
    else:
        outfile_name = os.path.join( tempfile.gettempdir(), server_filename)

    mainlog.debug(u"Storing file in {}".format(outfile_name))

    out = open(outfile_name,'wb')
    total_downloaded = 0

    while True:
        d = datasource.read(8192)
        total_downloaded += len(d)
        if progress_tracker:
            progress_tracker(total_downloaded)

        # self.logger.debug(u"Downloaded {} bytes".format(len(d)))
        if not d:
            break
        else:
            out.write( d)
            out.flush()
    out.close()

    mainlog.debug(u"Downloaded {}".format(outfile_name))
    return outfile_name


from koi.doc_manager.documents_service import documents_service
from koi.server.json_decorator import JsonCallWrapper

documents_service = JsonCallWrapper(documents_service,JsonCallWrapper.HTTP_MODE)

def update_name_and_description(document_id, name, description):
    documents_service.update_name_and_description(document_id, name, description)

