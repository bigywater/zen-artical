"""从 registry.k8s.io(或其它匿名可拉的 OCI 仓库)经本机代理 127.0.0.1:1087 拉 linux/arm64 镜像,打成 OCI tar 并 docker load(不改 Docker Desktop 设置)。
用法:python3 kpull.py registry.k8s.io/metrics-server/metrics-server:v0.7.2"""
import sys, json, hashlib, tarfile, io, os, subprocess, urllib.request, tempfile, shutil
PROXY = urllib.request.ProxyHandler({'http': 'http://127.0.0.1:1087', 'https': 'http://127.0.0.1:1087'})
OP = urllib.request.build_opener(PROXY)
ACC = ','.join(['application/vnd.oci.image.index.v1+json', 'application/vnd.docker.distribution.manifest.list.v2+json', 'application/vnd.oci.image.manifest.v1+json', 'application/vnd.docker.distribution.manifest.v2+json'])
def get(url, hdr=None): return OP.open(urllib.request.Request(url, headers=hdr or {}), timeout=600)
def pull(ref):
    reg, rest = ref.split('/', 1); repo, tag = rest.rsplit(':', 1); base = f'https://{reg}/v2/{repo}'
    mb = get(f'{base}/manifests/{tag}', {'Accept': ACC}).read(); m = json.loads(mb)
    if 'manifests' in m:
        e = next(x for x in m['manifests'] if x.get('platform', {}).get('os') == 'linux' and x['platform'].get('architecture') == 'arm64')
        mdig = e['digest']; mb = get(f'{base}/manifests/{mdig}', {'Accept': ACC}).read(); m = json.loads(mb)
    else: mdig = 'sha256:' + hashlib.sha256(mb).hexdigest()
    blobs = {}
    def blob(d):
        h = d.split(':')[1]; data = get(f'{base}/blobs/{d}').read(); assert hashlib.sha256(data).hexdigest() == h, d; blobs[h] = data; print('  blob', h[:12], len(data), flush=True)
    blob(m['config']['digest']); [blob(l['digest']) for l in m['layers']]
    idx = {'schemaVersion': 2, 'mediaType': 'application/vnd.oci.image.index.v1+json', 'manifests': [{'mediaType': m['mediaType'], 'digest': mdig, 'size': len(mb), 'annotations': {'io.containerd.image.name': ref, 'org.opencontainers.image.ref.name': tag}}]}
    tmp = tempfile.mkdtemp(); path = os.path.join(tmp, 'img.tar')
    with tarfile.open(path, 'w') as t:
        def add(name, data): ti = tarfile.TarInfo(name); ti.size = len(data); t.addfile(ti, io.BytesIO(data))
        add('oci-layout', b'{"imageLayoutVersion":"1.0.0"}'); add('index.json', json.dumps(idx).encode()); add('blobs/sha256/' + mdig.split(':')[1], mb)
        for h, data in blobs.items(): add('blobs/sha256/' + h, data)
    r = subprocess.run(['docker', 'load', '-i', path], capture_output=True, text=True); print(r.stdout, r.stderr); shutil.rmtree(tmp)
if __name__ == '__main__':
    for ref in sys.argv[1:]: print(ref); pull(ref)
