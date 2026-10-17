import os, sys, subprocess, tempfile, textwrap, json, time, shutil, difflib

HERE = os.environ['HERE']; W = os.path.realpath(tempfile.mkdtemp()); os.chdir(W)
V = HERE + '/venv/bin'
E = dict(os.environ); E.pop('HTTP_PROXY', None); E.pop('HTTPS_PROXY', None); E['NO_COLOR'] = '1'
def run(args, cwd=W):
    r = subprocess.run(args, capture_output=True, text=True, env=E, cwd=cwd); return r.returncode, (r.stdout + r.stderr).strip()
def w(path, body):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True); open(path, 'w').write(textwrap.dedent(body).lstrip())

MESSY = '''
import sys, os
from typing import List,Dict, Optional
import requests_not_installed
from collections import (OrderedDict,
    defaultdict, Counter, deque, namedtuple, ChainMap, UserDict)
import json
import re


def build(items:List[int],  mapping: Dict[str,int]={}, flag = True)->Optional[str]:
    result = {'a':1,'b':2,
        'c':3}
    long_call = some_function_name(argument_number_one, argument_number_two, argument_number_three, argument_number_four)
    if flag: return "yes"
    else:
        return 'no'
'''
w('messy.py', MESSY)
print("版本:", "; ".join(p + " " + run([V + '/python', '-m', 'pip', 'show', p])[1].splitlines()[1].split(': ')[1] for p in ('black', 'isort', 'ruff')))
print("\n== 一、各工具只做自己的事 ==")
for name, cmd in (("black", [V + '/black', '-q', '-']), ("isort", [V + '/isort', '-q', '-']), ("ruff format", [V + '/ruff', 'format', '-']), ("ruff check --select I --fix", [V + '/ruff', 'check', '--select', 'I', '--fix', '--stdin-filename', 'messy.py', '-'])):
    r = subprocess.run(cmd, input=MESSY, capture_output=True, text=True, env=E, cwd=W)
    out = r.stdout
    d = [l for l in difflib.unified_diff(MESSY.splitlines(), out.splitlines(), lineterm='', n=0) if not l.startswith(('---', '+++', '@@'))]
    imports_changed = [l for l in d if 'import' in l]
    print(f"  {name:<28} 改动 {len(d):>2} 行 | 其中涉及 import 的 {len(imports_changed)} 行 | 是否把 {{'a':1 ...}} 改成 {{\"a\": 1, ...}}: {'\"a\": 1' in out}")
print("  → black 与 ruff format 是「代码格式」,isort 与 ruff -I 是「import 排序」。谁也不会删掉没用到的 import:")
rc, out = run([V + '/ruff', 'check', '--select', 'F401,F821,E501', '--output-format', 'concise', 'messy.py'])
print("\n".join("    " + l for l in out.splitlines()[:8]))

IMPORTS = "\n".join(MESSY.strip().splitlines()[:7]) + "\n"
print("\n== 二、经典冲突: isort 默认配置 + black(只看 import 部分) ==")
print("  待处理的 import 片段:"); print("\n".join("    " + l for l in IMPORTS.splitlines()))
w('a.py', IMPORTS); run([V + '/isort', '-q', 'a.py']); rc, out = run([V + '/black', '--check', '--diff', '-q', 'a.py'])
print("  isort(默认配置) 之后, black --check 返回码 =", rc, "(1 = black 还想再改)")
print("  isort 默认生成:"); print("\n".join("    " + l for l in open('a.py').read().splitlines()))
print("  black 想改成:"); print("\n".join("    " + l for l in out.splitlines() if l.startswith('+') and not l.startswith('+++')))
w('b.py', IMPORTS); run([V + '/isort', '-q', '--profile', 'black', 'b.py']); rc2, out2 = run([V + '/black', '--check', '-q', 'b.py'])
print("  isort --profile black 之后, black --check 返回码 =", rc2, "(0 = 已经一致)")

print("\n== 三、CI 里两个检查都开着: 不同流水线的最终状态 ==")
def pipeline(seq):
    w('c.py', MESSY)
    for tool in seq:
        if tool == 'isort': run([V + '/isort', '-q', 'c.py'])
        elif tool == 'isort-black': run([V + '/isort', '-q', '--profile', 'black', 'c.py'])
        else: run([V + '/black', '-q', 'c.py'])
    b = run([V + '/black', '--check', '-q', 'c.py'])[0]; i = run([V + '/isort', '--check-only', '-q', 'c.py'])[0]; ib = run([V + '/isort', '--check-only', '-q', '--profile', 'black', 'c.py'])[0]
    return b, i, ib
for label, seq in (("isort(默认) → black", ['isort', 'black']), ("black → isort(默认)", ['black', 'isort']), ("isort --profile black → black", ['isort-black', 'black']), ("black → isort --profile black", ['black', 'isort-black'])):
    b, i, ib = pipeline(seq)
    print(f"  {label:<32} black --check: {'通过' if b == 0 else '失败'} | isort --check(默认配置): {'通过' if i == 0 else '失败'} | isort --check(black profile): {'通过' if ib == 0 else '失败'}")

print("\n== 四、ruff 一个工具能替代吗 ==")
shutil.copy('messy.py', 'p1.py'); run([V + '/isort', '-q', '--profile', 'black', 'p1.py']); run([V + '/black', '-q', 'p1.py'])
shutil.copy('messy.py', 'p2.py'); run([V + '/ruff', 'check', '--select', 'I', '--fix', '-q', 'p2.py']); run([V + '/ruff', 'format', '-q', 'p2.py'])
a, b = open('p1.py').read(), open('p2.py').read()
print("  isort(black profile)+black 与 ruff(I)+ruff format 的结果完全相同?", a == b)
if a != b:
    print("  差异:"); print("\n".join("    " + l for l in difflib.unified_diff(a.splitlines(), b.splitlines(), 'isort+black', 'ruff', lineterm='', n=0) if not l.startswith(('---', '+++'))))
print("  最终代码:"); print("\n".join("    " + l for l in b.splitlines()))

print("\n== 五、速度: 300 个文件、约 2 万行 ==")
os.makedirs('big')
for i in range(300):
    body = MESSY.replace('build', f'build_{i}')
    open(f'big/m{i}.py', 'w').write(body * 2)
def timed(cmd, n=3):
    best = 1e9
    for _ in range(n):
        shutil.rmtree('bigc', ignore_errors=True); shutil.copytree('big', 'bigc')
        t = time.perf_counter(); run(cmd + ['bigc']); best = min(best, time.perf_counter() - t)
    return best
lines = sum(len(open(f'big/m{i}.py').read().splitlines()) for i in range(300))
res = {}
for name, cmd in (("black", [V + '/black', '-q']), ("ruff format", [V + '/ruff', 'format', '-q']), ("isort --profile black", [V + '/isort', '-q', '--profile', 'black']), ("ruff check --select I --fix", [V + '/ruff', 'check', '--select', 'I', '--fix', '-q'])):
    res[name] = timed(cmd); print(f"  {name:<30} {res[name]*1000:8.0f} ms")
print(f"  (共 {lines} 行, 300 个文件; 每次都从原始文件重新拷贝, 取 3 次最小值)")
json.dump(res, open(HERE + '/out/102.json', 'w'))
