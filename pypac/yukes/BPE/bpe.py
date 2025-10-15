from struct import unpack

class Bpe:
	@staticmethod
	def expand(file: memoryview):
		output = []
		expansion = memoryview(bytearray(list(range(256))))
		file = file[16:]
		t8 = 0
		for i, byte in enumerate(file):
			if not (byte & 0x80):
				file = file[1:]
				decode = byte - 127
				t7 = t8 + decode
				if t7 != 256:
					two = file[0]
					got1 = expansion[t7:]
					got1[0] = two
					if t7 != two:
