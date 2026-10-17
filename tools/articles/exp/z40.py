import sys, os, time, json, re, signal; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z40'); R = {}
e = Ensemble('z40', 3, base=7300).start(); ld = e.leader(); fo = e.followers()
KEYS = ['zk_learner_proposal_received_count', 'zk_learner_commit_received_count', 'zk_commit_count', 'zk_avg_quorum_ack_latency', 'zk_avg_proposal_latency']
def snap(nd): m = kv(nd.four('mntr')); return {k.replace('zk_', ''): m.get(k) for k in KEYS}
print('== 一:一个写请求的广播:Proposal → Ack → Commit。通过 follower 写 500 个 znode,各节点计数器(写之前 → 之后)')
z = client(f'127.0.0.1:{fo[0].cport}'); before = {n.name: snap(n) for n in e.nodes}
for i in range(500): z.create(f'/n{i}', b'x')
time.sleep(0.5); after = {n.name: snap(n) for n in e.nodes}
for n in e.nodes:
    role = n.mode(); d = {k: (int(after[n.name][k] or 0) - int(before[n.name][k] or 0)) for k in ('learner_proposal_received_count', 'learner_commit_received_count', 'commit_count')}
    print(f'  {n.name} {role:<9} 收到 proposal +{d["learner_proposal_received_count"]:<4} 收到 commit +{d["learner_commit_received_count"]:<4} 本地提交 commit_count +{d["commit_count"]}')
R['counters'] = {n.name: {k: int(after[n.name][k] or 0) - int(before[n.name][k] or 0) for k in ('learner_proposal_received_count', 'learner_commit_received_count', 'commit_count')} for n in e.nodes}; R['modes'] = {n.name: n.mode() for n in e.nodes}
print('  leader 的 avg_quorum_ack_latency =', after[ld.name]['avg_quorum_ack_latency'], 'ms;avg_proposal_latency =', after[ld.name]['avg_proposal_latency'], 'ms')
print()
print('== 二:提交需要多数派确认:暂停两个 follower,leader 上的写请求卡住,数据对读不可见;恢复后才提交')
z.stop(); zl = client(f'127.0.0.1:{ld.cport}', timeout=30); zr = client(f'127.0.0.1:{ld.cport}', timeout=30)
for f in fo: f.pause()
res = zl.create_async('/pending', b'x'); time.sleep(1.5)
print('  两个 follower 暂停 1.5 秒后:异步 create 完成了吗?', res.ready(), '| 另一个客户端读 /pending:', zr.exists('/pending'), '| leader 的 zk_outstanding_requests =', kv(ld.four('mntr')).get('zk_outstanding_requests'))
R['pending'] = dict(ready=res.ready(), exists=zr.exists('/pending') is not None, outstanding=kv(ld.four('mntr')).get('zk_outstanding_requests'))
for f in fo: f.resume()
t0 = time.perf_counter()
try: res.get(timeout=20); ok = True
except Exception as ex: ok = type(ex).__name__
print(f'  follower 恢复后 {(time.perf_counter() - t0) * 1000:.0f} ms:create 结果 {ok},/pending 现在可见:', zr.exists('/pending') is not None); R['after_resume'] = dict(ok=str(ok), exists=zr.exists('/pending') is not None)
zl.stop(); zr.stop(); e.stop(); save('z40', R)
