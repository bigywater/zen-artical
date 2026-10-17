import sys, os, time, json, re, threading, subprocess, signal, socket, random, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from kazoo.recipe.watchers import ChildrenWatch
tee('z88'); R = {}
n = Node('z88', 7300, xmx=256, conf={'tickTime': 1000, 'maxClientCnxns': 500}).start(); adm = client('127.0.0.1:7300'); adm.ensure_path('/svc/orders')
P = str(HERE / 'procs' / 'prov.py'); procs = {}
def start(port, mode='naive'): procs[port] = subprocess.Popen([sys.executable, P, '7300', str(port), mode])
class Consumer:
    def __init__(self, zk='127.0.0.1:7300'):
        self.c = client(zk); self.addrs = []; self.log = []; self.seen = {}
        ChildrenWatch(self.c, '/svc/orders', self._cb)
    def _cb(self, kids):
        now = time.perf_counter()
        for k in kids:
            if k not in self.seen: self.seen[k] = now
        self.addrs = list(kids); self.log.append((now, list(kids)))
def call(addr, to=0.2):
    h, p = addr.split(':')
    try:
        s = socket.create_connection((h, int(p)), timeout=to); s.sendall(b'x'); r = s.recv(10); s.close(); return r == b'ok'
    except Exception: return False
print('== 一:起 5 个服务提供者(各自注册 /svc/orders/<host:port>,临时节点),消费者订阅')
for p in range(7701, 7706): start(p)
cons = Consumer(); t0 = time.time()
while len(cons.addrs) < 5 and time.time() - t0 < 15: time.sleep(0.05)
print('  消费者看到的列表:', sorted(cons.addrs)); print('  /svc/orders/127.0.0.1:7701 的数据:', adm.get('/svc/orders/127.0.0.1:7701')[0].decode(), '(临时节点,ephemeralOwner ≠ 0:', adm.get('/svc/orders/127.0.0.1:7701')[1].ephemeralOwner != 0, ')')
print()
print('== 二:上线:新提供者启动后,多久出现在消费者的列表里')
tj = time.perf_counter(); start(7706)
while '127.0.0.1:7706' not in cons.addrs and time.perf_counter() - tj < 15: time.sleep(0.01)
print(f'  从启动进程(含 Python 启动、连 ZooKeeper、建节点)到消费者看到它:{(time.perf_counter()-tj)*1000:.0f} ms'); R['join_ms'] = (time.perf_counter() - tj) * 1000
print()
print('== 三:下线:消费者持续请求(每 20 ms 一次,随机选一个当前列表里的实例),分别正常关闭和 kill -9 一个提供者,统计失败请求')
def traffic(seconds, kill, how):
    stats = dict(ok=0, fail=0, retried_ok=0); stop = threading.Event(); gone = {}
    def run():
        while not stop.is_set():
            a = random.choice(cons.addrs) if cons.addrs else None
            if a is None: time.sleep(0.02); continue
            if call(a): stats['ok'] += 1
            else:
                stats['fail'] += 1
                others = [x for x in cons.addrs if x != a]
                if others and call(random.choice(others)): stats['retried_ok'] += 1
            time.sleep(0.02)
    th = threading.Thread(target=run); th.start(); time.sleep(1.0); victim = 7701; ta = time.perf_counter()
    if how == 'kill': procs[victim].kill()
    else: procs[victim].send_signal(signal.SIGTERM)
    while f'127.0.0.1:{victim}' in cons.addrs and time.perf_counter() - ta < 15: time.sleep(0.01)
    gone = (time.perf_counter() - ta) * 1000; time.sleep(1.0); stop.set(); th.join(); return stats, gone
sk, gk = traffic(5, True, 'kill')
print(f'  kill -9:消费者的列表在 {gk:.0f} ms 后才去掉它;期间失败 {sk["fail"]} 次、成功 {sk["ok"]} 次;失败后立刻换一个实例重试成功 {sk["retried_ok"]} 次')
R['kill'] = dict(ms=gk, **sk)
start(7701); time.sleep(1.5)
st_, gt = traffic(5, False, 'term')
print(f'  SIGTERM(进程被终止、连接断开但没有主动注销):消费者的列表 {gt:.0f} ms 后去掉它;失败 {st_["fail"]} 次(进程被终止时没有注销节点:连接断了,但会话要等到超时才过期,节点才消失)')
R['term'] = dict(ms=gt, **st_)
print()
print('== 四:提供者主动注销(delete 自己的节点)后再退出:消费者多久感知')
start(7701); time.sleep(1.5)
ta = time.perf_counter(); adm.delete('/svc/orders/127.0.0.1:7701')
while '127.0.0.1:7701' in cons.addrs and time.perf_counter() - ta < 15: time.sleep(0.005)
print(f'  主动 delete 节点后消费者 {(time.perf_counter()-ta)*1000:.0f} ms 内去掉它(进程仍在运行但已不再被调用,可以先摘流量、再关进程)'); R['graceful_ms'] = (time.perf_counter() - ta) * 1000
print()
print('== 五:提供者进程活着但被冻结超过会话超时(SIGSTOP 5 s,会话超时 3 s):三种提供者 —— 只注册一次 / 重连后在监听器里直接 create / 重连后在新线程里 create')
procs[7701].kill(); time.sleep(4)
MODES = {7711: 'naive', 7712: 'rereg_sync', 7713: 'rereg_thread'}
for p, m in MODES.items(): start(p, m)
time.sleep(2); print('  起始列表里有 7711、7712、7713:', all(f'127.0.0.1:{p}' in cons.addrs for p in MODES))
for p in MODES: procs[p].send_signal(signal.SIGSTOP)
time.sleep(5); print('  冻结 5 秒后列表里的这三个:', sorted(a.split(':')[1] for a in cons.addrs if a.split(':')[1] in map(str, MODES)), '(都因会话过期被摘除)')
for p in MODES: procs[p].send_signal(signal.SIGCONT)
time.sleep(6); alive = {p: procs[p].poll() is None for p in MODES}
back = {MODES[p]: any(a.endswith(str(p)) for a in cons.addrs) for p in MODES}
print('  解冻 6 秒后三个进程都还活着:', all(alive.values()), '| 重新出现在列表里的:', back)
R['stop'] = back
for p in procs.values():
    try: p.kill()
    except Exception: pass
cons.c.stop(); adm.stop(); n.stop(); save('z88', R); os._exit(0)
