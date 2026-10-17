import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c74')
img('alpine:3.20')
purge()
def mb(s):
    m = re.match(r'([\d.]+)\s*(B|kB|KB|MB|GB|TB)', s.strip()); v = float(m.group(1))
    return v * {'B': 1e-6, 'kB': 1e-3, 'KB': 1e-3, 'MB': 1, 'GB': 1e3, 'TB': 1e6}[m.group(2)]
def df():
    rc, o = dk('system', 'df', '--format', '{{json .}}', timeout=120)
    return {j['Type']: j for j in (json.loads(l) for l in o.splitlines() if l.startswith('{'))}
def recl(j): return mb(j['Reclaimable'].split()[0])
print('== 一:docker system df 的四行(Docker Engine 29.8.2)')
d0 = df()
for k, j in d0.items(): print(f'  {k:14s} TotalCount={j["TotalCount"]} Active={j["Active"]} Size={j["Size"]} Reclaimable={j["Reclaimable"]}')
print('  JSON 字段:' + str(sorted(next(iter(d0.values())).keys())))
print('== 二:制造 30 MB 的东西,看每一行怎么变(本机还有别的镜像和容器,所以只看增量)')
def delta(a, b, key): return mb(b[key]['Size']) - mb(a[key]['Size'])
# 1) 卷:往里写 30 MB
dk('volume', 'create', '--label', 'bwlab=1', 'bwlab-c74v')
dk('run', '--rm', *LAB, '-v', 'bwlab-c74v:/v', 'alpine:3.20', 'sh', '-c', 'dd if=/dev/urandom of=/v/f.bin bs=1M count=30 2>/dev/null; sync')
d1 = df(); print(f'  往命名卷写 30 MB 随机数据:Local Volumes Size {d0["Local Volumes"]["Size"]} → {d1["Local Volumes"]["Size"]}(增加 {delta(d0, d1, "Local Volumes"):.1f} MB);Containers 行增量 {delta(d0, d1, "Containers"):.1f} MB(--rm 容器已删除)')
# 2) 容器可写层 30 MB
dk('run', '-d', '--name', 'bwlab-c74c', *LAB, 'alpine:3.20', 'sh', '-c', 'dd if=/dev/urandom of=/w.bin bs=1M count=30 2>/dev/null; sync; sleep 300'); time.sleep(2)
d2 = df(); print(f'  容器可写层写 30 MB:Containers Size {d1["Containers"]["Size"]} → {d2["Containers"]["Size"]}(增加 {delta(d1, d2, "Containers"):.1f} MB);TotalCount {d1["Containers"]["TotalCount"]} → {d2["Containers"]["TotalCount"]},Active {d1["Containers"]["Active"]} → {d2["Containers"]["Active"]}')
# 3) 镜像 + 构建缓存
d = ctx('c74', {'Dockerfile': 'FROM alpine:3.20\nRUN dd if=/dev/urandom of=/big.bin bs=1M count=30 2>/dev/null\n'})
rc, o = build(d, 'bwlab-c74img', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
d3 = df(); print(f'  构建带 30 MB 随机层的镜像:Images Size {d2["Images"]["Size"]} → {d3["Images"]["Size"]}(增加 {delta(d2, d3, "Images"):.1f} MB);Build Cache Size {d2["Build Cache"]["Size"]} → {d3["Build Cache"]["Size"]}(增加 {delta(d2, d3, "Build Cache"):.1f} MB)')
print('== 三:Reclaimable 是怎么算的')
r_vol_before = recl(d3["Local Volumes"]); r_con_before = recl(d3["Containers"]); r_img_before = recl(d3["Images"])
print(f'  现在:卷 Reclaimable={d3["Local Volumes"]["Reclaimable"]},容器 Reclaimable={d3["Containers"]["Reclaimable"]},镜像 Reclaimable={d3["Images"]["Reclaimable"]}')
dk('rm', '-f', 'bwlab-c74c')
d4 = df(); print(f'  删掉那个运行中的容器后:Containers Size {d3["Containers"]["Size"]} → {d4["Containers"]["Size"]};容器 TotalCount {d3["Containers"]["TotalCount"]} → {d4["Containers"]["TotalCount"]}')
print(f'  命名卷 bwlab-c74v 现在没有容器引用:Local Volumes Reclaimable {d3["Local Volumes"]["Reclaimable"]} → {d4["Local Volumes"]["Reclaimable"]}(这个卷里有 30 MB)')
print(f'  镜像 bwlab-c74img 没有被任何容器使用:Images Reclaimable {d3["Images"]["Reclaimable"]} → {d4["Images"]["Reclaimable"]}')
dk('run', '-d', '--name', 'bwlab-c74c2', *LAB, '-v', 'bwlab-c74v:/v', 'bwlab-c74img', 'sleep', '60'); time.sleep(1.5)
d5 = df(); print(f'  起一个使用这个卷和这个镜像的容器:Local Volumes Reclaimable {d4["Local Volumes"]["Reclaimable"]} → {d5["Local Volumes"]["Reclaimable"]};Images Reclaimable {d4["Images"]["Reclaimable"]} → {d5["Images"]["Reclaimable"]}')
purge()
