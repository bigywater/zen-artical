import sys, os, subprocess, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
from pcdp import Chrome, Browser
tee('p56')
d = pdir('p56')
LOGO = os.urandom(20 * 1024)
def srv(h):
    p = h.path.split('?')[0]
    ck = next((v for k, v in h.hdrs if k.lower() == 'cookie'), '')
    if p == '/p': return h.reply(200, b'<!doctype html><html><body><h1>page</h1><img src="/logo.png"><script>document.title = "ready"</script></body></html>', headers={'Content-Type': 'text/html', 'Set-Cookie': 'tracker=%d; Path=/' % int(time.time() * 1000)})
    if p == '/logo.png': return h.reply(200, LOGO, headers={'Content-Type': 'image/png', 'Cache-Control': 'max-age=3600'})
    h.reply(404, b'')

def tree_rss(pid):
    out = subprocess.run(['ps', '-axo', 'pid=,ppid=,rss='], capture_output=True, text=True).stdout.splitlines()
    rows = [tuple(map(int, l.split())) for l in out if len(l.split()) == 3]
    kids = {pid}; ch = True
    while ch:
        ch = False
        for p, pp, rss in rows:
            if pp in kids and p not in kids: kids.add(p); ch = True
    return len(kids), sum(r for p, pp, r in rows if p in kids) / 1024

N = 30
def wait_ready(pg, timeout=5):
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < timeout:
        if pg.eval('document.title') == 'ready': return
        time.sleep(0.01)

def run_strategy(name, sv):
    sv.reset(); times = []; t_all = time.perf_counter(); cookies_seen = []; extra = {}
    if name == 'A':                               # 每页启动一个新的浏览器进程
        for i in range(N):
            t0 = time.perf_counter(); ch = Chrome(free_port(9970), d); pg = ch.new_page(); pg.goto(sv.url('/p')); wait_ready(pg); times.append(ms(t0)); pg.close(); ch.stop()
    else:
        ch = Chrome(free_port(9970), d); time.sleep(0.6); b = Browser(ch) if name == 'C' else None; shared = ch.new_page() if name == 'D' else None; t_all = time.perf_counter()
        for i in range(N):
            t0 = time.perf_counter()
            if name == 'B': pg = ch.new_page()
            elif name == 'C': ctx = b.new_context(); pg = b.page_in(ctx)
            else: pg = shared
            pg.goto(sv.url('/p')); wait_ready(pg); times.append(ms(t0))
            if name == 'B': pg.close()
            elif name == 'C': pg.close(); b.close_target(pg.tid); b.dispose_context(ctx)
        extra['rss'] = tree_rss(ch.p.pid)
        if b: b.close()
        if shared: shared.close()
        ch.stop()
    total = (time.perf_counter() - t_all) * 1000
    page_reqs = [l for l in sv.log if l['path'] == '/p']; logo = sum(1 for l in sv.log if l['path'] == '/logo.png')
    ck = [next((v for k, v in l['hdrs'] if k.lower() == 'cookie'), '') for l in page_reqs]
    return dict(total=total, per=median(times), logo=logo, cookie_after_first=sum(1 for c in ck[1:] if c), pages=len(page_reqs), **extra)

NAMES = {'A': '每页启动一个新浏览器', 'B': '复用浏览器,每页一个新标签页(默认 context)', 'C': '复用浏览器,每页一个新的独立 context', 'D': '复用浏览器,反复用同一个标签页'}
with Srv(srv) as sv:
    print(f'== 一:{N} 次加载同一个页面(含一张可缓存的 20 KB 图片):总耗时与单次耗时中位数')
    R = {}
    for k in 'ABCD':
        R[k] = run_strategy(k, sv)
        print(f'  {NAMES[k]:<34}总耗时 {R[k]["total"]:>6.0f} ms;每页中位 {R[k]["per"]:>6.1f} ms')
    print(f'== 二:状态是否泄漏给下一次加载(服务器记录的 Cookie 头与图片请求数;{N} 次加载)')
    print(f'  {"策略":<34}{"第 2–" + str(N) + " 次带了之前的 Cookie":>24}{"图片请求数(缓存命中则少)":>22}')
    for k in 'ABCD': print(f'  {NAMES[k]:<30}{R[k]["cookie_after_first"]:>14} / {N - 1}{R[k]["logo"]:>16}')
    print('== 三:浏览器进程树的内存与进程数(跑完 30 次、关闭前);A 每页都结束浏览器,没有统计')
    for k in 'BCD': print(f'  {NAMES[k]:<30}进程数 {R[k]["rss"][0]},RSS 之和 {R[k]["rss"][1]:.0f} MiB')
    print('== 四:忘了关标签页:打开 60 个标签页不关,与每次关闭、反复用同一个标签页,进程数和内存')
    for lab, mode in (('每次打开新标签页但不关', 'leak'), ('每次打开新标签页并关闭', 'close'), ('反复用同一个标签页', 'reuse')):
        ch = Chrome(free_port(9970), d); time.sleep(0.8); shared = ch.new_page() if mode == 'reuse' else None; held = []
        for i in range(60):
            pg = shared or ch.new_page(); pg.goto(sv.url('/p')); wait_ready(pg)
            if mode == 'leak': held.append(pg)
            elif mode == 'close': pg.close()
        time.sleep(0.8); k, rss = tree_rss(ch.p.pid); print(f'  {lab}(60 次后):进程数 {k},RSS 之和 {rss:.0f} MiB')
        for p in held: p.close()
        if shared: shared.close()
        ch.stop()
purge()
