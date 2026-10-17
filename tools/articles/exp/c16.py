import sys, os, re, time, subprocess, json, hashlib, urllib.request, urllib.error; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c16')
img('alpine:3.20', 'registry:2')
purge()
P1 = free_port(9700); P2 = free_port(P1 + 1)
def start(name, port, delete):
    opts = ['-e', 'REGISTRY_STORAGE_DELETE_ENABLED=true'] if delete else []
    dk('run', '-d', '--name', name, *LAB, *opts, '-p', f'127.0.0.1:{port}:5000', 'registry:2')
    for _ in range(30):
        try: urllib.request.urlopen(f'http://127.0.0.1:{port}/v2/'); return
        except Exception: time.sleep(0.5)
def store(name):
    n = out('exec', name, 'sh', '-c', "find /var/lib/registry -path '*blobs*' -name data | wc -l")
    k = out('exec', name, 'sh', '-c', "du -sk /var/lib/registry | cut -f1")
    return int(n), int(k)
def mk(tag, seed):
    d = ctx('c16_' + seed, {'Dockerfile': 'FROM alpine:3.20\nCOPY blob.bin /blob.bin\n', 'blob.bin': os.urandom(2 * 1024 * 1024)})
    rc, o = build(d, tag, '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
def http(port, path, method='GET', accept=None):
    rq = urllib.request.Request(f'http://127.0.0.1:{port}{path}', method=method, headers={'Accept': accept} if accept else {})
    try:
        r = urllib.request.urlopen(rq); return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e: return e.code, dict(e.headers), e.read()
OCI = 'application/vnd.oci.image.manifest.v1+json'
print('== 一:默认配置的 registry 不允许删除镜像')
start('bwlab-reg1', P1, False)
mk(f'localhost:{P1}/c16/app:1', 'a')
dk('push', f'localhost:{P1}/c16/app:1', timeout=300)
st, h, _ = http(P1, '/v2/c16/app/manifests/1', method='HEAD', accept=OCI)
dg1 = h['Docker-Content-Digest']
st, h, b = http(P1, f'/v2/c16/app/manifests/{dg1}', method='DELETE')
print(f'  DELETE /v2/c16/app/manifests/<digest> → {st};正文:{b.decode().strip()[:150]}')
print('== 二:开启删除(REGISTRY_STORAGE_DELETE_ENABLED=true)后,推两个镜像:共用 alpine 基础层,各有一个 2 MiB 随机文件')
start('bwlab-reg2', P2, True)
mk(f'localhost:{P2}/c16/app:1', 'a2'); mk(f'localhost:{P2}/c16/app:2', 'b2')
rc, o1 = dk('push', f'localhost:{P2}/c16/app:1', timeout=300)
n1, k1 = store('bwlab-reg2')
rc, o2 = dk('push', f'localhost:{P2}/c16/app:2', timeout=300)
n2, k2 = store('bwlab-reg2')
print(f'  推 app:1 后:registry 磁盘上 blob 文件 {n1} 个,共 {k1} KB')
print(f'  再推 app:2 后:blob 文件 {n2} 个,共 {k2} KB(新增 {n2 - n1} 个文件、{k2 - k1} KB;输出里 "Layer already exists" {o2.count("Layer already exists")} 行)')
print('== 三:删除 app:1 的 manifest')
st, h, _ = http(P2, '/v2/c16/app/manifests/1', method='HEAD', accept=OCI)
dg = h['Docker-Content-Digest']
st, h, b = http(P2, f'/v2/c16/app/manifests/{dg}', method='DELETE')
print(f'  DELETE manifests/<app:1 的 digest> → {st}')
print('  tags/list → ' + http(P2, '/v2/c16/app/tags/list')[2].decode().strip())
st, _, _ = http(P2, '/v2/c16/app/manifests/1', accept=OCI); print(f'  GET manifests/1 → {st}')
n3, k3 = store('bwlab-reg2')
print(f'  删除后磁盘上 blob 文件 {n3} 个,共 {k3} KB(删除前 {n2} 个、{k2} KB)')
print('== 四:registry garbage-collect 才会真正回收')
rc, o = dk('exec', 'bwlab-reg2', 'registry', 'garbage-collect', '--dry-run', '/etc/docker/registry/config.yml')
print(f'  --dry-run:退出码 {rc};输出里 "eligible for deletion" 的行数 {o.count("eligible for deletion")}')
n4, k4 = store('bwlab-reg2'); print(f'  dry-run 之后磁盘:{n4} 个 blob 文件、{k4} KB')
rc, o = dk('exec', 'bwlab-reg2', 'registry', 'garbage-collect', '/etc/docker/registry/config.yml')
print(f'  真正执行:退出码 {rc};输出里 "eligible for deletion" 的行数 {o.count("eligible for deletion")}')
n5, k5 = store('bwlab-reg2'); print(f'  GC 之后磁盘:{n5} 个 blob 文件、{k5} KB(回收了 {n3 - n5} 个文件、{k3 - k5} KB)')
print('== 五:GC 之后留下的镜像还能不能拉')
dk('rmi', '-f', f'localhost:{P2}/c16/app:2')
rc, o = dk('pull', f'localhost:{P2}/c16/app:2', timeout=300); print(f'  docker pull app:2 → 退出码 {rc};{o.strip().splitlines()[-1]}')
rc, o = dk('pull', f'localhost:{P2}/c16/app:1', timeout=60); print(f'  docker pull app:1(已删除)→ 退出码 {rc};{[l for l in o.splitlines() if "rror" in l][0][:120]}')
print('== 六:同一个镜像推到另一个仓库名下')
rc, o = dk('tag', f'localhost:{P2}/c16/app:2', f'localhost:{P2}/c16/other:2')
rc, o = dk('push', f'localhost:{P2}/c16/other:2', timeout=300)
print(f'  push 退出码 {rc};输出里 "Mounted from" 的行数 {o.count("Mounted from")},"Layer already exists" 的行数 {o.count("Layer already exists")}')
print('  ' + ' | '.join(l for l in o.splitlines() if 'Mounted' in l or 'already' in l)[:200])
n6, k6 = store('bwlab-reg2'); print(f'  之后磁盘:{n6} 个 blob 文件、{k6} KB(推之前 {n5} 个、{k5} KB)')
purge()
