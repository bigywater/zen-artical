import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n40')
SITE = {
 'site/public/a.txt': '0123456789' * 10,
 'site/secret.txt': 'OUTSIDE-THE-ROOT\n',
}
PRE = '''package main
import ("fmt"; "io"; "net/http"; "net/http/httptest"; "net/url"; "os"; "path/filepath"; "runtime"; "strings"; "github.com/gin-gonic/gin")
var _ = os.Getpid
var _ = strings.TrimSpace
var _ = filepath.Join
var _ = url.QueryEscape
var _ = runtime.GC
var _ = io.EOF
var _ = http.StatusOK
func T(r *gin.Engine) *httptest.Server { return httptest.NewServer(r) }
func do(ts *httptest.Server, method, p string, hdr ...string) (*http.Response, string) {
	rq, _ := http.NewRequest(method, ts.URL+p, nil); for i := 0; i+1 < len(hdr); i += 2 { rq.Header.Set(hdr[i], hdr[i+1]) }
	resp, err := http.DefaultTransport.RoundTrip(rq); if err != nil { return nil, err.Error() }
	b, _ := io.ReadAll(resp.Body); resp.Body.Close(); return resp, string(b)
}
'''
def TT(src): d = dict(SITE); d['main.go'] = PRE + src; return d
print('== 一:c.File 与 FileAttachment 的源码:c.File 就是 http.ServeFile')
gfunc('context.go', 'File'); gfunc('context.go', 'FileAttachment')
print('== 二:Range 请求(文件 100 字节 = 0123456789 重复 10 次):各种写法的状态码、Content-Range、正文')
r = gin('n40a', TT('''
func main() {
	r := gin.New()
	r.GET("/f", func(c *gin.Context) { c.File("site/public/a.txt") })
	r.HEAD("/f", func(c *gin.Context) { c.File("site/public/a.txt") })
	r.GET("/data", func(c *gin.Context) { b, _ := os.ReadFile("site/public/a.txt"); c.Data(200, "text/plain", b) })
	ts := T(r); defer ts.Close()
	resp, b := do(ts, "GET", "/f"); fmt.Printf("  无 Range → %d 长度 %d Accept-Ranges=%q Content-Length=%s Last-Modified 有=%v\\n", resp.StatusCode, len(b), resp.Header.Get("Accept-Ranges"), resp.Header.Get("Content-Length"), resp.Header.Get("Last-Modified") != "")
	for _, rg := range []string{"bytes=0-9", "bytes=95-", "bytes=-5", "bytes=0-0", "bytes=50-1000", "bytes=0-4,10-14", "bytes=200-300", "bytes=5-2", "bytes=abc", "items=0-4", "bytes=0-9, 10-19, 20-29"} {
		resp, b := do(ts, "GET", "/f", "Range", rg)
		fmt.Printf("  Range: %-24q → %d Content-Range=%-18q Content-Type=%-52q 正文长度 %-3d %q\\n", rg, resp.StatusCode, resp.Header.Get("Content-Range"), resp.Header.Get("Content-Type"), len(b), func() string { if len(b) > 24 { return b[:24] + "…" }; return b }())
	}
	resp, b = do(ts, "GET", "/data", "Range", "bytes=0-9"); fmt.Printf("  对照 c.Data + Range: bytes=0-9 → %d Accept-Ranges=%q 正文长度 %d(整个文件)\\n", resp.StatusCode, resp.Header.Get("Accept-Ranges"), len(b))
	resp, _ = do(ts, "HEAD", "/f", "Range", "bytes=0-9"); fmt.Printf("  HEAD + Range → %d Content-Range=%q Content-Length=%s\\n", resp.StatusCode, resp.Header.Get("Content-Range"), resp.Header.Get("Content-Length"))
}'''))
out_lines(r, n=40)
print('== 三:If-Range:用 Last-Modified 做条件,匹配就返回部分内容,不匹配就返回整个文件(断点续传时文件变了)')
r = gin('n40b', TT('''
func main() {
	r := gin.New()
	r.GET("/f", func(c *gin.Context) { c.File("site/public/a.txt") })
	ts := T(r); defer ts.Close()
	resp, _ := do(ts, "GET", "/f"); lm := resp.Header.Get("Last-Modified")
	resp, b := do(ts, "GET", "/f", "Range", "bytes=0-9", "If-Range", lm); fmt.Printf("  If-Range=Last-Modified(匹配)→ %d 长度 %d\\n", resp.StatusCode, len(b))
	resp, b = do(ts, "GET", "/f", "Range", "bytes=0-9", "If-Range", "Mon, 01 Jan 2001 00:00:00 GMT"); fmt.Printf("  If-Range=更早的日期(文件“变了”)→ %d 长度 %d(返回整个文件)\\n", resp.StatusCode, len(b))
	resp, b = do(ts, "GET", "/f", "Range", "bytes=0-9", "If-Range", `"some-etag"`); fmt.Printf("  If-Range=一个 ETag(服务端没有 ETag)→ %d 长度 %d\\n", resp.StatusCode, len(b))
}'''))
out_lines(r)
print('== 四:FileAttachment 的 Content-Disposition:ASCII 名、含引号、含中文(filename*=UTF-8\'\'…,空格被编码成 +)')
r = gin('n40c', TT('''
func main() {
	r := gin.New()
	r.GET("/dl", func(c *gin.Context) { c.FileAttachment("site/public/a.txt", c.Query("n")) })
	ts := T(r); defer ts.Close()
	for _, n := range []string{"report.txt", "my report.txt", `a"b.txt`, `a\\b.txt`, "报告.txt", "中 文.txt", "résumé.txt"} {
		resp, _ := do(ts, "GET", "/dl?n="+url.QueryEscape(n)); fmt.Printf("  filename=%-14q → Content-Disposition: %s\\n", n, resp.Header.Get("Content-Disposition"))
	}
}'''))
out_lines(r)
print('== 五:c.File(用户给的路径):ServeFile 只拒绝“URL 路径”里的 ..,不检查你传给它的文件路径——查询参数里的 ../ 能读到根目录之外的文件')
r = gin('n40d', TT('''
func main() {
	r := gin.New()
	r.GET("/q", func(c *gin.Context) { c.File(filepath.Join("site/public", c.Query("f"))) })
	r.GET("/p/*name", func(c *gin.Context) { c.File(filepath.Join("site/public", c.Param("name"))) })
	r.GET("/safe", func(c *gin.Context) {
		p := filepath.Join("site/public", filepath.Clean("/"+c.Query("f")))
		c.File(p)
	})
	ts := T(r); defer ts.Close()
	for _, p := range []string{"/q?f=a.txt", "/q?f=../secret.txt", "/q?f=..%2fsecret.txt", "/p/a.txt", "/p/../secret.txt", "/p/..%2fsecret.txt", "/safe?f=a.txt", "/safe?f=../secret.txt"} {
		resp, b := do(ts, "GET", p); if len(b) > 24 { b = b[:24] + "…" }; fmt.Printf("  GET %-24s → %d %q\\n", p, resp.StatusCode, strings.TrimSpace(b))
	}
}'''))
out_lines(r)
print('== 六:大文件:c.File 流式发送 vs 先 ReadFile 再 c.Data——200 MiB 文件服务一次的累计分配')
r = gin('n40e', TT('''
func main() {
	f, _ := os.Create("site/big.bin"); f.Truncate(200 << 20); f.Close()
	r := gin.New()
	var a0 uint64
	alloc := func() uint64 { var m runtime.MemStats; runtime.ReadMemStats(&m); return m.TotalAlloc }
	r.GET("/file", func(c *gin.Context) { c.File("site/big.bin") })
	r.GET("/data", func(c *gin.Context) { b, _ := os.ReadFile("site/big.bin"); c.Data(200, "application/octet-stream", b) })
	r.GET("/reader", func(c *gin.Context) { f, _ := os.Open("site/big.bin"); defer f.Close(); fi, _ := f.Stat(); c.DataFromReader(200, fi.Size(), "application/octet-stream", f, map[string]string{"X-Extra": "yes"}) })
	ts := T(r); defer ts.Close()
	for _, p := range []string{"/file", "/data", "/reader"} {
		a0 = alloc(); resp, err := http.Get(ts.URL + p); if err != nil { fmt.Println(err); continue }
		n, _ := io.Copy(io.Discard, resp.Body); resp.Body.Close()
		fmt.Printf("  %-8s → %d 收到 %d MiB Content-Length=%s X-Extra=%q;进程累计分配增加 %.1f MiB\\n", p, resp.StatusCode, n>>20, resp.Header.Get("Content-Length"), resp.Header.Get("X-Extra"), float64(alloc()-a0)/(1<<20))
	}
	os.Remove("site/big.bin")
}'''), )
out_lines(r)
