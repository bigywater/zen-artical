import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
from etcdt import Etcd, b64
tee('v41'); reset()
print('etcd 3.7.2 的 lease(租约):客户端申请一个带 TTL 的 lease,把 key 挂在上面;lease 到期,挂着的 key 一起被删除;客户端定期 keepalive 续约。通过 etcd 自带的 HTTP/JSON 网关(/v3/lease/*、/v3/kv/*)操作,单节点(第四节是 3 节点)。服务发现里“实例的注册信息 = 一个挂在 lease 上的 key,心跳 = keepalive”')
E1 = Etcd('v41', n=1).start()
def call(path, body, i=0): return E1.call(i, path, body)[1]
def grant(ttl, i=0): d = E1.call(i, '/v3/lease/grant', {'TTL': str(ttl)})[1]; return d['ID'], int(d['TTL'])
def put(k, v, lease=None, i=0):
    b = {'key': b64(k), 'value': b64(v)}
    if lease: b['lease'] = lease
    return E1.call(i, '/v3/kv/put', b)[1]
def exists(k, i=0):
    d = E1.call(i, '/v3/kv/range', {'key': b64(k), 'serializable': True})[1]; return bool(d.get('kvs'))
def ttl_info(lid, i=0): return E1.call(i, '/v3/lease/timetolive', {'ID': lid, 'keys': True})[1]

# ============ 一 ============
print('== 一:申请的 TTL 和实际生效、key 实际多久消失。每个 TTL 申请 10 次,key 挂在 lease 上,之后不续约,每 20 ms 查一次 key 还在不在。“实际 TTL”是 etcd 回给客户端的 TTL(服务端可以改大申请值);“消失用了多久”是从申请成功到 key 查不到')
rows = []
for want in (1, 2, 3, 5):
    got_ttl = None; ds = []
    for k in range(10):
        lid, got = grant(want); got_ttl = got; put(f'/lab/k{k}', 'v', lid); t0 = time.perf_counter()
        while exists(f'/lab/k{k}'): time.sleep(0.02)
        ds.append(time.perf_counter() - t0)
    rows.append((f'{want} s', f'{got_ttl} s', f'{min(ds):.2f} s', f'{statistics.median(ds):.2f} s', f'{max(ds):.2f} s'))
table(rows, ['申请的 TTL', 'etcd 回的 TTL', '最短', '中位数', '最长(key 消失用了多久,10 次)'])
print('  etcd 对 TTL 有下限:申请 1 s 实际得到 2 s(我的理解是下限由选举超时推出来,这台默认选举超时 1 s,没有改参数验证);key 消失的时间比 TTL 多约半秒,看起来是 leader 周期性检查到期的 lease(检查周期约 0.5 s,这个周期是我从数据推测的,没有读源码)')

# ============ 二 ============
print('== 二:keepalive。TTL 5 s;三种客户端:(a) 每 TTL/3 ≈ 1.7 s 续约一次;(b) 每 4.5 s 续约一次;(c) 每 5.5 s 续约一次(比 TTL 还长)。共观察 14 秒,看 key 是否一直存在、续约后 timetolive 回报的剩余时间,以及 key 消失的时刻(如果消失了)')
rows = []
for name, iv in (('(a) 每 1.7 s 续约', 1.7), ('(b) 每 4.5 s 续约', 4.5), ('(c) 每 5.5 s 续约', 5.5)):
    lid, _ = grant(5); put('/lab/ka', 'v', lid); t0 = time.perf_counter(); next_ka = iv; gone = None; rem_after = None; n_ka = 0; ok_ka = 0
    while time.perf_counter() - t0 < 14.0:
        t = time.perf_counter() - t0
        if t >= next_ka:
            r = E1.call(0, '/v3/lease/keepalive', {'ID': lid})[1]; n_ka += 1
            if 'result' in r and int(r['result'].get('TTL', 0)) > 0: ok_ka += 1; rem_after = r['result']['TTL']
            next_ka += iv
        if gone is None and not exists('/lab/ka'): gone = t
        time.sleep(0.05)
    rows.append((name, '一直存在' if gone is None else f'{gone:.1f} s 时消失', f'{ok_ka} / {n_ka}', rem_after))
table(rows, ['续约方式', 'key', '续约成功 / 发出', '续约响应里的 TTL'])
print('  续约把剩余时间重置为完整的 TTL(响应里的 TTL 是 5);续约间隔小于 TTL 才能保住租约;lease 一旦过期,之后发出的 keepalive 就不再成功(上表 (c) 的两次续约响应里都没有大于 0 的 TTL),客户端必须重新申请 lease 并重新写 key')

# ============ 三 ============
print('== 三:一个 lease 挂很多 key。一个 lease 上挂 N 个 key(每个 100 字节),然后 revoke(或到期),看 revoke 要多久、之后 key 是否都消失了。再对比:N 个 key 各挂自己的 lease(每个 lease 一个 key),逐个 revoke 的总时间')
rows = []
for n in (100, 1000, 10000):
    lid, _ = grant(60)
    for k in range(n): put(f'/lab/m/{k}', 'x' * 100, lid)
    t0 = time.perf_counter(); E1.call(0, '/v3/lease/revoke', {'ID': lid}); dt = time.perf_counter() - t0
    left = int(E1.call(0, '/v3/kv/range', {'key': b64('/lab/m/'), 'range_end': b64('/lab/m0'), 'count_only': True, 'serializable': True})[1].get('count', 0))
    lids = []
    for k in range(min(n, 1000)):
        l2, _ = grant(60); put(f'/lab/s/{k}', 'x' * 100, l2); lids.append(l2)
    t1 = time.perf_counter()
    for l2 in lids: E1.call(0, '/v3/lease/revoke', {'ID': l2})
    dt2 = time.perf_counter() - t1
    rows.append((n, f'{dt * 1000:.1f} ms', left, f'{len(lids)} 个 lease 逐个 revoke', f'{dt2 * 1000:.0f} ms'))
table(rows, ['一个 lease 上挂的 key 数', 'revoke 用时', 'revoke 之后剩余的 key', '对照', '总用时'])
print('  revoke 一次请求就把挂在这个 lease 上的所有 key 删光(之后查询剩余为 0),用时随 key 数增长得很慢;而每个 key 一个 lease 时,要发 N 次 revoke,每次约 10 ms。服务发现里,一个服务实例通常只有一个 key,一个 lease;一个进程注册多个 key(例如多个服务名、多个端口)时,共用一个 lease 比较省')

# ============ 四 ============
print('== 四:leader 切换对 lease 的影响。3 节点 etcd,申请 TTL 10 s 的 lease(挂一个 key),过 6 s(正常剩余约 4 s)杀掉 leader,看新 leader 上 timetolive 回报的剩余时间,以及这个 key 实际在什么时候消失')
C3 = Etcd('v41c', n=3).start(); li = C3.leader_idx(); fol = [i for i in range(3) if i != li][0]
s, d = C3.call(li, '/v3/lease/grant', {'TTL': '10'}); lid = d['ID']; C3.call(li, '/v3/kv/put', {'key': b64('/lab/lk'), 'value': b64('v'), 'lease': lid}); t0 = time.perf_counter()
time.sleep(6.0); before = C3.call(li, '/v3/lease/timetolive', {'ID': lid})[1].get('TTL'); t_kill = time.perf_counter() - t0; C3.kill_node(li)
nl = C3.wait_leader(15); t_new = time.perf_counter() - t0; after = None
for _ in range(20):
    s, d = C3.call(nl, '/v3/lease/timetolive', {'ID': lid}) if nl is not None else (0, {})
    if s == 200: after = d.get('TTL'); break
    time.sleep(0.2)
gone = None
while time.perf_counter() - t0 < 30:
    d = C3.call(nl, '/v3/kv/range', {'key': b64('/lab/lk'), 'serializable': True})[1]
    if not d.get('kvs'): gone = time.perf_counter() - t0; break
    time.sleep(0.1)
table([(f'{t_kill:.1f} s', before, f'{t_new:.1f} s', after, f'{gone:.1f} s' if gone else '未消失')], ['杀 leader 的时刻(申请后)', '杀之前 timetolive 的剩余', '新 leader 选出的时刻', '新 leader 上 timetolive 的剩余', 'key 实际消失的时刻(申请后)'])
print('  原本申请后 10 s 到期;leader 切换之后,新 leader 上 timetolive 回报的剩余时间是完整的 10 s(杀 leader 之前是 3 s),key 因此比原定的到期时间晚得多才消失。我的理解是 lease 的剩余时间只在 leader 的内存里按时钟走,换 leader 之后新 leader 把它们重置为完整的 TTL(这个机制我没有读源码验证,只看到了结果)')
for i in range(3): C3.kill_node(i)
E1.procs[0].kill()
