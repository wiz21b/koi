import sys
if sys.version[0] == '3':
    import xmlrpc.client as xmlrpclib
else:
    import xmlrpclib


from PySide.QtCore import QByteArray
from PySide.QtGui import QImage


class User:
	def __init__(self,identifier,name):
		self.identifier = int(identifier)
		self.name = name

	def set_picture_bytes(self,bytes = None):
		self.picture_bytes = xmlrpclib.Binary(bytes)
		return

	@classmethod
	def from_hash(cls,hash):
		u = User(hash['identifier'],hash['name'])
		u.image = QImage.fromData(QByteArray(hash['picture_bytes'].data)).scaledToHeight(128)
		#u.image = None
		return u

		f = open(hash['picture_bytes'],"rb")
		bytes = f.read(-1)
		f.close()
		u.image = QImage.fromData(QByteArray(bytes)).scaledToHeight(256)

		return u
