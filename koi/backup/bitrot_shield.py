import os.path
import hashlib
import glob

HASHLIST_FILENAME = "hashlist.txt"

def checksum_file(filename):
    with open(filename, mode='rb') as f:
        d = hashlib.sha512()
        while True:
            buf = f.read(4096*4)
            if buf:
                d.update(buf)
            else:
                return d.hexdigest()


def checksum_directory( d, logger):

    hashes = dict()

    if os.path.exists(HASHLIST_FILENAME):
        with open(HASHLIST_FILENAME,"r", encoding="utf-8") as f:
            for line in f:
                # logger.info(line)
                check, fname = line.split(" /// ")

                hashes[fname.strip()] = check.strip()


    files_failed = 0
    files_checked = 0
    new_files = 0

    for fn in glob.glob('*'):
        if fn != HASHLIST_FILENAME and os.path.isfile(fn):

            check = checksum_file(fn)
            files_checked += 1

            if fn not in hashes:
                logger.info("New file {}".format(fn.encode("ascii", errors="replace")))
                hashes[fn] = check
                new_files += 1

            elif hashes[fn] != check:
                logger.error("Check failed {}".format( fn.encode("ascii", errors="replace")))
                files_failed += 1

    with open(HASHLIST_FILENAME,"w", encoding="utf-8") as f:
        for fn in sorted(hashes.keys()):
            f.write("{} /// {}\n".format( hashes[fn], fn))

    logger.info("Bitrot shield protection status : {} files checked, {} files failed, {} new files".format( files_checked, files_failed, new_files))


if __name__ == "__main__":

    import logging

    log = logging.getLogger("test")
    logging.basicConfig()
    log.setLevel( logging.DEBUG)

    checksum_directory('.', log)
