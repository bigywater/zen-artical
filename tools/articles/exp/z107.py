import sys, os, time, json, re, subprocess, shutil, base64, signal; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from etcdl import EtcdCluster, b64
tee('z107'); R = {}
K = HERE.parent / 'k8s'; APIS = K / 'kube-apiserver'; WD = ZDATA / 'z107'; shutil.rmtree(WD, ignore_errors=True); WD.mkdir(parents=True)
subprocess.run(['openssl', 'genrsa', '-out', str(WD / 'sa.key'), '2048'], capture_output=True); subprocess.run(['openssl', 'rsa', '-in', str(WD / 'sa.key'), '-pubout', '-out', str(WD / 'sa.pub')], capture_output=True)
(WD / 'tokens.csv').write_text('zkbook-token,admin,1001,"system:masters"\n'); ver = subprocess.run([str(APIS), '--version'], capture_output=True, text=True).stdout.strip()
def apiserver(etcd_url, port, name):
    f = WD / f'{name}.log'
    return subprocess.Popen([str(APIS), f'--etcd-servers={etcd_url}', f'--secure-port={port}', '--bind-address=127.0.0.1', f'--cert-dir={WD}/certs-{name}', f'--service-account-issuer=https://zkbook.local', f'--service-account-key-file={WD}/sa.pub', f'--service-account-signing-key-file={WD}/sa.key', '--service-cluster-ip-range=10.77.0.0/24', f'--token-auth-file={WD}/tokens.csv', '--authorization-mode=AlwaysAllow', '--v=1'], stdout=open(f, 'w'), stderr=subprocess.STDOUT)
import ssl, urllib.request
_ctx = ssl.create_default_context(); _ctx.check_hostname = False; _ctx.verify_mode = ssl.CERT_NONE
def api(port, method, path, body=None, ctype='application/json', timeout=10):
    req = urllib.request.Request(f'https://127.0.0.1:{port}{path}', data=(json.dumps(body).encode() if body is not None else None), method=method, headers={'Content-Type': ctype, 'Authorization': 'Bearer zkbook-token'})
    try:
        r = urllib.request.urlopen(req, context=_ctx, timeout=timeout); return r.status, r.read().decode()
    except urllib.error.HTTPError as e: return e.code, e.read().decode()
    except Exception as e: return 0, type(e).__name__ + ' ' + str(e)[:80]
def rv_of(port, path): return json.loads(api(port, 'GET', path)[1])['metadata']['resourceVersion']
def etcdctl(*a): return subprocess.run(['etcdctl', '--endpoints=http://127.0.0.1:7600', *a], capture_output=True, text=True).stdout
ec = EtcdCluster('z107e', 1, base=7600).start()
print(f'== 一:kube-apiserver(从 dl.k8s.io 的 kubernetes-src.tar.gz 的 v1.37.1 源码用 go build 编出 darwin/arm64,所以 --version 显示 {ver}),只配 --etcd-servers=本机 etcd 3.7.2,启动后 etcd 里是什么')
ap = apiserver('http://127.0.0.1:7600', 7651, 'a1'); t0 = time.time()
while time.time() - t0 < 120:
    if api(7651, 'GET', '/readyz')[1].strip() == 'ok': break
    time.sleep(1)
print(f'  GET /readyz → {api(7651, "GET", "/readyz")[1].strip()},启动到就绪 {time.time() - t0:.0f} s')
keys = [k for k in etcdctl('get', '/registry', '--prefix', '--keys-only').splitlines() if k.strip()]
tops = sorted({k.split('/')[2] for k in keys}); print(f'  etcd 里 /registry 下共 {len(keys)} 个 key,第一级分类 {len(tops)} 种,前 14 种:{tops[:14]}'); R['k0'] = dict(n=len(keys), tops=tops[:14])
print()
print('== 二:用 REST 调用建一个 namespace 与一个 ConfigMap,在 etcd 里找到它们')
print('  POST /api/v1/namespaces →', api(7651, 'POST', '/api/v1/namespaces', {'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': 'demo'}})[0]); print('  POST /api/v1/namespaces/demo/configmaps →', api(7651, 'POST', '/api/v1/namespaces/demo/configmaps', {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'cm1'}, 'data': {'a': 'b'}})[0], '(201 = 创建成功)')
ks = [k for k in etcdctl('get', '/registry', '--prefix', '--keys-only').splitlines() if 'demo' in k or 'cm1' in k]; print('  etcd 里含 demo / cm1 的 key:', ks); R['keys'] = ks
raw = subprocess.run(['etcdctl', '--endpoints=http://127.0.0.1:7600', 'get', '/registry/configmaps/demo/cm1', '--print-value-only'], capture_output=True).stdout
print(f'  值的前 12 个字节:{raw[:12]!r}(Kubernetes 的 protobuf 存储格式前缀 k8s\\x00),总长 {len(raw)} 字节;值里可见的字符串:{[x.decode() for x in re.findall(rb"[ -~]{3,}", raw)][:6]}'); R['magic'] = raw[:4].hex()
print()
print('== 三:resourceVersion 就是 etcd 的 revision:API 返回的 metadata.resourceVersion 与 etcd 里该 key 的 mod_revision')
rv = rv_of(7651, '/api/v1/namespaces/demo/configmaps/cm1'); js = json.loads(etcdctl('get', '/registry/configmaps/demo/cm1', '-w', 'json'))
mr = js['kvs'][0]['mod_revision']; print(f'  resourceVersion = {rv};etcd mod_revision = {mr};相等:{str(mr) == rv}'); R['rv'] = dict(rv=rv, mod=mr)
print('  PATCH 修改 data.a → c:', api(7651, 'PATCH', '/api/v1/namespaces/demo/configmaps/cm1', {'data': {'a': 'c'}}, 'application/merge-patch+json')[0])
rv2 = rv_of(7651, '/api/v1/namespaces/demo/configmaps/cm1'); js2 = json.loads(etcdctl('get', '/registry/configmaps/demo/cm1', '-w', 'json')); print(f'  修改后 resourceVersion = {rv2};etcd mod_revision = {js2["kvs"][0]["mod_revision"]};相等:{str(js2["kvs"][0]["mod_revision"]) == rv2}'); R['rv2'] = str(js2['kvs'][0]['mod_revision']) == rv2
print()
print('== 四:能不能把 --etcd-servers 指向 ZooKeeper(我的 7300 端口)?把同一个 kube-apiserver 的 --etcd-servers 改成 http://127.0.0.1:7300')
ap.terminate(); ap.wait(20)
zn = Node('z107z', 7300, xmx=256, conf={'tickTime': 1000}).start()
ap2 = apiserver('http://127.0.0.1:7300', 7652, 'a2'); time.sleep(60)
st, bd = api(7652, 'GET', '/readyz'); print(f'  60 秒后 GET https://127.0.0.1:7652/readyz → {st} {bd[:60]};apiserver 进程{"仍在运行" if ap2.poll() is None else "已退出,退出码 " + str(ap2.poll())}')
lg = (WD / 'a2.log').read_text().splitlines(); errl = [re.sub(r'^\S+\s+\d+\s+', '', l)[:230] for l in lg if l[:1] in 'EW' and 'FLAG' not in l]
print(f'  日志里的 E / W 行共 {len(errl)} 行,前 3 行与最后 1 行:'); [print('    ' + l) for l in errl[:3] + errl[-1:]]
print('  日志里是否出现 "Serving securely"(开始对外服务):', any('Serving securely' in l for l in lg)); R['zk_try'] = dict(status=st, alive=ap2.poll() is None, serving=any('Serving securely' in l for l in lg), first=errl[:3])
ap2.kill()
ec.stop(); zn.stop(); save('z107', R); os._exit(0)
