import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l74')
import ll as _ll
def run(d, cmd, t=0, **k): return _ll.run(d, cmd, t, **k)
def bench(d, cmd, n=5):
    ts = []
    for _ in range(n):
        t0 = time.perf_counter(); run(d, cmd); ts.append((time.perf_counter() - t0) * 1000)
    return median(ts)
def fmt(ms_): return f'{ms_:.0f} ms' if ms_ >= 10 else f'{ms_:.1f} ms'
R = {}   # 汇总用:R[(维度, 操作)] = [各规模的耗时]
def table(title, sizes, ops, d_of, unit_label, n_of=lambda s: 5, key=None):
    print(f'  {"":<34}' + ''.join(f'{unit_label(s):>12}' for s in sizes))
    for nm, cmd in ops:
        row = []
        for s in sizes: row.append(bench(d_of(s), cmd, n_of(s)))
        if key: R[(key, nm)] = row
        print(f'  {nm:<34}' + ''.join(f'{fmt(x):>12}' for x in row))

# ---------- 一:提交数增长(工作区只有 1 个文件,树大小不变)
CS = [1000, 10000, 40000]
print('== 一:提交数从 1,000 增到 40,000(每个提交只改同一个文件,工作区始终 1 个文件):各命令的耗时(5 次中位数,最大的 3 次)')
dc = {}
for n in CS:
    d = lab(f'l74c{n}'); fast_import(d, n); run(d, 'git checkout -q -f main'); run(d, 'git status -s'); dc[n] = d
table('', CS, [('git status', 'git status'), ('git log -1', 'git log -1 --format=%h'), ('git rev-list --count HEAD', 'git rev-list --count HEAD'), ('git log --oneline(全部)', 'git log --oneline | wc -l'), ('git log --stat -n 100', 'git log --stat -n 100 | wc -l')], lambda s: dc[s], lambda s: f'{s:,} 提交', lambda s: 3 if s == 40000 else 5, key='提交')
CO = "git count-objects -v | grep -E '^(count|in-pack)' | tr '\\n' ' '"
for n in CS: print(f'  {n:,} 提交:对象 {out1(dc[n], CO)} .git 目录 {out1(dc[n], "du -sk .git | cut -f1")} KB')

# ---------- 二:文件数增长
FS = [1000, 10000, 50000]
print('== 二:工作区文件数从 1,000 增到 50,000(只有 1 个提交,所有文件都已跟踪):各命令的耗时(5 次中位数,最大的 3 次)')
df = {}
for n in FS:
    d = lab(f'l74f{n}'); W(d, {f'd{i % 100:02d}/f{i}.txt': f'文件 {i}\n' for i in range(n)}); ci(d, 'x', t=0, add='-A'); run(d, 'git status -s'); df[n] = d
table('', FS, [('git status', 'git status'), ('git status -uno', 'git status -uno'), ('git add -A(没有改动)', 'git add -A'), ('git ls-files | wc -l', 'git ls-files | wc -l'), ('git diff --stat HEAD', 'git diff --stat HEAD | tail -1'), ('git commit --allow-empty', 'git commit -q --allow-empty -m e')], lambda s: df[s], lambda s: f'{s:,} 文件', lambda s: 3 if s == 50000 else 5, key='文件')
for n in FS: print(f'  {n:,} 文件:.git/index {int(out1(df[n], "stat -f %z .git/index")):,} 字节(每个文件约 {int(out1(df[n], "stat -f %z .git/index")) / n:.0f} 字节)')

# ---------- 三:对象数增长,树随提交增长
print('== 三:每个提交新增一个文件(树随提交增长):打包存储与松散存储,对象数、磁盘和遍历耗时')
dg = {}
for n in CS:
    d = lab(f'l74g{n}'); fast_import(d, n, fname=lambda i: f'd{i % 50:02d}/f{i}.txt'); run(d, 'git checkout -q -f main'); dg[n] = d
# 松散副本(只做前两档)
dl = {}
for n in CS[:2]:
    d = lab(f'l74l{n}'); run(d, 'git remote add o ' + str(dg[n]))
    packs = list((dg[n] / '.git' / 'objects' / 'pack').glob('*.pack')); assert len(packs) == 1
    r = subprocess.run([GIT, 'unpack-objects', '-q'], cwd=d, env=lenv(), input=packs[0].read_bytes(), capture_output=True); assert r.returncode == 0, r.stderr
    run(d, f'git --git-dir={dg[n]}/.git for-each-ref --format="%(objectname) %(refname)" | while read h r; do git update-ref $r $h; done'); dl[n] = d
print(f'  {"":<34}' + ''.join(f'{n:>12,}' for n in CS) + '   (提交数)')
FINDL = "find .git/objects -type f -path '*/??/*' | wc -l"
def objn(d): return int(out1(d, 'git cat-file --batch-all-objects --batch-check | wc -l'))
print(f'  {"对象总数":<34}' + ''.join(f'{objn(dg[n]):>12,}' for n in CS))
print(f'  {"打包:.git 目录 KB":<34}' + ''.join(f'{int(out1(dg[n], "du -sk .git | cut -f1")):>12,}' for n in CS))
print(f'  {"松散:.git 目录 KB":<34}' + ''.join(f'{int(out1(dl[n], "du -sk .git | cut -f1")):>12,}' for n in CS[:2]) + f'{"(未测)":>12}')
print(f'  {"松散:对象文件数":<34}' + ''.join(f'{int(out1(dl[n], FINDL)):>12,}' for n in CS[:2]) + f'{"(未测)":>12}')
for nm, cmd in [('rev-list --objects --all', 'git rev-list --objects --all | wc -l'), ('cat-file --batch-all-objects', 'git cat-file --batch-all-objects --batch-check | wc -l')]:
    rp = [bench(dg[n], cmd, 3) for n in CS]; rl = [bench(dl[n], cmd, 3) for n in CS[:2]]
    R[('对象', nm + '(打包)')] = rp
    print(f'  {nm + "(打包)":<34}' + ''.join(f'{fmt(x):>12}' for x in rp))
    print(f'  {nm + "(松散)":<34}' + ''.join(f'{fmt(x):>12}' for x in rl) + f'{"(未测)":>12}')
print(f'  {"git status(打包)":<34}' + ''.join(f'{fmt(bench(dg[n], "git status", 3)):>12}' for n in CS))
print(f'  (这一组里工作区文件数也随提交增长到 {int(out1(dg[40000], "git ls-files | wc -l")):,} 个,所以 status 的增长来自工作区而不是历史)')

CGSZ = 'du -ck .git/objects/info/commit-graph* .git/objects/info/commit-graphs 2>/dev/null | tail -1 | cut -f1'
# ---------- 四:带路径的 log
print('== 四:git log -- <目录>:每个提交都要比较树;commit-graph --changed-paths 的 Bloom filter 可以跳过不相关的提交')
CMD = 'git log --oneline -- d07/ | wc -l'
no = [bench(dg[n], CMD, 3) for n in CS]
print(f'  {"":<34}' + ''.join(f'{n:>12,}' for n in CS) + '   (提交数)')
print(f'  {"没有 commit-graph":<34}' + ''.join(f'{fmt(x):>12}' for x in no))
for n in CS: run(dg[n], 'git commit-graph write --reachable')
cg = [bench(dg[n], CMD, 3) for n in CS]
print(f'  {"有 commit-graph(无 Bloom)":<34}' + ''.join(f'{fmt(x):>12}' for x in cg))
for n in CS: run(dg[n], 'git commit-graph write --reachable --changed-paths')
bl = [bench(dg[n], CMD, 3) for n in CS]
print(f'  {"commit-graph + --changed-paths":<34}' + ''.join(f'{fmt(x):>12}' for x in bl))
print(f'  {"结果行数(三种相同)":<34}' + ''.join(f'{out1(dg[n], CMD):>12}' for n in CS))
R[('提交', 'log -- 目录(无 graph)')] = no; R[('提交', 'log -- 目录(Bloom)')] = bl
print(f'  {"commit-graph 文件大小":<34}' + ''.join(f'{int(out1(dg[n], CGSZ)):>9,} KB' for n in CS))

# ---------- 五:克隆
print('== 五:git clone(file:// 协议,走 upload-pack)的耗时:完整克隆、--depth 1、--filter=blob:none(3 次中位数)')
for n in CS: run(dg[n], 'git config uploadpack.allowFilter true; git config uploadpack.allowAnySHA1InWant true')
print(f'  {"":<34}' + ''.join(f'{n:>12,}' for n in CS) + '   (提交数)')
def clone_bench(n, opts):
    ts = []
    for _ in range(3):
        c = LT / 'l74clone'; shutil.rmtree(c, ignore_errors=True)
        t0 = time.perf_counter(); r = subprocess.run([GIT, 'clone', '-q', '--no-local', *opts.split(), f'file://{dg[n]}/.git', str(c)], env=lenv(), capture_output=True); ts.append((time.perf_counter() - t0) * 1000); assert r.returncode == 0, r.stderr
    sz = int(out1(LT, f'du -sk {c}/.git | cut -f1'))
    return median(ts), sz
for nm, opts in [('完整克隆', ''), ('--depth 1', '--depth 1'), ('--filter=blob:none', '--filter=blob:none')]:
    res = [clone_bench(n, opts) for n in CS]
    R[('克隆', nm)] = [x[0] for x in res]
    print(f'  {nm:<34}' + ''.join(f'{fmt(x[0]):>12}' for x in res))
    print(f'  {"  .git 大小":<34}' + ''.join(f'{x[1]:>9,} KB' for x in res))

# ---------- 六:增长倍数
print('== 六:规模增长 40 倍(提交 1,000 → 40,000)或 50 倍(文件 1,000 → 50,000)时,耗时增长了多少倍')
for (dim, nm), row in R.items():
    if dim in ('提交', '克隆', '对象'): base = f'{row[-1] / row[0]:>7.1f} 倍   (规模 ×40)'
    else: base = f'{row[-1] / row[0]:>7.1f} 倍   (规模 ×50)'
    print(f'  {nm:<34}{fmt(row[0]):>10} → {fmt(row[-1]):>10}   {base}')
