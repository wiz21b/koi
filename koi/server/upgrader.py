

# Deprecated


from urllib.request import build_opener,ProxyHandler,HTTPHandler,HTTPSHandler
from http.client import HTTPConnection


def http_download(download_url, outfile):
    urlopener = build_opener(
        HTTPHandler(),
        HTTPSHandler())

    datasource = urlopener.open(download_url)

    out = open(outfile,'wb')
    while True:
        d = datasource.read(8192)
        # self.logger.debug("Downloaded {} bytes".format(len(d)))
        if not d:
            break
        else:
            out.write( d)
            out.flush()
    out.close()
    datasource.close()


def upgrade(version, horse_dir : str, url : str):
    filename = "horse-{}.zip".format(version)
    dest = os.path.join(horse_dir,filename)

    if url.startswith("http"):
        http_download(download_url, outfile)

    configuration.set("DownloadSite","current_version",str(version))
    configuration.set("DownloadSite","client_path",dest)
    configuration.save()


# http_download('http://localhost:8079/file', "h.zip")