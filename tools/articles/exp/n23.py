import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n23')
PRE = '''package main
import ("errors"; "fmt"; "io"; "net/http/httptest"; "strings"; "github.com/gin-gonic/gin")
var _ = errors.New
var _ = io.EOF
var _ = strings.TrimSpace
func call(r *gin.Engine, method, url, body string) *httptest.ResponseRecorder { w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest(method, url, strings.NewReader(body))); return w }
'''
print('== 一:错误类型常量与 Context.Error 的源码')
gsrcl('errors.go', 15, 29)
gfunc('context.go', 'Error')
print('== 二:c.Error 收集什么:普通 error、*gin.Error(经过 %w 包装也一样)、nil;Errors 的几个方法')
r = gin('n23a', PRE + '''
func main() {
	r := gin.New()
	r.GET("/x", func(c *gin.Context) {
		e1 := c.Error(errors.New("数据库超时"))
		fmt.Printf("  c.Error(普通 error) → Type=%d(Private=1) Meta=%v,同一个指针存进 Errors: %v\\n", e1.Type, e1.Meta, c.Errors[0] == e1)
		pub := c.Error(errors.New("用户名已存在")).SetType(gin.ErrorTypePublic).SetMeta(gin.H{"code": 1001})
		wrapped := fmt.Errorf("外层: %w", pub)
		e3 := c.Error(wrapped)
		fmt.Printf("  c.Error(fmt.Errorf(\\"%%w\\", *gin.Error)) → 返回的指针就是原来的 *gin.Error: %v;Type=%d(Public=2)\\n", e3 == pub, e3.Type)
		fmt.Printf("  len(c.Errors)=%d(同一个 *Error 被存了 2 次)\\n", len(c.Errors))
		fmt.Printf("  Last().Error()=%q\\n", c.Errors.Last().Error())
		fmt.Printf("  ByType(Public) 有 %d 条,ByType(Private) 有 %d 条,ByType(Any) 有 %d 条\\n", len(c.Errors.ByType(gin.ErrorTypePublic)), len(c.Errors.ByType(gin.ErrorTypePrivate)), len(c.Errors.ByType(gin.ErrorTypeAny)))
		fmt.Printf("  Errors() = %q\\n", c.Errors.Errors())
		fmt.Printf("  String():\\n%s", indent(c.Errors.String()))
		b, _ := c.Errors.MarshalJSON(); fmt.Printf("  MarshalJSON() = %s\\n", b)
		b, _ = c.Errors.ByType(gin.ErrorTypePrivate).MarshalJSON(); fmt.Printf("  只有一个 Private 时 JSON() 是对象 %s\\n", b)
		func() { defer func() { fmt.Printf("  c.Error(nil) → panic: %v\\n", recover()) }(); c.Error(nil) }()
	})
	call(r, "GET", "/x", "")
}
func indent(s string) string { return "    " + strings.ReplaceAll(strings.TrimRight(s, "\\n"), "\\n", "\\n    ") + "\\n" }''')
out_lines(r)
print('== 三:框架自己往 c.Errors 里放什么:c.Bind(失败)是 ErrorTypeBind + 400 终止;ShouldBind 不放;渲染失败是 ErrorTypePrivate 并 Abort')
r = gin('n23b', PRE + '''
type P struct{ Age int `json:"age" binding:"required"` }
func main() {
	r := gin.New()
	rep := func(c *gin.Context, what string) {
		var ts []string
		for _, e := range c.Errors { ts = append(ts, fmt.Sprintf("Type=%d", e.Type)) }
		fmt.Printf("  %-34s Errors=%d %v IsAborted=%v 状态=%d 已写出=%v\\n", what, len(c.Errors), ts, c.IsAborted(), c.Writer.Status(), c.Writer.Written())
	}
	r.Use(func(c *gin.Context) { c.Next(); rep(c, c.Request.Header.Get("X-Case")) })
	r.POST("/bind", func(c *gin.Context) { var p P; c.Bind(&p) })
	r.POST("/should", func(c *gin.Context) { var p P; c.ShouldBind(&p) })
	r.GET("/render", func(c *gin.Context) { c.JSON(200, gin.H{"ch": make(chan int)}) })
	for _, k := range []struct{ name, method, url string }{{"c.Bind 失败", "POST", "/bind"}, {"c.ShouldBind 失败", "POST", "/should"}, {"c.JSON 序列化失败(channel)", "GET", "/render"}} {
		req := httptest.NewRequest(k.method, k.url, strings.NewReader(`{"age":0}`)); req.Header.Set("Content-Type", "application/json"); req.Header.Set("X-Case", k.name)
		func() { defer func() { recover() }(); r.ServeHTTP(httptest.NewRecorder(), req) }()
	}
	fmt.Printf("  ErrorTypeBind=1<<63=%d ErrorTypeRender=1<<62=%d(c.Render 失败走的是 c.Error(err),类型是 Private;Render 常量没有被 Gin 自己用到)\\n", uint64(gin.ErrorTypeBind), uint64(gin.ErrorTypeRender))
}''')
out_lines(r)
print('== 四:统一的错误处理中间件:handler 只 c.Error,中间件在 Next 之后统一写响应(只对公开错误展示给客户端)')
r = gin('n23c', PRE + '''
func ErrHandler() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Next()
		if len(c.Errors) == 0 || c.Writer.Written() { return }
		if pub := c.Errors.ByType(gin.ErrorTypePublic); len(pub) > 0 { c.JSON(400, gin.H{"errors": pub}); return }
		c.JSON(500, gin.H{"error": "服务器内部错误"})
	}
}
func main() {
	r := gin.New(); r.Use(ErrHandler())
	r.GET("/pub", func(c *gin.Context) { c.Error(errors.New("password too short")).SetType(gin.ErrorTypePublic).SetMeta(gin.H{"field": "password"}); c.Error(errors.New("内部:redis 连接池耗尽")) })
	r.GET("/priv", func(c *gin.Context) { c.Error(errors.New("内部:连接数据库失败 dsn=postgres://u:***@db")) })
	r.GET("/ok", func(c *gin.Context) { c.String(200, "fine") })
	r.GET("/early", func(c *gin.Context) { c.String(200, "已经写了"); c.Error(errors.New("写完之后才出错")) })
	for _, u := range []string{"/pub", "/priv", "/ok", "/early"} { w := call(r, "GET", u, ""); fmt.Printf("  GET %-7s → %d %s\\n", u, w.Code, strings.TrimSpace(w.Body.String())) }
}''')
out_lines(r)
print('== 五:Logger 中间件会把 Private 错误打印进访问日志(用一个 buffer 接收日志)')
r = gin('n23d', """package main
import ("bytes"; "errors"; "fmt"; "net/http/httptest"; "strings"; "github.com/gin-gonic/gin")
func main() {
	var buf bytes.Buffer
	r := gin.New(); r.Use(gin.LoggerWithWriter(&buf))
	r.GET("/x", func(c *gin.Context) { c.Error(errors.New("私有错误 A")); c.Error(errors.New("公开错误 B")).SetType(gin.ErrorTypePublic); c.Error(errors.New("私有错误 C")); c.String(200, "ok") })
	r.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", "/x", nil))
	for _, l := range strings.Split(strings.TrimRight(buf.String(), "\\n"), "\\n") { fmt.Printf("  %q\\n", l) }
}""")
out_lines(r)
