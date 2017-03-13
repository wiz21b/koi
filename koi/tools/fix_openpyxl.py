# See https://bitbucket.org/openpyxl/openpyxl/pull-requests/80/__about__py/diff

import builtins
import io
import os

_open = builtins.open

def fake_open(path, *args, **kwargs):
    if path.endswith(os.path.join('openpyxl', '.constants.json')):
        return '''{
            "__author__": "", "__author_email__": "", "__license__": "",
            "__maintainer_email__": "", "__url__": "", "__version__": ""
        }'''

        # return io.BytesIO(b'''{
        #     "__author__": "", "__author_email__": "", "__license__": "",
        #     "__maintainer_email__": "", "__url__": "", "__version__": ""
        # }''')
    return _open(path, *args, **kwargs)

def ignore_openpyxl_constants(*__):
    return

    builtins.open = fake_open
    __import__('openpyxl')  # read .constants.json by fake_open().
    builtins.open = _open