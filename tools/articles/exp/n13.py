import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n13')
print('== 一:Engine.ServeHTTP 与 handleHTTPRequest 的骨架(Gin 源码原文)')
gfunc('gin.go', 'ServeHTTP')
gsrcl('gin.go', 690, 735, title='gin.go 的 handleHTTPRequest(前半)')
print('== 二:Context 来自 sync.Pool:串行请求拿到的是同一个 *Context;reset 把请求相关的字段全清掉(Keys 不会泄漏给下一个请求)')
gfunc('context.go', 'reset')
r = gin('n13a', """package main
import ("fmt"; "net/http/httptest"; "github.com/gin-gonic/gin")
func main() {
	r := gin.New()
	var seen []*gin.Context
	r.GET("/u/:id", func(c *gin.Context) {
		fmt.Printf("  请求 %-8s Context=%p  进入时 Keys=%v Errors=%d Params=%v\\n", c.Param("id"), c, c.Keys, len(c.Errors), c.Params)
		c.Set("secret", "来自请求 "+c.Param("id")); c.Error(fmt.Errorf("e-%s", c.Param("id"))); seen = append(seen, c)
	})
	for _, id := range []string{"a", "b", "c"} { r.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", "/u/"+id, nil)) }
	fmt.Println("  三次请求是否同一个 Context:", seen[0] == seen[1] && seen[1] == seen[2])
	fmt.Printf("  请求结束后还拿着第 1 个 Context 指针去读:Keys=%v Errors=%d Params=%v(已经是第 3 个请求的了)\\n", seen[0].Keys, len(seen[0].Errors), seen[0].Params)
}""")
out_lines(r)
print('== 三:每个请求分配多少次内存(testing.AllocsPerRun,ServeHTTP + 丢弃输出的 ResponseWriter)')
r = gin('n13b', """package main
import ("fmt"; "io"; "net/http"; "net/http/httptest"; "testing"; "github.com/gin-gonic/gin")
type nw struct{ h http.Header }
func (w *nw) Header() http.Header { if w.h == nil { w.h = http.Header{} }; return w.h }
func (w *nw) Write(b []byte) (int, error) { return len(b), nil }
func (w *nw) WriteHeader(int) {}
func allocs(name string, r *gin.Engine, method, url string) {
	req := httptest.NewRequest(method, url, nil); var w nw
	r.ServeHTTP(&w, req)
	n := testing.AllocsPerRun(2000, func() { r.ServeHTTP(&w, req) })
	fmt.Printf("  %-44s %.0f allocs/请求\\n", name, n)
}
func main() {
	h := func(c *gin.Context) {}
	r := gin.New()
	r.GET("/static", h); r.GET("/u/:id", h); r.GET("/a/:x/b/:y/c/:z", h); r.GET("/f/*p", h)
	r.GET("/str", func(c *gin.Context) { c.String(200, "hello") })
	r.GET("/json", func(c *gin.Context) { c.JSON(200, gin.H{"a": 1}) })
	r.GET("/st", func(c *gin.Context) { c.Status(204) })
	allocs("静态路由,空 handler", r, "GET", "/static")
	allocs("1 个参数 /u/42", r, "GET", "/u/42")
	allocs("3 个参数", r, "GET", "/a/1/b/2/c/3")
	allocs("通配 /f/x/y/z", r, "GET", "/f/x/y/z")
	allocs("404", r, "GET", "/nothing")
	allocs("c.Status(204)", r, "GET", "/st")
	allocs("c.String(200, \\"hello\\")", r, "GET", "/str")
	allocs("c.JSON(200, gin.H{\\"a\\":1})", r, "GET", "/json")
	m := gin.New(); m.Use(func(c *gin.Context) { c.Next() }, func(c *gin.Context) { c.Next() }, func(c *gin.Context) { c.Next() }); m.GET("/static", h)
	allocs("3 个空中间件 + 静态路由", m, "GET", "/static")
	gin.DefaultWriter = io.Discard; d := gin.Default(); d.GET("/static", h)
	allocs("gin.Default()(Logger+Recovery)+ 静态路由", d, "GET", "/static")
}""")
out_lines(r)
print('== 四:handler 链跑完之后 WriteHeaderNow:只设状态不写正文也会发出状态行;什么都不做是 200')
r = gin('n13c', """package main
import ("fmt"; "net/http/httptest"; "github.com/gin-gonic/gin")
func main() {
	r := gin.New()
	r.GET("/nothing", func(c *gin.Context) {})
	r.GET("/status", func(c *gin.Context) { c.Status(201) })
	r.GET("/header", func(c *gin.Context) { c.Header("X-A", "1") })
	r.GET("/after", func(c *gin.Context) { c.Writer.WriteString("先写正文"); c.Status(500) })
	for _, u := range []string{"/nothing", "/status", "/header", "/after"} {
		w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest("GET", u, nil))
		fmt.Printf("  %-9s → 状态 %d 正文 %q X-A=%q\\n", u, w.Code, w.Body.String(), w.Header().Get("X-A"))
	}
}""")
out_lines(r)
print('== 五:第一次 ServeHTTP 才会跑一次 updateRouteTrees(sync.Once):把路由里转义的冒号 \\\\: 还原成 :')
gfunc('gin.go', 'updateRouteTree')
r = gin('n13d', """package main
import ("fmt"; "net/http/httptest"; "github.com/gin-gonic/gin")
func main() {
	r := gin.New(); h := func(c *gin.Context) { c.String(200, "命中 %s", c.FullPath()) }
	r.GET("/v1/\\\\:action", h); r.GET("/v1/items/:id", h)
	for _, ri := range r.Routes() { fmt.Printf("  第一次请求前 路由表:%q\\n", ri.Path) }
	w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest("GET", "/v1/:action", nil))
	fmt.Printf("  GET /v1/:action → %d %s\\n", w.Code, w.Body.String())
	for _, ri := range r.Routes() { fmt.Printf("  第一次请求后 路由表:%q\\n", ri.Path) }
	w = httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest("GET", "/v1/other", nil)); fmt.Printf("  GET /v1/other → %d(\\\\: 是字面量冒号,不是参数)\\n", w.Code)
}""")
out_lines(r)
