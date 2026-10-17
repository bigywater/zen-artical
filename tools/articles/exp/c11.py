import sys, os, re, time, subprocess, json, tarfile, tempfile; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c11')
purge()
GOSRC = '''package main

import (
	"fmt"
	"os"
	"runtime"
	"time"
)

func main() {
	if len(os.Args) > 1 && os.Args[1] == "spin" {
		t0 := time.Now()
		x := uint64(1)
		for i := 0; i < 300_000_000; i++ { x = x*6364136223846793005 + 1442695040888963407 }
		fmt.Printf("spin 3 亿次迭代 %.0f ms(%d)\\n", float64(time.Since(t0).Milliseconds()), x&1)
		return
	}
	fmt.Printf("我是 %s/%s 的二进制\\n", runtime.GOOS, runtime.GOARCH)
}
'''
d = ctx('c11', {'Dockerfile': 'FROM scratch\nARG TARGETARCH\nCOPY app-${TARGETARCH} /app\nENTRYPOINT ["/app"]\n', 'main.go': GOSRC, 'go.mod': 'module lab\n\ngo 1.27\n'})
env = dict(os.environ, GOTOOLCHAIN='local', GOPROXY='off', CGO_ENABLED='0', GOOS='linux')
for arch in ('arm64', 'amd64'):
    r = subprocess.run(['/opt/homebrew/bin/go', 'build', '-o', f'app-{arch}', '.'], cwd=d, env=dict(env, GOARCH=arch), capture_output=True, text=True); assert r.returncode == 0, r.stderr
(d / 'main.go').unlink(); (d / 'go.mod').unlink()
print('== 一:单平台构建 vs 多平台构建(FROM scratch,Go 静态二进制交叉编译出 arm64 和 amd64 两份;Docker Engine 29.8.2,containerd 镜像存储)')
t0 = time.time(); rc, o = dk('buildx', 'build', '--platform', 'linux/arm64', '-t', 'bwlab-c11-single', '--label', 'bwlab=1', '--load', str(d)); t1 = ms(t0)
print(f'  --platform linux/arm64:退出码 {rc},用时 {t1:.0f} ms')
t0 = time.time(); rc, o = dk('buildx', 'build', '--platform', 'linux/amd64,linux/arm64', '-t', 'bwlab-c11-multi', '--label', 'bwlab=1', '--load', str(d)); t2 = ms(t0)
print(f'  --platform linux/amd64,linux/arm64 --load:退出码 {rc},用时 {t2:.0f} ms;{o.strip().splitlines()[-1] if rc else "成功"}')
print('== 二:镜像的索引(manifest list / OCI index)里放了什么——用 docker save 读 index.json 与各 manifest')
tmp = tempfile.mkdtemp(); p = os.path.join(tmp, 'm.tar'); subprocess.run(['docker', 'save', '-o', p, 'bwlab-c11-multi'], check=True)
with tarfile.open(p) as t:
    def blob(d): return t.extractfile('blobs/sha256/' + d.split(':')[1]).read()
    idx = json.load(t.extractfile('index.json'))
    print(f'  index.json:{len(idx["manifests"])} 个条目,mediaType = {idx.get("mediaType")}')
    top = json.loads(blob(idx['manifests'][0]['digest']))
    ms_ = top.get('manifests', [])
    print(f'  顶层索引(mediaType = {top.get("mediaType")})里有 {len(ms_)} 个 manifest:')
    for e in ms_:
        plat = e.get('platform', {})
        ann = e.get('annotations', {})
        print(f'    {plat.get("os")}/{plat.get("architecture")} digest={e["digest"][7:19]}… size={e["size"]} 注解={ {k: v[:40] for k, v in ann.items()} }')
shutil.rmtree(tmp, ignore_errors=True)
print('== 三:在 arm64 的 Docker Desktop 上运行两个架构的镜像(amd64 靠模拟)')
for plat in ('linux/arm64', 'linux/amd64'):
    rc, o = dk('run', '--rm', *LAB, '--platform', plat, 'bwlab-c11-multi')
    print(f'  --platform {plat}:{o.strip().splitlines()[-1]}')
print('== 四:模拟的代价:同一个 3 亿次整数运算的循环')
for plat in ('linux/arm64', 'linux/amd64'):
    best = None
    for _ in range(3):
        rc, o = dk('run', '--rm', *LAB, '--platform', plat, 'bwlab-c11-multi', 'spin')
        m = re.search(r'spin 3 亿次迭代 (\d+) ms', o)
        if m: v = int(m.group(1)); best = v if best is None else min(best, v)
    print(f'  {plat}:3 次取最快 {best} ms')
print('== 五:镜像检查里的 Architecture 与 Os')
for tag in ('bwlab-c11-single', 'bwlab-c11-multi'):
    print(f'  {tag}:' + out('image', 'inspect', '--format', 'Os={{.Os}} Architecture={{.Architecture}} Size={{.Size}}', tag))
purge()
