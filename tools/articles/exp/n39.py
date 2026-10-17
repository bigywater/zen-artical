import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n39')
SITE = {
 'site/public/a.txt': 'file a\n',
 'site/public/index.html': '<h1>首页</h1>\n',
 'site/public/sub/b.txt': 'file b\n',
 'site/public/nested/deep/c.txt': 'file c\n',
 'site/public/.env': 'SECRET_KEY=dotfile-content\n',
 'site/public/noext': 'no extension\n',
 'site/public/page.html': '<p>x</p>\n',
 'site/secret.txt': 'OUTSIDE-THE-ROOT\n',
}
PRE = '''package main
import ("bufio"; "fmt"; "io"; "net"; "net/http"; "net/http/httptest"; "os"; "path/filepath"; "strings"; "github.com/gin-gonic/gin")
var _ = bufio.NewReader
var _ = io.EOF
var _ = filepath.Join
var _ = http.StatusOK
var _ = httptest.NewServer
var _ = os.Getpid
func raw(addr, reqLine string) string {
	conn, _ := net.Dial("tcp", addr); defer conn.Close()
	fmt.Fprintf(conn, "%s HTTP/1.1\\r\\nHost: a\\r\\nConnection: close\\r\\n\\r\\n", reqLine)
	br := bufio.NewReader(conn); st, _ := br.ReadString('\\n'); var loc string
	for { l, err := br.ReadString('\\n'); if err != nil || l == "\\r\\n" { break }; if strings.HasPrefix(l, "Location:") { loc = " " + strings.TrimSpace(l) } }
	b, _ := io.ReadAll(br); body := strings.TrimSpace(string(b)); if len(body) > 60 { body = body[:60] + "…" }
	return fmt.Sprintf("%s%s | %q", strings.TrimSpace(st), loc, body)
}
'''
def T(src): d = dict(SITE); d['main.go'] = PRE + src; return d
print('== 一:Static 与 StaticFS 的源码:Static 用 Dir(root, false),handler 先 Open 一下再交给 http.FileServer')
gfunc('routergroup.go', 'createStaticHandler')
gfunc('fs.go', 'Dir')
print('== 二:Static("/static", "site/public") 对各种请求的响应(原始 TCP 请求,避免客户端提前改写路径)')
r = gin('n39a', T('''
func main() {
	os.Symlink("../secret.txt", "site/public/link.txt")
	r := gin.New()
	r.Static("/static", "site/public")
	ts := httptest.NewServer(r); defer ts.Close(); addr := ts.Listener.Addr().String()
	for _, p := range []string{"/static/a.txt", "/static/sub/b.txt", "/static/nested/deep/c.txt", "/static/", "/static/index.html", "/static/sub/", "/static/sub", "/static/nested/", "/static/.env", "/static/noext", "/static/nope.txt", "/static/link.txt", "/static"} {
		fmt.Printf("  GET %-28s → %s\\n", p, raw(addr, "GET "+p))
	}
}'''))
out_lines(r)
print('== 三:路径穿越尝试:../、%2e%2e%2f、双重编码、反斜杠、NUL(原始请求行)')
r = gin('n39b', T('''
func main() {
	r := gin.New()
	r.Static("/static", "site/public")
	ts := httptest.NewServer(r); defer ts.Close(); addr := ts.Listener.Addr().String()
	for _, p := range []string{"/static/../secret.txt", "/static/..%2fsecret.txt", "/static/%2e%2e/secret.txt", "/static/%2e%2e%2fsecret.txt", "/static/..%252fsecret.txt", "/static/sub/../../secret.txt", `/static/..\\secret.txt`, "/static/%00", "/static//etc/passwd", "/static/sub/..%2f..%2fsecret.txt"} {
		fmt.Printf("  GET %-40s → %s\\n", p, raw(addr, "GET "+p))
	}
}'''))
out_lines(r)
print('== 四:目录列表:Static(不列)、StaticFS(http.Dir 列)、StaticFS(gin.Dir(.., true))')
r = gin('n39c', T('''
func main() {
	r := gin.New()
	r.Static("/nolist", "site/public")
	r.StaticFS("/list", http.Dir("site/public"))
	r.StaticFS("/list2", gin.Dir("site/public", true))
	ts := httptest.NewServer(r); defer ts.Close(); addr := ts.Listener.Addr().String()
	for _, p := range []string{"/nolist/sub/", "/list/sub/", "/list2/sub/", "/nolist/nested/", "/list/nested/"} {
		conn, _ := net.Dial("tcp", addr); fmt.Fprintf(conn, "GET %s HTTP/1.1\\r\\nHost: a\\r\\nConnection: close\\r\\n\\r\\n", p)
		b, _ := io.ReadAll(conn); conn.Close(); s := string(b); st := s[:strings.Index(s, "\\r\\n")]; body := s[strings.Index(s, "\\r\\n\\r\\n")+4:]
		fmt.Printf("  GET %-16s → %s | %q\\n", p, st, strings.TrimSpace(body))
	}
}'''))
out_lines(r)
print('== 五:缓存头:Last-Modified 与 If-Modified-Since → 304;没有 ETag;Content-Type 靠扩展名,没扩展名靠嗅探;HEAD')
r = gin('n39d', T('''
func main() {
	r := gin.New()
	r.Static("/static", "site/public")
	ts := httptest.NewServer(r); defer ts.Close()
	do := func(method, p string, hdr ...string) (*http.Response, string) {
		rq, _ := http.NewRequest(method, ts.URL+p, nil); for i := 0; i+1 < len(hdr); i += 2 { rq.Header.Set(hdr[i], hdr[i+1]) }
		resp, err := http.DefaultTransport.RoundTrip(rq); if err != nil { return nil, err.Error() }
		b, _ := io.ReadAll(resp.Body); resp.Body.Close(); return resp, string(b)
	}
	resp, _ := do("GET", "/static/a.txt")
	lm := resp.Header.Get("Last-Modified")
	fmt.Printf("  GET a.txt → %d Last-Modified=%q ETag=%q Content-Type=%q Content-Length=%s Accept-Ranges=%q Cache-Control=%q\\n", resp.StatusCode, lm, resp.Header.Get("ETag"), resp.Header.Get("Content-Type"), resp.Header.Get("Content-Length"), resp.Header.Get("Accept-Ranges"), resp.Header.Get("Cache-Control"))
	resp, b := do("GET", "/static/a.txt", "If-Modified-Since", lm); fmt.Printf("  带 If-Modified-Since=Last-Modified → %d 正文 %q\\n", resp.StatusCode, b)
	resp, b = do("GET", "/static/a.txt", "If-Modified-Since", "Mon, 01 Jan 2001 00:00:00 GMT"); fmt.Printf("  带更早的 If-Modified-Since → %d 正文 %q\\n", resp.StatusCode, b)
	resp, b = do("HEAD", "/static/a.txt"); fmt.Printf("  HEAD a.txt → %d 正文长度 %d Content-Length=%s\\n", resp.StatusCode, len(b), resp.Header.Get("Content-Length"))
	resp, _ = do("GET", "/static/noext"); fmt.Printf("  无扩展名 noext(内容是文本)→ Content-Type=%q(靠嗅探前 512 字节)\\n", resp.Header.Get("Content-Type"))
	resp, _ = do("GET", "/static/page.html"); fmt.Printf("  page.html → Content-Type=%q\\n", resp.Header.Get("Content-Type"))
	resp, _ = do("POST", "/static/a.txt"); fmt.Printf("  POST a.txt → %d(只注册了 GET 与 HEAD)\\n", resp.StatusCode)
}'''))
out_lines(r)
print('== 六:Static("/", ...) 与其它路由共存:catch-all 冲突的 panic 原文;StaticFile 不能带参数')
r = gin('n39e', T('''
func main() {
	try := func(label string, f func(r *gin.Engine)) {
		defer func() { if e := recover(); e != nil { fmt.Printf("  %-34s → panic: %v\\n", label, e) } }()
		r := gin.New(); f(r); fmt.Printf("  %-34s → 注册成功\\n", label)
	}
	h := func(c *gin.Context) {}
	try("先 GET /ping,再 Static(\\"/\\")", func(r *gin.Engine) { r.GET("/ping", h); r.Static("/", "site/public") })
	try("先 Static(\\"/\\"),再 GET /ping", func(r *gin.Engine) { r.Static("/", "site/public"); r.GET("/ping", h) })
	try("Static(\\"/assets\\") 与 GET /ping", func(r *gin.Engine) { r.GET("/ping", h); r.Static("/assets", "site/public") })
	try("Static(\\"/assets\\") 与 GET /assets/x", func(r *gin.Engine) { r.Static("/assets", "site/public"); r.GET("/assets/x", h) })
	try("StaticFile 路径里有参数", func(r *gin.Engine) { r.StaticFile("/f/:id", "site/public/a.txt") })
	try("Static 路径里有通配符", func(r *gin.Engine) { r.Static("/s/*x", "site/public") })
}'''))
out_lines(r)
