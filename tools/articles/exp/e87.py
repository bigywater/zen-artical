import subprocess, sys, os, tempfile, json, textwrap, time, importlib

HERE = os.getcwd(); W = os.path.realpath(tempfile.mkdtemp()); os.chdir(W)
def P(x): return x.replace(W, '<工作目录>').replace(os.path.realpath(sys.prefix), '<PREFIX>').replace(os.path.expanduser('~'), '~')
def run(args, env=None, cwd=W):
    e = dict(os.environ); e.pop('HTTP_PROXY', None); e.pop('HTTPS_PROXY', None); e.pop('PYTHONPATH', None)
    if env: e.update(env)
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True, env=e, cwd=cwd); return (r.stdout + r.stderr).strip()

os.makedirs('proj/sub'); os.makedirs('elsewhere'); os.makedirs('pp')
open('proj/show.py', 'w').write("import sys; print(repr(sys.path[0]))\n")
os.symlink(os.path.join(W, 'proj/show.py'), os.path.join(W, 'elsewhere/link.py'))
open('proj/pkg_mod.py', 'w').write("")
os.makedirs('proj/pkg'); open('proj/pkg/__init__.py', 'w').write(""); open('proj/pkg/m.py', 'w').write("import sys; print(repr(sys.path[0]))\n")

print("== 一、sys.path[0] 取决于怎么启动 ==")
print("  python proj/show.py            (在工作目录下) →", P(run(['proj/show.py'])))
print("  cd proj && python show.py                     →", P(run(['show.py'], cwd=os.path.join(W, 'proj'))))
print("  python -c 'import sys;print(repr(sys.path[0]))' →", P(run(['-c', 'import sys; print(repr(sys.path[0]))'])))
print("  python -m pkg.m  (在 proj 目录)                →", P(run(['-m', 'pkg.m'], cwd=os.path.join(W, 'proj'))))
print("  python elsewhere/link.py  (符号链接指向 proj/show.py) →", P(run(['elsewhere/link.py'])))
print("  python -P proj/show.py  (不自动加入脚本目录)   →", P(run(['-P', 'proj/show.py'])))
print("  PYTHONSAFEPATH=1 python -c ...                  →", P(run(['-c', 'import sys; print(repr(sys.path[0]))'], {'PYTHONSAFEPATH': '1'})))

print("\n== 二、完整的 sys.path, 每一项从哪来 ==")
open('proj/full.py', 'w').write("import sys\nfor i, p in enumerate(sys.path): print(i, p)\n")
out = run(['proj/full.py'], {'PYTHONPATH': os.path.join(W, 'pp')})
print("  (PYTHONPATH 指向 <工作目录>/pp)")
for l in out.splitlines(): print("   ", P(l))

print("\n== 三、同名文件遮蔽标准库 ==")
os.makedirs('shadow'); open('shadow/random.py', 'w').write("def randint(a, b): return 4  # 我写的\n")
open('shadow/use.py', 'w').write("import random\nprint('random 来自', random.__file__)\nprint('random.randint(1, 100) =', random.randint(1, 100))\n")
print("  shadow/ 里有一个自己写的 random.py, 从 shadow/use.py 里 import random:")
for l in P(run(['shadow/use.py'])).splitlines(): print("   ", l)
print("  同一个脚本, 但用 -P (脚本目录不进 sys.path) :")
for l in P(run(['-P', 'shadow/use.py'])).splitlines(): print("   ", l)
open('shadow/json.py', 'w').write("import json\nprint(json.dumps({'a': 1}))\n")
print("  文件本身叫 json.py, 里面 import json 再调用 dumps:")
print("   ", P(run(['shadow/json.py'])).splitlines()[-1])
open('shadow/os.py', 'w').write("print('这个 os.py 被执行了')\n"); open('shadow/use_os.py', 'w').write("import os; print('os 来自', os.__file__)\n")
print("  shadow/ 里放 os.py, 脚本里 import os:", P(run(['shadow/use_os.py'])), "(os 启动时已经导入, 不会被遮蔽)")

print("\n== 四、运行时改 sys.path, 以及目录缓存 ==")
os.makedirs('dyn')
sys.path.insert(0, os.path.join(W, 'dyn'))
try: import late_mod
except ModuleNotFoundError as e: print("  第一次 import late_mod →", type(e).__name__ + ":", e)
open('dyn/late_mod.py', 'w').write("X = 1\n")
try: import late_mod; print("  文件刚创建后立刻 import → 成功, X =", late_mod.X)
except ModuleNotFoundError as e: print("  文件刚创建后立刻 import →", type(e).__name__ + ":", e, " ← 目录内容被缓存了")
importlib.invalidate_caches()
try: import late_mod; print("  importlib.invalidate_caches() 之后 → 成功, X =", late_mod.X)
except ModuleNotFoundError as e: print("  invalidate_caches 之后 →", e)
fails = 0
for i in range(300):
    name = f"quick_{i}"
    try: importlib.import_module(name)
    except ModuleNotFoundError: pass
    open(f"dyn/{name}.py", "w").write("")           # 紧接着创建
    try: importlib.import_module(name)
    except ModuleNotFoundError: fails += 1
print(f"  连做 300 次「先 import 失败 → 立刻创建同名文件 → 再 import」, 第二次仍然找不到的有 {fails} 次")
print("  sys.path_importer_cache 里 dyn 目录对应:", type(sys.path_importer_cache[os.path.join(W, 'dyn')]).__name__)

print("\n== 五、真实 sys.path 各段的含义 (site / sysconfig) ==")
import site, sysconfig
paths = sysconfig.get_paths()
print("  stdlib     =", P(paths['stdlib'])); print("  platstdlib =", P(paths['platstdlib'])); print("  purelib    =", P(paths['purelib']))
print("  site.getusersitepackages() =", P(site.getusersitepackages()), "| ENABLE_USER_SITE =", site.ENABLE_USER_SITE)
json.dump({'w': W}, open('/dev/null', 'w'))
# 演示数据: 每个入口是否能找到 random
import importlib.machinery as M
def probe(name, path_list):
    rows = []
    for e in path_list:
        f = M.PathFinder.find_spec(name, [e]); rows.append((P(e) or '(空: 当前目录)', f.origin.replace(W, '<工作目录>').replace(os.path.realpath(sys.prefix), '<PREFIX>') if f else None))
    return rows
base = [p for p in json.loads(run(['-c', 'import sys, json; print(json.dumps(sys.path))'])) ]
base[0] = os.path.join(W, 'shadow')
d1 = probe('random', base[1:]); d2 = probe('random', base)
json.dump({'normal': d1, 'shadow': d2}, open(HERE + '/out/87.json', 'w'), ensure_ascii=False)
