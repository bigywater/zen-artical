import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import requests, logging, concurrent.futures as cf
from requests.adapters import HTTPAdapter
tee('p2')
HOLD = 0.2
def slow(h): time.sleep(HOLD); h.reply(200, b'ok')

class Cnt(logging.Handler):
    def __init__(self): super().__init__(); self.full = 0; self.msgs = []
    def emit(self, r):
        m = r.getMessage()
        if 'pool is full' in m: self.full += 1; self.msgs.append(m)
cnt = Cnt(); lg = logging.getLogger('urllib3.connectionpool'); lg.addHandler(cnt); lg.setLevel(logging.WARNING); lg.propagate = False

def wave(sess, url, n):
    t0 = time.perf_counter()
    with cf.ThreadPoolExecutor(n) as ex: list(ex.map(lambda _: sess.get(url).status_code, range(n)))
    return ms(t0)

def mk(**kw):
    s = requests.Session(); a = HTTPAdapter(**kw); s.mount('http://', a); return s

print('== 一:默认的连接池(pool_maxsize=10),30 个线程共用一个 Session,每个请求在服务器上停 0.2 秒')
with Srv(slow) as sv:
    cnt.full = 0; cnt.msgs.clear()
    s = requests.Session(); a = s.get_adapter('http://x')
    print(f'  默认适配器:pool_connections={a._pool_connections} pool_maxsize={a._pool_maxsize} pool_block={a._pool_block}')
    t = wave(s, sv.url('/'), 30)
    print(f'  第 1 波(30 个并发请求):耗时 {t:.0f} ms;服务器同时在处理的请求峰值 {sv.peak};累计接受 {sv.n_conn} 条连接')
    print(f'  urllib3 的 "Connection pool is full" 警告 {cnt.full} 条' + (f';第一条原文:{cnt.msgs[0]}' if cnt.msgs else ''))

print('== 二:连续两波 30 并发:池里只留得住 10 条,第二波只能复用 10 条')
for label, kw in (('默认 pool_maxsize=10', {}), ('pool_maxsize=30', dict(pool_maxsize=30))):
    with Srv(slow) as sv:
        cnt.full = 0
        s = mk(**kw)
        t1 = wave(s, sv.url('/'), 30); c1 = sv.n_conn; w1 = cnt.full
        t2 = wave(s, sv.url('/'), 30); c2 = sv.n_conn; w2 = cnt.full
        print(f'  {label}:第 1 波累计 {c1} 条连接({t1:.0f} ms,警告 {w1} 条);第 2 波累计 {c2} 条连接,新增 {c2 - c1} 条({t2:.0f} ms,累计警告 {w2} 条)')

print('== 三:pool_block=True:池满了就让线程排队等连接,而不是新建后丢掉')
with Srv(slow) as sv:
    cnt.full = 0
    s = mk(pool_maxsize=10, pool_block=True)
    t = wave(s, sv.url('/'), 30)
    print(f'  pool_maxsize=10, pool_block=True,30 个并发:耗时 {t:.0f} ms;服务器同时处理的峰值 {sv.peak};累计 {sv.n_conn} 条连接;警告 {cnt.full} 条')
    print(f'  对照:30 个请求每个 {HOLD * 1000:.0f} ms,如果最多只能 10 个并发,理论下限是 3 批 × {HOLD * 1000:.0f} = {3 * HOLD * 1000:.0f} ms')
with Srv(slow) as sv:
    s = mk(pool_maxsize=30)
    t = wave(s, sv.url('/'), 30)
    print(f'  对照 pool_maxsize=30:耗时 {t:.0f} ms;服务器同时处理的峰值 {sv.peak};累计 {sv.n_conn} 条连接')

print('== 四:pool_connections 是缓存的"主机池"个数:在 3 个主机(端口)之间轮流请求')
for pc in (1, 3):
    svs = [Srv(lambda h: h.reply(200, b'ok')) for _ in range(3)]
    for x in svs: x.th.start()
    s = mk(pool_connections=pc)
    for rnd in range(4):
        for x in svs: s.get(x.url('/'))
    print(f'  pool_connections={pc}:3 个服务器上累计连接数 {[x.n_conn for x in svs]}(共 12 次请求,每个主机 4 次)')
    for x in svs: x.stop()
purge()
