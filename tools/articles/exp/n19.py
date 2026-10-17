import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n19')
PRE = '''package main
import ("fmt"; "net/http/httptest"; "strings"; "github.com/gin-gonic/gin")
var tr []string
func T(s string) { tr = append(tr, s) }
func show(name string) { fmt.Printf("  %-34s %s\\n", name, strings.Join(tr, " → ")); tr = nil }
func do(r *gin.Engine) { w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest("GET", "/x", nil)); if w.Code != 200 { T(fmt.Sprint("[状态", w.Code, "]")) } }
func mw(n string, next bool) gin.HandlerFunc { return func(c *gin.Context) { T(n + "前"); if next { c.Next() }; T(n + "后") } }
'''
print('== 一:洋葱模型:A、B、C 三个中间件 + handler,每个都调用 c.Next()')
r = gin('n19a', PRE + '''
func main() {
	r := gin.New(); r.Use(mw("A", true), mw("B", true), mw("C", true))
	r.GET("/x", func(c *gin.Context) { T("handler") })
	do(r); show("都调用 Next")
}''')
out_lines(r)
print('== 二:中间件“不调用 Next”并不会让链停下——引擎外层的循环会继续跑后面的 handler,只是“后”半段提前了')
r = gin('n19b', PRE + '''
func main() {
	r := gin.New(); r.Use(mw("A", true), mw("B", false), mw("C", true))
	r.GET("/x", func(c *gin.Context) { T("handler") })
	do(r); show("B 不调用 Next")
	r2 := gin.New(); r2.Use(mw("A", true), func(c *gin.Context) { T("B前"); c.Next(); c.Next(); T("B后") }, mw("C", true))
	r2.GET("/x", func(c *gin.Context) { T("handler") })
	do(r2); show("B 调用两次 Next")
	r3 := gin.New(); r3.Use(mw("A", true), func(c *gin.Context) { T("B前"); c.Abort(); T("B后") }, mw("C", true))
	r3.GET("/x", func(c *gin.Context) { T("handler") })
	do(r3); show("B 调用 Abort(不调 Next)")
}''')
out_lines(r)
print('== 三:“后”半段能看到什么:状态、写出的字节数、Errors;handler 写响应之后再改状态和头,真实客户端收到什么')
r = gin('n19c', """package main
import ("fmt"; "io"; "net/http"; "net/http/httptest"; "github.com/gin-gonic/gin")
func main() {
	r := gin.New()
	r.Use(func(c *gin.Context) {
		c.Next()
		fmt.Printf("  中间件后半段:状态=%d 已写字节=%d 已写出=%v Errors=%d\\n", c.Writer.Status(), c.Writer.Size(), c.Writer.Written(), len(c.Errors))
		c.Header("X-Late", "1"); c.Status(500)
	})
	r.GET("/x", func(c *gin.Context) { c.Error(fmt.Errorf("e1")); c.String(201, "hello") })
	r.GET("/y", func(c *gin.Context) { c.Header("X-Early", "1"); c.Status(202) })
	ts := httptest.NewServer(r); defer ts.Close()
	for _, p := range []string{"/x", "/y"} {
		resp, _ := http.Get(ts.URL + p); b, _ := io.ReadAll(resp.Body); resp.Body.Close()
		fmt.Printf("  %s 客户端收到:状态=%d 正文=%q X-Late=%q X-Early=%q\\n", p, resp.StatusCode, b, resp.Header.Get("X-Late"), resp.Header.Get("X-Early"))
	}
}""")
out_lines(r)
print('== 四:panic 时的展开:Recovery 在最外层 vs 在中间')
r = gin('n19d', PRE + '''
func main() {
	r := gin.New(); r.Use(gin.CustomRecoveryWithWriter(nil, func(c *gin.Context, e any) { T("[Recovery 处理 panic]"); c.AbortWithStatus(500) }), mw("A", true), mw("B", true))
	r.GET("/x", func(c *gin.Context) { T("handler"); panic("boom") })
	do(r); show("Recovery 在最外层")
	r2 := gin.New(); r2.Use(mw("A", true), gin.CustomRecoveryWithWriter(nil, func(c *gin.Context, e any) { T("[Recovery 处理 panic]"); c.AbortWithStatus(500) }), mw("B", true))
	r2.GET("/x", func(c *gin.Context) { T("handler"); panic("boom") })
	do(r2); show("Recovery 在 A 与 B 之间")
	r3 := gin.New(); r3.Use(gin.CustomRecoveryWithWriter(nil, func(c *gin.Context, e any) { T("[Recovery 处理 panic]"); c.AbortWithStatus(500) }), mw("A", true), func(c *gin.Context) { defer T("B的defer"); c.Next(); T("B后") })
	r3.GET("/x", func(c *gin.Context) { T("handler"); panic("boom") })
	do(r3); show("B 用 defer 写收尾")
}''')
out_lines(r)
