import os
from struct import unpack_from, pack, unpack
from io import BytesIO


class PACIO:
	def __init__(self, *PAC_FILE_BUFFERS: str):
		toc = []
		self.data = []
		for x in range(len(PAC_FILE_BUFFERS)):
			y = (
				PAC_FILE_BUFFERS[x]
				.upper()
				.split(".")[0][:8]
				.encode("latin1", errors="ignore")
				+ b".PAC"
			)
			t, d = self.AddEnt(y, x)
			toc.append(t)
			self.data.append(d)
		toc.append(BytesIO(b"\xFF\xFF\xFF\xFF"))
		self.buffer = BytesIO(b"".join(t.getvalue() for t in toc)[:65536])  # 64kb

	@staticmethod
	def AddEnt(file: str, flag: int) -> tuple[BytesIO, BytesIO]:
		with open(file, "rb", buffering=2048) as f:
			header, tocsize, datasize, sectorcount = unpack("<4I", f.read(16))
			sectorcount += 1
			f.seek(1 * 2048)
			TOC = BytesIO(f.read(tocsize))
			f.seek(sectorcount * 2048)
			DATA = BytesIO(f.read(datasize))
		if flag == 0:
			startmarker = f"FF{flag}0000"
		else:
			startmarker = f"FF{flag}FFFF"
		fi = pack("<I", 0xFF | (flag << 8) | (0xFFFF if flag else 0x0000) << 16)
		start = BytesIO(fi)
		TOC.seek(0)
		toc = BytesIO(start.getvalue() + TOC.getvalue())
		TOC = toc
		return TOC, DATA

	def Search(self, path: str = "/EMD/0000"):
		parts = path.strip("/").split("/")
		folder, file = parts[0].ljust(4), parts[1].ljust(4)
		start = unpack("4B", self.buffer.read(4))
		startmarker = start[0]
		requestid = start[1]
		data = self.data[requestid]
		filepos = 0
		while True:
			if (name := unpack("4s", self.buffer.read(4))[0].decode("latin1")) != folder:
				filecount, flag = unpack_from("2B", self.buffer.read(2), 4 + filepos)
				size = (((filecount & 0x0FFF) << 2) + 8) - 4  # 4 for the name
				self.buffer.seek(size, 1)
				filepos = self.buffer.tell()
				continue
			else:
				filecount, flag, baseaddr = unpack("2BH", self.buffer.read(4))
				if filecount > 4095:
					raise ValueError("Too many files!")
				baseaddr <<= 11
				if flag == 0x80:
					for i in range((filecount // 3)):
						id = unpack(">H", self.buffer.read(2))[0]
						size = unpack("H", self.buffer.read(2))[0]
						name = str(id)
						if name != file:
							data.seek(size, 1)
							aligned = (data.tell() + 2047) &~ 2047
							data.seek(aligned)
							continue
						extfile = BytesIO(data.read(size))
						return extfile
				else:
					count = filecount | (flag << 8)
					for i in range((filecount // 3)):
						name = unpack("4s", self.buffer.read(4))[0].decode("latin1")
						addr, size = unpack("2H", self.buffer.read(4))
						if name != file:
							continue
						else:
							data.seek((addr << 11))
							file = BytesIO(data.read(size))
							return file

	def WriteArc(self, name: str = "plistps2.arc"):
		with open(name, "wb") as arc:
			arc.write(self.buffer.getvalue())
			arc.flush()

	def ExtractRootTOC(self):
		while True:
			name, filecount, flag, baseaddr = unpack("4s2BH", self.buffer.read(8))
			os.mkdir(f"C:\\PAC\\{name.rstrip(b'\x20').lower()}")

if __name__ == '__main__':
	pac = PACIO('M.PAC')
	file = pac.Search('/MOT/GAME')
	if file is None:
		print('No file')
	else:
		print(f'{file}')
	pac.WriteArc()