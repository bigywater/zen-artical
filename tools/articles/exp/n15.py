import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n15')
PRE = '''package main
import ("fmt"; "net/http/httptest"; "strings"; "github.com/gin-gonic/gin")
var _ = strings.TrimSpace
'''
print('== 一:RemoveExtraSlash 打开前后,带多余斜杠的请求(路由 /users/:id 与 /a/b、/f/*p)')
r = gin('n15a', PRE + '''
func main() {
	urls := []string{"/users/42", "/users//42", "//users/42", "/users/42//", "/a//b", "/a/./b", "/a/x/../b", "/f/x//y", "/users/42/"}
	for _, on := range []bool{false, true} {
		r := gin.New(); r.RemoveExtraSlash = on
		r.GET("/users/:id", func(c *gin.Context) { c.String(200, "id=%s", c.Param("id")) })
		r.GET("/a/b", func(c *gin.Context) { c.String(200, "a/b") })
		r.GET("/f/*p", func(c *gin.Context) { c.String(200, "p=%q", c.Param("p")) })
		fmt.Printf("  === RemoveExtraSlash = %v ===\\n", on)
		for _, u := range urls {
			w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest("GET", u, nil))
			loc := ""; if l := w.Header().Get("Location"); l != "" { loc = " Location=" + l }
			fmt.Printf("    %-14s → %d %-16q%s\\n", u, w.Code, strings.TrimSpace(w.Body.String()), loc)
		}
	}
}''')
out_lines(r)
print('== 二:匹配用的是清理后的路径,c.Request.URL.Path 仍是原样;通配符的值被清理(数据被改了)')
r = gin('n15b', PRE + '''
func main() {
	r := gin.New(); r.RemoveExtraSlash = true
	r.GET("/f/*p", func(c *gin.Context) { c.String(200, "p=%q  URL.Path=%q  FullPath=%q", c.Param("p"), c.Request.URL.Path, c.FullPath()) })
	for _, u := range []string{"/f/a//b", "/f//a/b", "/f/a/../b", "/f/a/./b/"} {
		w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest("GET", u, nil)); fmt.Printf("  %-14s → %d %s\\n", u, w.Code, w.Body.String())
	}
}''')
out_lines(r)
print('== 三:与 RedirectFixedPath / RedirectTrailingSlash 的组合:谁让请求直接命中,谁让客户端重定向')
r = gin('n15c', PRE + '''
func main() {
	for _, c := range [][2]bool{{false, false}, {true, false}, {false, true}, {true, true}} {
		r := gin.New(); r.RemoveExtraSlash, r.RedirectFixedPath = c[0], c[1]
		r.GET("/users/:id", func(c *gin.Context) { c.String(200, "id=%s", c.Param("id")) })
		r.GET("/dir/", func(c *gin.Context) { c.String(200, "dir") })
		fmt.Printf("  RemoveExtraSlash=%-5v RedirectFixedPath=%-5v:", c[0], c[1])
		for _, u := range []string{"/users//42", "/dir", "//dir/", "/dir//"} {
			w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest("GET", u, nil))
			loc := ""; if l := w.Header().Get("Location"); l != "" { loc = "→" + l }
			fmt.Printf("  %s %d%s", u, w.Code, loc)
		}
		fmt.Println()
	}
}''')
out_lines(r)
print('== 四:cleanPath 的源码规则与每次请求的内存分配(AllocsPerRun)')
gsrcl('path.go', 10, 22, title='path.go 的 cleanPath 注释')
r = gin('n15d', """package main
import ("fmt"; "net/http"; "net/http/httptest"; "testing"; "github.com/gin-gonic/gin")
type nw struct{ h http.Header }
func (w *nw) Header() http.Header { if w.h == nil { w.h = http.Header{} }; return w.h }
func (w *nw) Write(b []byte) (int, error) { return len(b), nil }
func (w *nw) WriteHeader(int) {}
func main() {
	for _, on := range []bool{false, true} {
		r := gin.New(); r.RemoveExtraSlash = on; r.GET("/users/:id", func(c *gin.Context) {})
		for _, u := range []string{"/users/42", "/users//42"} {
			req := httptest.NewRequest("GET", u, nil); var w nw; r.ServeHTTP(&w, req)
			fmt.Printf("  RemoveExtraSlash=%-5v %-12s %.0f allocs/请求\\n", on, u, testing.AllocsPerRun(2000, func() { r.ServeHTTP(&w, req) }))
		}
	}
}""")
out_lines(r)
