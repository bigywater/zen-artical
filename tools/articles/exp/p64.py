import sys, os, math, random, statistics, threading, time, urllib.parse as up, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import requests
from concurrent.futures import ThreadPoolExecutor
tee('p64')
def draw(r):
    """服务器端延迟(秒)的分布:90% 在 5–15 ms、8% 在 30–80 ms、2% 是长尾(100 ms 加上平均 300 ms 的指数分布,最多 3 秒)"""
    x = r.random()
    if x < 0.90: return r.uniform(0.005, 0.015)
    if x < 0.98: return r.uniform(0.03, 0.08)
    return min(3.0, 0.1 + r.expovariate(1 / 0.3))
def srv(h):
    u = up.urlsplit(h.path); q = dict(up.parse_qsl(u.query)); i = int(q.get('i', 0)); r = random.Random(i)
    lat = float(q['d']) if 'd' in q else draw(r); time.sleep(lat)
    a = int(q.get('a', 0)); pers = random.Random(i + 10 ** 6).random()     # 按 URL 固定的失败:每次都一样
    if pers < 0.02: return h.reply(503, b'busy')
    if pers < 0.03: return h.reply(200, b'')            # 软失败:200 但正文是空的
    if random.Random(i * 1000 + a).random() < 0.03: return h.reply(503, b'busy')     # 随机失败:每次尝试独立
    h.reply(200, b'<html>' + b'x' * 2000 + b'</html>')
def nearest_rank(v, p): v = sorted(v); return v[max(0, math.ceil(p / 100 * len(v)) - 1)]
def q_incl(v, p): return statistics.quantiles(v, n=100, method='inclusive')[int(p) - 1]
def q_excl(v, p): return statistics.quantiles(v, n=100, method='exclusive')[int(p) - 1]
def fetch(s, base, i, timeout=5, a=0):
    t0 = time.perf_counter()
    try:
        r = s.get(base + f'/p?i={i}&a={a}', timeout=timeout, stream=True); t_h = time.perf_counter() - t0; body = r.content; t = time.perf_counter() - t0
        return dict(i=i, status=r.status_code, body=len(body), ttfb=t_h, total=t, err=None)
    except Exception as e: return dict(i=i, status=None, body=0, ttfb=None, total=time.perf_counter() - t0, err=type(e).__name__)

with Srv(srv) as sv:
    B = sv.url('')
    s = requests.Session(); s.mount('http://', requests.adapters.HTTPAdapter(pool_maxsize=32))
    N = 2000; t0 = time.perf_counter()
    with ThreadPoolExecutor(16) as ex: res = list(ex.map(lambda i: fetch(s, B, i), range(N)))
    wall = time.perf_counter() - t0
    lat = [r['total'] * 1000 for r in res]
    print('== 一:先看分布:本机服务器上用 16 个线程抓 2000 个 URL(服务器延迟 90% 在 5–15 ms、8% 在 30–80 ms、2% 是长尾;2% 的 URL 固定返回 503、1% 的 URL 固定返回 200 但正文为空,另外每次请求有 3% 的概率随机返回 503)')
    print(f'  总耗时 {wall:.2f} 秒,平均 {statistics.mean(lat):.1f} ms,中位数 {statistics.median(lat):.1f} ms,p90 {q_incl(lat, 90):.1f} ms,p95 {q_incl(lat, 95):.1f} ms,p99 {q_incl(lat, 99):.1f} ms,最大 {max(lat):.0f} ms')
    print(f'  平均值比中位数高 {statistics.mean(lat) / statistics.median(lat):.1f} 倍;低于平均值的请求占 {sum(1 for x in lat if x < statistics.mean(lat)) * 100 / N:.0f}%')
    print('== 二:同一批数据,不同的分位数算法算出来的 p95 / p99 不一样(单位 ms)')
    for n in (100, 2000):
        sub = lat[:n]; print(f'  取前 {n:4d} 个:p99 最近排名 {nearest_rank(sub, 99):7.1f}、statistics.quantiles inclusive(线性插值) {q_incl(sub, 99):7.1f}、exclusive {q_excl(sub, 99):7.1f};p95 最近排名 {nearest_rank(sub, 95):6.1f}、inclusive {q_incl(sub, 95):6.1f}、exclusive {q_excl(sub, 95):6.1f}')
    print('== 三:样本少时 p99 很不稳定(从上面同一个分布里随机生成延迟,每个样本量重复 1000 次,看 p99 的 5%–95% 范围,inclusive 方法)')
    r = random.Random(3); truth = q_incl([draw(r) * 1000 for _ in range(400000)], 99)
    print(f'  用 40 万个样本估计的"真实" p99 ≈ {truth:.0f} ms')
    for n in (100, 1000, 10000):
        ests = sorted(q_incl([draw(r) * 1000 for _ in range(n)], 99) for _ in range(1000)); print(f'  每次 {n:5d} 个样本:p99 的 5%–95% 范围 {ests[50]:6.0f} – {ests[950]:6.0f} ms,中位 {ests[500]:6.0f} ms')
    print('== 四:几个 worker 各自算 p99 再平均,和合在一起算 p99 不是一回事(合成数据,从同一个延迟分布里生成,不是真实请求;4 个 worker 的负载不同:各抓 4000、2000、1000、200 个请求,最后一个 worker 的服务器更慢)')
    r = random.Random(4); workers = []
    for k, (n, slow) in enumerate(((4000, 1.0), (2000, 1.0), (1000, 1.0), (200, 6.0))): workers.append([draw(r) * 1000 * slow for _ in range(n)])
    allv = [x for w in workers for x in w]; p99s = [q_incl(w, 99) for w in workers]
    print(f'  各 worker 的 p99:{[round(x) for x in p99s]} ms;平均 {statistics.mean(p99s):.0f} ms;合在一起算 p99 {q_incl(allv, 99):.0f} ms;按请求数加权平均 {sum(p * len(w) for p, w in zip(p99s, workers)) / len(allv):.0f} ms')
    def hist(v, edges):
        c = [0] * (len(edges) + 1)
        for x in v:
            for j, e in enumerate(edges):
                if x <= e: c[j] += 1; break
            else: c[-1] += 1
        return c
    def hq(counts, edges, p):
        tot = sum(counts); need = p / 100 * tot; acc = 0
        for j, c in enumerate(counts):
            acc += c
            if acc >= need: return edges[j] if j < len(edges) else float('inf')
    E1 = [5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000]; E2 = [10, 20, 30, 40, 50, 60, 80, 100, 150, 200, 300, 400, 600, 800, 1200, 1600, 2400, 3200, 5000]
    merged1 = [sum(x) for x in zip(*[hist(w, E1) for w in workers])]; merged2 = [sum(x) for x in zip(*[hist(w, E2) for w in workers])]
    print(f'  每个 worker 只上报直方图(桶边界 {E1} ms),合并之后估计 p99 = {hq(merged1, E1, 99)} ms(桶的上边界);换成更细的 {len(E2)} 个桶估计 p99 = {hq(merged2, E2, 99)} ms;精确值 {q_incl(allv, 99):.0f} ms')
    print('== 五:超时请求的延迟记不记?(客户端 timeout=0.2 秒,抓 2000 个 URL,16 个线程;2% 的请求是长尾)')
    with ThreadPoolExecutor(16) as ex: res2 = list(ex.map(lambda i: fetch(s, B, i, timeout=0.2), range(N)))
    to = [r for r in res2 if r['err']]; okr = [r for r in res2 if r['status'] == 200 and r['body'] > 0]; allt = [r['total'] * 1000 for r in res2]; okt = [r['total'] * 1000 for r in okr]
    print(f'  超时 {len(to)} 个,错误类型 {dict(collections.Counter(r["err"] for r in to))};超时请求记下的耗时 中位 {statistics.median([r["total"] * 1000 for r in to]):.0f} ms(都被 timeout 截在 200 ms 附近)')
    print(f'  全部 {len(allt)} 个请求(含超时)p99 {q_incl(allt, 99):.0f} ms;只统计成功请求 {len(okt)} 个 p99 {q_incl(okt, 99):.0f} ms;真实耗时的 p99(不设 timeout,第一节的数据)是 {q_incl(lat, 99):.0f} ms')
    print('== 六:"成功率"有几种算法(第一节那 2000 个请求)')
    st = collections.Counter(r['status'] for r in res); good = sum(1 for r in res if r['status'] == 200); full = sum(1 for r in res if r['status'] == 200 and r['body'] > 0)
    print(f'  状态码分布 {dict(st)};只看状态码 200:{good}/{N} = {good * 100 / N:.1f}%;200 且正文非空:{full}/{N} = {full * 100 / N:.1f}%')
    first = res[:200]; last = res[-200:]
    ok_ = lambda rs: sum(1 for r in rs if r['status'] == 200 and r['body'] > 0) * 100 / len(rs)
    print(f'  按窗口看:前 200 个 {ok_(first):.1f}%,后 200 个 {ok_(last):.1f}%;各 200 个一窗口的 10 个窗口:{[round(ok_(res[k:k + 200])) for k in range(0, N, 200)]}')
    fails = [r['i'] for r in res if not (r['status'] == 200 and r['body'] > 0)]
    with ThreadPoolExecutor(16) as ex: res_r = list(ex.map(lambda i: fetch(s, B, i, a=1), fails))
    fixed = sum(1 for r in res_r if r['status'] == 200 and r['body'] > 0)
    print(f'  对失败的 {len(fails)} 个 URL 各重试 1 次:重试成功 {fixed} 个;最终成功率 {(full + fixed) * 100 / N:.1f}%(第一次 {full * 100 / N:.1f}%);一共发出 {N + len(fails)} 个请求(多发 {len(fails) * 100 / N:.1f}%);重试仍失败的 {len(fails) - fixed} 个里,按 URL 固定会失败的有 {sum(1 for r in res_r if not (r["status"] == 200 and r["body"] > 0) and random.Random(r["i"] + 10 ** 6).random() < 0.03)} 个(这是我在服务器里设定的,真实站点上看不到这个标签)')
purge()
