
from io import BytesIO
import json
from struct import error, unpack
from typing import BinaryIO
from dataclasses import dataclass
from functools import lru_cache

@dataclass(slots=True)
class FilePos:
	sector: int
	size: int
	uid: int


class File:
	FILE_ID = 0
	ENTRY_CAP = 756

	def __init__(self, path: str):
		assert ".PAC" in path or ".pac" in path
		with open(path, "rb", buffering=2048) as p:
			self.add_entry(p)
		File.FILE_ID += 1

	def add_entry(self, file: BinaryIO):
		RECORD_COUNT = 4
		ID = b"EPK8"
		assert file.read(4) == ID
		TOC, DATA, SECTOR_SIZE = unpack("<3I", file.read(12))
		assert SECTOR_SIZE == 7
		file.seek(2048)
		toc = BytesIO(file.read(TOC))
		START_OF_DATA = (SECTOR_SIZE + 1) * 2048
		file.seek(START_OF_DATA)
		self.data = file.read(DATA)
		ENTRY = {}
		while toc.tell() < len(toc.getvalue()):

			folder = unpack("4s", toc.read(4))[0].rstrip(b"\x20").decode("shift_jis")

			count: int
			islong: bool
			count, islong = unpack("<H?xxxxx", toc.read(8))

			assert count < 4096
			assert islong is True
			for i in range(0, count, RECORD_COUNT):
				name, sector, size = unpack("<8s2I", toc.read(16))
				size *= 256

				ENTRY.setdefault(folder, {})[name.rstrip(b"\x20").decode("shift_jis")] = {
					"lsn": sector,
					"size": size,
				}
		self.buffer = {
			ID.decode("shift_jis"): {
				"head": {"id": 255, "uid": File.FILE_ID, "entries": ENTRY}
			}
		}
	def dump(self, path: str):
		with open(path, 'w') as j:
			return json.dump(self.buffer, j, indent=4)

	
	@lru_cache(maxsize=4096, typed=True)
	def search(self, path: str = '/EMD/00010202') -> FilePos:
		HANDLE = FilePos(0, 0, 0)
		_, folder, file = path.split('/')
		for key, value in self.buffer.items():
			assert key == 'EPK8'
			assert isinstance(value, dict)
			for key2, value2 in value.items():
				assert key2 == 'head'
				for key3, value3 in value2.items():
					if key3 == 'id':
						assert value3 == 255
					elif key3 == 'uid':
						assert value3 < 256
						uid = value3
					if key3 == 'entries':
						for gotfolder, thing in value3.items():
							if gotfolder == folder:
								for filee, meh in thing.items():
									if file == filee:
										for key4, value4 in meh.items():
											if key4 == 'lsn':
												HANDLE.sector = value4
											if key4 == 'size':
												assert value4 > 0
												HANDLE.size = value4
												assert HANDLE.size > 0
										HANDLE.uid = uid
										return HANDLE
	def read(self, handle: FilePos, size: int) -> bytes:
		offset = (handle.sector) * 2048
		print(offset)
		cs = offset + size
		print(cs)
		return self.data[offset:cs]