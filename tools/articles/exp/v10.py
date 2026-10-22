import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v10'); reset()
def nerr(): print(f'  (连接类错误 {ERRORS["error"]} 次;不是超时,应为 0)')
print('限流的“维度”= 桶的 key 怎么取。限流器是第 9 篇里的 Go 令牌桶中间件(每个 key 一个桶),这里换不同的 key:全局一个桶 / 每个用户一个桶 / 每个 (用户, 接口) 一个桶。客户端是 Python 开环发请求,走真实的环回 HTTP')

def server(rate, burst, mode):
    port = free_port(); p = subprocess.Popen([str(HERE / 'vtmp/rl/rlsrv'), str(port), str(rate), str(burst), mode], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); wait_port(port, 10); return port, p
def stats(port):
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=3); c.request('GET', '/stats'); d = json.loads(c.getresponse().read()); c.close(); return d
def load(port, plan, dur):
    """plan: [(client, path, rate)];每个流各开一个开环发送线程"""
    res = {}
    def one(flow):
        c, path, rate = flow
        r = openloop(lambda i: rpc(port, path, 3.0, {'X-Client': c})[0], rate, dur, workers=200); res[flow] = collections.Counter(x for _, x in r)
    ths = [threading.Thread(target=one, args=(f,)) for f in plan]; [t.start() for t in ths]; [t.join() for t in ths]; return res

# ============ 一 ============
print('== 一:全局一个桶 vs 每个用户一个桶。限额 100 个/秒、burst 20;4 个用户同时发 5 秒:A 是“吵闹的邻居”,300 个/秒;B、C、D 各 20 个/秒(都远低于限额)。全局桶 = 所有人共用一个桶')
plan = [('A', '/', 300), ('B', '/', 20), ('C', '/', 20), ('D', '/', 20)]
rows = []
for mode, label in (('global', '全局一个桶'), ('user', '每个用户一个桶')):
    port, p = server(100, 20, mode); res = load(port, plan, 5.0); p.terminate(); p.wait(5)
    for (c, path, rate), cnt in res.items():
        tot = sum(cnt.values()); ok = cnt.get(200, 0)
        rows.append((label, c, f'{rate}/s', tot, ok, f'{ok / tot:.0%}'))
table(rows, ['做法', '用户', '发送速率', '请求数', '放行', '放行比例'])
nerr()

# ============ 二 ============
print('== 二:按接口(路由)限流。同一个用户 U 同时请求两个接口:/ping(便宜,100 个/秒)和 /report(贵,100 个/秒);每用户限额 100 个/秒、burst 20 的一个桶 vs 每个 (用户, 接口) 一个桶(/report 的限额 10 个/秒、burst 10,其余 100 个/秒)。5 秒。“/report 占了多少”看放行的两个接口各多少')
plan = [('U', '/ping', 100), ('U', '/report', 100)]
rows = []
for mode, label in (('user', '每个用户一个桶(两个接口共用 100/s)'), ('route', '每个 (用户, 接口) 一个桶,/report 10/s')):
    port, p = server(100, 20, mode); res = load(port, plan, 5.0); p.terminate(); p.wait(5)
    for (c, path, rate), cnt in res.items():
        tot = sum(cnt.values()); ok = cnt.get(200, 0); rows.append((label, path, tot, ok, f'{ok / tot:.0%}'))
table(rows, ['做法', '接口', '请求数', '放行', '放行比例'])
nerr()

# ============ 三 ============
print('== 三:按实例限流 vs 全局限流。用户 U 的目标限额是 100 个/秒;他以 200 个/秒均匀地发请求(10 秒),经过负载均衡到 3 个实例;每个实例有自己的本地令牌桶(burst = 限额)。虚拟时钟模拟。三种做法:每个实例限 100/s(每个实例都以为自己是唯一的一个)、每个实例限 100/3(平均分)、全局共享一个桶(例如放在 Redis)。三种流量分布:轮询(1/3、1/3、1/3)、倾斜(60%、30%、10%)、粘性(100% 到同一个实例)')
class TB:
    def __init__(s, rate, burst): s.rate, s.burst, s.tok, s.last = rate, burst, burst, 0.0
    def allow(s, t):
        s.tok = min(s.burst, s.tok + (t - s.last) * s.rate); s.last = t
        if s.tok >= 1: s.tok -= 1; return True
        return False
def sim(split, policy, rate=200, dur=10, seed=4):
    rng = random.Random(seed)
    if policy == 'each100': bs = [TB(100, 100) for _ in range(3)]
    elif policy == 'third': bs = [TB(100 / 3, 100 / 3) for _ in range(3)]
    else: bs = [TB(100, 100)] * 3
    ok = 0; n = int(rate * dur)
    for i in range(n):
        t = i / rate; r = rng.random(); k = 0
        acc = 0
        for j, w in enumerate(split):
            acc += w
            if r < acc: k = j; break
        ok += bs[k].allow(t) if policy != 'global' else bs[0].allow(t)
    return ok / dur
rows = []
for sname, split in (('轮询 1/3 : 1/3 : 1/3', (1 / 3, 1 / 3, 1 / 3)), ('倾斜 60% : 30% : 10%', (0.6, 0.3, 0.1)), ('粘性 100% : 0 : 0', (1.0, 0.0, 0.0))):
    rows.append((sname,) + tuple(f'{sim(split, p):.0f} 个/秒' for p in ('each100', 'third', 'global')))
table(rows, ['流量分布', '每个实例限 100/s', '每个实例限 100/3', '全局共享一个桶'])
print('  目标是 100 个/秒(令牌桶开头有 burst 个存量,10 秒里多放行 burst 个,所以“正好限住”时显示 110 个/秒)。每个实例各限 100/s:轮询时放行 200 个/秒(请求只有 200/s,3 个桶的额度加起来是 300,等于没限);倾斜时 192;粘性时 110(只有一个实例收到流量,它的桶正好限住)。每个实例限 100/3:轮询时 110;倾斜时 93,低于目标(被打得多的实例先限住,别的实例的额度用不上);粘性时 37。全局共享的桶不受流量分布影响,三行都是 110,代价是每次判断都要多一次对共享存储的访问(见下一篇)')
