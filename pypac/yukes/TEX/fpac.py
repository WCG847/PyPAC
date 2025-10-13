from struct import pack, unpack
from typing import BinaryIO

class FilePack:
	def __init__(self, file_list: BinaryIO):
		self.file = file_list
		self.file.seek(8)
		self.file.write(pack('<?', True)) # pretend we "converted the address"
		self.file.seek(0)

	def __getitem__(self, index: int) -> tuple[str, str, int, int, bytes]:
		self.file.seek(0)
		SIZE = 32
		count = int.from_bytes(self.file.read(4), 'little')
		if index < count:
			self.file.seek([self.file.seek(12), int.from_bytes(self.file.read(4), 'little')][1])
			ptr = index * SIZE
			self.file.seek(ptr, 1)
			table = self.file.read(SIZE)
			name = self.file.read(16).split(b'\x00')[0].decode('cp1252')
			ext = self.file.read(4).split(b'\x00')[0].decode('cp1252')
			size, offset = unpack('<2I', self.file.read(8))
			self.file.seek(offset)
			data = self.file.read(size)
			return name, ext, size, offset, data
