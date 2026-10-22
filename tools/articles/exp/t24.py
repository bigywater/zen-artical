import sys, os, json, base64, http.client; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
from rl import DelayProxy
tee('t24'); reset(); subprocess.run("pkill -f 'etcd --name t24' 2>/dev/null; true", shell=True)
b64 = lambda s: base64.b64encode(s.encode()).decode()
N = 3; CP = [free_port() for _ in range(N)]; PP = [free_port() for _ in range(N)]; QP = [free_port() for _ in range(N)]
class Px(DelayProxy):
    """rl.DelayProxy 在目标节点被杀(连不上)时 accept 线程会直接退出;这里改成连不上就关掉这一条连接、继续接受新的。"""
    def _accept(self):
        while self.alive:
            try: a, _ = self.ls.accept()
            except Exception: return
            try: b = socket.create_connection(('127.0.0.1', self.tport), timeout=2)
            except Exception:
                try: a.close()
                except Exception: pass
                continue
            for x in (a, b): x.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            for x, y in ((a, b), (b, a)): threading.Thread(target=self._pump, args=(x, y), daemon=True).start()
PX = [Px(QP[i], PP[i], 0) for i in range(N)]      # 每个节点的 peer 地址都对外公布成一个代理端口,方便给“发往这个节点的流量”加延迟
procs = [None] * N
def start_node(i):
    d = TT / f'etcd_t24_{i}'; d.mkdir(exist_ok=True)
    cl = ','.join(f't24n{j}=http://127.0.0.1:{QP[j]}' for j in range(N))
    cmd = ['etcd', '--name', f't24n{i}', '--data-dir', str(d / 'data'), '--listen-client-urls', f'http://127.0.0.1:{CP[i]}', '--advertise-client-urls', f'http://127.0.0.1:{CP[i]}',
           '--listen-peer-urls', f'http://127.0.0.1:{PP[i]}', '--initial-advertise-peer-urls', f'http://127.0.0.1:{QP[i]}', '--initial-cluster', cl, '--initial-cluster-token', 't24', '--heartbeat-interval', '100', '--election-timeout', '1000']
    procs[i] = subprocess.Popen(cmd, stdout=open(d / 'etcd.log', 'a'), stderr=subprocess.STDOUT, start_new_session=True)
def kill_node(i):
    if procs[i] and procs[i].poll() is None:
        os.killpg(procs[i].pid, signal.SIGKILL); procs[i].wait()
def call(i, path, body, timeout=3):
    c = http.client.HTTPConnection('127.0.0.1', CP[i], timeout=timeout)
    try: c.request('POST', path, json.dumps(body), {'Content-Type': 'application/json'}); r = c.getresponse(); d = r.read(); return r.status, json.loads(d or b'{}')
    finally: c.close()
def status(i):
    try: s, d = call(i, '/v3/maintenance/status', {}, 2); return d if s == 200 else None
    except Exception: return None
def put(i, k, v, timeout=3):
    return call(i, '/v3/kv/put', {'key': b64(k), 'value': b64(v)}, timeout)
def get(i, k, serializable=False, timeout=3):
    s, d = call(i, '/v3/kv/range', {'key': b64(k), 'serializable': serializable}, timeout)
    if s != 200: return f'错误 {s}:{d.get("message", d)}'
    kvs = d.get('kvs') or []; return base64.b64decode(kvs[0]['value']).decode() if kvs else None
def leader_idx():
    for i in range(N):
        d = status(i)
        if d and d.get('leader') and d['header']['member_id'] == d['leader']: return i
    return None
def wait_leader(timeout=20, among=None):
    t0 = time.time()
    while time.time() - t0 < timeout:
        l = leader_idx()
        if l is not None and (among is None or l in among): return l
        time.sleep(0.1)
    return None
def show_status(label, idxs=range(N)):
    print(f'  {label}')
    rows = []
    for i in idxs:
        d = status(i)
        if d: rows.append((f't24n{i}', '是' if d.get('leader') and d['header']['member_id'] == d['leader'] else '', d['header'].get('raft_term'), d.get('raftIndex'), d.get('raftAppliedIndex')))
        else: rows.append((f't24n{i}', '(不可达)', '-', '-', '-'))
    table(rows, ['节点', 'leader', 'raft term', 'raftIndex(日志最后一条)', 'raftAppliedIndex(已应用)'])
for i in range(N): start_node(i)
L = wait_leader(); assert L is not None
print(f'etcd {subprocess.run(["etcd", "--version"], capture_output=True, text=True).stdout.splitlines()[0]},3 个节点(客户端端口 {CP},peer 端口 {PP},每个节点的 peer 地址经过一层延迟代理 {QP},默认不加延迟);heartbeat-interval 100 ms、election-timeout 1000 ms;通过 etcd 自带的 HTTP/JSON 网关读写')

print('== 一:一次正常写入的提交:写入前后各节点的 raft 状态(raftIndex = 日志里最后一条的序号,raftAppliedIndex = 已经应用到状态机的序号)')
show_status('写入之前:'); [put(L, f'k{i}', f'v{i}') for i in range(5)]; time.sleep(0.3)
show_status('对 leader 写了 5 次之后:')
print(f'  leader 是 t24n{L};每个节点的 raftIndex 都涨了 5:每次写入是一条 Raft 日志,leader 把它复制给 follower,多数(3 个里的 2 个)落盘之后才算提交、才应用到状态机、才回复客户端')

print('== 二:杀掉一个 follower:剩下 2 个仍是多数,写入照常提交;重启之后落后的 follower 追上')
f1 = [i for i in range(N) if i != L][0]
def put_lat(i, n=100):
    lat = []
    for k in range(n): t0 = time.perf_counter(); s, _ = put(i, f'lat{k}', 'x'); lat.append(time.perf_counter() - t0); assert s == 200
    return statistics.median(lat), sorted(lat)[int(n * 0.99) - 1]
m0, p0 = put_lat(L); kill_node(f1); time.sleep(0.5); m1, p1 = put_lat(L)
print(f'  杀掉 follower t24n{f1}(kill -9)之后,对 leader 写 100 次:中位数 {m1 * 1000:.2f} ms、p99 {p1 * 1000:.2f} ms(杀之前 {m0 * 1000:.2f} ms、p99 {p0 * 1000:.2f} ms);leader 仍是 t24n{leader_idx()}')
[put(L, f'while-down-{i}', 'x') for i in range(50)]; show_status('杀掉 follower 期间又写了 50 次之后:')
t0 = time.time(); start_node(f1)
while True:
    a, b = status(f1), status(L)
    if a and b and a.get('raftAppliedIndex') == b.get('raftAppliedIndex'): break
    if time.time() - t0 > 20: break
    time.sleep(0.02)
print(f'  重启 t24n{f1} 之后 {(time.time() - t0) * 1000:.0f} ms 它的 raftAppliedIndex 追上了 leader'); show_status('追上之后:')

print('== 三:再杀掉两个节点(只剩 1 个,不再是多数):写入不能提交,客户端超时;读也不行(线性一致读要确认自己还是 leader);只剩的节点会让出 leader;而那次超时的写入,等多数回来之后居然还是提交了')
L = wait_leader(); put(L, 'key', 'old'); others = [i for i in range(N) if i != L]; keep = L
for i in others: kill_node(i)
t0 = time.time(); s = None
try: s, d = put(keep, 'key', 'new', timeout=3); print(f'  对唯一存活的 t24n{keep} 写 key = new:返回 {s}')
except Exception as e: print(f'  对唯一存活的 t24n{keep} 写 key = new(客户端超时 3 秒):{type(e).__name__},等了 {time.time() - t0:.1f} s 没有结果 —— 提交不了')
t0 = time.time()
try: r = get(keep, 'key', timeout=3); print(f'  线性一致读 key:{r}(用时 {time.time() - t0:.1f} s)')
except Exception as e: print(f'  线性一致读 key:{type(e).__name__}(等了 {time.time() - t0:.1f} s,拿不到多数的确认)')
print(f'  可串行化读(serializable,只读本节点自己的状态):key = {get(keep, "key", serializable=True)}(那条没提交的 new 没有生效)')
time.sleep(2.0); d = status(keep); print(f'  再过 2 秒,t24n{keep} 报告的 leader 字段 = {d.get("leader", 0) if d else "不可达"}(0 表示没有 leader:它联系不上多数,自己让出了 leader)')
start_node(others[0]); l2 = wait_leader(20)
print(f'  重启一个节点 t24n{others[0]},多数恢复,选出 leader = t24n{l2};此刻线性一致读 key = {get(l2, "key")}')
print('  客户端那次写入虽然超时了,但它已经是 leader 日志里的一条:多数恢复之后被提交了。所以“超时”不等于“没写成功”,只表示“不知道”')
start_node(others[1]); time.sleep(1.0)

print('== 四:Raft 论文图 8 的场景(手写的 5 节点日志模拟,不是 etcd):上一任期的日志条目即使复制到了多数,也不能靠“数副本数”提交,否则已提交的会被覆盖')
class Srv:
    def __init__(self, name): self.name = name; self.log = []; self.term = 0     # log 里是各条日志的任期
    def last(self): return (self.log[-1] if self.log else 0, len(self.log))
def elect(cands, voters, new_term):
    """cands 里第一个人在 new_term 竞选,voters 投票(日志要不比候选人新才投);返回是否赢得多数"""
    c = cands; votes = 1
    for v in voters:
        if v is c: continue
        v.term = max(v.term, new_term)
        if c.last() >= v.last(): votes += 1
    c.term = new_term; return votes >= 3
def append_to(leader, follower, upto):
    follower.log = list(leader.log[:upto]); follower.term = max(follower.term, leader.term)
def scenario(rule):
    S = [Srv(f'S{i + 1}') for i in range(5)]; s1, s2, s3, s4, s5 = S; out = []
    s1.term = 2; s1.log = [1, 2]                                     # (a) S1 在任期 2 当 leader,日志位置 2 的条目(任期 2)只复制到了 S2
    s2.log = [1, 2]
    for s in (s3, s4, s5): s.log = [1]
    s1.log = [1, 2]; out.append('(a) S1(任期 2 的 leader)把位置 2 的条目复制给了 S2,S3、S4、S5 还没有')
    # (b) S1 宕机;S5 凭 S3、S4 的票当选任期 3,在位置 2 追加了自己的条目(任期 3),还没来得及复制
    assert elect(s5, [s3, s4, s5], 3); s5.log = [1, 3]; out.append('(b) S1 宕机,S5 在任期 3 当选(S3、S4 投票,它们的日志不比 S5 新),在位置 2 追加了自己的条目(任期 3),没来得及复制')
    # (c) S5 宕机;S1 重启,凭 S2、S3 的票当选任期 4,把位置 2(任期 2)复制给 S3
    assert elect(s1, [s1, s2, s3], 4); append_to(s1, s3, 2); out.append('(c) S5 宕机,S1 重启并在任期 4 当选(S2、S3 投票),继续复制位置 2 的旧条目(任期 2):现在 S1、S2、S3 都有了它')
    committed = False
    if rule == 'count':                                              # 错误的规则:只要复制到多数就提交
        committed = True; out.append('    按“复制到多数就提交”的规则:S1 把位置 2(任期 2)标成已提交、应用给客户端')
    else:
        out.append('    按 Raft 的规则:任期 4 的 leader 不能靠数副本数提交上一任期的条目;S1 要先在任期 4 追加一条自己的条目(位置 3),复制到多数后,才连同前面的一起提交')
    # (d) S1 宕机;S5 重启并在任期 5 竞选:S5 的日志最后一条任期 3
    if rule == 'term':                                                # 正确规则下 S1 在宕机之前已经把任期 4 的条目复制到了 S2、S3
        s1.log.append(4); append_to(s1, s2, 3); append_to(s1, s3, 3); committed = True; out.append('    S1 的任期 4 条目(位置 3)复制到了 S2、S3,多数达成,位置 2 与 3 一起提交')
    for s in (s5, s2, s3, s4): pass
    won = elect(s5, [s5, s2, s3, s4], 5)
    out.append(f'(d) S1 宕机,S5 重启在任期 5 竞选:能不能当选 = {won}(S2、S3、S4 要检查 S5 的日志是否“不比自己旧”)')
    if won:
        for s in (s2, s3, s4, s1): s.log = list(s5.log[:2]) + (s.log[2:] if False else [])  # S5 当选后把自己的日志强加给大家(位置 2 被覆盖成任期 3)
        out.append('    S5 当选,按 AppendEntries 把自己的日志(位置 2 的任期是 3)复制给大家,覆盖了 S1、S2、S3 上位置 2 的任期 2 条目')
    surv = [s.log[1] if len(s.log) > 1 else None for s in (s1, s2, s3)]
    return out, committed, surv, won
for rule, name in (('count', '规则 A:只要复制到多数就提交(没有“当前任期”的限制)'), ('term', '规则 B:Raft 的规则(只有当前任期的条目才靠数副本数提交,旧任期的条目随它们一起提交)')):
    out, committed, surv, won = scenario(rule); print(f'  {name}'); [print('    ' + l) for l in out]
    print(f'    结果:S5 {"当选了" if won else "没能当选"};已经提交的位置 2 条目现在在 S1、S2、S3 上的任期是 {surv} —— ' + ('已经提交 / 应用过的条目被覆盖了(任期 2 变成 3)' if committed and won else '没有被覆盖'))

print('== 五:提交只等“最快的多数”:3 节点,在 peer 通信上加延迟(代理按“被连接的一方”加延迟,每个方向都延迟);对 leader 写 40 次的延迟中位数。前面几节杀过、重启过节点,这一节换一个全新的集群')
for i in range(N): kill_node(i)
for i in range(N): shutil.rmtree(TT / f'etcd_t24_{i}', ignore_errors=True)
for i in range(N): start_node(i)
L = wait_leader(); assert L is not None; fs = [i for i in range(N) if i != L]; time.sleep(1.0)
def set_delay(i, ms): PX[i].d = ms / 1000.0
rows = []
for name, cfg in (('不加延迟', {}), (f'一个 follower(t24n{fs[0]})的 peer 地址 +20 ms', {fs[0]: 20}), ('两个 follower 的 peer 地址各 +20 ms', {fs[0]: 20, fs[1]: 20}), (f'两个 follower:+20 ms 和 +60 ms', {fs[0]: 20, fs[1]: 60}), (f'leader(t24n{L})的 peer 地址 +20 ms', {L: 20}), ('三个节点的 peer 地址都 +20 ms', {0: 20, 1: 20, 2: 20})):
    for i in range(N): set_delay(i, 0)
    for i, ms in cfg.items(): set_delay(i, ms)
    time.sleep(0.5); med, p99 = put_lat(L, 40); rows.append((name, f'{med * 1000:.1f} ms', f'{p99 * 1000:.1f} ms'))
for i in range(N): set_delay(i, 0)
table(rows, ['配置', '写入延迟中位数', 'p99'])
print('  只有一个 follower 慢时,leader 加上另一个 follower 就是多数,延迟几乎不变;两个 follower 都慢时,延迟随较快的那个上升(+20 和 +60 的配置与两个都 +20 差不多,说明等的是较快的那个,不是较慢的)。代理是按“被连接的一方”加延迟的,每种配置具体延迟了 AppendEntries 还是确认的路径,我没有逐条验证,只看写入延迟的变化')
for i in range(N): kill_node(i)
for p in PX: p.close()
reset(); subprocess.run("pkill -f 'etcd --name t24' 2>/dev/null; true", shell=True)
for i in range(N): shutil.rmtree(TT / f'etcd_t24_{i}', ignore_errors=True)
