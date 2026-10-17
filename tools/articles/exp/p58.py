import sys, os, json, urllib.parse as up; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
from pcdp import Chrome
tee('p58')
d = pdir('p58')
APP = """
const q = new URLSearchParams(location.search); const variant = q.get('variant') || 'naive';
const list = document.getElementById('list'); const sentinel = document.getElementById('sentinel');
let page = 1, loading = false, done = false;
async function loadMore() {
  if (loading || done) return; loading = true;
  const r = await fetch('/api/items?page=' + page); const j = await r.json();
  for (const it of j.items) { const li = document.createElement('li'); li.className = 'item'; li.style.height = '100px'; li.textContent = it; list.appendChild(li); }
  page = j.next; loading = false;
  if (!page) { done = true; sentinel.textContent = 'END'; io.disconnect(); window.__done = true; }
  else if (variant === 'reobserve') { io.unobserve(sentinel); io.observe(sentinel); }
}
const io = new IntersectionObserver(entries => { for (const e of entries) if (e.isIntersecting) loadMore(); });
io.observe(sentinel);
"""
def srv(h):
    u = up.urlsplit(h.path); q = dict(up.parse_qsl(u.query))
    if u.path == '/': return h.reply(200, b'<!doctype html><html><body style="margin:0"><ul id="list" style="margin:0;padding:0;list-style:none"></ul><div id="sentinel" style="height:20px">...</div><script src="/app.js"></script></body></html>', headers={'Content-Type': 'text/html'})
    if u.path == '/app.js': return h.reply(200, APP.encode(), headers={'Content-Type': 'application/javascript'})
    if u.path == '/api/items':
        pg = int(q['page']); time.sleep(0.08); items = [f'item {(pg - 1) * 10 + i}' for i in range(10)]
        return h.reply(200, json.dumps(dict(items=items, next=pg + 1 if pg < 10 else None)).encode(), headers={'Content-Type': 'application/json'})
    h.reply(404, b'')

def items(pg): return pg.eval('document.querySelectorAll("#list .item").length')
def height(pg): return pg.eval('document.documentElement.scrollHeight')
def nreq(sv): return sum(1 for l in sv.log if l['path'].startswith('/api/items'))

with Srv(srv) as sv, Chrome(free_port(9970), d) as ch:
    B = sv.url('')
    def open_page(variant='naive', vh=600):
        pg = ch.new_page(); pg.send('Emulation.setDeviceMetricsOverride', width=800, height=vh, deviceScaleFactor=1, mobile=False)
        sv.reset(); pg.goto(B + f'/?variant={variant}'); time.sleep(0.4); return pg
    print('== 一:不滚动:打开页面(视口高度 600 px,每条 100 px,每页 10 条,共 10 页 100 条)后等 1.5 秒')
    pg = open_page(); n0 = items(pg); time.sleep(1.5)
    print(f'  打开后条目数 {n0},1.5 秒后条目数 {items(pg)},服务器收到 /api/items 请求 {nreq(sv)} 次(页面一打开,空列表里的哨兵就在视口内,IntersectionObserver 第一次回调就加载了第 1 页;加载完后哨兵被推到视口外,不滚动就不会再触发);页面总高度 {height(pg)} px'); pg.close()
    print('== 二:一点一点往下滚(每次滚 300 px,滚完等 0.12 秒),连续 3 次条目数没增加就判定到底了')
    pg = open_page(); t0 = time.perf_counter(); steps = 0; last = items(pg); stable = 0; y = 0
    while stable < 3 and steps < 200:
        y += 300; pg.eval(f'window.scrollTo(0, {y})'); steps += 1; time.sleep(0.12)
        n = items(pg); stable = stable + 1 if n == last else 0; last = n
    print(f'  滚了 {steps} 次(含最后确认不再增加的 3 次),条目数 {items(pg)},/api/items 请求 {nreq(sv)} 次,用时 {ms(t0):.0f} ms,页面显示结束标记:{pg.eval("window.__done === true")}'); pg.close()
    print('== 三:每次直接跳到底部(scrollTo 页面高度),等 0.15 秒,重复直到不再增加')
    pg = open_page(); t0 = time.perf_counter(); steps = 0; last = items(pg); stable = 0
    while stable < 2 and steps < 100:
        pg.eval('window.scrollTo(0, document.documentElement.scrollHeight)'); steps += 1; time.sleep(0.15)
        n = items(pg); stable = stable + 1 if n == last else 0; last = n
    print(f'  跳了 {steps} 次,条目数 {items(pg)},/api/items 请求 {nreq(sv)} 次,用时 {ms(t0):.0f} ms,结束标记:{pg.eval("window.__done === true")}'); pg.close()
    print('== 四:视口很高(3000 px)时,朴素写法(只在哨兵"进入"视口时加载一次)会卡住;每次加载后重新 observe 的写法不会')
    for variant, lab in (('naive', '朴素:只响应"进入视口"'), ('reobserve', '修正:加载完成后重新 observe')):
        pg = open_page(variant, 3000); time.sleep(1.5); n_auto = items(pg)
        t0 = time.perf_counter(); steps = 0; last = items(pg); stable = 0
        while stable < 2 and steps < 60:
            pg.eval('window.scrollTo(0, document.documentElement.scrollHeight)'); steps += 1; time.sleep(0.15)
            n = items(pg); stable = stable + 1 if n == last else 0; last = n
        print(f'  {lab}:不滚动等 1.5 秒后条目数 {n_auto};再滚动 {steps} 次后 {items(pg)};/api/items 请求共 {nreq(sv)} 次'); pg.close()
    print('== 五:判断"到底了"的两种办法:页面自己的结束标记(sentinel 文字变成 END) 对 条目数在一段静默期内不再增加')
    pg = open_page(); t0 = time.perf_counter()
    while pg.eval('document.getElementById("sentinel").textContent') != 'END' and time.perf_counter() - t0 < 20:
        pg.eval('window.scrollTo(0, document.documentElement.scrollHeight)'); time.sleep(0.1)
    t_marker = ms(t0)
    pg.close(); pg = open_page(); t0 = time.perf_counter(); last = items(pg); quiet_start = time.perf_counter()
    while time.perf_counter() - quiet_start < 1.0:
        pg.eval('window.scrollTo(0, document.documentElement.scrollHeight)'); time.sleep(0.1)
        n = items(pg)
        if n != last: last = n; quiet_start = time.perf_counter()
    t_quiet = ms(t0)
    print(f'  用结束标记判断:{t_marker:.0f} ms 到底;用"条目数 1.0 秒内不再增加"判断:{t_quiet:.0f} ms(比结束标记多出约 {t_quiet - t_marker:.0f} ms;这是两次独立加载的差,其中包含那 1.0 秒静默期);两者都得到 {items(pg)} 条'); pg.close()
purge()
