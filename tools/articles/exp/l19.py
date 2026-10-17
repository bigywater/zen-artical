import sys, os, random; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l19')
rnd = random.Random(19)
def ln(): return ' '.join(''.join(rnd.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(rnd.randint(3, 8))) for _ in range(8))
lines = [ln() for _ in range(300)]
base = lab('l19base')
print('== 一:准备一个“乱七八糟”的仓库:差的 pack、含不可达对象的 pack、松散的新对象、一个不可达的松散 blob')
for v in range(30):
    lines[rnd.randrange(300)] = ln(); W(base, {'a.txt': '\n'.join(lines) + '\n'}); ci(base, f'v{v}', t=v)
run(base, 'git repack -adfq --window=0 --depth=0')
W(base, {'tmp.txt': 'tmp\n'}); run(base, 'git checkout -q -b tmp', 40); X = ci(base, 'tmp 分支上的提交', t=40)
run(base, 'git repack -dq'); run(base, 'git checkout -q main && git branch -q -D tmp && git reflog expire --expire=now --all')
for v in range(2):
    lines[rnd.randrange(300)] = ln(); W(base, {'a.txt': '\n'.join(lines) + '\n'}); ci(base, f'新 {v}', t=50 + v)
UB = out1(base, 'echo 不可达的 blob | git hash-object -w --stdin')
def state(d):
    loose = int(out1(d, "find .git/objects -mindepth 2 -type f -path '*/??/*' | grep -v pack | wc -l"))
    packs = sorted((d / '.git' / 'objects' / 'pack').glob('*.pack')); sz = sum(p.stat().st_size for p in packs)
    cr = len(list((d / '.git' / 'objects' / 'pack').glob('*.mtimes')))
    ex = lambda o: run(d, f'git cat-file -e {o}')[0] == 0
    return dict(loose=loose, packs=len(packs), size=sz, cruft=cr, X=ex(X), UB=ex(UB))
s0 = state(base)
print(f'  松散对象 {s0["loose"]} 个;pack {s0["packs"]} 个(合计 {s0["size"]:,} 字节);不可达的提交 X(在 pack 里)存在: {s0["X"]};不可达的 blob UB(松散)存在: {s0["UB"]}')
sh(base, 'ls .git/objects/pack/*.pack | wc -l; git count-objects -v | grep -E "^(count|in-pack|packs)"')
print('== 二:同一份起点,分别执行不同的 repack 选项,看结果')
print(f'  {"命令":<36}{"松散":>6}{"pack":>6}{"pack 合计字节":>14}{"cruft":>7}  X(pack 里不可达) UB(松散不可达)')
def row(name, st): print(f'  {name:<36}{st["loose"]:>6}{st["packs"]:>6}{st["size"]:>14,}{st["cruft"]:>7}  {"留着" if st["X"] else "没了":<16}{"留着" if st["UB"] else "没了"}')
row('(起点)', s0)
RES = {}
for nm, cmd in [('git repack', 'git repack -q'), ('git repack -d', 'git repack -d -q'), ('git repack -a -d', 'git repack -a -d -q'), ('git repack -A -d', 'git repack -A -d -q'),
                ('git repack -a -d -f', 'git repack -a -d -f -q'), ('git repack -a -d -k', 'git repack -a -d -k -q'), ('git repack -a -d --cruft', 'git repack -a -d --cruft -q')]:
    dd = LT / 'l19v'; shutil.rmtree(dd, ignore_errors=True); shutil.copytree(base, dd, symlinks=True)
    rc, o = run(dd, cmd); st = state(dd); RES[nm] = st; row(nm, st)
    if rc: print('    出错:', o)
print('== 三:-f 的区别:起点的 pack 是用 --window=0 --depth=0 打的(完全没有 delta),比较不加 -f 与加 -f 重新打包后的大小')
print(f'  起点合计 {s0["size"]:,} 字节;-a -d:{RES["git repack -a -d"]["size"]:,};-a -d -f(重算 delta):{RES["git repack -a -d -f"]["size"]:,}')
print('== 四:-A 与 -a 的区别:pack 里的不可达对象 X 会发生什么')
for nm in ['git repack -a -d', 'git repack -A -d', 'git repack -a -d --cruft']:
    st = RES[nm]; print(f'  {nm:<28} X: {"留着" if st["X"] else "没了"}   松散对象 {st["loose"]},cruft 文件 {st["cruft"]}')
print('== 五:cruft pack 的目录结构')
dd = LT / 'l19v'; shutil.rmtree(dd, ignore_errors=True); shutil.copytree(base, dd, symlinks=True); run(dd, 'git repack -a -d --cruft -q')
sh(dd, 'ls -l .git/objects/pack | awk \'NR>1 {print $5, $9}\' | sed -E "s/pack-[0-9a-f]{40}/pack-<hash>/"')
sh(dd, 'git count-objects -v | grep -E "^(count|in-pack|packs)"')
