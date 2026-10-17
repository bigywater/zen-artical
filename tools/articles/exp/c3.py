import sys, os, re, time, subprocess, tarfile, io, json, tempfile; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c3')
img('alpine:3.20')
purge()
def size(tag):
    return int(out('image', 'inspect', '--format', '{{.Size}}', tag))
def saved_layers(tag):
    """docker save 导出 tar,返回 [(层 blob 前 12 位, 压缩/未压缩的字节数, 层内条目列表)]"""
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, 'img.tar')
    subprocess.run(['docker', 'save', '-o', p, tag], check=True)
    res = []
    with tarfile.open(p) as t:
        names = {m.name: m for m in t.getmembers()}
        idx = json.load(t.extractfile('index.json'))
        def blob(d): return t.extractfile('blobs/sha256/' + d.split(':')[1]).read()
        m0 = json.loads(blob(idx['manifests'][0]['digest']))
        # 可能是 manifest list
        if 'manifests' in m0:
            for e in m0['manifests']:
                if e.get('platform', {}).get('architecture') == 'arm64' and e.get('annotations', {}).get('vnd.docker.reference.type') is None:
                    m0 = json.loads(blob(e['digest'])); break
        for l in m0['layers']:
            data = blob(l['digest'])
            try:
                with tarfile.open(fileobj=io.BytesIO(data), mode='r:*') as lt:
                    ents = [(x.name, x.size) for x in lt.getmembers()]
            except Exception as ex:
                ents = [('(无法解析:' + str(ex)[:40] + ')', 0)]
            res.append((l['digest'].split(':')[1][:12], len(data), ents))
    shutil.rmtree(tmp, ignore_errors=True)
    return res
MB = 1024 * 1024
DF_A = 'FROM alpine:3.20\nRUN dd if=/dev/urandom of=/big.bin bs=1M count=20 2>/dev/null\nRUN rm /big.bin\n'
DF_B = 'FROM alpine:3.20\nRUN dd if=/dev/urandom of=/big.bin bs=1M count=20 2>/dev/null && rm /big.bin\n'
base = size('alpine:3.20')
rc0, o0 = dk('images', 'alpine:3.20')
print('== 一:创建 20 MiB 的文件、下一层再删掉它,镜像变小了吗(alpine:3.20 本身 Size = %.2f MB)' % (base / 1e6))
print('  alpine:3.20 的 docker images:' + ' | '.join(re.sub(r'\s{2,}', ' / ', l.strip()) for l in o0.split('\n')[:2]))
for tag, df, label in (('bwlab-c3a', DF_A, '两个 RUN:先 dd,再 rm'), ('bwlab-c3b', DF_B, '一个 RUN:dd && rm')):
    d = ctx(tag, {'Dockerfile': df})
    rc, o = build(d, tag)
    s = size(tag)
    print(f'  [{label}] 退出码 {rc};docker image inspect 的 Size = {s / 1e6:.2f} MB(比 alpine 多 {(s - base) / 1e6:.2f} MB)')
    rc2, o2 = dk('images', tag)
    print('    docker images:' + ' | '.join(re.sub(r'\s{2,}', ' / ', l.strip()) for l in o2.split('\n')[:2]))
print('== 二:docker history —— 每一层的大小')
for tag in ('bwlab-c3a', 'bwlab-c3b'):
    rc, o = dk('history', '--no-trunc=false', '--format', '{{.Size}}\t{{.CreatedBy}}', tag)
    lines = [l for l in o.split('\n') if l.strip()][:4]
    print(f'  {tag}:')
    for l in lines:
        sz, cmd = l.split('\t', 1)
        print(f'    {sz:>10s}  {re.sub(r"\\s+", " ", cmd)[:90]}')
print('== 三:docker save 出来看每一层 tar 里到底有什么(找 whiteout 文件)')
for tag in ('bwlab-c3a', 'bwlab-c3b'):
    layers = saved_layers(tag)
    print(f'  {tag}:共 {len(layers)} 层(含 alpine 基础层),后面几层:')
    for h, n, ents in layers[1:]:
        shown = ' '.join(f'{nm}({sz}B)' for nm, sz in ents[:6])
        print(f'    层 {h}… 文件大小 {n / 1e6:.2f} MB;条目 {len(ents)} 个:{shown}')
print('== 四:删除只是在上面盖了一层,下面的层里文件仍然完整:把 Dockerfile 拆成两个阶段,单独构建到 gen 阶段')
DF_D = 'FROM alpine:3.20 AS gen\nRUN dd if=/dev/urandom of=/big.bin bs=1M count=20 2>/dev/null\nFROM gen\nRUN rm /big.bin\n'
d = ctx('bwlab-c3d', {'Dockerfile': DF_D})
rc, o = build(d, 'bwlab-c3d-gen', '--target', 'gen'); rc, o = build(d, 'bwlab-c3d')
rc, o = dk('run', '--rm', *LAB, 'bwlab-c3d-gen', 'ls', '-la', '/big.bin')
print('  从 gen 阶段的镜像启动:ls -la /big.bin → ' + o.strip().split('\n')[-1])
rc, o = dk('run', '--rm', *LAB, 'bwlab-c3d', 'ls', '-la', '/big.bin')
print('  从最终镜像(多了 rm 那一层)启动:ls -la /big.bin → ' + o.strip().split('\n')[-1])
print('== 五:多阶段构建:只把需要的文件拷进最终阶段,才真正变小')
DF_C = 'FROM alpine:3.20 AS gen\nRUN dd if=/dev/urandom of=/big.bin bs=1M count=20 2>/dev/null && echo small > /small.txt && rm /big.bin\nFROM alpine:3.20\nCOPY --from=gen /small.txt /small.txt\n'
d = ctx('bwlab-c3c', {'Dockerfile': DF_C}); rc, o = build(d, 'bwlab-c3c')
print(f'  [多阶段:生成阶段用掉 20 MiB,最终阶段只 COPY --from 一个小文件] 镜像 {size("bwlab-c3c") / 1e6:.2f} MB(比 alpine 多 {(size("bwlab-c3c") - base) / 1e6:.2f} MB)')
purge()
