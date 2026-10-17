import sys, os, subprocess, json, urllib.request; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import pcdp
from pcdp import Chrome
tee('p54')
d = pdir('p54')

def tree(pid):
    out = subprocess.run(['ps', '-axo', 'pid=,ppid=,rss=,command='], capture_output=True, text=True).stdout.splitlines()
    rows = []
    for l in out:
        parts = l.split(None, 3)
        if len(parts) < 4: continue
        rows.append((int(parts[0]), int(parts[1]), int(parts[2]), parts[3]))
    kids = {pid}; changed = True
    while changed:
        changed = False
        for p, pp, rss, cmd in rows:
            if pp in kids and p not in kids: kids.add(p); changed = True
    sel = [r for r in rows if r[0] in kids]
    def kind(cmd):
        if '--type=renderer' in cmd: return '渲染进程'
        if '--type=gpu-process' in cmd: return 'GPU 进程'
        if '--type=utility' in cmd: return '工具进程'
        if '--type=' in cmd: return '其它子进程'
        return '浏览器主进程'
    cnt = {}
    for r in sel: cnt[kind(r[3])] = cnt.get(kind(r[3]), 0) + 1
    return len(sel), sum(r[2] for r in sel) / 1024, cnt

def start(extra=()):
    t0 = time.perf_counter(); ch = Chrome(free_port(9970), d, extra=extra); t_up = ms(t0)
    return ch, t_up

HOST = '--host-resolver-rules=MAP *.test 127.0.0.1'
IMG = b'\x89PNG\r\n\x1a\n' + os.urandom(100 * 1024)
def srv(h):
    p = h.path.split('?')[0]
    if p == '/simple': return h.reply(200, b'<html><body><h1>hi</h1></body></html>', headers={'Content-Type': 'text/html'})
    if p == '/heavy':
        imgs = ''.join(f'<img src="/img/{i}.png" width="50">' for i in range(20))
        return h.reply(200, f'<html><head><link rel="stylesheet" href="/s.css"></head><body><h1>heavy</h1>{imgs}</body></html>'.encode(), headers={'Content-Type': 'text/html'})
    if p.startswith('/img/'): return h.reply(200, IMG, headers={'Content-Type': 'image/png'})
    if p == '/s.css': return h.reply(200, b'body{background:#eee}' + b'/*' + b'x' * 50000 + b'*/', headers={'Content-Type': 'text/css'})
    h.reply(404, b'')

with Srv(srv) as sv:
    B = sv.url('')
    print('== 一:冷启动时间(从 Popen 到调试端口可用 / 再到第一个页面 load 完成),各 5 次')
    ups, loads = [], []
    for _ in range(5):
        t0 = time.perf_counter(); ch = Chrome(free_port(9970), d); up = ms(t0)
        pg = ch.new_page(); t1 = time.perf_counter(); pg.goto(B + '/simple'); ld = ms(t1); pg.close(); ch.stop(); ups.append(up); loads.append(ld)
    print(f'  调试端口可用:中位 {median(ups):.0f} ms(各次 {[round(x) for x in ups]});新建标签页并加载简单页面:中位 {median(loads):.0f} ms(各次 {[round(x) for x in loads]})')
    print('== 二:内存:进程数与各进程 RSS 之和(会把共享内存页重复计算,所以偏大,只用来看趋势),打开 0、1、5、10 个标签页(同一个站点、简单页面)')
    ch = Chrome(free_port(9970), d); time.sleep(1.0); pages = []
    print(f'  {"标签页数":>8}{"进程数":>8}{"RSS 之和":>12}  进程构成')
    for n in (0, 1, 5, 10):
        while len(pages) < n:
            pg = ch.new_page(); pg.goto(B + '/simple'); pages.append(pg)
        time.sleep(0.8); k, rss, cnt = tree(ch.p.pid); print(f'  {n:>8}{k:>8}{rss:>9.0f} MiB  {cnt}')
    for pg in pages: pg.close()
    ch.stop()
    print('== 三:同一站点的新标签页 与 不同站点的新标签页,渲染进程数的增长一样吗(用 --host-resolver-rules 把 *.test 解析到本机,a.test、b.test…是不同站点;每个页面都是通过 CDP 新建的标签页)')
    ch = Chrome(free_port(9970), d, extra=(HOST,)); time.sleep(1.0); pages = []
    print(f'  {"打开的页面":<30}{"进程数":>8}{"渲染进程数":>10}{"RSS 之和":>12}')
    for lab, urls in (('1 个站点 × 1 页', [f'http://a.test:{sv.port}/simple']), ('同一站点再开 4 页(共 5 页)', [f'http://a.test:{sv.port}/simple?{i}' for i in range(4)]), ('4 个不同站点各 1 页(再加 4 页)', [f'http://{c}.test:{sv.port}/simple' for c in 'bcde']), ('再加 5 个不同站点各 1 页', [f'http://{c}.test:{sv.port}/simple' for c in 'fghij'])):
        for u in urls:
            pg = ch.new_page(); pg.goto(u); pages.append(pg)
        time.sleep(0.8); k, rss, cnt = tree(ch.p.pid); print(f'  {lab:<26}{k:>8}{cnt.get("渲染进程", 0):>10}{rss:>9.0f} MiB')
    for pg in pages: pg.close()
    ch.stop()
    print('== 四:不下载图片和样式能省多少(一个含 20 张各 100 KB 图片和一个 50 KB 样式表的页面):用 CDP 的 Network.setBlockedURLs 拦截,统计传输字节与加载耗时,各 5 次')
    ch = Chrome(free_port(9970), d); time.sleep(0.8)
    def measure(block):
        res = []
        for _ in range(5):
            pg = ch.new_page(); pg.send('Network.enable')
            if block: pg.send('Network.setBlockedURLs', urls=['*.png', '*.css'])
            t0 = time.perf_counter(); pg.goto(B + '/heavy'); el = ms(t0)
            nbytes = sum(e['params'].get('encodedDataLength', 0) for e in pg.events if e['method'] == 'Network.loadingFinished')
            blocked = sum(1 for e in pg.events if e['method'] == 'Network.loadingFailed' and e['params'].get('blockedReason'))
            res.append((el, nbytes, blocked)); pg.close()
        return median([r[0] for r in res]), median([r[1] for r in res]), res[-1][2]
    for lab, blk in (('不拦截', False), ('拦截 *.png 和 *.css', True)):
        el, nb, bl = measure(blk); print(f'  {lab}:加载 {el:.0f} ms,传输 {nb / 1024:.0f} KiB,被拦截的请求 {bl} 个')
    ch.stop()
purge()
