import sys, os, re, time, subprocess, json, tarfile, tempfile; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c21')
img('alpine:3.20')
purge()
def vm(cmd):
    rc, o = dk('run', '--rm', '--privileged', '--pid=host', *LAB, 'alpine:3.20', 'nsenter', '-t', '1', '-m', '-u', '-n', '-i', 'sh', '-c', cmd, raw=True)
    return o.strip()
d = ctx('c21', {'Dockerfile': 'FROM alpine:3.20\nRUN mkdir /dir && echo a > /dir/a.txt && echo b > /dir/b.txt && echo g > /gone.txt && echo k > /keep.txt\n'})
rc, o = build(d, 'bwlab-c21', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
cid = out('run', '-d', '--name', 'bwlab-c21c', *LAB, 'bwlab-c21', 'sleep', '600')
mt = vm(f"grep '{cid}' /proc/mounts").splitlines()[0]
up = re.search(r'upperdir=([^,]+)', mt.split()[3]).group(1)
def desc(rel):
    return vm(f"stat -c '%F, 主设备号:次设备号 = %t:%T' {up}/{rel} 2>&1 | head -1")
def xa(rel):
    rc, o = dk('run', '--rm', '--privileged', *LAB, '-v', f'{up}:/up:ro', 'python:3.12-alpine', 'python', '-c', f"import os; p='/up/{rel}'; print({{k: os.getxattr(p, k).decode() for k in os.listxattr(p)}})")
    return o.strip().splitlines()[-1]
def ls_up(): return vm(f"ls -A {up}").replace('\n', ' ') or '(空)'
print('== 一:在容器里删除镜像里的一个文件,upperdir 里发生了什么(Docker Engine 29.8.2,在 Docker Desktop 虚拟机里读 upperdir)')
print(f'  初始 upperdir:{ls_up()}')
dk('exec', cid, 'rm', '/gone.txt')
print(f'  rm /gone.txt 之后 upperdir:{ls_up()}')
print(f'  upperdir/gone.txt 是:{desc("gone.txt")}')
print(f'  容器里 ls /gone.txt:{dk("exec", cid, "ls", "/gone.txt")[1].strip()}')
print(f'  upperdir/gone.txt 的大小:{vm(f"stat -c %s {up}/gone.txt")} 字节')
print('== 二:删除只存在于可写层的文件,不会留下痕迹')
dk('exec', cid, 'sh', '-c', 'echo t > /tmp/only-upper.txt; rm /tmp/only-upper.txt')
print(f'  upperdir/tmp 里:{vm(f"ls -A {up}/tmp 2>&1").replace(chr(10), " ") or "(空)"}(创建又删除一个只在可写层的文件)')
print('== 三:删掉整个目录,再重新建一个同名目录')
dk('exec', cid, 'rm', '-rf', '/dir')
print(f'  rm -rf /dir 之后 upperdir/dir 是:{desc("dir")};容器里 ls /dir:{dk("exec", cid, "ls", "/dir")[1].strip()}')
dk('exec', cid, 'sh', '-c', 'mkdir /dir && echo c > /dir/c.txt')
print(f'  重新 mkdir /dir 并写入 c.txt 之后 upperdir/dir 是:{desc("dir")};里面有:{vm(f"ls -A {up}/dir").replace(chr(10), " ")}')
print(f'  upperdir/dir 的扩展属性:{xa("dir")}')
print(f'  容器里 ls /dir:{dk("exec", cid, "ls", "/dir")[1].strip()}(原来的 a.txt、b.txt 被这个 opaque 目录整个盖住了)')
print('== 四:删掉文件再用同名重新创建:没有 whiteout 了')
dk('exec', cid, 'sh', '-c', 'rm /keep.txt; echo again > /keep.txt')
print(f'  upperdir/keep.txt 是:{desc("keep.txt")};内容:{vm(f"cat {up}/keep.txt")}')
print('== 五:把这个容器 docker commit 成镜像,whiteout 在新层的 tar 里长什么样')
rc, o = dk('commit', cid, 'bwlab-c21-committed')
tmp = tempfile.mkdtemp(); p = os.path.join(tmp, 'c.tar'); subprocess.run(['docker', 'save', '-o', p, 'bwlab-c21-committed'], check=True)
with tarfile.open(p) as t:
    idx = json.load(t.extractfile('index.json'))
    def blob(dg): return t.extractfile('blobs/sha256/' + dg.split(':')[1]).read()
    m = json.loads(blob(idx['manifests'][0]['digest']))
    if 'manifests' in m: m = json.loads(blob([e for e in m['manifests'] if e.get('platform', {}).get('architecture') == 'arm64'][0]['digest']))
    import gzip, io
    L = m['layers'][-1]; raw = blob(L['digest']); raw = gzip.decompress(raw) if L['mediaType'].endswith('gzip') else raw
    tt = tarfile.open(fileobj=io.BytesIO(raw))
    names = [x.name for x in tt.getmembers() if 'etc/' not in x.name and 'tmp' not in x.name]
print(f'  commit 退出码 {rc};镜像共 {len(m["layers"])} 层,最后一层(只含这个容器的改动)的条目:{names}')
shutil.rmtree(tmp, ignore_errors=True)
purge()
