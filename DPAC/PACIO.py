import os
from struct import unpack, pack
from io import BytesIO


class PACIO:
	"""
	Merge several *.PAC files and let you pull individual entries out by
	virtual path, e.g.  /MOT/GAME   or   /GA2D/DALL
	"""

	TOC_TERMINATOR = b"\xFF\xFF\xFF\xFF"
	SECTOR_SIZE    = 2048

	# ───────────────────────────────  construction ──────────────────────────────
	def __init__(self, *pac_paths: str):
		"""
		Accept one or more PAC filenames, merge their TOCs, keep their data
		payloads separately in memory, and leave a combined TOC in
		self.buffer.  The first four bytes of each chunk in that TOC are
		always:   0xFF, <PAC-index>, 0xFF, 0xFF
		"""
		toc_chunks, self.data = [], []

		for index, path in enumerate(pac_paths):
			chunk_toc, chunk_data = self._read_single_pac(path, index)
			toc_chunks.append(chunk_toc)
			self.data.append(chunk_data)

		toc_chunks.append(BytesIO(self.TOC_TERMINATOR))
		self.buffer = BytesIO(b"".join(c.getvalue() for c in toc_chunks))
		self.buffer.seek(0)

	@staticmethod
	def _read_single_pac(path: str, pac_index: int) -> tuple[BytesIO, BytesIO]:
		"""
		Return (toc_stream, data_stream) for one PAC file.
		A 4-byte marker is prepended to the TOC so the merged stream knows
		when to switch to this PAC’s DATA block.
		"""
		with open(path, "rb") as f:
			header, toc_size, data_size, sector_count = unpack("<4I", f.read(16))

			f.seek(PACIO.SECTOR_SIZE)                     # start of TOC
			toc_bytes  = f.read(toc_size)

			f.seek((sector_count + 1) * PACIO.SECTOR_SIZE)  # start of DATA
			data_bytes = f.read(data_size)

		# marker  FF <index> FF FF
		marker = pack("BBBB", 0xFF, pac_index, 0xFF, 0xFF)

		return BytesIO(marker + toc_bytes), BytesIO(data_bytes)

	# ────────────────────────────  public helpers  ───────────────────────────────
	def WriteArc(self, outname: str = "plistps2.arc") -> None:
		"""Dump the merged TOC to disk (handy for inspection)."""
		with open(outname, "wb") as fh:
			fh.write(self.buffer.getvalue())

	def ExtractRootTOC(self, output_root: str = "C:\\PAC\\"):
		self.buffer.seek(0)
		current_data = None

		while True:
			chunk = self.buffer.read(4)
			if len(chunk) < 4:
				raise EOFError("Corrupt TOC – ran past the end without terminator")

			if chunk == self.TOC_TERMINATOR:
				break

			if chunk[0] == 0xFF and chunk[2:] == b"\xFF\xFF":
				pac_id = chunk[1]
				try:
					current_data = self.data[pac_id]
				except IndexError:
					raise IndexError(f"TOC refers to PAC ID {pac_id}, but only {len(self.data)} loaded.")
				continue

			folder_name = chunk.decode("latin1").rstrip()
			filecount, flag, baseaddr = unpack("2BH", self.buffer.read(4))
			baseaddr <<= 11  # sector to byte

			folder_path = os.path.join(output_root, folder_name)
			os.makedirs(folder_path, exist_ok=True)

			if current_data is None:
				raise RuntimeError("PAC data not set before folder entry.")

			if flag == 0x80:
				# Extended TOC
				for _ in range(filecount // 3):
					file_id = int.from_bytes(self.buffer.read(2), "big")
					size    = int.from_bytes(self.buffer.read(2), "little")
					file_name = str(file_id).rjust(4, "0")
					data_pos = current_data.tell()
					file_data = current_data.read(size)

					with open(os.path.join(folder_path, file_name), "wb") as out:
						out.write(file_data)

					# Align to next sector
					current_data.seek((current_data.tell() + self.SECTOR_SIZE - 1) & ~(self.SECTOR_SIZE - 1))
			else:
				# Normal TOC
				words = (filecount | (flag << 8)) & 0x0FFF
				for _ in range(words // 2):
					fname = self.buffer.read(4).decode("latin1").rstrip()
					addr  = int.from_bytes(self.buffer.read(2), "little") << 11
					size  = int.from_bytes(self.buffer.read(2), "little")

					current_data.seek(addr)
					file_data = current_data.read(size)

					with open(os.path.join(folder_path, fname), "wb") as out:
						out.write(file_data)


	# ────────────────────────────────  Search  ──────────────────────────────────
	def Search(self, path: str):
		"""
		Return a BytesIO containing the requested file, or None if not found.
		path must be of the form  /XXXX/YYYY   where XXXX is the 4-char folder
		and YYYY the 4-char file name (numbers are fine – they’re padded).
		"""
		folder, filename = (p.ljust(4) for p in path.strip("/").split("/", 1))

		self.buffer.seek(0)
		current_data = None                               # DATA block we’re reading

		while True:
			chunk = self.buffer.read(4)
			if len(chunk) < 4:
				raise EOFError("Corrupt TOC – ran past the end without terminator")

			# ──────────────────  special markers  ──────────────────
			if chunk == self.TOC_TERMINATOR:
				return None                               # not found, clean EOF

			if chunk[0] == 0xFF and chunk[2:] == b"\xFF\xFF":
				pac_id = chunk[1]
				try:
					current_data = self.data[pac_id]
				except IndexError:
					raise IndexError(f"TOC refers to PAC ID {pac_id} (only {len(self.data)} loaded)")
				continue                                  # next four bytes are a folder name

			# ──────────────────  normal folder entry  ──────────────────
			folder_name = chunk.decode("latin1")
			filecount, flag, baseaddr = unpack("2BH", self.buffer.read(4))

			if folder_name == folder:
				return self._extract_from_folder(filename, filecount, flag, baseaddr, current_data)

			# Folder doesn’t match → skip its directory entries
			self._skip_directory_entries(filecount, flag)

	# ───────────────────────  helpers used by Search()  ─────────────────────────
	def _skip_directory_entries(self, filecount: int, flag: int) -> None:
		"""
		Jump over a folder's directory table without parsing it.

		· Extended table (flag == 0x80) ➜ 1 word per file  → 4  bytes/entry
		· Normal   table (flag != 0x80) ➜ 2 words per file → 8  bytes/entry
		  (name 4 B, offset 2 B, size 2 B)
		"""
		if flag == 0x80:                         # extended (ID/size) table
			n_files   = filecount // 3           # spec: words/3 → files
			entry_len = 4
		else:                                    # normal (name/addr/size) table
			words     = (filecount | flag << 8) & 0x0FFF
			n_files   = words // 2               # two words per file
			entry_len = 8

		self.buffer.seek(n_files * entry_len, os.SEEK_CUR)


	def _extract_from_folder(self, filename: str, filecount: int,
							 flag: int, baseaddr: int, data: BytesIO | None):
		"""
		We’re inside the sought-after folder.  Parse its directory table and
		return the requested file (as BytesIO) or None.
		"""
		if data is None:
			raise RuntimeError("Folder record came before any PAC-switch marker")

		baseaddr <<= 11                          # sector → byte

		# ─── extended 4-byte entries (flag 0x80) ───────────────────────────
		if flag == 0x80:
			for _ in range(filecount // 3):
				file_id = int.from_bytes(self.buffer.read(2), "big")
				size    = int.from_bytes(self.buffer.read(2), "little")
				if str(file_id).ljust(4) != filename:
					data.seek(size, os.SEEK_CUR)
					data.seek((data.tell() + self.SECTOR_SIZE - 1)
							  & ~(self.SECTOR_SIZE - 1))
					continue
				return BytesIO(data.read(size))
			return None

		# ─── normal 8-byte entries ─────────────────────────────────────────
		words     = (filecount | flag << 8) & 0x0FFF
		n_files   = words // 2                   # two words (8 B) per file

		for _ in range(n_files):
			fname = self.buffer.read(4).decode("latin1")
			addr  = int.from_bytes(self.buffer.read(2), "little")
			size  = int.from_bytes(self.buffer.read(2), "little")
			if fname != filename:
				continue
			data.seek(addr << 11)
			return BytesIO(data.read(size))

		return None


if __name__ == '__main__':
	pac = PACIO('M.PAC', 'GAME2D.PAC')
	file = pac.Search('/MOT/GAME')
	file2 = pac.Search('/GA2D/DALL')
	if file is None:
		print('No file')
	else:
		print(f'{file.read()}')
	if file2 is None:
		print('No file')
	else:
		print(f'{file2.read()}')

	pac.WriteArc()
	pac.ExtractRootTOC()