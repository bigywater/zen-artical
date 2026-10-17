import sys, os, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r39b')
n = Node(7239).start(); c = n.c()
c.do('CONFIG', 'SET', 'stream-node-max-entries', 4)
ids = [c.do('XADD', 's', f'{1000+i*7}-{i%3}', 'temp', str(20 + i)) for i in range(10)]
print('写入的 10 个 ID:', ids)
raw = c.do('DUMP', 's', raw=True)
print('DUMP 长度', len(raw), '字节;第 1 字节(RDB 类型号)=', raw[0])
pos = 1
def rlen(b, p):
    x = b[p]; t = x >> 6
    if t == 0: return x & 0x3f, p + 1
    if t == 1: return ((x & 0x3f) << 8) | b[p+1], p + 2
    if x == 0x80: return struct.unpack('>I', b[p+1:p+5])[0], p + 5
    if x == 0x81: return struct.unpack('>Q', b[p+1:p+9])[0], p + 9
    raise ValueError(hex(x))
nodes, pos = rlen(raw, pos)
print('RDB 里 listpack 节点数 =', nodes, '(与 XINFO radix-tree-keys =', kv(c.do('XINFO', 'STREAM', 's'))['radix-tree-keys'], ')')
for i in range(nodes):
    kl, pos = rlen(raw, pos); key = raw[pos:pos+kl]; pos += kl
    ll, pos = rlen(raw, pos); lp = raw[pos:pos+ll]; pos += ll
    ms, seq = struct.unpack('>QQ', key)
    tot, cnt = struct.unpack('<IH', lp[:6])
    print(f'节点 {i}: key 长 {kl} 字节 = 大端(ms={ms}, seq={seq});listpack {ll} 字节,头部记录 {tot} 字节 / {cnt} 个元素')
print('对照第 1、5、9 条的 ID:', ids[0], ids[4], ids[8])
cleanup([n])
