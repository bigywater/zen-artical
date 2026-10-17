import sys, time, os, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r123'); R = {}
n = Node(9124, name='s123'); n.start(); a = n.c()
print('== 一:ACL CAT:命令分类,以及每个分类里有多少条命令(本实例 8.10.2)')
cats = a.do('ACL', 'CAT'); print('  分类:', ' '.join(cats))
cnt = {c: len(a.do('ACL', 'CAT', c)) for c in cats}
allc = len(a.do('COMMAND', 'LIST'))
print('  COMMAND LIST 总数(不含子命令):', allc)
for c in cats: print(f'  @{c:<12} {cnt[c]:>4}')
R['cnt'] = cnt; R['total'] = allc
print('  @dangerous 的前 20 条:', ' '.join(a.do('ACL', 'CAT', 'dangerous')[:20]))
print()
print('== 二:几种常见配置,用 ACL DRYRUN 对同一批命令判定(不用真连,服务端直接回答)')
sh(a, 'ACL', 'SETUSER', 'ro', 'on', 'nopass', '~*', '-@all', '+@read')
sh(a, 'ACL', 'SETUSER', 'nodanger', 'on', 'nopass', '~*', '+@all', '-@dangerous')
sh(a, 'ACL', 'SETUSER', 'appuser', 'on', 'nopass', '~app:*', '-@all', '+get', '+set', '+del')
sh(a, 'ACL', 'SETUSER', 'empty', 'on', 'nopass')
for u in ('ro', 'nodanger', 'appuser', 'empty'): sh(a, 'ACL', 'GETUSER', u, show=False); print(f'  {u}:', [l for l in a.do("ACL", "LIST") if l.startswith("user " + u + " ")][0])
cmds = [('GET', 'app:1'), ('SET', 'app:1', 'v'), ('DEL', 'app:1'), ('GET', 'x'), ('SCAN', 0), ('KEYS', '*'), ('INFO',), ('PING',), ('EVAL', 'return 1', 0), ('CONFIG', 'GET', 'dir'), ('CONFIG', 'SET', 'dir', '/tmp'), ('FLUSHALL',), ('SUBSCRIBE', 'ch'), ('PUBLISH', 'ch', 'm'), ('SAVE',), ('SHUTDOWN', 'NOSAVE'), ('MONITOR',), ('CLIENT', 'LIST'), ('DEBUG', 'SLEEP', 0)]
tab = {}
print(f'  {"命令":<24}' + ''.join(f'{u:>10}' for u in ('ro', 'nodanger', 'appuser', 'empty')))
for cm in cmds:
    row = []
    for u in ('ro', 'nodanger', 'appuser', 'empty'):
        r = a.do('ACL', 'DRYRUN', u, *cm, raise_err=False)
        row.append('允许' if r == 'OK' else '拒绝')
    tab[' '.join(map(str, cm))] = row
    print(f'  {" ".join(map(str, cm)):<24}' + ''.join(f'{x:>10}' for x in row))
R['tab'] = tab
print('  ACL DRYRUN 的拒绝原因示例:'); [sh(a, 'ACL', 'DRYRUN', 'ro', *c) for c in (('SET', 'k', 'v'),)]; sh(a, 'ACL', 'DRYRUN', 'appuser', 'GET', 'x'); sh(a, 'ACL', 'DRYRUN', 'nodanger', 'FLUSHALL')
print()
print('== 三:规则顺序:同样两条规则,顺序不同,结果不同')
sh(a, 'ACL', 'SETUSER', 'o1', 'on', 'nopass', '~*', '+@all', '-@dangerous')
sh(a, 'ACL', 'SETUSER', 'o2', 'on', 'nopass', '~*', '-@dangerous', '+@all')
for u in ('o1', 'o2'):
    print(f'  {u}:', [l for l in a.do("ACL", "LIST") if l.startswith("user " + u + " ")][0])
    print(f'    FLUSHALL → {a.do("ACL", "DRYRUN", u, "FLUSHALL", raise_err=False)!s}'[:100])
R['o1'] = str(a.do('ACL', 'DRYRUN', 'o1', 'FLUSHALL')); R['o2'] = str(a.do('ACL', 'DRYRUN', 'o2', 'FLUSHALL'))
print()
print('== 四:子命令粒度:只允许 CONFIG GET,不允许 CONFIG SET')
sh(a, 'ACL', 'SETUSER', 'cfg', 'on', 'nopass', '~*', '-@all', '+config|get', '+ping')
print('  ', [l for l in a.do("ACL", "LIST") if l.startswith("user cfg ")][0])
b = n.c(); sh(b, 'AUTH', 'cfg', 'x'); sh(b, 'CONFIG', 'GET', 'maxmemory'); R['sub_set'] = str(sh(b, 'CONFIG', 'SET', 'maxmemory', '1mb')); sh(b, 'CONFIG', 'REWRITE')
print()
print('== 五:选择器(selector):同一个用户在不同 key 上有不同权限')
sh(a, 'ACL', 'SETUSER', 'sel', 'on', 'nopass', '~cache:*', '+@all', '-@dangerous', '(~reports:* +get)')
print('  ', [l for l in a.do("ACL", "LIST") if l.startswith("user sel ")][0])
for cm in (('SET', 'cache:1', 'v'), ('GET', 'reports:1'), ('SET', 'reports:1', 'v'), ('GET', 'other:1')):
    print(f'  DRYRUN sel {" ".join(cm)} →', fmt(a.do('ACL', 'DRYRUN', 'sel', *cm, raise_err=False)))
R['sel'] = {' '.join(cm): str(a.do('ACL', 'DRYRUN', 'sel', *cm, raise_err=False)) for cm in (('SET', 'cache:1', 'v'), ('GET', 'reports:1'), ('SET', 'reports:1', 'v'), ('GET', 'other:1'))}
print()
print('== 六:为什么 nodanger 连 INFO、SUBSCRIBE 也不行?')
d = a.do('ACL', 'CAT', 'dangerous')
print('  INFO / CLIENT LIST / MONITOR / DEBUG 在 @dangerous 里吗:', {x: (x in d) for x in ('info', 'client|list', 'monitor', 'debug')})
print('  PING 在 @read 里吗:', 'ping' in a.do('ACL', 'CAT', 'read'), ';在 @fast 里吗:', 'ping' in a.do('ACL', 'CAT', 'fast'))
for cm in (('SUBSCRIBE', 'ch'), ('INFO',)): print(f'  DRYRUN nodanger {" ".join(cm)} → {fmt(a.do("ACL", "DRYRUN", "nodanger", *cm))}')
sh(a, 'ACL', 'SETUSER', 'nodanger2', 'on', 'nopass', '~*', '&*', '+@all', '-@dangerous')
for cm in (('SUBSCRIBE', 'ch'), ('PUBLISH', 'ch', 'm')): print(f'  DRYRUN nodanger2(加了 &*) {" ".join(cm)} → {fmt(a.do("ACL", "DRYRUN", "nodanger2", *cm))}')
save('r123', R); cleanup([n])
