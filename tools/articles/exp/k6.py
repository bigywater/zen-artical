import sys, os, re, time, json, yaml; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k6')
cn, _ = up('main')
NS = ns('k6')
rv = lambda name='cm1': ko('get', 'cm', name, '-n', NS, '-o', 'jsonpath={.metadata.resourceVersion}')
data = lambda name='cm1': ko('get', 'cm', name, '-n', NS, '-o', 'jsonpath={.data}')
k('create', 'cm', 'cm1', '-n', NS, '--from-literal=owner=nobody')
r0 = rv()
print(f'集群 {cn};命名空间 {NS} 里有 ConfigMap cm1,data={data()},resourceVersion={r0}')

print('== 一:两个写入者读到同一个版本,先后用 replace 写回——后写的得到 409 Conflict')
y = yaml.safe_load(ko('get', 'cm', 'cm1', '-n', NS, '-o', 'yaml'))    # 两个写入者都读到的版本
ya, yb = json.loads(json.dumps(y)), json.loads(json.dumps(y))
ya['data']['owner'] = 'A'; yb['data']['owner'] = 'B'
rc, o = k('replace', '-f', '-', input=yaml.dump(ya)); print(f'  写入者 A(带着 resourceVersion={r0})replace:退出码 {rc};{o.strip()};现在 resourceVersion={rv()}')
r1 = rv()
rc, o = k('replace', '-f', '-', input=yaml.dump(yb)); print(f'  写入者 B(带着同样的 resourceVersion={r0})replace:退出码 {rc};{o.strip()}')
print(f'  cm1 现在:data={data()} resourceVersion={rv()}(B 的修改没有写进去)')
rc, o = k('get', '--raw', f'/api/v1/namespaces/{NS}/configmaps/cm1', '-v=0', raw=True)
import subprocess
srv = ko('config', 'view', '--minify', '-o', 'jsonpath={.clusters[0].cluster.server}')
tok = ko('create', 'token', 'default', '-n', NS)

print('== 二:哪些写法会冲突——patch 和 replace 带不带 resourceVersion')
rc, o = k('patch', 'cm', 'cm1', '-n', NS, '--type=merge', '-p', json.dumps({'metadata': {'resourceVersion': r0}, 'data': {'owner': 'C'}}))
print(f'  merge patch 里带着旧的 resourceVersion={r0}:退出码 {rc};{o.strip()}')
rc, o = k('patch', 'cm', 'cm1', '-n', NS, '--type=merge', '-p', json.dumps({'data': {'owner': 'D'}}))
print(f'  merge patch 不带 resourceVersion:退出码 {rc};{o.strip()};data={data()}')
y2 = json.loads(json.dumps(y)); y2['metadata'].pop('resourceVersion', None); y2['data']['owner'] = 'E'
rc, o = k('replace', '-f', '-', input=yaml.dump(y2)); print(f'  replace 的 YAML 里去掉 resourceVersion:退出码 {rc};{o.strip()};data={data()}(ConfigMap 允许无条件更新)')
y3 = json.loads(json.dumps(y)); y3['data']['owner'] = 'F'
rc, o = k('apply', '-f', '-', input=yaml.dump({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'cm1', 'namespace': NS}, 'data': {'owner': 'F'}})); print(f'  kubectl apply(它自己先读最新的再算 patch,不带 resourceVersion):退出码 {rc};{"没有冲突" if rc == 0 else o.strip()[:100]};data={data()}')

print('== 三:resourceVersion 就是 etcd 里的修订号(mod_revision),只有真正的修改才会让它变化')
def etcd_kv(key):
    rc, o = k('exec', '-n', 'kube-system', f'etcd-{cn}-control-plane', '--', 'etcdctl', '--endpoints=https://127.0.0.1:2379', '--cacert=/etc/kubernetes/pki/etcd/ca.crt', '--cert=/etc/kubernetes/pki/etcd/server.crt', '--key=/etc/kubernetes/pki/etcd/server.key', 'get', key, '-w', 'json', raw=True)
    return json.loads(o)['kvs'][0]
kv_ = etcd_kv(f'/registry/configmaps/{NS}/cm1')
print(f'  cm1:metadata.resourceVersion={rv()};etcd 里这个 key 的 mod_revision={kv_["mod_revision"]},create_revision={kv_["create_revision"]}(创建时的 resourceVersion 是 {r0})')
r_before = rv(); k('label', 'cm', 'cm1', '-n', NS, 'x=1'); a = rv()
rc, o = k('label', 'cm', 'cm1', '-n', NS, 'x=1', '--overwrite'); b = rv()
print(f'  打标签 x=1:{r_before} → {a};再打一次一模一样的 x=1:{o.strip()},resourceVersion {a} → {b}(没有变化)')
k('label', 'cm', 'cm1', '-n', NS, 'x=2', '--overwrite'); c = rv(); print(f'  改成 x=2:{b} → {c}')
k('create', 'cm', 'cm2', '-n', NS, '--from-literal=a=1'); k('create', 'cm', 'cm3', '-n', NS, '--from-literal=a=1')
print(f'  之后创建 cm2、cm3:resourceVersion 分别是 {rv("cm2")}、{rv("cm3")}——所有对象共用 etcd 的同一个递增序列,数字大小可以比较先后(但官方说它是不透明的字符串)')

print('== 四:按 resourceVersion 读——读到过去的状态,以及读一个还不存在的未来版本')
rc, o = k('get', '--raw', f'/api/v1/namespaces/{NS}/configmaps?resourceVersion={r0}&resourceVersionMatch=Exact', raw=True)
try:
    j = json.loads(o); print(f'  list?resourceVersion={r0}&resourceVersionMatch=Exact(cm1 创建时的版本):cm1 的 data={next(i.get("data") for i in j["items"] if i["metadata"]["name"] == "cm1")}(现在是 {data()});list 的 resourceVersion={j["metadata"]["resourceVersion"]}')
except Exception: print('  Exact 读:' + o.strip()[:200])
rc, o = k('get', '--raw', f'/api/v1/namespaces/{NS}/configmaps?resourceVersion=1&resourceVersionMatch=Exact', raw=True)
print(f'  resourceVersion=1(早已被压缩掉)Exact:{o.strip()[:230]}')
cur = json.loads(ko('get', '--raw', f'/api/v1/namespaces/{NS}/configmaps'))['metadata']['resourceVersion']
big = int(cur) + 1000000
t0 = time.time(); rc, o = k('get', '--raw', f'/api/v1/namespaces/{NS}/configmaps?resourceVersion={big}', raw=True, timeout=130)
print(f'  list?resourceVersion={big}(当前是 {cur}):{time.time() - t0:.1f} 秒后返回;{o.strip()[:260]}')
rc, o = k('get', '--raw', f'/api/v1/namespaces/{NS}/configmaps?resourceVersion=0', raw=True)
print(f'  list?resourceVersion=0(任意版本,可以走缓存):items={len(json.loads(o)["items"])} 个')
rmns(NS)
