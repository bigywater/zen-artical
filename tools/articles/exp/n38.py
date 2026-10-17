import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n38')
PRE = '''package main
import ("bufio"; "fmt"; "io"; "net"; "net/http"; "net/http/httptest"; "strings"; "sync/atomic"; "time"; "github.com/gin-gonic/gin")
var _ = bufio.NewReader
var _ = http.StatusOK
var _ = io.EOF
var _ = net.Dial
var _ = atomic.AddInt64
var _ = time.Now
var _ = strings.TrimSpace
'''
print('== 一:Stream 与 SSEvent 的源码')
gfunc('context.go', 'Stream'); gfunc('context.go', 'SSEvent')
print('== 二:c.SSEvent 写出的原始字节:字符串、数字、结构体(JSON)、多行文本、空事件名;以及响应头')
r = gin('n38a', PRE + '''
type M struct{ A int `json:"a"`; B string `json:"b"` }
func main() {
	r := gin.New()
	r.GET("/e", func(c *gin.Context) {
		c.SSEvent("message", "hello")
		c.SSEvent("num", 42)
		c.SSEvent("obj", M{1, "x<y"})
		c.SSEvent("multi", "line1\\nline2\\nline3")
		c.SSEvent("", "没有事件名")
		c.SSEvent("bytes", []byte("raw"))
		c.SSEvent("nilmsg", nil)
	})
	w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest("GET", "/e", nil))
	fmt.Printf("  状态 %d;Content-Type=%q;Cache-Control=%q;Connection=%q;X-Accel-Buffering=%q\\n  原始正文:\\n", w.Code, w.Header().Get("Content-Type"), w.Header().Get("Cache-Control"), w.Header().Get("Connection"), w.Header().Get("X-Accel-Buffering"))
	for _, l := range strings.Split(w.Body.String(), "\\n") { fmt.Printf("    |%s\\n", l) }
}''')
out_lines(r, n=40)
print('== 三:真实流式:服务端每 200ms 发一个事件,客户端逐行读取并记录到达时间(c.Stream 每步 Flush;对照:循环里只 SSEvent、不 Flush)')
r = gin('n38b', PRE + '''
func main() {
	r := gin.New()
	r.GET("/stream", func(c *gin.Context) {
		i := 0
		c.Stream(func(w io.Writer) bool {
			if i >= 4 { return false }
			time.Sleep(200 * time.Millisecond); i++
			c.SSEvent("tick", i); return true
		})
	})
	r.GET("/noflush", func(c *gin.Context) {
		for i := 1; i <= 4; i++ { time.Sleep(200 * time.Millisecond); c.SSEvent("tick", i) }
	})
	r.GET("/flush", func(c *gin.Context) {
		for i := 1; i <= 4; i++ { time.Sleep(200 * time.Millisecond); c.SSEvent("tick", i); c.Writer.Flush() }
	})
	ts := httptest.NewServer(r); defer ts.Close()
	for _, p := range []string{"/stream", "/noflush", "/flush"} {
		t0 := time.Now(); resp, _ := http.Get(ts.URL + p)
		hdr := time.Since(t0).Milliseconds()
		br := bufio.NewReader(resp.Body); var arr []string
		for { l, err := br.ReadString('\\n'); if err != nil { break }; if strings.HasPrefix(l, "data:") { arr = append(arr, fmt.Sprintf("%s@%dms", strings.TrimSpace(l[5:]), time.Since(t0).Milliseconds())) } }
		resp.Body.Close()
		fmt.Printf("  %-9s 响应头到达 %3d ms;事件到达:%v;TransferEncoding=%v\\n", p, hdr, arr, resp.TransferEncoding)
	}
}''', timeout=120)
out_lines(r)
print('== 四:客户端断开:Stream 靠 CloseNotify 发现并返回 true;断开之后 step 还会被调用几次')
r = gin('n38c', PRE + '''
func main() {
	r := gin.New(); var steps int64; done := make(chan string, 1)
	r.GET("/s", func(c *gin.Context) {
		gone := c.Stream(func(w io.Writer) bool { time.Sleep(50 * time.Millisecond); atomic.AddInt64(&steps, 1); c.SSEvent("t", 1); return true })
		done <- fmt.Sprintf("Stream 返回 clientGone=%v;step 共被调用 %d 次", gone, atomic.LoadInt64(&steps))
	})
	ts := httptest.NewServer(r); defer ts.Close()
	conn, _ := net.Dial("tcp", ts.Listener.Addr().String()); fmt.Fprint(conn, "GET /s HTTP/1.1\\r\\nHost: a\\r\\n\\r\\n")
	time.Sleep(330 * time.Millisecond); before := atomic.LoadInt64(&steps); t0 := time.Now(); conn.Close()
	fmt.Printf("  客户端在约 330 ms 时断开,此时 step 已调用 %d 次\\n", before)
	select { case s := <-done: fmt.Printf("  断开后 %d ms:%s(断开之后又多调用 %d 次)\\n", time.Since(t0).Milliseconds(), s, atomic.LoadInt64(&steps)-before); case <-time.After(3 * time.Second): fmt.Println("  3 秒后 Stream 仍没有返回") }
}''')
out_lines(r)
print('== 五:step 里不阻塞会怎样:100 ms 内 step 被空转调用的次数(CPU 打满);正确写法是在 step 里等 channel / ticker')
r = gin('n38d', PRE + '''
func main() {
	r := gin.New(); var n int64
	r.GET("/spin", func(c *gin.Context) {
		end := time.Now().Add(100 * time.Millisecond)
		c.Stream(func(w io.Writer) bool { atomic.AddInt64(&n, 1); return time.Now().Before(end) })
	})
	r.GET("/wait", func(c *gin.Context) {
		ch := make(chan int); go func() { for i := 1; i <= 3; i++ { time.Sleep(30 * time.Millisecond); ch <- i }; close(ch) }()
		c.Stream(func(w io.Writer) bool { v, ok := <-ch; if !ok { return false }; c.SSEvent("m", v); atomic.AddInt64(&n, 1); return true })
	})
	ts := httptest.NewServer(r); defer ts.Close()
	for _, p := range []string{"/spin", "/wait"} {
		atomic.StoreInt64(&n, 0); resp, _ := http.Get(ts.URL + p); io.Copy(io.Discard, resp.Body); resp.Body.Close()
		fmt.Printf("  %-6s step 被调用 %d 次\\n", p, atomic.LoadInt64(&n))
	}
}''')
out_lines(r)
