import glob
import os

#python \PORT-STC\opt\python\Tools\i18n\pygettext.py --default-domain koi i18n.py
#REM msginit --locale=en --input=koi.pot
#msgmerge --update en.po koi.pot

GETTEXT_PATH="c:\\port-stc\\opt\\gnu\\bin\\"
FILE_LIST_PATH = 'c:/tmp/file_list'
MESSAGES_POT_PATH = 'c:/tmp/messages.pot'

# glob doesn't recurse. The file matcher does (check the web) but not a priority to use it right now.
globstr = ['*.py','*/*.py','*/*/*.py','*/*/*/*.py']


def which(program):
    # Inspired from http://stackoverflow.com/questions/377017/test-if-executable-exists-in-python/377028#377028
    import os
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            print(exe_file)
            if is_exe(exe_file):
                return exe_file
            if is_exe(exe_file + ".exe"):
                return exe_file

    return None

def prepare_translations(lang):

    print("Preparing translations for {}".format(lang))

    top_dir = os.path.join( os.path.dirname(__file__), "..", "koi")
    print("Top dir = {}".format(str(top_dir)))

    base_dir = os.path.join( top_dir, "resources", "i18n")

    translations_dir = os.path.join(base_dir,lang,"LC_MESSAGES")
    if not os.path.exists(translations_dir):
        os.makedirs(translations_dir)

    po = os.path.join(base_dir,lang + ".po")
    mo = os.path.join(translations_dir,"all_messages.mo")

    print("PO file is : {}".format(po))
    print("MO file is : {}".format(mo))


    print("Scanning source code deep to the fourth level, starting at {}".format(
        os.path.abspath(top_dir)))
    nb_files = 0


    file_list = open(FILE_LIST_PATH,'w')
    for gs in globstr:
        for f in glob.iglob( os.path.join(top_dir, gs)):
            file_list.write(f+"\n")
            nb_files += 1
    file_list.close()
    print("Read {} files".format(nb_files))

    # We'll use xgettext to find out all the string that can be internationalized.

    # Well, in the end, it seems it's better to reset the messages.pot
    # file instead of merging. Merging seems to imply : keeping all
    # that's old (included what's not used anymore)

    join = ""
    # if os.path.exists('messages.pot'):
    #     join = "--join-existing"

    # xgettext won't output .pot files per default but .po files.
    # That's a known shortcoming, see gettext documentation about PO Template files.
    os.system("xgettext --files-from={} {} --output={}".format(FILE_LIST_PATH,join,MESSAGES_POT_PATH))

    # Now we have all the strings, we merge them with those which are
    # already translated (in the *.po files)

    if os.path.exists(po):
        print("merging")
        os.system("msgmerge --update {} {}".format(po,MESSAGES_POT_PATH))
    else:
        print("creating")
        os.system("msginit --locale={} --output-file={} --input={}".format(lang, po, MESSAGES_POT_PATH))

    print("Now you can open and edit the {} file to write your translations".format(po))

    # Now we create the actual translations files as used during program execution

    # If somethign goes wrong here, it may be that you miss
    # the directory where msgfmt must put its stuff

    os.system("msgfmt --output={} {}".format(mo, po))

if not which("msgfmt"):
    print("Is gettext installed correctly ?")
    exit(-1)

prepare_translations("en")
prepare_translations("fr")
print()
print("In emacs, hit 'enter' to start editing a message; C-c C-c to save; 'f' to go to next fuzzy; 'tab' to toggle fuzzy")
