import sys, os, asyncio; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path = [p for p in sys.path if os.path.basename(p) != 'exp']          # exp/ 里有 v2.py 等文件,会盖住 nacos SDK 的顶层包 v2
from msl import *
import shutil, subprocess as sp, urllib.parse
tee('v55'); reset()
print('配置变更怎么通知到客户端。Nacos 3.2.4(自己起的单机实例,Java 17)的配置中心用 nacos-sdk-python 3.2.0(gRPC 长连接,服务端推、客户端回来拉);对照一个我自己写的很小的长轮询配置服务和固定间隔的短轮询(都是本进程里的 Python HTTP 服务)。时间都是同一台机器上的 time.time(),发布时刻取调用发出之前')
shutil.rmtree(TT / 'nacos_v55', ignore_errors=True)
N = Nacos('v55', 8850, 8851).start(); time.sleep(4)
CL = TT / 'v55_client.py'
CL.write_text('''import asyncio, sys, time
from v2.nacos import NacosConfigService, ClientConfigBuilder, ConfigParam
srv, data_id, K = sys.argv[1], sys.argv[2], int(sys.argv[3])
async def main():
    svcs = []
    for i in range(K):
        async def cb(tenant, d, g, content, i=i):
            print(f'cb {i} {time.time():.6f} {content}', flush=True)
        cs = await NacosConfigService.create_config_service(ClientConfigBuilder().server_address(srv).build())
        await cs.get_config(ConfigParam(data_id=data_id, group='DEFAULT_GROUP'))
        await cs.add_listener(data_id, 'DEFAULT_GROUP', cb); svcs.append(cs)
    print('ready', flush=True)
    await asyncio.get_running_loop().run_in_executor(None, sys.stdin.readline)
asyncio.run(main())
''')
class NClient:
    def __init__(self, data_id, K=1):
        self.cbs = []; self.lk = threading.Lock()
        self.p = sp.Popen([sys.executable, str(CL), '127.0.0.1:8850', data_id, str(K)], stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.STDOUT, text=True, start_new_session=True)
        self.ready = threading.Event(); threading.Thread(target=self.rd, daemon=True).start()
        assert self.ready.wait(120), 'client not ready'
        self.t_ready = time.time(); self.K = K; self.data_id = data_id
    def rd(self):
        for line in self.p.stdout:
            if line.strip() == 'ready': self.ready.set()
            elif line.startswith('cb '):
                _, i, t, c = line.rstrip('\n').split(' ', 3)
                with self.lk: self.cbs.append((int(i), float(t), c))
    def got(self, content): 
        with self.lk: return [(i, t) for i, t, c in self.cbs if c == content]
    def warm(self, timeout=60.0):
        """add_listener 返回之后服务端不一定马上开始推送(实测前几次发布没有回调):反复发布 warm 内容,直到每个监听者都收到过一次回调;返回距离 ready 的秒数"""
        n = 0
        while time.time() - self.t_ready < timeout:
            publish(self.data_id, f'warm{n}'); n += 1; time.sleep(0.25)
            with self.lk: got = {i for i, t, c in self.cbs if c.startswith('warm')}
            if len(got) >= self.K: break
        else: return None
        time.sleep(1.0); return time.time() - self.t_ready
    def kill(self):
        try: os.killpg(self.p.pid, signal.SIGKILL)
        except Exception: pass
def publish(data_id, content):
    t = time.time(); s, d = N.http('POST', '/nacos/v3/admin/cs/config', body={'dataId': data_id, 'groupName': 'DEFAULT_GROUP', 'content': content, 'type': 'text'}, timeout=10.0); t2 = time.time()
    assert s == 200, (s, d); return t, t2
def stats(xs, unit=1000):
    xs = sorted(xs); return f'{xs[0] * unit:.1f} / {statistics.median(xs) * unit:.1f} / {xs[int(len(xs) * 0.99) - 1 if len(xs) > 100 else -1] * unit:.1f}'

# ============ 一 ============
print('== 一:Nacos 的推送延迟。先发布 init,再起一个监听这个配置的 SDK 客户端子进程;之后每 0.4 s 发布一个新内容(共 30 次),记录从发布调用发出到客户端回调被调用的时间。再分别用 1 个监听者和 30 个监听者(同一个子进程里 30 个 SDK 客户端,各一条连接)各测一轮')
rows = []; warm = []
for K in (1, 30):
    did = f'push{K}'; publish(did, 'init'); c = NClient(did, K); tw = c.warm(); warm.append((K, tw))
    n = 30 if K == 1 else 10; pubs = []
    for i in range(n):
        t, t2 = publish(did, f'c{i}'); pubs.append((f'c{i}', t, t2)); time.sleep(0.4 if K == 1 else 1.0)
    time.sleep(2.0)
    lat = []; miss = 0
    for name, t, t2 in pubs:
        g = c.got(name)
        if len(g) < K: miss += K - len(g)
        lat += [tt - t for _, tt in g]
    spread = []
    for name, t, t2 in pubs:
        g = [tt for _, tt in c.got(name)]
        if len(g) == K: spread.append(max(g) - min(g))
    rows.append((K, n, f'{len(lat)}/{n * K}', stats(lat), f'{statistics.median(spread) * 1000:.1f}' if spread else '-'))
    c.kill()
table(rows, ['监听者数', '发布次数', '收到回调数/应收', '延迟 最小 / 中位 / 最大(ms)', '同一次发布各监听者收到时间的跨度,中位(ms)'])
print('  add_listener 返回(子进程打印 ready)之后,到每个监听者都收到过第一次推送的时间:' + ';'.join(f'{k} 个监听者 {t:.1f} s' if t else f'{k} 个监听者 60 s 内没有' for k, t in warm) + '(这段时间里的发布没有回调,所以上表只统计生效之后的发布)')
print('  发布调用(POST)自己也要花时间;这里的延迟从调用发出之前算起,所以包含服务端处理发布的时间')

# ============ 二 ============
print('== 二:推送、长轮询、短轮询的对比。同一组变更(10 次,时刻用固定种子随机),同时发布到 Nacos(SDK 监听)和我写的小配置服务;小配置服务上有三种客户端:短轮询 1 s、短轮询 5 s、长轮询(服务端挂起最多 10 s,有变化立刻返回)。记录每次变更各客户端看到的延迟,以及 50 s 里客户端发出的 HTTP 请求数(只统计小配置服务这三种;Nacos 的 gRPC 长连接上的保活帧没有统计)')
state = {'v': 0, 'val': 'init'}; cond = threading.Condition(); reqs = collections.Counter()
def app(h):
    u = urllib.parse.urlparse(h.path); q = urllib.parse.parse_qs(u.query); who = h.headers.get('X-Client', '?')
    if u.path == '/pub':
        with cond: state['v'] += 1; state['val'] = q['val'][0]; cond.notify_all()
        h.reply(200, b'ok'); return
    reqs[who] += 1
    if u.path == '/wait':
        since = int(q['v'][0]); to = float(q['t'][0])
        with cond: cond.wait_for(lambda: state['v'] > since, timeout=to); v, val = state['v'], state['val']
        h.reply(200, json.dumps({'v': v, 'val': val}).encode()); return
    with cond: v, val = state['v'], state['val']
    h.reply(200, json.dumps({'v': v, 'val': val}).encode())
CS = Svc(app, 'cfg'); seen = {k: {} for k in ('short1', 'short5', 'long10')}; stop = threading.Event()
def short(name, interval):
    last = 0
    while not stop.is_set():
        s, d, dt = rpc(CS.port, '/get', 5.0, {'X-Client': name})
        if s == 200:
            j = json.loads(d)
            if j['v'] > last: last = j['v']; seen[name][j['val']] = time.time()
        stop.wait(interval)
def long_(name, to):
    last = 0
    while not stop.is_set():
        s, d, dt = rpc(CS.port, f'/wait?v={last}&t={to}', to + 5, {'X-Client': name})
        if s == 200:
            j = json.loads(d)
            if j['v'] > last: last = j['v']; seen[name][j['val']] = time.time()
        else: stop.wait(0.5)
ths = [threading.Thread(target=short, args=('short1', 1.0), daemon=True), threading.Thread(target=short, args=('short5', 5.0), daemon=True), threading.Thread(target=long_, args=('long10', 10), daemon=True)]
publish('cmp', 'init'); NC = NClient('cmp', 1); NC.warm()
for t in ths: t.start()
time.sleep(1.5); rng = random.Random(11); at = sorted(rng.uniform(2, 45) for _ in range(10)); T0 = time.time(); pubt = {}
for i, a in enumerate(at):
    time.sleep(max(0, T0 + a - time.time()))
    t_n, _ = publish('cmp', f'm{i}'); t_l = time.time(); rpc(CS.port, f'/pub?val=m{i}', 5.0); pubt[f'm{i}'] = (t_n, t_l)
time.sleep(max(0, T0 + 50 - time.time())); stop.set(); time.sleep(0.5)
def lat_of(name): return [seen[name][k] - pubt[k][1] for k in pubt if k in seen[name]]
rows = []
nl = [NC.got(k)[0][1] - pubt[k][0] for k in pubt if NC.got(k)]
rows.append(('Nacos 推送(SDK 监听)', f'{len(nl)}/10', stats(nl), '(gRPC 长连接,没有统计)'))
for name, label in (('short1', '短轮询 1 s'), ('short5', '短轮询 5 s'), ('long10', '长轮询(最多挂起 10 s)')):
    l = lat_of(name); rows.append((label, f'{len(l)}/10', stats(l) if l else '-', reqs[name]))
table(rows, ['方式', '收到变更数', '延迟 最小 / 中位 / 最大(ms)', '50 s 里发出的 HTTP 请求数'])
NC.kill()
order = sorted(pubt, key=lambda k: int(k[1:]))
for name, interval in (('short1', 1.0), ('short5', 5.0)):
    missed = [k for k in order if k not in seen[name]]
    gaps = [(k, (pubt[order[order.index(k) + 1]][1] - pubt[k][1]) if order.index(k) + 1 < len(order) else None) for k in missed]
    print(f'  {name}(间隔 {interval:g} s)没有看到的变更:' + (', '.join(f'{k}(与下一次变更相隔 {g:.2f} s)' if g is not None else f'{k}(最后一次变更)' for k, g in gaps) if gaps else '无'))
print('  轮询看到的是“轮询那一刻的最新值”,所以没看到的变更对应上面与下一次变更的间隔;短轮询的请求数只取决于间隔,与变更多少无关;长轮询在没有变化时每个超时周期发一次请求,有变化时立即返回')

# ============ 三 ============
print('== 三:客户端暂时联系不上时变更会不会丢。SDK 客户端子进程监听配置 frz;(a)SIGSTOP 冻住它 5 s,期间发布 3 次(间隔 0.5 s),然后 SIGCONT;(b)冻住 45 s(比服务端发现死连接的时间长),期间发布 3 次,然后 SIGCONT;(c)Nacos 被 SIGKILL 后重启,服务起来之后马上发布一次。记录客户端恢复之后收到的回调个数、最后一个回调的内容、距离恢复(SIGCONT 或服务可用)的时间')
rows = []
for label, frozen in (('(a)冻住 5 s', 5), ('(b)冻住 45 s', 45)):
    did = f'frz{frozen}'; publish(did, 'init'); c = NClient(did, 1); c.warm()
    os.kill(c.p.pid, signal.SIGSTOP); time.sleep(0.5)
    for i in range(3): publish(did, f'f{i}'); time.sleep(0.5)
    time.sleep(max(0, frozen - 2.0)); n0 = len(c.cbs); tc = time.time(); os.kill(c.p.pid, signal.SIGCONT)
    t_end = time.time() + 40
    while time.time() < t_end and not any(x[2] == 'f2' for x in c.cbs[n0:]): time.sleep(0.1)
    time.sleep(1.5); new = c.cbs[n0:]; during = c.cbs[:n0]
    rows.append((label, len(new), new[-1][2] if new else '-', f'{new[-1][1] - tc:.2f} s' if new else '-', ' '.join(f'{x[2]}@{x[1] - tc:.2f}' for x in new)))
    c.kill()
publish('rst', 'init'); c = NClient('rst', 1); c.warm(); n0 = len(c.cbs)
N.kill(); time.sleep(1.0); N.start(wait=False)
ok = poll_ok = None
t0 = time.time()
while time.time() - t0 < 120:
    try:
        s, d = N.http('GET', '/nacos/v3/admin/cs/config', {'dataId': 'rst', 'groupName': 'DEFAULT_GROUP'}, timeout=1.0)
        if s == 200: break
    except Exception: pass
    time.sleep(0.2)
t_up = time.time(); publish('rst', 'after-restart')
while time.time() < t_up + 120 and not any(x[2] == 'after-restart' for x in c.cbs[n0:]): time.sleep(0.1)
new = c.cbs[n0:]; rows.append(('(c)Nacos 重启', len(new), new[-1][2] if new else '-', f'{new[-1][1] - t_up:.2f} s' if new else '120 s 内没有', ' '.join(f'{x[2]}@{x[1] - t_up:.2f}' for x in new)))
c.kill()
table(rows, ['情形', '恢复后收到的回调数', '最后一个回调的内容', '最后一个回调距恢复', '恢复后的全部回调(内容@距恢复秒数)'])
N.stop(); CS.stop()
print('ERRORS', dict(ERRORS))
