import sys, os, subprocess, threading, time, urllib.request; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n47')
PRE = '''package main
import ("context"; "fmt"; "io"; "net"; "net/http"; "net/http/httptest"; "os"; "os/signal"; "strings"; "sync"; "syscall"; "time"; "github.com/gin-gonic/gin")
var _ = context.Background
var _ = io.EOF
var _ = net.Dial
var _ = os.Getpid
var _ = signal.Notify
var _ = strings.TrimSpace
var _ = sync.Mutex{}
var _ = syscall.SIGTERM
var _ = httptest.NewServer
var t0 = time.Now()
func ms() string { return fmt.Sprintf("%4d ms", time.Since(t0).Milliseconds()) }
func get(url string) (string, error) {
	resp, err := http.Get(url); if err != nil { return "", err }
	b, _ := io.ReadAll(resp.Body); resp.Body.Close(); return fmt.Sprintf("%d %s", resp.StatusCode, strings.TrimSpace(string(b))), nil
}
func tail(err error) string { s := err.Error(); return s[strings.LastIndex(s, ": ")+2:] }
'''
print('== 一:Shutdown 的行为(进程内):handler 要跑 500ms,100ms 时调用 Shutdown(ctx 2s)')
r = gin('n47a', PRE + '''
func main() {
	r := gin.New(); r.GET("/slow", func(c *gin.Context) { time.Sleep(500 * time.Millisecond); c.String(200, "slow done") })
	ln, _ := net.Listen("tcp", "127.0.0.1:0"); srv := &http.Server{Handler: r}; go srv.Serve(ln); base := "http://" + ln.Addr().String()
	var wg sync.WaitGroup; wg.Add(1)
	go func() { defer wg.Done(); res, err := get(base + "/slow"); fmt.Printf("  %s 在途请求结束:%s err=%v\\n", ms(), res, err) }()
	time.Sleep(100 * time.Millisecond)
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second); defer cancel()
	fmt.Printf("  %s 调用 Shutdown\\n", ms())
	go func() { time.Sleep(50 * time.Millisecond); _, err := get(base + "/slow"); fmt.Printf("  %s Shutdown 之后的新请求:err=%v\\n", ms(), tail(err)) }()
	err := srv.Shutdown(ctx); fmt.Printf("  %s Shutdown 返回 err=%v\\n", ms(), err)
	wg.Wait()
}''')
out_lines(r)
print('== 二:ctx 比 handler 先到期:Shutdown 返回 context deadline exceeded,但在途请求并没有被中止;之后 srv.Close() 才会真的断开')
r = gin('n47b', PRE + '''
func main() {
	r := gin.New(); r.GET("/slow", func(c *gin.Context) { time.Sleep(1000 * time.Millisecond); c.String(200, "slow done") })
	ln, _ := net.Listen("tcp", "127.0.0.1:0"); srv := &http.Server{Handler: r}; go srv.Serve(ln); base := "http://" + ln.Addr().String()
	for _, force := range []bool{false, true} {
		t0 = time.Now()
		var wg sync.WaitGroup; wg.Add(1)
		ln2, _ := net.Listen("tcp", "127.0.0.1:0"); s2 := &http.Server{Handler: r}; go s2.Serve(ln2); b2 := "http://" + ln2.Addr().String()
		go func() { defer wg.Done(); res, err := get(b2 + "/slow"); if err != nil { res = "错误:" + tail(err) }; fmt.Printf("  %s 在途请求结束:%s\\n", ms(), res) }()
		time.Sleep(100 * time.Millisecond)
		ctx, cancel := context.WithTimeout(context.Background(), 300*time.Millisecond)
		err := s2.Shutdown(ctx); cancel(); fmt.Printf("  %s Shutdown(ctx 300ms) 返回 err=%v;强制 Close=%v\\n", ms(), err, force)
		if force { fmt.Printf("  %s 调用 srv.Close()\\n", ms()); s2.Close() }
		wg.Wait()
		fmt.Println("  ---")
	}
	_ = base
}''')
out_lines(r)
print('== 三:空闲的 keep-alive 连接:Shutdown 立刻关闭它们;长连接(长轮询 / SSE)不会自己结束,Shutdown 会一直等到 ctx 到期;用 RegisterOnShutdown + BaseContext 通知 handler 退出')
r = gin('n47c', PRE + '''
func main() {
	for _, notify := range []bool{false, true} {
		t0 = time.Now()
		root, cancelRoot := context.WithCancel(context.Background())
		r := gin.New(); r.ContextWithFallback = true
		r.GET("/stream", func(c *gin.Context) {
			c.Writer.WriteString("start\\n"); c.Writer.Flush()
			select { case <-c.Request.Context().Done(): fmt.Printf("  %s 流式 handler 看到取消:%v\\n", ms(), c.Request.Context().Err()); case <-time.After(5 * time.Second): }
		})
		ln, _ := net.Listen("tcp", "127.0.0.1:0")
		srv := &http.Server{Handler: r, BaseContext: func(net.Listener) context.Context { return root }}
		if notify { srv.RegisterOnShutdown(cancelRoot) }
		go srv.Serve(ln)
		resp, _ := http.Get("http://" + ln.Addr().String() + "/stream"); buf := make([]byte, 6); resp.Body.Read(buf)
		time.Sleep(100 * time.Millisecond)
		ctx, cancel := context.WithTimeout(context.Background(), 1500*time.Millisecond)
		err := srv.Shutdown(ctx); cancel()
		fmt.Printf("  RegisterOnShutdown 通知 handler=%-5v → %s Shutdown 返回 err=%v\\n", notify, ms(), err)
		cancelRoot(); resp.Body.Close(); srv.Close(); fmt.Println("  ---")
	}
}''', timeout=60)
out_lines(r)
print('== 四:被 Hijack 的连接(WebSocket 等)不归 Shutdown 管:Shutdown 立刻返回,连接还活着')
r = gin('n47d', PRE + '''
func main() {
	r := gin.New(); done := make(chan struct{})
	r.GET("/hj", func(c *gin.Context) {
		conn, _, err := c.Writer.Hijack(); if err != nil { return }
		conn.Write([]byte("HTTP/1.1 200 OK\\r\\nContent-Length: 5\\r\\n\\r\\nhello")); <-done; conn.Write([]byte("")); conn.Close()
	})
	ln, _ := net.Listen("tcp", "127.0.0.1:0"); srv := &http.Server{Handler: r}; go srv.Serve(ln)
	conn, _ := net.Dial("tcp", ln.Addr().String()); fmt.Fprint(conn, "GET /hj HTTP/1.1\\r\\nHost: a\\r\\n\\r\\n")
	buf := make([]byte, 100); n, _ := conn.Read(buf); fmt.Printf("  %s 客户端读到 %d 字节(handler 已 Hijack,还拿着连接)\\n", ms(), n)
	ctx, cancel := context.WithTimeout(context.Background(), 1*time.Second); defer cancel()
	err := srv.Shutdown(ctx); fmt.Printf("  %s Shutdown 返回 err=%v(没有等被 Hijack 的连接)\\n", ms(), err)
	conn.SetReadDeadline(time.Now().Add(200 * time.Millisecond)); _, err = conn.Read(buf)
	if ne, ok := err.(net.Error); ok && ne.Timeout() { fmt.Printf("  %s 被 Hijack 的连接仍然开着(读超时而不是 EOF)\\n", ms()) } else { fmt.Printf("  连接状态 err=%v\\n", err) }
	close(done)
}''')
out_lines(r)
print('== 五:真实进程:收到 SIGTERM。A:什么都没处理(r.Run);B:signal.NotifyContext + Shutdown。客户端发一个 1.0s 的请求,200ms 时发 SIGTERM')
SRC = """package main
import ("context"; "fmt"; "net/http"; "os"; "os/signal"; "syscall"; "time"; "github.com/gin-gonic/gin")
func main() {
	r := gin.New()
	r.GET("/slow", func(c *gin.Context) { time.Sleep(1000 * time.Millisecond); c.String(200, "slow done") })
	addr := os.Args[2]
	if os.Args[1] == "plain" { r.Run(addr); return }
	srv := &http.Server{Addr: addr, Handler: r}
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, os.Interrupt); defer stop()
	go func() { if err := srv.ListenAndServe(); err != http.ErrServerClosed { fmt.Println("listen:", err) } }()
	<-ctx.Done(); stop()
	fmt.Println("收到信号,开始 Shutdown"); sc, cancel := context.WithTimeout(context.Background(), 5*time.Second); defer cancel()
	if err := srv.Shutdown(sc); err != nil { fmt.Println("shutdown:", err); os.Exit(1) }
	fmt.Println("Shutdown 完成,退出")
}"""
d = gin_dir('n47e', SRC); crc, cout = go(d, 'build', '-o', 'app'); assert crc == 0, cout
import socket
def wait(port):
    for _ in range(100):
        try: socket.create_connection(('127.0.0.1', port), 0.1).close(); return
        except Exception: time.sleep(0.05)
for mode, port in [('plain', 9741), ('graceful', 9742)]:
    p = subprocess.Popen([str(d / 'app'), mode, f'127.0.0.1:{port}'], env=genv(GIN_MODE='release'), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    wait(port); res = {}
    def req():
        t0 = time.time()
        try: res['r'] = urllib.request.urlopen(f'http://127.0.0.1:{port}/slow', timeout=5).read().decode()
        except Exception as e: res['r'] = '错误:' + type(e).__name__ + ' ' + str(e)[:40]
        res['t'] = time.time() - t0
    th = threading.Thread(target=req); th.start(); time.sleep(0.2); ts = time.time(); p.terminate()
    rc = p.wait(timeout=10); out = p.stdout.read().strip().replace('\n', ' | '); th.join()
    print(f'  [{mode}] SIGTERM 发出 {((time.time()-ts)*1000):.0f} ms 后进程退出,退出码 {rc};在途请求(耗时 {res["t"]*1000:.0f} ms)结果:{res["r"]};进程输出:{out or "(无)"}')
