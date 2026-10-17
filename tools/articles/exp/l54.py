import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l54')
def mk():
    d = lab('l54'); ci(d, 'R 起点', {'f': '1\n', 'g': '1\n'}, t=0)
    run(d, 'git checkout -q -b x'); ci(d, 'X1 改 f 为 2', {'f': '2\n'}, t=1); ci(d, 'X2 改 gx', {'gx': 'x\n'}, t=2)
    run(d, 'git checkout -q main'); run(d, 'git checkout -q -b y'); ci(d, 'Y1 也把 f 改成 2', {'f': '2\n'}, t=3); ci(d, 'Y2 改 hy', {'hy': 'y\n'}, t=4)
    run(d, 'git checkout -q main'); ci(d, 'M1 改 g', {'g': 'm\n'}, t=5)
    run(d, 'git merge -q --no-edit -m "合并 x" x', t=6); run(d, 'git merge -q --no-edit -m "合并 y" y', t=7)
    ci(d, 'M2 改 f 为 3', {'f': '3\n'}, t=8); run(d, 'git tag v1', t=8); ci(d, 'M3 改 hy', {'hy': 'z\n'}, t=9); return d
G = "sed -E 's/^([*|\\\\/ ]+)[0-9a-f]{7} /\\1/'"
d = mk()
print('== 一:历史的形状(--graph):X、Y 两个分支各自把 f 改成 2,先后合并进 main')
sh(d, f"git log --graph --format='%s' | sed -E 's/^/  /'")
print('== 二:git log -- f 的默认行为:历史简化。合并提交如果和某一个 parent 在 f 上完全一样,就只沿着那个 parent 往下走')
sh(d, "git log --format='%s' -- f")
print('  (X1 和 Y1 都把 f 改成了 2,但默认只显示 X1:合并 y 的提交的 f 与它的两个 parent 都一样,git 只沿第一个 parent 走,Y 那条分支被整条丢掉了。)')
print('== 三:--full-history 不简化合并;--simplify-merges 在 full-history 的基础上去掉多余的合并;--sparse 连不相关的提交也留下')
for opt in ['', '--full-history', '--full-history --simplify-merges', '--full-history --sparse']:
    o = out1(d, f"git log {opt} --format=%s -- f").split('\n'); print(f'  git log {opt:<34} -- f  ({len(o):>2} 个): ' + ' | '.join(o))
print('== 四:同样的选项加上 --graph,能看到被丢弃的分支')
sh(d, f"git log --graph --full-history --format='%s' -- f | sed -E 's/^/  /'")
print('== 五:--first-parent 只沿第一个 parent;--ancestry-path 只要“A 的后代并且是 B 的祖先”;--simplify-by-decoration 只留带 ref 的提交')
sh(d, "echo '--first-parent:'; git log --first-parent --format='%s' | tr '\\n' '|'; echo; echo '--ancestry-path R..main:'; git log --ancestry-path --format='%s' $(git rev-list --max-parents=0 HEAD)..main | tr '\\n' '|'; echo; echo '--ancestry-path X1..main:'; git log --ancestry-path --format='%s' $(git rev-parse x~1)..main | tr '\\n' '|'; echo; echo '--simplify-by-decoration:'; git log --simplify-by-decoration --format='%s (%D)' | sed -E 's/HEAD -> //' | tr '\\n' '|'; echo")
print('== 六:--graph 的 ASCII 画法:* 是提交,| 是还在延续的线,\\ 与 / 是线的分合,*-. 是章鱼合并')
d2 = lab('l54b'); ci(d2, 'base', {'a': '0\n'}, t=0)
for b in 'pqr':
    run(d2, f'git checkout -q -b {b} main'); ci(d2, f'{b}1', {b: '1\n'}, t=1)
run(d2, 'git checkout -q main'); run(d2, 'git merge -q --no-edit -m "章鱼合并 p q r" p q r', t=9)
sh(d2, "git log --graph --format='%s' | sed -E 's/^/  /'")
