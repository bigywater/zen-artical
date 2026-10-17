import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n18')
PRE = '''package main
import ("fmt"; "net/http/httptest"; "github.com/gin-gonic/gin")
'''
print('== 一:Abort 的源码:只是把 index 设成 abortIndex(63);Next 的循环条件因此不再成立')
gfunc('context.go', 'Next'); gfunc('context.go', 'Abort'); gfunc('context.go', 'IsAborted')
gfind('context.go', r'abortIndex int8', ctx=0)
print('== 二:Abort() 不是 return:调用之后当前 handler 剩下的代码照样执行,只是后面的 handler 不再执行')
r = gin('n18a', PRE + '''
func main() {
	r := gin.New()
	r.Use(func(c *gin.Context) { fmt.Println("  [M1 前]"); c.Next(); fmt.Println("  [M1 后] IsAborted =", c.IsAborted()) })
	r.Use(func(c *gin.Context) {
		fmt.Println("  [M2 前]")
		if c.Query("deny") == "1" { c.Abort(); fmt.Println("  [M2] Abort() 之后这一行仍然执行") }
		c.Next()   // Abort 之后再 Next:循环条件已不成立,什么都不会执行
		fmt.Println("  [M2 后]")
	})
	r.GET("/x", func(c *gin.Context) { fmt.Println("  [handler] 执行"); c.String(200, "ok") })
	for _, u := range []string{"/x", "/x?deny=1"} {
		fmt.Println(" ", u); w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest("GET", u, nil)); fmt.Printf("  → 状态 %d 正文 %q\\n", w.Code, w.Body.String())
	}
}''')
out_lines(r)
print('== 三:几种 Abort 变体写了什么')
r = gin('n18b', PRE + '''
func main() {
	type c1 struct{ name string; f gin.HandlerFunc }
	cs := []c1{
		{"Abort()", func(c *gin.Context) { c.Abort() }},
		{"AbortWithStatus(401)", func(c *gin.Context) { c.AbortWithStatus(401) }},
		{"AbortWithStatusJSON(403, ...)", func(c *gin.Context) { c.AbortWithStatusJSON(403, gin.H{"err": "forbidden"}) }},
		{"AbortWithError(400, err)", func(c *gin.Context) { c.AbortWithError(400, fmt.Errorf("坏请求")) }},
		{"Abort() 后 c.JSON(418, ...)", func(c *gin.Context) { c.Abort(); c.JSON(418, gin.H{"t": 1}) }},
		{"AbortWithStatus(401) 后 c.JSON(200, ...)", func(c *gin.Context) { c.AbortWithStatus(401); c.JSON(200, gin.H{"t": 1}) }},
	}
	for _, x := range cs {
		r := gin.New()
		r.Use(x.f, func(c *gin.Context) { c.Next() })
		r.GET("/x", func(c *gin.Context) { c.String(200, "handler") })
		w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest("GET", "/x", nil))
		fmt.Printf("  %-40s → 状态 %d 正文 %-24q Content-Type=%q\\n", x.name, w.Code, w.Body.String(), w.Header().Get("Content-Type"))
	}
}''')
out_lines(r)
print('== 四:handler 数量的上限:abortIndex = 63,所以一条路由最多 62 个 handler?注册 62、63、64 个时分别会怎样')
r = gin('n18c', """package main
import ("fmt"; "github.com/gin-gonic/gin")
func main() {
	for _, n := range []int{61, 62, 63, 64} {
		func() {
			defer func() { if e := recover(); e != nil { fmt.Printf("  一条路由挂 %d 个 handler → panic: %v\\n", n, e) } }()
			r := gin.New(); hs := make([]gin.HandlerFunc, n)
			for i := range hs { hs[i] = func(c *gin.Context) {} }
			r.GET("/x", hs...)
			fmt.Printf("  一条路由挂 %d 个 handler → 注册成功\\n", n)
		}()
	}
}""")
out_lines(r)
