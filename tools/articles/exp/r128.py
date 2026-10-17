import sys, time, os, json, subprocess, socket, re, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r128'); R = {}
def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try: s.connect(('10.255.255.255', 1)); return s.getsockname()[0]
    finally: s.close()
LAN = lan_ip(); R['lan'] = LAN
print(f'== 零:本机有两个地址:回环 127.0.0.1 和局域网地址 {LAN}。从本机连自己的局域网地址,服务端看到的来源就不是回环地址')
def ask(host, port, *cmd, auth=None):
    try:
        c = C(host and host, timeout=3) if False else C(port, host=host, timeout=3)
        if auth: c.do('AUTH', auth)
        r = c.do(*cmd, raise_err=False); c.close(); return r
    except Exception as e:
        return f'<{type(e).__name__}: {e}>'
def show(label, host, port, *cmd, auth=None):
    r = ask(host, port, *cmd, auth=auth); s = str(r) if not isinstance(r, Err) else f'(error) {r}'
    print(f'  {label:<46} → {s[:200]}'); return s
cases = []
print()
print('== 一:不带任何配置文件,只用 redis-server --port 启动(出厂默认)')
D = RDATA / 's128a'; shutil.rmtree(D, ignore_errors=True); D.mkdir(parents=True)
pa = subprocess.Popen(['redis-server', '--port', '9160', '--dir', str(D), '--save', '', '--logfile', str(D / 'redis.log')], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
R['a'] = {'lo': show('经 127.0.0.1 PING', '127.0.0.1', 9160, 'PING'), 'lan': show(f'经 {LAN} PING', LAN, 9160, 'PING')}
print('  CONFIG GET bind / protected-mode:', ask('127.0.0.1', 9160, 'CONFIG', 'GET', 'bind'), ask('127.0.0.1', 9160, 'CONFIG', 'GET', 'protected-mode'))
R['a_cfg'] = [ask('127.0.0.1', 9160, 'CONFIG', 'GET', 'bind'), ask('127.0.0.1', 9160, 'CONFIG', 'GET', 'protected-mode')]
lg = [l for l in (D / 'redis.log').read_text().splitlines() if 'WARNING' in l or 'rotected' in l or 'authentication' in l]
print('  启动日志里的相关行:'); [print('   ', re.sub(r'^\d+:\w \d+ \w+ \d+ [\d:.]+ ', '', l)[:220]) for l in lg]
R['a_log'] = [re.sub(r'^\d+:\w \d+ \w+ \d+ [\d:.]+ ', '', l) for l in lg]
lsof = subprocess.run(['lsof', '-nP', '-iTCP:9160', '-sTCP:LISTEN'], capture_output=True, text=True).stdout.strip().splitlines()[1:]
print('  监听地址:', ' ; '.join(l.split()[-2] for l in lsof)); R['a_listen'] = [l.split()[-2] for l in lsof]
print('  运行时执行 CONFIG SET protected-mode no 后,经局域网 PING:', end=' '); ask('127.0.0.1', 9160, 'CONFIG', 'SET', 'protected-mode', 'no'); print(str(ask(LAN, 9160, 'PING'))); R['a_after_no'] = str(ask(LAN, 9160, 'PING'))
pa.terminate(); pa.wait(10)
print()
print('== 二:四种配置组合,分别从回环和局域网地址连')
combos = [
    ('B  bind * · protected-mode yes · 无密码', dict(bind='0.0.0.0', **{'protected-mode': 'yes'}), None),
    ('C  bind * · protected-mode yes · requirepass', dict(bind='0.0.0.0', requirepass='pw123', **{'protected-mode': 'yes'}), 'pw123'),
    ('D  bind * · protected-mode no · 无密码', dict(bind='0.0.0.0', **{'protected-mode': 'no'}), None),
    (f'E  bind 127.0.0.1 {LAN} · protected-mode yes · 无密码', dict(bind=f'127.0.0.1 {LAN}', **{'protected-mode': 'yes'}), None),
]
R['combos'] = {}
for i, (label, conf, pw) in enumerate(combos):
    n = Node(9161 + i, name=f's128{i}', conf=conf); n.start()
    print(f'  [{label}]')
    row = {}
    row['lo'] = show('    经 127.0.0.1 PING', '127.0.0.1', n.port, 'PING')
    row['lan'] = show(f'    经 {LAN} PING', LAN, n.port, 'PING')
    if pw: row['lan_auth'] = show(f'    经 {LAN} 先 AUTH 再 PING', LAN, n.port, 'PING', auth=pw)
    R['combos'][label[0]] = row
    n.stop(); time.sleep(0.3)
print()
print('== 三:另一条路——保持 protected-mode yes,给 default 用户加密码(不用 requirepass 字段,而是 ACL)')
n = Node(9166, name='s128f', conf={'bind': '0.0.0.0', 'protected-mode': 'yes'}); n.start()
a = n.c(); a.do('ACL', 'SETUSER', 'default', '>pw123')
R['acl_pw'] = dict(lan=show(f'经 {LAN} PING(无 AUTH)', LAN, 9166, 'PING'), lan_auth=show(f'经 {LAN} AUTH 后 PING', LAN, 9166, 'PING', auth='pw123'))
print('  这时 ACL LIST 里 default:', a.do('ACL', 'LIST')[0][:80])
n.stop()
save('r128', R)
