# -*- mode: python -*-

# To reinstall : sudo pip install --upgrade --no-deps --force-reinstall

import os

BASE_DIR=None
try:
    BASE_DIR = os.environ['TMP_HOME']
except:
    BASE_DIR = os.path.join( r'\PORT-STC\PRIVATE\PL\horse')

print("------------------------------------------------------XXX {}".format(BASE_DIR))

RESOURCE_DIR=os.path.join(BASE_DIR,"koi","resources")
I18N_DIR=os.path.join(RESOURCE_DIR,"i18n")
HOOKS_DIR=os.path.join(BASE_DIR,"tools","hooks")
SRC_DIR=os.path.join(BASE_DIR)

a = Analysis([os.path.join(BASE_DIR,'koi','server','service_win32.py')],
             pathex=[BASE_DIR],
             hiddenimports=['win32timezone'],
             hookspath=[HOOKS_DIR])



def all_dir(src):
    import glob
    import os.path

    a = []
    for name in glob.glob(src+r'\**\*'):
        print(name)
        print(os.path.basename(name))
        a.append( (os.path.basename(name),name,'DATA') )
    return a

specific_data = [(r"resources\general_conditions.txt", os.path.join(RESOURCE_DIR,'general_conditions.txt'),'DATA'),
             (r'resources\package_version',    os.path.join(RESOURCE_DIR,'package_version'),'DATA'),
             (r'resources\file_server_logo.png',    os.path.join(RESOURCE_DIR,'file_server_logo.png'),'DATA'),
             (r'resources\server_config_check.cfg',   os.path.join(RESOURCE_DIR,'server_config_check.cfg'),'DATA'),
             (r'resources\server\order_confirmation_report.docx',   os.path.join(RESOURCE_DIR,'server','order_confirmation_report.docx'),'DATA'),
             (r'resources\server\preorder_letter.docx',   os.path.join(RESOURCE_DIR,'server','preorder_letter.docx'),'DATA'),
             (r"i18n\en\LC_MESSAGES\all_messages.mo", os.path.join(I18N_DIR,    r"en\LC_MESSAGES\all_messages.mo"),'DATA'),
             (r"i18n\fr\LC_MESSAGES\all_messages.mo", os.path.join(I18N_DIR,    r"fr\LC_MESSAGES\all_messages.mo"),'DATA') ]


# http://stackoverflow.com/questions/19055089/pyinstaller-onefile-warning-pyconfig-h-when-importing-scipy-or-scipy-signal
for d in a.datas:
    if 'pyconfig' in d[0]: 
        a.datas.remove(d)
        break

# One EXE file
pyz = PYZ(a.pure)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          specific_data,
          name='koi_server.exe',
          debug=False,
          console=True )

