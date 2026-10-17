"""docker 守护进程拉不到 Docker Hub(没有配置代理)时:经本机代理 127.0.0.1:1087 在宿主机上下载镜像(linux/arm64),打成 OCI 布局 tar,再 docker load。不改 Docker Desktop 的任何设置。"""
import sys, json, hashlib, tarfile, io, os, subprocess, urllib.request, urllib.parse, tempfile, shutil
PROXY = urllib.request.ProxyHandler({'http': 'http://127.0.0.1:1087', 'https': 'http://127.0.0.1:1087'})
OP = urllib.request.build_opener(PROXY)
ACC = ','.join(['application/vnd.oci.image.index.v1+json', 'application/vnd.docker.distribution.manifest.list.v2+json', 'application/vnd.oci.image.manifest.v1+json', 'application/vnd.docker.distribution.manifest.v2+json'])
def get(url, hdr=None, tok=None):
    h = dict(hdr or {}); 
    if tok: h['Authorization'] = 'Bearer ' + tok
    return OP.open(urllib.request.Request(url, headers=h), timeout=300)
def pull(ref):
    repo, tag = ref.rsplit(':', 1); full = repo if '/' in repo else 'library/' + repo
    tok = json.load(get(f'https://auth.docker.io/token?service=registry.docker.io&scope=repository:{full}:pull'))['token']
    base = f'https://registry-1.docker.io/v2/{full}'
    r = get(f'{base}/manifests/{tag}', {'Accept': ACC}, tok); mb = r.read(); m = json.loads(mb)
    if 'manifests' in m:
        e = next(x for x in m['manifests'] if x['platform'].get('os') == 'linux' and x['platform'].get('architecture') == 'arm64' and 'annotations' not in x or (x['platform'].get('os') == 'linux' and x['platform'].get('architecture') == 'arm64' and x.get('annotations', {}).get('vnd.docker.reference.type') is None))
        mdig = e['digest']; r = get(f'{base}/manifests/{mdig}', {'Accept': ACC}, tok); mb = r.read(); m = json.loads(mb)
    else: mdig = 'sha256:' + hashlib.sha256(mb).hexdigest()
    tmp = tempfile.mkdtemp(); blobs = {}
    def blob(d):
        h = d.split(':')[1]; data = get(f'{base}/blobs/{d}', None, tok).read(); assert hashlib.sha256(data).hexdigest() == h, d; blobs[h] = data; print('  blob', h[:12], len(data), flush=True)
    blob(m['config']['digest']); [blob(l['digest']) for l in m['layers']]
    idx = {'schemaVersion': 2, 'mediaType': 'application/vnd.oci.image.index.v1+json', 'manifests': [{'mediaType': m['mediaType'], 'digest': mdig, 'size': len(mb), 'annotations': {'io.containerd.image.name': f'docker.io/{full}:{tag}', 'org.opencontainers.image.ref.name': tag}}]}
    path = os.path.join(tmp, 'img.tar')
    with tarfile.open(path, 'w') as t:
        def add(name, data): ti = tarfile.TarInfo(name); ti.size = len(data); t.addfile(ti, io.BytesIO(data))
        add('oci-layout', b'{"imageLayoutVersion":"1.0.0"}'); add('index.json', json.dumps(idx).encode()); add('blobs/sha256/' + mdig.split(':')[1], mb)
        for h, data in blobs.items(): add('blobs/sha256/' + h, data)
    r = subprocess.run(['docker', 'load', '-i', path], capture_output=True, text=True); print(r.stdout, r.stderr); shutil.rmtree(tmp)
if __name__ == '__main__':
    for ref in sys.argv[1:]: print(ref); pull(ref)
