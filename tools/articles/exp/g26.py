import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g26')
SRC = r'''
package main

import (
	"fmt"
	"math"
	"time"
)

type Weekday int

const (
	Sunday Weekday = iota
	Monday
	Tuesday
	_
	Thursday
)

type ByteSize float64

const (
	_           = iota
	KB ByteSize = 1 << (10 * iota)
	MB
	GB
)

const (
	A, B = iota, iota * 10
	C, D
	E, F
)

const (
	FlagRead = 1 << iota
	FlagWrite
	FlagExec
	FlagAll = FlagRead | FlagWrite | FlagExec
)

const (
	X = iota
	Y = "字符串"
	Z
	W = iota
)

const Z2 = iota

func main() {
	fmt.Printf("  Weekday:Sunday = %d、Monday = %d、Tuesday = %d、Thursday = %d(用 _ 跳过了 3)\n", Sunday, Monday, Tuesday, Thursday)
	fmt.Printf("  ByteSize:KB = %v、MB = %v、GB = %v;%%T = %T\n", KB, MB, GB, KB)
	fmt.Printf("  一行多个:A, B = %d, %d;C, D = %d, %d;E, F = %d, %d\n", A, B, C, D, E, F)
	fmt.Printf("  位标志:FlagRead = %d、FlagWrite = %d、FlagExec = %d、FlagAll = %d\n", FlagRead, FlagWrite, FlagExec, FlagAll)
	fmt.Printf("  隐式重复与 iota:X = %d、Y = %q、Z = %q(沿用上一行的表达式)、W = %d(iota 仍按行号递增)\n", X, Y, Z, W)
	fmt.Printf("  另一个 const 块里 iota 重新从 0 开始:Z2 = %d\n", Z2)

	fmt.Println("== 二:无类型常量是精确计算的,只有落到变量时才有精度与范围")
	const big = 1 << 100
	fmt.Printf("  const big = 1 << 100;big >> 98 = %d(int 装不下 big,但常量表达式可以)\n", big>>98)
	const third = 1.0 / 3
	fmt.Printf("  const third = 1.0 / 3;third * 3 == 1 → %v;float64 变量:x := 1.0 / 3.0; x*3 == 1 → %v\n", third*3 == 1, func() bool { x := 1.0; y := 3.0; return x/y*3 == 1 }())
	const a, b = 0.1, 0.2
	x, y := 0.1, 0.2
	fmt.Printf("  常量 0.1 + 0.2 == 0.3 → %v;变量 x + y == 0.3 → %v;x + y = %v\n", a+b == 0.3, x+y == 0.3, x+y)
	fmt.Printf("  整数常量除法 1/2 = %v;1/2.0 = %v;7/2 = %v;-7/2 = %v;7.0/2 = %v\n", 1/2, 1/2.0, 7/2, -7/2, 7.0/2)
	fmt.Printf("  math.Pi 的常量精度:float64(math.Pi) = %.20f;math.Pi*1e30/1e30 == math.Pi → %v\n", math.Pi, math.Pi*1e30/1e30 == math.Pi)
	fmt.Printf("  默认类型:%T %T %T %T %T\n", 1, 1.5, 'a', "s", 1+2i)
	var f32 float32 = 16777217
	fmt.Printf("  var f32 float32 = 16777217 → %v(float32 只能精确表示到 2^24 = 16777216)\n", f32)

	fmt.Println("== 三:带类型常量与 time.Duration")
	const timeout = 5 * time.Second
	const half = 1500 * time.Millisecond
	n := 3
	fmt.Printf("  const timeout = 5 * time.Second → %v;1500 * time.Millisecond → %v(整数倍的常量乘法)\n", timeout, half)
	fmt.Printf("  n := 3;time.Duration(n) * time.Second → %v\n", time.Duration(n)*time.Second)
	fmt.Printf("  len(\"abcd\") 是常量,可以作数组长度:[len(\"abcd\")]int 占 %d 字节\n", func() int { var arr [len("abcd")]int; return len(arr) * 8 }())
}
'''
print('== 一:iota 的各种写法(Go 1.27.1)')
r = grun('ci1', {'main.go': SRC})
print(r['out'] if r['crc'] == 0 else r['cout'])

print('== 四:编译错误:溢出、混用类型、移位')
def ce(title, code, n=2):
    rr = grun('ce', {'main.go': code})
    ls = [re.sub(r'^\./', '', l) for l in rr['cout'].split('\n') if re.match(r'^(\./)?main\.go:\d+', l)][:n]
    if rr['crc'] == 0: ls = ['编译通过,运行输出:' + rr['out'].replace('\n', ' | ')]
    print(f'  {title}:')
    for l in ls: print('    ' + l)
ce('var x int8 = 200', 'package main\n\nvar x int8 = 200\n\nfunc main() { _ = x }\n')
ce('const c int32 = 1 << 31', 'package main\n\nconst c int32 = 1 << 31\n\nfunc main() { _ = c }\n')
ce('const half = 1.5 * time.Second(time.Second 是带类型的整数常量)', 'package main\n\nimport "time"\n\nconst half = 1.5 * time.Second\n\nfunc main() { _ = half }\n')
ce('const huge = 1 << 1000 是合法的常量,但赋给 int 变量', 'package main\n\nconst huge = 1 << 1000\n\nvar h = huge\n\nfunc main() { _ = h }\n')
ce('const huge = 1 << 1000;huge >> 995 = ?', 'package main\n\nimport "fmt"\n\nconst huge = 1 << 1000\n\nfunc main() { fmt.Println(huge >> 995) }\n')
ce('n := 3; n * time.Second(类型不匹配)', 'package main\n\nimport "time"\n\nfunc main() { n := 3; _ = n * time.Second }\n')
ce('var s uint = 1; var f float64 = 1 << s(非常量移位)', 'package main\n\nfunc main() { var s uint = 1; var f float64 = 1 << s; _ = f }\n')
ce('常量整数除以 0', 'package main\n\nfunc main() { _ = 1 / 0 }\n')
ce('x := 10; var f float64 = x(变量不能隐式转换)', 'package main\n\nfunc main() { x := 10; var f float64 = x; _ = f }\n')
ce('const 用函数结果初始化', 'package main\n\nimport "time"\n\nconst now = time.Now()\n\nfunc main() {}\n')

def ok_shift(k):
    rr = grun('cs', {'main.go': f'package main\n\nimport "fmt"\n\nconst c = 1 << {k}\n\nfunc main() {{ fmt.Println(c >> {k - 2}) }}\n'})
    return rr['crc'] == 0
lo, hi = 100, 1000
assert ok_shift(lo) and not ok_shift(hi)
while hi - lo > 1:
    mid = (lo + hi) // 2
    if ok_shift(mid): lo = mid
    else: hi = mid
rr = grun('cs', {'main.go': f'package main\n\nimport "fmt"\n\nconst c = 1 << {lo}\n\nfunc main() {{ fmt.Println(c >> {lo - 2}) }}\n'})
print(f'  二分法找无类型整数常量的上限:const c = 1 << k 能编译并算出 c >> (k-2) 的最大 k = {lo}(1 << {lo} 约 {2 ** lo:.3e});k = {hi} 报 constant shift overflow;k = {lo} 时 c >> {lo - 2} 的运行输出 = {rr["out"]}')
shutil.rmtree(GT / 'cs', ignore_errors=True)
