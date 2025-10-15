from struct import unpack
from typing import BinaryIO

class MPQ:
	def __init__(self, path: str):
		with open(path, 'rb') as mpq:
			self.to_dict(mpq)

	def to_dict(self, handle: BinaryIO):
		entries = []
		assert handle.read(4) == b'MPQ\0'
		file_loc, table_loc, table_count = unpack('>3I', handle.read(12))
		handle.seek(table_loc)
		for i in range(0, table_count, 2):
			offset, size = unpack('>2I', handle.read(8))
			entries.append({'offset': offset, 'size': size})
		handle.seek(file_loc)
		self.data = handle.read()
		self.keys = {
			'root': {
				'id': 'MPQ',
				'fileLocation': file_loc,
				'tableLocation': table_loc,
				},
			'table': entries}
