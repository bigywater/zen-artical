import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n9')
PRE = '''package main
import ("fmt"; "net/http/httptest"; "strings"; "github.com/gin-gonic/gin")
func try(r *gin.Engine, method, url string) {
	w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest(method, url, strings.NewReader("")))
	ct := w.Header().Get("Content-Type"); x := w.Header().Get("X-Seen")
	fmt.Printf("  %-6s %-10s → %d %q  Content-Type=%q X-Seen=%q\\n", method, url, w.Code, w.Body.String(), ct, x)
}
'''
print('== 一:没有 NoRoute 时的默认 404(serveError 的源码和默认响应)')
gfunc('gin.go', 'serveError')
r = gin('n9a', PRE + '''
func main() { r := gin.New(); r.GET("/ok", func(c *gin.Context) { c.String(200, "ok") }); try(r, "GET", "/nope") }''')
out_lines(r)
print('== 二:NoRoute handler 怎么写,默认 404 的正文什么时候还在')
r = gin('n9b', PRE + '''
func main() {
	cases := map[string]gin.HandlerFunc{
		"1 只设置头,不写正文": func(c *gin.Context) { c.Header("X-Seen", "1") },
		"2 c.String(404, 自定义)": func(c *gin.Context) { c.String(404, "自定义:%s 不存在", c.Request.URL.Path) },
		"3 c.String(200, ...)": func(c *gin.Context) { c.String(200, "这里也有") },
		"4 只 c.Status(200)": func(c *gin.Context) { c.Status(200) },
		"5 c.JSON(404, ...)": func(c *gin.Context) { c.JSON(404, gin.H{"error": "not found", "status": c.Writer.Status(), "fullPath": c.FullPath()}) },
		"6 c.Redirect(302, /home)": func(c *gin.Context) { c.Redirect(302, "/home") },
	}
	for _, k := range []string{"1 只设置头,不写正文", "2 c.String(404, 自定义)", "3 c.String(200, ...)", "4 只 c.Status(200)", "5 c.JSON(404, ...)", "6 c.Redirect(302, /home)"} {
		r := gin.New(); r.NoRoute(cases[k]); fmt.Printf("  [%s]\\n", k); try(r, "GET", "/nope")
	}
}''')
out_lines(r)
print('== 三:NoRoute 的 handler 链 = 全局中间件 + NoRoute 的 handler;注册先后不影响;404 时 c.FullPath() 是空串,Params 为空')
r = gin('n9c', '''package main
import ("fmt"; "net/http/httptest"; "github.com/gin-gonic/gin")
func mw(name string) gin.HandlerFunc { return func(c *gin.Context) { fmt.Printf(" %s(进)", name); c.Next(); fmt.Printf(" %s(出,状态 %d)", name, c.Writer.Status()) } }
func main() {
	a := gin.New()
	a.NoRoute(func(c *gin.Context) { fmt.Printf(" [NoRoute: FullPath=%q Params=%v 状态=%d]", c.FullPath(), c.Params, c.Writer.Status()) })
	a.Use(mw("M1"))
	a.Use(mw("M2"))
	fmt.Print("  先 NoRoute 后 Use:"); a.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", "/nope", nil)); fmt.Println()
	b := gin.New()
	b.Use(mw("M1"))
	b.NoRoute(func(c *gin.Context) { fmt.Print(" [NoRoute]") }, func(c *gin.Context) { fmt.Print(" [NoRoute2]") })
	b.Use(mw("M2"))
	fmt.Print("  Use、NoRoute、Use 交错:"); b.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", "/nope", nil)); fmt.Println()
	c := gin.New()
	c.Use(mw("M1"))
	c.NoRoute(func(c *gin.Context) { fmt.Print(" [NoRoute-abort]"); c.AbortWithStatusJSON(404, gin.H{"e": 1}) }, func(c *gin.Context) { fmt.Print(" [不会执行]") })
	fmt.Print("  NoRoute 里 Abort:"); c.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", "/nope", nil)); fmt.Println()
}''')
out_lines(r)
print('== 四:NoMethod 同理,但要先打开 HandleMethodNotAllowed;以及静态文件 404 也走 NoRoute')
r = gin('n9d', PRE + '''
func main() {
	r := gin.New()
	r.NoRoute(func(c *gin.Context) { c.Header("X-Seen", "noroute"); c.String(404, "NR") })
	r.NoMethod(func(c *gin.Context) { c.Header("X-Seen", "nomethod"); c.String(405, "NM Allow=%s", c.Writer.Header().Get("Allow")) })
	r.GET("/x", func(c *gin.Context) {}); r.Static("/assets", ".")
	try(r, "POST", "/x"); fmt.Println("  --- HandleMethodNotAllowed = true ---")
	r.HandleMethodNotAllowed = true
	try(r, "POST", "/x"); try(r, "GET", "/assets/不存在.css"); try(r, "GET", "/zzz")
}''')
out_lines(r)
