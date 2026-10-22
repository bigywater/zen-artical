import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import hashlib, bisect, zlib
tee('v19'); reset()
print('哈希分片的问题:节点增减时有多少 key 的归属会变。对照三种:取模(hash(key) mod N)、手写的一致性哈希环(每个节点放 vnodes 个虚拟节点,key 顺时针找第一个虚拟节点)、nginx 的 hash $key consistent(ketama)。key 都是 "key0" 到 "keyN" 这样的字符串')
def h64(s): return int.from_bytes(hashlib.md5(s.encode()).digest()[:8], 'big')
class Ring:
    def __init__(s, nodes, vnodes=100, weights=None):
        s.pts = []
        for n in nodes:
            for v in range(int(vnodes * (weights.get(n, 1) if weights else 1))): s.pts.append((h64(f'{n}#{v}'), n))
        s.pts.sort(); s.keys = [p[0] for p in s.pts]
    def get(s, key):
        i = bisect.bisect(s.keys, h64(key)) % len(s.keys); return s.pts[i][1]
def modn(nodes): 
    return lambda key: nodes[h64(key) % len(nodes)]

# ============ 一 ============
print('== 一:取模 vs 一致性哈希环。100000 个 key,10 个节点;分别 加 1 个节点(10 → 11)和 去掉 1 个节点(10 → 9),统计归属变了的 key 的比例;理论值:加一个节点时,理想情况下只需要 1/11 ≈ 9.1% 的 key 搬到新节点;去掉一个时 1/10 = 10%。vnodes 是每个节点的虚拟节点数;“负载不均”= 最忙节点的 key 数 ÷ 平均数')
keys = [f'key{i}' for i in range(100000)]
N10 = [f'n{i}' for i in range(10)]
def stats(f10, f11, f9):
    a10 = [f10(k) for k in keys]; a11 = [f11(k) for k in keys]; a9 = [f9(k) for k in keys]
    c = collections.Counter(a10)
    return sum(1 for x, y in zip(a10, a11) if x != y) / len(keys), sum(1 for x, y in zip(a10, a9) if x != y) / len(keys), max(c.values()) / (len(keys) / 10)
rows = []
m = stats(modn(N10), modn(N10 + ['n10']), modn(N10[:-1])); rows.append(('取模', '-', f'{m[0]:.1%}', f'{m[1]:.1%}', f'{m[2]:.2f}'))
for vn in (1, 10, 100, 1000):
    r10, r11, r9 = Ring(N10, vn), Ring(N10 + ['n10'], vn), Ring(N10[:-1], vn); m = stats(r10.get, r11.get, r9.get)
    rows.append(('一致性哈希环', vn, f'{m[0]:.1%}', f'{m[1]:.1%}', f'{m[2]:.2f}'))
table(rows, ['算法', 'vnodes', '加 1 个节点:归属变了', '去掉 1 个节点:归属变了', '10 个节点时的负载不均(最忙 ÷ 平均)'])

# ============ 二 ============
print('== 二:nginx 的真实表现。4 个后端 A、B、C、D;2000 个请求,每个带不同的 X-Key;先发一遍记下每个 key 落到谁;然后 reload 成 5 个后端(加 E)再发一遍;再 reload 成 3 个后端(去掉 D,即 A、B、C)再发一遍。比较 hash $http_x_key(普通)与 hash $http_x_key consistent(ketama)归属变了的 key 的比例')
SV = {n: Svc((lambda t: (lambda h: h.reply(200, t.encode())))(n)) for n in 'ABCDE'}
def body(names, cons):
    return f'hash $http_x_key{" consistent" if cons else ""}; ' + ' '.join(f'server 127.0.0.1:{SV[n].port};' for n in names)
def assign(ng, n=2000):
    out = []
    for i in range(n):
        st, b, _ = rpc(ng.port, '/', 5.0, {'X-Key': f'k{i}'}); out.append(b.decode())
    return out
rows = []
for cons in (False, True):
    ng = Nginx('v19n', 'upstream u { %s } server { listen {port}; location / { proxy_pass http://u; } }' % body('ABCD', cons)).start()
    a4 = assign(ng); c4 = collections.Counter(a4)
    ng.write('upstream u { %s } server { listen {port}; location / { proxy_pass http://u; } }' % body('ABCDE', cons)); ng.reload(); time.sleep(0.6); a5 = assign(ng)
    ng.write('upstream u { %s } server { listen {port}; location / { proxy_pass http://u; } }' % body('ABC', cons)); ng.reload(); time.sleep(0.6); a3 = assign(ng)
    ng.stop()
    ch5 = sum(1 for x, y in zip(a4, a5) if x != y) / len(a4); ch3 = sum(1 for x, y in zip(a4, a3) if x != y) / len(a4)
    moved_to_E = sum(1 for x, y in zip(a4, a5) if x != y and y == 'E') / max(1, sum(1 for x, y in zip(a4, a5) if x != y))
    ch3_fromD = sum(1 for x, y in zip(a4, a3) if x != y and x != 'D')
    rows.append(('consistent(ketama)' if cons else '普通 hash', ' / '.join(str(c4[n]) for n in 'ABCD'), f'{ch5:.1%}', f'{moved_to_E:.0%}', f'{ch3:.1%}', ch3_fromD))
table(rows, ['指令', '4 个后端时 A / B / C / D 各收到', '加 E:归属变了', '其中搬到了新节点 E 的占比', '去掉 D:归属变了', '去掉 D 时原本不在 D 上却被搬走的 key 数'])
print('  理想值:加第 5 个节点只需搬 1/5 = 20% 的 key(都搬到 E);去掉 D 只需搬原本在 D 上的 key(约 25%),其余 key 不动')

# ============ 三 ============
print('== 三:有权重的节点和热点 key。手写的环上,节点 n0 的权重为 3、其余 9 个节点权重为 1(vnodes = 100 × 权重),100000 个均匀的 key:n0 应该分到 3/12 = 25%。热点:再让 1 个 key 占总流量的 10%(其余均匀),看这 10% 落在哪个节点上——一致性哈希只管 key 的归属,不管 key 的热度')
ring = Ring(N10, 100, {'n0': 3}); c = collections.Counter(ring.get(k) for k in keys)
print('  按权重分:n0 =', f'{c["n0"] / len(keys):.1%}', '(理论 25.0%);其余 9 个节点各自:', ' / '.join(f'{c[n] / len(keys):.1%}' for n in N10[1:]))
load = collections.Counter()
rng = random.Random(5)
for i in range(200000):
    k = 'HOT' if rng.random() < 0.10 else f'key{rng.randrange(100000)}'; load[Ring.get(ring, k)] += 1
hot = ring.get('HOT'); tot = sum(load.values())
print(f'  热点 key 落在 {hot}(权重 {3 if hot == "n0" else 1}):它的负载占全部流量的 {load[hot] / tot:.1%};按权重本来应该占 {(3 if hot == "n0" else 1) / 12:.1%}。其余各节点的负载占比:', ' / '.join(f'{n}={load[n] / tot:.1%}' for n in N10))
