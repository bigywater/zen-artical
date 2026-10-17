import subprocess, json, os, sys
ft = open('ft_path.txt').read().strip()
def run(py, env=None, args=()):
    e = dict(os.environ); e.pop('HTTP_PROXY', None); e.pop('HTTPS_PROXY', None); e.update(env or {})
    return json.loads(subprocess.run([py, *args, 'exp/w91b.py'], capture_output=True, text=True, env=e, timeout=600).stdout)
def probe(py, env=None):
    e = dict(os.environ); e.pop('HTTP_PROXY', None); e.pop('HTTPS_PROXY', None); e.update(env or {})
    return subprocess.run([py, '-c', "import sys, sysconfig; print(sys.version.split()[0], '| Py_GIL_DISABLED =', sysconfig.get_config_var('Py_GIL_DISABLED'), '| sys._is_gil_enabled() =', sys._is_gil_enabled(), '| abiflags =', sys.abiflags)"], capture_output=True, text=True, env=e).stdout.strip()
cfgs = [("普通 3.14(有 GIL)", sys.executable, None), ("3.14t(自由线程)", ft, None), ("3.14t + PYTHON_GIL=1(重新打开 GIL)", ft, {'PYTHON_GIL': '1'})]
print("== 一、三个解释器 ==")
for name, py, env in cfgs: print(f"  {name:<34} {probe(py, env)}")
allres = {}
print("\n== 二、4 个 CPU 密集线程的加速比 (每个线程做 300 万次整数乘加, 各取 3 次最小值) ==")
print(f"  机器有 {os.cpu_count()} 个核")
for name, py, env in cfgs:
    r = run(py, env); allres[name] = r
    print(f"  {name}")
    for n, s, t in r['rows']: print(f"     线程数 {n}: 串行 {s*1000:7.1f} ms   线程并行 {t*1000:7.1f} ms   加速比 {s/t:4.2f}x")
print("\n== 三、4 个线程各做 50 万次 box[0] += 1, 重复 5 次, 期望每次 2000000 ==")
for name, py, env in cfgs: print(f"  {name:<34} {allres[name]['race']}")
json.dump(allres, open('out/91.json', 'w'), ensure_ascii=False)
