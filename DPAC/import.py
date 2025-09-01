from enum import IntEnum
from struct import pack, unpack
from io import BytesIO
from typing import BinaryIO


class Import:
	class FLAG_ENUM(IntEnum):
		PSX = 0
		PS2 = 1

	def __init__(self, pach: str, mode: FLAG_ENUM = FLAG_ENUM.PS2):
		"""Accepts a PACH path i.e. C:\\MyPac.PAC, a FLAG_ENUM (0 for PSX, 1 for PS2)"""
		self.mode = mode
		with open(pach, "rb", buffering=2048) as f:
			if mode == Import.FLAG_ENUM.PS2:
				f.seek(4)
				tocsize, datasize, seccount = unpack("<3I", f.read(12))
				f.seek(2048)
				self.toc = BytesIO(f.read(tocsize))
				absoluteoffset = (seccount + 1) * 2048
				f.seek(absoluteoffset)
				self.data = BytesIO(f.read(datasize))
			elif mode == Import.FLAG_ENUM.PSX:
				raise NotImplementedError("Not supported")

	def get_file(self, path: str) -> BytesIO:
		parts = path.upper().encode("ascii").decode("ascii").split("/")
		folder = parts[1].ljust(4)
		file = parts[2].ljust(4)
		if (len(parts[1]) + len(parts[2])) > 8:
			raise ValueError(
				f"The specified name {path} does not adhere to MS-DOS 8.3 Standards."
			)
		while self.toc.tell() < len(self.toc.getvalue()):
			gotfolder = self._unpack_string()
			if gotfolder == folder:
				fieldcount: int = unpack("<H", self.toc.read(2))[
					0
				]  # the amount of records associated with a folder
				basesector: int = unpack("<H", self.toc.read(2))[0]
				if fieldcount & 0x8000 == 0x8000:
					print("Activating extension entry parsing...")
					fieldcount &= 0xFFF
					for j in range(fieldcount // 3):
						id = unpack("<H", self.toc.read(2))[0]
						filename = str(hex(id)[2:].zfill(4))
						print(filename)
						size = unpack("<H", self.toc.read(2))[0]
						print(f'{size}')
						Import._seek(self.data, basesector)
						got = self.data.read(size)
						if filename == file:
							self.data.seek(0)
							return BytesIO(got)
				else:
					for i in range(fieldcount // 3):
						name, sector, size = unpack("<4sHH", self.toc.read(8))
						filename = name.decode("ascii")
						if filename == file:
							Import._seek(self.data, sector)
							return BytesIO(self.data.read(size))
			else:
				fieldcount: int = unpack("<H", self.toc.read(2))[
					0
				]  # the amount of records associated with a folder
				basesector: int = unpack("<H", self.toc.read(2))[0]
				if fieldcount & 0x8000 == 0x8000:
					fieldcount = (fieldcount & 0xFFF) // 3
					self.toc.seek(4 * fieldcount, 1)
					continue
				else:
					fieldcount = (fieldcount & 0xFFF) // 3
					self.toc.seek(8 * fieldcount, 1)
					continue

	@staticmethod
	def _seek(f, num):
		return f.seek(num * 2048)

	def _unpack_string(self) -> str:
		return unpack("4s", self.toc.read(4))[0].decode("ascii")

	def write_arc(self, output_name: str, *additional_tocs):
		with open(output_name, 'wb') as arc:
			arc.write(b'\xff\x00\x00\x00')
			arc.write(self.toc.getvalue())
			f = 1
			if additional_tocs:
				for g in additional_tocs:
					arc.write(b'\xff\xff')
					arc.write(pack('<H', f))
					f += 1
					arc.write(g.getvalue())
			arc.write(b'\xff\xff\xff\xff')
			arc.flush()


if __name__ == '__main__':
	path = r"C:\mods\Patches\PS2\WWE RAW NEW GENERATION\pac\ch.pac"
	MyPAC = Import(path, 1)
	file = MyPAC.get_file('/EMD/0001')
	if file:
		print(file.getvalue())
		with open('0001', 'wb') as f:
			f.write(file.getvalue())
			f.flush()
	MyPAC.write_arc('MyArc.ARC')