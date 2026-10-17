import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n7')
PRE = '''package main
import ("fmt"; "net/http/httptest"; "strings"; "github.com/gin-gonic/gin")
func try(r *gin.Engine, method, url string) {
	w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest(method, url, strings.NewReader("")))
	loc := ""; if l := w.Header().Get("Location"); l != "" { loc = "  Location: " + l }
	fmt.Printf("  %-6s %-24s → %d%s\\n", method, url, w.Code, loc)
}
'''
print('== 一:RedirectFixedPath 默认关闭;打开后大小写、多余斜杠、./ 与 ../ 怎么修正')
r = gin('n7a', PRE + '''
func main() {
	h := func(c *gin.Context) { c.String(200, "ok %s", c.FullPath()) }
	for _, on := range []bool{false, true} {
		r := gin.New(); r.RedirectFixedPath = on
		r.GET("/users/profile", h); r.GET("/Hello", h); r.GET("/files/:name", h); r.GET("/dir/", h)
		fmt.Printf("  === RedirectFixedPath = %v ===\\n", on)
		for _, u := range []string{"/USERS/Profile", "/hello", "/users//profile", "/users/./profile", "/users/x/../profile", "//users/profile", "/Files/ABC", "/DIR", "/DIR/", "/users/PROFILE/"} { try(r, "GET", u) }
	}
}''')
out_lines(r)
print('== 二:源码:RedirectFixedPath 先做 cleanPath,再用大小写不敏感查找;POST 同样是 307')
gfunc('gin.go', 'redirectFixedPath')
gfind('gin.go', r'RedirectFixedPath', ctx=0, maxn=6)
r = gin('n7b', PRE + '''
func main() {
	r := gin.New(); r.RedirectFixedPath = true
	h := func(c *gin.Context) { c.String(200, "ok") }
	r.POST("/Api/Items", h)
	try(r, "POST", "/api/items"); try(r, "POST", "/api//items"); try(r, "GET", "/api/items")
	r.GET("/a/b", h)
	fmt.Println("  --- 同时命中 TSR(少一个斜杠)和大小写错误 ---")
	r.GET("/Docs/", h)
	try(r, "GET", "/docs"); try(r, "GET", "/DOCS/")
}''')
out_lines(r)
print('== 三:代价:打开之后每个 404 都要多做一次 cleanPath + 大小写不敏感遍历。树里 1000 条路由,请求一个不存在的路径')
r = gin('n7c', """package main
import ("fmt"; "net/http"; "net/http/httptest"; "sort"; "testing"; "github.com/gin-gonic/gin")
type nw struct{ h http.Header }
func (w *nw) Header() http.Header { if w.h == nil { w.h = http.Header{} }; return w.h }
func (w *nw) Write(b []byte) (int, error) { return len(b), nil }
func (w *nw) WriteHeader(int) {}
func bench(name string, f func(b *testing.B)) {
	var xs, al []float64
	for i := 0; i < 9; i++ { br := testing.Benchmark(f); xs = append(xs, float64(br.T.Nanoseconds())/float64(br.N)); al = append(al, float64(br.AllocsPerOp())) }
	sort.Float64s(xs)
	fmt.Printf("  %-34s 中位 %7.1f ns/op(最小 %.1f / 最大 %.1f),%.0f allocs/op\\n", name, xs[4], xs[0], xs[8], al[0])
}
func build(fixed bool) *gin.Engine {
	r := gin.New(); r.RedirectFixedPath = fixed; h := func(c *gin.Context) {}
	for i := 0; i < 1000; i++ { r.GET(fmt.Sprintf("/api/v1/resource%d/items/:id", i), h) }
	return r
}
func main() {
	for round := 1; round <= 2; round++ {
		fmt.Printf("  第 %d 轮\\n", round)
		for _, fixed := range []bool{false, true} {
			r := build(fixed); var w nw
			do := func(path string) func(b *testing.B) { req := httptest.NewRequest("GET", path, nil); return func(b *testing.B) { b.ReportAllocs(); for i := 0; i < b.N; i++ { r.ServeHTTP(&w, req) } } }
			bench(fmt.Sprintf("fixed=%v 命中 /api/v1/resource500/items/9", fixed), do("/api/v1/resource500/items/9"))
			bench(fmt.Sprintf("fixed=%v 404 /nothing/here", fixed), do("/nothing/here"))
			bench(fmt.Sprintf("fixed=%v 404 /api/v1/resource500/other", fixed), do("/api/v1/resource500/other"))
		}
	}
}
""", patched=True, timeout=300)
out_lines(r)
