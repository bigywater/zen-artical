import sys, os, re, time, subprocess, json, tarfile, tempfile, hashlib, gzip, io; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c14')
img('alpine:3.20')
purge()
DF = '''FROM alpine:3.20
ENV APP_MODE=demo
LABEL purpose=c14
RUN echo hello > /hello.txt
COPY data.txt /data.txt
EXPOSE 8080
ENTRYPOINT ["/bin/sh","-c"]
CMD ["cat /hello.txt"]
'''
d = ctx('c14', {'Dockerfile': DF, 'data.txt': 'x' * 1000 + '\n'})
rc, o = build(d, 'bwlab-c14', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
tmp = tempfile.mkdtemp(); p = os.path.join(tmp, 'i.tar'); subprocess.run(['docker', 'save', '-o', p, 'bwlab-c14'], check=True)
t = tarfile.open(p)
names = t.getnames()
def blob(dg): return t.extractfile('blobs/sha256/' + dg.split(':')[1]).read()
print('== 一:docker save 出来的 tar 的目录结构(OCI 镜像布局)')
tops = sorted({n.split('/')[0] for n in names})
print(f'  顶层条目:{tops}')
print(f'  blobs/sha256/ 下共 {len([n for n in names if n.startswith("blobs/sha256/") and not n.endswith("/")])} 个文件,文件名就是内容的 sha256')
lay = json.load(t.extractfile('oci-layout'))
print(f'  oci-layout 的内容:{lay}')
bad = 0
for n in names:
    if n.startswith('blobs/sha256/') and not n.endswith('/'):
        if hashlib.sha256(t.extractfile(n).read()).hexdigest() != n.split('/')[-1]: bad += 1
print(f'  逐个重新计算 sha256 与文件名对不上的 blob 数:{bad}')
print('== 二:从 index.json 一路读到 manifest')
idx = json.load(t.extractfile('index.json'))
top = idx['manifests'][0]
print(f'  index.json:schemaVersion={idx["schemaVersion"]},{len(idx["manifests"])} 个条目;第 1 个 mediaType={top["mediaType"]} size={top["size"]}')
m = json.loads(blob(top['digest']))
if 'manifests' in m:
    print(f'  它是索引,里面有 {len(m["manifests"])} 个 manifest:' + ', '.join(f'{e.get("platform", {}).get("os")}/{e.get("platform", {}).get("architecture")}' for e in m['manifests']))
    pick = [e for e in m['manifests'] if e.get('platform', {}).get('architecture') == 'arm64'][0]
    m = json.loads(blob(pick['digest']))
print(f'  manifest 的键:{list(m.keys())};mediaType={m["mediaType"]}')
print(f'  config:mediaType={m["config"]["mediaType"]} size={m["config"]["size"]} digest={m["config"]["digest"][7:19]}…')
for i, l in enumerate(m['layers']):
    print(f'  layers[{i}]:mediaType={l["mediaType"]} size={l["size"]} digest={l["digest"][7:19]}…')
print('== 三:config 里有什么')
cfg = json.loads(blob(m['config']['digest']))
print(f'  config 的顶层键:{list(cfg.keys())}')
c = cfg['config']
print(f'  config.Env={c.get("Env")}')
print(f'  config.Entrypoint={c.get("Entrypoint")} Cmd={c.get("Cmd")} ExposedPorts={c.get("ExposedPorts")} Labels={c.get("Labels")}')
print(f'  architecture={cfg["architecture"]} os={cfg["os"]} created={cfg["created"][:19]}')
print(f'  rootfs.type={cfg["rootfs"]["type"]};diff_ids 共 {len(cfg["rootfs"]["diff_ids"])} 个')
print('== 四:history 与层的对应关系:有几条历史,几条没有产生层')
hs = cfg['history']
print(f'  history 共 {len(hs)} 条,其中 empty_layer=true 的有 {sum(1 for h in hs if h.get("empty_layer"))} 条;layers 有 {len(m["layers"])} 层')
for h in hs:
    print(f'    {"(无层)" if h.get("empty_layer") else "(有层)"} {re.sub(r"\s+", " ", h.get("created_by", ""))[:70]}')
print('== 五:layer 的 digest 与 config 里的 diff_id 为什么是两个值')
for i, l in enumerate(m['layers']):
    raw = blob(l['digest'])
    comp_ok = hashlib.sha256(raw).hexdigest() == l['digest'].split(':')[1]
    unz = gzip.decompress(raw) if l['mediaType'].endswith('gzip') else raw
    did = 'sha256:' + hashlib.sha256(unz).hexdigest()
    print(f'  layers[{i}]:压缩后 {len(raw)} 字节,解压后 {len(unz)} 字节;压缩数据的 sha256 与 manifest 里的 digest 一致:{comp_ok};解压数据的 sha256 与 diff_ids[{i}] 一致:{did == cfg["rootfs"]["diff_ids"][i]};digest 和 diff_id 相同吗?{l["digest"] == did}')
print('== 六:最上面那层的 tar 里放了什么')
raw = blob(m['layers'][-1]['digest']); unz = gzip.decompress(raw) if m['layers'][-1]['mediaType'].endswith('gzip') else raw
tt = tarfile.open(fileobj=io.BytesIO(unz))
print('  最后一层(COPY data.txt)的文件:' + ', '.join(f'{x.name}({x.size} 字节)' for x in tt.getmembers()))
raw = blob(m['layers'][-2]['digest']); unz = gzip.decompress(raw) if m['layers'][-2]['mediaType'].endswith('gzip') else raw
tt = tarfile.open(fileobj=io.BytesIO(unz))
print('  倒数第二层(RUN echo hello)的文件:' + ', '.join(f'{x.name}({x.size} 字节)' for x in tt.getmembers()))
t.close(); shutil.rmtree(tmp, ignore_errors=True)
purge()
