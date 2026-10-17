import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n3')
PRE = '''package main
import ("fmt"; "net/http/httptest"; "github.com/gin-gonic/gin")
func try(r *gin.Engine, method, url string) {
	w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest(method, url, nil))
	loc := ""; if l := w.Header().Get("Location"); l != "" { loc = " Location=" + l }
	fmt.Printf("  %-4s %-26s → %d %q%s\\n", method, url, w.Code, w.Body.String(), loc)
}
func try404(r *gin.Engine, method, url string) { try(r, method, url) }
'''
print('== 一::id 只匹配一段,*path 吞掉剩下的全部(两条独立的路由 /u/:id 和 /s/*p 各自的行为)')
r = gin('n3a', PRE + '''
func main() {
	r := gin.New()
	r.GET("/u/:id", func(c *gin.Context) { c.String(200, "id=%q", c.Param("id")) })
	r.GET("/s/*p", func(c *gin.Context) { c.String(200, "p=%q", c.Param("p")) })
	for _, u := range []string{"/u/1", "/u/1/2", "/u/", "/u", "/u/a%20b", "/u/中文"} { try(r, "GET", u) }
	for _, u := range []string{"/s/", "/s/a", "/s/a/b/c", "/s/a/b/", "/s", "/s//x"} { try(r, "GET", u) }
}''')
out_lines(r)
print('== 二:同一位置同时有 :id 和 *p,或者两个名字不同的参数,会怎样(注册时 panic 的原文)')
r = gin('n3b', '''package main
import ("fmt"; "github.com/gin-gonic/gin")
func reg(label string, paths ...string) {
	defer func() { if e := recover(); e != nil { fmt.Printf("  [%s] panic: %v\\n", label, e) } }()
	r := gin.New(); h := func(c *gin.Context) {}
	for _, p := range paths { r.GET(p, h) }
	fmt.Printf("  [%s] 注册成功: %v\\n", label, paths)
}
func main() {
	reg(":id 与 *p 同位置", "/x/:id", "/x/*p")
	reg("*p 与 :id 同位置(顺序反过来)", "/x/*p", "/x/:id")
	reg(":id 与 :name 同位置", "/x/:id", "/x/:name")
	reg(":id 与 :name 后面还有静态段", "/x/:id/a", "/x/:name/b")
	reg("同名 :id 后面不同的静态段", "/x/:id/a", "/x/:id/b")
	reg("*p 之后还有路径", "/x/*p/more")
	reg("*p 与静态 /x/ 同位置", "/x/*p", "/x/")
	reg("*p 与静态 /x/a 同位置", "/x/*p", "/x/a")
	reg("静态 /x/a 先注册、*p 后注册", "/x/a", "/x/*p")
	reg(":id 与静态 /x/new 共存", "/x/new", "/x/:id")
}''')
out_lines(r)
print('== 三:*p 的值从斜杠开始,常见写法 c.Param("p")[1:];*p 能匹配空吗?')
r = gin('n3c', PRE + '''
func main() {
	r := gin.New()
	r.GET("/files/*p", func(c *gin.Context) {
		p := c.Param("p")
		c.String(200, "p=%q 去掉开头斜杠=%q", p, p[1:])
	})
	for _, u := range []string{"/files/a/b.txt", "/files/", "/files", "/files/a//b", "/files/%2e%2e/x", "/files/../x"} { try(r, "GET", u) }
}''')
out_lines(r)
print('== 四:一个常见误会:/files/:name 能不能匹配带斜杠的名字(:name 只吃一段)')
r = gin('n3d', PRE + '''
func main() {
	r := gin.New()
	r.GET("/files/:name", func(c *gin.Context) { c.String(200, "name=%q", c.Param("name")) })
	for _, u := range []string{"/files/a.txt", "/files/dir/a.txt", "/files/dir%2Fa.txt"} { try(r, "GET", u) }
	r2 := gin.New(); r2.UseRawPath = true; r2.UnescapePathValues = true
	r2.GET("/files/:name", func(c *gin.Context) { c.String(200, "name=%q", c.Param("name")) })
	fmt.Println("  --- UseRawPath=true + UnescapePathValues=true 之后 ---")
	for _, u := range []string{"/files/a.txt", "/files/dir/a.txt", "/files/dir%2Fa.txt"} { try(r2, "GET", u) }
}''')
out_lines(r)
