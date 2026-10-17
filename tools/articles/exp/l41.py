import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l41')
BASE = ''.join(f'第 {i} 行\n' for i in range(1, 11))
def L(s, ch):
    X = s.split('\n')
    for k, v in ch.items(): X[k - 1] = v
    return '\n'.join(X)
def scenario(name, base_files, ours, theirs):
    d = lab(name); ci(d, '基础', base_files, t=0); run(d, 'git checkout -q -b theirs')
    W(d, theirs); run(d, 'git add -A; git rm -q --cached --ignore-unmatch -r . >/dev/null 2>&1; git add -A; git commit -q -m theirs改动', 1) if False else None
    return d
def mk(name, base, ours, theirs, delete_ours=(), delete_theirs=(), rename_theirs=None):
    d = lab(name); ci(d, '基础', base, t=0); run(d, 'git checkout -q -b theirs')
    W(d, theirs)
    for f in delete_theirs: run(d, f'git rm -q {f}')
    if rename_theirs: run(d, f'git mv {rename_theirs[0]} {rename_theirs[1]}')
    run(d, 'git add -A; git commit -q -m theirs改动', 1); run(d, 'git checkout -q main')
    W(d, ours)
    for f in delete_ours: run(d, f'git rm -q {f}')
    run(d, 'git add -A; git commit -q -m ours改动', 2); return d
print('== 一:两边改了同一个文件的不同位置:干净合并;结果与 git merge-file(三方合并的底层命令)一致')
d = mk('l41a', {'f.txt': BASE}, {'f.txt': L(BASE, {2: '第 2 行 ours 改'})}, {'f.txt': L(BASE, {8: '第 8 行 theirs 改'})})
sh(d, 'git merge theirs 2>&1 | head -3; git diff HEAD~1 --stat | tail -1')
ours = d / 'o.txt'; basef = d / 'b.txt'; th = d / 't.txt'
ours.write_text(L(BASE, {2: '第 2 行 ours 改'})); basef.write_text(BASE); th.write_text(L(BASE, {8: '第 8 行 theirs 改'}))
mf = subprocess.run([GIT, 'merge-file', '-p', str(ours), str(basef), str(th)], capture_output=True, text=True, env=lenv()).stdout
print(f'  git merge-file -p ours base theirs 的输出与合并结果一致: {mf == (d / "f.txt").read_text()}')
print('== 二:改同一处:冲突。工作区里是冲突标记,index 里是三个阶段(stage 1 基础、2 ours、3 theirs)')
d = mk('l41b', {'f.txt': BASE}, {'f.txt': L(BASE, {5: '第 5 行 ours 改'})}, {'f.txt': L(BASE, {5: '第 5 行 theirs 改'})})
sh(d, 'git merge theirs 2>&1 | head -3; git status --short; sed -n 4,8p f.txt')
sh(d, "git ls-files -u | sed -E 's/^([0-9]+) [0-9a-f]{40} ([123])/\\1 <sha> stage\\2/'")
sh(d, 'for s in 1 2 3; do printf "stage $s: "; git show :$s:f.txt | sed -n 5p; done')
sh(d, 'cat .git/MERGE_HEAD | cut -c1-7; cat .git/MERGE_MSG | head -3; ls .git | grep -E "^MERGE_"')
print('== 三:边界:两边做了完全相同的改动 → 不冲突;两个改动相邻(只隔 0 行)→ 冲突,隔一行 → 不冲突')
d = mk('l41c', {'f.txt': BASE}, {'f.txt': L(BASE, {5: '第 5 行 一样的改'})}, {'f.txt': L(BASE, {5: '第 5 行 一样的改'})})
sh(d, 'git merge theirs 2>&1 | head -2')
d = mk('l41d', {'f.txt': BASE}, {'f.txt': L(BASE, {5: '第 5 行 ours'})}, {'f.txt': L(BASE, {6: '第 6 行 theirs'})})
sh(d, 'git merge theirs 2>&1 | head -2')
d = mk('l41e', {'f.txt': BASE}, {'f.txt': L(BASE, {5: '第 5 行 ours'})}, {'f.txt': L(BASE, {7: '第 7 行 theirs'})})
sh(d, 'git merge theirs 2>&1 | head -2')
print('== 四:文件级冲突:一边删除一边修改、两边各自新增同名文件')
d = mk('l41f', {'f.txt': BASE, 'g.txt': 'g\n'}, {'f.txt': L(BASE, {5: '第 5 行 ours 改'})}, {'g.txt': 'g\n'}, delete_theirs=['f.txt'])
sh(d, 'git merge theirs 2>&1 | head -3; git status --short')
d = mk('l41g', {'a.txt': 'a\n'}, {'new.txt': 'ours 新增的 new\n'}, {'new.txt': 'theirs 新增的 new\n'})
sh(d, 'git merge theirs 2>&1 | head -3; git status --short; cat new.txt')
print('== 五:一边改名、一边修改内容:ort 跟着改名走,修改应用到新名字上')
d = mk('l41h', {'old.txt': BASE}, {'old.txt': L(BASE, {5: '第 5 行 ours 改'})}, {}, rename_theirs=('old.txt', 'renamed.txt'))
sh(d, 'git merge theirs 2>&1 | head -4; ls; sed -n 5p renamed.txt')
print('== 六:-X ours/-X theirs 只在冲突的块上选边;-s ours 则整个忽略对方')
for nm, opt in [('-X ours', '-X ours'), ('-X theirs', '-X theirs'), ('-s ours', '-s ours')]:
    d = mk('l41i', {'f.txt': BASE, 'x.txt': 'x\n'}, {'f.txt': L(BASE, {5: '第 5 行 ours 改', 2: '第 2 行 ours 改'})}, {'f.txt': L(BASE, {5: '第 5 行 theirs 改', 9: '第 9 行 theirs 改'}), 'x.txt': 'x theirs 改\n'})
    run(d, f'git merge {opt} theirs 2>&1')
    print(f'  git merge {nm}:第 2 行={out1(d, "sed -n 2p f.txt")!r:<22} 第 5 行={out1(d, "sed -n 5p f.txt")!r:<22} 第 9 行={out1(d, "sed -n 9p f.txt")!r:<22} x.txt={out1(d, "cat x.txt")!r}')
print('  (-X 只在冲突块选边,不冲突的块两边都收;-s ours 不收对方的任何改动,但仍产生一个有两个 parent 的合并提交)')
sh(d, 'git cat-file -p HEAD | grep -c "^parent"')
print('== 七:取消合并')
d = mk('l41j', {'f.txt': BASE}, {'f.txt': L(BASE, {5: '第 5 行 ours 改'})}, {'f.txt': L(BASE, {5: '第 5 行 theirs 改'})})
run(d, 'git merge theirs'); sh(d, 'git merge --abort; git status --short; ls .git | grep -E "^MERGE_" || echo "(MERGE_HEAD 等文件都没了)"; sed -n 5p f.txt')
