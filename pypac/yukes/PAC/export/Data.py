from io import BytesIO
import json
from struct import pack
class Data:
	def write(self, path: str, out: str):
		toc = BytesIO()
		data = BytesIO()
		with open(path, 'r') as j:

			d: dict = json.load(j)
			for i, (key, record) in enumerate(d.items()):
				for label, folder in record.items():
					if label == 'path':
						with open(folder, 'rb') as f:
							adr = (data.tell()) + 1
							da = f.read()
							size = len(da)
							data.write(da)
							assert adr < (0xFFFFFF + 1)
							excess = (adr & 0xFF0000) >> 16
							ptr = (adr & 0x1FFFFF)
							toc.write(pack('<H', int(key)))
							toc.write(pack('<HB', ptr, excess))
							packed = (size & 0xFFFFFF)
							toc.write(pack('<I', packed))
							toc.seek(-1, 1)
		with open(out, 'wb') as pac:
			pac.write(b'PAC ')
			pac.write(pack('<I', i + 1))
			pac.write(toc.getvalue())
			pac.write(data.getvalue())
			pac.flush()

if __name__ == '__main__':
	with open('MCMAHON.JSON', 'w') as f:
		dictt = {'0': {'path': '0.BPE'}, '1': {'path': '30.BPE'}}
		json.dump(dictt, f, indent=4)

	j = Data()
	j.write('MCMAHON.JSON', 'test.pac')