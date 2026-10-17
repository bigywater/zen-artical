import sys, time, os, json, socket, re, shutil, tempfile; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r129'); R = {}
def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try: s.connect(('10.255.255.255', 1)); return s.getsockname()[0]
    finally: s.close()
LAN = lan_ip()
TMP = RDATA / 's129_tmp'; shutil.rmtree(TMP, ignore_errors=True); TMP.mkdir(parents=True)
print(f'== 一:自查清单:站在「局域网上的一个陌生客户端」的位置({LAN}),对自己的实例问几个问题。五种配置各跑一遍')
cfgs = [('A 裸奔(全默认)', {'protected-mode': 'no'}), ('B protected-configs=yes', {'protected-mode': 'no', 'enable-protected-configs': 'yes'}),
        ('C protected-configs=local', {'protected-mode': 'no', 'enable-protected-configs': 'local'}), ('D default -@dangerous', {'protected-mode': 'no'}), ('E requirepass', {'protected-mode': 'no', 'requirepass': 'S3cret-pw'})]
danger = [('FLUSHALL',), ('KEYS', '*'), ('CONFIG', 'SET', 'dir', '/tmp'), ('REPLICAOF', '10.0.0.1', '6379'), ('SHUTDOWN', 'NOSAVE'), ('DEBUG', 'SLEEP', '0'), ('SAVE',), ('MONITOR',), ('EVAL', 'return 1', '0')]
rows = {}; nodes = []
for i, (label, conf) in enumerate(cfgs):
    n = Node(9170 + i, name=f's129{i}', conf=dict(bind='0.0.0.0', **conf)); n.start(); nodes.append(n)
    adm = n.c()
    if 'requirepass' in conf: adm.do('AUTH', conf['requirepass'])
    adm.do('ACL', 'SETUSER', 'admin', 'on', '>adminpw', '~*', '&*', '+@all')
    if i == 3: adm.do('ACL', 'SETUSER', 'default', '-@dangerous')
    adm.do('SET', 'session:1', 'pretend-secret')
    adm.close(); adm = n.c(); adm.do('AUTH', 'admin', 'adminpw')
    rr = {}
    def lanq(*cmd):
        try:
            c = C(n.port, host=LAN, timeout=3); r = c.do(*cmd, raise_err=False); c.close(); return r
        except Exception as e: return f'<{type(e).__name__}>'
    def short(r):
        if isinstance(r, Err): return str(r).split(' ')[0]
        if isinstance(r, list): return f'{len(r)} 项'
        return str(r)[:24]
    rr['PING'] = short(lanq('PING'))
    ins = lanq('INFO', 'server'); rr['INFO server'] = 'OK' if isinstance(ins, str) and 'redis_version' in ins else short(ins)
    if rr['INFO server'] == 'OK' and i == 0:
        R.setdefault('info_leak', {}).update({k: v for k, v in (l.split(':', 1) for l in ins.splitlines() if ':' in l) if k in ('redis_version', 'os', 'arch_bits', 'tcp_port', 'executable', 'config_file', 'process_id', 'run_id')})
    rr['DBSIZE'] = short(lanq('DBSIZE')); g_ = lanq('GET', 'session:1'); rr['GET session:1'] = '读到' if g_ == 'pretend-secret' else short(g_)
    d0 = adm.do('CONFIG', 'GET', 'dir')[1]
    rr['CONFIG GET dir'] = short(lanq('CONFIG', 'GET', 'dir'))
    r = lanq('CONFIG', 'SET', 'dir', str(TMP)); rr['CONFIG SET dir(改到我自己的临时目录)'] = 'OK' if r == 'OK' else short(r); R.setdefault('setdir_err', {})[label[0]] = str(r)
    changed = adm.do('CONFIG', 'GET', 'dir')[1] != d0
    if changed: adm.do('CONFIG', 'SET', 'dir', d0)
    rr['  dir 真的被改了吗'] = '是' if changed else '否'
    dbg = lanq('DEBUG', 'SLEEP', '0'); R.setdefault('debug_err', {})[label[0]] = str(dbg); rr['DEBUG SLEEP 0'] = short(dbg); rr['MODULE LIST'] = short(lanq('MODULE', 'LIST'))
    rr['KEYS *'] = short(lanq('KEYS', '*'))
    for cm in danger[:1] + danger[3:5]:
        rr['DRYRUN default ' + ' '.join(cm)] = 'OK' if adm.do('ACL', 'DRYRUN', 'default', *cm) == 'OK' else '拒绝'
    dl = [l for l in adm.do('ACL', 'LIST') if l.startswith('user default ')][0]; rr['default 是否 -@dangerous'] = '是' if '-@dangerous' in dl else '否'
    rows[label] = rr
    hold = C(n.port, host=LAN, timeout=3); hold.do('PING', raise_err=False) if i == 0 else None
    if i == 0:
        R['defaults'] = {k: adm.do('CONFIG', 'GET', k)[1] for k in ('enable-protected-configs', 'enable-debug-command', 'enable-module-command', 'protected-mode')}
        cl = [l for l in adm.do('CLIENT', 'LIST').splitlines() if LAN in l]
        R['seen_by_server'] = bool(cl); R['client_list_example'] = re.sub(r'\bid=\d+ ', '', cl[0])[:90] if cl else ''
        R['conns'] = int(info(adm, 'stats')['total_connections_received'])
keys = list(next(iter(rows.values())).keys())
w = 40
print(f'  {"检查项":<{w}}' + ''.join(f'{lab.split()[0]:>12}' for lab, _ in cfgs))
for k in keys: print(f'  {k:<{w}}' + ''.join(f'{str(rows[lab][k]):>12}' for lab, _ in cfgs))
print('  ' + ' | '.join(c[0] for c in cfgs))
R['rows'] = rows; R['keys'] = keys; R['labels'] = [c[0] for c in cfgs]
print()
print('== 二:出厂默认的三个「危险开关」')
print('  ', R['defaults']); print('  A 里 CONFIG SET dir 被拒的原文:', R['setdir_err']['A']); print('  B(=yes)里同一条:', R['setdir_err']['B']); print('  C(=local)里:', R['setdir_err']['C']); print('  DEBUG(A):', R['debug_err']['A'])
print('  A 上,陌生客户端保持着连接时,管理员的 CLIENT LIST 能看到来源地址吗(是否有来自 %s 的连接)' % LAN, '→', R['seen_by_server'], '|', R['client_list_example'])
print('  服务端 INFO 泄露给未登录客户端的字段(A):')
for k, v in R['info_leak'].items(): print(f'    {k:<14} {v}')
save('r129', R); cleanup(nodes)
