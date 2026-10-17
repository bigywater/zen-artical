import sys, os, json, random, urllib.parse as up, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
from pcdp import Chrome
import websocket
tee('p55')
d = pdir('p55')
PAGE_JS = """
const list = document.getElementById('list');
function add(n, base) { for (let i = 0; i < n; i++) { const li = document.createElement('li'); li.className = 'item'; li.textContent = 'item ' + (base + i); list.appendChild(li); } }
const q = new URLSearchParams(location.search); const mode = q.get('mode'); const d1 = +q.get('d1'), d2 = +q.get('d2');
(async () => {
  if (mode === 'longpoll') fetch(q.get('hang'), {mode: 'no-cors'});
  const r1 = await fetch('/data?d=' + d1 + '&n=' + (mode === 'two' ? 5 : 20)); const j1 = await r1.json(); add(j1.n, 0);
  if (mode === 'two') { const r2 = await fetch('/data?d=' + d2 + '&n=15'); const j2 = await r2.json(); add(j2.n, 5); }
})();
"""
stop_evt = threading.Event()
def srv(h):
    u = up.urlsplit(h.path); q = dict(up.parse_qsl(u.query))
    if u.path == '/p': return h.reply(200, b'<!doctype html><html><body><ul id="list"></ul><script src="/page.js"></script></body></html>', headers={'Content-Type': 'text/html'})
    if u.path == '/page.js': return h.reply(200, PAGE_JS.encode(), headers={'Content-Type': 'application/javascript'})
    if u.path == '/data':
        time.sleep(int(q.get('d', 0)) / 1000); return h.reply(200, json.dumps({'n': int(q.get('n', 20))}).encode(), headers={'Content-Type': 'application/json'})
    h.reply(404, b'')
def srv_hang(h):
    stop_evt.wait(15); h.reply(200, b'{}')

def count(pg): return pg.eval('document.querySelectorAll("#list .item").length')
def wait_poll(pg, want, timeout=6.0, step=0.05):
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < timeout:
        if count(pg) >= want: return True
        time.sleep(step)
    return False
def wait_idle(pg, quiet=0.3, timeout=6.0):
    """网络空闲:没有在途请求,且至少 quiet 秒内没有新的网络事件"""
    t0 = time.perf_counter(); inflight = set(); last = time.perf_counter()
    for e in pg.events:
        pass
    # 事件在 goto 前 Network.enable 之后已累积在 pg.events 里
    evs = list(pg.events); pg.events.clear()
    def feed(e):
        nonlocal last
        m, p = e['method'], e['params']
        if m == 'Network.requestWillBeSent': inflight.add(p['requestId']); last = time.perf_counter()
        elif m in ('Network.loadingFinished', 'Network.loadingFailed'): inflight.discard(p['requestId']); last = time.perf_counter()
    for e in evs: feed(e)
    while time.perf_counter() - t0 < timeout:
        if not inflight and time.perf_counter() - last >= quiet: return True
        pg.ws.settimeout(0.05)
        try:
            m = json.loads(pg.ws.recv())
            if 'method' in m: feed(m)
        except websocket.WebSocketTimeoutException: pass
    return False

STRATS = [('固定等待 0.5 秒', lambda pg: (time.sleep(0.5), None)[1]), ('固定等待 1.5 秒', lambda pg: (time.sleep(1.5), None)[1]), ('轮询:出现第一个 .item 就继续', lambda pg: wait_poll(pg, 1)),
          ('轮询:等到 20 个 .item', lambda pg: wait_poll(pg, 20)), ('等网络空闲(0.3 秒内无请求,最长 6 秒)', lambda pg: wait_idle(pg))]
rng = random.Random(55)
with Srv(srv) as sv, Srv(srv_hang) as sh, Chrome(free_port(9970), d) as ch:
    B = sv.url(''); HANG = sh.url('/hang')
    time.sleep(0.8)
    LOADS = 12
    cases = {}
    for kind in ('single', 'two', 'longpoll'):
        cases[kind] = [(rng.randint(50, 1100), rng.randint(300, 900)) for _ in range(LOADS)]
    TITLE = {'single': '页面 A:一次请求,数据在 0.05–1.1 秒(随机)后到达,一次渲染 20 条', 'two': '页面 B:两阶段加载:第一次请求(0.05–1.1 秒后)渲染 5 条,第二次请求(再过 0.3–0.9 秒)再渲染 15 条', 'longpoll': '页面 C:同页面 A,但页面一直挂着一个 15 秒的长连接请求(像轮询或推送;放在另一个端口的服务器上,免得占满 Chrome 对同一主机端口的并发连接数)'}
    SEC = {'single': '一', 'two': '二', 'longpoll': '三'}
    for kind in ('single', 'two', 'longpoll'):
        print(f'== {SEC[kind]}:{TITLE[kind]}(每个策略各 {LOADS} 次加载,延迟序列相同)')
        print(f'  {"等待策略":<36}{"拿到完整 20 条":>14}{"平均耗时":>10}{"平均多等":>10}')
        for lab, fn in STRATS:
            ok = 0; tot = 0.0; ideal = 0.0
            for d1, d2 in cases[kind]:
                pg = ch.new_page(); pg.send('Network.enable'); t0 = time.perf_counter()
                pg.goto(B + f'/p?mode={kind}&d1={d1}&d2={d2}&hang={HANG}')
                fn(pg); el = time.perf_counter() - t0
                n = count(pg); ok += (n == 20); tot += el
                ideal += (d1 + (d2 if kind == 'two' else 0)) / 1000
                pg.close()
            print(f'  {lab:<32}{ok:>8} / {LOADS}{tot / LOADS * 1000:>8.0f} ms{(tot - ideal) / LOADS * 1000:>8.0f} ms')
        print(f'  ("平均多等" = 平均耗时减去数据实际到齐所需的时间)')
    stop_evt.set()
purge()
