import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n11')
print('== 一:FullPath 的源码与 Context.reset 里怎么清它')
gfunc('context.go', 'FullPath')
gfind('context.go', r'c\.fullPath = ""', ctx=0)
gfind('gin.go', r'c\.fullPath = value\.fullPath', ctx=0)
print('== 二:FullPath 在各种情形下的值:参数路由、Group、通配、中间件里(c.Next 之前)、404、重定向')
r = gin('n11a', """package main
import ("fmt"; "net/http/httptest"; "github.com/gin-gonic/gin")
func main() {
	r := gin.New(); calls := 0
	r.Use(func(c *gin.Context) {
		calls++
		before := c.FullPath(); c.Next()
		fmt.Printf("  %-26s 中间件里 Next 之前 FullPath=%-28q 之后 FullPath=%q 状态=%d\\n", c.Request.Method+" "+c.Request.URL.Path, before, c.FullPath(), c.Writer.Status())
	})
	h := func(c *gin.Context) {}
	r.GET("/users/:id", h)
	r.GET("/files/*path", h)
	api := r.Group("/api/v1")
	api.GET("/orders/:oid/items/:iid", h)
	r.GET("/dir/", h)
	for _, u := range []string{"/users/42", "/files/a/b.txt", "/api/v1/orders/7/items/9", "/nope", "/dir", "/users/"} {
		w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest("GET", u, nil))
		if w.Code == 301 { fmt.Printf("  %-26s 重定向 %d → %s(没有经过中间件)\\n", "GET "+u, w.Code, w.Header().Get("Location")) }
	}
	fmt.Println("  共 6 个请求,中间件执行了", calls, "次")
}""")
out_lines(r)
print('== 三:为什么要用 FullPath:给监控打标签。10000 个不同的用户 ID 请求,按 URL.Path 与按 FullPath 分别有多少个不同的标签')
r = gin('n11b', """package main
import ("fmt"; "net/http/httptest"; "github.com/gin-gonic/gin")
func main() {
	r := gin.New()
	byPath, byFull := map[string]int{}, map[string]int{}
	r.Use(func(c *gin.Context) {
		c.Next()
		byPath[c.Request.URL.Path]++
		fp := c.FullPath(); if fp == "" { fp = "(未匹配)" }
		byFull[fp]++
	})
	r.GET("/users/:id", func(c *gin.Context) {}); r.GET("/users/:id/orders/:oid", func(c *gin.Context) {})
	for i := 0; i < 10000; i++ {
		r.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", fmt.Sprintf("/users/%d", i), nil))
		if i%2 == 0 { r.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", fmt.Sprintf("/users/%d/orders/%d", i, i*3), nil)) }
		if i%10 == 0 { r.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", fmt.Sprintf("/scan/%d.php", i), nil)) }
	}
	fmt.Printf("  按 URL.Path 打标签:%d 个不同的值\\n", len(byPath))
	fmt.Printf("  按 FullPath 打标签:%d 个不同的值:%v\\n", len(byFull), byFull)
}""")
out_lines(r)
print('== 四:Routes() 给出的路由表(Method / Path / Handler 名 / 对应函数)')
r = gin('n11c', """package main
import ("fmt"; "github.com/gin-gonic/gin")
type S struct{}
func (S) List(c *gin.Context) {}
func getUser(c *gin.Context) {}
func main() {
	r := gin.New()
	r.GET("/users/:id", getUser)
	r.POST("/users", func(c *gin.Context) {})
	g := r.Group("/api")
	g.GET("/list", S{}.List)
	g.Use(gin.Logger())
	g.PUT("/x", gin.Recovery())
	for _, ri := range r.Routes() { fmt.Printf("  %-6s %-14s handler=%s\\n", ri.Method, ri.Path, ri.Handler) }
}""")
out_lines(r)
