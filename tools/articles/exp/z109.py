import sys, os, time, json, re, threading, hashlib, random, statistics, base64, http.client, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from etcdl import EtcdCluster, b64
from kazoo.recipe.watchers import DataWatch, ChildrenWatch
from kazoo.security import make_digest_acl
from kazoo.exceptions import NoNodeError, NoAuthError
tee('z109'); R = {}
random.seed(7)
n = Node('z109', 7300, xmx=384, conf={'tickTime': 1000, 'maxClientCnxns': 500}).start(); z = client('127.0.0.1:7300')
ec = EtcdCluster('z109e', 1, base=7600).start(); E = ec.nodes[0]
class EC:
    def __init__(self): self.c = http.client.HTTPConnection('127.0.0.1', E.cport, timeout=10)
    def call(self, path, body):
        self.c.request('POST', path, json.dumps(body), {'Content-Type': 'application/json'}); r = self.c.getresponse(); d = r.read(); return json.loads(d or b'{}')
    def put(self, k, v, lease=None): return self.call('/v3/kv/put', dict(key=b64(k), value=b64(v), **({'lease': lease} if lease else {})))
    def delete(self, k): return self.call('/v3/kv/deleterange', {'key': b64(k)})
    def range(self, k, end=None, limit=0): 
        b = {'key': b64(k)}
        if end: b['range_end'] = b64(end)
        if limit: b['limit'] = limit
        return self.call('/v3/kv/range', b)
    def txn_put(self, items): return self.call('/v3/kv/txn', {'success': [{'request_put': {'key': b64(k), 'value': b64(v)}} for k, v in items]})
def prefix_end(p): return p[:-1] + chr(ord(p[-1]) + 1)
def etcd_all(prefix='/'):
    out_ = {}; key = prefix; end = prefix_end(prefix); e = EC()
    while True:
        d = e.range(key, end, 1000); kvs = d.get('kvs', [])
        for kv_ in kvs: out_[base64.b64decode(kv_['key']).decode()] = (base64.b64decode(kv_.get('value', '')).decode('latin1'), int(kv_.get('version', 0)), int(kv_.get('mod_revision', 0)))
        if not d.get('more'): break
        key = base64.b64decode(kvs[-1]['key']).decode() + '\x00'
    return out_
NOAUTH = []
def zk_all(c, root='/'):
    out_ = {}; stack = [root]
    while stack:
        p = stack.pop()
        try: data, st = c.get(p)
        except NoNodeError: continue
        except NoAuthError: NOAUTH.append(p); continue
        if p != '/': out_[p] = (data.decode('latin1'), st)
        try: kids = c.get_children(p)
        except NoNodeError: continue
        for k in kids:
            q = p.rstrip('/') + '/' + k
            if not q.startswith('/zookeeper'): stack.append(q)
    return out_
print('== 一:造一份数据:/app 下 20 个服务 × 4 个环境 × 若干配置项(分层配置)、/queue 下 30 个顺序节点、10 个临时节点、5 个带 digest ACL 的节点')
acl = [make_digest_acl('admin', 'pw', all=True)]
t0 = time.time(); z.ensure_path('/app'); z.ensure_path('/queue'); z.ensure_path('/live')
cnt = 0
for s in range(20):
    for env in ('dev', 'test', 'stg', 'prod'):
        base = f'/app/svc{s:02d}/{env}'; z.ensure_path(base)
        for k in range(60): z.create_async(f'{base}/key{k:02d}', ('v' * random.randint(20, 200)).encode()); cnt += 1
for i in range(30): z.create('/queue/job-', f'task {i}'.encode(), sequence=True)
eph = [client('127.0.0.1:7300') for _ in range(10)]
for i, c in enumerate(eph): c.create(f'/live/node{i}', b'alive', ephemeral=True)
for i in range(5): z.create(f'/app/svc00/prod/secret{i}', b'top-secret', acl=acl)
time.sleep(2); src0 = zk_all(z); na0 = list(NOAUTH); NOAUTH.clear()
print(f'  先用没有任何凭据的迁移工具遍历:读到 {len(src0)} 个 znode,其中 {len(na0)} 个因 ACL 拒绝而读不了(NoAuthError):{sorted(na0)[:2]}…')
z.add_auth('digest', 'admin:pw'); src = zk_all(z); mt = kv(n.four('mntr')); R['noauth'] = dict(without=len(src0), blocked=len(na0), with_auth=len(src))
print(f'  给迁移工具加上 digest 凭据(add_auth)后遍历:{len(src)} 个 znode')
kinds = dict(total=len(src), ephemeral=sum(1 for p, (d, st) in src.items() if st.ephemeralOwner), sequential=sum(1 for p in src if p.startswith('/queue/job-')))
acl_n = sum(1 for p in src if p.startswith('/app/svc00/prod/secret'))
print(f'  znode 总数 {kinds["total"]}(不含 /zookeeper),临时节点 {kinds["ephemeral"]},顺序节点 {kinds["sequential"]},带 ACL 的节点 {acl_n};建数据用时 {time.time() - t0:.1f} s'); R['src'] = dict(kinds, acl=acl_n)
print()
print('== 二:整体搬迁:遍历 ZooKeeper(路径 → 数据),每 100 个 key 一个 etcd 事务写入;key 就是 znode 路径')
t0 = time.time(); e = EC(); items = [(p, d) for p, (d, st) in src.items()]; [e.txn_put(items[i:i + 100]) for i in range(0, len(items), 100)]; t_copy = time.time() - t0
print(f'  {len(items)} 个 key 写入 etcd,用时 {t_copy:.2f} s({len(items) / t_copy:.0f} key/s)'); R['copy'] = dict(n=len(items), s=t_copy)
print()
print('== 三:核对:把 etcd 里的全部 key 读回,与 ZooKeeper 的内容逐个比较(路径集合、数据)')
dst = etcd_all('/'); same_keys = set(dst) == set(src); diff = [p for p in src if p in dst and dst[p][0] != src[p][0]]
sha = lambda m: hashlib.sha256(''.join(f'{p}={v[0]}\n' for p, v in sorted(m.items())).encode('latin1')).hexdigest()[:16]
print(f'  路径集合相同:{same_keys}(ZooKeeper {len(src)} / etcd {len(dst)});数据不同的 key:{len(diff)};整体 sha256 前 16 位:ZK {sha(src)} / etcd {sha(dst)}'); R['verify'] = dict(same=same_keys, diff=len(diff), sha_eq=sha(src) == sha(dst))
print()
print('== 四:语义上「搬不过去」的东西(都是实测)')
p = '/app/svc00/prod/key00'; print(f'  版本号:ZooKeeper 里 {p} 的 version={src[p][1].version}(czxid={src[p][1].czxid:#x});搬到 etcd 后 version={dst[p][1]},mod_revision={dst[p][2]} —— 版本信息被重置,依赖 version 做 CAS 的客户端要重新读')
print(f'  临时节点:ZooKeeper 里 /live/node* 是临时节点(属于 10 个会话);etcd 里它们现在是普通 key。关闭那 10 个 ZooKeeper 会话后:ZooKeeper 剩 ', end='')
[c.stop() for c in eph]; time.sleep(1.5); left = [k for k in z.get_children('/live')]; print(f'{len(left)} 个,etcd 里仍有 {sum(1 for k in dst if k.startswith("/live/"))} 个 —— 要自己用租约重建「会话消失就删除」的语义')
R['eph'] = dict(zk_left=len(left), etcd_left=sum(1 for k in dst if k.startswith('/live/')))
print(f'  ACL:ZooKeeper 里 {acl_n} 个节点带 digest ACL;搬到 etcd 后,读回来的字段只有 key、value、version、revision,没有 ACL 信息(etcd 的授权是另一套机制,我没有配置,也就没有迁移任何访问控制)')
print(f'  顺序节点:/queue/job-0000000000… 搬过去只是普通 key(序号只是名字的一部分);之后想继续「建节点时自动加序号」,要自己用事务实现,这里没有实现')
try: kids_zk = z.get_children('/app/svc1')
except NoNodeError: kids_zk = None
d1 = EC().range('/app/svc1', prefix_end('/app/svc1')); d2 = EC().range('/app/svc1/', prefix_end('/app/svc1/'))
print(f'  「列出 /app/svc1 的子节点」:ZooKeeper 里 /app/svc1 {"不存在(服务名是 svc10–svc19)" if kids_zk is None else "存在"};etcd 用前缀 /app/svc1 查询返回 {len(d1.get("kvs", []))} 个 key(把 svc10~svc19 全匹配了),用 /app/svc1/ 查询返回 {len(d2.get("kvs", []))} 个')
R['prefix'] = dict(no_slash=len(d1.get('kvs', [])), slash=len(d2.get('kvs', [])))
d3 = EC().range('/app/svc00/', prefix_end('/app/svc00/')); print(f'  「列出 /app/svc00 的子节点」:ZooKeeper 的 get_children 返回 {len(z.get_children("/app/svc00"))} 个直接子节点({z.get_children("/app/svc00")});etcd 的前缀查询 /app/svc00/ 返回 {len(d3.get("kvs", []))} 个 key(整棵子树,要自己按层级过滤出直接子节点)'); R['subtree'] = dict(zk=len(z.get_children('/app/svc00')), etcd=len(d3.get('kvs', [])))
print()
print('== 五:切换期间的增量同步:用 ZooKeeper 的 watch 追踪变化并写到 etcd(DataWatch + ChildrenWatch,覆盖新建、修改、删除),同时对 ZooKeeper 做 300 次随机变更')
class Syncer:
    def __init__(self, c, root='/app'):
        self.c = c; self.e = EC(); self.lock = threading.Lock(); self.watched = set(); self.lag = []; self.ts = {}; self.root = root
    def start(self, paths):
        for p in paths: self.watch(p)
    def watch(self, p):
        if p in self.watched: return
        self.watched.add(p); DataWatch(self.c, p, lambda d, st, p=p: self.on_data(p, d, st)); ChildrenWatch(self.c, p, lambda kids, p=p: self.on_kids(p, kids))
    def on_data(self, p, d, st):
        with self.lock:
            if d is None: self.e.delete(p)
            else:
                self.e.put(p, d.decode('latin1')); t = self.ts.pop(p, None)
                if t: self.lag.append(time.time() - t)
    def on_kids(self, p, kids):
        for k in kids: self.watch(p.rstrip('/') + '/' + k)
paths = [p for p in src if p.startswith('/app/') and p.count('/') <= 3 or p == '/app']
sy = Syncer(z); t0 = time.time(); sy.start(['/app'] + [p for p in src if p.startswith('/app')]); time.sleep(3)
print(f'  同步器为 {len(sy.watched)} 个 znode 挂了 watch(挂完用时 {time.time() - t0:.1f} s)')
mt2 = kv(n.four('mntr')); R['sync_watches'] = int(mt2['zk_watch_count'])
plist = [p for p in src if p.startswith('/app/svc') and '/key' in p]; ops = collections.Counter()
for i in range(300):
    r = random.random(); base = random.choice(plist).rsplit('/', 1)[0]
    try:
        if r < 0.6: p = random.choice(plist); sy.ts[p] = time.time(); z.set(p, f'upd{i}'.encode()); ops['改'] += 1
        elif r < 0.85: p = f'{base}/new{i}'; sy.ts[p] = time.time(); z.create(p, f'new{i}'.encode()); ops['建'] += 1; plist.append(p)
        else: p = random.choice(plist); z.delete(p); ops['删'] += 1; plist.remove(p)
    except NoNodeError: pass
    time.sleep(0.02)
time.sleep(3)
src2 = {p: v for p, v in zk_all(z, '/app').items()}; dst2 = {p: v for p, v in etcd_all('/app').items()}
miss = [p for p in src2 if p not in dst2]; extra = [p for p in dst2 if p not in src2 and p != '/app']; bad = [p for p in src2 if p in dst2 and dst2[p][0] != src2[p][0]]
print(f'  变更 {dict(ops)};同步后 /app 子树:ZooKeeper {len(src2)} / etcd {len(dst2)};etcd 缺少 {len(miss)} 个、多出 {len(extra)} 个、数据不同 {len(bad)} 个')
if sy.lag: print(f'  「修改 / 新建」从 ZooKeeper 写入返回到 etcd 里写完的延迟:中位 {statistics.median(sy.lag) * 1000:.0f} ms,最大 {max(sy.lag) * 1000:.0f} ms({len(sy.lag)} 个样本)')
R['sync'] = dict(ops=dict(ops), zk=len(src2), etcd=len(dst2), miss=len(miss), extra=len(extra), bad=len(bad), lag_med=statistics.median(sy.lag) * 1000 if sy.lag else None, lag_max=max(sy.lag) * 1000 if sy.lag else None)
print('  差异示例:', (miss + extra + bad)[:4])
z.stop(); ec.stop(); n.stop(); save('z109', R); os._exit(0)
