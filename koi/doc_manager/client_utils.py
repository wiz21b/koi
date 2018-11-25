import tempfile
import os.path
import re
import sys

from urllib.request import build_opener,ProxyHandler,HTTPHandler,HTTPSHandler
from http.client import HTTPConnection, HTTPSConnection, OK

from pymediafire import MultiRead

from koi.base_logging import mainlog
from koi.Configurator import configuration
from koi.utils import download_file
import io

class FilePath:
    def __init__(self,path):
        self.path = path

class MultiRead:
    """ This class will present a read()able object to
    the httplib send() method. This object represents
    an HTTP multiple part/form data collection. Each item
    in the collection is either :

    * key value parts
    * files

    This object has the property of allowing httplib to
    work with a read block size. That in turns allows
    us to send files over http wich are bigger than
    the RAM.
    """

    BOUNDARY = '----------ThIs_Is_tHe_bouNdaRY_$' # BUG That's a hack, I can't send myself to mediafire :-)
    CRLF = '\r\n'

    def __init__(self,logger=None):
        if logger:
            self.logger = logger
        else:
            self.logger = DevNullLogger()
        self.to_read = []
        self.current_file_dnx = 0
        self.current_file = None
        self._size = 0

    def add_field(self, key, value):

        L = []
        # L.append('--' + self.BOUNDARY)
        # L.append('Content-Disposition: form-data; name="{}"'.format(key))
        # L.append('')
        # L.append("{}".format(value))

        L.append(u'--' + self.BOUNDARY)
        L.append(u'Content-Disposition: form-data; name="{}"'.format(key))
        L.append(u'')
        L.append(u"{}".format(value))
        data = self.CRLF.join(L) + self.CRLF
        data = bytearray(data, 'utf-8')
        self.to_read.append(data)
        self._size += len(data)


    def add_file_part(self,filepath):

        # Extract the filename... FIXME May have encoding issues
        filename = os.path.split(filepath)[-1]

        # CRLF must be set very accurately to respect http://tools.ietf.org/html/rfc1867
        s = '--' + self.BOUNDARY + self.CRLF
        s += 'Content-Disposition: form-data; name="%s"; filename="%s"' % ('uploaded_file', filename) + self.CRLF
        s += ('Content-Type: %s' % mimetypes.guess_type(filepath)[0] or 'application/octet-stream') + self.CRLF
        s += self.CRLF

        s = bytearray(s, 'utf-8')
        self.to_read.append(s)
        self._size += len(s)

        self.to_read.append(FilePath(filepath))
        s = os.path.getsize(filepath)
        self._size += s

        self.logger.debug(u"Appended {} with {} bytes".format(filepath,s))


    def close_parts(self):
        data = self.CRLF + '--' + self.BOUNDARY + '--' + self.CRLF
        data += self.CRLF
        data = bytearray(data, 'utf-8')
        self.to_read.append(data)
        self._size += len(data)

    def content_type(self):
        return 'multipart/form-data; boundary={}'.format(self.BOUNDARY)

    def total_size(self):
        return self._size

    def open(self):
        self.current_file_ndx = 0
        self.current_file = None
        self._pick_next_file()

    def close(self):
        if self.current_file:
            self.current_file.close()
            self.current_file = None

        self.current_file_ndx = len(self.to_read)

    def _pick_next_file(self):


        if self.current_file_ndx >= len(self.to_read):
            self.current_file = None
            self.logger.debug("Picking next item to upload : reached the end")

        else:
            self.logger.debug("Picking next item to upload : opening one more")
            to_send = self.to_read[self.current_file_ndx]

            if type(to_send) == str or type(to_send) == unicode:
                if sys.version[0] == "2":
                    self.current_file = io.BytesIO(bytearray(to_send.encode('utf-8')))
                else:
                    self.current_file = io.BytesIO(bytes(to_send,'utf-8'))

            # elif type(to_send) == unicode:
            #     self.current_file = StringIO(to_send.encode('utf-8'))
            elif type(to_send) == FilePath:
                self.current_file = open( to_send.path, "rb")
            elif type(to_send) == bytearray:
                self.current_file = io.BytesIO(to_send)
            else:
                raise Exception("Internal error type={}".format(type(to_send)))

            self.current_file_ndx += 1

        return self.current_file


    def read(self,size=None):
        if not size:
            return self._read(size=self.total_size())
        else:
            return self._read(size)

    def _read(self,size=8192):

        if not self.current_file or size == 0:
            return []

        else:
            r = self.current_file.read(size)
            self.logger.debug("Read {}/{} bytes".format(len(r),self.total_size()))

            if not r: # EOF
                self.current_file.close()
                if self._pick_next_file():
                    return self._read(size)
                else:
                    return ''

            elif 0 < len(r) <= size:
                return r

            else:
                raise Exception("Something unbelievable occured : len(r)={}, size={}".format(len(r),size))



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
    """

    :param path:
    :param progress_tracker:
    :param file_id: 0 if uploading a new document, not 0 if repplacing an existing document.
    :param post_url:
    :return:
    """

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

    if configuration.get("DownloadSite","base_url").startswith('https'):
        h = HTTPSConnection(host,port)
    else:
        h = HTTPConnection(host, port)

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
        h.close()
        return file_id
    else:
        raise Exception("Unable to upload, server response status was {}".format(server_response.status))


def upload_template(path, progress_tracker, doc_id):
    mainlog.debug("Uploading template (client utils)")
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

    url = configuration.get("DownloadSite","base_url") + "/download_file?file_id={}".format(doc_id)
    return download_file( url, destination, progress_tracker)


from koi.doc_manager.documents_service import documents_service
from koi.server.json_decorator import JsonCallWrapper

documents_service = JsonCallWrapper( documents_service, JsonCallWrapper.DIRECT_MODE)

def update_name_and_description(document_id, name, description):
    documents_service.update_name_and_description(document_id, name, description)
