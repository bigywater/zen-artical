import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r62'); R = {}
PORT = 7220
def build(name, N=1000):
    n = Node(PORT, name=name, conf={'appendonly': 'yes', 'appendfsync': 'always'}).start(); c = n.c()
    for i in range(N): c.do('SET', f'k{i}', f'v{i}')
    n.stop(); time.sleep(0.3)
    d = n.dir / 'appendonlydir'; incr = [p for p in d.iterdir() if p.name.endswith('.incr.aof')][0]
    return n, d, incr
def try_start(n, extra=(), wait=4):
    """直接起 redis-server;返回 (是否起来了, 日志里的关键行, DBSIZE)。"""
    (n.dir / 'redis.log').write_text('')
    n.write_conf(); p = subprocess.Popen(['redis-server', str(n.confpath())] + list(extra), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=n.dir)
    n.p = p; t0 = time.time(); up = False; db = None
    while time.time() - t0 < wait:
        if p.poll() is not None: break
        try:
            c = C(PORT, timeout=1)
            if info(c, 'persistence')['loading'] == '0':
                up = True; db = c.do('DBSIZE'); break
        except Exception: pass
        time.sleep(0.1)
    lines = [l.split('* ', 1)[-1].split('# ', 1)[-1] for l in n.log().splitlines() if any(k in l for k in ('AOF', 'aof', 'Bad', 'short read', 'Unexpected', 'redis-check', 'Fatal', 'loaded'))]
    return up, lines, db, p.poll()
def show(lines, maxn=8):
    for l in lines[:maxn]: print('   ', l[:320])

print('== 一:写入 1000 个 key(appendfsync always),正常退出,再启动:基线')
n, d, incr = build('p62a')
size = incr.stat().st_size; print(f'incr 文件 {incr.name}:{size} 字节')
up, lines, db, rc = try_start(n); print('起来了:', up, ' DBSIZE =', db); n.stop()
R['base'] = dict(size=size, db=db)
print()
print('== 二:模拟崩溃时写了一半:截掉 incr 文件末尾 5 个字节(最后一条命令不完整)')
data = incr.read_bytes(); incr.write_bytes(data[:-5])
print('aof-load-truncated yes(默认):')
up, lines, db, rc = try_start(n); print('  起来了:', up, ' DBSIZE =', db); show(lines); n.stop()
R['trunc_yes'] = dict(up=up, db=db)
print('aof-load-truncated no:')
incr.write_bytes(data[:-5]); n.conf['aof-load-truncated'] = 'no'
up, lines, db, rc = try_start(n); print('  起来了:', up, ' 进程退出码:', rc); show(lines); n.stop()
R['trunc_no'] = dict(up=up, rc=rc)
n.conf.pop('aof-load-truncated', None)
print()
print('== 三:文件中间被写坏(把第 500 个 key 的命令头覆盖成 8 个字节的垃圾):Redis 拒绝启动')
incr.write_bytes(data)
i = data.find(b'\r\n$4\r\nk500\r\n'); bad = bytearray(data); bad[i + 2:i + 10] = b'GARBAGE!'; incr.write_bytes(bytes(bad))
up, lines, db, rc = try_start(n); print('起来了:', up, ' 进程退出码:', rc); show(lines); n.stop()
R['bad'] = dict(up=up, rc=rc, off=i)
print()
print('== 四:redis-check-aof(只检查,不修改)')
man = str(n.dir / 'appendonlydir' / 'appendonly.aof.manifest')
r = subprocess.run(['redis-check-aof', man], capture_output=True, text=True, input='n\n', timeout=60)
out_ = [l for l in (r.stdout + r.stderr).strip().splitlines() if not any(k in l for k in ('AUX FIELD', '[info]', 'Checksum', 'looks OK', 'Checking RDB'))]; print('\n'.join('   ' + l for l in out_)); R['check'] = out_
print()
print('== 五:redis-check-aof --fix:把文件截到最后一条完好命令,再启动')
r = subprocess.run(['redis-check-aof', '--fix', man], capture_output=True, text=True, input='y\n', timeout=60)
out_ = (r.stdout + r.stderr).strip().splitlines(); out_ = [l for l in out_ if not any(k in l for k in ('AUX FIELD', '[info]', 'Checksum', 'looks OK', 'Checking RDB'))]; print('\n'.join('   ' + l for l in out_)); R['fixout'] = out_
fixed = incr.stat().st_size; print(f'修复后 incr 文件 {fixed} 字节(原 {size} 字节)')
up, lines, db, rc = try_start(n); print('起来了:', up, ' DBSIZE =', db); n.stop()
R['fix'] = dict(size=fixed, db=db, up=up)
print(f'数据损失:{1000 - db} 个 key(损坏点 k500 及之后的全部命令)')
print()
print('== 六:Redis 8 的 aof-load-corrupt-tail-max-size:允许丢弃损坏点之后最多这么多字节,然后照常启动')
for lim in (1000, 16500, 20000):
    incr.write_bytes(bytes(bad)); n.conf['aof-load-corrupt-tail-max-size'] = str(lim)
    up, lines, db, rc = try_start(n); print(f'aof-load-corrupt-tail-max-size {lim}: 起来了 {up},DBSIZE = {db},退出码 {rc}')
    show([l for l in lines if 'Bad file' in l or 'corrupt' in l.lower() or 'Truncat' in l][:3]); n.stop()
    R[f'tail{lim}'] = dict(up=up, db=db)
save('r62', R); cleanup([n])
