import sys, os, pickle, concurrent.futures as cf, multiprocessing as mp; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import lxml.html
ROW = '<tr class="r"><td><a href="/item/%d">商品 %d</a></td><td class="p">¥%d.00</td><td><span>库存 %d</span></td></tr>\n'
def make_page(kb):
    rows = max(1, int(kb * 1024 / 95))
    return ('<html><head><title>列表</title></head><body><table>' + ''.join(ROW % (i, i, i % 97, i % 13) for i in range(rows)) + '</table></body></html>').encode()

def parse(body): return int(lxml.html.fromstring(body).xpath('count(//a)'))
def parse_tree(body): return lxml.html.fromstring(body)
def parse_links(body): return lxml.html.fromstring(body).xpath('//a/@href')
def noop(x): return 0
def echo_len(b): return len(b)

def main():
    tee('p20')
    ncpu = os.cpu_count()
    print(f'== 一:进程池的固定成本(本机 {ncpu} 个核心,Python 3.14 在 macOS 上的默认启动方式:{mp.get_start_method()})')
    t0 = time.perf_counter(); ex = cf.ProcessPoolExecutor(4); f = ex.submit(noop, 0); f.result(); cold = ms(t0)
    futs = [ex.submit(noop, 0) for _ in range(4)]; [x.result() for x in futs]
    rt = []
    for _ in range(300):
        t0 = time.perf_counter(); ex.submit(noop, 0).result(); rt.append(ms(t0))
    print(f'  创建 4 进程的池并跑完第一个空任务(冷启动):{cold:.0f} ms')
    print(f'  池预热之后,一个空任务来回一趟:中位数 {median(rt):.3f} ms,p95 {pct(rt, 95):.3f} ms(300 次)')
    ex.shutdown()

    print('== 二:不同页面大小,解析同样数量的页面:直接解析 / 8 个线程 / 4 个进程 / 8 个进程(进程池已预热,取 3 次中位数)')
    print(f'  {"页面":>8}{"个数":>6}{"单页解析":>10}{"直接":>9}{"线程×8":>9}{"进程×4":>9}{"进程×8":>9}{"进程×8 相对直接":>16}')
    pools = {4: cf.ProcessPoolExecutor(4), 8: cf.ProcessPoolExecutor(8)}
    for p in pools.values(): list(p.map(noop, range(16)))
    tp = cf.ThreadPoolExecutor(8)
    for kb, n in ((5, 4000), (20, 1500), (100, 300), (500, 60), (2000, 20)):
        page = make_page(kb); pages = [page] * n
        one = median([(lambda t0: (parse(page), ms(t0))[1])(time.perf_counter()) for _ in range(5)])
        def inline(): [parse(b) for b in pages]
        def thr(): list(tp.map(parse, pages))
        def proc(w, cs): list(pools[w].map(parse, pages, chunksize=cs))
        res = {}
        for name, fn in (('inline', inline), ('thr', thr), ('p4', lambda: proc(4, max(1, n // 32))), ('p8', lambda: proc(8, max(1, n // 32)))):
            ts = []
            for _ in range(3):
                t0 = time.perf_counter(); fn(); ts.append(ms(t0))
            res[name] = median(ts)
        print(f'  {len(page) / 1024:>6.0f}KB{n:>6}{one:>8.2f} ms{res["inline"]:>7.0f} ms{res["thr"]:>7.0f} ms{res["p4"]:>7.0f} ms{res["p8"]:>7.0f} ms{res["inline"] / res["p8"]:>14.2f} 倍')
    tp.shutdown()

    print('== 三:只传输页面的成本(进程里什么也不解析,只返回长度):传 N 字节来回一趟')
    ex = pools[4]
    for kb in (5, 100, 2000, 20000):
        page = bytes(kb * 1024)
        ts = []
        for _ in range(20):
            t0 = time.perf_counter(); ex.submit(echo_len, page).result(); ts.append(ms(t0))
        pk = []
        for _ in range(5):
            t0 = time.perf_counter(); pickle.dumps(page, protocol=pickle.HIGHEST_PROTOCOL); pk.append(ms(t0))
        print(f'  {kb:>6} KB:提交 + 返回一趟 {median(ts):.3f} ms;其中 pickle.dumps 本身 {median(pk):.3f} ms')

    print('== 四:返回值的坑')
    page = make_page(100)
    try: pools[4].submit(parse_tree, page).result()
    except Exception as e: print(f'  让子进程返回解析好的 lxml 树:{type(e).__name__}: {str(e)[:60]}')
    t0 = time.perf_counter(); r = pools[4].submit(parse, page).result(); a = ms(t0)
    t0 = time.perf_counter(); r2 = pools[4].submit(parse_links, page).result(); b = ms(t0)
    print(f'  返回一个整数(链接数 {r}):{a:.2f} ms;返回全部 {len(r2)} 个链接字符串的列表:{b:.2f} ms(列表序列化后约 {len(pickle.dumps(r2)) / 1024:.0f} KB)')
    print('== 五:批量提交(map 的 chunksize)的影响:4000 个小页面(约 6 KB,单页解析 0.15 ms),8 个进程')
    page = make_page(5); pages = [page] * 4000
    t0 = time.perf_counter(); [parse(b) for b in pages]; base = ms(t0)
    print(f'  直接解析:{base:.0f} ms')
    for cs in (1, 8, 125):
        ts = []
        for _ in range(3):
            t0 = time.perf_counter(); list(pools[8].map(parse, pages, chunksize=cs)); ts.append(ms(t0))
        print(f'  chunksize={cs:<4}:{median(ts):.0f} ms(相对直接解析 {base / median(ts):.2f} 倍)')
    for p in pools.values(): p.shutdown()

if __name__ == '__main__':
    main()
