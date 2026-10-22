import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import traceback, hashlib, re, asyncio, concurrent.futures
tee('v79'); reset()
print('错误追踪:异常堆栈与采样。Python 3.14 的 traceback 模块(纯进程内的实验):(一)堆栈的大小和格式化的耗时随调用深度怎么增长;(二)怎么给异常分组(指纹),不同策略得到几个组;(三)同一个 bug 瞬间爆发时,全量捕获与限流采样的开销;(四)线程池、asyncio 里没被处理的异常会不会丢')
def recurse(d, kind='ValueError'):
    if d == 0: raise ValueError(f'bad value in order {random.randrange(10**6)}')
    return recurse(d - 1) + 1

# ============ 一 ============
print('== 一:堆栈的大小与格式化耗时。在调用深度 d 处抛出 ValueError,用 traceback.format_exc() 取完整堆栈文本。两种调用方式:(a)自己调自己的递归(每一帧都是同一个函数、同一行);(b)两个函数 ping / pong 交替递归(相邻两帧不同,Python 的 traceback 不会把它们当作重复)。再试 limit=-20(只保留最内层 20 帧)和 “raise … from …” 的两层异常链(用 (b) 的深度)。每种取 200 次的中位数')
def ping(d):
    if d == 0: raise ValueError(f'bad value in order {random.randrange(10**6)}')
    return pong(d - 1) + 1
def pong(d):
    return ping(d - 1) + 1
rows = []
for d in (4, 20, 100, 500):
    ts_a = []; ln_a = 0; ts_b = []; ln_b = 0; ln20 = 0; lnc = 0
    for _ in range(200):
        try: recurse(d)
        except ValueError:
            t = time.perf_counter(); s_ = traceback.format_exc(); ts_a.append((time.perf_counter() - t) * 1e6); ln_a = len(s_)
        try: ping(d)
        except ValueError:
            t = time.perf_counter(); s_ = traceback.format_exc(); ts_b.append((time.perf_counter() - t) * 1e6); ln_b = len(s_); ln20 = len(traceback.format_exc(limit=-20))
    try:
        try: ping(d)
        except ValueError as e: raise RuntimeError('wrapped') from e
    except RuntimeError: lnc = len(traceback.format_exc())
    rows.append((d, ln_a, f'{statistics.median(ts_a):.0f}', ln_b, f'{statistics.median(ts_b):.0f}', ln20, lnc))
table(rows, ['调用深度', '(a)自递归:堆栈文本字节数', '(a)format_exc 耗时(µs)', '(b)ping/pong:堆栈文本字节数', '(b)format_exc 耗时(µs)', '(b)limit=-20 的字节数', '(b)带异常链(from)的字节数'])
print('  交替调用的堆栈文本随深度线性变长,格式化的耗时也线性增长;自己调自己的递归在文本里被折叠成 “Previous line repeated N more times”(字节数几乎不变),但格式化的耗时仍然随深度增长;limit 能限制放进报告的帧数;异常链会把两层异常的堆栈都带上')

# ============ 二 ============
print('== 二:给异常分组。1 万个异常来自 5 个不同的 bug(B1~B5),每个异常的消息里都带随机的订单号、UUID 或路径;其中 B2 从两条不同的调用路径(A→x→f 和 B→x→f)都会抛出。比较五种指纹:(a)原始消息文本;(b)只用异常类型;(c)规整后的消息(数字、UUID、路径换成占位符);(d)异常类型 + 最内层 2 帧的函数名(不含行号、不含外层调用者);(e)异常类型 + 全部帧的函数名。看得到几个组,以及是否正确地分成 5 个')
def f_b1(): raise KeyError(f'order-{random.randrange(10**8)} missing in cache')
def f_b2(): raise ValueError(f'invalid amount {random.random():.6f} for user {random.randrange(10**5)}')
def f_b3(): raise ValueError(f'cannot parse /var/data/{random.randrange(10**6)}/part-{random.randrange(100)}.csv')
def f_b4(): raise TimeoutError(f'upstream timeout after {random.choice([1000, 2000, 3000])} ms (req {uuid_hex()})')
def f_b5(): raise ValueError(f'invalid amount {random.random():.6f} for user {random.randrange(10**5)}')    # 与 B2 消息格式相同但是另一个函数里的另一个 bug
def uuid_hex(): return '%032x' % random.getrandbits(128)
def x_mid(fn): fn()
def path_a(fn): x_mid(fn)
def path_b(fn): x_mid(fn)
bugs = [('B1', f_b1, [path_a]), ('B2', f_b2, [path_a, path_b]), ('B3', f_b3, [path_a]), ('B4', f_b4, [path_b]), ('B5', f_b5, [path_a])]
errs = []
for i in range(10000):
    name, fn, paths = random.choice(bugs)
    try: random.choice(paths)(fn)
    except Exception as e: errs.append((name, e))
def fp_raw(e): return hashlib.md5(f'{type(e).__name__}:{e}'.encode()).hexdigest()
def fp_type(e): return type(e).__name__
def norm_msg(m): return re.sub(r'\d+(\.\d+)?', 'N', re.sub(r'[0-9a-f]{32}', 'UUID', re.sub(r'/[\w/.\-]+', 'PATH', m)))
def fp_norm(e): return type(e).__name__ + ':' + norm_msg(str(e))
def fp_stack(e):
    fr = traceback.extract_tb(e.__traceback__)[-2:]; return type(e).__name__ + ':' + '>'.join(f.name for f in fr)
def fp_stack_all(e):
    fr = traceback.extract_tb(e.__traceback__); return type(e).__name__ + ':' + '>'.join(f.name for f in fr)
rows = []
for name, fp in (('(a)原始消息', fp_raw), ('(b)只用异常类型', fp_type), ('(c)规整后的消息', fp_norm), ('(d)类型 + 最内层 2 帧', fp_stack), ('(e)类型 + 全部帧的函数名', fp_stack_all)):
    g = collections.defaultdict(set)
    for bug, e in errs: g[fp(e)].add(bug)
    mixed = sum(1 for bugs_ in g.values() if len(bugs_) > 1); split = collections.Counter()
    for k, bugs_ in g.items():
        for b in bugs_: split[b] += 1
    rows.append((name, len(g), mixed, ', '.join(f'{b}→{split[b]}' for b in sorted(split))))
table(rows, ['指纹策略', '得到的组数', '混了不同 bug 的组数', '每个 bug 被分成几个组'])
print('  用原始消息分组,每个异常几乎都是一个独立的组(消息里带着变量);只用类型会把不同的 bug 混在一起(B2、B3、B5 都是 ValueError);规整消息之后 B2 和 B5(消息格式一样)被混在一起;按最内层几帧的函数名分组能正确区分 5 个 bug,并把 B2 的两条调用路径合并;用全部帧则把 B2 拆成两组')

# ============ 三 ============
print('== 三:同一个 bug 瞬间爆发。2 万次同样的异常(同一个指纹)在一个紧凑的循环里抛出。三种处理:(a)每次都完整捕获(格式化堆栈 + JSON 序列化放进列表);(b)按指纹限流:每秒最多完整捕获 10 次,其余只给计数器加一;(c)前 5 次完整捕获,之后每 100 次捕获 1 次。比较:耗费的 CPU 时间、保留下来的字节数、能还原出的总次数')
def capture(e): return json.dumps({'type': type(e).__name__, 'msg': str(e), 'stack': traceback.format_exception(e)})
def storm(mode, n=20000):
    kept = []; cnt = 0; tokens = 10.0; last = time.perf_counter(); c0 = time.process_time(); t0 = time.perf_counter(); skipped = 0
    for i in range(n):
        try: recurse(30)
        except ValueError as e:
            cnt += 1
            if mode == 'all': kept.append(capture(e))
            elif mode == 'bucket':
                now = time.perf_counter(); tokens = min(10.0, tokens + (now - last) * 10); last = now
                if tokens >= 1: tokens -= 1; kept.append(capture(e))
                else: skipped += 1
            else:
                if cnt <= 5 or cnt % 100 == 0: kept.append(capture(e))
                else: skipped += 1
    cpu = time.process_time() - c0; wall = time.perf_counter() - t0
    if mode == 'all': est = len(kept)
    elif mode == 'bucket': est = cnt             # 计数器给出准确总数
    else: est = 5 + (cnt // 100) * 100             # 采样估计
    return cpu, wall, len(kept), sum(len(k) for k in kept), cnt, est
rows = []
for mode, name in (('none', '(基线)只抛出并捕获、不记录'), ('all', '(a)每次完整捕获'), ('bucket', '(b)按指纹限流 + 计数器'), ('sample', '(c)前 5 次 + 每 100 次 1 次')):
    if mode == 'none':
        c0 = time.process_time()
        for _ in range(20000):
            try: recurse(30)
            except ValueError: pass
        cpu = time.process_time() - c0; rows.append((name, f'{cpu:.2f}', 0, 0, 20000, '-')); continue
    cpu, wall, nk, nb, cnt, est = storm(mode); rows.append((name, f'{cpu:.2f}', nk, f'{nb / 1e6:.2f} MB', cnt, est))
table(rows, ['处理方式', 'CPU 时间(s)', '完整捕获的次数', '保留的字节数', '实际发生的次数', '能还原出的总次数'])
print('  完整捕获的开销主要在格式化堆栈和序列化,同一个 bug 每次捕获的堆栈几乎一样,信息量很小;限流之后只保留少量样本,再用计数器记录总次数,开销接近基线,信息也没丢多少;只靠采样会让次数变成估计值')

# ============ 四 ============
print('== 四:没被处理的异常会不会丢。100 个任务各抛出一个异常:(a)提交到 ThreadPoolExecutor 但不取结果(不调 result());(b)用 threading.Thread 直接起线程;(c)asyncio.create_task 起任务但不 await。分别在“没有任何钩子”和“装了 threading.excepthook / asyncio 异常处理器 / Future 回调”的情况下,统计被错误追踪捕获到的异常个数')
def run_case(hooks):
    seen = []
    old_th = threading.excepthook
    if hooks: threading.excepthook = lambda a: seen.append('thread')
    def boom(): raise RuntimeError('boom')
    pool = concurrent.futures.ThreadPoolExecutor(4); futs = [pool.submit(boom) for _ in range(100)]
    if hooks:
        for f in futs: f.add_done_callback(lambda f: seen.append('future') if f.exception() else None)
    pool.shutdown(wait=True)
    ths = [threading.Thread(target=boom) for _ in range(100)]
    import io, contextlib
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        for t in ths: t.start()
        for t in ths: t.join()
    async def main():
        loop = asyncio.get_running_loop()
        if hooks: loop.set_exception_handler(lambda l, ctx: seen.append('asyncio'))
        async def abody(): raise RuntimeError('boom')
        for _ in range(100): asyncio.create_task(abody())
        await asyncio.sleep(0.3)
        import gc; gc.collect(); await asyncio.sleep(0.2)
    with contextlib.redirect_stderr(err): asyncio.run(main())
    threading.excepthook = old_th
    c = collections.Counter(seen); return c.get('future', 0), c.get('thread', 0), c.get('asyncio', 0), err.getvalue().count('Traceback') + err.getvalue().count('never retrieved')
rows = []
for hooks, name in ((False, '没有任何钩子'), (True, '装了钩子')):
    f, t, a, e = run_case(hooks); rows.append((name, f'{f} / 100', f'{t} / 100', f'{a} / 100', e))
table(rows, ['配置', '(a)线程池任务(Future 回调捕获到)', '(b)裸线程(threading.excepthook 捕获到)', '(c)asyncio 任务(异常处理器捕获到)', '被打印到 stderr 的堆栈/提示行数'])
print('  线程池里的任务异常存放在 Future 里,不取结果就悄悄丢了;裸线程和没 await 的 asyncio 任务的异常只会被默认处理打印到 stderr(没有集中的错误追踪就看不到);错误追踪要在这三个位置都装钩子')
print('ERRORS', dict(ERRORS))
