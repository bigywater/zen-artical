import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
from etcdt import Etcd, b64
import shutil
tee('v49'); reset()
print('大量实例同时(重新)注册时,etcd 3.7.2 的 watch 要向每个 watcher 推送每一个事件:事件总数 = 变更数 × 监听这个前缀的 watcher 数。单节点 etcd,watcher 是 HTTP 流连接(每个 watcher 一个线程,只数收到的事件个数,不解析 JSON),写入用 8 个线程并发。etcd 内存用 ps 看 etcd 进程的 RSS')
shutil.rmtree(TT / 'etcd_v49_0', ignore_errors=True); E1 = Etcd('v49', n=1).start(); EPID = E1.procs[0].pid
def rss(): return int(sh(f'ps -o rss= -p {EPID}').strip() or 0) / 1024
class RawWatch:
    def __init__(self, prefix, start_rev=None):
        self.n = 0; self.last = None; self.stop = False; self.t0 = time.perf_counter()
        c = http.client.HTTPConnection('127.0.0.1', E1.CP[0], timeout=120); self.c = c
        cr = {'key': b64(prefix), 'range_end': b64(prefix[:-1] + chr(ord(prefix[-1]) + 1))}
        if start_rev: cr['start_revision'] = str(start_rev)
        c.request('POST', '/v3/watch', json.dumps({'create_request': cr}), {'Content-Type': 'application/json'}); self.r = c.getresponse()
        self.th = threading.Thread(target=self._read, daemon=True); self.th.start()
    def _read(self):
        try:
            while not self.stop:
                line = self.r.fp.readline()
                if not line: break
                k = line.count(b'"mod_revision"')
                if k: self.n += k; self.last = time.perf_counter()
        except Exception: pass
    def close(self):
        self.stop = True
        try: self.c.sock.shutdown(socket.SHUT_RDWR)
        except Exception: pass
        self.th.join(2)
        try: self.c.close()
        except Exception: pass
def write_storm(keys, threads=8):
    lat = []; lk = threading.Lock(); chunks = [keys[i::threads] for i in range(threads)]
    def w(ch):
        c = E1.conn(0, 30)
        for k in ch:
            t = time.perf_counter(); Etcd.req(c, '/v3/kv/put', {'key': b64(k), 'value': b64('127.0.0.1:8080')}); d = time.perf_counter() - t
            with lk: lat.append(d)
    t0 = time.perf_counter(); ths = [threading.Thread(target=w, args=(ch,)) for ch in chunks]; [t.start() for t in ths]; [t.join() for t in ths]; return lat, time.perf_counter() - t0, t0

# ============ 一 ============
print('== 一:注册风暴 × watcher 数。1000 个实例的注册信息(1000 个 put)在 8 个并发线程里一次性写完;W 个 watcher 都监听同一个前缀 /svc/。统计:put 延迟 p50 / p99,写完总用时,所有 watcher 都收到全部 1000 个事件用了多久(从风暴开始算),etcd 内存 RSS 的变化(MB),以及事件总数 = 收到的事件数之和')
rows = []
for W in (0, 50, 200, 500):
    base = f'/svc{W}/'; ws = [RawWatch(base) for _ in range(W)]; time.sleep(0.5); m0 = rss()
    lat, dt, t0 = write_storm([f'{base}i{i:05d}' for i in range(1000)])
    t_done = None
    deadline = time.perf_counter() + 30
    while W and time.perf_counter() < deadline:
        if all(w.n >= 1000 for w in ws): t_done = max(w.last for w in ws) - t0; break
        time.sleep(0.05)
    m1 = rss(); tot = sum(w.n for w in ws)
    rows.append((W, f'{pct(lat, 50) * 1000:.1f} / {pct(lat, 99) * 1000:.1f} ms', f'{dt:.2f} s', (f'{t_done:.2f} s' if t_done else '-' if W == 0 else '超时'), f'{tot:,}', f'{m1 - m0:+.0f} MB'))
    for w in ws: w.close()
table(rows, ['watcher 数 W', 'put 延迟 p50 / p99', '1000 个 put 写完用时', '全部 watcher 收齐 1000 个事件用时', '收到的事件总数', 'etcd 内存变化'])
print('  事件总数 = 1000 × W:同样的 1000 次注册,watcher 越多,etcd 要推送的事件越多。put 的延迟和“所有 watcher 都收齐”的用时都随 W 增长(看上表),etcd 内存也涨;但要注意 watcher 的读线程(Python)、写入线程和 etcd 都在同一台机器上抢 CPU,延迟增长里有多少来自 etcd 的推送、多少来自测量环境本身,这个实验分不开')

# ============ 二 ============
print('== 二:按服务分片监听。20 个服务,每个服务 50 个实例(共 1000 个实例),W = 200 个 watcher,每个 watcher 只关心一个服务(每个服务 10 个 watcher)。对照:(a) 每个 watcher 监听全局前缀 /all/(每个事件推给 200 个 watcher);(b) 每个 watcher 只监听自己关心的 /all/<服务名>/ 前缀。同样写 1000 个 put。统计收到的事件总数、全部 watcher 收齐各自该收的事件用时、etcd 内存变化')
rows = []
for name, shard in (('(a) 全局前缀', False), ('(b) 按服务前缀', True)):
    ws = []; keys = [f'/all{int(shard)}/s{s:02d}/i{i:03d}' for s in range(20) for i in range(50)]
    for w in range(200):
        s = w % 20; ws.append(RawWatch(f'/all{int(shard)}/s{s:02d}/' if shard else f'/all{int(shard)}/'))
    time.sleep(0.5); m0 = rss(); lat, dt, t0 = write_storm(keys)
    need = 50 if shard else 1000; deadline = time.perf_counter() + 30; t_done = None
    while time.perf_counter() < deadline:
        if all(w.n >= need for w in ws): t_done = max(w.last for w in ws) - t0; break
        time.sleep(0.05)
    m1 = rss(); tot = sum(w.n for w in ws)
    rows.append((name, f'{tot:,}', f'{t_done:.2f} s' if t_done else '超时', f'{m1 - m0:+.0f} MB', f'{pct(lat, 99) * 1000:.1f} ms'))
    for w in ws: w.close()
table(rows, ['做法', '收到的事件总数', '收齐用时', 'etcd 内存变化', 'put 延迟 p99'])
print('  按服务前缀分片之后,每个 watcher 只收到它关心的那 50 个事件,事件总数是全局前缀的二十分之一;服务发现的 key 设计成 /服务名/实例 而不是平铺在一个前缀下,就是为了让 watcher 只订阅自己用到的服务')

# ============ 三 ============
print('== 三:重连风暴。200 个 watcher 都监听 /svc3/,同时都在断线 1 秒之后重连,各自从旧的 revision 开始补发(这期间已经写入了 1000 个事件)。统计:补齐所有 watcher 需要的时间,以及 etcd 内存')
base = '/svc3/'; ws = [RawWatch(base) for _ in range(200)]; time.sleep(0.5)
rev0 = int(E1.call(0, '/v3/kv/range', {'key': b64('/x'), 'limit': 1})[1]['header']['revision']) + 1
for w in ws: w.close()
lat, dt, t0 = write_storm([f'{base}i{i:05d}' for i in range(1000)]); time.sleep(1.0); m0 = rss(); t1 = time.perf_counter()
ws2 = [RawWatch(base, start_rev=rev0) for _ in range(200)]; deadline = time.perf_counter() + 60; t_done = None
while time.perf_counter() < deadline:
    if all(w.n >= 1000 for w in ws2): t_done = max(w.last for w in ws2) - t1; break
    time.sleep(0.05)
m1 = rss(); tot = sum(w.n for w in ws2)
table([('200 个 watcher 同时重连并补发', f'{tot:,}', f'{t_done:.2f} s' if t_done else '超时', f'{m1 - m0:+.0f} MB')], ['情形', '补发的事件总数', '全部补齐用时', 'etcd 内存变化'])
for w in ws2: w.close()
print('  重连时从旧 revision 补发历史事件,每个 watcher 要补 1000 个事件,200 个同时重连就是 20 万个事件一起补(看上表的用时和内存变化)。注册中心恢复后所有客户端同时重连是 watch 压力最大的时刻之一,客户端重连要加随机退避,避免同时涌入(见第 3 篇)。第二节里“etcd 内存变化”几乎为 0,是因为第一节已经把 etcd 的内存撑起来了,该列只在第一、三节有参考意义')
E1.procs[0].kill()
