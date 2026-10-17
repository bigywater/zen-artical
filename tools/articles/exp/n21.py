import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n21')
print('== 一:Deadline / Done / Err / Value 的源码')
gsrcl('context.go', 1433, 1483, w=110)
print('== 二:默认(ContextWithFallback=false)与打开之后:c 作为 context.Context 用时的行为')
r = gin('n21a', """package main
import ("context"; "fmt"; "net/http"; "net/http/httptest"; "io"; "time"; "github.com/gin-gonic/gin")
type ctxKey string
func work(ctx context.Context, name string) string {
	t0 := time.Now()
	select {
	case <-ctx.Done(): return fmt.Sprintf("%s:%v 取消(%d ms)", name, ctx.Err(), time.Since(t0).Milliseconds())
	case <-time.After(400 * time.Millisecond): return fmt.Sprintf("%s:没有被取消,自己跑完 (%d ms)", name, time.Since(t0).Milliseconds())
	}
}
func main() {
	for _, fb := range []bool{false, true} {
		r := gin.New(); r.ContextWithFallback = fb
		r.Use(func(c *gin.Context) {
			ctx, cancel := context.WithTimeout(context.WithValue(c.Request.Context(), ctxKey("trace"), "T-1"), 100*time.Millisecond); defer cancel()
			c.Request = c.Request.WithContext(ctx); c.Set("user", "alice"); c.Next()
		})
		r.GET("/viaC", func(c *gin.Context) {
			_, hasDl := c.Deadline()
			c.String(200, "c.Done()==nil:%v  c.Err()=%v  c.Deadline() ok=%v\\n    c.Value(\\"user\\")=%v  c.Value(ctxKey(\\"trace\\"))=%v  c.Request.Context().Value(ctxKey(\\"trace\\"))=%v\\n    %s", c.Done() == nil, c.Err(), hasDl, c.Value("user"), c.Value(ctxKey("trace")), c.Request.Context().Value(ctxKey("trace")), work(c, "work(c)"))
		})
		r.GET("/viaReq", func(c *gin.Context) { c.String(200, "%s", work(c.Request.Context(), "work(c.Request.Context())")) })
		ts := httptest.NewServer(r)
		var outs []string
		for _, p := range []string{"/viaC", "/viaReq"} { resp, _ := http.Get(ts.URL + p); b, _ := io.ReadAll(resp.Body); resp.Body.Close(); outs = append(outs, string(b)) }
		ts.Close()
		fmt.Printf("  ContextWithFallback=%v:\\n    %s\\n    %s\\n", fb, outs[0], outs[1])
	}
}""")
out_lines(r)
print('== 三:用 c 作父 context 派生子 context(context.WithTimeout(c, ...))时,请求超时 / 客户端断开能不能传下去')
r = gin('n21b', """package main
import ("context"; "fmt"; "net"; "net/http"; "net/http/httptest"; "io"; "time"; "github.com/gin-gonic/gin")
func main() {
	for _, fb := range []bool{false, true} {
		r := gin.New(); r.ContextWithFallback = fb
		done := make(chan string, 1)
		r.GET("/x", func(c *gin.Context) {
			child, cancel := context.WithTimeout(c, 1500*time.Millisecond); defer cancel()   // 以 c 为父
			t0 := time.Now()
			select {
			case <-child.Done(): done <- fmt.Sprintf("子 context 结束:%v,%d ms 后", child.Err(), time.Since(t0).Milliseconds())
			}
			c.String(200, "x")
		})
		ts := httptest.NewServer(r)
		conn, _ := net.Dial("tcp", ts.Listener.Addr().String())
		fmt.Fprintf(conn, "GET /x HTTP/1.1\\r\\nHost: a\\r\\n\\r\\n")
		time.Sleep(200 * time.Millisecond); conn.Close()      // 客户端在 200ms 时断开
		fmt.Printf("  ContextWithFallback=%-5v 客户端 200ms 时断开 → %s\\n", fb, <-done)
		ts.Close(); _ = http.StatusOK; _ = io.EOF
	}
}""")
out_lines(r)
