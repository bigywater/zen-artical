import sys, os, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l63')
import ll as _ll
def run(d, cmd, t='now', **k): return _ll.run(d, cmd, t, **k)
def sh(d, cmd, t='now', **k): return _ll.sh(d, cmd, t, **k)
def ci(d, msg, files=None, t='now', **k): return _ll.ci(d, msg, files, t, **k)
SAN = lambda t: re.sub(r'\b[0-9a-f]{40}\b', '<sha40>', re.sub(r'\b[0-9a-f]{7}\b', '<sha7>', t))
def install(d, names, rc=None, extra=None):
    """给仓库 d 装上记录型 hook:把 hook 名字、参数、(可选)stdin 追加到 .git/hook.log;rc 是 {hook名: 退出码}。"""
    for n in names:
        code = (rc or {}).get(n, 0)
        stdin_part = 'cat > /tmp/_hk_stdin.$$; sed "s/^/    stdin: /" /tmp/_hk_stdin.$$ >> "$LOG"; rm -f /tmp/_hk_stdin.$$' if n in ('pre-push', 'pre-receive', 'post-receive', 'post-rewrite', 'reference-transaction') else ''
        body = f'#!/bin/sh\nLOG="$(git rev-parse --git-dir 2>/dev/null)/hook.log"\n[ -d "$LOG" ] && LOG=hook.log\nLOG="${{HOOKLOG:-$LOG}}"\necho "{n} $*" >> "$LOG"\n{stdin_part}\n{(extra or {}).get(n, "")}\nexit {code}\n'
        f = d / 'hooks' / n if (d / 'hooks').exists() else d / '.git' / 'hooks' / n
        f.write_text(body); f.chmod(0o755)
def log(d, n=40):
    pass
def log(d, n=40):
    f = d / '.git' / 'hook.log' if (d / '.git').exists() else d / 'hook.log'
    return [_ll.tidy(SAN(l)) for l in f.read_text().split('\n') if l] if f.exists() else []
def clear(d):
    for f in ((d / '.git' / 'hook.log'), (d / 'hook.log')):
        if f.exists(): f.unlink()
CLIENT = ['pre-commit', 'prepare-commit-msg', 'commit-msg', 'post-commit', 'pre-merge-commit', 'post-merge', 'pre-rebase', 'post-checkout', 'post-rewrite', 'pre-push']
print('== 一:git commit 触发的 hook 和顺序(参数是 hook 收到的命令行参数)')
d = lab('l63a'); ci(d, '基础', {'a': '1\n'}); install(d, CLIENT)
W(d, {'a': '2\n'}); run(d, 'git add a'); clear(d); run(d, 'git commit -q -m "第二次"')
for l in log(d): print('  ' + l)
print('  (prepare-commit-msg 的参数:消息文件 + 来源 message;commit-msg 的参数:消息文件;post-commit 没有参数)')
print('== 二:退出码的影响:pre-commit / commit-msg 非 0 就中止提交;post-commit 非 0 被忽略;--no-verify 跳过前两者')
for nm, rc in [('pre-commit 退出 1', {'pre-commit': 1}), ('commit-msg 退出 1', {'commit-msg': 1}), ('post-commit 退出 1', {'post-commit': 1})]:
    d = lab('l63b'); ci(d, '基础', {'a': '1\n'}); install(d, CLIENT, rc); W(d, {'a': '2\n'}); run(d, 'git add a'); clear(d)
    rc_, o = run(d, 'git commit -q -m x 2>&1'); n_ = out1(d, 'git rev-list --count HEAD')
    print(f'  {nm:<20}→ git commit 退出码 {rc_},提交数 {n_}(原来 1);触发的 hook: {" → ".join(l.split()[0] for l in log(d))}')
d = lab('l63b'); ci(d, '基础', {'a': '1\n'}); install(d, CLIENT, rc={'pre-commit': 1, 'commit-msg': 1}); W(d, {'a': '2\n'}); run(d, 'git add a'); clear(d)
rc_, o = run(d, 'git commit -q --no-verify -m x 2>&1')
print(f'  pre-commit 与 commit-msg 都退出 1,但 --no-verify:退出码 {rc_},提交数 {out1(d, "git rev-list --count HEAD")};触发的 hook: {" → ".join(l.split()[0] for l in log(d))}(prepare-commit-msg 和 post-commit 不受 --no-verify 影响)')
print('== 三:commit-msg 可以改写提交说明;prepare-commit-msg 可以预填')
d = lab('l63c'); ci(d, '基础', {'a': '1\n'}); install(d, ['commit-msg'], extra={'commit-msg': 'echo "[审核通过]" >> "$1"'}); W(d, {'a': '2\n'}); run(d, 'git add a'); run(d, 'git commit -q -m "原始说明"')
sh(d, 'git log -1 --format=%B | head -3')
print('== 四:checkout、merge、rebase 的 hook 与参数')
d = lab('l63d'); ci(d, '基础', {'a': '1\n'}); install(d, CLIENT); run(d, 'git checkout -q -b side'); ci(d, 'side 上的提交', {'s': '1\n'}); run(d, 'git checkout -q main'); ci(d, 'main 上的提交', {'m': '1\n'})
clear(d); run(d, 'git checkout -q side'); print('  git checkout side:'); [print('    ' + l) for l in log(d)]
run(d, 'git checkout -q main'); clear(d); run(d, 'git merge -q --no-edit side'); print('  git merge side(非快进,产生合并提交):'); [print('    ' + l) for l in log(d)]
base_ = out1(d, 'git rev-list --max-parents=0 HEAD'); run(d, f'git checkout -q -b topic {base_}'); ci(d, 'topic 提交', {'t': '1\n'}); clear(d); run(d, 'git rebase -q main'); print('  git rebase main(topic 上有 1 个提交要搬):'); [print('    ' + l) for l in log(d)]
print('  (post-checkout 的三个参数:旧 HEAD、新 HEAD、1=切换分支 / 0=检出文件;post-rewrite 的 stdin 是“旧 sha 新 sha”)')
print('== 五:git push 触发 pre-push:参数是远程名和 URL,stdin 每行“本地ref 本地sha 远程ref 远程sha”;非 0 阻止推送')
R = LT / 'l63r.git'; shutil.rmtree(R, ignore_errors=True); run(LT, f'git init -q --bare {R}')
d = lab('l63e'); ci(d, '基础', {'a': '1\n'}); run(d, f'git remote add origin {R}'); install(d, ['pre-push']); clear(d)
run(d, 'git push -q origin main'); [print('  ' + l) for l in log(d)]
install(d, ['pre-push'], rc={'pre-push': 1}); ci(d, '又一个', {'a': '2\n'}); rc_, o = run(d, 'git push origin main 2>&1'); print(f'  pre-push 退出 1:git push 退出码 {rc_},远程 main 仍是旧的: {out1(R, "git rev-list --count main")} 个提交')
print('== 六:服务端 hook(裸仓库):pre-receive → update(每个 ref 一次)→ 接受 → post-receive → post-update')
SR = LT / 'l63srv.git'; shutil.rmtree(SR, ignore_errors=True); run(LT, f'git init -q --bare {SR}')
hk = SR / 'hooks'
install(SR, ['pre-receive', 'update', 'post-receive', 'post-update'])
for n_ in ['pre-receive', 'update', 'post-receive', 'post-update']:
    f = hk / n_; t_ = f.read_text().replace('LOG="$(git rev-parse --git-dir 2>/dev/null)/hook.log"', f'LOG={SR}/hook.log'); f.write_text(t_)
d = lab('l63f'); ci(d, '基础', {'a': '1\n'}); run(d, f'git remote add origin {SR}'); run(d, 'git branch topic')
run(d, 'git push -q origin main topic'); (SR / 'hook.log').exists()
for l in [_ll.tidy(SAN(x)) for x in (SR / 'hook.log').read_text().split('\n') if x]: print('  ' + l)
print('  (update 对每个被更新的 ref 各运行一次,参数是 “ref 旧值 新值”;pre-receive / post-receive 只运行一次,stdin 每行 “旧值 新值 ref”;新建分支的旧值是全 0)')
print('  update 非 0 只拒绝那个 ref;pre-receive 非 0 则整个推送被拒绝:')
install(SR, ['update'], extra={'update': 'case "$1" in refs/heads/topic) exit 1;; esac'}); f = hk / 'update'; f.write_text(f.read_text().replace('LOG="$(git rev-parse --git-dir 2>/dev/null)/hook.log"', f'LOG={SR}/hook.log'))
ci(d, '第二个', {'a': '2\n'}); run(d, 'git checkout -q topic'); ci(d, 'topic 的新提交', {'t': '1\n'}); run(d, 'git checkout -q main')
rc_, o = run(d, 'git push origin main topic 2>&1 | grep -E "^ [!*+ ]|remote:|rejected" | sed -E "s/[0-9a-f]{7}/<sha7>/g"')
print('  update 对 topic 退出 1 的推送结果:'); [print('    ' + l) for l in o.split('\n') if l]
print(f'  远程 main 是否更新: {out1(SR, "git rev-list --count main")} 个提交;远程 topic: {out1(SR, "git rev-list --count topic")} 个提交(topic 没更新)')
install(SR, ['pre-receive'], rc={'pre-receive': 1}); f = hk / 'pre-receive'; f.write_text(f.read_text().replace('LOG="$(git rev-parse --git-dir 2>/dev/null)/hook.log"', f'LOG={SR}/hook.log'))
ci(d, '第三个', {'a': '3\n'}); rc_, o = run(d, 'git push origin main 2>&1 | grep -E "^ [!*+ ]|remote:|rejected" | sed -E "s/[0-9a-f]{7}/<sha7>/g"')
print('  pre-receive 退出 1:'); [print('    ' + l) for l in o.split('\n') if l]
print('== 七:hook 的几个常见坑:要有可执行位;不随 clone 传递;core.hooksPath 可以集中管理')
d = lab('l63g'); ci(d, '基础', {'a': '1\n'}); install(d, ['pre-commit'], extra={'pre-commit': 'echo "pre-commit 运行了"'}); (d / '.git' / 'hooks' / 'pre-commit').chmod(0o644)
W(d, {'a': '2\n'}); run(d, 'git add a'); rc_, o = run(d, 'git commit -m x 2>&1 | head -4'); print('  去掉可执行位的 pre-commit:'); [print('    ' + l[:110]) for l in o.split('\n') if l]
(d / '.git' / 'hooks' / 'pre-commit').chmod(0o755)
c = LT / 'l63gc'; shutil.rmtree(c, ignore_errors=True); run(LT, f'git clone -q {d} l63gc')
print(f'  clone 出来的仓库 .git/hooks 里有 pre-commit 吗: {(c / ".git" / "hooks" / "pre-commit").exists()}(clone 不复制 hook;里面只有 *.sample 示例文件:{len(list((c / ".git" / "hooks").glob("*.sample")))} 个)')
shared = LT / 'l63_shared_hooks'; shutil.rmtree(shared, ignore_errors=True); shared.mkdir(); (shared / 'pre-commit').write_text('#!/bin/sh\necho "来自 core.hooksPath 的 pre-commit"\nexit 0\n'); (shared / 'pre-commit').chmod(0o755)
run(c, f'git config core.hooksPath {shared}'); run(c, 'git config user.name A; git config user.email a@e'); W(c, {'a': '9\n'}); run(c, 'git add a')
rc_, o = run(c, 'git commit -m y 2>&1 | head -2'); print('  设置 core.hooksPath 指向一个共享目录后:', o.replace('\n', ' | '))
