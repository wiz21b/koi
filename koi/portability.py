__author__ = 'stc'

import sys
import os
import subprocess

from koi.Configurator import configuration
from koi.base_logging import mainlog


def open_a_file_on_os(filepath):

    if filepath.endswith(".pdf"):

        pdf_cmd = configuration.get('Programs','pdf_viewer')
        mainlog.debug("Opening PDF {} with {}".format(filepath, pdf_cmd))
        if pdf_cmd:
            # Start our own viewer (which is way faster than acrobat)
            p1 = subprocess.Popen([pdf_cmd,filepath])
            p1.wait()
        else:
            os.startfile(filepath)

        return

    if sys.platform.startswith('darwin'):
        subprocess.call(('open', filepath))

    elif os.name == 'nt':

        if filepath.endswith(".docx"):
            import win32com.client

            # See http://stackoverflow.com/questions/26907177/key-error-while-using-cx-freeze-for-making-exe
            # word = win32com.delivery_slips.gencache.EnsureDispatch('Word.Application')
            word = win32com.client.dynamic.Dispatch('Word.Application')

            word.Visible = True
            doc = word.Documents.Open(filepath)
        else:
            os.startfile(filepath)

    elif os.name == 'posix':
        subprocess.call(('xdg-open', filepath))

