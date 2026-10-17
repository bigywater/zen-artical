import os, sys, subprocess, tempfile, textwrap, json, time, re

HERE = os.environ['HERE']; W = os.path.realpath(tempfile.mkdtemp()); os.chdir(W)
V = HERE + '/venv/bin'
E = dict(os.environ); E.pop('HTTP_PROXY', None); E.pop('HTTPS_PROXY', None); E['NO_COLOR'] = '1'
def w(path, body):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True); open(path, 'w').write(textwrap.dedent(body).lstrip())
def py(code):
    r = subprocess.run([sys.executable, '-c', textwrap.dedent(code)], capture_output=True, text=True, env=E, cwd=W); return (r.stdout + r.stderr).strip()
def pytest(*a):
    r = subprocess.run([V + '/python', '-m', 'pytest', '-p', 'no:cacheprovider', '-q', '--no-header', '-W', 'ignore', *a], capture_output=True, text=True, env=E, cwd=W); return (r.stdout + r.stderr).strip()

w('shop.py', '''
    import time, datetime
    from time import time as time_fn
    def is_business_hours():
        h = datetime.datetime.fromtimestamp(time.time()).hour
        return 9 <= h < 17
    def timestamp_via_from_import():
        return time_fn()
''')
print("== 一、依赖「现在」的测试: 什么时候跑,什么结果 ==")
code = '''
    from unittest.mock import patch
    import datetime, shop
    res = []
    for hour in range(24):
        fake = datetime.datetime(2026, 9, 29, hour, 30).timestamp()
        with patch("time.time", return_value=fake):
            res.append(shop.is_business_hours())
    print("不打补丁的测试 assert is_business_hours() 在一天 24 个整点里会通过的时刻:", [h for h, ok in enumerate(res) if ok])
    print("  → 24 小时里 %d 小时通过, %d 小时失败: 同一份代码、同一个测试, 结果取决于你在几点跑" % (sum(res), 24 - sum(res)))
'''
print(py(code))

print("\n== 二、patch 的陷阱 ==")
code = '''
    from unittest.mock import patch
    import shop, time, datetime
    with patch("time.time", return_value=1234.0):
        print("patch('time.time') 之后: shop.is_business_hours() 看到的 time.time() =", time.time(), "(生效, 因为它写的是 time.time())")
        print("  但 from time import time as time_fn 的那份:", shop.timestamp_via_from_import(), "  ← 没有被替换, 仍是真实时间戳(≈ 现在)" if shop.timestamp_via_from_import() > 1e9 else "  被替换了")
    with patch("shop.time_fn", return_value=1234.0):
        print("改成 patch('shop.time_fn') 之后:", shop.timestamp_via_from_import(), "(patch 要打在「使用它的地方」)")
    try:
        with patch("datetime.datetime.now", return_value=1): pass
    except TypeError as e: print("patch('datetime.datetime.now') → TypeError:", e)
'''
print(py(code))

print("\n== 三、更好的办法: 把时钟当成参数传进去 ==")
w('clock.py', '''
    import datetime
    def is_business_hours(now=None):
        now = now or datetime.datetime.now()
        return 9 <= now.hour < 17
''')
code = '''
    import datetime, clock
    print("  is_business_hours(datetime(2026,9,29,10,0)) =", clock.is_business_hours(datetime.datetime(2026, 9, 29, 10, 0)))
    print("  is_business_hours(datetime(2026,9,29,23,0)) =", clock.is_business_hours(datetime.datetime(2026, 9, 29, 23, 0)))
    print("  (不需要任何 patch, 也不依赖真实时钟)")
'''
print(py(code))

print("\n== 四、随机数 ==")
w('lucky.py', '''
    import random
    def roll(rng=random): return rng.randint(1, 6)
''')
code = '''
    import random, lucky
    print("  全局 random 无种子,连跑 8 次 roll():", [lucky.roll() for _ in range(8)])
    random.seed(42); a = [lucky.roll() for _ in range(6)]
    random.seed(42); b = [lucky.roll() for _ in range(6)]
    print("  random.seed(42) 两次:", a, b, "相同:", a == b)
    r1, r2 = random.Random(7), random.Random(7)
    print("  注入独立的 Random(7) 实例:", [lucky.roll(r1) for _ in range(6)], [lucky.roll(r2) for _ in range(6)])
    random.seed(1); x = random.random(); r = random.Random(1); y = r.random()
    print("  全局 seed(1) 与 Random(1) 产生同一个序列:", x == y)
    random.seed(99)
    _ = random.Random(5).random()
    print("  seed(99) 后另造并使用一个 Random(5), 全局序列是否完全不受影响?", random.random() == (lambda: (random.seed(99), random.random())[1])())
'''
print(py(code))
SECOND = py('import random; random.seed(0); a = random.randint(1, 100); b = random.randint(1, 100); print(a, b)').split()
FIRST_V, SECOND_V = SECOND
w('test_order.py', f'''
    import random
    def test_a_seeds():
        random.seed(0)
        assert random.randint(1, 100) == {FIRST_V}          # 依赖刚刚设置的种子
    def test_b_uses_global():
        # 没有自己设置种子: 它「碰巧」期望 seed(0) 之后的第二个值 —— 只有紧跟在 test_a 之后才成立
        assert random.randint(1, 100) == {SECOND_V}
''')
print(f"  (seed(0) 之后依次得到 {FIRST_V}, {SECOND_V};test_a 断言第一个值,test_b 没设种子却断言第二个值)")
print("\n  两个测试共用全局随机状态: 顺序 a → b:", pytest('test_order.py::test_a_seeds', 'test_order.py::test_b_uses_global').splitlines()[-1])
print("  顺序 b → a:                            ", pytest('test_order.py::test_b_uses_global', 'test_order.py::test_a_seeds').splitlines()[-1])

print("\n== 五、禁止真实网络 ==")
w('conftest.py', '''
    import socket, pytest
    @pytest.fixture
    def no_network(monkeypatch):
        real = socket.socket.connect
        def guard(self, addr, *a, **k):
            host = addr[0] if isinstance(addr, tuple) else addr
            if host not in ("127.0.0.1", "::1", "localhost"):
                raise RuntimeError(f"测试里不允许访问外部网络: {addr}")
            return real(self, addr, *a, **k)
        monkeypatch.setattr(socket.socket, "connect", guard)
''')
w('test_net.py', '''
    import socket, time, pytest
    def fetch(host):
        s = socket.create_connection((host, 80), timeout=0.6); s.close()
    def test_without_guard():
        t = time.perf_counter()
        try: fetch("203.0.113.1")            # TEST-NET-3: 文档保留地址, 不会有任何主机应答
        except OSError as e: print("  [无保护] %s 用时 %.2f s" % (type(e).__name__, time.perf_counter() - t))
    def test_with_guard(no_network):
        t = time.perf_counter()
        try: fetch("203.0.113.1")
        except RuntimeError as e: print("  [有保护] RuntimeError: %s 用时 %.4f s" % (e, time.perf_counter() - t))
    def test_loopback_still_ok(no_network):
        srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(1)
        c = socket.create_connection(srv.getsockname(), timeout=1); c.close(); srv.close()
        print("  [有保护] 连接本机回环地址仍然可以")
''')
o = pytest('-s', 'test_net.py')
print("\n".join(l[l.index('['):] and "  " + l[l.index('['):] for l in o.splitlines() if '[无保护]' in l or '[有保护]' in l))
print("  ", o.splitlines()[-1])

print("\n== 六、把 sleep 换掉 ==")
w('retry.py', '''
    import time
    def call_with_retry(f, tries=3, delay=1.0):
        for i in range(tries):
            try: return f()
            except ConnectionError:
                if i == tries - 1: raise
                time.sleep(delay)
''')
w('test_retry.py', '''
    import time, retry, pytest
    def make(n):
        state = {"n": 0}
        def f():
            state["n"] += 1
            if state["n"] <= n: raise ConnectionError("boom")
            return "ok"
        return f
    def test_real_sleep():
        assert retry.call_with_retry(make(2), delay=0.5) == "ok"          # 真实等待 0.5 + 0.5
    def test_patched_sleep(monkeypatch):
        slept = []
        monkeypatch.setattr(time, "sleep", slept.append)                 # 记录而不真的睡
        assert retry.call_with_retry(make(2), delay=0.5) == "ok"
        assert slept == [0.5, 0.5]
''')
for name in ('test_real_sleep', 'test_patched_sleep'):
    o = pytest(f'test_retry.py::{name}', '-v')
    print(f"  {name:<20} → {o.splitlines()[-1].strip('= ')}")
json.dump({}, open(HERE + '/out/105.json', 'w'))
