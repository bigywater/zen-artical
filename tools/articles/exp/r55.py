import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r55'); R = {}
M = Node(7161, name='m55', conf={'repl-diskless-sync': 'no', 'repl-backlog-size': '16kb'}).start(); m = M.c()
for i in range(5): m.do('SET', f'k{i}', i)

class Fake:
    """手写的假从库:只做握手 + PSYNC,自己读原始字节。"""
    def __init__(self):
        self.s = socket.create_connection(('127.0.0.1', 7161)); self.buf = b''
    def cmd(self, *a):
        self.s.sendall(C.enc(a))
    def line(self, t=5):
        self.s.settimeout(t)
        while b'\r\n' not in self.buf:
            self.buf += self.s.recv(65536)
        l, self.buf = self.buf.split(b'\r\n', 1); return l.decode()
    def take(self, n, t=5):
        self.s.settimeout(t)
        while len(self.buf) < n: self.buf += self.s.recv(65536)
        d, self.buf = self.buf[:n], self.buf[n:]; return d
    def drain(self, t=0.5):
        self.s.settimeout(t)
        try:
            while True:
                d = self.s.recv(65536)
                if not d: break
                self.buf += d
        except socket.timeout: pass
        d, self.buf = self.buf, b''; return d
    def handshake(self):
        self.cmd('PING'); self.line()
        self.cmd('REPLCONF', 'listening-port', 7999); self.line()
        self.cmd('REPLCONF', 'capa', 'eof', 'capa', 'psync2'); self.line()
show = lambda b: b.decode().replace('\r\n', ' ⏎ ')

print('== 一:第一次连接:PSYNC ? -1(不知道 replid,也没有 offset)')
f = Fake(); f.handshake(); f.cmd('PSYNC', '?', -1)
l = f.line(); print('主库回复:', l)
_, replid, off = l.split(); off = int(off)
n = int(f.line()[1:]); rdb = f.take(n)
print(f'随后是 RDB 负载:长度行 ${n},前 9 字节 = {rdb[:9]!r}(RDB 魔数 + 版本)')
R['full'] = dict(replid=replid, off=off, rdb=n)
print()
print('== 二:全量同步之后,主库把每条写命令按原样(RESP 编码)推给从库')
w = M.c()
w.do('SET', 'a', 1); w.do('INCR', 'n'); w.do('LPUSH', 'l', 'x', 'y')
raw = f.drain(0.6); print(show(raw))
print(f'流的总长度 {len(raw)} 字节;从库当前 offset = {off} + {len(raw)} = {off + len(raw)}')
cur = off + len(raw); R['stream1'] = len(raw)
print('主库 master_repl_offset =', info(m, 'replication')['master_repl_offset'])
f.s.close(); time.sleep(0.3)
print()
print('== 三:从库断开,主库继续写 3 条命令')
w.do('SET', 'x', 1); w.do('LPUSH', 'l', 'a', 'b'); w.do('DEL', 'a')
print('主库 master_repl_offset =', info(m, 'replication')['master_repl_offset'])
print()
print('== 四:重连,带上 replid 和 offset+1 请求 PSYNC')
f = Fake(); f.handshake(); f.cmd('PSYNC', replid, cur + 1)
l = f.line(); print('主库回复:', l)
raw2 = f.drain(0.6); print('补发的内容:', show(raw2))
print(f'补发了 {len(raw2)} 字节(= 断开期间写入的字节数);从库 offset → {cur + len(raw2)}')
R['cont'] = len(raw2)
f.s.close(); time.sleep(0.3)
print()
print('== 五:几种不能部分重同步的请求')
base = cur + len(raw2)
w.pipeline([['SET', 'pad', 'x' * 100] for _ in range(1000)])
bl = info(m, 'replication')
print(f'(先在主库写入约 100 KB:master_repl_offset = {bl["master_repl_offset"]},backlog 起点 first_byte_offset = {bl["repl_backlog_first_byte_offset"]})')
for name, args in (('replid 不认识', ('deadbeef' * 5, base + 1)), ('offset 比主库还大', (replid, base + 100000000)), ('offset 太旧(早于 backlog 起点)', (replid, base + 1))):
    f = Fake(); f.handshake(); f.cmd('PSYNC', *args); l = f.line(); print(f'{name:<28} PSYNC {str(args[0])[:8]}… {args[1]} → {l[:60]}')
    f.s.close(); time.sleep(0.2)
    if l.startswith('+FULLRESYNC'): pass
s = repl_stats(m); print('主库 stats:', s)
R['stats'] = s
save('r55', R); cleanup([M])
