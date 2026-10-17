import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n46')
PRE = '''package main
import ("context"; "errors"; "fmt"; "io"; "net"; "net/http"; "net/http/httptest"; "strings"; "sync"; "time"; "github.com/gin-gonic/gin")
var _ = context.Background
var _ = errors.New
var _ = io.EOF
var _ = httptest.NewServer
var _ = net.Dial
var _ = strings.TrimSpace
var _ = sync.Mutex{}
func get(url string) (int, string, time.Duration, error) {
	t0 := time.Now(); resp, err := http.Get(url); if err != nil { return 0, "", time.Since(t0), err }
	b, _ := io.ReadAll(resp.Body); resp.Body.Close(); return resp.StatusCode, strings.TrimSpace(string(b)), time.Since(t0), nil
}
'''
print('== 一:标准库 http.TimeoutHandler 包住 Gin:到点返回 503,但 handler 并不会被打断——它继续跑完,只是写出的内容被丢弃')
r = gin('n46a', PRE + '''
func main() {
	r := gin.New(); r.ContextWithFallback = true
	var mu sync.Mutex; var ev []string; t0 := time.Now()
	rec := func(s string) { mu.Lock(); ev = append(ev, fmt.Sprintf("%4d ms %s", time.Since(t0).Milliseconds(), s)); mu.Unlock() }
	r.GET("/slow", func(c *gin.Context) {
		rec("handler 开始")
		time.Sleep(300 * time.Millisecond)
		rec(fmt.Sprintf("handler 睡醒,Request.Context().Err()=%v", c.Request.Context().Err()))
		_, err := c.Writer.WriteString("迟到的响应")
		rec(fmt.Sprintf("handler 写响应的返回值 err=%v", err))
	})
	ts := httptest.NewServer(http.TimeoutHandler(r, 100*time.Millisecond, "超时了"))
	defer ts.Close()
	code, body, el, err := get(ts.URL + "/slow"); rec(fmt.Sprintf("客户端收到 %d %q(耗时 %d ms)err=%v", code, body, el.Milliseconds(), err))
	time.Sleep(300 * time.Millisecond)
	for _, e := range ev { fmt.Println("  " + e) }
}''')
out_lines(r)
print('== 二:用 context 超时自己控制:handler 收到取消就主动结束(客户端同样 100ms 得到 504,handler 也立刻停下)')
r = gin('n46b', PRE + '''
func main() {
	r := gin.New()
	var mu sync.Mutex; var ev []string; t0 := time.Now()
	rec := func(s string) { mu.Lock(); ev = append(ev, fmt.Sprintf("%4d ms %s", time.Since(t0).Milliseconds(), s)); mu.Unlock() }
	r.Use(func(c *gin.Context) {
		ctx, cancel := context.WithTimeout(c.Request.Context(), 100*time.Millisecond); defer cancel()
		c.Request = c.Request.WithContext(ctx); c.Next()
	})
	r.GET("/slow", func(c *gin.Context) {
		rec("handler 开始")
		select {
		case <-time.After(300 * time.Millisecond): c.String(200, "完成")
		case <-c.Request.Context().Done(): rec(fmt.Sprintf("handler 收到取消:%v,立即返回 504", c.Request.Context().Err())); c.AbortWithStatusJSON(504, gin.H{"error": "timeout"})
		}
		rec("handler 返回")
	})
	ts := httptest.NewServer(r); defer ts.Close()
	code, body, el, err := get(ts.URL + "/slow"); rec(fmt.Sprintf("客户端收到 %d %q(耗时 %d ms)err=%v", code, body, el.Milliseconds(), err))
	time.Sleep(300 * time.Millisecond)
	for _, e := range ev { fmt.Println("  " + e) }
}''')
out_lines(r)
print('== 三:handler 不理会 context(调一个不接受 context 的慢函数):context 超时对它没有任何作用')
r = gin('n46c', PRE + '''
func main() {
	r := gin.New()
	r.Use(func(c *gin.Context) { ctx, cancel := context.WithTimeout(c.Request.Context(), 100*time.Millisecond); defer cancel(); c.Request = c.Request.WithContext(ctx); c.Next() })
	r.GET("/ignore", func(c *gin.Context) { time.Sleep(300 * time.Millisecond); c.String(200, "睡了 300ms,ctx.Err()=%v", c.Request.Context().Err()) })
	ts := httptest.NewServer(r); defer ts.Close()
	code, body, el, err := get(ts.URL + "/ignore"); fmt.Printf("  客户端收到 %d %q(耗时 %d ms)err=%v\\n", code, body, el.Milliseconds(), err)
}''')
out_lines(r)
print('== 四:http.Server 的 WriteTimeout:到点直接关连接,客户端拿不到任何响应(对比 TimeoutHandler 的 503)')
r = gin('n46d', PRE + '''
func tail(err error) string { if err == nil { return "<nil>" }; s := err.Error(); return s[strings.LastIndex(s, ": ")+2:] }
func main() {
	r := gin.New(); r.GET("/slow", func(c *gin.Context) { time.Sleep(300 * time.Millisecond); c.String(200, "done") })
	ts := httptest.NewUnstartedServer(r); ts.Config.WriteTimeout = 100 * time.Millisecond; ts.Start(); defer ts.Close()
	code, body, el, err := get(ts.URL + "/slow"); fmt.Printf("  WriteTimeout=100ms:客户端 %d %q 耗时 %d ms,错误:%v\\n", code, body, el.Milliseconds(), tail(err))
	ts2 := httptest.NewServer(http.TimeoutHandler(r, 100*time.Millisecond, "超时了")); defer ts2.Close()
	code, body, el, err = get(ts2.URL + "/slow"); fmt.Printf("  TimeoutHandler=100ms:客户端 %d %q 耗时 %d ms,错误:%v\\n", code, body, el.Milliseconds(), err)
}''')
out_lines(r)
print('== 五:r.Run / RunListener 创建的 http.Server 没有任何超时:慢速发送请求头的连接会被一直保持;设置 ReadHeaderTimeout 后到点关闭')
gfunc('gin.go', 'RunListener')
r = gin('n46e', PRE + '''
func probe(addr string, wait time.Duration) string {
	conn, err := net.Dial("tcp", addr); if err != nil { return err.Error() }
	defer conn.Close(); fmt.Fprint(conn, "GET / HTTP/1.1\\r\\nHost: a\\r\\nX-Slow: ")
	t0 := time.Now(); conn.SetReadDeadline(time.Now().Add(wait)); buf := make([]byte, 512); n, err := conn.Read(buf)
	if ne, ok := err.(net.Error); ok && ne.Timeout() { return fmt.Sprintf("等了 %d ms,服务端一直没有关闭连接(请求头还没发完)", time.Since(t0).Milliseconds()) }
	return fmt.Sprintf("%d ms 后连接被服务端关闭:读到 %d 字节 %q err=%v", time.Since(t0).Milliseconds(), n, strings.SplitN(string(buf[:n]), "\\r\\n", 2)[0], err)
}
func main() {
	r := gin.New(); r.GET("/", func(c *gin.Context) {})
	ln, _ := net.Listen("tcp", "127.0.0.1:0")
	go r.RunListener(ln)
	time.Sleep(100 * time.Millisecond)
	fmt.Printf("  r.RunListener(默认):%s\\n", probe(ln.Addr().String(), 1500*time.Millisecond))
	ln2, _ := net.Listen("tcp", "127.0.0.1:0")
	srv := &http.Server{Handler: r, ReadHeaderTimeout: 300 * time.Millisecond}
	go srv.Serve(ln2); time.Sleep(100 * time.Millisecond)
	fmt.Printf("  http.Server{ReadHeaderTimeout: 300ms}:%s\\n", probe(ln2.Addr().String(), 1500*time.Millisecond))
}''', timeout=60)
out_lines(r)
