import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n6')
PRE = '''package main
import ("fmt"; "net/http/httptest"; "strings"; "github.com/gin-gonic/gin")
func try(r *gin.Engine, method, url string, hdr ...string) {
	req := httptest.NewRequest(method, url, strings.NewReader("")); for i := 0; i+1 < len(hdr); i += 2 { req.Header.Set(hdr[i], hdr[i+1]) }
	w := httptest.NewRecorder(); r.ServeHTTP(w, req)
	loc := ""; if l := w.Header().Get("Location"); l != "" { loc = "  Location: " + l }
	hd := ""; if len(hdr) > 1 { hd = fmt.Sprintf(" [%s: %q]", hdr[0], hdr[1]) }
	fmt.Printf("  %-6s %-22s%s → %d%s\\n", method, url, hd, w.Code, loc)
}
'''
print('== 一:默认的 RedirectTrailingSlash=true:路由带斜杠、请求不带,或者反过来')
r = gin('n6a', PRE + '''
func main() {
	r := gin.New()
	fmt.Println("  默认值 RedirectTrailingSlash =", r.RedirectTrailingSlash, ",RedirectFixedPath =", r.RedirectFixedPath, ",HandleMethodNotAllowed =", r.HandleMethodNotAllowed)
	h := func(c *gin.Context) { c.String(200, "ok") }
	r.GET("/dir/", h)
	r.GET("/file", h)
	r.GET("/users/:id/", h)
	r.GET("/", h)
	for _, u := range []string{"/dir", "/dir/", "/file", "/file/", "/users/7", "/users/7/", "/dir?x=1&y=2", "/file/?x=1"} { try(r, "GET", u) }
}''')
out_lines(r)
print('== 二:状态码:GET 是 301,其他方法是 307(源码 redirectRequest)')
gfunc('gin.go', 'redirectRequest')
r = gin('n6b', PRE + '''
func main() {
	r := gin.New(); h := func(c *gin.Context) { c.String(200, "ok") }
	for _, m := range []string{"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"} { r.Handle(m, "/x/", h) }
	for _, m := range []string{"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "CONNECT"} { try(r, m, "/x") }
}''')
out_lines(r)
print('== 三:关闭 RedirectTrailingSlash 之后,以及 X-Forwarded-Prefix 对 Location 的影响')
r = gin('n6c', PRE + '''
func main() {
	h := func(c *gin.Context) { c.String(200, "ok") }
	r := gin.New(); r.GET("/dir/", h)
	try(r, "GET", "/dir")
	r.RedirectTrailingSlash = false
	fmt.Println("  --- RedirectTrailingSlash = false ---")
	try(r, "GET", "/dir")
	r.RedirectTrailingSlash = true
	fmt.Println("  --- 带 X-Forwarded-Prefix 头(反向代理挂在子路径下)---")
	try(r, "GET", "/dir", "X-Forwarded-Prefix", "/app")
	try(r, "GET", "/dir", "X-Forwarded-Prefix", "/app/")
	try(r, "GET", "/dir", "X-Forwarded-Prefix", "//evil.com")
	try(r, "GET", "/dir", "X-Forwarded-Prefix", "/a b;c")
}''')
out_lines(r)
print('== 四:真实的 HTTP 客户端遇到这个重定向(服务只注册了 POST /upload/,客户端 POST /upload 带 body)')
r = gin('n6d', '''package main
import ("fmt"; "io"; "net/http"; "net/http/httptest"; "strings"; "github.com/gin-gonic/gin")
func main() {
	r := gin.New(); var seen []string
	r.POST("/upload/", func(c *gin.Context) { b, _ := io.ReadAll(c.Request.Body); seen = append(seen, fmt.Sprintf("%s %s body=%q", c.Request.Method, c.Request.URL.Path, b)); c.String(200, "stored") })
	ts := httptest.NewServer(r); defer ts.Close()
	cl := &http.Client{CheckRedirect: func(req *http.Request, via []*http.Request) error { fmt.Printf("  客户端被重定向到 %s,方法 %s\\n", req.URL.Path, req.Method); return nil }}
	resp, err := cl.Post(ts.URL+"/upload", "text/plain", strings.NewReader("hello"))
	if err != nil { fmt.Println("  错误:", err); return }
	b, _ := io.ReadAll(resp.Body)
	fmt.Printf("  最终响应:%d %q\\n  服务端的 handler 看到:%v\\n", resp.StatusCode, b, seen)
	r2 := gin.New(); seen = nil
	r2.GET("/old/", func(c *gin.Context) { c.String(200, "get ok") })
	ts2 := httptest.NewServer(r2); defer ts2.Close()
	cl2 := &http.Client{CheckRedirect: func(req *http.Request, via []*http.Request) error { return http.ErrUseLastResponse }}
	resp, _ = cl2.Get(ts2.URL + "/old")
	fmt.Printf("  不跟随重定向时:%d,Location=%s\\n", resp.StatusCode, resp.Header.Get("Location"))
}''')
out_lines(r)
