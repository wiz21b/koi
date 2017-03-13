import sys
from time import time
from koi.Configurator import mainlog,configuration



_chrono = None
_first_chrono = None

def chrono_start(title = None):
    global _chrono, _first_chrono

    if title:
        mainlog.debug("{} Chrono start".format(title))

    _first_chrono = _chrono = time()

def chrono_sec():
    global _chrono
    return time() - _chrono

def chrono_click(msg = None):
    global _chrono, _first_chrono

    # Timings are just for development purposes :-)
    if getattr(sys, 'frozen', False):
        return

    if not _chrono:
        chrono_start()

    t = time()
    s = t - _chrono
    total = t - _first_chrono
    if msg:
        mainlog.debug("{} : step {:03.3f}s, total {:03.3f}s".format(msg,s,total))
    else:
        mainlog.debug("chrono : step {}s, total:{}s".format(s, total))

    _chrono = time()
