import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r69'); R = {}
n = Node(7330, name='c69', conf={'cluster-enabled': 'yes', 'cluster-config-file': 'nodes.conf'}).start(); c = n.c()
print('== 一:自己实现的 CRC16(XMODEM)对照服务器的 CLUSTER KEYSLOT')
print('crc16("123456789") = 0x%04X(XMODEM 标准校验值是 0x31C3)' % crc16('123456789'))
rnd = random.Random(3); ok = 0; tot = 20000; ex = []
for i in range(tot):
    k = ''.join(rnd.choice('abcdefghijklmnopqrstuvwxyz0123456789:_{}') for _ in range(rnd.randrange(1, 24)))
    if keyslot(k) == c.do('CLUSTER', 'KEYSLOT', k): ok += 1
    elif len(ex) < 3: ex.append(k)
print(f'随机 key {tot} 个(含 {{ }} 字符):自己算的槽位与服务器一致 {ok} 个,不一致 {tot-ok} 个 {ex}')
for k in ('foo', 'bar', 'user:1000', '{user1}:a', '{user1}:b', 'a{}b'): print(f'  CLUSTER KEYSLOT {k:<12} → {c.do("CLUSTER", "KEYSLOT", k):>5}   自己算 {keyslot(k):>5}')
R['match'] = [ok, tot]
print()
print('== 二:100 万个 key(user:0…user:999999)在 16384 个槽里的分布')
cnt = collections.Counter(keyslot(f'user:{i}') for i in range(1000000))
vals = [cnt.get(s, 0) for s in range(16384)]; mean = 1000000 / 16384
chi = sum((v - mean) ** 2 / mean for v in vals)
print(f'平均 {mean:.2f} 个/槽;最小 {min(vals)},最大 {max(vals)};标准差 {statistics.pstdev(vals):.2f}(泊松期望 {mean**.5:.2f})')
print(f'卡方统计量 = {chi:.0f}(自由度 16383;若完全均匀随机,期望 ≈ 16383,标准差 ≈ {(2*16383)**.5:.0f})')
share = [sum(vals[a:b + 1]) for a, b in ((0, 5460), (5461, 10922), (10923, 16383))]
print('三段槽位(0–5460 / 5461–10922 / 10923–16383)各占 key:', share, [f'{x/10000:.2f}%' for x in share])
R['dist'] = dict(mean=mean, mn=min(vals), mx=max(vals), sd=statistics.pstdev(vals), chi=chi, share=share)
print()
print('== 三:16384 个槽 = 2048 字节的位图:每个 PING 都带着它。让节点连到我伪造的「对端」,读它发来的第一条集群总线消息')
lst = socket.socket(); lst.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); lst.bind(('127.0.0.1', 17331)); lst.listen(1); lst.settimeout(10)
c.do('CLUSTER', 'ADDSLOTSRANGE', 0, 100)
c.do('CLUSTER', 'MEET', '127.0.0.1', 7331, 17331)
conn, _ = lst.accept(); conn.settimeout(5)
buf = b''
while len(buf) < 8: buf += conn.recv(65536)
totlen = struct.unpack('>I', buf[4:8])[0]
while len(buf) < totlen: buf += conn.recv(65536)
sig = buf[:4]; ver, port, typ, count = struct.unpack('>HHHH', buf[8:16])
sender = buf[40:80].decode(); bitmap = buf[80:80 + 2048]
bits = sum(bin(b).count('1') for b in bitmap)
print(f'签名 {sig!r};总长度 totlen = {totlen} 字节;消息类型编号 {typ}(由 CLUSTER MEET 触发的第一条消息);gossip 条目数 count = {count}')
print(f'sender = {sender[:8]}…(CLUSTER MYID = {c.do("CLUSTER", "MYID")[:8]}…,一致: {sender == c.do("CLUSTER", "MYID")});位图 2048 字节里置位的槽数 = {bits}(我分配了 0–100,共 101 个)')
print(f'位图前 16 字节(十六进制):{bitmap[:16].hex()}(槽 0–100 → 前 12 个字节全 ff、第 13 个字节低位置位)')
R['ping'] = dict(totlen=totlen, typ=typ, count=count, bits=bits, bitmap_len=len(bitmap))
conn.close(); lst.close()
print()
print('== 四:如果槽位数是 65536,同样的位图会是 8192 字节;16384 → 2048 字节')
print('16384/8 =', 16384 // 8, '字节;65536/8 =', 65536 // 8, '字节')
save('r69', R); cleanup([n])
