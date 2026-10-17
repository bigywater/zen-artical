import sys, time, os, json, re, glob, stat, subprocess, shutil, pathlib; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r132'); R = {}
def mode(p): return oct(os.stat(p).st_mode & 0o777)[2:].rjust(4, '0')
def run_case(label, umask, port, sockperm):
    D = RDATA / f's132_{label}'; shutil.rmtree(D, ignore_errors=True); D.mkdir(parents=True)
    conf = f'''port {port}
bind 127.0.0.1
dir {D}
save ""
appendonly yes
aclfile {D}/users.acl
logfile {D}/redis.log
cluster-enabled yes
cluster-config-file nodes.conf
masterauth Conf-Plain-Pw
unixsocket /tmp/rs132{label}.sock
''' + (f'unixsocketperm {sockperm}\n' if sockperm else '')
    (D / 'users.acl').write_text('')
    cp = D / 'redis.conf'; cp.write_text(conf)
    old = os.umask(0o022); os.chmod(cp, 0o644); os.umask(old)
    p = subprocess.Popen(['redis-server', str(cp)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=D, preexec_fn=lambda: os.umask(umask))
    t0 = time.time()
    while time.time() - t0 < 10:
        try: c = C(port); break
        except Exception: time.sleep(0.05)
    c.do('CLUSTER', 'ADDSLOTSRANGE', 0, 16383); time.sleep(0.5)
    c.pipeline([['SET', f'k{i}', 'v' * 30] for i in range(6000)])
    c.do('ACL', 'SETUSER', 'svc', 'on', '>hunter2', '~*', '+get'); c.do('ACL', 'SAVE'); c.do('CONFIG', 'REWRITE')
    c.do('CONFIG', 'SET', 'rdb-key-save-delay', 500); c.do('BGSAVE'); tmpmode = '(没抓到)'; t1 = time.time()
    while time.time() - t1 < 4:
        tmp = sorted(glob.glob(str(D / 'temp-*.rdb')))
        if tmp: tmpmode = mode(tmp[0]); break
        time.sleep(0.02)
    while info(c, 'persistence')['rdb_bgsave_in_progress'] == '1': time.sleep(0.2)
    c.do('BGREWRITEAOF'); time.sleep(1.5)
    rows = {}
    rows['数据目录'] = mode(D)
    rows['redis.conf(CONFIG REWRITE 之后)'] = mode(cp)
    rows['dump.rdb'] = mode(D / 'dump.rdb'); rows['BGSAVE 进行中的 temp-*.rdb'] = tmpmode
    rows['appendonlydir/'] = mode(D / 'appendonlydir')
    for f in sorted(os.listdir(D / 'appendonlydir')): rows['  appendonlydir/' + re.sub(r'\d+', 'N', f)] = mode(D / 'appendonlydir' / f)
    rows['users.acl(ACL SAVE)'] = mode(D / 'users.acl'); rows['nodes.conf'] = mode(D / 'nodes.conf'); rows['redis.log'] = mode(D / 'redis.log'); rows['r.sock'] = mode(f'/tmp/rs132{label}.sock')
    txt = cp.read_text(); rows['_conf_has_plain_requirepass'] = 'Conf-Plain-Pw' in txt
    rows['_acl_has_hash_only'] = ('hunter2' not in (D / 'users.acl').read_text()) and ('#' in (D / 'users.acl').read_text())
    p.terminate(); p.wait(10)
    try: os.unlink(f'/tmp/rs132{label}.sock')
    except OSError: pass
    return rows
print('== 一:默认 umask 022 与 umask 077 下,Redis 创建的各个文件的权限(八进制)')
A = run_case('a', 0o022, 9200, None); B = run_case('b', 0o077, 9201, None)
keys = [k for k in A if not k.startswith('_')]
print(f'  {"文件":<40}{"umask 022":>12}{"umask 077":>12}')
for k in keys: print(f'  {k:<40}{A[k]:>12}{B.get(k, "-"):>12}')
R['A'] = A; R['B'] = B; R['keys'] = keys
print()
print('== 二:unixsocketperm 对 Unix 套接字文件权限的影响(umask 022)')
C_ = run_case('c', 0o022, 9202, '700'); print('  未设 unixsocketperm:', A['r.sock'], ' 设 unixsocketperm 700:', C_['r.sock']); R['sock'] = [A['r.sock'], C_['r.sock']]
print()
print('== 三:配置文件里的 requirepass 是明文;ACL 文件里只有哈希')
print('  redis.conf 含明文的 masterauth 密码:', A['_conf_has_plain_requirepass'], '   users.acl 只有哈希、没有明文:', A['_acl_has_hash_only'])
print('  一个明文的 requirepass 行读起来是:', [l for l in (RDATA / 's132_a' / 'redis.conf').read_text().splitlines() if l.startswith('masterauth')])
print('  users.acl 内容:', (RDATA / 's132_a' / 'users.acl').read_text().strip().splitlines())
print()
print('== 四:附带发现:配了 aclfile 之后,redis.conf 里的 requirepass 还起作用吗?')
D = RDATA / 's132_d'; shutil.rmtree(D, ignore_errors=True); D.mkdir(parents=True); (D / 'users.acl').write_text('')
(D / 'redis.conf').write_text(f'port 9203\nbind 127.0.0.1\ndir {D}\nsave ""\nlogfile {D}/redis.log\naclfile {D}/users.acl\nrequirepass Conf-Plain-Pw\n')
p = subprocess.Popen(['redis-server', str(D / 'redis.conf')], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=D); time.sleep(1)
c = C(9203); r = c.do('PING', raise_err=False); print('  aclfile(空)+ requirepass:不带密码 PING →', r); a_ = c.do('ACL', 'LIST'); print('  ACL LIST →', a_); R['aclfile_requirepass'] = dict(ping=str(r), acl=a_)
print('  日志里的相关行:', [re.sub(r'^\d+:\w \d+ \w+ \d+ [\d:.]+ ', '', l)[:160] for l in (D / 'redis.log').read_text().splitlines() if 'acl' in l.lower() or 'requirepass' in l.lower()][:3])
p.terminate(); p.wait(10)
(D / 'redis.conf').write_text(f'port 9204\nbind 127.0.0.1\ndir {D}\nsave ""\nrequirepass Conf-Plain-Pw\naclfile {D}/users.acl\n')
p = subprocess.Popen(['redis-server', str(D / 'redis.conf')], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=D); time.sleep(1)
c = C(9204); r2 = c.do('PING', raise_err=False); print('  把 requirepass 写在 aclfile 前面:不带密码 PING →', r2); R['aclfile_requirepass']['ping_reordered'] = str(r2)
p.terminate(); p.wait(10)
save('r132', R)
