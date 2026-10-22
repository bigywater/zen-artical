import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v27'); reset()
print('nginx 的限流:limit_req(漏桶,按请求速率)和 limit_conn(按并发连接数)。限流的 key 是 $binary_remote_addr(这里所有请求都来自 127.0.0.1,所以是同一个 key);超限时返回 429(limit_req_status / limit_conn_status 429)。后端是本进程里的 Python 服务(立刻回复),nginx 1.31.6')
B = Svc(lambda h: h.reply(200, b'ok'))
def conf(zone, loc, up=None):
    return f'limit_req_zone $binary_remote_addr zone=z:1m rate={zone}; limit_conn_zone $binary_remote_addr zone=c:1m; upstream u {{ server 127.0.0.1:{(up or B).port}; }} server {{ listen {{port}}; location / {{ limit_req_status 429; limit_conn_status 429; {loc} proxy_pass http://u; }} }}'

# ============ 一 ============
print('== 一:burst 与 nodelay。limit_req_zone rate=10r/s(每 100 ms 一个)。30 个请求在同一时刻发出(用 barrier 对齐)。四种 limit_req:(a) 没有 burst;(b) burst=5;(c) burst=5 nodelay;(d) burst=10 delay=3。统计放行(200)和拒绝(429)各多少,以及放行的请求各自等了多久(排队被拖慢的时间)')
def burst_test(directive, n=30):
    ng = Nginx('v27a', conf('10r/s', directive)).start(); bar = threading.Barrier(n); res = []; lk = threading.Lock()
    def w():
        bar.wait(); st, _, dt = rpc(ng.port, '/', 10.0, keepalive=False)
        with lk: res.append((st, dt))
    ths = [threading.Thread(target=w) for _ in range(n)]; [t.start() for t in ths]; [t.join() for t in ths]; ng.stop()
    ok = sorted(dt for st, dt in res if st == 200); rej = sum(1 for st, dt in res if st == 429)
    return len(ok), rej, ok
rows = []
for name, d in (('(a) 无 burst', 'limit_req zone=z;'), ('(b) burst=5', 'limit_req zone=z burst=5;'), ('(c) burst=5 nodelay', 'limit_req zone=z burst=5 nodelay;'), ('(d) burst=10 delay=3', 'limit_req zone=z burst=10 delay=3;')):
    ok, rej, lat = burst_test(d)
    rows.append((name, ok, rej, ' '.join(f'{x * 1000:.0f}' for x in lat)))
table(rows, ['配置', '放行', '拒绝(429)', '放行的请求各自的耗时(ms,从小到大)'])
print('  无 burst 时同一时刻只放行 1 个;burst=5 放行 1 + 5 = 6 个,但后面 5 个被排队、每隔 100 ms 放一个(漏桶的“漏”);nodelay 让这 6 个立刻处理,代价是之后要隔够时间才再有额度;delay=3 是折中:前 1 + 3 个立刻,后面的排队延迟,总共 burst=10 个位置')

# ============ 二 ============
print('== 二:持续过载。client 以 20 个/秒的开环速率(不管上一个有没有回来)发 5 秒共 100 个请求,limit_req rate=10r/s。比较 burst 0 / burst 5 / burst 5 nodelay:每秒放行多少(按请求发出的时刻分到第 0 到 4 秒),以及总共放行多少')
def sustained(directive):
    ng = Nginx('v27b', conf('10r/s', directive)).start()
    out = openloop(lambda i: rpc(ng.port, '/', 10.0, keepalive=False), 20, 5.0, workers=200); ng.stop()
    per = [sum(1 for ts, (st, b, dt) in out if st == 200 and int(ts) == s) for s in range(5)]
    return sum(1 for ts, (st, b, dt) in out if st == 200), per
rows = []
for name, d in (('burst 0', 'limit_req zone=z;'), ('burst 5', 'limit_req zone=z burst=5;'), ('burst 5 nodelay', 'limit_req zone=z burst=5 nodelay;')):
    tot, per = sustained(d); rows.append((name, tot, per))
table(rows, ['配置', '100 个请求里放行', '按发出时刻,第 0..4 秒各放行'])
print('  速率上限就是 rate × 时间:5 秒 × 10 个/秒 = 50 个;burst 额外送一次性的额度(burst 5 最多多放 5 个,即 55);burst 0 时放行的比 50 还少一些,我的解释是请求每 50 ms 到一个,而放行要求距离上一个放行的请求至少 100 ms,到达时刻稍有抖动就差一点点被拒绝(这个解释没有单独验证);burst 排队放行的请求要等一会儿才有响应(漏桶每 100 ms 放一个),如果 client 是等响应再发下一个的(闭环),它自己的发送速率会被拖慢到 rate,于是一个都不会被拒绝,这里用开环才看得到拒绝')

# ============ 三 ============
print('== 三:limit_conn。后端要 1 s 才回(同时可以处理很多个);limit_conn zone=c 3(同一个 key 最多 3 个并发连接)。12 个请求同时发出。统计放行与拒绝。再对比 limit_req 与 limit_conn 守的是什么:limit_req 数“单位时间内到达的请求”,limit_conn 数“同时在处理的请求”')
slow = Svc(lambda h: (time.sleep(1.0), h.reply(200, b'slow'))[1], backlog=256)
rows = []
for name, d in (('limit_conn c 3', 'limit_conn c 3;'), ('limit_req rate=10r/s burst=20 nodelay', 'limit_req zone=z burst=20 nodelay;')):
    ng = Nginx('v27c', conf('10r/s', d, up=slow)).start(); bar = threading.Barrier(12); res = []; lk = threading.Lock()
    def w():
        bar.wait(); st, _, dt = rpc(ng.port, '/', 10.0, keepalive=False)
        with lk: res.append(st)
    ths = [threading.Thread(target=w) for _ in range(12)]; [t.start() for t in ths]; [t.join() for t in ths]; ng.stop()
    rows.append((name, collections.Counter(res).get(200, 0), collections.Counter(res).get(429, 0)))
table(rows, ['配置', '放行', '拒绝(429)'])
slow.stop()
