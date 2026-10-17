"""out/w60.txt 由多次实验合并而成:一/三/四/五 来自 exp/w60.py(旧的第 1/3/4/5 节),二、六 来自 w60b.py,七 来自 w60c.py,八 来自 w60e.py,九~十二 来自 w60d.py。"""
import re, sys, os
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def secs(name):
    t = open(f'{D}/out/{name}.txt').read(); parts = re.split(r'(?m)^(?=== )', t); return [p.rstrip('\n') for p in parts if p.startswith('== ')]
NUM = '零一二三四五六七八九十'
def lab(n): return NUM[n] if n <= 10 else '十' + NUM[n - 10]
old = secs('w60_base'); b = secs('w60b'); c = secs('w60c'); e = secs('w60e'); d = secs('w60d')
pick = [old[0], b[0], old[2], old[3], old[4], b[1], c[0], e[0], d[0], d[1], d[2], d[3]]
out = []
for i, s in enumerate(pick, 1):
    s = re.sub(r'^== [^:]+:', f'== {lab(i)}:', s, count=1)
    s = s.replace('第九节的 3 次 + 本节的 5 次', '第十节的 3 次 + 本节的 5 次').replace('#kernel;', '')
    out.append(s)
open(f'{D}/out/w60.txt', 'w').write('\n'.join(out) + '\n')
print(len(out), 'sections')
