import sys, os, time, json, re, signal; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z70'); R = {}
def lines(nd, pats, n=2): return [re.sub(r'^\S+ \[.*?\] \w+\s+\S+ - ', '', l)[:150] for l in nd.log().splitlines() if any(p in l for p in pats)][-n:]
def case(title, symptom, cmd, out_lines, log_lines):
    print(f'  ■ {title}'); print(f'    客户端看到:{symptom}'); print(f'    先执行:{cmd}')
    for l in out_lines: print(f'      → {l}')
    for l in log_lines: print(f'    服务端日志:{l}')
    R[title] = dict(symptom=symptom, cmd=cmd, out=out_lines, log=log_lines)
print('== 故障排查速查:每一种故障都是我真的造出来的,下面是客户端症状、第一条应当执行的命令、以及日志里的关键行')
# A 没有多数派
e = Ensemble('z70a', 3, base=7300); [nd.prepare() for nd in e.nodes]; e.nodes[0].start(wait=False); time.sleep(5)
try: client('127.0.0.1:7300', timeout=4, start_timeout=4); sym = '连接成功'
except Exception as ex: sym = f'{type(ex).__name__}(连接 / 超时)'
case('A. 集群没有多数派(3 个节点只起了 1 个)', sym, 'echo srvr | nc 127.0.0.1 7300', [four(7300, 'srvr').strip().splitlines()[0]], lines(e.nodes[0], ['Cannot open channel', 'Notification time out'], 2))
e.nodes[0].stop()
# B 连接数超限
n = Node('z70b', 7301, conf={'maxClientCnxns': 3}).start(); cl = [client('127.0.0.1:7301', timeout=5) for _ in range(3)]
try: client('127.0.0.1:7301', timeout=4, start_timeout=4); sym = '连接成功'
except Exception as ex: sym = f'{type(ex).__name__}(连接超时)'
time.sleep(0.5)
case('B. 单个 IP 连接数超限(maxClientCnxns=3)', sym, 'echo cons | nc 127.0.0.1 7301(会被拒绝,先看日志)', ['(新连接被服务端直接拒绝,四字命令自己也是一个连接)'], lines(n, ['Too many connections'], 1))
[c.stop() for c in cl]; n.stop()
# C fsync 慢
n = Node('z70c', 7302, conf={}, jvm=['-Dzookeeper.fsync.warningthresholdms=1']).start(); z = client('127.0.0.1:7302'); [z.create(f'/n{i}', b'x') for i in range(100)]
m = kv(n.four('mntr'))
case('C. 写变慢(这里把 fsync 告警阈值调到 1 ms 来触发日志)', f'同步写 p50 约 3 ms', 'echo mntr | nc 127.0.0.1 7302 | grep fsync', [f'zk_avg_fsynctime = {m.get("zk_avg_fsynctime")}', f'zk_max_fsynctime = {m.get("zk_max_fsynctime")}'], lines(n, ['fsync-ing the write ahead log'], 1))
z.stop(); n.stop()
# D 会话过期
n = Node('z70d', 7303, conf={'tickTime': 1000}).start(); z = client('127.0.0.1:7303', timeout=4); z.create('/e', b'', ephemeral=True); st = []; z.add_listener(lambda s: st.append(str(s)))
n.pause(); time.sleep(7); n.resume(); time.sleep(3)
case('D. 会话过期(服务端被暂停 7 秒,会话超时 4 秒)', f'状态变化 {st}', 'echo dump | nc 127.0.0.1 7303(看 Session Sets 与临时节点)', ['临时节点 /e 随会话过期被删除:' + str(z.exists('/e') is None)], lines(n, ['Expiring session', 'expired'], 2))
z.stop(); n.stop()
# E jute.maxbuffer
n = Node('z70e', 7304).start(); z = client('127.0.0.1:7304')
try: z.create('/big', b'x' * 2 * 1048576); sym = '成功'
except Exception as ex: sym = type(ex).__name__
case('E. 请求超过 jute.maxbuffer(写 2 MiB 的 znode)', sym, '看服务端日志(客户端只有 ConnectionLoss)', [], lines(n, ['Len error'], 1))
n.stop(); save('z70', R)
