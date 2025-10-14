
import json
from struct import unpack
from typing import BinaryIO

class Data:
	def __init__(self, adr: BinaryIO):
		assert adr.read(4) == b'PAC '
		count = unpack('<I', adr.read(4))[0]
		ENTRY = {}
		for i in range(count):
			id, ptr = unpack('<2H', adr.read(4))
			ptr &= 0x1FFFFF
			size = unpack('B', adr.read(1))[0] << 16; adr.seek(-1, 1)
			address = ptr + size
			size = ((unpack('<I', adr.read(4))[0]) << 32 & 0xFFFFFFFFFFFFFFFF) >> 40 & 0xFFFFFFFFFFFFFFFF
			print(size)
			ENTRY.setdefault(id, {'address': address, 'size': size})

		self.adr = {'id': 'PAC', 'keys': ENTRY}
		self.data = adr.read()

	def dump(self, path: str):
		with open(path, 'w') as jn:
			json.dump(self.adr, jn, indent=4)


	def __getitem__(self, key: int) -> bytes:
		v2 = self.adr['keys'][key]
		return self.data[v2['address']:v2['address'] + v2['size']]

	def __len__(self) -> int:
		return len(self.adr['keys'])