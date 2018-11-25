__author__ = 'stc'

from urllib.request import build_opener, HTTPHandler, HTTPSHandler
import re
from datetime import datetime, timedelta
import tempfile
import os

from koi.Configurator import mainlog


class SourceFunctionDecorator:
    """ META Decorator.

    Decorator inherited from this class will be
    able to reach the source function that was
    decorated first in the decorators chain.
    The source function is available through the _original_func attribute.

    Inheriting from here also gives you enough power
    to decorate functions and methods, so you don't have to supply
    your own __get__ and __call__ methods.

    Don't forget to call super().__init__ if you inherit this!
    """

    def __init__(self, func_or_decorator):

        self._decorated_func = func_or_decorator
        # self._instance = None

        # Since the decoration occurs at class construction time,
        # The function we received is not bound to any instance
        # So we'll have to fiddle a bit to figure out the instance
        # on which the 'original_func' is called

        # Now we keep a link to the source function, the one
        # that was decorated first.

        mainlog.debug("SourceFunctionDecorator : __init__ decorating {}".format(func_or_decorator))
        if hasattr(func_or_decorator, "_original_func"):
            mainlog.debug("{} has the _original_func".format(func_or_decorator))
            self._original_func = getattr(func_or_decorator, "_original_func")
        else:
            mainlog.debug("{} has *not* the _original_func".format(func_or_decorator))
            self._original_func = func_or_decorator

        # mainlog.debug("SourceFunctionDecorator : decorated! : {}".format(self._original_func))

    def __getattr__(self, name):
        # This will be called if the attribute named name is not found here
        # (so self._decorated_func is not concerned)
        # Notice I get the attr from the decorated func instead of original func.
        # This way I hope (not tested) that this will be applied recursively
        # along the chain of decorators until an attribute with the given name
        # is found.

        return getattr(self._decorated_func, name)

    def is_method(self):
        return hasattr( self, '_instance')

    def __get__(self, instance, cls=None):
        # This is a huge dirty fix. It makes sure that if one calls this
        # through object dispatching (self.xxxx()), then 'self' will be known
        # to us. This is important to have the right parameters when
        # calling the decorated functions (that is, if the function is an
        # object's method, then we need to add the 'self' parameter at the beginning
        # of the parameters list).

        # This works because on accessing the decorated method, Python actually
        # accesses this decorator. When that is done, Python sees it as a
        # descriptor because it has the __get__ method. Upon that, Python calls
        # the __get__ method. There, we have the opportunity to find the
        # instance of the method (which we don't know because the decorator
        # is built at class definition time...)

        # mainlog.debug("__get__ was called instance={}, class={} (I am {})".format(instance, cls, self))
        # Not __getattr__ !!!
        self._instance = instance
        return self

    def __call__(self,*args,**kwargs):
        # mainlog.debug("SourceFunctionDecorator.__call__ args are {} {}".format(args, kwargs))
        if hasattr(self, '_instance'):
            # mainlog.debug("SourceFunctionDecorator.__call__ as method (I am {})".format(self))
            return self._decorated_func(self._instance,*args,**kwargs)
        else:
            # mainlog.debug("SourceFunctionDecorator.__call__ as function (I am {})".format(self._decorated_func))
            return self._decorated_func(*args, **kwargs)


    def call_decorated(self,*args,**kwargs):
        """
        Call the decorated funtion/method with the given parameters.

        This method takes care of figuring out the 'self' if necesary.

        :param args:
        :param kwargs:
        :return:
        """
        # mainlog.debug("SourceFunctionDecorator.__call__ decorated args are {} {}".format(args, kwargs))

        if hasattr(self, '_instance'):
            # mainlog.debug("SourceFunctionDecorator.__call__ decorated as method (I am {})".format(self))
            return self._decorated_func(self._instance,*args,**kwargs)
        else:
            # mainlog.debug("SourceFunctionDecorator.__call__ decorated as function (I am {})".format(self._decorated_func))
            return self._decorated_func(*args, **kwargs)


class CacheResult(SourceFunctionDecorator):
    '''Decorator. Caches a function's return value each time it is called.
    If called later with the same arguments, the cached value is returned
    (not reevaluated).

    One can clear the cache by calling clear_cache.
    '''

    def __init__(self, func):
        mainlog.debug("CacheResult : __init__ decorating {}".format(func))
        super(CacheResult, self).__init__(func)
        self.__func = func
        self.__cache = dict()
        self.__expiration = dict()
        self.expire_time = timedelta(hours=1)

    def clear_cache(self):
        self.__cache = dict()
        self.__expiration = dict()

    def __call__(self, *args, **kwargs):
        if args in self.__cache and self.__expiration[args] > datetime.now():
            mainlog.debug("CacheResult : cache hit ! args={}".format(args))
            return self.__cache[args]
        else:
            # mainlog.debug("CacheResult : cache miss !")
            # value = self.__func(*args)
            value = self.call_decorated(*args, **kwargs)
            self.__cache[args] = value
            self.__expiration[args] = datetime.now() + self.expire_time
            return value


def make_temp_file(prefix = None, extension : str = None):
    """ The temporary  file won't be deleted """

    if extension and not extension.startswith('.'):
        extension = "." + extension

    if not prefix:
        prefix = 'koi_'

    handle, absolute_path = tempfile.mkstemp(prefix=prefix, suffix=extension)
    os.close( handle) # Make sure we can open the  file any way we want
    return absolute_path



content_disposition_download_regex = re.compile("attachment; +filename=\"([^\"]+)\"")

def download_file(url, destination = None, progress_tracker = None):
    """ Download document from url.

    :param progress_tracker: a progress tacker
    :param destination: Where to store the file (full path, with filename). If omitted,
    then we'll try to get the filename advertised by the server. If that fails,
    we take a temporary file name
    :return: the full path to the downloaded file. You'll have to delete that
    file if you need to.
    """

    mainlog.debug(u"Downloading from {}".format(url))

    urlopener = build_opener(
        HTTPHandler(),
        HTTPSHandler())

    datasource = urlopener.open(url)

    meta = datasource.info()

    server_filename = None
    if 'Content-Disposition' in meta:
        match = content_disposition_download_regex.match(meta[ 'Content-Disposition'])
        if match:
            server_filename = match.group(1)

    if "Content-Length" in meta:
        file_size = int( meta[ "Content-Length"])
    else:
        file_size = None

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
    elif server_filename:
        outfile_name = os.path.join( tempfile.gettempdir(), server_filename)
    else:
        outfile_name = make_temp_file()


    mainlog.debug( "Storing file in {}".format(outfile_name))

    total_downloaded = 0

    with open(outfile_name,'wb') as out:
        while True:
            d = datasource.read(8192)

            if d:
                out.write( d)
            else:
                break

            total_downloaded += len(d)
            if progress_tracker:
                progress_tracker(total_downloaded)


    mainlog.debug( "Downloaded {}".format(outfile_name))

    if file_size and total_downloaded and file_size != total_downloaded:
        mainlog.warn("The number of bytes downloaded differs from the advertised content length ()".format(file_size))

    return outfile_name
