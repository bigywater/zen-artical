import sys, os, re, random; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l73')
import ll as _ll
def run(d, cmd, t=0, **k): return _ll.run(d, cmd, t, **k)
def sh(d, cmd, t=0, **k): return _ll.sh(d, cmd, t, **k)
def ci(d, msg, files=None, t=0, **k): return _ll.ci(d, msg, files, t, **k)
rnd = random.Random(73)
def st(d):
    loose = int(out1(d, "find .git/objects -type f -path '*/??/*' | wc -l")); packs = len(list((d / '.git' / 'objects' / 'pack').glob('*.pack')))
    cg = (d / '.git' / 'objects' / 'info' / 'commit-graph').exists() or (d / '.git' / 'objects' / 'info' / 'commit-graphs').exists()
    midx = (d / '.git' / 'objects' / 'pack' / 'multi-pack-index').exists()
    lrefs = int(out1(d, "find .git/refs -type f | wc -l")); pr = (d / '.git' / 'packed-refs').exists()
    prefetch = int(out1(d, "git for-each-ref refs/prefetch | wc -l"))
    return dict(松散对象=loose, pack数=packs, 提交图=cg, midx=midx, 松散ref=lrefs, packed_refs=pr, prefetch引用=prefetch)
def prep(name):
    d = lab(name); [ci(d, f'提交 {i}', {f'g{i % 5}/f{j}.txt': f'{i}-{j}\n' for j in range(80)}, t=i) for i in range(1, 9)]
    run(d, 'git branch b1; git branch b2; git tag t1')
    # 制造几个 pack:对最近几个提交逐个 repack(不合并旧 pack)
    return d
print('== 一:这台 git(2.54.0)认识哪些 maintenance 任务:对每个名字执行 git maintenance run --task=<名>')
d = prep('l73a'); names = ['gc', 'commit-graph', 'prefetch', 'loose-objects', 'incremental-repack', 'pack-refs', 'reflog-expire', 'rerere-gc', 'worktree-prune', 'geometric-repack', 'bogus']
ok = []
for n in names:
    rc, o = run(d, f'git maintenance run --task={n} 2>&1 | head -2'); good = 'not a valid task' not in o and 'unknown' not in o
    if n != 'bogus' or not good: pass
    print(f'  {n:<20}→ ' + ('可用' if good else o.replace(chr(10), ' ')[:70])); 
print('== 二:每个任务单独运行,看它改变了仓库的什么(松散对象/pack/提交图/midx/ref)')
print(f'  {"任务":<20}' + ' '.join(f'{k:<8}' for k in ['松散对象', 'pack数', '提交图', 'midx', '松散ref', 'packed_refs']))
def row(name, s): print(f'  {name:<20}' + ' '.join(f'{str(v):<8}' for k, v in s.items() if k != 'prefetch引用'))
base = prep('l73b'); row('(起点)', st(base))
for t_ in ['loose-objects', 'commit-graph', 'pack-refs', 'incremental-repack', 'geometric-repack', 'gc']:
    dd = LT / 'l73t'; shutil.rmtree(dd, ignore_errors=True); shutil.copytree(base, dd, symlinks=True)
    run(dd, f'git maintenance run --task={t_}'); row(t_, st(dd))
    if t_ == 'loose-objects': run(dd, 'git maintenance run --task=loose-objects'); row('loose-objects(第 2 次)', st(dd))
print('== 三:prefetch:把远程的新分支预先下载到 refs/prefetch/<远程>/ 下,不动 refs/remotes,也不改变本地分支')
R = LT / 'l73remote.git'; shutil.rmtree(R, ignore_errors=True); run(base, f'git clone -q --bare . {R}')
c = LT / 'l73c'; shutil.rmtree(c, ignore_errors=True); run(LT, f'git clone -q {R} l73c')
run(base, 'git checkout -q -b newwork'); ci(base, '远程上新增的分支提交', {'x': '1\n'}, t=50); run(base, f'git push -q {R} newwork')
sh(c, 'git for-each-ref --format="%(refname)" refs/remotes refs/prefetch | tr "\\n" " "; echo "(prefetch 之前)"')
run(c, 'git maintenance run --task=prefetch')
sh(c, 'git for-each-ref --format="%(refname)" refs/remotes refs/prefetch | tr "\\n" " "; echo "(prefetch 之后)"')
sh(c, 'git fetch -q; git for-each-ref --format="%(refname)" refs/remotes refs/prefetch | tr "\\n" " "; echo "(之后真的 git fetch 的结果:refs/remotes 更新;refs/prefetch 在下次 prefetch 时会被清理)"')
print('== 四:不带 --task 时运行哪些任务由 maintenance.strategy 决定:对四种取值记录 git 实际启动的子命令')
d4 = lab('l73d'); ci(d4, 'x', {'a': '1\n'}, t=0)
def subcmds(opt):
    rc, o = run(d4, f"GIT_TRACE=1 bash -c 'git {opt} maintenance run' 2>&1 | grep 'trace: run_command' | sed -E 's/.*run_command: //' | grep -v 'git pack-objects' | cut -c1-70")
    return o.split('\n')
for strat, opt in [('(不设置)', ''), ('gc', '-c maintenance.strategy=gc'), ('geometric', '-c maintenance.strategy=geometric'), ('incremental', '-c maintenance.strategy=incremental')]:
    print(f'  strategy {strat}:' + ('' if strat != '(不设置)' else '  (手动 git maintenance run 的默认)'))
    for l in subcmds(opt): print('    ' + l)
rc, o = run(d4, 'git -c maintenance.strategy=bogus maintenance run 2>&1 | head -1'); print('  strategy bogus:  ' + o)
print('== 五:--auto 的阈值:commit-graph.auto(默认 100 个不在提交图里的可达提交)、loose-objects.auto(默认 100,数全仓库的松散对象)')
for n in (99, 100):
    d5 = lab('l73e'); fast_import(d5, n); run(d5, 'git checkout -q main')
    run(d5, 'git maintenance run --auto --task=commit-graph'); has = (d5 / '.git' / 'objects' / 'info' / 'commit-graphs').exists()
    print(f'  {n} 个提交没有提交图 → git maintenance run --auto --task=commit-graph: ' + ('写了提交图' if has else '什么也没做'))
for n_, lim in ((99, ''), (100, ''), (9, '-c maintenance.loose-objects.auto=10'), (10, '-c maintenance.loose-objects.auto=10')):
    d6 = lab('l73f')
    for i in range(n_): run(d6, 'git hash-object -w --stdin', stdin=f'r{i}\n')
    tot = int(out1(d6, "find .git/objects -type f -path '*/??/*' | wc -l"))
    run(d6, f'git {lim} maintenance run --auto --task=loose-objects'); np1 = len(list((d6 / '.git' / 'objects' / 'pack').glob('*.pack')))
    print(f'  全仓库 {tot} 个松散对象({"loose-objects.auto=10" if lim else "默认阈值 100"})→ git maintenance run --auto --task=loose-objects: ' + ('打包了' if np1 else '什么也没做'))
print('== 六:配置:每个任务的开关与间隔')
sh(d4, 'git config --get-regexp "^maintenance" || echo "(没有 maintenance 配置)"')
run(d4, 'git config maintenance.commit-graph.enabled true; git config maintenance.loose-objects.enabled true; git config maintenance.commit-graph.schedule daily')
sh(d4, 'git config --get-regexp "^maintenance" | sort')
sh(d4, "GIT_TRACE=1 git maintenance run 2>&1 | grep 'trace: run_command' | sed -E 's/.*run_command: //' | grep -v 'git pack-objects' | cut -c1-70")
