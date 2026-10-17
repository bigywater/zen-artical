import struct, sys
d = open(sys.argv[1], 'rb').read(); o = 24; n = b = mx = fr = 0
while o + 16 <= len(d):
    ts, us, il, ol = struct.unpack('<IIII', d[o:o+16]); pk = d[o+16:o+16+il]; o += 16 + il
    n += 1; b += ol; mx = max(mx, ol)
    if len(pk) >= 22:
        fo = struct.unpack('>H', pk[20:22])[0]
        if fo & 0x3fff: fr += 1
print(n, b, mx, fr)
