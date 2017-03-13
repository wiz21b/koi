__author__ = 'stc'

import socket
import ipaddress

def guess_server_public_ip():
    try:
        return socket.gethostbyname(socket.gethostname())
    except:
        return '127.0.0.1'

def string_represents_ip_address(s):
    try:
       ip = ipaddress.ip_address(str(s).strip())
       return True
    except ValueError:
       return False
