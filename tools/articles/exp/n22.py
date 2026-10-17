import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n22')
print('== 一:GET 请求,客户端 200ms 后直接关闭连接:服务端的 Request.Context() 什么时候被取消')
SRC = """package main
import ("fmt"; "io"; "net"; "net/http"; "net/http/httptest"; "time"; "github.com/gin-gonic/gin")
func main() {
	r := gin.New(); r.ContextWithFallback = true
	ev := make(chan string, 8)
	r.GET("/wait", func(c *gin.Context) {
		t0 := time.Now()
		select {
		case <-c.Request.Context().Done(): ev <- fmt.Sprintf("handler 在 %d ms 时看到 Request.Context() 取消:%v", time.Since(t0).Milliseconds(), c.Request.Context().Err())
		case <-time.After(2 * time.Second): ev <- "handler 等满 2000 ms,始终没有收到取消"
		}
	})
	r.POST("/nobody", func(c *gin.Context) {   // 不读 body
		t0 := time.Now()
		select {
		case <-c.Request.Context().Done(): ev <- fmt.Sprintf("handler(不读 body)在 %d ms 时看到取消:%v", time.Since(t0).Milliseconds(), c.Request.Context().Err())
		case <-time.After(2 * time.Second): ev <- "handler(不读 body)等满 2000 ms,始终没有收到取消"
		}
	})
	r.POST("/readbody", func(c *gin.Context) {   // 读 body:客户端只发了一部分
		t0 := time.Now()
		n, err := io.Copy(io.Discard, c.Request.Body)
		ev <- fmt.Sprintf("handler 读 body:读到 %d 字节后返回 err=%v,%d ms;此时 Request.Context().Err()=%v", n, err, time.Since(t0).Milliseconds(), c.Request.Context().Err())
	})
	ts := httptest.NewServer(r); defer ts.Close()
	addr := ts.Listener.Addr().String()
	for _, tc := range []struct{ name, req string }{
		{"GET /wait", "GET /wait HTTP/1.1\\r\\nHost: a\\r\\n\\r\\n"},
		{"POST /nobody(声明 1000 字节只发 10 字节)", "POST /nobody HTTP/1.1\\r\\nHost: a\\r\\nContent-Length: 1000\\r\\n\\r\\n0123456789"},
		{"POST /readbody(声明 1000 字节只发 10 字节)", "POST /readbody HTTP/1.1\\r\\nHost: a\\r\\nContent-Length: 1000\\r\\n\\r\\n0123456789"},
	} {
		conn, _ := net.Dial("tcp", addr); fmt.Fprint(conn, tc.req)
		time.Sleep(200 * time.Millisecond); conn.Close()
		fmt.Printf("  [%s] 客户端 200 ms 时关闭连接\\n    %s\\n", tc.name, <-ev)
	}
	_ = http.StatusOK
}"""
r = gin('n22a', SRC, timeout=120)
out_lines(r)
print('== 二:客户端断开之后,服务端继续往连接里写会怎样(写 handler 睡 300ms 后分块写)')
r = gin('n22b', """package main
import ("fmt"; "net"; "net/http/httptest"; "strings"; "time"; "github.com/gin-gonic/gin")
func main() {
	r := gin.New(); ev := make(chan string, 4)
	r.GET("/w", func(c *gin.Context) {
		time.Sleep(300 * time.Millisecond)
		chunk := strings.Repeat("x", 64*1024); var firstErr error; wrote := 0
		for i := 0; i < 200; i++ {
			n, err := c.Writer.WriteString(chunk); wrote += n
			if err != nil { firstErr = err; ev <- fmt.Sprintf("第 %d 次写(累计 %d KB)返回错误:%v;c.Request.Context().Err()=%v", i+1, wrote/1024, firstErr, c.Request.Context().Err()); return }
			c.Writer.Flush()
			time.Sleep(time.Millisecond)
		}
		ev <- fmt.Sprintf("写了 %d KB 都没有出错", wrote/1024)
	})
	ts := httptest.NewServer(r); defer ts.Close()
	conn, _ := net.Dial("tcp", ts.Listener.Addr().String()); fmt.Fprint(conn, "GET /w HTTP/1.1\\r\\nHost: a\\r\\n\\r\\n")
	time.Sleep(100 * time.Millisecond); conn.Close()
	fmt.Println("  客户端 100ms 时断开;handler 300ms 时开始写,每块 64KB 并 Flush")
	fmt.Println("  " + <-ev)
}""")
out_lines(r)
print('== 三:断开之后 c.Done()(ContextWithFallback)与 c.Request.Context().Done() 各自的状态')
r = gin('n22c', """package main
import ("fmt"; "net"; "net/http/httptest"; "time"; "github.com/gin-gonic/gin")
func main() {
	for _, fb := range []bool{false, true} {
		r := gin.New(); r.ContextWithFallback = fb; ev := make(chan string, 2)
		r.GET("/x", func(c *gin.Context) {
			t0 := time.Now()
			<-c.Request.Context().Done()
			s := fmt.Sprintf("c.Request.Context().Done() 在 %d ms 触发", time.Since(t0).Milliseconds())
			select {
			case <-c.Done(): s += ";c.Done() 也已触发"
			case <-time.After(100 * time.Millisecond): s += fmt.Sprintf(";c.Done() 100 ms 内没有触发(c.Done()==nil: %v)", c.Done() == nil)
			}
			ev <- s
		})
		ts := httptest.NewServer(r)
		conn, _ := net.Dial("tcp", ts.Listener.Addr().String()); fmt.Fprint(conn, "GET /x HTTP/1.1\\r\\nHost: a\\r\\n\\r\\n")
		time.Sleep(150 * time.Millisecond); conn.Close()
		fmt.Printf("  ContextWithFallback=%-5v → %s\\n", fb, <-ev); ts.Close()
	}
}""")
out_lines(r)
print('== 四:为什么不读 body 的 POST 检测不到断开:net/http 服务器的源码(Go 1.27.1 标准库)')
L = open(GOROOT + '/src/net/http/server.go').read().split('\n')
print('  <GOROOT>/src/net/http/server.go(Go 1.27.1):')
for i in range(2119, 2127): print(f'  {i + 1:>6} | {L[i].rstrip()}'.replace('\t', '    '))
