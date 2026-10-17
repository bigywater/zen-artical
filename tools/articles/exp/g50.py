import sys, os, re, time, statistics, subprocess, tarfile, io; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g50')
SRC = r'''
package main

import (
	"fmt"
	"os"
	"runtime"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

func rd(p string) string {
	b, err := os.ReadFile(p)
	if err != nil { return "(读不到:" + err.Error() + ")" }
	return strings.Join(strings.Fields(string(b)), " ")
}

func stat() map[string]string {
	m := map[string]string{}
	b, _ := os.ReadFile("/sys/fs/cgroup/cpu.stat")
	for _, l := range strings.Split(string(b), "\n") {
		f := strings.Fields(l)
		if len(f) == 2 { m[f[0]] = f[1] }
	}
	return m
}

func main() {
	switch os.Args[1] {
	case "info":
		fmt.Printf("  NumCPU=%d GOMAXPROCS=%d | cpu.max=%q | 环境变量 GOMAXPROCS=%q GODEBUG=%q\n", runtime.NumCPU(), runtime.GOMAXPROCS(0), rd("/sys/fs/cgroup/cpu.max"), os.Getenv("GOMAXPROCS"), os.Getenv("GODEBUG"))
	case "watch":
		for i := 0; i < 16; i++ {
			fmt.Printf("  t=%4.1fs GOMAXPROCS=%d cpu.max=%q\n", float64(i)*0.5, runtime.GOMAXPROCS(0), rd("/sys/fs/cgroup/cpu.max"))
			time.Sleep(500 * time.Millisecond)
		}
	case "burn":
		// 一个“很并行”的程序:NumCPU 个 goroutine 同时空转 3 秒,同时量 1ms 睡眠的最大超时
		var stop atomic.Bool
		var wg sync.WaitGroup
		for i := 0; i < runtime.NumCPU(); i++ {
			wg.Add(1)
			go func() { defer wg.Done(); x := 0; for !stop.Load() { for j := 0; j < 1000; j++ { x += j } }; _ = x }()
		}
		var worst time.Duration
		var n int
		end := time.Now().Add(3 * time.Second)
		for time.Now().Before(end) {
			t0 := time.Now()
			time.Sleep(time.Millisecond)
			if d := time.Since(t0) - time.Millisecond; d > worst { worst = d }
			n++
		}
		stop.Store(true); wg.Wait()
		s := stat()
		fmt.Printf("  GOMAXPROCS=%d:3 秒内 nr_periods=%s nr_throttled=%s throttled_usec=%s;1ms 睡眠 %d 次,最坏超时 %.1f ms\n", runtime.GOMAXPROCS(0), s["nr_periods"], s["nr_throttled"], s["throttled_usec"], n, float64(worst.Microseconds())/1000)
	}
}
'''
def build(name, gover):
    d = gdir(name); write(d, {'main.go': SRC}); mod(d, go=gover)
    rc, o = go(d, 'build', '-o', 'app', env=dict(GOOS='linux', GOARCH='arm64', CGO_ENABLED='0'))
    assert rc == 0, o
    return d / 'app'
def make_image(tag, binpath):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w') as t:
        ti = tarfile.TarInfo('app'); data = open(binpath, 'rb').read(); ti.size = len(data); ti.mode = 0o755
        t.addfile(ti, io.BytesIO(data))
    p = subprocess.run(['docker', 'import', '-c', 'ENTRYPOINT ["/app"]', '-', tag], input=buf.getvalue(), capture_output=True)
    assert p.returncode == 0, p.stderr
make_image('g50:new', build('cm1', '1.27'))
make_image('g50:old', build('cm2', '1.24'))
def dk(*a, tmo=60):
    p = subprocess.run(['docker', *a], capture_output=True, text=True, timeout=tmo)
    return (p.stdout + p.stderr).rstrip()
def run(tag, mode, *opts, tmo=60):
    return dk('run', '--rm', *opts, tag, mode, tmo=tmo)
print('== 零:宿主(Docker Desktop 的 Linux 虚拟机)与 go.mod 的语言版本')
print('  ' + dk('info', '--format', 'Docker Desktop 虚拟机:{{.NCPU}} 个 CPU,{{.OSType}}/{{.Architecture}},cgroup 版本 {{.CgroupVersion}}'))
print('  镜像 g50:new 的 go.mod 写 go 1.27;镜像 g50:old 的 go.mod 写 go 1.24(同一份源码,都由 Go 1.27.1 交叉编译为 linux/arm64 静态程序,用 docker import 做成只含这一个文件的镜像)')
print('== 一:不同的容器 CPU 限制下,默认的 GOMAXPROCS(go 1.27 的程序)')
for label, opts in [('不限制', []), ('--cpus=4', ['--cpus=4']), ('--cpus=2', ['--cpus=2']), ('--cpus=2.5', ['--cpus=2.5']), ('--cpus=1', ['--cpus=1']), ('--cpus=0.5', ['--cpus=0.5']), ('--cpuset-cpus=0-2', ['--cpuset-cpus=0-2'])]:
    print(f'  [{label}]' + run('g50:new', 'info', *opts))
print('== 二:go.mod 写 go 1.24 的同一份程序(语言版本低,默认不看 cgroup)')
for label, opts in [('--cpus=2', ['--cpus=2']), ('--cpus=0.5', ['--cpus=0.5'])]:
    print(f'  [{label}]' + run('g50:old', 'info', *opts))
print('== 三:手动覆盖的几种方式(go 1.27 的程序,都在 --cpus=2 下)')
print('  [环境变量 GOMAXPROCS=8]' + run('g50:new', 'info', '--cpus=2', '-e', 'GOMAXPROCS=8'))
print('  [GODEBUG=containermaxprocs=0]' + run('g50:new', 'info', '--cpus=2', '-e', 'GODEBUG=containermaxprocs=0'))
print('== 四:运行中改限制:启动 --cpus=2 的容器,约 2 秒后 docker update --cpus=4,再 2 秒后改成 1(程序每 0.5 秒打印一次)')
name = 'g50watch'
dk('rm', '-f', name)
subprocess.run(['docker', 'run', '-d', '--name', name, '--cpus=2', 'g50:new', 'watch'], capture_output=True)
time.sleep(2.2); dk('update', '--cpus=4', name); time.sleep(2.0); dk('update', '--cpus=1', name)
time.sleep(5.0)
lg = dk('logs', name).split('\n')
for l in lg: print(l)
dk('rm', '-f', name)
print('== 五:一个很并行的程序(10 个空转 goroutine + 1ms 睡眠计时)在 --cpus=1 下:按 cgroup 取默认值 vs 强制 GOMAXPROCS=10')
for i in range(3):
    print('  [默认]' + run('g50:new', 'burn', '--cpus=1', tmo=60))
    print('  [GOMAXPROCS=10]' + run('g50:new', 'burn', '--cpus=1', '-e', 'GOMAXPROCS=10', tmo=60))
print('== 六:runtime.GOMAXPROCS 文档与 godebug 文档里的说明')
r, o = go(gdir('doc1'), 'doc', 'runtime.GOMAXPROCS');
for l in o.split('\n')[4:]:
    if l.strip() and not l.startswith('[default]'): print('  ' + l)
gd = open(GOROOT + '/doc/godebug.md').read().split('\n')
for i, l in enumerate(gd):
    if 'containermaxprocs' in l and l.startswith('Go 1.25'):
        for x in gd[i:i + 14]: print('  ' + x)
        break
else:
    i = next(i for i, l in enumerate(gd) if 'containermaxprocs' in l)
    for x in gd[max(0, i - 4):i + 10]: print('  ' + x)
subprocess.run(['docker', 'rmi', '-f', 'g50:new', 'g50:old'], capture_output=True)
