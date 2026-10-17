import sys, os, re, time, subprocess, json, tarfile, tempfile, gzip, io; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c82')
img('alpine:3.20')
purge()
SALT = str(time.time())
DF = f'''FROM alpine:3.20
RUN echo salt-{SALT}
RUN mkdir /data && dd if=/dev/urandom of=/data/a.bin bs=1M count=10 2>/dev/null
RUN dd if=/dev/urandom of=/data/b.bin bs=1M count=5 2>/dev/null
RUN dd if=/dev/urandom of=/data/a.bin bs=1M count=10 2>/dev/null
RUN rm /data/b.bin
RUN chmod 600 /data/a.bin
'''
d = ctx('c82', {'Dockerfile': DF}); rc, o = build(d, 'bwlab-c82', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
tmp = tempfile.mkdtemp(); p = os.path.join(tmp, 'i.tar'); subprocess.run(['docker', 'save', '-o', p, 'bwlab-c82'], check=True)
t = tarfile.open(p)
def blob(dg): return t.extractfile('blobs/sha256/' + dg.split(':')[1]).read()
idx = json.load(t.extractfile('index.json')); m = json.loads(blob(idx['manifests'][0]['digest']))
if 'manifests' in m: m = json.loads(blob([e for e in m['manifests'] if e.get('platform', {}).get('architecture') == 'arm64'][0]['digest']))
cfg = json.loads(blob(m['config']['digest']))
layers = []
for L in m['layers']:
    raw = blob(L['digest']); raw = gzip.decompress(raw) if L['mediaType'].endswith('gzip') else raw
    tf = tarfile.open(fileobj=io.BytesIO(raw)); members = [(x.name.lstrip('./'), x.size, x.isfile(), x.mode) for x in tf.getmembers()]
    layers.append((len(raw), len(blob(L['digest'])), members))
hist = [h for h in cfg['history'] if not h.get('empty_layer')]
print('== 一:每一层加进来多少字节(docker save 里的层,用自己写的 Python 分析,类似 dive 的做法;Docker Engine 29.8.2)')
print(f'  共 {len(layers)} 层(history 里产生层的有 {len(hist)} 条)')
for i, (raw, comp, mem) in enumerate(layers):
    cmd = re.sub(r'\s+', ' ', hist[i].get('created_by', ''))[:60] if i < len(hist) else ''
    big = [f'{n}({s / 1e6:.1f}MB)' for n, s, f, md in mem if f and s > 1e6]
    wh = [n for n, s, f, md in mem if '.wh.' in n]
    print(f'  层 {i}:tar {raw / 1e6:.1f} MB;{cmd};大文件:{big or "无"};whiteout:{wh or "无"}')
print('== 二:哪些字节是「浪费」的:被后面的层覆盖或删除的文件')
cur = {}; wasted = []
for i, (raw, comp, mem) in enumerate(layers):
    for n, s, f, md in mem:
        base = os.path.basename(n); dn = os.path.dirname(n)
        if base.startswith('.wh.'):
            tgt = os.path.join(dn, base[4:])
            if tgt in cur: wasted.append((tgt, cur.pop(tgt), i, '被删除'))
            continue
        if not f: continue
        if n in cur: wasted.append((n, cur[n], i, '被覆盖'))
        cur[n] = (i, s)
for n, (li, s), by, why in wasted:
    if s > 100_000: print(f'  {n}:层 {li} 里的 {s / 1e6:.1f} MB 在层 {by} {why}')
tot = sum(s for raw, comp, mem in layers for n, s, f, md in mem if f)
w = sum(s for n, (li, s), by, why in wasted)
print(f'  所有层里的文件字节总和 {tot / 1e6:.1f} MB;被后面层覆盖或删除的(浪费)共 {w / 1e6:.1f} MB;有效 {(tot - w) / 1e6:.1f} MB;效率 = 有效 ÷ 总和 = {(tot - w) / tot * 100:.1f}%')
print(f'  容器里实际可见的 /data 下的文件:' + dk('run', '--rm', 'bwlab-c82', 'sh', '-c', 'ls -l /data | tail -n +2 | awk "{print \\$1, \\$5, \\$9}"')[1].strip().replace('\n', ' ; '))
print('== 三:对比:把这些操作合并成一条 RUN')
d2 = ctx('c82b', {'Dockerfile': f'FROM alpine:3.20\nRUN echo salt2-{SALT}\nRUN mkdir /data && dd if=/dev/urandom of=/data/a.bin bs=1M count=10 2>/dev/null && chmod 600 /data/a.bin\n'})
rc, o = build(d2, 'bwlab-c82b', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
s1 = int(out('image', 'inspect', '--format', '{{.Size}}', 'bwlab-c82')); s2 = int(out('image', 'inspect', '--format', '{{.Size}}', 'bwlab-c82b'))
print(f'  镜像 Size:浪费版 {s1 / 1e6:.1f} MB(层数 {len(layers)}),合并版 {s2 / 1e6:.1f} MB;最终容器里看到的文件相同:{dk("run", "--rm", "bwlab-c82b", "sh", "-c", "ls -l /data | tail -n +2 | awk \'{print $1, $5, $9}\'")[1].strip()}')
t.close(); shutil.rmtree(tmp, ignore_errors=True)
purge()
