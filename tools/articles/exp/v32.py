import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v32'); reset()
print('发布策略的量化。金丝雀:新版本只拿一小部分流量,按阶段放大,在每个阶段结束时看指标决定继续还是回滚;蓝绿:新旧两套都在,一次性把流量从蓝切到绿。后端是本进程里的 Python 服务(stable 永远正常;canary 有 5% 的请求返回 503),网关是 nginx 1.31.6(用 reload 改配置)')
def stable_app(h): h.reply(200, b'S')
def make_canary(p, seed):
    rng = random.Random(seed); lk = threading.Lock()
    def app(h):
        with lk: bad = rng.random() < p
        h.reply(503 if bad else 200, b'C')
    return app
def conf(pct, S, C):
    pc = f'{pct}%' if pct > 0 else '0.0001%'
    return f'upstream stable {{ server 127.0.0.1:{S.port}; }} upstream canary {{ server 127.0.0.1:{C.port}; }} split_clients "${{request_id}}" $target {{ {pc} canary; * stable; }} server {{ listen {{port}}; location / {{ proxy_pass http://$target; }} }}'

# ============ 一 ============
print('== 一:金丝雀分阶段放量。每个阶段 2 秒、200 个请求/秒(共约 400 个请求),阶段 = 1% → 5% → 25% → 50% → 100%;每个阶段结束时检查 canary 的错误:出现至少 5 个错误且错误率 ≥ 2% 就回滚(把 canary 比例改回 0)。canary 其实有 5% 的请求返回 503。重复 4 次(不同的随机种子),看每次在哪个阶段发现、用户一共看到多少个 503')
def canary_run(seed):
    S = Svc(stable_app); C = Svc(make_canary(0.05, seed)); ng = Nginx('v32a', conf(1, S, C)).start(); stages = [1, 5, 25, 50, 100]; log = []; user_err = 0; detected = None
    for st in stages:
        ng.write(conf(st, S, C)); ng.reload(); time.sleep(0.5)
        res = openloop(lambda i: rpc(ng.port, '/', 5.0, keepalive=False), 200, 2.0, workers=100)
        codes = collections.Counter((b.decode() if code == 200 else str(code)) for ts, (code, b, dt) in res)
        n_c = codes.get('C', 0) + codes.get('503', 0); errs = codes.get('503', 0); user_err += errs
        log.append((st, n_c, errs))
        if errs >= 5 and errs / max(n_c, 1) >= 0.02: detected = st; ng.write(conf(0, S, C)); ng.reload(); break
    ng.stop(); S.stop(); C.stop(); return log, detected, user_err
rows = []
for seed in (1, 2, 3, 4):
    log, det, ue = canary_run(seed)
    rows.append((seed, ' → '.join(f'{st}%:{nc}个请求/{e}个错' for st, nc, e in log), f'{det}% 阶段发现并回滚' if det else '没有发现', ue))
table(rows, ['重复', '各阶段 canary 收到的请求数 / 其中的错误数', '结果', '用户一共看到的 503'])
print('  1% 阶段 canary 只收到几个请求,5% 的错误率几乎肯定一个错误都没有;错误要攒够 5 个才报警,所以通常要到 25% 阶段才发现。越早放大比例,发现越快,但出事时受影响的用户也越多')

# ============ 二 ============
print('== 二:发现概率。用二项分布算(不是实测):canary 的错误率 5%、基线 0%,规则同上(错误 ≥ 5 且错误率 ≥ 2%)。canary 在某个阶段收到的请求数 = 总请求率 × 流量比例 × 观察窗口。下表是“这个阶段能发现问题”的概率')
import math
def p_detect(n, p=0.05, k=5, rate=0.02):
    if n == 0: return 0.0
    lp, lq = math.log(p), math.log(1 - p); total = 0.0
    e0 = max(k, math.ceil(rate * n))
    for e in range(e0, n + 1):
        total += math.exp(math.lgamma(n + 1) - math.lgamma(e + 1) - math.lgamma(n - e + 1) + e * lp + (n - e) * lq)
    return total
rows = []
for rps in (50, 200, 1000):
    for share in (1, 5, 25):
        row = [f'{rps}/s', f'{share}%']
        for win in (10, 60, 300):
            n = int(rps * share / 100 * win); row.append(f'{n} 个请求 · {p_detect(n):.1%}')
        rows.append(tuple(row))
table(rows, ['总请求率', 'canary 比例', '观察 10 s', '观察 60 s', '观察 300 s'])
print('  需要的是 canary 本身收到的请求数,而不是总流量:总请求率低、比例小,就要观察更久;低流量的服务做金丝雀,窗口要按“攒够多少个请求”来定,而不是固定几分钟')

# ============ 三 ============
print('== 三:蓝绿切换。blue 和 green 两套后端(都正常,各回自己的名字),nginx 的 upstream 先指向 blue,在第 2 秒用 reload 改成 green;200 个请求/秒的开环流量共 6 秒。比较三种做法:(a) reload 之后保持 blue 继续运行;(b) reload 之后立刻关掉 blue 进程;(c) 同 (b) 但 nginx 到后端用 keepalive 长连接。统计切换期间的错误数,以及“混合窗口”(第一个 green 应答和最后一个 blue 应答之间的时间)')
BACK = HERE / 'vtmp/v20/backend.py'
def bg_run(kill_blue, keepalive):
    pb, pg = free_port(), free_port()
    blue = subprocess.Popen([sys.executable, str(BACK), str(pb), 'blue'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    green = subprocess.Popen([sys.executable, str(BACK), str(pg), 'green'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); wait_port(pb, 10); wait_port(pg, 10)
    ka = 'keepalive 8;' if keepalive else ''
    kal = 'proxy_http_version 1.1; proxy_set_header Connection "";' if keepalive else ''
    def cfg(p): return f'upstream u {{ server 127.0.0.1:{p}; {ka} }} server {{ listen {{port}}; location / {{ proxy_pass http://u; {kal} }} }}'
    ng = Nginx('v32c', cfg(pb)).start(); out = []; T0 = time.perf_counter(); switched = [None]
    def switcher():
        time.sleep(2.0); ng.write(cfg(pg)); ng.reload(); switched[0] = time.perf_counter() - T0
        if kill_blue: blue.kill()
    th = threading.Thread(target=switcher); th.start()
    res = openloop(lambda i: rpc(ng.port, '/', 5.0, keepalive=keepalive), 200, 6.0, workers=100); th.join()
    ng.stop(); blue.kill(); green.kill()
    errs = sum(1 for ts, (c, b, dt) in res if c != 200); tags = sorted((ts, b.decode()) for ts, (c, b, dt) in res if c == 200)
    first_green = next((t for t, b in tags if b == 'green'), None); last_blue = max((t for t, b in tags if b == 'blue'), default=None)
    return errs, len(res), (last_blue - first_green) if first_green is not None and last_blue is not None else None, first_green, switched[0]
rows = []
for name, kb, ka in (('(a) reload 后保持 blue 运行', False, False), ('(b) reload 后立刻 kill blue', True, False), ('(c) 同 (b),到后端用 keepalive 长连接', True, True)):
    errs, n, mix, fg, sw = bg_run(kb, ka)
    rows.append((name, f'{errs} / {n}', f'{mix * 1000:.0f} ms' if mix is not None and mix > 0 else '没有重叠', f'{(fg - sw) * 1000:.0f} ms' if fg and sw else '-'))
table(rows, ['做法', '错误数 / 请求数', '混合窗口(第一个 green 应答到最后一个 blue 应答)', '从 reload 完成到第一个 green 应答'])
print('  nginx reload 之后,新的 worker 立刻用新配置接新连接,旧 worker 继续处理已经在它手上的请求和长连接直到处理完;所以 blue 要等旧 worker 把在途请求处理完再下线,立刻 kill 会让还在旧 worker 上的在途请求失败')
