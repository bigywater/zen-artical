import sys, os, re, time, subprocess, json, hashlib, urllib.request, urllib.error, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c15')
img('alpine:3.20', 'registry:2')
purge()
PORT = free_port(9700)
REG = f'localhost:{PORT}'
dk('run', '-d', '--name', 'bwlab-reg', *LAB, '-p', f'127.0.0.1:{PORT}:5000', 'registry:2')
for _ in range(20):
    try: urllib.request.urlopen(f'http://127.0.0.1:{PORT}/v2/'); break
    except Exception: time.sleep(0.5)
def reqs(skip):
    """返回 registry 日志里第 skip 条之后的请求:(方法, 归一化路径, 状态码)。"""
    rc, o = dk('logs', 'bwlab-reg', raw=True)
    rows = []
    for l in o.split('\n'):
        m = re.search(r'http\.request\.method=(\w+) .*?http\.request\.uri="([^"]+)".*?http\.response\.status=(\d+)', l)
        if not m: continue
        rows.append((m.group(1), norm(m.group(2)), int(m.group(3))))
    return rows[skip:], len(rows)
def norm(u):
    u = u.split('?')[0]
    u = re.sub(r'/uploads/[0-9a-f-]{36}', '/uploads/<uuid>', u)
    u = re.sub(r'sha256:[0-9a-f]{64}', lambda m: 'sha256:' + m.group(0)[7:13] + '…', u)
    return u
def show(rows):
    cnt = collections.Counter(rows)
    seen = []
    for r in rows:
        if r in seen: continue
        seen.append(r)
        print(f'    {r[0]:5s} {r[1]}  → {r[2]}' + (f'  (共 {cnt[r]} 次)' if cnt[r] > 1 else ''))
print('== 一:registry 是一个 HTTP 服务;/v2/ 是入口(registry:2 容器,端口 ' + str(PORT) + ',本机)')
r = urllib.request.urlopen(f'http://127.0.0.1:{PORT}/v2/')
print(f'  GET /v2/ → {r.status};响应头 Docker-Distribution-Api-Version = {r.headers["Docker-Distribution-Api-Version"]};正文 = {r.read().decode()}')
d = ctx('c15', {'Dockerfile': 'FROM alpine:3.20\nRUN echo a > /a\nCOPY f /f\n', 'f': 'hello\n'})
rc, o = build(d, f'{REG}/c15/app:1', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
n0 = reqs(0)[1]
print('== 二:docker push 发出的 HTTP 请求(来自 registry 自己的访问日志;路径里的 uuid 和摘要已缩写)')
rc, o = dk('push', f'{REG}/c15/app:1', timeout=300)
rows, n1 = reqs(n0)
print(f'  push 退出码 {rc};共 {len(rows)} 个请求,按首次出现顺序:')
show(rows)
print('== 三:删掉本地镜像标签再 docker pull(本地的层内容还在)')
dk('rmi', '-f', f'{REG}/c15/app:1')
rc, o = dk('pull', f'{REG}/c15/app:1', timeout=300)
rows2, n2 = reqs(n1)
print(f'  pull 退出码 {rc};输出里出现 Already exists 的行数 {o.count("Already exists")};共 {len(rows2)} 个请求:')
show(rows2)
rc, o = dk('pull', f'{REG}/c15/app:1', timeout=300)
rows3, n3 = reqs(n2)
print(f'  镜像已经是最新时再 pull 一次:{len(rows3)} 个请求:')
show(rows3)
B = f'http://127.0.0.1:{PORT}'
print('== 四:本机从没有过的镜像:不经过 docker,直接用 HTTP 往 registry 里手工上传一个镜像,再 docker pull')
import io, tarfile, gzip
def upload_blob(name, data):
    dg = 'sha256:' + hashlib.sha256(data).hexdigest()
    r = urllib.request.urlopen(urllib.request.Request(f'{B}/v2/{name}/blobs/uploads/', method='POST', data=b''))
    loc = r.headers['Location']; loc = loc if loc.startswith('http') else B + loc
    sep = '&' if '?' in loc else '?'
    r2 = urllib.request.urlopen(urllib.request.Request(f'{loc}{sep}digest={dg}', method='PUT', data=data, headers={'Content-Type': 'application/octet-stream'}))
    return dg, r2.status
buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode='w') as tf:
    payload = b'hand made layer\n' * 50
    ti = tarfile.TarInfo('hello.txt'); ti.size = len(payload); ti.mtime = 0; tf.addfile(ti, io.BytesIO(payload))
tar_bytes = buf.getvalue()
layer = gzip.compress(tar_bytes, mtime=0)
diff = 'sha256:' + hashlib.sha256(tar_bytes).hexdigest()
cfgj = json.dumps({'architecture': 'arm64', 'os': 'linux', 'config': {'Cmd': ['/hello.txt']}, 'rootfs': {'type': 'layers', 'diff_ids': [diff]}}).encode()
ld, ls_ = upload_blob('c15/hand', layer); cdg, cs = upload_blob('c15/hand', cfgj)
man = json.dumps({'schemaVersion': 2, 'mediaType': 'application/vnd.oci.image.manifest.v1+json', 'config': {'mediaType': 'application/vnd.oci.image.config.v1+json', 'digest': cdg, 'size': len(cfgj)}, 'layers': [{'mediaType': 'application/vnd.oci.image.layer.v1.tar+gzip', 'digest': ld, 'size': len(layer)}]}).encode()
r = urllib.request.urlopen(urllib.request.Request(f'{B}/v2/c15/hand/manifests/v1', method='PUT', data=man, headers={'Content-Type': 'application/vnd.oci.image.manifest.v1+json'}))
print(f'  手工上传:层 {len(layer)} 字节(上传返回 {ls_}),config {len(cfgj)} 字节(返回 {cs}),manifest {len(man)} 字节(返回 {r.status})')
nA = reqs(0)[1]
rc, o = dk('pull', f'{REG}/c15/hand:v1', timeout=300)
rowsH, _ = reqs(nA)
print(f'  docker pull 退出码 {rc};输出里 Already exists 的行数 {o.count("Already exists")};共 {len(rowsH)} 个请求:')
show(rowsH)
print(f'  拉下来的镜像:docker image inspect 的层数 = {len(json.loads(out("image", "inspect", "--format", "{{json .RootFS.Layers}}", f"{REG}/c15/hand:v1")))},diff_id 与我写进 config 的一致吗?{json.loads(out("image", "inspect", "--format", "{{json .RootFS.Layers}}", f"{REG}/c15/hand:v1"))[0] == diff}')
print('== 五:自己用 HTTP 客户端读 registry')
def get(path, method='GET', accept=None):
    rq = urllib.request.Request(B + path, method=method, headers={'Accept': accept} if accept else {})
    try:
        r = urllib.request.urlopen(rq); return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()
print('  GET /v2/_catalog → ' + get('/v2/_catalog')[2].decode().strip())
print('  GET /v2/c15/app/tags/list → ' + get('/v2/c15/app/tags/list')[2].decode().strip())
OCI = 'application/vnd.oci.image.manifest.v1+json'
st, h, body = get('/v2/c15/app/manifests/1', accept=OCI)
dg = h.get('Docker-Content-Digest')
print(f'  GET manifests/1(Accept: OCI manifest)→ {st};Content-Type = {h.get("Content-Type")};正文 {len(body)} 字节;Docker-Content-Digest = {dg[:19]}…;自己对正文算 sha256 一致吗?{"sha256:" + hashlib.sha256(body).hexdigest() == dg}')
st2, h2, body2 = get('/v2/c15/app/manifests/1')
print(f'  不带 Accept 头再请求同一个 tag → {st2};Content-Type = {h2.get("Content-Type")};正文是同一份吗?{body2 == body}')
st3, h3, body3 = get('/v2/c15/app/manifests/1', accept='application/vnd.docker.distribution.manifest.v2+json')
print(f'  只接受 Docker schema2 manifest 类型(Accept: application/vnd.docker.distribution.manifest.v2+json)→ {st3};Content-Type = {h3.get("Content-Type")}')
st4, h4, body4 = get('/v2/c15/app/manifests/' + dg, method='HEAD', accept=OCI)
print(f'  HEAD manifests/<digest> → {st4};Content-Length = {h4.get("Content-Length")}')
m = json.loads(body)
cd = m['config']['digest']
st5, h5, cb = get(f'/v2/c15/app/blobs/{cd}')
print(f'  GET blobs/<config digest> → {st5};{len(cb)} 字节;sha256 与 digest 一致吗?{"sha256:" + hashlib.sha256(cb).hexdigest() == cd}')
st6, h6, b6 = get('/v2/c15/app/manifests/nope')
print(f'  GET manifests/nope → {st6};正文 = {b6.decode().strip()[:160]}')
st7, h7, b7 = get('/v2/c15/app/blobs/sha256:' + '0' * 64)
print(f'  GET blobs/<不存在的摘要> → {st7}')
purge()
