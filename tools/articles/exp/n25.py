import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n25')
print('== 一:第一次写之前改的头会发给客户端,之后改的不会(真实 HTTP 客户端看到的头)')
r = gin('n25a', """package main
import ("fmt"; "io"; "net/http"; "net/http/httptest"; "sort"; "strings"; "github.com/gin-gonic/gin")
func main() {
	r := gin.New()
	r.GET("/before", func(c *gin.Context) { c.Header("X-Step", "1-before"); c.Header("X-Step", "2-before-again"); c.String(200, "body") })
	r.GET("/after-body", func(c *gin.Context) { c.String(200, "body"); c.Header("X-Late", "after-body") })
	r.GET("/after-status", func(c *gin.Context) { c.Writer.WriteHeaderNow(); c.Header("X-Late", "after-WriteHeaderNow") })
	r.GET("/status-only", func(c *gin.Context) { c.Status(202); c.Header("X-Late", "after-c.Status(没写出)") })
	r.GET("/delete", func(c *gin.Context) { c.Header("X-Gone", "v"); c.Header("X-Gone", ""); c.Writer.Header().Del("X-Del"); c.Writer.Header().Set("X-Del", "1"); c.Writer.Header().Del("X-Del"); c.String(200, "ok") })
	ts := httptest.NewServer(r); defer ts.Close()
	for _, p := range []string{"/before", "/after-body", "/after-status", "/status-only", "/delete"} {
		resp, _ := http.Get(ts.URL + p); io.Copy(io.Discard, resp.Body); resp.Body.Close()
		var ks []string
		for k, v := range resp.Header { if strings.HasPrefix(k, "X-") { ks = append(ks, k+"="+strings.Join(v, "|")) } }
		sort.Strings(ks)
		fmt.Printf("  %-14s → %d 客户端看到的 X- 头:%v\\n", p, resp.StatusCode, ks)
	}
}""")
out_lines(r)
print('== 二:Content-Type:不设就在第一次写时由 Go 嗅探;之后再设没用')
r = gin('n25b', """package main
import ("fmt"; "io"; "net/http"; "net/http/httptest"; "github.com/gin-gonic/gin")
func main() {
	r := gin.New()
	r.GET("/sniff-html", func(c *gin.Context) { c.Writer.WriteString("<html><body>hi</body></html>") })
	r.GET("/sniff-text", func(c *gin.Context) { c.Writer.WriteString("just text") })
	r.GET("/sniff-json", func(c *gin.Context) { c.Writer.WriteString(`{"a":1}`) })
	r.GET("/sniff-png", func(c *gin.Context) { c.Writer.Write([]byte("\\x89PNG\\r\\n\\x1a\\n....")) })
	r.GET("/set-before", func(c *gin.Context) { c.Header("Content-Type", "application/json"); c.Writer.WriteString("<html>x</html>") })
	r.GET("/set-after", func(c *gin.Context) { c.Writer.WriteString("<html>x</html>"); c.Header("Content-Type", "application/json") })
	r.GET("/c-string", func(c *gin.Context) { c.String(200, "<html>x</html>") })
	ts := httptest.NewServer(r); defer ts.Close()
	for _, p := range []string{"/sniff-html", "/sniff-text", "/sniff-json", "/sniff-png", "/set-before", "/set-after", "/c-string"} {
		resp, _ := http.Get(ts.URL + p); io.Copy(io.Discard, resp.Body); resp.Body.Close()
		fmt.Printf("  %-13s Content-Type=%q\\n", p, resp.Header.Get("Content-Type"))
	}
}""")
out_lines(r)
print('== 三:在 net/http 层重复 WriteHeader:服务器会往 ErrorLog 打 superfluous 日志(Gin 这一层的 WriteHeader 只记录状态,不会触发)')
r = gin('n25c', """package main
import ("bytes"; "fmt"; "io"; "log"; "net/http"; "net/http/httptest"; "strings"; "github.com/gin-gonic/gin")
func main() {
	r := gin.New()
	r.GET("/gin-twice", func(c *gin.Context) { c.Writer.WriteHeader(201); c.Writer.WriteHeaderNow(); c.Writer.WriteHeader(500); c.Writer.WriteHeaderNow(); c.String(201, "ok") })
	r.GET("/raw-twice", func(c *gin.Context) {
		raw := c.Writer.(interface{ Unwrap() http.ResponseWriter }).Unwrap()
		raw.WriteHeader(201); raw.WriteHeader(500); c.Writer.WriteString("x")
	})
	var logbuf bytes.Buffer
	ts := httptest.NewUnstartedServer(r); ts.Config.ErrorLog = log.New(&logbuf, "", 0); ts.Start(); defer ts.Close()
	for _, p := range []string{"/gin-twice", "/raw-twice"} {
		logbuf.Reset()
		resp, _ := http.Get(ts.URL + p); io.Copy(io.Discard, resp.Body); resp.Body.Close()
		l := strings.TrimSpace(logbuf.String()); if l == "" { l = "(没有日志)" }
		fmt.Printf("  %-11s → 客户端状态 %d;服务器 ErrorLog:%s\\n", p, resp.StatusCode, l)
	}
}""")
out_lines(r)
print('== 四:想在写完正文之后再发的头:Trailer(用 http.TrailerPrefix,走 chunked)')
r = gin('n25d', """package main
import ("crypto/sha256"; "encoding/hex"; "fmt"; "io"; "net/http"; "net/http/httptest"; "github.com/gin-gonic/gin")
func main() {
	r := gin.New()
	r.GET("/t", func(c *gin.Context) {
		h := sha256.New()
		for _, part := range []string{"hello ", "trailer ", "world"} { c.Writer.WriteString(part); h.Write([]byte(part)); c.Writer.Flush() }
		c.Header(http.TrailerPrefix+"X-Body-Sha256", hex.EncodeToString(h.Sum(nil))[:16])
		c.Header("X-Not-Trailer", "late")
	})
	ts := httptest.NewServer(r); defer ts.Close()
	resp, _ := http.Get(ts.URL + "/t")
	fmt.Printf("  读 body 之前:resp.Trailer=%v,TransferEncoding=%v\\n", resp.Trailer, resp.TransferEncoding)
	b, _ := io.ReadAll(resp.Body); resp.Body.Close()
	fmt.Printf("  读完 body 之后:正文=%q resp.Trailer=%v;X-Not-Trailer=%q\\n", b, resp.Trailer, resp.Header.Get("X-Not-Trailer"))
}""")
out_lines(r)
