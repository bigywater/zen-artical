import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l45')
import ll as _ll
def run(d, cmd, t='now', **k): return _ll.run(d, cmd, t, **k)
def sh(d, cmd, t='now', **k): return _ll.sh(d, cmd, t, **k)
def ci(d, msg, files=None, t='now', **k): return _ll.ci(d, msg, files, t, **k)
NAMES = {}
def nm(h, label=None):
    if h not in NAMES: NAMES[h] = label or f'#{len(NAMES) + 1}'
    return NAMES[h]
def mk(name):
    d = lab(name); ci(d, 'M1', {'a': '1\n'}, t=0)
    run(d, 'git checkout -q -b feature', 1); ci(d, 'F1', {'f1': '1\n'}, t=1); ci(d, 'F2', {'f2': '1\n'}, t=2); ci(d, 'F3', {'f3': '1\n'}, t=3)
    run(d, 'git checkout -q main', 4); ci(d, 'M2', {'m2': '1\n'}, t=4); ci(d, 'M3', {'m3': '1\n'}, t=5); return d
print('== 一:rebase 之后:3 个提交变成 3 个新的提交(新 hash),作者保留,提交者变成执行 rebase 的人')
d = mk('l45a'); old = out1(d, 'git rev-list --reverse main..feature').split()
for i, h in enumerate(old, 1): nm(h, f'旧F{i}')
sh(d, "git log --format='%s  author=%an  committer=%cn' main..feature", t=10)
run(d, 'git checkout -q feature'); run(d, 'git rebase main', t=20, who='Bob')
new = out1(d, 'git rev-list --reverse main..feature').split()
for i, h in enumerate(new, 1): nm(h, f'新F{i}')
sh(d, "git log --graph --format='%s  author=%an  committer=%cn' main..feature; git log --oneline -1 main | sed -E 's/^[0-9a-f]+ /main 的末端: /'", t=20)
print('  旧提交与新提交对应(同样的改动,不同的 parent,所以 hash 不同):')
for i in range(3):
    print(f'    {nm(old[i])} → {nm(new[i])}   tree 相同? {out1(d, f"git rev-parse {old[i]}^{{tree}}") == out1(d, f"git rev-parse {new[i]}^{{tree}}")}  parent: {nm(out1(d, f"git rev-parse {old[i]}^")) if out1(d, f"git rev-parse {old[i]}^") in NAMES else "M1"} → {nm(out1(d, f"git rev-parse {new[i]}^")) if out1(d, f"git rev-parse {new[i]}^") in NAMES else "M3"}')
print('  新提交的 tree 都和旧的不同,因为每个新提交都建立在 M3 之上,tree 里多了 m2、m3(以第 1 个为例):')
print('   旧F1 的文件:', out1(d, f'git ls-tree --name-only {old[0]}').replace('\n', ' '), '| 新F1 的文件:', out1(d, f'git ls-tree --name-only {new[0]}').replace('\n', ' '))
print('== 二:旧提交没有消失:ORIG_HEAD 指着旧的末端;reflog 里有每一步')
print(f'  ORIG_HEAD 指向旧F3: {out1(d, "git rev-parse ORIG_HEAD") == old[2]};有多少个分支包含旧F3: {out1(d, f"git branch --contains {old[2]} | wc -l").strip()}')
sh(d, "git reflog -8 --format='%gd: %gs'", t=20)
sh(d, "git range-diff main ORIG_HEAD feature", t=20)
print('== 三:rebase 过程中停下来:.git/rebase-merge/ 里记录了状态(冲突时)')
d = mk('l45b'); ci(d, 'M4 改了 f2', {'f2': 'main 里也有 f2\n'}, t=6); run(d, 'git checkout -q feature')
sh(d, 'git rebase main 2>&1 | head -3; ls .git/rebase-merge | tr "\\n" " "; echo')
sh(d, 'cd .git/rebase-merge; for f in head-name onto orig-head msgnum end; do printf "%-10s" $f; cat $f | sed -E "s/[0-9a-f]{40}/<sha40>/"; done; echo "--- git-rebase-todo:"; cat git-rebase-todo | sed -E "s/^(pick|p) [0-9a-f]+/\\1 <sha>/"; echo "--- done:"; cat done | sed -E "s/^(pick|p) [0-9a-f]+/\\1 <sha>/"')
sh(d, 'git status | sed -n 1,4p')
run(d, 'echo 解决 > f2; git add f2'); sh(d, 'GIT_EDITOR=true git rebase --continue 2>&1 | tail -1')
print(f'  完成后 .git/rebase-merge 还存在吗: {(d / ".git" / "rebase-merge").exists()}')
print('== 四:对上游已经有的补丁,rebase 会丢弃重复(靠 patch-id)')
d = lab('l45c'); ci(d, 'M1', {'a': '1\n'}, t=0); run(d, 'git checkout -q -b feature'); ci(d, 'F1', {'f1': '1\n'}, t=1); f2 = ci(d, 'F2 (同样的补丁会被上游拿走)', {'f2': '1\n'}, t=2); run(d, 'git checkout -q main')
ci(d, 'M2', {'m2': '1\n'}, t=3); run(d, f'git cherry-pick -x {f2} >/dev/null', t=4); ci(d, 'M3', {'m3': '1\n'}, t=5)
run(d, 'git checkout -q feature')
sh(d, 'git rebase main 2>&1 | sed -E "s/[0-9a-f]{7,}/<sha>/g"; git log --format=%s main..feature')
sh(d, 'git cherry -v main feature | sed -E "s/[0-9a-f]{40}/<sha40>/"')
print('== 五:快进的情况:feature 已经包含 main,rebase 什么也不用重放')
d = lab('l45d'); ci(d, 'M1', {'a': '1\n'}, t=0); run(d, 'git checkout -q -b feature'); ci(d, 'F1', {'f1': '1\n'}, t=1)
sh(d, 'git rebase main 2>&1 | head -2')
