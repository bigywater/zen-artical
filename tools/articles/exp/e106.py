import sys, threading, time, json, os, random, collections, queue, subprocess, textwrap, tempfile

print("Python", sys.version.split()[0], "| GIL 开启:", sys._is_gil_enabled(), "| switch interval =", sys.getswitchinterval())

print("\n== 一、同一段有竞态的代码: 自然运行 vs 强制线程切换 ==")
class Account:
    def __init__(self): self.balance = 0
    def deposit_racy(self, n):
        cur = self.balance          # 读
        time.sleep(0)               # 让出一次 GIL: 制造线程切换的机会(测试里常用「拧一下」的办法)
        self.balance = cur + n      # 写
def trial(threads=4, per=200):
    a = Account(); ths = [threading.Thread(target=lambda: [a.deposit_racy(1) for _ in range(per)]) for _ in range(threads)]
    [t.start() for t in ths]; [t.join() for t in ths]; return a.balance, threads * per
res = [trial() for _ in range(10)]
print("  在读和写之间加一个线程让出点(time.sleep(0)); 4 个线程各存 200 次 1 元, 期望 800; 连续 10 次结果:", [r[0] for r in res])
print("  10 次里恰好等于 800 的次数:", sum(1 for r in res if r[0] == r[1]))
def trial_nosleep(threads=4, per=200):
    a = Account(); a.deposit_racy = lambda n: setattr(a, 'balance', a.balance + n)
    ths = [threading.Thread(target=lambda: [a.deposit_racy(1) for _ in range(per)]) for _ in range(threads)]
    [t.start() for t in ths]; [t.join() for t in ths]; return a.balance
print("  去掉让出点、自然运行(同样的「先读后写」逻辑), 10 次结果:", [trial_nosleep() for _ in range(10)], "← 每次都是 800: 测试全绿, 但竞态并没有消失")

print("\n== 二、放大竞态: 缩小切换间隔 + 重复跑 ==")
def natural(n, iters=300, threads=4):
    bad = 0
    for _ in range(iters):
        box = [0]
        def w():
            for _ in range(n): box[0] += 1
        ths = [threading.Thread(target=w) for _ in range(threads)]
        [t.start() for t in ths]; [t.join() for t in ths]
        if box[0] != threads * n: bad += 1
    return bad
default_iv = sys.getswitchinterval()
r1 = natural(50); sys.setswitchinterval(1e-6); r2 = natural(50); sys.setswitchinterval(default_iv)
print(f"  {default_iv*1000:.1f} ms(默认切换间隔): 300 次里出错 {r1} 次 | 切换间隔调到 0.001 ms: 300 次里出错 {r2} 次")
print("  (这份 box[0] += 1 在 GIL 版 3.14 上很难自然出错; 结果取决于解释器版本和机器, 想要稳定复现需要用别的手段)")

print("\n== 三、用同步原语「排演」一次特定的交错 ==")
def interleave():
    a = Account(); e1, e2 = threading.Event(), threading.Event(); log = []
    def deposit(name, wait_evt, set_evt):
        cur = a.balance; log.append(f"{name} 读到 {cur}")
        if set_evt: set_evt.set()
        if wait_evt: wait_evt.wait()
        a.balance = cur + 1; log.append(f"{name} 写入 {cur + 1}")
    t1 = threading.Thread(target=deposit, args=("线程A", e2, e1)); t2 = threading.Thread(target=deposit, args=("线程B", None, e2))
    t1.start(); e1.wait(); t2.start(); t1.join(); t2.join(); return a.balance, log
bal, log = interleave()
print("  用两个 Event 强制「A 读 → B 读 → B 写 → A 写」的顺序:")
for l in log: print("    ", l)
print(f"  两次存款后余额 = {bal} (期望 2) ← 每次都稳定复现丢失更新, 不靠运气")
def interleave_fixed():
    a = Account(); lock = threading.Lock()
    def deposit():
        with lock:
            cur = a.balance; a.balance = cur + 1
    ths = [threading.Thread(target=deposit) for _ in range(2)]; [t.start() for t in ths]; [t.join() for t in ths]; return a.balance
print("  加锁之后同样两次存款:", interleave_fixed(), "(期望 2)")

print("\n== 四、超时才是并发测试的安全网 ==")
def hang_test():
    q = queue.Queue(); res = {}
    def consumer():
        res['v'] = q.get()            # 生产者永远不来: 永久阻塞
    t = threading.Thread(target=consumer, daemon=True); t.start()
    t.join(timeout=0.5); return t.is_alive()
t0 = time.perf_counter(); alive = hang_test(); dt = time.perf_counter() - t0
print(f"  消费者线程等一个永远不会到的消息: join(timeout=0.5) 在 {dt:.2f} s 后返回, 线程仍存活 = {alive} → 测试可以据此明确失败, 而不是把 CI 卡死")
code = "import queue; q = queue.Queue(); q.get()"
t0 = time.perf_counter()
try: subprocess.run([sys.executable, '-c', code], timeout=1.0)
except subprocess.TimeoutExpired: print(f"  没有超时保护的死等, 由外部 timeout 在 {time.perf_counter() - t0:.2f} s 杀掉(subprocess.run(timeout=1.0))")

print("\n== 五、断言「最终一致」: 用轮询等待代替 sleep ==")
def eventually(cond, timeout=2.0, step=0.001):
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < timeout:
        if cond(): return time.perf_counter() - t0
        time.sleep(step)
    raise AssertionError("超时")
done = []
def worker(delay): time.sleep(delay); done.append(1)
rows = []
for delay in (0.02, 0.05, 0.1):
    done.clear(); threading.Thread(target=worker, args=(delay,)).start()
    waited = eventually(lambda: done)
    rows.append((delay, waited)); print(f"  后台任务实际需要 {delay*1000:.0f} ms: 轮询版测试等了 {waited*1000:.1f} ms 就通过; 「固定 sleep(0.2)」的测试要等 200 ms")
json.dump({'trials': [r[0] for r in res], 'rows': rows, 'log': log, 'bal': bal}, open(os.path.join(os.environ['HERE'], 'out/106.json'), 'w'), ensure_ascii=False)
