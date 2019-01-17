"""
Dear PyInstaller,

I've been trying to import the pubsub module but had problems with that... I've seen post related to pubsub but they were all related to wx widget. I use pubsub alone.

My import is done like this :

{{{
from pubsub import pub
}}}

But when I run the exe packaged by PyInstaller, it complains that :


{{{
Traceback (most recent call last):
  File "<string>", line 28, in <module>
  File "C:\PORT-STCA2\opt\PyInstaller-2.1\PyInstaller\loader\pyi_importers.py", line 270, in load_module
    exec(bytecode, module.__dict__)
  File "C:\PORT-STCA2\pl-PRIVATE\horse\tools\build\python\out00-PYZ.pyz\pubsub.pub", line 79, in <module>
  File "C:\PORT-STCA2\opt\PyInstaller-2.1\PyInstaller\loader\pyi_importers.py", line 270, in load_module
    exec(bytecode, module.__dict__)
  File "C:\PORT-STCA2\pl-PRIVATE\horse\tools\build\python\out00-PYZ.pyz\pubsub.core.listener", line 13, in <module>
ImportError: No module named listenerimpl

}}}


So I've written a hook made of three files (based on tons of information from the web) :

### hook-pubsub.core.py

{{{
import os
import PyInstaller.hooks.hookutils
from PyInstaller.hooks.hookutils import logger

def hook(mod):

    logger.info('pubsub: module %s ' % mod)
    pth = str(mod.__path__[0])
    if os.path.isdir(pth):
        # If the user imported setuparg1, this is detected
        # by the pubsub.setuparg1.py hook. That
        # hook sets 'pubsub'
        # to "arg1", and with that, we set the appropriate path here.
        # If nothing is detected by pubsub.setuparg1.py, we default to kwargs.
        protocol = PyInstaller.hooks.hookutils.hook_variables.get('pubsub','kwargs')
        new_path = os.path.normpath(os.path.join(pth, protocol))
        logger.info('pubsub: Adding %s protocol path : %s' % (protocol, new_path))
        mod.__path__.append(new_path)

    return mod

}}}

### hook-pubsub.setuparg1.py


{{{
import PyInstaller.hooks.hookutils


# If the user imports setuparg1, we just set an attribute
# in PyInstaller.hooks.hookutils that allows us to later
# find out about this.
PyInstaller.hooks.hookutils.hook_variables['pubsub'] = 'arg1'
}}}

### hook-pubsub.py


{{{
# Empty file to avoid a RuntimeWarning about a parent module not found
# But I really don't understand why I need that...
}}}


I guess it'd be nice to have that in PyInstaller's distribution :-)
But it sure needs more testing.

stF
"""

import os
import PyInstaller.hooks.hookutils
from PyInstaller.hooks.hookutils import logger


def hook(mod):

    logger.info('pubsub: module %s ' % mod)
    pth = str(mod.__path__[0])
    if os.path.isdir(pth):
        # If the user imported setuparg1, this is detected
        # by the pubsub.setuparg1.py hook. That
        # hook sets 'pubsub'
        # to "arg1", and with that, we set the appropriate path here.
        # If nothing is detected by pubsub.setuparg1.py, we default to kwargs.
        protocol = PyInstaller.hooks.hookutils.hook_variables.get('pubsub','kwargs')
        new_path = os.path.normpath(os.path.join(pth, protocol))
        logger.info('pubsub: Adding %s protocol path : %s' % (protocol, new_path))
        mod.__path__.append(new_path)

    return mod

