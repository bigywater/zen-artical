import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l47')
BASE = ''.join(f'第 {i} 行\n' for i in range(1, 21))
def L(s, ch, ins=None):
    X = s.split('\n')
    for k, v in ch.items(): X[k - 1] = v
    return '\n'.join(X)
def mk(name):
    d = lab(name); ci(d, '基础', {'f.txt': BASE}, t=0)
    run(d, 'git checkout -q -b feature', 1); fx = ci(d, '修复:第 10 行', {'f.txt': L(BASE, {10: '第 10 行(已修复)'})}, t=2, who='Alice'); ci(d, '后续提交', {'g.txt': 'g\n'}, t=3)
    run(d, 'git checkout -q main', 4); ci(d, 'main 在文件开头加两行', {'f.txt': '新增行 A\n新增行 B\n' + BASE}, t=5); return d, fx
print('== 一:cherry-pick 把一个提交的改动“再做一遍”:新提交作者不变,提交者与 parent 不同,hash 不同')
d, fx = mk('l47a')
sh(d, f'git cherry-pick -x {fx} 2>&1 | head -2', t=20, who='Bob')
sh(d, "git log -1 --format='%s%n  author=%an committer=%cn%n  parent: %p' | sed -E 's/[0-9a-f]{7}/<sha>/'; git log -1 --format=%b | sed -E 's/[0-9a-f]{40}/<sha40>/'")
print(f'  原提交 parent 是 基础提交,新提交 parent 是 main 的上一个提交;两个提交的 tree 不同(新的带有 main 加的两行): {out1(d, f"git rev-parse {fx}^{{tree}}") != out1(d, "git rev-parse HEAD^{tree}")}')
print('== 二:cherry-pick 就是一次三方合并:基础 = 提交的 parent,ours = 当前 HEAD,theirs = 那个提交。用 git merge-tree 手工做同样的合并,tree 完全一致')
d, fx = mk('l47b'); head_before = out1(d, 'git rev-parse HEAD')
mt = out1(d, f'git merge-tree --write-tree --merge-base={fx}^ {head_before} {fx}').split()[0]
run(d, f'git cherry-pick {fx}', t=20, who='Bob')
print(f'  merge-tree 算出的 tree: {mt[:12]}   cherry-pick 之后 HEAD 的 tree: {out1(d, "git rev-parse HEAD^{tree}")[:12]}   相同: {mt == out1(d, "git rev-parse HEAD^{tree}")}')
print('== 三:patch-id:补丁内容的指纹(忽略行号)。同一个补丁 cherry-pick 到别处,patch-id 不变')
d, fx = mk('l47c'); run(d, f'git cherry-pick {fx}', t=20, who='Bob'); newc = out1(d, 'git rev-parse HEAD')
pid = lambda c: out1(d, f'git show {c} | git patch-id --stable | cut -d" " -f1')
print(f'  原提交的 patch-id  : {pid(fx)}\n  新提交的 patch-id  : {pid(newc)}\n  相同: {pid(fx) == pid(newc)}(hash 不同: {fx != newc};行号不同: 原来改的是第 10 行,新提交里变成第 12 行)')
sh(d, 'git show HEAD | grep "^@@"; git show %s | grep "^@@"' % fx)
print('  对照:补丁里多改一个字,patch-id 就不同;只改空白,默认的 --stable 会忽略空白:')
d2, fx2 = mk('l47d')
W(d2, {'x': 'a b\n'}); 
A = 'diff --git a/f b/f\n--- a/f\n+++ b/f\n@@ -1 +1 @@\n-old\n+new\n'
B = 'diff --git a/f b/f\n--- a/f\n+++ b/f\n@@ -10 +10 @@\n-old\n+new\n'
C = 'diff --git a/f b/f\n--- a/f\n+++ b/f\n@@ -1 +1 @@\n-old\n+new!\n'
Ws = 'diff --git a/f b/f\n--- a/f\n+++ b/f\n@@ -1 +1 @@\n-old\n+new   \n'
def pidtxt(t): return subprocess.run([GIT, 'patch-id', '--stable'], input=t, capture_output=True, text=True, env=lenv()).stdout.split()[0][:12]
print(f'    A(改第 1 行) {pidtxt(A)}  | 同样内容但行号是 10 {pidtxt(B)}  | 多一个感叹号 {pidtxt(C)}  | 行尾多空白 {pidtxt(Ws)}')
print('== 四:git cherry / log --cherry-pick 用 patch-id 判断“上游是否已经有这个补丁”')
d, fx = mk('l47e')
sh(d, 'git cherry -v main feature | sed -E "s/[0-9a-f]{40}/<sha40>/"')
run(d, f'git cherry-pick {fx}', t=20, who='Bob')
sh(d, 'git cherry -v main feature | sed -E "s/[0-9a-f]{40}/<sha40>/"; echo "(- 表示 main 里已经有等价的补丁,+ 表示还没有)"')
sh(d, 'git log --left-right --cherry-pick --oneline main...feature | sed -E "s/[0-9a-f]{7} //"; echo "(--cherry-pick 把互相等价的提交过滤掉了)"')
print('== 五:冲突之后手工解决的结果,patch-id 往往变了,git 就认不出它们是同一个补丁')
d = lab('l47f'); ci(d, '基础', {'f.txt': BASE}, t=0); run(d, 'git checkout -q -b feature', 1); fx = ci(d, '改第 10 行', {'f.txt': L(BASE, {10: '第 10 行(feature)'})}, t=2)
run(d, 'git checkout -q main', 3); ci(d, 'main 也改第 10 行', {'f.txt': L(BASE, {10: '第 10 行(main)'})}, t=4)
sh(d, f'git cherry-pick {fx} 2>&1 | head -2; ls .git | grep CHERRY_PICK_HEAD', t=20, who='Bob')
W(d, {'f.txt': L(BASE, {10: '第 10 行(我手工合并的)'})}); run(d, 'git add f.txt; git -c core.editor=true cherry-pick --continue', t=21, who='Bob')
newc = out1(d, 'git rev-parse HEAD'); print(f'  原提交 patch-id {pid(fx)} ；解决冲突后的提交 patch-id {pid(newc)}；相同: {pid(fx) == pid(newc)}')
sh(d, 'git cherry -v main feature | sed -E "s/[0-9a-f]{40}/<sha40>/"')
print('== 六:补丁已经在当前分支里时,cherry-pick 变成空提交,git 会告诉你')
d, fx = mk('l47g'); run(d, f'git cherry-pick {fx}', t=20, who='Bob')
sh(d, f'git cherry-pick {fx} 2>&1 | head -3', t=21, who='Bob')
run(d, 'git cherry-pick --skip', t=22)
