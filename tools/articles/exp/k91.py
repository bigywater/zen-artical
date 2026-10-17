import sys, os, re, time, json, random, string, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k91')
cn, _ = up('main'); wait_nodes_ready()
POD = f'etcd-{cn}-control-plane'
def etcdctl(*a, input=None, timeout=120):
    return k('exec', '-i', '-n', 'kube-system', POD, '--', 'etcdctl', '--endpoints=https://127.0.0.1:2379', '--cacert=/etc/kubernetes/pki/etcd/ca.crt', '--cert=/etc/kubernetes/pki/etcd/server.crt', '--key=/etc/kubernetes/pki/etcd/server.key', *a, input=input, raw=True, timeout=timeout)
def status():
    rc, o = etcdctl('endpoint', 'status', '-w', 'json'); st = json.loads(o)[0]['Status']
    return dict(db=st['dbSize'], inuse=st['dbSizeInUse'], rev=st['header']['revision'])
mb = lambda b: f'{b / 1048576:.1f} MiB'
VAL = ''.join(random.choices(string.ascii_letters + string.digits, k=100_000))
def put_all(n, prefix='/k91/'):
    for i in range(n): etcdctl('put', f'{prefix}{i:04d}', input=VAL)
print(f'集群 {cn};etcd 是多版本存储(MVCC):每次写都产生新 revision,旧版本留在文件里,直到 compaction 标记可丢弃、defrag 才把文件真正缩小')
rc, o = etcdctl('get', 'compact_rev_key'); print(f'  kube-apiserver 自己每 5 分钟压缩一次;它记下的最后压缩位置 compact_rev_key 的值:{o.strip().splitlines()[-1] if o.strip() else "(没有)"}')
etcdctl('del', '/k91/', '--prefix')
etcdctl('compact', str(status()['rev'])); etcdctl('defrag')
s0 = status(); print(f'  基线:dbSize={mb(s0["db"])};dbSizeInUse={mb(s0["inuse"])};revision={s0["rev"]}')

print('== 一:写 200 个 100KB 的 key')
t0 = time.time(); put_all(200); s1 = status()
print(f'  写 200 个 100KB 的 key({time.time() - t0:.0f} 秒):dbSize={mb(s1["db"])}(+{mb(s1["db"] - s0["db"])});dbSizeInUse={mb(s1["inuse"])};revision {s0["rev"]} → {s1["rev"]}(+{s1["rev"] - s0["rev"]}:200 次写,其余是集群自己的写入)')

print('== 二:同一批 key 覆盖写 3 遍——旧版本都还在')
rev_first = s1['rev']
for r in range(3): put_all(200)
s2 = status(); rc, o = etcdctl('get', '/k91/0000', f'--rev={rev_first - 199}', '-w', 'json'); got = json.loads(o).get('kvs')
print(f'  覆盖写 3 遍后:dbSize={mb(s2["db"])}(+{mb(s2["db"] - s1["db"])});dbSizeInUse={mb(s2["inuse"])};revision {s1["rev"]} → {s2["rev"]}(+{s2["rev"] - s1["rev"]},600 次写加集群自己的写入)——实际有效数据只有 200 个 key 约 {mb(200 * 100_000)},其余都是旧版本')
print(f'  用 --rev={rev_first - 199}(第一遍写入时)读 /k91/0000:{"还能读到,长度 %d 字节" % len(__import__("base64").b64decode(got[0]["value"])) if got else "读不到"}(旧版本还在)')

print('== 三:compact——旧版本被标记为可丢弃,文件并没有变小')
cur = s2['rev']; rc, o = etcdctl('compact', str(cur)); print(f'  etcdctl compact {cur}:{o.strip()}')
rc, o = etcdctl('get', '/k91/0000', f'--rev={rev_first - 199}'); print(f'  再读 --rev={rev_first - 199}:{(re.search(r'(Error:[^"]*compacted|required revision has been compacted)', o) or re.search(r'.{0,10}', o)).group(0)[:140]}')
time.sleep(3); s3 = status(); print(f'  compact 之后:dbSize={mb(s3["db"])}(几乎没变);dbSizeInUse={mb(s3["inuse"])}(降了 {mb(s2["inuse"] - s3["inuse"])})——文件里出现了大量可复用的空闲页,但文件本身不缩')

print('== 四:defrag——把文件真正缩小')
t0 = time.time(); rc, o = etcdctl('defrag'); dt = time.time() - t0; time.sleep(2); s4 = status()
print(f'  etcdctl defrag({dt:.1f} 秒):{[l for l in o.strip().splitlines() if not l.startswith("{")][-1][-90:]};dbSize={mb(s3["db"])} → {mb(s4["db"])};dbSizeInUse={mb(s4["inuse"])}(现在两者接近)')
etcdctl('del', '/k91/', '--prefix'); rc, o = etcdctl('get', '/registry/namespaces/default', '-w', 'fields'); n = status()
etcdctl('compact', str(n['rev'])); etcdctl('defrag'); s5 = status()
print(f'  把测试 key 删掉后再 compact + defrag:dbSize={mb(s5["db"])}(回到基线 {mb(s0["db"])} 附近);revision={s5["rev"]}')
rc, o = k('get', 'pod', '-n', 'kube-system', POD, '-o', 'jsonpath={.spec.containers[0].command}'); fl_ = [x for x in json.loads(o) if 'quota' in x or 'compaction' in x]
print(f'  etcd 的启动参数里 quota-backend-bytes / auto-compaction:{fl_ or "都没有设置,用默认值(db 配额默认 2 GiB;etcd 自己不自动压缩,由 kube-apiserver 每 5 分钟压缩)"}')
