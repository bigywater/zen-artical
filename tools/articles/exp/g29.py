import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g29')
SRC = r'''
package main

/*
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int c_add(int a, int b) { return a + b; }
static size_t c_strlen(const char *s) { return strlen(s); }
static unsigned c_sum(const unsigned char *p, int n) { unsigned s = 0; for (int i = 0; i < n; i++) s += p[i]; return s; }
static void c_sleep_ms(int ms) { usleep(ms * 1000); }
*/
import "C"

import (
	"fmt"
	"sort"
	"testing"
	"unsafe"
)

//go:noinline
func goAdd(a, b int) int { return a + b }

var sink int

func main() {
	bench("Go 函数 goAdd(1, 2)(//go:noinline)", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += goAdd(1, 2) } })
	bench("C.c_add(1, 2)(cgo 调用)", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += int(C.c_add(1, 2)) } })
	s := "hello, cgo"
	bench("C.CString + C.c_strlen + C.free", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			cs := C.CString(s)
			sink += int(C.c_strlen(cs))
			C.free(unsafe.Pointer(cs))
		}
	})
	buf := make([]byte, 4096)
	for i := range buf { buf[i] = byte(i) }
	bench("C.c_sum(&buf[0], 4096)(不拷贝,传 Go 内存的指针)", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += int(C.c_sum((*C.uchar)(unsafe.Pointer(&buf[0])), C.int(len(buf)))) } })
	bench("Go 循环对 4096 字节求和", func(b *testing.B) { for i := 0; i < b.N; i++ { var t uint32; for _, c := range buf { t += uint32(c) }; sink += int(t) } })
	fmt.Printf("  AllocsPerRun:C.c_add %.0f 次;C.CString + c_strlen + free %.0f 次\n", testing.AllocsPerRun(1000, func() { sink += int(C.c_add(1, 2)) }), testing.AllocsPerRun(1000, func() { cs := C.CString(s); sink += int(C.c_strlen(cs)); C.free(unsafe.Pointer(cs)) }))
	_ = sort.Ints
}
''' + GBENCH
print('== 一:一次 cgo 调用的成本(Go 1.27.1,arm64,系统 clang;7 轮取中位数)')
r = grun('cg1', {'main.go': SRC}, timeout=900)
print(r['out'] if r['crc'] == 0 else r['cout'])

print('== 二:cgo 做了什么:go tool cgo 生成的文件与 C.c_add 对应的 Go 包装(摘录)')
d = gdir('cg2'); write(d, {'main.go': '''package main

/*
static int c_add(int a, int b) { return a + b; }
*/
import "C"

import "fmt"

func main() { fmt.Println(C.c_add(1, 2)) }
'''}); mod(d)
rc, o = go(d, 'tool', 'cgo', '-objdir', 'gen', 'main.go')
print(f'  go tool cgo -objdir gen main.go:rc={rc}')
gen = sorted(os.listdir(d / 'gen'))
print('  生成的文件:' + ' '.join(gen))
gt = (d / 'gen' / '_cgo_gotypes.go').read_text()
i = gt.index('func _Cfunc_c_add')
print('  _cgo_gotypes.go 里 C.c_add 的 Go 包装:')
for l in gt[i - 120:i + 650].split('\n')[:22]: print('    ' + l.replace(str(GT), '<gtmp>'))

print('== 三:阻塞在 C 里的 goroutine 占一个线程(runtime/pprof 的 threadcreate 计数)')
TH = r'''
package main

/*
#include <unistd.h>
static void c_sleep_ms(int ms) { usleep(ms * 1000); }
*/
import "C"

import (
	"fmt"
	"os"
	"runtime/pprof"
	"sync"
	"time"
)

func main() {
	mode := os.Args[1]
	n := 100
	before := pprof.Lookup("threadcreate").Count()
	var wg sync.WaitGroup
	t0 := time.Now()
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if mode == "c" { C.c_sleep_ms(300) } else { time.Sleep(300 * time.Millisecond) }
		}()
	}
	time.Sleep(150 * time.Millisecond)
	mid := pprof.Lookup("threadcreate").Count()
	wg.Wait()
	fmt.Printf("  %d 个 goroutine 各睡 300 ms(%s):线程创建数 %d → %d(增加 %d),总耗时 %.0f ms\n", n, map[string]string{"c": "C.usleep", "go": "time.Sleep"}[mode], before, mid, mid-before, float64(time.Since(t0).Milliseconds()))
}
'''
d3 = gdir('cg3'); write(d3, {'main.go': TH}); mod(d3)
rc, o = go(d3, 'build', '-o', 'app'); assert rc == 0, o
for mode in ('go', 'c'):
    p = subprocess.run([str(d3 / 'app'), mode], capture_output=True, text=True)
    print(p.stdout.rstrip() or p.stderr[:300])

print('== 四:不用 cgo 的限制:CGO_ENABLED=0 与交叉编译;以及 cgo 指针传递规则')
rc, o = go(d, 'build', '-o', 'app0', env=dict(CGO_ENABLED='0'))
print(f'  CGO_ENABLED=0 构建含 import "C" 的包:rc={rc}')
for l in o.split('\n')[:3]: print('    ' + l.replace('./main.go', 'main.go'))
rc, o = go(d, 'build', '-o', 'applinux', env=dict(GOOS='linux', GOARCH='amd64', CGO_ENABLED='1'))
print(f'  从 macOS 用 CGO_ENABLED=1 交叉编译到 linux/amd64:rc={rc}')
for l in o.split('\n')[:4]: print('    ' + re.sub(r'/(private|var|tmp)/[^\s:]*', '<路径>', l)[:200])
PT = r'''
package main

/*
typedef struct { int *p; } holder;
static int deref(holder *h) { return *h->p; }
*/
import "C"

import (
	"fmt"
	"runtime"
)

func main() {
	x := C.int(7)
	h := &C.holder{p: &x} // 传给 C 的 Go 内存里含有 Go 指针
	defer func() { fmt.Println("  recover:", recover()) }()
	fmt.Println(C.deref(h))
	_ = runtime.GOOS
}
'''
d4 = gdir('cg4'); write(d4, {'main.go': PT}); mod(d4)
rc, o = go(d4, 'build', '-o', 'app'); assert rc == 0, o
p = subprocess.run([str(d4 / 'app')], capture_output=True, text=True)
lines = [re.sub(r'0x[0-9a-f]+', '0x…', l.strip()) for l in (p.stdout + p.stderr).split('\n') if l.strip()]
print(f'  把含 Go 指针的结构体指针传给 C(默认 cgocheck=1):退出码 {p.returncode};' + ' / '.join(lines[:3])[:300])
