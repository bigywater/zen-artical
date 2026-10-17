import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g101')
SRC = r'''
package main

import (
	"bytes"
	"fmt"
	html "html/template"
	"os"
	"strings"
	text "text/template"
)

func exec(parse func(string) (interface{ Execute(w interface{ Write([]byte) (int, error) }, data any) error }, error), tpl string, data any) string { return "" }

func runHTML(tpl string, data any) string {
	t, err := html.New("t").Parse(tpl)
	if err != nil { return "解析失败:" + err.Error() }
	var b bytes.Buffer
	if err := t.Execute(&b, data); err != nil { e := err.Error(); if len(e) > 120 { e = e[:120] + "…" }; return b.String() + "  ← 执行出错:" + e }
	return b.String()
}

func runText(tpl string, data any) string {
	t, err := text.New("t").Parse(tpl)
	if err != nil { return "解析失败:" + err.Error() }
	var b bytes.Buffer
	if err := t.Execute(&b, data); err != nil { return b.String() + "  ← 执行出错:" + err.Error() }
	return b.String()
}

func main() {
	xss := `<script>alert(1)</script>`
	switch os.Args[1] {
	case "contexts":
		cases := []struct{ name, tpl string; data any }{
			{"HTML 文本", `<p>{{.}}</p>`, xss},
			{"带引号的属性值", `<a title="{{.}}">x</a>`, `" onmouseover="alert(1)`},
			{"不带引号的属性值", `<a title={{.}}>x</a>`, `x onmouseover=alert(1)`},
			{"href 里的 URL(危险协议)", `<a href="{{.}}">x</a>`, `javascript:alert(1)`},
			{"href 里的 URL(正常)", `<a href="{{.}}">x</a>`, `https://example.com/a b?x=1&y=2`},
			{"URL 查询参数", `<a href="/s?q={{.}}">x</a>`, `a&b=<c>`},
			{"JavaScript 里的字符串", `<script>var s = {{.}};</script>`, `</script><script>alert(1)`},
			{"JavaScript 里的数字", `<script>var n = {{.}};</script>`, 42},
			{"JavaScript 里的对象", `<script>var o = {{.}};</script>`, map[string]any{"a": 1, "b": "<x>"}},
			{"CSS 属性值", `<p style="color: {{.}}">x</p>`, `red; background: url(javascript:alert(1))`},
			{"HTML 注释里", `<!-- {{.}} -->x`, `--><script>`},
		}
		for _, c := range cases {
			fmt.Printf("  [%s] html/template: %s\n", c.name, runHTML(c.tpl, c.data))
		}
		fmt.Printf("  对比:text/template 处理 HTML 文本: %s\n", runText(`<p>{{.}}</p>`, xss))
	case "bypass":
		fmt.Printf("  传 string:%s\n", runHTML(`<p>{{.}}</p>`, "<b>粗体</b>"))
		fmt.Printf("  传 template.HTML(声明“这段已经安全”):%s\n", runHTML(`<p>{{.}}</p>`, html.HTML("<b>粗体</b>")))
		fmt.Printf("  传 template.HTML 但里面有脚本:%s(调用方负责保证它安全)\n", runHTML(`<p>{{.}}</p>`, html.HTML(xss)))
		fmt.Printf("  传 template.URL(\"javascript:alert(1)\") 到 href:%s\n", runHTML(`<a href="{{.}}">x</a>`, html.URL("javascript:alert(1)")))
	case "errors":
		fmt.Printf("  分支让上下文不一致:%s\n", runHTML(`{{if .}}<a href="{{else}}<a title="{{end}}x">y</a>`, true))
		fmt.Printf("  在 <script> 里拼 JS 标识符:%s\n", runHTML(`<script>var {{.}} = 1;</script>`, "x"))
		fmt.Printf("  JS 反引号模板字符串里的 {{.}}(值是 a`b):%s\n", runHTML("<script>var s = `{{.}}`;</script>", "a`b"))
	case "once":
		t := html.Must(html.New("t").Parse(`<p>{{.}}</p>`))
		var b bytes.Buffer
		t.Execute(&b, "<a>")
		_, err := t.Parse(`<p>{{.}}</p>`)
		fmt.Printf("  已经 Execute 过的模板再 Parse:%v\n", err)
		_ = strings.Repeat
	}
}
'''
d = gdir('ht3'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); print(o) if rc else None; assert rc == 0, o
def run(m):
    p = subprocess.run([str(d / 'app'), m], capture_output=True, text=True, timeout=300)
    return tidy(p.stdout + p.stderr)
print('== 一:同一个值,放在不同的上下文里,html/template 的转义结果(Go 1.27.1)')
print(run('contexts'))
print('== 二:声明“这段已经安全”的类型会绕过转义')
print(run('bypass'))
print('== 三:模板写法有歧义时,Execute 会报错')
print(run('errors'))
print('== 四:Execute 之后不能再 Parse')
print(run('once'))
print('== 五:html/template 文档里关于上下文转义的说明')
r, o = go(gdir('doc1'), 'doc', 'html/template')
t = ' '.join(l.strip() for l in o.split('\n'))
i = t.find('This package wraps text/template')
j = t.find('If successful, tmpl will now be injection-safe.')
print('  ' + t[i:j + len('If successful, tmpl will now be injection-safe.')])
