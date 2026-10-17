import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g73')
SRC = r'''
package main

import (
	"context"
	"fmt"
	"os"
	"strings"
	"testing"
)

type keyA struct{}
type keyB struct{}
type ptrKey struct{ name string }

var pk = &ptrKey{"pk"}

type ctxKey int

const (
	k0 ctxKey = iota
)

var sink any

func main() {
	switch os.Args[1] {
	case "collide":
		// 两个“包”都用字符串 "id" 作 key
		ctx := context.Background()
		ctx = context.WithValue(ctx, "id", "来自包 A 的请求ID")
		ctx = context.WithValue(ctx, "id", "来自包 B 的用户ID")
		fmt.Printf("  都用字符串 \"id\" 作 key:包 A 取回的是 %q(被包 B 覆盖)\n", ctx.Value("id"))
		ctx2 := context.Background()
		ctx2 = context.WithValue(ctx2, keyA{}, "来自包 A 的请求ID")
		ctx2 = context.WithValue(ctx2, keyB{}, "来自包 B 的用户ID")
		fmt.Printf("  各自定义 struct{} 类型作 key:包 A 取回 %q,包 B 取回 %q\n", ctx2.Value(keyA{}), ctx2.Value(keyB{}))
		type S string
		ctx3 := context.WithValue(context.Background(), S("id"), "自定义字符串类型")
		fmt.Printf("  自定义类型 type S string 作 key:ctx.Value(\"id\") = %v;ctx.Value(S(\"id\")) = %q\n", ctx3.Value("id"), ctx3.Value(S("id")))
	case "depth":
		for _, d := range []int{1, 10, 100, 1000} {
			ctx := context.Background()
			ctx = context.WithValue(ctx, keyA{}, "target") // 最里面(最先加入)的一层
			for i := 0; i < d-1; i++ { ctx = context.WithValue(ctx, ctxKey(i+1), i) }
			res := testing.Benchmark(func(b *testing.B) { for i := 0; i < b.N; i++ { sink = ctx.Value(keyA{}) } })
			res2 := testing.Benchmark(func(b *testing.B) { for i := 0; i < b.N; i++ { sink = ctx.Value(ctxKey(d - 1)) } })
			fmt.Printf("  链长 %4d 层:查最早加入的 key %6d ns/次;查最后加入的 key %3d ns/次\n", d, res.NsPerOp(), res2.NsPerOp())
		}
	case "alloc":
		bg := context.Background()
		fmt.Printf("  WithValue(ctx, struct{} 类型的 key, 字符串值):每次 %.0f 次分配\n", testing.AllocsPerRun(1000, func() { sink = context.WithValue(bg, keyA{}, "v") }))
		fmt.Printf("  WithValue(ctx, 指针 key, 字符串值):每次 %.0f 次分配\n", testing.AllocsPerRun(1000, func() { sink = context.WithValue(bg, pk, "v") }))
		x := 12345
		fmt.Printf("  WithValue(ctx, struct{} key, 整数值 12345):每次 %.0f 次分配\n", testing.AllocsPerRun(1000, func() { sink = context.WithValue(bg, keyA{}, x) }))
		fmt.Printf("  WithValue(ctx, 自定义 int 类型 key = 3, 字符串值):每次 %.0f 次分配\n", testing.AllocsPerRun(1000, func() { sink = context.WithValue(bg, ctxKey(3), "v") }))
		fmt.Printf("  WithValue(ctx, 字符串 key \"id\", 字符串值):每次 %.0f 次分配\n", testing.AllocsPerRun(1000, func() { sink = context.WithValue(bg, "id", "v") }))
		s := strings.Repeat("x", 10)
		ctx := context.WithValue(bg, keyA{}, s)
		fmt.Printf("  ctx.Value(key) 查找一层:每次 %.0f 次分配\n", testing.AllocsPerRun(1000, func() { sink = ctx.Value(keyA{}) }))
	case "type":
		ctx := context.WithValue(context.Background(), keyA{}, 42)
		defer func() { fmt.Printf("  ctx.Value 取回 any,断言成错误类型:%v\n", recover()) }()
		v := ctx.Value(keyA{})
		fmt.Printf("  取回 %v(类型 %T)\n", v, v)
		_ = v.(string)
	}
}
'''
d = gdir('cv1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(m):
    p = subprocess.run([str(d / 'app'), m], capture_output=True, text=True, timeout=120)
    return tidy(p.stdout + p.stderr)
print('== 一:key 用字符串会撞车(Go 1.27.1,arm64 macOS)')
print(run('collide'))
print('== 二:查找是沿着链表往上找,层数越多越慢')
print(run('depth'))
print('== 三:每次 WithValue 的分配')
print(run('alloc'))
print('== 四:取回来的是 any,类型要自己断言')
print(run('type'))
print('== 五:文档与源码')
r, o = go(gdir('doc1'), 'doc', 'context.WithValue')
ls = [l.strip() for l in o.split('\n')]
i = next(i for i, l in enumerate(ls) if l.startswith('Use context Values only'))
print('  ' + ' '.join(ls[i:i + 2]))
i = next(i for i, l in enumerate(ls) if l.startswith('The provided key must be comparable'))
print('  ' + ' '.join(ls[i:i + 6]))
src = open(GOROOT + '/src/context/context.go').read()
m = re.search(r'func value\(c Context, key any\) any \{.*?\n\}\n', src, re.S)
body = m.group(0)
lines = body.split('\n')
print('  context.go 的 value 函数(节选):')
for l in lines[:9]: print('    ' + l.replace('\t', '    '))
