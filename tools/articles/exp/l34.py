import sys, os, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l34')
ORIG = ''.join(f'行 {i:02d}\n' for i in range(1, 41))
def edit(s, ch):
    L = s.split('\n')
    for ln, new in ch.items(): L[ln - 1] = new
    return '\n'.join(L)
NEW = edit(ORIG, {3: '行 03 改了', 5: '行 05 改了', 20: '行 20 改了', 38: '行 38 改了'})
def repo(name, new=NEW):
    d = lab(name); ci(d, '起点', {'f.txt': ORIG}, t=0); W(d, {'f.txt': new}); return d
def addp(d, answers, cfg=''):
    return run(d, f'printf "{answers}" | git {cfg} add -p f.txt 2>&1')[1]
HH = "grep -E '^@@' "
print('== 一:工作区有 4 处改动(第 3、5、20、38 行),git diff 把它们切成几个 hunk')
d = repo('l34a'); sh(d, "git diff | grep -E '^@@'")
print('  第 3 行与第 5 行相隔一行,各带 3 行上下文,上下文重叠,于是合成了一个 hunk')
print('== 二:git add -p 逐个询问;用管道喂答案(y 暂存、n 跳过、s 拆分、q 退出),看最终暂存了什么')
print('  答案 n、y、y(第一个 hunk 不要,后两个要);add -p 每个 hunk 问一次(提示里的 s 只在可拆分时才出现):')
sh(d, "printf 'n\\ny\\ny\\n' | git add -p f.txt 2>&1 | grep -E '^(@@|\\()' | sed -E 's/^(\\([0-9]\\/[0-9]\\) Stage this hunk \\[[^]]*\\]\\?) .*/\\1/'", n=10)
print('  暂存区里(git diff --cached)和工作区里剩下的(git diff):')
sh(d, "git diff --cached | grep -E '^(@@|[+-][^+-])'")
sh(d, "git diff | grep -E '^(@@|[+-][^+-])'")
print('== 三:s 把一个 hunk 拆成更小的:只有改动之间隔着未改动行时才能拆')
d = repo('l34b'); o = addp(d, 's\\ny\\nn\\nq\\n')
print('  对第一个 hunk 输入 s:git 回答 Split into 2 hunks.(第 3 行与第 5 行的改动被分开),再对拆出的第一块输 y、第二块输 n、然后 q:')
print('    ' + next(l for l in o.split('\n') if 'Split into' in l)[-24:].strip())
d = repo('l34b'); addp(d, 's\\ny\\nn\\nq\\n')
sh(d, "git diff --cached | grep -E '^(@@|[+-][^+-])'")
print('== 四:e 手工编辑 hunk:把 +行 03 改了 改成 +行 03 我手工改的,并删掉 +行 05 改了(只剩 -行 05,等于只暂存“删除第 5 行”);git 重算 @@ 头里的行数')
d = repo('l34c')
ed = LT / 'l34_editor.py'
ed.write_text('import sys,re\np=sys.argv[1]\nL=open(p).read().split("\\n")\nout=[]\nfor l in L:\n    if l.startswith("+行 05 改了"): continue\n    if l.startswith("+行 03 改了"): l="+行 03 我手工改的"\n    out.append(l)\nopen(p,"w").write("\\n".join(out))\n')
rc, o = run(d, f'printf "e\\nq\\n" | GIT_EDITOR="python3 {ed}" git add -p f.txt 2>&1 | tail -3')
sh(d, "git diff --cached | grep -E '^(@@|[+-][^+-])'")
sh(d, "git show :f.txt | sed -n '3p;5p'; echo '--- 工作区:'; sed -n '3p;5p' f.txt")
print('== 五:暂存的 blob = HEAD 版本 + 选中的 hunk;和手工 git apply --cached 同一份补丁得到的 blob 完全相同')
d = repo('l34d'); addp(d, 'n\\ny\\nn\\n'); b1 = out1(d, 'git rev-parse :f.txt')
d2 = repo('l34e'); run(d2, 'git diff > full.patch')
txt = (d2 / 'full.patch').read_text(); parts = re.split(r'(?m)^(?=@@ )', txt); head, hunks = parts[0], parts[1:]
(d2 / 'sel.patch').write_text(head + hunks[1]); run(d2, 'git apply --cached sel.patch'); b2 = out1(d2, 'git rev-parse :f.txt')
print(f'  add -p(n、y、n)暂存的 blob: {b1[:12]}   手工只取第 2 个 hunk 的补丁 git apply --cached: {b2[:12]}   相同: {b1 == b2}')
print('  工作区文件没动:', (d / 'f.txt').read_text() == NEW)
print('== 六:新文件需要先 git add -N(intent-to-add)才能用 -p;checkout -p、reset -p、stash -p 是同一套机制')
d = lab('l34f'); ci(d, '起点', {'a.txt': 'a\n'}, t=0); W(d, {'new.txt': ''.join(f'n{i}\n' for i in range(1, 7))})
sh(d, 'printf "y\\n" | git add -p 2>&1 | head -2; git status --short')
sh(d, 'git add -N new.txt; git status --short; printf "y\\n" | git add -p new.txt 2>&1 | grep -E "^(@@|\\(1/1\\))" | head -2; git diff --cached --stat | tail -1')
d = repo('l34g'); run(d, 'git add f.txt')
sh(d, "printf 'n\\ny\\nn\\n' | git reset -p f.txt >/dev/null 2>&1; git diff --cached | grep -E '^(@@|[+-][^+-])'")
