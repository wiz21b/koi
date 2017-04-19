# -*- mode: python -*-
# This file is to build the client "one-exe" meant to
# be distributed as the demo of Koi
# This is a PyInstaller specification file.
# We don't use cx_freeze here because it can't do "one file" exe's.
# For some reason, PYTHONPATH must be set.
# If not, the pyinstaller will have missing module

# set PYTHONPATH=C:\PORT-STC\PRIVATE\PL\horse
# cd %PYTHONPATH%
# pyinstaller --onefile --noconfirm tools\koi_demo_client.spec
# horse.exe
# rmdir /S /Q  dist & rmdir /S /Q  build

# Had to do this : Fixed by me : http://stackoverflow.com/questions/35691320/issues-with-pyinstaller-and-reportlab
# ('coz I was afraid of upgrading to pyinstaller 3.xxx)

import os



def get_env( var_name, var_default):
    if var_name in os.environ:
        return os.environ[var_name]
    else:
        return var_default

BASE_DIR = get_env('TMP_HOME', r'C:\PORT-STC\PRIVATE\PL\horse\koi')
VERSION = get_env('VERSION', '1.0.0')
SUFFIX = get_env('SUFFIX', '')
SERVER_ADDRESS = get_env('SERVER_ADDRESS', '127.0.0.1')



zehiddenimports = [
    'reportlab.pdfbase._fontdata_enc_macexpert',
    'reportlab.pdfbase._fontdata_enc_macroman',
    'reportlab.pdfbase._fontdata_enc_pdfdoc',
    'reportlab.pdfbase._fontdata_enc_standard',
    'reportlab.pdfbase._fontdata_enc_symbol',
    'reportlab.pdfbase._fontdata_enc_winansi',
    'reportlab.pdfbase._fontdata_enc_zapfdingbats',
    'reportlab.pdfbase._fontdata_widths_courier',
    'reportlab.pdfbase._fontdata_widths_courierbold',
    'reportlab.pdfbase._fontdata_widths_courierboldoblique',
    'reportlab.pdfbase._fontdata_widths_courieroblique',
    'reportlab.pdfbase._fontdata_widths_helvetica',
    'reportlab.pdfbase._fontdata_widths_helveticabold',
    'reportlab.pdfbase._fontdata_widths_helveticaboldoblique',
    'reportlab.pdfbase._fontdata_widths_helveticaoblique',
    'reportlab.pdfbase._fontdata_widths_symbol',
    'reportlab.pdfbase._fontdata_widths_timesbold',
    'reportlab.pdfbase._fontdata_widths_timesbolditalic',
    'reportlab.pdfbase._fontdata_widths_timesitalic',
    'reportlab.pdfbase._fontdata_widths_timesroman',
    'reportlab.pdfbase._fontdata_widths_zapfdingbats']




RESOURCE_DIR=os.path.join(BASE_DIR,'koi',"resources")
I18N_DIR=os.path.join(RESOURCE_DIR,"i18n")
HOOKS_DIR=os.path.join(BASE_DIR,"tools","hooks")

top_script = os.path.join(BASE_DIR,'koi','python.py')

# Solve relative imports issues
# f = open(top_script,'w')
# f.write('import src.python')
# f.close()

net_cfg = os.path.join(RESOURCE_DIR,'net.cfg')
with open( net_cfg, 'w') as f:
    f.write(SERVER_ADDRESS)


specific_data = [(r'resources\client_splash.png',  os.path.join(RESOURCE_DIR,'client_splash.png'),'DATA'),
                 (r'resources\package_version',    os.path.join(RESOURCE_DIR,'package_version'),'DATA'),
                 (r'resources\config.cfg',         os.path.join(RESOURCE_DIR,'config.cfg'),'DATA'),
                 (r'resources\net.cfg',            net_cfg,'DATA'),
                 (r'resources\config-check.cfg',   os.path.join(RESOURCE_DIR,'config-check.cfg'),'DATA'),
                 (r'resources\letter_header.png',  os.path.join(RESOURCE_DIR,'letter_header.png'),'DATA'),
                 (r'resources\letter_footer.png',  os.path.join(RESOURCE_DIR,'letter_footer.png'),'DATA'),
                 (r'resources\standard.qss',       os.path.join(RESOURCE_DIR,'standard.qss'),'DATA'),
                 (r'resources\bigfont.qss',        os.path.join(RESOURCE_DIR,'bigfont.qss'),'DATA'),
                 (r'resources\DejaVuSansMono.ttf', os.path.join(RESOURCE_DIR,'DejaVuSansMono.ttf'),'DATA'),
                 (r'resources\Roboto-Regular.ttf', os.path.join(RESOURCE_DIR,'Roboto-Regular.ttf'),'DATA'),
                 (r'resources\Roboto-Bold.ttf',    os.path.join(RESOURCE_DIR,'Roboto-Bold.ttf'),'DATA'),
                 (r'resources\plus_icon.png',      os.path.join(RESOURCE_DIR,'plus_icon.png'),'DATA'),
                 (r'resources\plusplus_icon.png',  os.path.join(RESOURCE_DIR,'plusplus_icon.png'),'DATA'),
                 (r'resources\minus_icon.png',     os.path.join(RESOURCE_DIR,'minus_icon.png'),'DATA'),
                 (r'resources\up_icon.png',        os.path.join(RESOURCE_DIR,'up_icon.png'),'DATA'),
                 (r'resources\win_icon.png',       os.path.join(RESOURCE_DIR,'win_icon.png'),'DATA'),
                 (r'resources\thumb-up-3x.png',    os.path.join(RESOURCE_DIR,'thumb-up-3x.png'),'DATA'),
                 (r'resources\appbar.book.hardcover.open.png', os.path.join(RESOURCE_DIR,'appbar.book.hardcover.open.png'),'DATA'),
                 (r'resources\appbar.cabinet.files.png',       os.path.join(RESOURCE_DIR,'appbar.cabinet.files.png'),'DATA'),
                 (r'resources\appbar.page.delete.png',         os.path.join(RESOURCE_DIR,'appbar.page.delete.png'),'DATA'),
                 (r'resources\appbar.page.download.png',       os.path.join(RESOURCE_DIR,'appbar.page.download.png'),'DATA'),
                 (r'resources\appbar.page.search.png',         os.path.join(RESOURCE_DIR,'appbar.page.search.png'),'DATA'),
                 (r'resources\appbar.page.upload.png',         os.path.join(RESOURCE_DIR,'appbar.page.upload.png'),'DATA'),
                 (r'resources\comments.png',       os.path.join(RESOURCE_DIR,'comments.png'),'DATA'),
                 (r'resources\SumatraPDF.exe',     os.path.join(RESOURCE_DIR,'SumatraPDF.exe'),'DATA'),
                 (r"resources\general_conditions.txt", os.path.join(RESOURCE_DIR,'general_conditions.txt'),'DATA'),
                 (r'resources\manual.html',        os.path.join(RESOURCE_DIR,'manual.html'),'DATA'),
                 (r"resources\i18n\en\LC_MESSAGES\all_messages.mo", os.path.join(I18N_DIR,    r"en\LC_MESSAGES\all_messages.mo"),'DATA'),
                 (r"resources\i18n\fr\LC_MESSAGES\all_messages.mo", os.path.join(I18N_DIR,    r"fr\LC_MESSAGES\all_messages.mo"),'DATA') ]

# specific_data += all_dir(BASE_DIR+r'\i18n')
#          name=os.path.join('build\\pyi.win32\\python', 'horse.exe'),

a = Analysis([top_script],
             hiddenimports=zehiddenimports) # , hookspath=[HOOKS_DIR])

pyz = PYZ(a.pure - [('DeclEnumP3',None,None)]) # The minus thign doesn't quite work, it's easier to remove the file from the file system. I leave this comment here because I may have got something wrog => maybe post to mailing list for help ?

all_debug = False

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas + specific_data,
          # exclude_binaries=1,
          name='koi_client{}.exe'.format( SUFFIX),
          debug=all_debug,
          strip=False,
          upx=True,
          console=all_debug )

#print("-------------------------------------- Collecting to {}".format(os.environ['DIST_DIR']))

# if --onefile, then the COLLECT must be removed
"""
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas + specific_data,
               strip=None,
               upx=True,
               name="horse") # Name of the directory containing the release, wil be created inside a dist directory given by default by PyInstaller. Only a single name is recognized (c:\aa\bb will be transformed into bb)
"""
