import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l50')
def mk(name):
    d = lab(name); ci(d, 'c1', {'x': '版本 1\n'}, t=0); ci(d, 'c2', {'x': '版本 2\n'}, t=1); ci(d, 'c3', {'x': '版本 3\n'}, t=2)
    W(d, {'x': '版本 3 + 暂存的改动\n'}); run(d, 'git add x'); W(d, {'x': '版本 3 + 暂存的改动 + 工作区的改动\n', 'z': '未跟踪\n'}); return d
def state(d):
    head = out1(d, 'git log -1 --format=%s'); idx = out1(d, 'git show :x'); wt = (d / 'x').read_text().strip() if (d / 'x').exists() else '(不存在)'
    return f'HEAD={head:<3} | 暂存区 x={idx!r:<28} | 工作区 x={wt!r:<30} | 未跟踪 z {"还在" if (d / "z").exists() else "没了"}'
print('== 一:起点:三个区域各不相同——HEAD 是 c3(x=版本 3),暂存区里 x 带“暂存的改动”,工作区里 x 又多了“工作区的改动”,另有未跟踪文件 z')
d = mk('l50a'); print('  ' + state(d))
print('== 二:三种模式对 HEAD、暂存区、工作区的影响(都 reset 到 HEAD~1,也就是 c2)')
res = {}
for mode in ['--soft', '--mixed', '--hard']:
    d = mk('l50b'); run(d, f'git reset {mode} HEAD~1'); res[mode] = state(d); print(f'  git reset {mode}: ' + res[mode])
print('  规律:--soft 只动 HEAD;--mixed(默认)动 HEAD 和暂存区;--hard 三个都动(未跟踪文件不碰)')
print('== 三:--hard 会丢掉工作区的改动,但对象还在:被 reset 掉的 c3 和暂存的 blob 仍然能找回')
d = mk('l50c'); c3 = out1(d, 'git rev-parse HEAD'); blob = out1(d, 'git rev-parse :x'); run(d, 'git reset --hard HEAD~1')
print(f'  c3 还在对象库里: {run(d, f"git cat-file -e {c3}")[0] == 0};暂存过的 blob 内容: {out1(d, f"git cat-file -p {blob}")!r}(从没 add 过的“工作区的改动”则没有对象,真的丢了)')
sh(d, "git reflog -3 --format='%gd: %gs'")
print(f'  ORIG_HEAD 指向被 reset 掉的 c3: {out1(d, "git rev-parse ORIG_HEAD") == c3}')
print('== 四:--keep 与 --merge:更安全的 hard,遇到会被覆盖的本地改动就拒绝')
for mode in ['--keep', '--merge']:
    d = mk('l50d'); rc, o = run(d, f'git reset {mode} HEAD~1 2>&1'); print(f'  git reset {mode} HEAD~1 → {o.replace(chr(10), " / ")}   | ' + state(d))
d = lab('l50e'); ci(d, 'c1', {'x': '1\n', 'y': 'y\n'}, t=0); ci(d, 'c2', {'x': '2\n'}, t=1); W(d, {'y': 'y 的本地改动\n'})
rc, o = run(d, 'git reset --keep HEAD~1 2>&1'); print(f'  对比:本地改的是 y(c1 到 c2 没碰 y)时 --keep 可以成功: HEAD={out1(d, "git log -1 --format=%s")},x={out1(d, "cat x")!r},y={out1(d, "cat y")!r}(本地改动保留)')
print('== 五:带路径的 reset 只动暂存区:git reset <提交> -- 路径 不动 HEAD,也不动工作区')
d = mk('l50f'); head0 = out1(d, 'git rev-parse HEAD')
sh(d, 'git reset HEAD~1 -- x; git status --short')
print('  ' + state(d)); print(f'  HEAD 没动: {out1(d, "git rev-parse HEAD") == head0}')
sh(d, 'git reset -- x; git status --short', ind='  ')
print('== 六:reset 只移动“当前分支”,不改变其它分支')
d = mk('l50g'); run(d, 'git branch keep'); run(d, 'git reset --hard -q HEAD~2')
sh(d, "git log --oneline --all --decorate | sed -E 's/^[0-9a-f]{7} //'")
