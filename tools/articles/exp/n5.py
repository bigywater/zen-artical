import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n5')
print('== 一:Group 怎么拼路径(joinPaths 源码)')
gsrcl('utils.go', 135, 145)
gsrcl('routergroup.go', 72, 79, title='routergroup.go 的 Group')
gsrcl('routergroup.go', 241, 248, title='routergroup.go 的 combineHandlers')
print('== 二:Group(a) + GET(b) 的各种拼法,登记到路由表里的最终路径')
r = gin('n5a', '''package main
import ("fmt"; "github.com/gin-gonic/gin")
func main() {
	cases := [][2]string{{"/api", "/users"}, {"/api/", "users"}, {"/api", "users"}, {"/api", "/users/"}, {"/api", ""}, {"/api", "/"}, {"api", "users"}, {"/", "/users"}, {"", "/users"}, {"/api//v1", "//users"}, {"/api/v1/..", "/users"}}
	for _, c := range cases {
		func() {
			defer func() { if e := recover(); e != nil { fmt.Printf("  Group(%q).GET(%q) → panic: %v\\n", c[0], c[1], e) } }()
			r := gin.New(); g := r.Group(c[0])
			g.GET(c[1], func(c *gin.Context) {})
			fmt.Printf("  Group(%q).GET(%q) → 路由 %q,BasePath()=%q\\n", c[0], c[1], r.Routes()[0].Path, g.BasePath())
		}()
	}
}''')
out_lines(r)
print('== 三:中间件继承:嵌套 Group,每条路由最终有几个 handler,请求时的执行顺序')
r = gin('n5b', """package main
import ("fmt"; "net/http/httptest"; "strings"; "github.com/gin-gonic/gin")
func mw(name string) gin.HandlerFunc { return func(c *gin.Context) { fmt.Printf(" %s", name); c.Next(); fmt.Printf(" /%s", name) } }
func main() {
	r := gin.New()
	r.Use(mw("global"))
	api := r.Group("/api", mw("api"))
	v1 := api.Group("/v1")
	v1.Use(mw("v1"))
	admin := v1.Group("/admin", mw("admin"))
	r.GET("/ping", func(c *gin.Context) { fmt.Print(" [h]") })
	api.GET("/a", func(c *gin.Context) { fmt.Print(" [h]") })
	v1.GET("/b", func(c *gin.Context) { fmt.Print(" [h]") })
	admin.GET("/c", mw("c-only"), func(c *gin.Context) { fmt.Print(" [h]") })
	for _, u := range []string{"/ping", "/api/a", "/api/v1/b", "/api/v1/admin/c"} {
		fmt.Printf("  GET %-17s →", u)
		r.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", u, nil)); fmt.Println()
	}
	for _, l := range strings.Split(r.DumpTree("GET"), "\\n") { if strings.Contains(l, "handlers=") { fmt.Println("  树里:" + strings.TrimSpace(l)) } }
}""", patched=True)
out_lines(r)
print('== 四:中间件只作用于“Use 之后注册”的路由(handler 链在注册那一刻就拼好了)')
r = gin('n5c', """package main
import ("fmt"; "net/http/httptest"; "github.com/gin-gonic/gin")
func mw(name string) gin.HandlerFunc { return func(c *gin.Context) { fmt.Printf(" %s", name); c.Next() } }
func h(c *gin.Context) { fmt.Print(" [h]") }
func main() {
	r := gin.New()
	r.GET("/before", h)
	r.Use(mw("late"))
	r.GET("/after", h)
	g := r.Group("/g")
	sub := g.Group("/s")
	g.Use(mw("g-late"))
	g.GET("/own", h)
	sub.GET("/x", h)
	g2 := r.Group("/g2")
	g2.GET("/early", h)
	g2.Use(mw("g2-late"))
	g2.GET("/late", h)
	for _, u := range []string{"/before", "/after", "/g/own", "/g/s/x", "/g2/early", "/g2/late"} {
		fmt.Printf("  GET %-12s →", u)
		r.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", u, nil)); fmt.Println()
	}
}""")
out_lines(r)
print('== 五:404 要不要经过全局中间件?(Engine.Use 会重建 404/405 的 handler 链,Group.Use 不会)')
gfind('gin.go', r'rebuild404Handlers|rebuild405Handlers|allNoRoute = ', ctx=0, maxn=8)
r = gin('n5d', """package main
import ("fmt"; "net/http/httptest"; "github.com/gin-gonic/gin")
func mw(name string) gin.HandlerFunc { return func(c *gin.Context) { fmt.Printf(" %s", name); c.Next() } }
func main() {
	r := gin.New()
	r.Use(mw("A"))
	g := r.Group("/g", mw("G"))
	g.GET("/ok", func(c *gin.Context) { c.String(200, "ok") })
	for _, u := range []string{"/g/ok", "/g/nothing", "/nothing"} {
		fmt.Printf("  GET %-12s →", u)
		w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest("GET", u, nil)); fmt.Printf("  状态 %d\\n", w.Code)
	}
}""")
out_lines(r)
