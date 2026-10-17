import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g102')
SRC = r'''
package main

import (
	"bytes"
	"encoding/gob"
	"encoding/json"
	"fmt"
	"os"
	"testing"
)

type Point struct {
	X, Y int
	Name string
}

type Animal interface{ Sound() string }
type Dog struct{ Name string }

func (d Dog) Sound() string { return "汪" }

type Holder struct{ A Animal }

type V1 struct{ A int; B string }
type V2 struct{ B string; C float64; A int } // 字段顺序不同,多了 C
type V3 struct{ A string }                    // A 的类型变了

type Big struct {
	ID    int
	Name  string
	Email string
	Score float64
	Tags  []string
	Attrs map[string]int
}

func main() {
	switch os.Args[1] {
	case "sizes":
		var buf bytes.Buffer
		enc := gob.NewEncoder(&buf)
		var sizes []int
		last := 0
		for i := 0; i < 4; i++ {
			enc.Encode(Point{X: i + 1, Y: 2, Name: "p"})
			sizes = append(sizes, buf.Len()-last)
			last = buf.Len()
		}
		fmt.Printf("  同一个 Encoder 连续 Encode 4 个 Point{X,Y,Name}:每条消息的字节数 = %v(第一条含类型定义)\n", sizes)
		var sizes2 []int
		for i := 0; i < 4; i++ {
			var b bytes.Buffer
			gob.NewEncoder(&b).Encode(Point{X: i + 1, Y: 2, Name: "p"})
			sizes2 = append(sizes2, b.Len())
		}
		fmt.Printf("  每次新建 Encoder:每条消息的字节数 = %v(类型定义每次都重发)\n", sizes2)
		j, _ := json.Marshal(Point{X: 1, Y: 2, Name: "p"})
		fmt.Printf("  同一个值的 JSON:%d 字节(%s)\n", len(j), string(j))
		var b3 bytes.Buffer
		gob.NewEncoder(&b3).Encode(Point{})
		fmt.Printf("  全是零值的 Point{} 用新 Encoder 编码:%d 字节(零值字段不编码)\n", b3.Len())
		fmt.Printf("  第 2 条消息(同一个 Encoder)的十六进制:%x\n", func() []byte { var b bytes.Buffer; e := gob.NewEncoder(&b); e.Encode(Point{1, 2, "p"}); n := b.Len(); e.Encode(Point{2, 2, "p"}); return b.Bytes()[n:] }())
	case "compat":
		var buf bytes.Buffer
		gob.NewEncoder(&buf).Encode(V1{A: 7, B: "hi"})
		var v2 V2
		err := gob.NewDecoder(bytes.NewReader(buf.Bytes())).Decode(&v2)
		fmt.Printf("  V1{A:7,B:\"hi\"} 解码进字段顺序不同、多了 C 的 V2:%+v,err=%v\n", v2, err)
		var v3 V3
		err = gob.NewDecoder(bytes.NewReader(buf.Bytes())).Decode(&v3)
		fmt.Printf("  解码进 A 变成 string 的 V3:%+v,err=%v\n", v3, err)
		type Empty struct{ Z int }
		var e Empty
		err = gob.NewDecoder(bytes.NewReader(buf.Bytes())).Decode(&e)
		fmt.Printf("  解码进一个字段名完全不同的结构体:%+v,err=%v\n", e, err)
	case "iface":
		var buf bytes.Buffer
		err := gob.NewEncoder(&buf).Encode(Holder{A: Dog{"旺财"}})
		fmt.Printf("  没有 Register 就编码含接口字段的结构体:err=%v\n", err)
		gob.Register(Dog{})
		buf.Reset()
		err = gob.NewEncoder(&buf).Encode(Holder{A: Dog{"旺财"}})
		var h Holder
		err2 := gob.NewDecoder(&buf).Decode(&h)
		fmt.Printf("  gob.Register(Dog{}) 之后:编码 err=%v,解码 err=%v,得到 %#v\n", err, err2, h)
	case "speed":
		v := Big{ID: 12345, Name: "张三", Email: "zhangsan@example.com", Score: 98.5, Tags: []string{"a", "bb", "ccc"}, Attrs: map[string]int{"x": 1, "y": 2}}
		var buf bytes.Buffer
		gob.NewEncoder(&buf).Encode(v)
		first := buf.Len()
		enc := gob.NewEncoder(&buf)
		enc.Encode(v)
		n0 := buf.Len()
		enc.Encode(v)
		second := buf.Len() - n0
		j, _ := json.Marshal(v)
		fmt.Printf("  Big 结构体:JSON %d 字节;gob 新 Encoder 的单条 %d 字节;同一个 Encoder 的第 2 条 %d 字节\n", len(j), first, second)
		r1 := testing.Benchmark(func(b *testing.B) { b.ReportAllocs(); for i := 0; i < b.N; i++ { var bb bytes.Buffer; gob.NewEncoder(&bb).Encode(v) } })
		var bb bytes.Buffer
		e2 := gob.NewEncoder(&bb)
		e2.Encode(v)
		r2 := testing.Benchmark(func(b *testing.B) { b.ReportAllocs(); for i := 0; i < b.N; i++ { bb.Reset(); e2.Encode(v) } })
		r3 := testing.Benchmark(func(b *testing.B) { b.ReportAllocs(); for i := 0; i < b.N; i++ { json.Marshal(v) } })
		fmt.Printf("  编码:gob 每次新建 Encoder %d ns/次、%d 次分配;gob 复用 Encoder %d ns/次、%d 次分配;JSON %d ns/次、%d 次分配\n", r1.NsPerOp(), r1.AllocsPerOp(), r2.NsPerOp(), r2.AllocsPerOp(), r3.NsPerOp(), r3.AllocsPerOp())
		var one bytes.Buffer
		gob.NewEncoder(&one).Encode(v)
		d1 := testing.Benchmark(func(b *testing.B) { b.ReportAllocs(); for i := 0; i < b.N; i++ { var o Big; gob.NewDecoder(bytes.NewReader(one.Bytes())).Decode(&o) } })
		d2 := testing.Benchmark(func(b *testing.B) { b.ReportAllocs(); for i := 0; i < b.N; i++ { var o Big; json.Unmarshal(j, &o) } })
		fmt.Printf("  解码:gob(每次新建 Decoder)%d ns/次、%d 次分配;JSON %d ns/次、%d 次分配\n", d1.NsPerOp(), d1.AllocsPerOp(), d2.NsPerOp(), d2.AllocsPerOp())
		var stream bytes.Buffer
		se := gob.NewEncoder(&stream)
		for i := 0; i < 1000; i++ { se.Encode(v) }
		sd := testing.Benchmark(func(b *testing.B) {
			b.ReportAllocs()
			for i := 0; i < b.N; i++ {
				dec := gob.NewDecoder(bytes.NewReader(stream.Bytes()))
				for k := 0; k < 1000; k++ { var o Big; dec.Decode(&o) }
			}
		})
		fmt.Printf("  解码:一个 Decoder 连续解 1000 条消息,平均每条 %d ns、%d 次分配(含第一条编译解码器的成本)\n", sd.NsPerOp()/1000, sd.AllocsPerOp()/1000)
	}
}
'''
d = gdir('gb1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(m):
    p = subprocess.run([str(d / 'app'), m], capture_output=True, text=True, timeout=300)
    return tidy(p.stdout + p.stderr)
print('== 一:类型信息只发一次(Go 1.27.1)')
print(run('sizes'))
print('== 二:字段按名字匹配,顺序无关;多出来的字段被忽略')
print(run('compat'))
print('== 三:接口字段必须 Register')
print(run('iface'))
print('== 四:大小与速度(和 JSON 对比,arm64 macOS)')
print(run('speed'))
print('== 五:encoding/gob 包文档的开头')
r, o = go(gdir('doc1'), 'doc', 'encoding/gob')
t = ' '.join(l.strip() for l in o.split('\n'))
m = re.search(r'The implementation compiles a custom codec.*?amortizing the cost of compilation\.', t)
print('  ' + (m.group(0) if m else '(未找到)'))
