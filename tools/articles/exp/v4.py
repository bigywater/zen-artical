import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v4'); reset()
def nerr(): print(f'  (连接类错误 {ERRORS["error"]} 次;不是超时,应为 0)')
print('重试预算:一个共享的令牌桶——每发出一个原始请求存入 ratio 个令牌(桶上限 10 个,开始时为空),每次重试要取走 1 个令牌,取不到就不重试、直接把失败返回。ratio = 10% 的意思是长期来看重试最多占原始请求的 10%。“不限”是每个请求失败后最多再试 2 次(共 3 次),不看预算')

class Budget:
    def __init__(self, ratio, cap=10.0): self.r, self.cap, self.t, self.lk = ratio, cap, 0.0, threading.Lock()
    def deposit(self):
        with self.lk: self.t = min(self.cap, self.t + self.r)
    def withdraw(self):
        with self.lk:
            if self.t >= 1.0: self.t -= 1.0; return True
            return False

def call(port, budget, unlimited=False, attempts=3):
    """一个原始请求;返回 (状态码, 实际发出的次数)"""
    if budget: budget.deposit()
    n = 0
    while True:
        n += 1; st, _, _ = rpc(port, '/', 3.0)
        if st == 200 or n >= attempts: return st, n
        if not unlimited and not (budget and budget.withdraw()): return st, n

# ============ 一 ============
print('== 一:预算 × 失败率。服务对每次调用独立地以概率 p 返回 503;client 8 个并发线程、共 1500 个原始请求。“放大”= 服务收到的调用 ÷ 原始请求数;“成功”= 原始请求最终拿到 200 的比例')
rows = []
for p in (0.05, 0.2, 0.5, 1.0):
    for name, ratio, unl in (('不重试', None, False), ('预算 10%', 0.1, False), ('预算 20%', 0.2, False), ('预算 50%', 0.5, False), ('不限(共 3 次)', None, True)):
        rng = random.Random(4); lk = threading.Lock(); hits = [0]
        def app(h):
            with lk: hits[0] += 1; bad = rng.random() < p
            h.reply(503 if bad else 200, b'x')
        S = Svc(app); bud = Budget(ratio) if ratio else None
        if name == '不重试': attempts = 1
        else: attempts = 3
        res = par(lambda i: call(S.port, bud, unl, attempts), list(range(1500)), 8); S.stop()
        ok = sum(1 for st, n in res if st == 200)
        rows.append((f'{p:.0%}', name, f'{ok / 1500:.1%}', f'{hits[0] / 1500:.3f}', hits[0]))
table(rows, ['服务失败率 p', '重试策略', '成功', '放大(服务收到 ÷ 原始请求)', '服务收到的调用'])
nerr()

# ============ 二 ============
print('== 二:容量有限的服务 + 一段变慢。服务同时最多处理 4 个请求、每个 20 ms(容量 200/s),忙时立刻回 503;client 以 120/s 发 8 秒;第 2 到 3.5 秒处理时间变成 3 倍。比较:不重试、不限(共 3 次)、预算 10%。每秒服务收到的调用数 / client 成功率')
state = {'slow': 1.0}; sem = threading.Semaphore(4); arr = collections.Counter(); T0 = [0.0]
def c_cap(h):
    arr[int(time.time() - T0[0])] += 1
    if not sem.acquire(blocking=False): return h.reply(503, b'busy')
    try: time.sleep(0.02 * state['slow'])
    finally: sem.release()
    h.reply(200, b'ok')
def run2(mode):
    C = Svc(c_cap); bud = Budget(0.1) if mode == 'budget' else None
    arr.clear(); state['slow'] = 1.0; T0[0] = time.time()
    def trig():
        time.sleep(2.0); state['slow'] = 3.0; time.sleep(1.5); state['slow'] = 1.0
    threading.Thread(target=trig, daemon=True).start()
    att = 1 if mode == 'none' else 3
    res = openloop(lambda i: call(C.port, bud, mode == 'unlimited', att)[0], 120, 8, workers=500)
    ok = collections.Counter(); tot = collections.Counter()
    for ts, st in res: tot[int(ts)] += 1; ok[int(ts)] += (st == 200)
    C.stop(); return [arr[s] for s in range(8)], [ok[s] / max(tot[s], 1) for s in range(8)]
rows = []
for name, mode in (('不重试', 'none'), ('不限(共 3 次)', 'unlimited'), ('预算 10%', 'budget')):
    a, o = run2(mode); rows.append((name, '收到的调用/s') + tuple(a)); rows.append(('', 'client 成功率') + tuple(f'{x:.0%}' for x in o))
table(rows, ['', '', '第 0 秒', '1', '2', '3', '4', '5', '6', '7'])
nerr()

# ============ 三 ============
print('== 三:多层叠加。client → A → B → C 三层,每一层都用自己的重试策略对下一层重试;C 一直 503(完全不可用),发 200 个请求。看 C 平均每个原始请求收到几次调用')
def layer(down, mode):
    bud = Budget(0.1) if mode == 'budget' else None
    def app(h):
        st, n = call(down, bud, mode == 'unlimited', 3)
        h.reply(200 if st == 200 else 503, b'x')
    return Svc(app)
rows = []
for name, mode in (('每层不限(共 3 次)', 'unlimited'), ('每层预算 10%', 'budget')):
    hits = [0]
    def c_dead(h): hits[0] += 1; h.reply(503, b'x')
    C = Svc(c_dead); top = C; ss = [C]
    for _ in range(3): top = layer(top.port, mode); ss.append(top)
    par(lambda i: rpc(top.port, '/', 30.0)[0], list(range(200)), 4)
    rows.append((name, hits[0], f'{hits[0] / 200:.2f}')); [s.stop() for s in ss]
table(rows, ['策略', 'C 收到的调用', '每个原始请求'])
print('  每层预算 10% 时,放大的上界是每层 1.1 倍,三层是 1.1³ = 1.33;实测值在这附近(桶开始时是空的,所以略低于上界)')
nerr()
