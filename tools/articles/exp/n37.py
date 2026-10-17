import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n37')
TPL = {
 'tpl/index.html': '<h1>{{.Title}}</h1><p>{{.Body}}</p>',
 'tpl/user.html': '<div class="u">{{.Name | upper}} - {{.Bio}}</div>',
 'tpl/layout.html': '{{define "layout"}}<html><body>{{template "content" .}}</body></html>{{end}}',
 'tpl/page.html': '{{template "layout" .}}{{define "content"}}<main>{{.Msg}}</main>{{end}}',
 'tpl/partial.html': 'ok {{.Missing.Field}} 后面的内容',
 'tpl/a/item.html': '<i>A 目录的 item</i>',
 'tpl/b/item.html': '<i>B 目录的 item</i>',
 'tpl/c/uniq.html': '{{define "c/uniq.html"}}<i>带目录前缀的名字</i>{{end}}',
}
PRE = '''package main
import ("fmt"; "html/template"; "net/http/httptest"; "os"; "strings"; "testing"; "sort"; "github.com/gin-gonic/gin")
var _ = template.HTMLEscapeString
var _ = os.Getpid
var _ = testing.Benchmark
var _ = sort.Strings
func get(r *gin.Engine, url string) (*httptest.ResponseRecorder, string) { w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest("GET", url, nil)); return w, strings.TrimSpace(w.Body.String()) }
'''
def T(src): d = dict(TPL); d['main.go'] = PRE + src; return d
print('== 一:LoadHTMLGlob 的源码与两种渲染器:release 启动时解析一次;debug 每次渲染都重新解析')
gfunc('gin.go', 'LoadHTMLGlob')
gfind('render/html.go', r'func \(r HTMLProduction\) Instance|func \(r HTMLDebug\) Instance|func \(r HTMLDebug\) loadTemplate|ParseGlob|template\.Must', ctx=0, maxn=8)
print('== 二:基本用法:模板名是文件的 base name;自动转义;template.HTML 可信;SetFuncMap;define / template 嵌套')
r = gin('n37a', T('''
func main() {
	r := gin.New()
	r.SetFuncMap(template.FuncMap{"upper": strings.ToUpper})
	r.LoadHTMLGlob("tpl/*.html")
	r.GET("/i", func(c *gin.Context) { c.HTML(200, "index.html", gin.H{"Title": "标题", "Body": "正文 <b>粗体</b> & 'q' <script>alert(1)</script>"}) })
	r.GET("/u", func(c *gin.Context) { c.HTML(200, "user.html", gin.H{"Name": "ann", "Bio": template.HTML("<em>可信的 HTML</em>")}) })
	r.GET("/u2", func(c *gin.Context) { c.HTML(200, "user.html", gin.H{"Name": "bob", "Bio": "<em>不可信</em>"}) })
	r.GET("/p", func(c *gin.Context) { c.HTML(200, "page.html", gin.H{"Msg": "嵌套模板"}) })
	for _, p := range []string{"/i", "/u", "/u2", "/p"} { w, b := get(r, p); fmt.Printf("  %-4s → %d Content-Type=%q\\n       %s\\n", p, w.Code, w.Header().Get("Content-Type"), b) }
}'''))
out_lines(r)
print('== 三:debug 与 release 的区别:改了模板文件之后,不重启能不能看到;每次渲染的耗时')
src3 = '''
func main() {
	r := gin.New()
	r.SetFuncMap(template.FuncMap{"upper": strings.ToUpper})
	r.LoadHTMLGlob("tpl/*.html")
	r.GET("/i", func(c *gin.Context) { c.HTML(200, "index.html", gin.H{"Title": "T", "Body": "B"}) })
	_, b1 := get(r, "/i")
	os.WriteFile("tpl/index.html", []byte("<h1>改过的模板 {{.Title}}</h1>"), 0o644)
	_, b2 := get(r, "/i")
	fmt.Printf("  GIN_MODE=%s 改模板文件前 %q → 改之后(不重启)%q\\n", gin.Mode(), b1, b2)
	os.WriteFile("tpl/index.html", []byte("<h1>{{.Title}}</h1><p>{{.Body}}</p>"), 0o644)
	var xs []float64
	for i := 0; i < 5; i++ {
		br := testing.Benchmark(func(b *testing.B) {
			b.ReportAllocs()
			req := httptest.NewRequest("GET", "/i", nil); for i := 0; i < b.N; i++ { r.ServeHTTP(httptest.NewRecorder(), req) }
		})
		xs = append(xs, float64(br.T.Nanoseconds())/float64(br.N)/1000)
	}
	sort.Float64s(xs)
	fmt.Printf("  GIN_MODE=%s 渲染一次 index.html(glob 匹配 5 个模板文件):中位 %.1f µs\\n", gin.Mode(), xs[2])
}'''
for mode in ['release', 'debug']:
    r = gin('n37b_' + mode, T(src3), env=dict(GIN_MODE=mode), timeout=300)
    pr('\n'.join(l for l in r['out'].split('\n') if l.startswith('  GIN_MODE')) if r['crc'] == 0 else r['cout'], 10, '')
print('== 四:不同目录下的同名文件:模板名只取 base name,后一个覆盖前一个;在文件里 define 带目录的名字可以避免')
r = gin('n37c', T('''
func main() {
	r := gin.New()
	r.LoadHTMLGlob("tpl/*/*.html")
	r.GET("/a", func(c *gin.Context) { c.HTML(200, "item.html", nil) })
	r.GET("/u", func(c *gin.Context) { c.HTML(200, "c/uniq.html", nil) })
	r.GET("/uu", func(c *gin.Context) { c.HTML(200, "uniq.html", nil) })
	for _, p := range []string{"/a", "/u", "/uu"} { _, b := get(r, p); fmt.Printf("  %-4s → %s\\n", p, b) }
}'''))
out_lines(r)
print('== 五:出错时:找不到模板名、渲染中途出错(已经写出的部分还是发给了客户端)、SetFuncMap 写在 LoadHTMLGlob 之后')
r = gin('n37d', T('''
func main() {
	r := gin.New()
	r.SetFuncMap(template.FuncMap{"upper": strings.ToUpper})
	r.LoadHTMLGlob("tpl/*.html")
	var errs []string
	r.Use(func(c *gin.Context) { c.Next(); for _, e := range c.Errors { errs = append(errs, e.Error()) } })
	r.GET("/nope", func(c *gin.Context) { c.HTML(200, "nope.html", nil) })
	r.GET("/partial", func(c *gin.Context) { c.HTML(200, "partial.html", struct{ X int }{1}) })
	for _, p := range []string{"/nope", "/partial"} { w, b := get(r, p); fmt.Printf("  %-9s → 状态 %d 正文 %q\\n", p, w.Code, b) }
	for _, e := range errs { fmt.Printf("  c.Errors: %s\\n", e) }
	func() {
		defer func() { fmt.Printf("  先 LoadHTMLGlob 后 SetFuncMap(模板里用了 upper)→ panic: %v\\n", recover()) }()
		r2 := gin.New(); r2.LoadHTMLGlob("tpl/*.html"); r2.SetFuncMap(template.FuncMap{"upper": strings.ToUpper})
	}()
}'''))
out_lines(r)
