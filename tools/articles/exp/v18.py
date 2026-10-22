import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v18'); reset()
print('三个后端 A、B、C(本进程里的 Python 服务,回自己的名字)放在 nginx 1.31.6 的一个 upstream 里,看各种负载均衡指令的实际分布;最后把 nginx 的“平滑加权轮询”用 Python 手写一遍,和 nginx 真实的选择顺序逐个比对')
def backend(tag, delay=0.0):
    def app(h):
        if delay: time.sleep(delay)
        h.reply(200, tag.encode())
    return Svc(app)
def ngx(name, upstream_body, loc_extra=''):
    return Nginx(name, f'upstream u {{ {upstream_body} }} server {{ listen {{port}}; location / {{ proxy_pass http://u; {loc_extra} }} }}').start()
def seq(ng, n, headers=None):
    out = []
    for i in range(n):
        st, body, _ = rpc(ng.port, '/', 5.0, headers=headers(i) if headers else None)
        out.append(body.decode() if st == 200 else str(st))
    return out
A, B, C = backend('A'), backend('B'), backend('C')
def srv(w=None):
    return ' '.join(f'server 127.0.0.1:{s.port}{(" weight=%d" % w[i]) if w else ""};' for i, s in enumerate((A, B, C)))

# ============ 一 ============
print('== 一:分布。每种配置顺序发 700 个请求(一条一条串行),统计 A / B / C 各收到多少。ip_hash 用 client 的地址(这里所有请求都来自 127.0.0.1);hash $http_x_user 用 X-User 头(700 个请求带 700 个不同的用户名);consistent 是 ketama 一致性哈希')
rows = []
for name, body, extra, hd in (('默认(轮询)', srv(), '', None), ('weight=5:1:1', srv((5, 1, 1)), '', None), ('weight=3:2:1', srv((3, 2, 1)), '', None), ('ip_hash(全是 127.0.0.1)', 'ip_hash; ' + srv(), '', None), ('hash $http_x_user', 'hash $http_x_user; ' + srv(), '', lambda i: {'X-User': f'user{i}'}), ('hash $http_x_user consistent', 'hash $http_x_user consistent; ' + srv(), '', lambda i: {'X-User': f'user{i}'}), ('random', 'random; ' + srv(), '', None), ('random two least_conn', 'random two least_conn; ' + srv(), '', None)):
    ng = ngx('v18a', body, extra); s = seq(ng, 700, hd); ng.stop(); c = collections.Counter(s)
    rows.append((name, c.get('A', 0), c.get('B', 0), c.get('C', 0)))
table(rows, ['指令', 'A', 'B', 'C'])

# ============ 二 ============
print('== 二:后端速度不一样时的 least_conn。A、B 每个请求 10 ms,C 每个请求 100 ms;16 个并发线程各发 100 个请求(共 1600 个)。比较轮询 / least_conn / random two least_conn 的分布和延迟')
SA, SB, SC = backend('A', 0.01), backend('B', 0.01), backend('C', 0.1)
rows = []
for name, extra_up in (('轮询', ''), ('least_conn', 'least_conn;'), ('random two least_conn', 'random two least_conn;')):
    body = extra_up + ' ' + ' '.join(f'server 127.0.0.1:{s.port};' for s in (SA, SB, SC)); ng = ngx('v18b', body)
    lat = []; got = collections.Counter(); lk = threading.Lock()
    def w(i):
        for _ in range(100):
            st, b, dt = rpc(ng.port, '/', 5.0)
            with lk: lat.append(dt); got[b.decode()] += 1
    t0 = time.perf_counter(); ths = [threading.Thread(target=w, args=(i,)) for i in range(16)]; [t.start() for t in ths]; [t.join() for t in ths]; dt = time.perf_counter() - t0; ng.stop()
    rows.append((name, got['A'], got['B'], got['C'], f'{statistics.median(lat) * 1000:.0f} ms', f'{pct(lat, 99) * 1000:.0f} ms', f'{1600 / dt:.0f}/s'))
table(rows, ['指令', 'A(10 ms)', 'B(10 ms)', 'C(100 ms)', '延迟中位数', 'p99', '总吞吐'])

# ============ 三 ============
print('== 三:手写平滑加权轮询(smooth weighted round-robin)。算法:每个节点有 weight 和 current;每次选择先让所有节点 current += weight,选 current 最大的节点,再让它的 current -= 总权重。拿它的输出,和 nginx 真实的选择顺序逐个比对')
class SWRR:
    def __init__(s, ws): s.names = list(ws); s.w = dict(ws); s.cur = {k: 0 for k in ws}; s.tot = sum(ws.values())
    def next(s):
        for k in s.names: s.cur[k] += s.w[k]
        best = max(s.names, key=lambda k: s.cur[k]); s.cur[best] -= s.tot; return best
class RR:
    def __init__(s, names): s.names, s.i = list(names), 0
    def next(s): r = s.names[s.i % len(s.names)]; s.i += 1; return r
rows = []
for name, w in (('weight=5:1:1', (5, 1, 1)), ('weight=3:2:1', (3, 2, 1)), ('weight=1:1:1', (1, 1, 1))):
    ng = ngx('v18c', srv(w)); real = seq(ng, 14); ng.stop()
    sw = SWRR(dict(zip('ABC', w))); mine = [sw.next() for _ in range(14)]
    rows.append((name, ''.join(real), ''.join(mine), '相同' if real == mine else '不同'))
table(rows, ['nginx 配置', 'nginx 真实的前 14 个选择', '手写 SWRR 的前 14 个', '比对'])
print('  手写的普通轮询(RR)就是 i % n;加权轮询如果简单地把每个节点重复 weight 次再循环,会得到 AAAAABC 这样的序列(同一个节点连续被选很多次),平滑加权轮询把它们错开')
naive = []
for k, n in zip('ABC', (5, 1, 1)): naive += [k] * n
print('  朴素的“重复 weight 次”序列(5:1:1)前 14 个:', ''.join((naive * 2)[:14]))
