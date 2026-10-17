import os, sys, subprocess, tempfile, textwrap, json, re, time, shutil

HERE = os.environ['HERE']; W = os.path.realpath(tempfile.mkdtemp()); os.chdir(W)
V = HERE + '/venv/bin'
E = dict(os.environ); E.pop('HTTP_PROXY', None); E.pop('HTTPS_PROXY', None); E['NO_COLOR'] = '1'
def w(path, body):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True); open(path, 'w').write(textwrap.dedent(body).lstrip())
def run(args):
    r = subprocess.run(args, capture_output=True, text=True, env=E, cwd=W); return r.returncode, (r.stdout + r.stderr)
def clean(s): return re.sub(r'[⠀-⣿]\s*[A-Za-z ]+', '', s)

w('src/calc.py', '''
    def clamp(x, lo, hi):
        if x < lo:
            return lo
        if x > hi:
            return hi
        return x

    def is_adult(age):
        return age >= 18

    def total(prices, tax):
        s = 0
        for p in prices:
            s += p
        return s * (1 + tax)
''')
w('pyproject.toml', '''
    [tool.mutmut]
    source_paths = ["src/"]
    pytest_add_cli_args_test_selection = ["test_calc.py"]
''')
w('test_calc.py', '''
    import sys; sys.path.insert(0, "src")
    from calc import clamp, is_adult, total

    def test_clamp_runs():
        clamp(5, 0, 10); clamp(-1, 0, 10); clamp(99, 0, 10)      # 三个分支都执行了, 但没有断言

    def test_adult():
        assert is_adult(30)

    def test_total():
        assert total([1, 2], 0) == 3
''')
print("mutmut", run([V + '/mutmut', '--version'])[1].strip())
print("\n== 一、覆盖率: 这套测试看上去很完整 ==")
rc, out = run([V + '/python', '-m', 'coverage', 'run', '--branch', '--source=src', '-m', 'pytest', '-q', '--no-header', '-p', 'no:cacheprovider', 'test_calc.py'])
print("  pytest:", out.strip().splitlines()[-1])
print("\n".join("  " + l for l in run([V + '/python', '-m', 'coverage', 'report', '-m'])[1].strip().splitlines()))

def mm_run():
    t = time.perf_counter(); rc, out = run([V + '/mutmut', 'run']); el = time.perf_counter() - t
    last = [l for l in re.split(r'[\r\n]', out) if re.search(r'\d+/\d+\s+🎉', l)]
    m = re.search(r'(\d+)/(\d+)\s+🎉 (\d+) 🫥 (\d+)\s+⏰ (\d+)\s+🤔 (\d+)\s+🙁 (\d+)', last[-1])
    return el, dict(zip(['done', 'total', 'killed', 'nocov', 'timeout', 'suspicious', 'survived'], map(int, m.groups())))
print("\n== 二、变异测试: mutmut run ==")
el, s1 = mm_run()
print(f"  共生成 {s1['total']} 个变异体, 用时 {el:.1f} s: 被测试杀死 {s1['killed']} 个, 存活 {s1['survived']} 个 (存活 = 测试没发现这个改动)")
rc, res = run([V + '/mutmut', 'results']); res = clean(res)
names = re.findall(r'^\s*(\S+): survived', res, re.M)
rc, resall = run([V + '/mutmut', 'results', '--all', 'true']); resall = clean(resall)
status1 = re.findall(r'^\s*(\S+): (\w+)', resall, re.M)
alld = {}
for n, st in status1:
    rc, d = run([V + '/mutmut', 'show', n]); alld[n] = (st, [l for l in d.splitlines() if l.startswith(('-', '+')) and not l.startswith(('---', '+++'))])
print("  全部变异体及其状态:")
for n, (st, ls) in alld.items(): print(f"    {n:<26} {st:<9} " + "  ".join(ls))
print("  mutmut results 里存活的变异体:"); print("\n".join("    " + n for n in names))
print("\n== 三、每个存活变异体具体改了什么 ==")
diffs = []
for n in names:
    rc, d = run([V + '/mutmut', 'show', n]); lines = [l for l in d.splitlines() if l.startswith(('-', '+')) and not l.startswith(('---', '+++'))]
    diffs.append((n, lines)); print(f"  {n}: " + "  ".join(lines))

w('test_calc.py', '''
    import sys; sys.path.insert(0, "src")
    from calc import clamp, is_adult, total

    def test_clamp():
        assert clamp(5, 0, 10) == 5
        assert clamp(-1, 0, 10) == 0
        assert clamp(99, 0, 10) == 10
        assert clamp(0, 0, 10) == 0        # 边界: 等于下限
        assert clamp(10, 0, 10) == 10      # 边界: 等于上限

    def test_adult():
        assert is_adult(30)
        assert is_adult(18)                # 边界
        assert not is_adult(17)

    def test_total():
        assert total([1, 2], 0) == 3
        assert total([10, 20], 0.5) == 45.0
        assert total([], 0.5) == 0
''')
shutil.rmtree('mutants', ignore_errors=True)
print("\n== 四、补上边界断言之后再跑一遍 ==")
el2, s2 = mm_run()
print(f"  共 {s2['total']} 个变异体, 用时 {el2:.1f} s: 杀死 {s2['killed']} 个, 存活 {s2['survived']} 个")
rc, res2 = run([V + '/mutmut', 'results']); names2 = re.findall(r'^\s*(\S+): survived', clean(res2), re.M)
for n in names2:
    rc, d = run([V + '/mutmut', 'show', n]); lines = [l for l in d.splitlines() if l.startswith(('-', '+')) and not l.startswith(('---', '+++'))]
    print(f"  仍然存活: {n}: " + "  ".join(lines))
json.dump({'all1': alld, 's1': s1, 's2': s2, 'diffs': diffs, 'names2': names2, 't': [el, el2]}, open(HERE + '/out/104.json', 'w'), ensure_ascii=False)
