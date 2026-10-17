import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z45'); R = {}
e = Ensemble('z45', 3, base=7300).start(); ld = e.leader(); f = e.followers()[0]; others = [n for n in e.nodes if n is not f]
hosts = ','.join(f'127.0.0.1:{n.cport}' for n in others); z = client(hosts, timeout=20); z.create('/seed', b'x')
print('== 一:一个 follower 离线后:集群继续服务(2/3 仍是多数派),leader 的 zk_synced_followers 从 2 变成 1')
print('  离线前 leader 的 synced_followers =', kv(ld.four('mntr')).get('zk_synced_followers')); f.kill(); time.sleep(3)
print('  离线后 synced_followers =', kv(ld.four('mntr')).get('zk_synced_followers'), '| 写入:', '成功' if can_write(hosts) else '失败'); R['down'] = kv(ld.four('mntr')).get('zk_synced_followers')
print()
print('== 二:离线期间错过不同数量的写入,重启后追上要多久、用什么方式同步')
print(f'  {"错过的写入":>10} {"追上用时 ms":>12} {"同步方式(leader 日志)":<30}')
R['catch'] = []; made = 0
for n_ in (100, 3000, 30000):
    rs = [z.create_async(f'/m{made + i}', b'x' * 50) for i in range(n_)]; [r.get() for r in rs]; made += n_
    ld = e.leader(); nb = len(ld.log().splitlines()); t0 = time.perf_counter(); f.start(wipe=False, wait=False)
    while time.perf_counter() - t0 < 60:
        if f.mode() == 'follower' and f.srvr().get('zxid') == e.leader().srvr().get('zxid'): break
        time.sleep(0.02)
    dt = (time.perf_counter() - t0) * 1000
    kind = [re.search(r'Sending (DIFF|snapshot|TRUNC)', l).group(1) for l in e.leader().log().splitlines()[nb:] if re.search(r'Sending (DIFF|snapshot|TRUNC)', l)]
    R['catch'].append((n_, dt, kind)); print(f'  {n_:>10} {dt:>12.0f} {str(kind):<30}')
    f.kill(); time.sleep(2)
print()
print('== 三:追上之后,从这个 follower 读到的数据与 leader 一致吗(重启最后一次后检查)')
f.start(wipe=False, wait=False); time.sleep(3)
zf = client(f'127.0.0.1:{f.cport}'); zl = client(f'127.0.0.1:{e.leader().cport}')
cf, cl = len(zf.get_children('/')), len(zl.get_children('/')); print(f'  根下子节点数:follower {cf} / leader {cl};Zxid:follower {f.srvr().get("zxid")} / leader {e.leader().srvr().get("zxid")}'); R['same'] = (cf, cl)
zf.stop(); zl.stop(); z.stop(); e.stop(); save('z45', R)
