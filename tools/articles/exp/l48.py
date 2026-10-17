import sys, os, hashlib; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l48')
BASE = ''.join(f'第 {i} 行\n' for i in range(1, 9))
def L(ch):
    X = BASE.split('\n')
    for k, v in ch.items(): X[k - 1] = v
    return '\n'.join(X)
OURS = L({4: '第 4 行 ours'}); THEIRS = L({4: '第 4 行 theirs'}); RES = L({4: '第 4 行 我的解法(合并了两边)'})
def mk(name, rerere):
    d = lab(name); ci(d, '基础', {'f.txt': BASE}, t=0); run(d, 'git checkout -q -b theirs'); ci(d, 'theirs 改第 4 行', {'f.txt': THEIRS}, t=1); run(d, 'git checkout -q main'); ci(d, 'ours 改第 4 行', {'f.txt': OURS}, t=2)
    if rerere: run(d, 'git config rerere.enabled true')
    return d
print('== 一:没有 rerere:同一个冲突,每次都得重新手工解决')
d = mk('l48a', False); run(d, 'git merge theirs')
sh(d, 'git status --short; ls .git | grep -c rr-cache | sed "s/^ */rr-cache 目录数: /"')
W(d, {'f.txt': RES}); run(d, 'git add f.txt; git commit -q -m 第一次合并', 3)
run(d, 'git reset -q --hard HEAD~1'); sh(d, 'git merge theirs 2>&1 | tail -2; git status --short; sed -n 4,8p f.txt', n=8)
print('== 二:打开 rerere.enabled:冲突发生时记录“解决前”,提交时记录“解决后”')
d = mk('l48b', True)
sh(d, 'git merge theirs 2>&1 | grep -E "rerere|Recorded|CONFLICT"')
sh(d, 'ls .git/rr-cache | sed -E "s/^[0-9a-f]{40}$/<冲突指纹 40 位>/"; ls .git/rr-cache/*/ | grep -v "^$"')
W(d, {'f.txt': RES}); sh(d, 'git add f.txt; git commit -q -m 第一次合并 2>&1; ls .git/rr-cache/*/ | grep -v "^$" | tr "\\n" " "; echo', t=3)
print('  (提交时 git 调用 rerere 记录了 postimage)')
print('== 三:三个文件的内容:preimage = 带冲突标记的文件,postimage = 你解决之后的文件;目录名是冲突内容的指纹')
rr = next((d / '.git' / 'rr-cache').iterdir()); fid = rr.name
pre = (rr / 'preimage').read_text(); post = (rr / 'postimage').read_text()
print('  preimage:'); [print('    | ' + l) for l in pre.split('\n')[3:8]]
print('  postimage 的第 4 行:', post.split('\n')[3])
def rid(pre):
    # 取冲突块里 ours / theirs 两段,排序后各自加 \0 做 SHA-1
    lines = pre.split('\n'); i = [k for k, l in enumerate(lines) if l.startswith('<<<<<<<')][0]; j = [k for k, l in enumerate(lines) if l.startswith('=======')][0]; k2 = [k for k, l in enumerate(lines) if l.startswith('>>>>>>>')][0]
    a = '\n'.join(lines[i + 1:j]) + '\n'; b = '\n'.join(lines[j + 1:k2]) + '\n'
    one, two = sorted([a, b]); return hashlib.sha1(one.encode() + b'\0' + two.encode() + b'\0').hexdigest()
print(f'  目录名(冲突指纹): {fid[:12]}…   自己用 SHA-1(排序后的两段冲突内容各加 \\0)算: {rid(pre)[:12]}…   相同: {rid(pre) == fid}')
print('== 四:同样的冲突再出现:自动套用上次的解法')
run(d, 'git reset -q --hard HEAD~1')
sh(d, 'git merge theirs 2>&1 | grep -E "Resolved|CONFLICT|rerere"; git status --short; sed -n 4p f.txt')
print('  git diff 显示相对 stage 的变化(文件已按上次解法写好,但没有自动 git add,因为 rerere.autoUpdate 默认关闭):')
sh(d, 'git rerere status; git diff --stat | tail -1')
run(d, 'git add f.txt; git commit -q -m 第二次合并', 4)
print('== 五:rebase、cherry-pick、换一个分支重复同样的冲突也认:指纹只看冲突内容,不看哪个分支')
run(d, 'git reset -q --hard HEAD~1'); run(d, 'git checkout -q -b other main', 5)
sh(d, 'git cherry-pick theirs 2>&1 | grep -E "Resolved|CONFLICT|rerere|Recorded"; sed -n 4p f.txt')
run(d, 'git cherry-pick --abort'); run(d, 'git checkout -q main')
d2 = mk('l48c', True); run(d2, 'git merge theirs'); W(d2, {'f.txt': RES}); run(d2, 'git add f.txt; git commit -q -m 合并', 3)
run(d2, 'git reset -q --hard HEAD~1'); run(d2, 'git checkout -q theirs')
sh(d2, 'git rebase main 2>&1 | grep -E "Resolved|CONFLICT|Recorded|rerere|Rebasing"; sed -n 4p f.txt')
run(d2, 'git rebase --abort')
print('== 六:不满意要忘掉:git rerere forget;过期的记录由 git rerere gc 清理(解决过的 60 天,没解决的 15 天)')
run(d, 'git checkout -q main'); run(d, 'git reset -q --hard HEAD~0')
sh(d, 'git merge theirs 2>&1 | grep -E "Resolved|CONFLICT"; ls .git/rr-cache/*/ | grep -v "^$" | tr "\\n" " "; echo')
sh(d, 'git rerere forget f.txt 2>&1; ls .git/rr-cache/*/ | grep -v "^$" | tr "\\n" " "; echo "(forget 之后:只剩 preimage,postimage 没了)"')
run(d, 'git merge --abort')
sh(d, 'git config --get gc.rerereResolved || echo "gc.rerereResolved 未设置(默认 60 天)"; git config --get gc.rerereUnresolved || echo "gc.rerereUnresolved 未设置(默认 15 天)"; git rerere gc; echo "git rerere gc 退出码 $?"')
