import sys, os, hashlib; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l20')
DEF = HOME / '.gitconfig_def'; DEF.write_text('[init]\n\tdefaultBranch = main\n')   # 不含 gc.auto / maintenance.auto 的全局配置:用 git 的默认值
E0 = {'GIT_CONFIG_GLOBAL': str(DEF)}
def mk(name):
    d = lab(name); ci(d, 'x', {'a': '1\n'}, t=0); return d
def write_loose(d, contents):
    fs = []
    for i, c in enumerate(contents):
        p = LT / '_objs' / f'{d.name}_{i}'; p.parent.mkdir(exist_ok=True); p.write_bytes(c); fs.append(str(p))
    run(d, 'git hash-object -w --stdin-paths', stdin='\n'.join(fs) + '\n', env=E0)
    shutil.rmtree(LT / '_objs', ignore_errors=True)
def with_prefix(n, prefix='17'):
    out = []; i = 0
    while len(out) < n:
        c = f'blob-{i}\n'.encode(); h = hashlib.sha1(b'blob %d\0' % len(c) + c).hexdigest(); i += 1
        if h.startswith(prefix): out.append(c)
    return out
def n17(d): return int(out1(d, 'ls .git/objects/17 2>/dev/null | wc -l'))
def auto(d, extra=''): return run(d, f'git -c gc.autoDetach=false {extra} gc --auto 2>&1', env=E0)[1]
print('== 一:默认配置下的规则:git gc --auto 只数 objects/17 这一个目录,和 (gc.auto + 255) / 256 比较')
d = mk('l20a')
sh(d, 'git config --get gc.auto || echo "gc.auto 未设置(git 默认 6700)"', env=E0)
print(f'  (6700 + 255) // 256 = {(6700 + 255) // 256}:objects/17 里松散对象超过 27 个才触发')
print('== 二:往 objects/17 里放 26、27、28 个(不可达的)松散对象,每次执行 git gc --auto')
cs = with_prefix(28)
for k in (26, 27, 28):
    write_loose(d, cs[:k]); o = auto(d)
    print(f'  objects/17 里 {n17(d)} 个 → git gc --auto 输出:', o.replace('\n', ' / ') if o else '(没有输出,什么也没做)')
print('== 三:随机分布的松散对象:放多少个才触发(每行一个新仓库,objects/17 的个数是随机的)')
print(f'  {"松散对象总数":>10}  {"objects/17 个数":>14}  {"触发 gc --auto"}')
for N in [5000, 6000, 6500, 6700, 7000, 7500, 8000]:
    dd = mk(f'l20n{N}'); write_loose(dd, [f'随机 {N}-{i}\n'.encode() for i in range(N)]); k = n17(dd); o = auto(dd)
    print(f'  {N:>10,}  {k:>14}  {"是" if "Auto packing" in o else "否"}')
    shutil.rmtree(dd, ignore_errors=True)
print('== 四:触发之后:不可达的松散对象还在,所以下一次 gc --auto 仍然触发(这里是同步运行,每次都完整地重新跑一遍)')
d = LT / 'l20a'
print(f'  第一次触发之后 objects/17 里还有 {n17(d)} 个松散对象')
for i in (1, 2):
    print(f'  第 {i} 次再执行 git gc --auto:'); print('   ', (auto(d) or '(没有输出)').replace('\n', '\n    '))
print(f'  两次之后 objects/17 里仍有 {n17(d)} 个')
print('== 五:另一个触发条件:pack 数超过 gc.autoPackLimit(默认 50)')
d = mk('l20p')
def add_pack(k):
    W(d, {f'p{k}.txt': f'{k}\n'}); ci(d, f'p{k}', t=k); run(d, 'git repack -dq', env=E0)
for k in range(1, 51): add_pack(k)
npk = lambda: int(out1(d, 'ls .git/objects/pack/*.pack | wc -l'))
print(f'  现在有 {npk()} 个 pack'); o = auto(d); print(f'  git gc --auto → {o.replace(chr(10), " / ") if o else "(没有输出)"};pack 数 {npk()}')
add_pack(51); print(f'  再多一个:{npk()} 个 pack'); o = auto(d); print(f'  git gc --auto → {o.replace(chr(10), " / ") if o else "(没有输出)"};pack 数 {npk()}')
