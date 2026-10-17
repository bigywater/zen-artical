import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n24')
print('== 一:responseWriter 的源码:size = -1 表示“还没写”;WriteHeader 只记录状态,WriteHeaderNow 才真正发出')
gsrcl('response_writer.go', 42, 56, title='response_writer.go 的 responseWriter')
gsrcl('response_writer.go', 58, 90, title='response_writer.go 的 reset / WriteHeader / Write')
print('== 二:Status() / Size() / Written() 在一次请求里的变化')
r = gin('n24a', """package main
import ("fmt"; "net/http/httptest"; "github.com/gin-gonic/gin")
func main() {
	r := gin.New()
	r.GET("/x", func(c *gin.Context) {
		p := func(step string) { fmt.Printf("  %-34s Status()=%d Size()=%-3d Written()=%v\\n", step, c.Writer.Status(), c.Writer.Size(), c.Writer.Written()) }
		p("handler 刚进入")
		c.Header("X-A", "1"); p("c.Header(\\"X-A\\", \\"1\\")")
		c.Status(201); p("c.Status(201)")
		c.Status(202); p("再 c.Status(202)(还没写,可以改)")
		c.Writer.WriteHeaderNow(); p("c.Writer.WriteHeaderNow()")
		c.Status(500); p("再 c.Status(500)(已经发出,改不动)")
		c.Writer.WriteString("hello"); p("WriteString(\\"hello\\")")
		c.Writer.Write([]byte(" world")); p("Write(\\" world\\")")
		c.Header("X-Late", "1")
	})
	w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest("GET", "/x", nil))
	fmt.Printf("  最终客户端:状态=%d 正文=%q\\n", w.Code, w.Body.String())
}""")
out_lines(r)
print('== 三:已经发出之后再改状态:release 模式静默忽略,debug 模式会打印一条 WARNING')
r = gin('n24b', """package main
import ("net/http/httptest"; "github.com/gin-gonic/gin")
func main() {
	r := gin.New()
	r.GET("/x", func(c *gin.Context) { c.String(200, "body"); c.Status(500) })
	r.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", "/x", nil))
}""", env=dict(GIN_MODE='debug'))
out_lines(r)
print('== 四:包装 ResponseWriter 抓取响应体(日志 / 签名 / 压缩中间件的常见写法):只覆盖 Write 会漏掉什么')
r = gin('n24c', """package main
import ("bytes"; "fmt"; "io"; "net/http"; "net/http/httptest"; "github.com/gin-gonic/gin")
type capW struct{ gin.ResponseWriter; buf bytes.Buffer; viaWrite, viaWS int }
func (w *capW) Write(b []byte) (int, error) { w.viaWrite++; w.buf.Write(b); return w.ResponseWriter.Write(b) }
type capW2 struct{ capW }
func (w *capW2) WriteString(s string) (int, error) { w.viaWS++; w.buf.WriteString(s); return w.ResponseWriter.WriteString(s) }
func main() {
	h := map[string]gin.HandlerFunc{
		"c.String":            func(c *gin.Context) { c.String(200, "hello %s", "str") },
		"c.JSON":              func(c *gin.Context) { c.JSON(200, gin.H{"a": 1}) },
		"c.Data":              func(c *gin.Context) { c.Data(200, "text/plain", []byte("data!")) },
		"c.Writer.WriteString": func(c *gin.Context) { c.Writer.WriteString("direct") },
		"io.WriteString(c.Writer, ...)": func(c *gin.Context) { io.WriteString(c.Writer, "iows") },
	}
	for _, name := range []string{"c.String", "c.JSON", "c.Data", "c.Writer.WriteString", "io.WriteString(c.Writer, ...)"} {
		var one *capW; var two *capW2
		r := gin.New()
		r.Use(func(c *gin.Context) { one = &capW{ResponseWriter: c.Writer}; c.Writer = one; c.Next() })
		r.GET("/x", h[name])
		w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest("GET", "/x", nil))
		r2 := gin.New()
		r2.Use(func(c *gin.Context) { two = &capW2{capW{ResponseWriter: c.Writer}}; c.Writer = two; c.Next() })
		r2.GET("/x", h[name])
		w2 := httptest.NewRecorder(); r2.ServeHTTP(w2, httptest.NewRequest("GET", "/x", nil))
		fmt.Printf("  %-32s 客户端收到 %-12q | 只覆盖 Write:抓到 %-12q | 再覆盖 WriteString:抓到 %q\\n", name, w.Body.String(), one.buf.String(), two.buf.String())
	}
	_ = http.StatusOK
}""")
out_lines(r)
print('== 五:Hijack:正文写出之前可以,写出之后返回 errHijackAlreadyWritten(真实服务器)')
r = gin('n24d', """package main
import ("fmt"; "io"; "net/http"; "net/http/httptest"; "github.com/gin-gonic/gin")
func main() {
	var res []string
	r := gin.New()
	r.GET("/before", func(c *gin.Context) { conn, _, err := c.Writer.Hijack(); res = append(res, fmt.Sprintf("写正文前 Hijack: conn!=nil %v err=%v", conn != nil, err)); if conn != nil { conn.Write([]byte("HTTP/1.1 200 OK\\r\\nContent-Length: 2\\r\\n\\r\\nhi")); conn.Close() } })
	r.GET("/after", func(c *gin.Context) { c.String(200, "already"); c.Writer.Flush(); _, _, err := c.Writer.Hijack(); res = append(res, fmt.Sprintf("写正文后 Hijack: err=%v", err)) })
	ts := httptest.NewServer(r); defer ts.Close()
	for _, p := range []string{"/before", "/after"} { resp, err := http.Get(ts.URL + p); if err == nil { b, _ := io.ReadAll(resp.Body); resp.Body.Close(); res = append(res, fmt.Sprintf("  客户端收到 %d %q", resp.StatusCode, b)) } }
	for _, s := range res { fmt.Println("  " + s) }
}""")
out_lines(r)
