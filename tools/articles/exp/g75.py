import sys, os, re, time, statistics, subprocess, tarfile, io; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g75')
SRC = r'''
package main

import (
	"fmt"
	"os"
	"testing"
	"time"
)

var sinkL *time.Location

func must(name string) *time.Location {
	l, err := time.LoadLocation(name)
	if err != nil { panic(err) }
	return l
}

func main() {
	switch os.Args[1] {
	case "dst":
		ny := must("America/New_York")
		a := time.Date(2026, 3, 7, 12, 0, 0, 0, ny)
		fmt.Printf("  纽约 2026-03-07 12:00 (春季跳时前一天)+ Add(24h) = %s;AddDate(0,0,1) = %s\n", a.Add(24*time.Hour).Format("2006-01-02 15:04 MST"), a.AddDate(0, 0, 1).Format("2006-01-02 15:04 MST"))
		fmt.Printf("  两者相差 %v\n", a.AddDate(0, 0, 1).Sub(a.Add(24*time.Hour)))
		gap := time.Date(2026, 3, 8, 2, 30, 0, 0, ny)
		fmt.Printf("  不存在的时刻 time.Date(2026,3,8,2,30,…,纽约)(当天 2:00 直接跳到 3:00):得到 %s\n", gap.Format("2006-01-02 15:04 MST -0700"))
		amb := time.Date(2026, 11, 1, 1, 30, 0, 0, ny)
		fmt.Printf("  重复出现的时刻 time.Date(2026,11,1,1,30,…,纽约)(当天 1:30 出现两次):得到 %s\n", amb.Format("2006-01-02 15:04 MST -0700"))
		d := time.Date(2026, 3, 8, 0, 0, 0, 0, ny)
		e := time.Date(2026, 3, 9, 0, 0, 0, 0, ny)
		fmt.Printf("  纽约 3 月 8 日这一天(跳时日)有 %.0f 小时\n", e.Sub(d).Hours())
		d2 := time.Date(2026, 11, 1, 0, 0, 0, 0, ny)
		e2 := time.Date(2026, 11, 2, 0, 0, 0, 0, ny)
		fmt.Printf("  纽约 11 月 1 日这一天(回拨日)有 %.0f 小时\n", e2.Sub(d2).Hours())
	case "parse":
		t1, _ := time.Parse("2006-01-02 15:04:05", "2026-06-01 12:00:00")
		sh := must("Asia/Shanghai")
		t2, _ := time.ParseInLocation("2006-01-02 15:04:05", "2026-06-01 12:00:00", sh)
		fmt.Printf("  time.Parse(无时区的字符串):%s;ParseInLocation(…, 上海):%s;两者相差 %v\n", t1.Format(time.RFC3339), t2.Format(time.RFC3339), t1.Sub(t2))
		t3, err := time.Parse("2006-01-02 15:04:05 MST", "2026-06-01 12:00:00 EST")
		name, off := t3.Zone()
		fmt.Printf("  time.Parse(…, \"… EST\"):err=%v,区名 %q,偏移 %d 秒(没有系统认识 EST 时,偏移为 0,不是 −5 小时)\n", err, name, off)
		ny := must("America/New_York")
		t4, _ := time.ParseInLocation("2006-01-02 15:04:05 MST", "2026-06-01 12:00:00 EST", ny)
		name, off = t4.Zone()
		fmt.Printf("  time.ParseInLocation(…, \"… EST\", 纽约):区名 %q,偏移 %d 秒(字符串里写的 EST 没有生效,按位置 6 月的实际规则得到 EDT)\n", name, off)
		_, err = time.Parse("2006-1-2", "2026-06-01")
		fmt.Printf("  layout \"2006-1-2\" 解析 \"2026-06-01\":err=%v\n", err)
	case "load":
		r1 := testing.Benchmark(func(b *testing.B) { for i := 0; i < b.N; i++ { sinkL, _ = time.LoadLocation("Asia/Shanghai") } })
		sh := must("Asia/Shanghai")
		t := time.Now()
		r2 := testing.Benchmark(func(b *testing.B) { for i := 0; i < b.N; i++ { _ = t.In(sh) } })
		r3 := testing.Benchmark(func(b *testing.B) { for i := 0; i < b.N; i++ { _ = t.Format(time.RFC3339) } })
		fmt.Printf("  time.LoadLocation(\"Asia/Shanghai\") %d ns/次(%d 次分配);t.In(已加载的位置) %d ns/次;t.Format(RFC3339) %d ns/次\n", r1.NsPerOp(), r1.AllocsPerOp(), r2.NsPerOp(), r3.NsPerOp())
	case "env":
		fmt.Printf("  TZ=%q:time.Local = %s;现在 %s\n", os.Getenv("TZ"), time.Local, time.Now().Format("15:04 MST -0700"))
	case "container":
		l, err := time.LoadLocation("Asia/Shanghai")
		if err != nil { fmt.Printf("  time.LoadLocation(\"Asia/Shanghai\") 失败:%v\n", err); return }
		fmt.Printf("  time.LoadLocation(\"Asia/Shanghai\") 成功:%s\n", time.Date(2026, 6, 1, 12, 0, 0, 0, time.UTC).In(l).Format("15:04 MST -0700"))
	}
}
'''
d = gdir('tz1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(m, env=None):
    e = dict(os.environ); e.update(env or {})
    p = subprocess.run([str(d / 'app'), m], capture_output=True, text=True, timeout=120, env=e)
    return tidy(p.stdout + p.stderr)
print('== 一:夏令时(Go 1.27.1,macOS 上用系统 /usr/share/zoneinfo)')
print(run('dst'))
print('== 二:解析字符串时区的坑')
print(run('parse'))
print('== 三:LoadLocation 每次都读文件')
print(run('load'))
print('== 四:TZ 环境变量决定 time.Local')
for tz in ('', 'UTC', 'Asia/Shanghai', 'America/New_York'):
    print(run('env', {'TZ': tz}) if tz else run('env', {'TZ': ''}))
print('== 五:容器里没有 tzdata 会怎样(linux/arm64 静态程序,docker import 成只有一个文件的镜像,不含 /usr/share/zoneinfo)')
def build_linux(tags=None):
    dd = gdir('tz2' + ('t' if tags else '')); write(dd, {'main.go': SRC}); mod(dd)
    args = ['build', '-o', 'app'] + (['-tags', tags] if tags else [])
    rc, o = go(dd, *args, env=dict(GOOS='linux', GOARCH='arm64', CGO_ENABLED='0')); assert rc == 0, o
    return dd / 'app'
def image(tag, binpath):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w') as t:
        ti = tarfile.TarInfo('app'); data = open(binpath, 'rb').read(); ti.size = len(data); ti.mode = 0o755
        t.addfile(ti, io.BytesIO(data))
    p = subprocess.run(['docker', 'import', '-c', 'ENTRYPOINT ["/app"]', '-', tag], input=buf.getvalue(), capture_output=True); assert p.returncode == 0, p.stderr
b1 = build_linux(); b2 = build_linux('timetzdata')
image('g75:plain', b1); image('g75:tzdata', b2)
s1, s2 = os.path.getsize(b1), os.path.getsize(b2)
print(f'  二进制大小:不带 tzdata {s1 / 1e6:.2f} MB;加 -tags timetzdata {s2 / 1e6:.2f} MB(多 {(s2 - s1) / 1024:.0f} KiB)')
for tag, lab in (('g75:plain', '普通编译'), ('g75:tzdata', '-tags timetzdata')):
    p = subprocess.run(['docker', 'run', '--rm', tag, 'container'], capture_output=True, text=True, timeout=60)
    print(f'  [{lab}] ' + (p.stdout + p.stderr).strip())
subprocess.run(['docker', 'rmi', '-f', 'g75:plain', 'g75:tzdata'], capture_output=True)
print('== 六:time.LoadLocation 的文档')
r, o = go(gdir('doc1'), 'doc', 'time.LoadLocation')
ls = [l.strip() for l in o.split('\n')][3:]
print('  ' + ' '.join(x for x in ls if x)[:900])
