import os, sys, subprocess, tempfile, textwrap, json, time, re

HERE = os.environ['HERE']; W = os.path.realpath(tempfile.mkdtemp()); os.chdir(W)
V = HERE + '/venv/bin'
E = dict(os.environ); E.pop('HTTP_PROXY', None); E.pop('HTTPS_PROXY', None); E['NO_COLOR'] = '1'; E['MYPY_FORCE_COLOR'] = '0'
def w(path, body):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True); open(path, 'w').write(textwrap.dedent(body).lstrip())
def mypy(*args, cache=True):
    a = [V + '/mypy', '--no-color-output', '--show-error-codes', '--no-pretty', *args]
    if not cache: a += ['--cache-dir=/dev/null']
    t = time.perf_counter(); r = subprocess.run(a, capture_output=True, text=True, env=E, cwd=W); el = time.perf_counter() - t
    return (r.stdout + r.stderr).strip(), el
def count(out):
    m = re.search(r'Found (\d+) errors?', out); return int(m.group(1)) if m else 0

w('legacy/__init__.py', "")
w('legacy/orders.py', '''
    import json

    def load_orders(path):
        with open(path) as f:
            return json.load(f)

    def order_total(order):
        total = 0
        for item in order["items"]:
            total = total + item["price"] * item["qty"]
        return total + "1"                     # 旧代码里的 bug: int + str

    def format_receipt(order, currency="CNY"):
        lines = []
        for item in order["items"]:
            lines.append(item["name"] + ": " + item["price"])   # bug: str + int (取决于数据)
        return "\\n".join(lines) + currency

    class Cache:
        def __init__(self):
            self.data = {}
            self.hits = 0
        def get(self, key):
            if key in self.data:
                self.hits += 1
                return self.data[key]
            return None
''')
w('legacy/users.py', '''
    def find_user(users, name):
        for u in users:
            if u["name"] == name:
                return u

    def greet(user):
        return "hello " + user["name"].upper()

    def age_next_year(user):
        return user["age"] + "1"
''')
w('legacy/helpers.py', '''
    def merge(a, b):
        r = dict(a)
        r.update(b)
        return r

    def safe_int(x, default=0):
        try:
            return int(x)
        except (TypeError, ValueError):
            return default
''')
w('newcode/__init__.py', "")
w('newcode/service.py', '''
    from legacy.orders import order_total, Cache
    from legacy.helpers import safe_int

    def discounted(order: dict[str, object], rate: float) -> float:
        base: float = order_total(order)          # legacy 函数没有类型 → 返回 Any, mypy 不知道它其实会出错
        return base * rate

    def parse_qty(raw: str) -> int:
        n: str = safe_int(raw)                    # 这里我们错把结果标成 str; legacy 无类型, mypy 不报
        return len(n)

    def cache_hits(c: Cache) -> int:
        return c.hits + "1"                       # 新代码里自己写错的, 可以被检查出来
''')

print("mypy 版本:", mypy('--version')[0])
print("\n== 一、默认配置: 旧代码里的 bug 一个都看不见 ==")
out, t = mypy('legacy', 'newcode', cache=False)
print(out)

levels = [
    ("默认配置", []),
    ("--check-untyped-defs", ['--check-untyped-defs']),
    ("--disallow-untyped-defs", ['--disallow-untyped-defs']),
    ("--strict", ['--strict']),
]
print("\n== 二、逐档收紧, 每档报告多少个错误 ==")
counts = {}
for name, flags in levels:
    out, t = mypy('legacy', 'newcode', *flags, cache=False); counts[name] = count(out)
    print(f"  {name:<26} {counts[name]:>3} 个错误")
out, _ = mypy('legacy', 'newcode', '--check-untyped-defs', cache=False)
print("\n  --check-untyped-defs 下报告的 2 个错误(默认配置一个都看不到):")
print("\n".join("    " + l for l in out.splitlines() if 'error' in l))
out, _ = mypy('legacy', 'newcode', '--strict', cache=False)
print("\n  --strict 下的 14 个错误按类型统计:")
import collections
c = collections.Counter(re.findall(r'\[([a-z-]+)\]$', l)[0] for l in out.splitlines() if 'error' in l and re.findall(r'\[([a-z-]+)\]$', l))
print("\n".join(f"    {k:<18} {v}" for k, v in c.most_common()))

print("\n== 三、Any 会传染: 无类型的函数返回 Any ==")
w('probe.py', '''
    from legacy.helpers import safe_int, merge
    from legacy.orders import Cache
    reveal_type(safe_int)
    reveal_type(safe_int("3"))
    reveal_type(merge({"a": 1}, {"b": 2}))
    reveal_type(Cache().get("k"))
''')
out, _ = mypy('probe.py', cache=False); print("\n".join("  " + l for l in out.splitlines() if 'note' in l))

print("\n== 四、按模块分档: 旧模块宽松, 新模块严格 ==")
w('mypy.ini', '''
    [mypy]
    check_untyped_defs = true

    [mypy-legacy.*]
    ignore_errors = true

    [mypy-newcode.*]
    strict = true
''')
out, _ = mypy('legacy', 'newcode', '--config-file=mypy.ini', cache=False)
print(f"  mypy.ini: 全局 check_untyped_defs; legacy.* ignore_errors; newcode.* strict → {count(out)} 个错误")
print("\n".join("    " + l for l in out.splitlines() if 'error' in l))

print("\n== 五、# type: ignore 与 warn_unused_ignores ==")
w('ign.py', '''
    x: int = "a"  # type: ignore
    y: int = 1  # type: ignore
    z: int = "b"  # type: ignore[assignment]
''')
o1, _ = mypy('ign.py', cache=False); o2, _ = mypy('ign.py', '--warn-unused-ignores', cache=False)
print("  默认:", o1.splitlines()[-1]); print("  --warn-unused-ignores:"); print("\n".join("    " + l for l in o2.splitlines()))

print("\n== 六、增量缓存 ==")
big = os.path.join(W, 'bigpkg'); os.makedirs(big)
for i in range(60):
    w(f'bigpkg/m{i}.py', "\n".join(f"def f{i}_{k}(x: int) -> int:\n    return x + {k}\n" for k in range(40)) + (f"\nfrom bigpkg.m{i-1} import f{i-1}_0\n" if i else ""))
w('bigpkg/__init__.py', "")
subprocess.run(['rm', '-rf', '.mypy_cache'], cwd=W)
_, t1 = mypy('bigpkg'); _, t2 = mypy('bigpkg')
open('bigpkg/m30.py', 'a').write("\ndef newfn(x: int) -> int:\n    return x\n")
_, t3 = mypy('bigpkg')
print(f"  60 个模块: 冷启动 {t1:.2f} s | 无改动再跑 {t2:.2f} s | 改了 1 个文件再跑 {t3:.2f} s | 缓存目录大小 {sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk('.mypy_cache') for f in fs)/1e6:.1f} MB")
json.dump({'counts': counts, 't': [t1, t2, t3]}, open(HERE + '/out/103.json', 'w'), ensure_ascii=False)
