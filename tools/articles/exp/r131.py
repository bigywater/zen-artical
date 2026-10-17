import sys, time, os, json, re, glob; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r131'); R = {}
def brief(r): return str(r).replace('(error) ', '')[:140]
print('== 一:配置文件里 rename-command:FLUSHALL 改成空串(禁用)、KEYS 改成空串、CONFIG 改名 CFG_a83f')
n = Node(9190, name='s131', conf={'rename-command': ['FLUSHALL ""', 'KEYS ""', 'CONFIG CFG_a83f'], 'appendonly': 'no'}); n.start(); a = n.c()
a.do('SET', 'k', 1)
R['calls'] = {}
for cm in (('FLUSHALL',), ('KEYS', '*'), ('CONFIG', 'GET', 'dir'), ('CFG_a83f', 'GET', 'maxmemory'), ('DBSIZE',)):
    r = a.do(*cm, raise_err=False); R['calls'][' '.join(cm)] = brief(r); print(f'  {" ".join(cm):<24} → {brief(r)}')
print()
print('== 二:改名之后,命令表和统计里叫什么')
lst = a.do('COMMAND', 'LIST')
R['names'] = {x: (x in lst) for x in ('flushall', 'keys', 'config|get', 'cfg_a83f', 'cfg_a83f|get', 'config')}
print('  COMMAND COUNT =', a.do('COMMAND', 'COUNT'), '  COMMAND LIST 里是否含:', R['names'])
r = a.do('COMMAND', 'INFO', 'flushall', 'cfg_a83f', 'config'); print('  COMMAND INFO flushall / cfg_a83f / config →', ['(nil)' if x is None else x[0] for x in r]); R['cinfo'] = ['(nil)' if x is None else x[0] for x in r]
cs = [l for l in info(a, 'commandstats') if 'cfg' in l or 'config' in l or 'flushall' in l]; print('  INFO commandstats 里与之相关的行:', cs); R['cstats'] = cs
r = a.do('CFG_a83f', 'SET', 'rename-command', 'x y', raise_err=False); print('  运行时 CFG_a83f SET rename-command →', brief(r)); R['runtime_rename'] = brief(r)
a.do('CFG_a83f', 'REWRITE'); rl_ = [l for l in (n.dir / 'redis.conf').read_text().splitlines() if l.startswith('rename-command')]; print('  CFG_a83f REWRITE 之后 redis.conf 里的 rename-command 行:', rl_); R['rewrite_lines'] = rl_
print()
print('== 三:同样想禁用 FLUSHALL,用 ACL(-flushall)和 rename 的差别:被拒的尝试能不能被看见')
ren = a
acl = Node(9191, name='s131b'); acl.start(); b = acl.c(); b.do('ACL', 'SETUSER', 'default', '-flushall')
def counts(c):
    st = info(c, 'stats'); es = [l for l in info(c, 'errorstats')]
    return dict(acl_cmd=int(st.get('acl_access_denied_cmd', 0)), unexpected=int(st.get('unexpected_error_replies', 0)), acl_log=len(c.do('ACL', 'LOG', raise_err=False)) if isinstance(c.do('ACL', 'LOG', raise_err=False), list) else -1, errorstats=es)
for _ in range(3): ren.do('FLUSHALL', raise_err=False); b.do('FLUSHALL', raise_err=False)
cr = counts(n.c('' if False else None) if False else a); cb = counts(b)
# rename 节点上 ACL LOG 仍可用
print('  rename 节点(3 次 FLUSHALL):', {k: v for k, v in cr.items()}); print('  ACL  节点(3 次 FLUSHALL):', {k: v for k, v in cb.items()})
print('  两种失败的回复:rename →', brief(ren.do('FLUSHALL', raise_err=False)), '| ACL →', brief(b.do('FLUSHALL', raise_err=False)))
R['cmp'] = dict(rename=cr, acl=cb, rename_reply=brief(ren.do('FLUSHALL', raise_err=False)), acl_reply=brief(b.do('FLUSHALL', raise_err=False)))
cleanup([n, acl]); time.sleep(0.5)
print()
print('== 四:改名与复制 / AOF(主库改名,从库不改)')
m = Node(9192, name='s131m', conf={'rename-command': 'FLUSHALL FA9x', 'appendonly': 'yes', 'appendfsync': 'always'}); m.start()
rp = Node(9193, name='s131r', conf={'replicaof': '127.0.0.1 9192'}); rp.start(); wait_link(rp.c())
mc = m.c(); rc = rp.c()
for i in range(20): mc.do('SET', f'k{i}', i)
time.sleep(0.5); print('  主库、从库 DBSIZE:', mc.do('DBSIZE'), rc.do('DBSIZE'))
print('  主库执行 FA9x(改名后的 FLUSHALL) →', brief(mc.do('FA9x', raise_err=False))); time.sleep(0.8)
print('  之后 主库、从库 DBSIZE:', mc.do('DBSIZE'), rc.do('DBSIZE'), '  从库 master_link_status =', info(rc, 'replication')['master_link_status'])
aof = ''.join(open(f, 'rb').read().decode('utf-8', 'replace') for f in sorted(glob.glob(str(m.dir / 'appendonlydir' / '*.incr.aof'))))
names = re.findall(r'\r\n\$\d+\r\n([A-Za-z0-9_]+)\r\n', aof)
flush_in_aof = [x for x in names if x.upper() in ('FLUSHALL', 'FA9X')]
print('  主库 AOF 里记录的清库命令名:', flush_in_aof); R['rep_a'] = dict(dbsize=[mc.do('DBSIZE'), rc.do('DBSIZE')], link=info(rc, 'replication')['master_link_status'], aof=flush_in_aof)
print('  从库日志里与命令相关的行:', [l[-110:] for l in rp.log().splitlines() if 'unknown' in l.lower() or 'error' in l.lower()][:3])
cleanup([rp, m]); time.sleep(0.5)
print()
print('== 五:反过来:主库正常,从库把 FLUSHALL 禁用(rename-command FLUSHALL "")')
m = Node(9194, name='s131m2', conf={'appendonly': 'no'}); m.start()
rp = Node(9195, name='s131r2', conf={'replicaof': '127.0.0.1 9194', 'rename-command': 'FLUSHALL ""'}); rp.start(); wait_link(rp.c())
mc = m.c(); rc = rp.c()
for i in range(20): mc.do('SET', f'k{i}', i)
time.sleep(0.5); print('  主库、从库 DBSIZE:', mc.do('DBSIZE'), rc.do('DBSIZE'))
print('  主库执行 FLUSHALL →', brief(mc.do('FLUSHALL', raise_err=False))); time.sleep(1)
rep = info(rc, 'replication')
print('  之后 主库、从库 DBSIZE:', mc.do('DBSIZE'), rc.do('DBSIZE'), '  从库 master_link_status =', rep['master_link_status'])
print('  从库日志里与命令相关的行:', [re.sub(r'^\d+:\w \d+ \w+ \d+ [\d:.]+ ', '', l)[:150] for l in rp.log().splitlines() if 'unknown' in l.lower() or 'error' in l.lower() or 'flushall' in l.lower()][:4])
R['rep_b'] = dict(dbsize=[mc.do('DBSIZE'), rc.do('DBSIZE')], link=rep['master_link_status'])
time.sleep(1.5); rep = info(rc, 'replication'); print('  再过 1.5 s:主库、从库 DBSIZE:', mc.do('DBSIZE'), rc.do('DBSIZE'), '  link =', rep['master_link_status'], ' 从库 master_repl_offset =', rep['master_repl_offset'], ' 主库 =', info(mc, 'replication')['master_repl_offset'])
R['rep_b']['later'] = dict(dbsize=[mc.do('DBSIZE'), rc.do('DBSIZE')], link=rep['master_link_status'], offs=[rep['master_repl_offset'], info(mc, 'replication')['master_repl_offset']])
print()
print('== 六:一个没有查明原因的怪现象:同一连接上,紧跟在「新名字」之后的「原名字」居然能执行')
q = Node(9196, name='s131q', conf={'rename-command': ['FLUSHALL ""', 'KEYS K_ab7']}); q.start()
def t(c, *cm): return brief(c.do(*cm, raise_err=False))[:50]
R['quirk'] = {}
f = q.c(); R['quirk']['fresh'] = t(f, 'KEYS', '*'); print('  新连接直接 KEYS * →', R['quirk']['fresh'])
x = q.c(); steps_ = [('K_ab7', '*'), ('KEYS', '*'), ('DBSIZE',), ('KEYS', '*')]
res = [t(x, *cm) for cm in steps_]; R['quirk']['seq1'] = list(zip([' '.join(c) for c in steps_], res))
for c_, r_ in R['quirk']['seq1']: print(f'    同一连接:{c_:<10} → {r_}')
y = q.c(); steps2 = [('K_ab7', '*'), ('KEYS', 'a*'), ('KEYS', '*'), ('FLUSHALL',)]
res2 = [t(y, *cm) for cm in steps2]; R['quirk']['seq2'] = list(zip([' '.join(c) for c in steps2], res2)); print('  另一条连接:')
for c_, r_ in R['quirk']['seq2']: print(f'    {c_:<10} → {r_}')
z = q.c(); R['quirk']['other'] = t(z, 'KEYS', '*'); print('  第三条连接(没用过新名字)直接 KEYS * →', R['quirk']['other'])
cleanup([q])
save('r131', R); cleanup([rp, m])
