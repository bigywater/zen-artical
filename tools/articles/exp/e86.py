import subprocess, sys, os, time, statistics, tempfile, json, re

def run(args, env=None, code=None):
    e = dict(os.environ); e.pop('HTTP_PROXY', None); e.pop('HTTPS_PROXY', None)
    if env: e.update(env)
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, env=e)

print("== 一、启动时按顺序导入了哪些模块 (-X importtime -c pass, 只列最外层) ==")
r = run(['-X', 'importtime', '-c', 'pass'])
rows = []
for l in r.stderr.splitlines()[1:]:
    m = re.match(r'import time:\s+(\d+) \|\s+(\d+) \|(\s*)(\S+)', l)
    if m: rows.append((m.group(4), int(m.group(1)), int(m.group(2)), len(m.group(3)) // 2))
top = [(n, s, c) for n, s, c, d in rows if d == 0]
print(f"  共 {len(rows)} 行导入记录, 其中最外层(不是被别的模块触发)的 {len(top)} 个, 顺序如下 (自身耗时 µs / 累计 µs):")
for i, (n, s, c) in enumerate(top): print(f"   {i+1:>2}. {n:<26} 自身 {s:>5}   累计 {c:>5}")
print(f"  最外层累计耗时合计 ≈ {sum(c for _, _, c in top)} µs")
site_c = next(c for n, s, c in top if n == 'site')
print(f"  其中 site 模块(处理 site-packages / .pth / sitecustomize)一项累计 {site_c} µs")

print("\n== 二、启动开关对速度和模块数的影响 (各 30 次, 取中位数) ==")
def bench(args, n=30):
    ts = []
    for _ in range(n):
        t = time.perf_counter(); run([*args, '-c', 'pass']); ts.append((time.perf_counter() - t) * 1000)
    return statistics.median(ts)
cases = [("python -c pass", []), ("python -S -c pass  (不 import site)", ['-S']), ("python -I -c pass  (隔离模式)", ['-I']), ("python -I -S -c pass", ['-I', '-S']), ("python -E -c pass  (忽略环境变量)", ['-E'])]
res = []
for name, a in cases:
    n_mod = int(run([*a, '-c', 'import sys; print(len(sys.modules))']).stdout.strip())
    ms = bench(a); res.append((name, ms, n_mod))
    print(f"  {name:<38} {ms:6.1f} ms   启动后 sys.modules 有 {n_mod} 个")

print("\n== 三、site 阶段会执行什么: .pth 文件与 sitecustomize ==")
d = tempfile.mkdtemp()
ub = os.path.join(d, 'ub'); env = {'PYTHONUSERBASE': ub}
usp = run(['-c', 'import site; print(site.getusersitepackages())'], env).stdout.strip()
os.makedirs(usp); os.makedirs(os.path.join(d, 'pp'))
open(os.path.join(usp, 'demo.pth'), 'w').write("import sys; sys.stderr.write('  [.pth] demo.pth 的这一行在启动时执行了\\n')\n" + os.path.join(d, 'extra_path') + "\n")
os.makedirs(os.path.join(d, 'extra_path'))
open(os.path.join(d, 'pp', 'sitecustomize.py'), 'w').write("import sys; sys.stderr.write('  [sitecustomize] 被自动导入了\\n')\n")
code = "import sys; sys.stderr.write('  [脚本] 主脚本开始执行\\n'); print('  extra_path 在 sys.path 里?', any(p.endswith('extra_path') for p in sys.path))"
r = run(['-c', code], {**env, 'PYTHONPATH': os.path.join(d, 'pp')})
print("  在用户 site-packages 里放 demo.pth, 在 PYTHONPATH 里放 sitecustomize.py, 然后运行:\n" + r.stderr.rstrip() + "\n" + r.stdout.rstrip())
r = run(['-S', '-c', code], {**env, 'PYTHONPATH': os.path.join(d, 'pp')}); print("  同样的环境, 加 -S:\n" + r.stderr.rstrip() + "\n" + r.stdout.rstrip())
r = run(['-I', '-c', code], {**env, 'PYTHONPATH': os.path.join(d, 'pp')}); print("  同样的环境, 加 -I:\n" + r.stderr.rstrip() + "\n" + r.stdout.rstrip())

print("\n== 四、sys.flags / sys.orig_argv ==")
r = run(['-I', '-c', 'import sys; print("orig_argv =", sys.orig_argv[1:], "| argv =", sys.argv, "| isolated =", sys.flags.isolated, "| no_user_site =", sys.flags.no_user_site, "| ignore_environment =", sys.flags.ignore_environment)'])
print(" ", r.stdout.strip())
json.dump({'top': top, 'res': res}, open('out/86.json', 'w'), ensure_ascii=False)
