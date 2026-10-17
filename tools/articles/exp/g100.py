import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g100')
SRC = r'''
package main

import (
	"bytes"
	"errors"
	"fmt"
	"os"
	"strings"
	"testing"
	"text/template"
)

type User struct {
	Name  string
	Age   int
	Tags  []string
	Admin bool
}

func (u User) Greeting() string   { return "你好," + u.Name }
func (u *User) PtrMethod() string { return "指针方法:" + u.Name }

func run(label, text string, data any, funcs template.FuncMap, opts ...string) {
	t := template.New("t")
	if funcs != nil { t = t.Funcs(funcs) }
	if len(opts) > 0 { t = t.Option(opts...) }
	t, err := t.Parse(text)
	if err != nil { fmt.Printf("  %-34s 解析失败:%v\n", label, err); return }
	var b bytes.Buffer
	err = t.Execute(&b, data)
	out := strings.ReplaceAll(b.String(), "\n", "\\n")
	if err != nil { fmt.Printf("  %-34s 输出 %q,执行出错:%v\n", label, out, err); return }
	fmt.Printf("  %-34s %s\n", label, out)
}

func main() {
	u := User{Name: "小明", Age: 20, Tags: []string{"a", "b"}, Admin: true}
	switch os.Args[1] {
	case "pipe":
		run(`{{.Name | printf "%q"}}`, `{{.Name | printf "%q"}}`, u, nil)
		run(`{{3 | printf "%d-%d" 1}}`, `{{3 | printf "%d-%d" 1}}`, nil, nil)
		run(`{{.Name | printf "%q" | len}}`, `{{.Name | printf "%q" | len}}`, u, nil)
		run(`{{len .Tags | printf "标签数=%d"}}`, `{{len .Tags | printf "标签数=%d"}}`, u, nil)
		run(`{{printf "%s=%d" .Name .Age}}`, `{{printf "%s=%d" .Name .Age}}`, u, nil)
		run(`{{.Greeting}}`, `{{.Greeting}}`, u, nil)
		run(`{{.PtrMethod}}(值 u)`, `{{.PtrMethod}}`, u, nil)
		run(`{{.PtrMethod}}(&u)`, `{{.PtrMethod}}`, &u, nil)
	case "var":
		funcs := template.FuncMap{"add": func(a, b int) int { return a + b }}
		run(`在 if 里用 := 声明`, `{{$x := 1}}{{if true}}{{$x := 2}}{{end}}{{$x}}`, nil, nil)
		run(`在 if 里用 = 赋值`, `{{$x := 1}}{{if true}}{{$x = 2}}{{end}}{{$x}}`, nil, nil)
		run(`range 里累加`, `{{$n := 0}}{{range .}}{{$n = add $n .}}{{end}}{{$n}}`, []int{1, 2, 3, 4}, funcs)
		run(`range 的下标和值`, `{{range $i, $v := .}}{{$i}}={{$v}};{{end}}`, []string{"x", "y"}, nil)
		run(`$ 指向根数据`, `{{range .Tags}}{{$.Name}}-{{.}};{{end}}`, u, nil)
		run(`with 改变 .`, `{{with .Tags}}{{index . 0}}{{end}}|{{with .Name}}{{.}}{{end}}`, u, nil)
	case "missing":
		m := map[string]int{"a": 1}
		run(`map 缺 key(默认)`, `{{.b}}`, m, nil)
		run(`map 缺 key(missingkey=error)`, `{{.b}}`, m, nil, "missingkey=error")
		run(`map 缺 key(missingkey=zero)`, `{{.b}}`, m, nil, "missingkey=zero")
		run(`struct 缺字段`, `{{.Nope}}`, u, nil)
		run(`nil 指针上取字段`, `{{.Name}}`, (*User)(nil), nil)
		run(`未定义的函数`, `{{nofunc .}}`, nil, nil)
	case "truthy":
		run(`{{if .}} 对空字符串`, `[{{if .}}真{{else}}假{{end}}]`, "", nil)
		run(`{{if .}} 对 0`, `[{{if .}}真{{else}}假{{end}}]`, 0, nil)
		run(`{{if .}} 对空切片`, `[{{if .}}真{{else}}假{{end}}]`, []int{}, nil)
		run(`{{if .}} 对 nil`, `[{{if .}}真{{else}}假{{end}}]`, nil, nil)
		run(`{{if .}} 对非空 map`, `[{{if .}}真{{else}}假{{end}}]`, map[string]int{"a": 1}, nil)
		run(`{{if .}} 对结构体(零值)`, `[{{if .}}真{{else}}假{{end}}]`, User{}, nil)
		cnt := 0
		funcs := template.FuncMap{"side": func() bool { cnt++; return true }}
		run(`or 短路:{{or true (side)}}`, `{{or true (side)}}`, nil, funcs)
		fmt.Printf("    side() 被调用了 %d 次\n", cnt)
	case "funcs":
		boom := template.FuncMap{"div": func(a, b int) (int, error) { if b == 0 { return 0, errors.New("除数为 0") }; return a / b, nil }}
		run(`div 10 2`, `{{div 10 2}}`, nil, boom)
		run(`div 10 0(函数返回 error)`, `前缀{{div 10 0}}后缀`, nil, boom)
		func() {
			defer func() { fmt.Printf("  %-34s panic:%v\n", "先 Parse 再 Funcs", recover()) }()
			template.Must(template.New("t").Parse(`{{up "x"}}`)).Funcs(template.FuncMap{"up": strings.ToUpper})
		}()
		func() {
			defer func() { fmt.Printf("  %-34s panic:%v\n", "FuncMap 里函数返回 3 个值", recover()) }()
			template.New("t").Funcs(template.FuncMap{"bad": func() (int, int, int) { return 1, 2, 3 }})
		}()
	case "trim":
		run(`不修剪空白`, "[\n{{.Name}}\n]", u, nil)
		run(`{{- 修剪左边 -}}`, "[\n{{- .Name -}}\n]", u, nil)
	case "cost":
		tpl := template.Must(template.New("t").Parse(`用户 {{.Name}},年龄 {{.Age}},标签 {{range .Tags}}[{{.}}]{{end}}`))
		var b bytes.Buffer
		r1 := testing.Benchmark(func(b2 *testing.B) { b2.ReportAllocs(); for i := 0; i < b2.N; i++ { b.Reset(); tpl.Execute(&b, u) } })
		r2 := testing.Benchmark(func(b2 *testing.B) { b2.ReportAllocs(); for i := 0; i < b2.N; i++ { b.Reset(); fmt.Fprintf(&b, "用户 %s,年龄 %d,标签 %s", u.Name, u.Age, "[a][b]") } })
		r3 := testing.Benchmark(func(b2 *testing.B) { b2.ReportAllocs(); for i := 0; i < b2.N; i++ { t2 := template.Must(template.New("t").Parse(`用户 {{.Name}},年龄 {{.Age}},标签 {{range .Tags}}[{{.}}]{{end}}`)); b.Reset(); t2.Execute(&b, u) } })
		fmt.Printf("  已解析的模板 Execute:%d ns/次、%d 次分配;fmt.Fprintf:%d ns/次、%d 次分配;每次都 Parse + Execute:%d ns/次、%d 次分配\n", r1.NsPerOp(), r1.AllocsPerOp(), r2.NsPerOp(), r2.AllocsPerOp(), r3.NsPerOp(), r3.AllocsPerOp())
	}
}
'''
d = gdir('tp1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(m):
    p = subprocess.run([str(d / 'app'), m], capture_output=True, text=True, timeout=300)
    return tidy(p.stdout + p.stderr)
for sec, m, title in (('一', 'pipe', '管道:前一个命令的结果作为后一个命令的“最后一个参数”(Go 1.27.1)'), ('二', 'var', '变量与作用域'), ('三', 'missing', '缺 key、缺字段与未定义的函数'), ('四', 'truthy', '什么算“真”'), ('五', 'funcs', 'FuncMap'), ('六', 'trim', '空白修剪'), ('七', 'cost', '成本(arm64 macOS)')):
    print(f'== {sec}:{title}')
    print(run(m))
print('== 八:text/template 文档里关于管道的说明')
r, o = go(gdir('doc1'), 'doc', 'text/template')
t = ' '.join(l.strip() for l in o.split('\n'))
for k in ('A pipeline may be "chained" by separating a sequence of commands with pipeline characters',):
    i = t.find(k)
    print('  ' + (t[i:i + 260] if i >= 0 else '(未找到)' + k))
