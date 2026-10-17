import sys, os, re, signal; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l71')
import ll as _ll
def run(d, cmd, t=0, **k): return _ll.run(d, cmd, t, **k)
BIN = LT / '_bin71'; shutil.rmtree(BIN, ignore_errors=True); BIN.mkdir(); HL = LT / 'helper71.log'; SL = LT / 'server71.log'
def script(name, body):
    f = BIN / name; f.write_text('#!/bin/sh\n' + body + '\n'); f.chmod(0o755)
# 记录型 helper:每次调用把命令和 stdin 写进日志;get 返回环境变量 CRED_USER / CRED_PASS(没设置就什么都不返回)
script('git-credential-lab', f'''cmd="$1"; echo "[$HELPER_NAME] $cmd" >> {HL}; input=$(cat); echo "$input" | sed 's/^/    stdin: /' | sed 's/password=.*/password=<已隐藏>/' >> {HL}
if [ "$cmd" = get ] && [ -n "$CRED_USER" ]; then echo "username=$CRED_USER"; echo "password=$CRED_PASS"; fi''')
script('git-credential-second', f'''cmd="$1"; echo "[second] $cmd" >> {HL}; cat > /dev/null
if [ "$cmd" = get ]; then echo "username=备用用户"; echo "password=备用密码"; fi''')
d = lab('l71'); 
def env(**x):
    e = dict(PATH=f'{BIN}:/usr/bin:/bin:/usr/sbin:/sbin', GIT_TERMINAL_PROMPT='0', HELPER_NAME='lab'); e.update(x); return e
def g(cmd, stdin=None, **x):
    rc, o = run(d, cmd, env=env(**x), stdin=stdin); return rc, o
def hlog(): return [l for l in HL.read_text().split('\n') if l] if HL.exists() else []
def clear(): HL.write_text(''); SL.write_text('') if SL.exists() or True else None
def show_log(ind='    '):
    for l in hlog(): print(ind + l)
print('== 一:git credential 是 git 自己用的“凭据协议”的命令行入口:往 stdin 写 key=value,空行结束')
g('git config credential.helper lab')
clear(); rc, o = g('git credential fill', stdin='protocol=https\nhost=example.com\n\n', CRED_USER='alice', CRED_PASS='s3cret')
print('  git credential fill 的输出(host 等原样回显,helper 补上了 username 和 password):'); [print('    ' + re.sub(r'password=.*', 'password=<已隐藏>', l)) for l in o.split('\n') if l]
print('  helper 收到的调用(get)和它的 stdin:'); show_log()
clear(); rc, o = g('git credential fill', stdin='protocol=https\nhost=example.com\n\n'); print(f'  helper 什么也不返回、又不允许提示终端时: 退出码 {rc};输出: {o.strip()[:90]}')
print('== 二:approve / reject 对应 helper 的 store / erase')
clear(); g('git credential approve', stdin='protocol=https\nhost=example.com\nusername=alice\npassword=s3cret\n\n'); g('git credential reject', stdin='protocol=https\nhost=example.com\nusername=alice\npassword=s3cret\n\n')
show_log()
print('== 三:凭据协议里 credential.useHttpPath 决定 path 是否传给 helper;url 被拆成多个字段')
clear(); g('git credential fill', stdin='url=https://bob@git.example.com/org/repo.git\n\n', CRED_USER='bob', CRED_PASS='pw'); print('  默认(不带 path):'); show_log()
g('git config credential.useHttpPath true'); clear(); g('git credential fill', stdin='url=https://bob@git.example.com/org/repo.git\n\n', CRED_USER='bob', CRED_PASS='pw'); print('  credential.useHttpPath=true 之后:'); show_log(); g('git config --unset credential.useHttpPath')
print('== 四:真实的 HTTP 认证流程:本机起一个要求 Basic 认证的 git smart-http 服务(git http-backend)')
srv = LT / 'l71srv'; shutil.rmtree(srv, ignore_errors=True); srv.mkdir(); run(srv, 'git init -q --bare repo.git')
seed = lab('l71seed'); _ll.ci(seed, 'S1', {'a': '1\n'}, t=0); run(seed, f'git push -q {srv}/repo.git main')
PORT = 9811; sv = subprocess.Popen([sys.executable, str(LT / '_basic_git_server.py'), str(srv), str(PORT), 'alice', 's3cret'], env=dict(os.environ, SERVER_LOG=str(SL)), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
URL = f'http://127.0.0.1:{PORT}/repo.git'
def slog(): return [l for l in SL.read_text().split('\n') if l] if SL.exists() else []
try:
    clear(); rc, o = g(f'git ls-remote {URL}', CRED_USER='alice', CRED_PASS='s3cret')
    print(f'  正确的凭据:git ls-remote 退出码 {rc}'); print('  服务器看到的请求:'); [print('    ' + l.replace(str(PORT), '<端口>')) for l in slog()[:4]]
    print('  helper 被调用:'); show_log()
    clear(); rc, o = g(f'git ls-remote {URL}', CRED_USER='alice', CRED_PASS='错误的密码')
    print(f'  helper 给了错误的密码:退出码 {rc};{o.strip().splitlines()[-1][:100] if o.strip() else ""}'); print('  服务器看到的请求:'); [print('    ' + l) for l in slog()[:4]]
    print('  helper 被调用(注意最后的 erase——认证被拒绝后 git 通知 helper 删掉这条凭据):'); show_log()
    print('== 五:多个 helper 按顺序询问,第一个给出完整凭据的算数;approve 时通知所有 helper')
    g('git config --add credential.helper second'); g('git config --unset-all credential.helper'); g('git config --add credential.helper lab'); g('git config --add credential.helper second')
    clear(); rc, o = g('git credential fill', stdin='protocol=https\nhost=example.com\n\n'); print(f'  第一个 helper(lab)没给凭据,第二个给了: ' + re.sub(r'password=.*', 'password=<已隐藏>', o.replace(chr(10), ' | ')))
    show_log()
    clear(); g('git credential approve', stdin='protocol=https\nhost=example.com\nusername=备用用户\npassword=备用密码\n\n'); print('  approve 时(store)两个 helper 都被通知:'); show_log()
finally:
    sv.terminate()
print('== 六:自带的 credential-store helper:把凭据以明文写进文件(权限 600),reject 时删掉')
cs = LT / 'creds_store'; cs.unlink(missing_ok=True)
g(f'git config credential.helper "store --file {cs}"'); g('git config --unset-all credential.helper'); g(f'git config credential.helper "store --file {cs}"')
g('git credential approve', stdin='protocol=https\nhost=example.com\nusername=alice\npassword=s3cret\n\n')
print('  credential-store 写下的文件(明文!):', cs.read_text().strip().replace('s3cret', '<密码>'), f'| 权限 {oct(cs.stat().st_mode)[-3:]}')
rc, o = g('git credential fill', stdin='protocol=https\nhost=example.com\n\n'); print('  之后 fill 不再需要提示:', re.sub(r'password=.*', 'password=<已隐藏>', o.replace(chr(10), ' | ')))
rc, o = g('git credential reject', stdin='protocol=https\nhost=example.com\nusername=alice\npassword=s3cret\n\n'); print('  reject 之后文件内容:', repr(cs.read_text()))
