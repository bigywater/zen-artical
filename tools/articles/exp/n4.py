import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n4')
print('== 一:registered 时的各种冲突(每行是一组路由,按顺序注册到同一个 GET 树;输出是 recover 到的 panic 原文)')
r = gin('n4a', '''package main
import ("fmt"; "github.com/gin-gonic/gin")
func reg(label string, paths ...string) {
	defer func() { if e := recover(); e != nil { fmt.Printf("  ✗ %-30s %v\\n", label, e) } }()
	r := gin.New(); h := func(c *gin.Context) {}
	for _, p := range paths { r.GET(p, h) }
	var got []string; for _, ri := range r.Routes() { got = append(got, ri.Path) }
	fmt.Printf("  ✓ %-30s 注册 %v → 路由表 %v\\n", label, paths, got)
}
func main() {
	reg("静态与参数共存(静态先)", "/users/new", "/users/:id")
	reg("静态与参数共存(参数先)", "/users/:id", "/users/new")
	reg("参数后面接不同静态段", "/users/:id/a", "/users/:id/b")
	reg("同位置参数改名", "/users/:id", "/users/:uid")
	reg("根上的参数与静态", "/about", "/:lang")
	reg("根上的参数与静态(反序)", "/:lang", "/about")
	reg("根上的 :a 与 :b/x", "/:a", "/:b/x")
	reg("参数与更长的静态路径", "/a/:id", "/a/b/c")
	reg("通配符 :id 与 *p 同位置", "/a/:id", "/a/*p")
	reg("*p 与静态 /a/b 同位置", "/a/*p", "/a/b")
	reg("同一路由注册两次", "/ping", "/ping")
	reg("同一路由带不同参数名", "/u/:id", "/u/:id")
	reg("参数名为空 /u/:", "/u/:")
	reg("一段里两个通配符", "/u/:a:b")
	reg("*p 后面还有路径", "/s/*p/x")
	reg("没有斜杠的 *p", "/s*p")
	reg("路径不以 / 开头", "users")
	reg("转义冒号 /u/\\\\:id", "/u/\\\\:id")
}''')
out_lines(r)
print('== 二:panic 发生在注册的那一行,不是第一个请求到来的时候(栈顶的几帧)')
r = gin('n4b', '''package main
import ("fmt"; "runtime/debug"; "strings"; "github.com/gin-gonic/gin")
func main() {
	defer func() {
		e := recover()
		fmt.Println("  recover:", e)
		st := strings.Split(string(debug.Stack()), "\\n")
		n := 0
		for _, l := range st {
			if strings.Contains(l, "gin") && strings.Contains(l, "(") && !strings.HasPrefix(l, "\\t") && !strings.Contains(l, "debug.Stack") && n < 6 { fmt.Println("   ", strings.SplitN(l, "(0x", 2)[0]); n++ }
		}
	}()
	r := gin.New(); h := func(c *gin.Context) {}
	r.GET("/a/:id", h)
	fmt.Println("  第一条路由注册完成,下一行会 panic")
	r.GET("/a/*p", h)
	fmt.Println("  不会打印到这里")
}''')
out_lines(r)
print('== 三:静态与参数共存时,请求怎么选?(含回溯:先走静态分支,走不通再退回参数分支)')
r = gin('n4c', '''package main
import ("fmt"; "net/http/httptest"; "github.com/gin-gonic/gin")
func main() {
	r := gin.New()
	h := func(name string) gin.HandlerFunc { return func(c *gin.Context) { fmt.Printf("  %-22s → 命中 %-14s Params=%v\\n", c.Request.URL.Path, name, c.Params) } }
	r.GET("/files/a/b", h("/files/a/b"))
	r.GET("/files/:id/c", h("/files/:id/c"))
	r.GET("/files/new", h("/files/new"))
	r.GET("/files/:id", h("/files/:id"))
	for _, u := range []string{"/files/a/b", "/files/a/c", "/files/a", "/files/new", "/files/newer", "/files/x/c", "/files/new/c", "/files/a/d"} {
		w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest("GET", u, nil))
		if w.Code != 200 { fmt.Printf("  %-22s → %d\\n", u, w.Code) }
	}
}''')
out_lines(r)
print('== 四:冲突检查的源码:panic 信息拼在 addRoute / insertChild 里')
gfind('tree.go', r'conflicts with existing', ctx=0, maxn=6)
gfind('tree.go', r'handlers are already registered|only one wildcard per path|catch-all routes are only allowed|wildcards must be named|no / before catch-all', ctx=0, maxn=8)
gfind('gin.go', r"path must begin with '/'|there must be at least one handler|HTTP method can not be empty", ctx=0, maxn=4)
