import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n8')
PRE = '''package main
import ("fmt"; "net/http/httptest"; "strings"; "github.com/gin-gonic/gin")
func try(r *gin.Engine, method, url string) {
	w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest(method, url, strings.NewReader("")))
	al := ""; if a := w.Header().Get("Allow"); a != "" { al = "  Allow: " + a }
	fmt.Printf("  %-7s %-14s → %d %q%s\\n", method, url, w.Code, strings.TrimSpace(w.Body.String()), al)
}
'''
print('== 一:默认 HandleMethodNotAllowed=false:方法不对只是 404;打开后才是 405 + Allow')
r = gin('n8a', PRE + '''
func main() {
	h := func(c *gin.Context) { c.String(200, "ok") }
	for _, on := range []bool{false, true} {
		r := gin.New(); r.HandleMethodNotAllowed = on
		r.GET("/x", h); r.POST("/x", h); r.PUT("/y/:id", h)
		fmt.Printf("  === HandleMethodNotAllowed = %v ===\\n", on)
		for _, c := range [][2]string{{"GET", "/x"}, {"DELETE", "/x"}, {"PATCH", "/y/5"}, {"GET", "/y/5"}, {"HEAD", "/x"}, {"OPTIONS", "/x"}, {"DELETE", "/nothing"}} { try(r, c[0], c[1]) }
	}
}''')
out_lines(r)
print('== 二:405 的判定(源码):遍历其它方法的树,只要有一棵能匹配这个路径就是 405')
gsrcl('gin.go', 738, 757, title='gin.go 的 handleHTTPRequest 里 405 的部分')
print('== 三:Allow 里的顺序 = 各方法的树被创建(第一次注册)的顺序')
r = gin('n8b', PRE + '''
func main() {
	h := func(c *gin.Context) { c.String(200, "ok") }
	for _, order := range [][]string{{"GET", "POST", "PUT"}, {"PUT", "POST", "GET"}, {"DELETE", "PATCH", "GET", "POST"}} {
		r := gin.New(); r.HandleMethodNotAllowed = true
		for _, m := range order { r.Handle(m, "/res", h) }
		fmt.Printf("  注册顺序 %v:\\n", order); try(r, "OPTIONS", "/res")
		fmt.Printf("    r.TreeMethods() = %v\\n", r.TreeMethods())
	}
}''', patched=True)
out_lines(r)
print('== 四:NoMethod 处理器与 405 页面;以及“只有尾斜杠不同”时是 404 还是 405')
r = gin('n8c', PRE + '''
func main() {
	h := func(c *gin.Context) { c.String(200, "ok") }
	r := gin.New(); r.HandleMethodNotAllowed = true
	r.GET("/x", h); r.POST("/dir/", h)
	r.NoMethod(func(c *gin.Context) { c.JSON(405, gin.H{"error": "method not allowed", "allow": c.Writer.Header().Get("Allow")}) })
	try(r, "DELETE", "/x"); try(r, "DELETE", "/dir/"); try(r, "DELETE", "/dir"); try(r, "GET", "/dir"); try(r, "GET", "/dir/")
}''')
out_lines(r)
