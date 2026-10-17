import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l46')
import ll as _ll
def run(d, cmd, t='now', **k): return _ll.run(d, cmd, t, **k)
def sh(d, cmd, t='now', **k): return _ll.sh(d, cmd, t, **k)
def ci(d, msg, files=None, t='now', **k): return _ll.ci(d, msg, files, t, **k)
def mk(name):
    d = lab(name); ci(d, '基础', {'a': '0\n'}, t=0)
    for i, c in enumerate(['A 加功能', 'B 修 bug', 'C 写文档', 'D 调样式'], 1): ci(d, c, {f'f{i}': f'{i}\n'}, t=i)
    return d
def seqed(name, code):
    f = LT / f'_seq_{name}.py'
    f.write_text("import sys\np = sys.argv[1]\nL = [l.rstrip('\\n') for l in open(p)]\ntodo = [l for l in L if l and not l.startswith('#')]\ndef find(sub): return next(i for i, l in enumerate(todo) if sub in l)\n" + code + "\nopen(p, 'w').write('\\n'.join(todo) + '\\n')\n")
    return f'python3 {f}'
MSG = LT / '_msged.py'; MSG.write_text("import sys,os\nopen(sys.argv[1],'w').write(os.environ['NEWMSG']+'\\n')\n")
SED = lambda script: f"GIT_SEQUENCE_EDITOR=\"sed -i.bak {shq(script)}\""
LOG = "git log --format='%s' --reverse | tail -n +2 | tr '\\n' ' '; echo"
print('== 一:git rebase -i 给你的 todo 列表:每个提交一行 “命令 hash 说明”,下面是命令速查')
d = mk('l46a')
sh(d, "GIT_SEQUENCE_EDITOR='cat' git rebase -i HEAD~4 2>&1 | sed -E 's/^(pick|p) [0-9a-f]{7} /\\1 <sha> /' | head -22", n=26)
print('== 二:改顺序、丢弃:todo 里调换行就是调换提交,删掉或写 drop 就是丢弃')
d = mk('l46b'); h_before = out1(d, 'git log --format=%h --reverse | tail -n +2').split()
sh(d, f"git log --format=%s --reverse | tail -n +2 | tr '\\n' ' '; echo '  ← rebase 之前'")
run(d, 'git rebase -i HEAD~4', env={'GIT_SEQUENCE_EDITOR': seqed('s2', "todo.insert(find('B 修 bug') + 1, todo.pop(find('A 加功能')))\ni = find('C 写文档'); todo[i] = todo[i].replace('pick', 'drop', 1)")}, t=30, who='Bob')
sh(d, f"git log --format=%s --reverse | tail -n +2 | tr '\\n' ' '; echo '  ← todo 里把 A 挪到 B 后面、C 改成 drop'")
print('== 三:squash 与 fixup:都把提交合并进上一个,squash 保留说明供你编辑,fixup 直接丢掉这个提交的说明')
for nm, cmd in [('squash', 'squash'), ('fixup', 'fixup')]:
    d = mk('l46c')
    run(d, 'git rebase -i HEAD~4', env={'GIT_SEQUENCE_EDITOR': seqed('s3' + nm, f"i = find('B 修 bug'); todo[i] = todo[i].replace('pick', '{cmd}', 1)"), 'GIT_EDITOR': 'true'}, t=30, who='Bob')
    print(f'  [{nm}] 提交数 {out1(d, "git rev-list --count HEAD")}(原来 5);合并后那个提交的完整说明:{out1(d, "git log -1 --format=%B HEAD~2").replace(chr(10), " / ")!r};它的 tree 里有: {out1(d, "git ls-tree --name-only HEAD~2").replace(chr(10), " ")}')
print('== 四:edit 停下来让你改,reword 只改说明')
d = mk('l46d')
run(d, 'git rebase -i HEAD~4', env={'GIT_SEQUENCE_EDITOR': seqed('s4', "i = find('B 修 bug'); todo[i] = todo[i].replace('pick', 'edit', 1)\nj = find('D 调样式'); todo[j] = todo[j].replace('pick', 'reword', 1)"), 'GIT_EDITOR': f'python3 {MSG}', 'NEWMSG': 'D 调样式(新说明)'}, t=30, who='Bob')
sh(d, 'git status | head -4 | sed -E "s/[0-9a-f]{7}/<sha>/g"; git log -1 --format=%s')
run(d, 'echo 额外 > extra.txt; git add extra.txt; git commit -q --amend --no-edit', t=31, who='Bob')
run(d, 'git rebase --continue', env={'GIT_EDITOR': f'python3 {MSG}', 'NEWMSG': 'D 调样式(新说明)'}, t=32, who='Bob')
sh(d, "git log --format=%s --reverse | tail -n +2 | tr '\\n' ' '; echo; git show --stat --format= HEAD~2 | tail -2")
print('== 五:exec:每个提交重放后运行一条命令;失败就停下')
d = mk('l46e')
sh(d, "git rebase -i --exec 'test ! -f f3 || (echo 测试失败:f3 存在 && false)' HEAD~4 2>&1 | grep -E 'Executing|Rebasing|测试失败|stopped|error' | head -6", env={'GIT_SEQUENCE_EDITOR': 'true'})
sh(d, 'git status | head -3 | sed -E "s/[0-9a-f]{7}/<sha>/g"; git rebase --abort')
print('== 六:--autosquash:git commit --fixup=<提交> 做的 “fixup! 说明” 提交,会被自动排到目标提交后面并标成 fixup')
d = mk('l46f'); target = out1(d, 'git rev-parse HEAD~3')
W(d, {'f2': '修正\n'}); run(d, f'git add -A; git commit -q --fixup={target}', t=10)
sh(d, "git log --format=%s -1")
sh(d, "GIT_SEQUENCE_EDITOR=cat git rebase -i --autosquash HEAD~5 2>&1 | grep -E '^(pick|fixup)' | sed -E 's/^(pick|fixup) [0-9a-f]{7} /\\1 /'")
print('== 七:没有被改动的前缀不会被改写:rebase -i 从第一个被修改的提交开始才有新 hash')
d = mk('l46g'); before = out1(d, 'git log --format=%h --reverse | tail -n +2').split()
run(d, 'git rebase -i HEAD~4', env={'GIT_SEQUENCE_EDITOR': seqed('s7', "i = find('C 写文档'); todo[i] = todo[i].replace('pick', 'reword', 1)"), 'GIT_EDITOR': f'python3 {MSG}', 'NEWMSG': 'C 写文档(改了说明)'}, t=30, who='Bob')
after = out1(d, 'git log --format=%h --reverse | tail -n +2').split()
for n, (a, b) in zip(['A 加功能', 'B 修 bug', 'C 写文档', 'D 调样式'], zip(before, after)): print(f'  {n:<10} {a} → {b}  {"没变" if a == b else "新 hash"}')
