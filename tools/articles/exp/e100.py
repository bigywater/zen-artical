import os, sys, subprocess, tempfile, textwrap, json, time, re

HERE = os.environ['HERE']; W = os.path.realpath(tempfile.mkdtemp()); os.chdir(W)
PY = HERE + '/venv/bin/python'
E = dict(os.environ); E.pop('HTTP_PROXY', None); E.pop('HTTPS_PROXY', None); E['COVERAGE_FILE'] = os.path.join(W, '.coverage')
def w(path, body): open(path, 'w').write(textwrap.dedent(body).lstrip())
def run(args):
    r = subprocess.run([PY, *args], capture_output=True, text=True, env=E, cwd=W); return (r.stdout + r.stderr).strip()
def cov(*args): return run(['-m', 'coverage', *args])

print("coverage", cov('--version').splitlines()[0])
w('shop.py', '''
    def price_with_discount(price, qty, is_member):
        total = price * qty
        if qty >= 10:
            total = total * 0.9
        if is_member:
            total = total - 5
        return total
''')
w('untested.py', '''
    def never_called(x):
        return x * 2
    def also_never(y):
        return y + 1
''')
w('test_shop_noassert.py', '''
    from shop import price_with_discount
    def test_runs():
        price_with_discount(100, 10, True)      # 只是调用, 什么也不断言
''')
print("\n== 一、只调用、不断言的测试: 覆盖率会怎么说 ==")
print(run(['-m', 'pytest', '-q', '--no-header', '-p', 'no:cacheprovider', '--version']).splitlines()[0])
cov('run', '--branch', '-m', 'pytest', '-q', '--no-header', '-p', 'no:cacheprovider', 'test_shop_noassert.py')
print("$ coverage report -m --include=shop.py  (行覆盖 + 分支覆盖)")
print(cov('report', '-m', '--include=shop.py'))
cov('run', '-m', 'pytest', '-q', '--no-header', '-p', 'no:cacheprovider', 'test_shop_noassert.py')
print("\n  不开分支覆盖(只算行)时的同一个测试:")
print("\n".join("  " + l for l in cov('report', '-m', '--include=shop.py').splitlines()))

print("\n== 二、100% 行覆盖的测试, 有没有发现 bug ==")
print("  bug: 会员减 5 元不设下限, 小额订单会变成负数。price_with_discount(1, 1, True) =", run(['-c', 'from shop import price_with_discount; print(price_with_discount(1, 1, True))']))
print("  只调用不断言的测试(上面的 test_shop_noassert.py, 覆盖了每一行):", run(['-m', 'pytest', '-q', '--no-header', '-p', 'no:cacheprovider', 'test_shop_noassert.py']).splitlines()[-1])
w('test_shop_prop.py', "from shop import price_with_discount\ndef test_never_negative(): assert price_with_discount(1, 1, True) >= 0\n")
print("  一条真正在断言业务规则的测试(价格不应为负):", run(['-m', 'pytest', '-q', '--no-header', '-p', 'no:cacheprovider', 'test_shop_prop.py']).splitlines()[-1])
cov('run', '--branch', '-m', 'pytest', '-q', '--no-header', '-p', 'no:cacheprovider', 'test_shop_prop.py')
print("  这条能发现 bug 的测试自己的覆盖率:"); print("\n".join("    " + l for l in cov('report', '-m', '--include=shop.py').splitlines()))

print("\n== 三、没被 import 的文件默认不出现在报告里 ==")
w('test_only_shop.py', '''
    from shop import price_with_discount
    def test_a(): assert price_with_discount(100, 1, False) == 100
    def test_b(): assert price_with_discount(100, 10, False) == 900.0
    def test_c(): assert price_with_discount(100, 1, True) == 95
''')
cov('run', '--branch', '-m', 'pytest', '-q', '--no-header', '-p', 'no:cacheprovider', 'test_only_shop.py')
print("$ coverage report   (默认: 只统计被导入过的文件)")
print(cov('report', '--omit=test_*'))
cov('run', '--branch', '--source=.', '-m', 'pytest', '-q', '--no-header', '-p', 'no:cacheprovider', 'test_only_shop.py')
print("$ coverage run --source=. ...; coverage report   (把整个目录都算进来)")
print(cov('report', '--omit=test_*'))

print("\n== 四、# pragma: no cover 会直接改变数字 ==")
w('shop2.py', '''
    def f(x):
        if x > 0:
            return 1
        else:  # pragma: no cover
            return -1
''')
w('test_shop2.py', "from shop2 import f\ndef test_f(): assert f(1) == 1\n")
cov('run', '--branch', '-m', 'pytest', '-q', '--no-header', '-p', 'no:cacheprovider', 'test_shop2.py')
print("\n".join(l for l in cov('report', '-m', '--include=shop2.py').splitlines()))

print("\n== 五、覆盖率的运行开销 ==")
w('hot.py', '''
    import time
    def work(n):
        s = 0
        for i in range(n):
            if i % 3 == 0: s += i
            else: s -= 1
        return s
    t = time.perf_counter(); work(2_000_000); print(round((time.perf_counter() - t) * 1000, 1))
''')
lines = "\n".join(f"    v{i} = {i} + 1" for i in range(30000))
w('many.py', "import time\ndef big():\n" + lines + "\n    return v0\nt = time.perf_counter(); big(); print(round((time.perf_counter() - t) * 1000, 1))\n")
def best(prefix, script, n=7):
    return min(float(run([*prefix, script]).splitlines()[-1]) for _ in range(n))
for label, script in (("同一批代码反复执行(200 万次循环, 只有几行不同的代码)", 'hot.py'), ("3 万行不同的代码各执行一次", 'many.py')):
    plain = best([], script); cl = best(['-m', 'coverage', 'run'], script); cb = best(['-m', 'coverage', 'run', '--branch'], script)
    print(f"  {label}:\n     不开覆盖率 {plain:7.1f} ms | 行覆盖 {cl:7.1f} ms ({cl/plain:.2f}x) | 行+分支覆盖 {cb:7.1f} ms ({cb/plain:.2f}x)   (各 7 次取最小值)")
    if script == 'hot.py': J = {'hot': [plain, cl, cb]}
    else: J['many'] = [plain, cl, cb]
json.dump(J, open(HERE + '/out/100.json', 'w'))
