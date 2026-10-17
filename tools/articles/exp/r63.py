import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r63'); R = {}
PORT = 7230
N = 200000
def build(name, conf):
    n = Node(PORT, name=name, conf=dict(conf, **{'rdbcompression': 'no'})).start(); c = n.c()
    for i in range(0, N, 5000): c.pipeline([['SET', f'user:{i+j}', 'value-%08d' % (i + j)] for j in range(5000)])
    return n, c
def try_start(n, wait=5):
    (n.dir / 'redis.log').write_text('')
    n.write_conf(); p = subprocess.Popen(['redis-server', str(n.confpath())], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=n.dir); n.p = p
    t0 = time.time()
    while time.time() - t0 < wait:
        if p.poll() is not None: break
        try:
            c = C(PORT, timeout=1)
            if info(c, 'persistence')['loading'] == '0': return True, c, p.poll()
        except Exception: pass
        time.sleep(0.1)
    return False, None, p.poll()
def keylines(n):
    return [l.split('# ', 1)[-1].split('* ', 1)[-1] for l in n.log().splitlines() if any(k in l for k in ('RDB', 'rdb', 'checksum', 'Fatal', 'Bad', 'Internal', 'Wrong', 'corrupt'))]
def chk(path, maxn=14):
    r = subprocess.run(['redis-check-rdb', str(path)], capture_output=True, text=True, timeout=60)
    L = [l for l in (r.stdout + r.stderr).strip().splitlines() if 'AUX FIELD' not in l]
    return r.returncode, L[:maxn]

print(f'== 一:健康的 dump.rdb({N} 个 key)上跑 redis-check-rdb')
n, c = build('p63a', {})
c.do('SAVE'); n.stop(); rdb = n.dir / 'dump.rdb'; good = rdb.read_bytes()
print(f'dump.rdb:{len(good)} 字节;结尾 8 字节(CRC64)= {good[-8:].hex()}')
rc, L = chk(rdb); print('退出码', rc); print('\n'.join('   ' + l for l in L))
R['good'] = dict(size=len(good), crc=good[-8:].hex(), rc=rc, out=L)
print()
print('== 二:把某个 value 里的一个字节改掉(value-00100000 → value-00100X00),再让 Redis 启动')
i = good.find(b'value-00100000'); bad = bytearray(good); bad[i + 11] = ord('X'); rdb.write_bytes(bytes(bad))
up, c2, rc = try_start(n)
print('起来了:', up, ' 退出码:', rc)
for l in keylines(n)[-4:]: print('   ', l[:200])
R['flip_yes'] = dict(up=up, rc=rc, log=keylines(n)[-4:])
rc2, L = chk(rdb, 20); print('redis-check-rdb:'); print('\n'.join('   ' + l for l in L)); R['flip_check'] = L
n.stop()
print()
print('== 三:同样的改动,但这份 RDB 是在 rdbchecksum no 下生成的——没有校验和,Redis 不知道文件坏了')
n2, c = build('p63b', {'rdbchecksum': 'no'})
c.do('SAVE'); n2.stop(); rdb2 = n2.dir / 'dump.rdb'; g2 = rdb2.read_bytes()
print(f'结尾 8 字节 = {g2[-8:].hex()}(全 0 = 未计算校验和)')
i = g2.find(b'value-00100000'); b2 = bytearray(g2); b2[i + 11] = ord('X'); rdb2.write_bytes(bytes(b2))
up, c3, rc = try_start(n2)
print('起来了:', up, ' DBSIZE =', c3.do('DBSIZE') if up else None)
if up:
    print('GET user:100000 →', c3.do('GET', 'user:100000'), '  (原值 value-00100000)')
    R['flip_no'] = dict(up=up, val=c3.do('GET', 'user:100000'))
n2.stop()
print()
print('== 四:截断(只剩前一半)的文件')
rdb.write_bytes(good[:len(good) // 2]); up, c4, rc = try_start(n); print('起来了:', up, ' 退出码:', rc)
for l in keylines(n)[-3:]: print('   ', l[:200])
rc3, L = chk(rdb, 8); print('redis-check-rdb:'); print('\n'.join('   ' + l for l in L)); R['trunc'] = dict(up=up, check=L)
n.stop()
print()
print('== 五:校验和的代价:SAVE 100 万个 key,rdbchecksum yes vs no,每种 5 次取中位')
def savetime(chk_):
    nn = Node(PORT, name='p63t', conf={'rdbchecksum': chk_, 'rdbcompression': 'no'}).start(); cc = nn.c()
    for i in range(0, 1000000, 5000): cc.pipeline([['SET', f'user:{i+j}', 'value-%08d' % (i + j)] for j in range(5000)])
    ts = []
    for _ in range(5):
        t = time.perf_counter(); cc.do('SAVE'); ts.append(time.perf_counter() - t)
    nn.stop(); return ts
ty = savetime('yes'); tn = savetime('no')
print(f'rdbchecksum yes:{[round(x, 3) for x in ty]}  中位 {statistics.median(ty):.3f} s')
print(f'rdbchecksum no :{[round(x, 3) for x in tn]}  中位 {statistics.median(tn):.3f} s')
R['save'] = dict(yes=ty, no=tn)
save('r63', R)
