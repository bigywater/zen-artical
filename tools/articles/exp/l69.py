import sys, os, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l69')
import ll as _ll
def run(d, cmd, t=0, **k): return _ll.run(d, cmd, t, **k)
CF = LT / '_cfg'; shutil.rmtree(CF, ignore_errors=True); CF.mkdir()
SYS, GLB, XDG = CF / 'system.conf', CF / 'global.conf', CF / 'xdg_config'
(CF / 'work').mkdir()
d = lab('l69')
def env(**x):
    e = dict(GIT_CONFIG_NOSYSTEM='', GIT_CONFIG_SYSTEM=str(SYS), GIT_CONFIG_GLOBAL=str(GLB)); e.update(x); return e
def g(cmd, dd=None, **x):
    rc, o = run(dd or d, cmd, env=env(**x)); return o
def show(cmd, ind='  ', dd=None, **x):
    print(f'{ind}$ {cmd}'); o = g(cmd, dd, **x); o = o.replace(str(CF), '<cfg>').replace(str(d), '<repo>'); [print(ind + '  ' + l) for l in o.split('\n') if l]
for f in (SYS, GLB): f.write_text('')
print('== 一:同一个键 user.name 在四个层级各设一个值:谁说了算')
g('git config --system user.name 系统层', GIT_CONFIG_SYSTEM=str(SYS)); g('git config --global user.name 全局层'); g('git config --local user.name 仓库层')
show('git config --show-origin --show-scope --get-all user.name')
show('git config user.name')
print('  (--get-all 按读取顺序列出所有值,最后一个生效;顺序是 system → global → local)')
print('== 二:命令行 -c 和环境变量还要更高')
show('git -c user.name=命令行 config user.name')
show('git config user.name', GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='user.name', GIT_CONFIG_VALUE_0='环境变量')
show('git -c user.name=命令行 config --show-scope --get-all user.name', GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='user.name', GIT_CONFIG_VALUE_0='环境变量')
print('== 三:worktree 层:extensions.worktreeConfig 打开后,每个工作树有自己的 config.worktree')
ci_ = lambda: _ll.ci(d, 'x', {'a': '1\n'}, t=0)
shutil.rmtree(LT / 'l69wt', ignore_errors=True); ci_(); run(d, 'git worktree add -q ../l69wt -b wt', env=env()) ; wt = LT / 'l69wt'
g('git config extensions.worktreeConfig true'); g('git config --worktree user.name 工作树层', dd=wt)
show('git config --show-scope --show-origin --get-all user.name', dd=wt)
show('git config --show-scope --get-all user.name', dd=d)
print('  同一个仓库的另一个工作树(主工作树)看不到“工作树层”的值')
print('== 四:include 和 includeIf:把别的文件的内容插入到这个位置;位置决定覆盖关系')
(CF / 'extra.conf').write_text('[user]\n\tname = include 进来的\n\temail = inc@example.com\n')
GLB.write_text('[user]\n\tname = 全局层\n[include]\n\tpath = extra.conf\n[user]\n\temail = 全局 include 之后\n')
show('git config --show-origin --get-all user.name'); show('git config --show-origin --get-all user.email')
print('  includeIf "gitdir:":仓库路径匹配时才引入——可以给公司目录配一套身份')
(CF / 'work.conf').write_text('[user]\n\tname = 工作身份\n\temail = me@corp.example\n')
GLB.write_text(f'[user]\n\tname = 全局层\n\temail = me@home.example\n[includeIf "gitdir:{LT}/l69w*/"]\n\tpath = {CF}/work.conf\n')
d2 = lab('l69work')
for nm, dd in [('l69(路径不匹配)', d), ('l69work(匹配 gitdir:…/l69w*/)', d2)]:
    print(f'  [{nm}] user.name = ' + g('git config user.name', dd=dd) + ' ; user.email = ' + g('git config user.email', dd=dd))
print('== 五:多值的键:--get 取最后一个,--get-all 取全部;remote.origin.fetch 这样的键会叠加')
GLB.write_text('[remote "origin"]\n\tfetch = +refs/heads/global/*:refs/remotes/origin/global/*\n')
g('git remote add origin /tmp/x.git')
show('git config --show-scope --get-all remote.origin.fetch'); show('git config --get remote.origin.fetch')
g('git config --unset remote.origin.fetch')
print('  git config --unset remote.origin.fetch(写操作默认只改 local 文件)之后:'); show('git config --show-scope --get-all remote.origin.fetch', ind='    ')
print('== 六:git 从哪些地方读配置:--list --show-origin 的文件清单')
(CF / 'xdg' / 'git').mkdir(parents=True, exist_ok=True); (CF / 'xdg' / 'git' / 'config').write_text('[core]\n\tpager = xdg-pager\n\teditor = xdg-editor\n')
def real(extra=None):
    e = lenv(); e.pop('GIT_CONFIG_GLOBAL', None); e.update(GIT_CONFIG_NOSYSTEM='', GIT_CONFIG_SYSTEM=str(SYS), HOME=str(CF), XDG_CONFIG_HOME=str(CF / 'xdg')); e.update(extra or {}); return e
def lst():
    r = subprocess.run('git config --list --show-origin --show-scope | grep -E "core\\.(pager|editor)"', shell=True, cwd=d, env=real(), capture_output=True, text=True)
    for l in r.stdout.strip().split('\n'): print('    ' + l.replace(str(CF), '<cfg>'))
(CF / '.gitconfig').unlink(missing_ok=True)
print('  只有 $XDG_CONFIG_HOME/git/config(没有 ~/.gitconfig):'); lst()
(CF / '.gitconfig').write_text('[core]\n\tpager = home-pager\n\teditor = home-editor\n')
print('  两个都有(~/.gitconfig 在后,覆盖前者):'); lst()
subprocess.run('git config --global core.pager written-by-global', shell=True, cwd=d, env=real())
print('  git config --global 写入的是 ~/.gitconfig(已存在时优先),不是 XDG 那个:', 'written-by-global' in (CF / '.gitconfig').read_text(), '/', 'written-by-global' in (CF / 'xdg' / 'git' / 'config').read_text())
