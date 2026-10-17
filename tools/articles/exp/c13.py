import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c13')
img('alpine:3.20')
purge()
def mk(name, tag, text, *extra):
    d = ctx(name, {'Dockerfile': f'FROM alpine:3.20\nRUN echo {text} > /version\nCMD ["cat","/version"]\n'})
    rc, o = build(d, tag, *extra)
    assert rc == 0, o[-300:]
def insp(ref, fmt): return out('image', 'inspect', '--format', fmt, ref)
def short(x): return x.replace('sha256:', '')[:12]
def untagged():
    rc, o = dk('image', 'ls', '-a')
    return [l.split()[1] for l in o.split('\n')[1:] if l.startswith('<untagged>') and short(l.split()[1]) != 'eb9a37c40105']
print('== 一:tag 只是一个名字,镜像的身份是 ID(Docker Engine 29.8.2,containerd 镜像存储)')
mk('c13a', 'bwlab-c13:a', 'v1')
ida = insp('bwlab-c13:a', '{{.Id}}')
print(f'  构建 v1 并命名 bwlab-c13:a:ID = {short(ida)}…(完整形式 sha256: 加 64 位十六进制,共 {len(ida)} 个字符)')
print(f'  .Id 和 .Descriptor.digest 相同吗?{ida == insp("bwlab-c13:a", "{{.Descriptor.digest}}")}(这个镜像存储里镜像 ID 就是顶层 manifest 的摘要)')
print(f'  RepoDigests = {insp("bwlab-c13:a", "{{json .RepoDigests}}")}(没有推送过)')
mk('c13b', 'bwlab-c13:b', 'v2')
idb = insp('bwlab-c13:b', '{{.Id}}')
print(f'  再构建 v2 命名为 bwlab-c13:b:ID = {short(idb)}…')
print('== 二:docker tag 把名字挪走之后,旧镜像去哪了')
print(f'  docker tag bwlab-c13:b bwlab-c13:a → 退出码 {dk("tag", "bwlab-c13:b", "bwlab-c13:a")[0]}')
print(f'  现在 bwlab-c13:a 的 ID = {short(insp("bwlab-c13:a", "{{.Id}}"))}…,和 bwlab-c13:b 相同吗?{insp("bwlab-c13:a", "{{.Id}}") == idb}')
print(f'  docker image ls -a 里出现的 <untagged> 镜像:{[short(x) for x in untagged()]}(旧 v1 的 ID 是 {short(ida)})')
rc, o = dk('run', '--rm', '--pull=never', short(ida)); print(f'  按旧 ID 运行 docker run --pull=never {short(ida)} → 退出码 {rc};输出:{o}')
print('== 三:name@digest 的引用方式:在本机什么时候能找到')
rc, o = dk('run', '--rm', '--pull=never', f'bwlab-c13@{ida}'); print(f'  docker run --pull=never bwlab-c13@sha256:{short(ida)}… → 退出码 {rc};{o.splitlines()[0][:70]}…')
rc, o = dk('run', '--rm', '--pull=never', f'bwlab-c13@{idb}'); print(f'  docker run --pull=never bwlab-c13@sha256:{short(idb)}… → 退出码 {rc};输出:{o}')
rc, o = dk('run', '--rm', '--pull=never', f'bwlab-c13@sha256:{"0" * 64}'); print(f'  引用一个不存在的摘要 → 退出码 {rc};{[l for l in o.splitlines() if l.strip()][0][:110]}')
print('== 四:重新构建同一个 tag(docker build 而不是 docker tag),旧镜像还在吗')
mk('c13c', 'bwlab-c13:c', 'v1')
idc1 = insp('bwlab-c13:c', '{{.Id}}')
mk('c13c', 'bwlab-c13:c', 'v2', '--no-cache')
idc2 = insp('bwlab-c13:c', '{{.Id}}')
print(f'  同一个 tag bwlab-c13:c 先后构建两次:ID {short(idc1)} → {short(idc2)}')
rc, o = dk('run', '--rm', '--pull=never', short(idc1)); print(f'  按第一次的 ID 运行 → 退出码 {rc};{next((l for l in o.splitlines() if "docker:" in l or "No such" in l), o)[:120]}')
print(f'  docker image ls -a 里的 <untagged>:{[short(x) for x in untagged()]}')
print('== 五:同一个 Dockerfile 构建两次(--no-cache),是同一个镜像吗')
ids, layers = [], []
for i in range(2):
    mk('c13d', 'bwlab-c13:d', 'same', '--no-cache')
    ids.append(insp('bwlab-c13:d', '{{.Id}}'))
    layers.append(json.loads(insp('bwlab-c13:d', '{{json .RootFS.Layers}}')))
    time.sleep(1.1)
print(f'  两次构建的镜像 ID:{short(ids[0])} 和 {short(ids[1])};相同吗?{ids[0] == ids[1]}')
print(f'  RootFS.Layers 共 {len(layers[0])} 层;alpine 基础层相同吗?{layers[0][0] == layers[1][0]};RUN 产生的那层相同吗?{layers[0][-1] == layers[1][-1]}')
print('== 六:全部命中缓存的重复构建,ID 变不变')
for label, extra in (('默认(带 provenance 证明)', ()), ('--provenance=false --sbom=false', ('--provenance=false', '--sbom=false'))):
    got, lay = [], []
    for i in range(3):
        mk('c13e', 'bwlab-c13:e', 'cached', *extra)
        got.append(short(insp('bwlab-c13:e', '{{.Id}}'))); lay.append(insp('bwlab-c13:e', '{{json .RootFS.Layers}}'))
    print(f'  {label}:三次构建的 ID = {got};ID 互不相同的有 {len(set(got))} 个;层(RootFS.Layers)都相同吗?{len(set(lay)) == 1}')
purge()
