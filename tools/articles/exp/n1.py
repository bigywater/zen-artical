import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n1')
HDR = 'package main\nimport ("fmt"; "net/http"; "net/http/httptest"; "github.com/gin-gonic/gin")\nvar _ = http.StatusOK\nvar _ = httptest.NewRecorder\n'
print('== 一:node 结构体与四种节点类型(Gin 源码原文)')
gsrcl('tree.go', 90, 108)
print('== 二:注册 8 条 GET 路由之后,树长什么样(DumpTree 是我在源码副本里加的只读打印函数)')
r = gin('n1a', HDR + '''
func main() {
	r := gin.New(); h := func(c *gin.Context) {}
	routes := []string{"/", "/users", "/users/:id", "/users/:id/posts", "/users/new", "/static/*filepath", "/search", "/src/a/b"}
	for _, p := range routes { r.GET(p, h) }
	fmt.Println("注册顺序:", routes)
	fmt.Print(r.DumpTree("GET"))
}''', patched=True)
out_lines(r)
print('== 三::id 节点和 *filepath 节点的细节(只注册两条路由)')
r = gin('n1b', HDR + '''
func main() {
	r := gin.New(); h := func(c *gin.Context) {}
	r.GET("/users/:id", h)
	fmt.Println("[只有 /users/:id]"); fmt.Print(r.DumpTree("GET"))
	r2 := gin.New()
	r2.GET("/static/*filepath", h)
	fmt.Println("[只有 /static/*filepath]"); fmt.Print(r2.DumpTree("GET"))
	r3 := gin.New()
	r3.GET("/a/:x/b/:y/*rest", h)
	fmt.Println("[/a/:x/b/:y/*rest]"); fmt.Print(r3.DumpTree("GET"))
}''', patched=True)
out_lines(r)
print('== 四:匹配时参数怎么取出来(同一棵树、同一个 handler 打印 c.Params 和 c.FullPath())')
r = gin('n1c', HDR + '''
func main() {
	r := gin.New()
	h := func(c *gin.Context) { fmt.Printf("  %-28s → FullPath=%-22q Params=%v\\n", c.Request.URL.Path, c.FullPath(), c.Params) }
	for _, p := range []string{"/users/new", "/users/:id", "/users/:id/posts", "/static/*filepath", "/a/:x/b/:y/*rest"} { r.GET(p, h) }
	for _, u := range []string{"/users/new", "/users/42", "/users/42/posts", "/static/css/app.css", "/static/", "/a/1/b/2/c/d/e"} {
		r.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", u, nil))
	}
	for _, u := range []string{"/users/", "/users/42/post", "/static"} {
		w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest("GET", u, nil))
		fmt.Printf("  %-28s → 状态码 %d 位置 %q\\n", u, w.Code, w.Header().Get("Location"))
	}
}''', patched=True)
out_lines(r)
print('== 五:树的规模:各注册 1000 条静态/参数路由后的节点个数(DumpTree 行数)')
r = gin('n1d', '''package main
import ("fmt"; "strings"; "strconv"; "github.com/gin-gonic/gin")
func main() {
	h := func(c *gin.Context) {}
	a := gin.New(); b := gin.New()
	for i := 0; i < 1000; i++ { a.GET("/api/v1/resource"+strconv.Itoa(i)+"/list", h); b.GET("/api/v1/resource"+strconv.Itoa(i)+"/:id", h) }
	fmt.Println("1000 条静态路由 节点数:", strings.Count(a.DumpTree("GET"), "\\n"))
	fmt.Println("1000 条带 :id 的路由 节点数:", strings.Count(b.DumpTree("GET"), "\\n"))
	c := gin.New()
	for _, m := range []string{"GET", "POST", "PUT", "DELETE"} { c.Handle(m, "/x", h) }
	fmt.Println("4 个方法各注册 /x 之后的树(顺序):", c.TreeMethods())
}''', patched=True)
out_lines(r)
