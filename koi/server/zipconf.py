import re
from  zipfile import * 
import configobj

def append_config(zippath, cfg):
    cfg_file = "horse/resources/config.cfg"

    already_present = False
    zf = ZipFile(zippath)
    for n in zf.namelist():
        if n == cfg_file:
            already_present = True
            break
    zf.close()

    if already_present:
        return

    zf = ZipFile(zippath,'a')
    zf.writestr(cfg_file, cfg)
    zf.close()


def make_basic_config(ip):
    cfg = configobj.ConfigObj()

    cfg['Database'] = {}
    cfg['Database']['url'] = "postgresql://horse_clt:HorseAxxess@{}:5432/horsedb".format(ip)

    cfg['DownloadSite'] = {}
    cfg['DownloadSite']['url_file'] = ip + "/file"
    cfg['DownloadSite']['url_version'] = ip + "/version"
    cfg['DownloadSite']['url_database_url'] = ip + "/database"

    txt = ""
    for l in cfg.write():
        txt += "{}\n".format(l)
    return txt


def copy_config(server_cfg):

    cfg = configobj.ConfigObj()

    cfg['Database'] = {}
    cfg['Database']['url'] = server_cfg.get('Database','url')

    cfg['DownloadSite'] = {}
    cfg['DownloadSite']['url_file'] = server_cfg.get('DownloadSite','url_file')
    cfg['DownloadSite']['url_version'] = server_cfg.get('DownloadSite','url_version')
    cfg['DownloadSite']['url_database_url'] = server_cfg.get('DownloadSite','url_database_url')

    txt = ""
    for l in cfg.write():
        txt += "{}\n".format(l)
    return txt


def configure_zip(zip_path, ip):

    txt_cfg = make_basic_config(ip)
    append_config(zip_path,txt_cfg)

def configure_zip_with_config(zip_path, configration):

    txt_cfg = copy_config(configration)
    append_config(zip_path,txt_cfg)


if __name__ == "__main__":
    configure_zip(r'C:\Users\stc\AppData\Roaming\horse\horse.zip', "127.0.0.1")
