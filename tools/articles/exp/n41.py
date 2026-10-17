import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n41')
PRE = '''package main
import ("bytes"; "errors"; "fmt"; "io"; "net/http"; "net/http/httptest"; "sort"; "strings"; "testing"; "time"; "github.com/gin-gonic/gin")
var _ = errors.New
var _ = io.Discard
var _ = http.StatusOK
var _ = sort.Strings
var _ = testing.Benchmark
var _ = time.Now
var _ = strings.TrimSpace
func hit(r *gin.Engine, method, url string) { r.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest(method, url, nil)) }
func lines(b *bytes.Buffer) { for _, l := range strings.Split(strings.TrimRight(b.String(), "\\n"), "\\n") { fmt.Printf("  %q\\n", l) }; b.Reset() }
'''
print('== 一:默认格式的源码(defaultLogFormatter)与一行日志里每一段的含义')
gsrcl('logger.go', 166, 195)
r = gin('n41a', PRE + '''
func main() {
	var buf bytes.Buffer
	r := gin.New(); r.Use(gin.LoggerWithWriter(&buf))
	r.GET("/ok", func(c *gin.Context) { c.String(200, "ok") })
	r.GET("/slow", func(c *gin.Context) { time.Sleep(1234 * time.Millisecond); c.String(200, "slow") })
	r.GET("/err", func(c *gin.Context) { c.Error(errors.New("数据库超时")); c.String(500, "e") })
	r.POST("/p", func(c *gin.Context) { c.Status(201) })
	for _, u := range [][2]string{{"GET", "/ok"}, {"GET", "/ok?token=SECRET&a=1"}, {"GET", "/slow"}, {"GET", "/nope"}, {"GET", "/err"}, {"POST", "/p"}, {"GET", "/中文/path%20with%20space"}, {"DELETE", "/ok"}} { hit(r, u[0], u[1]) }
	lines(&buf)
}''')
out_lines(r)
print('== 二:耗时从哪里算到哪里:Logger 放在最前 vs 放在慢中间件之后(各 sleep 50ms)')
r = gin('n41b', PRE + '''
func main() {
	var buf bytes.Buffer
	slow := func(c *gin.Context) { time.Sleep(50 * time.Millisecond); c.Next() }
	r1 := gin.New(); r1.Use(gin.LoggerWithWriter(&buf), slow); r1.GET("/x", func(c *gin.Context) { c.String(200, "x") })
	r2 := gin.New(); r2.Use(slow, gin.LoggerWithWriter(&buf)); r2.GET("/x", func(c *gin.Context) { c.String(200, "x") })
	hit(r1, "GET", "/x"); fmt.Println("  Logger 在前,slow 在后:"); lines(&buf)
	hit(r2, "GET", "/x"); fmt.Println("  slow 在前,Logger 在后(slow 的 50ms 不被计入):"); lines(&buf)
	ts := httptest.NewServer(func() *gin.Engine { r := gin.New(); r.Use(gin.LoggerWithWriter(&buf)); r.GET("/x", func(c *gin.Context) { c.String(200, "x") }); return r }())
	defer ts.Close(); t0 := time.Now(); resp, _ := http.Get(ts.URL + "/x"); io.Copy(io.Discard, resp.Body); resp.Body.Close()
	fmt.Printf("  真实 HTTP 往返(含建立连接)客户端测得 %.2f ms;服务端日志里记录的是:\\n", float64(time.Since(t0).Microseconds())/1000); lines(&buf)
}''')
out_lines(r)
print('== 三:颜色:输出不是终端时不带颜色;ForceConsoleColor 之后带 ANSI 转义;DisableConsoleColor 关闭')
r = gin('n41c', PRE + '''
func main() {
	var buf bytes.Buffer
	mk := func() *gin.Engine { r := gin.New(); r.Use(gin.LoggerWithWriter(&buf)); r.GET("/ok", func(c *gin.Context) { c.String(200, "ok") }); r.GET("/bad", func(c *gin.Context) { c.Status(404) }); return r }
	r := mk(); hit(r, "GET", "/ok"); fmt.Println("  默认(buffer 不是终端):"); lines(&buf)
	gin.ForceConsoleColor(); r = mk(); hit(r, "GET", "/ok"); hit(r, "GET", "/bad"); fmt.Println("  ForceConsoleColor:"); lines(&buf)
	gin.DisableConsoleColor(); r = mk(); hit(r, "GET", "/ok"); fmt.Println("  DisableConsoleColor:"); lines(&buf)
}''')
out_lines(r)
print('== 四:LoggerConfig:SkipPaths、Skip、SkipQueryString(别把令牌写进日志)、自定义 Formatter(JSON 一行)')
r = gin('n41d', PRE + '''
func main() {
	var buf bytes.Buffer
	r := gin.New()
	r.Use(gin.LoggerWithConfig(gin.LoggerConfig{
		Output: &buf, SkipPaths: []string{"/health"}, SkipQueryString: true,
		Skip: func(c *gin.Context) bool { return c.Writer.Status() < 400 && strings.HasPrefix(c.Request.URL.Path, "/quiet") },
		Formatter: func(p gin.LogFormatterParams) string {
			return fmt.Sprintf(`{"t":"%s","status":%d,"latency_us":%d,"ip":"%s","method":"%s","path":"%s","size":%d,"ua":"%s","user":%v}`+"\\n", p.TimeStamp.Format("15:04:05"), p.StatusCode, p.Latency.Microseconds(), p.ClientIP, p.Method, p.Path, p.BodySize, p.Request.UserAgent(), p.Keys["user"])
		},
	}))
	r.GET("/health", func(c *gin.Context) { c.String(200, "ok") })
	r.GET("/quiet/a", func(c *gin.Context) { c.String(200, "ok") })
	r.GET("/quiet/missing", func(c *gin.Context) { c.Status(404) })
	r.GET("/api", func(c *gin.Context) { c.Set("user", "alice"); c.String(200, "hello") })
	for _, u := range []string{"/health", "/quiet/a", "/quiet/missing", "/api?token=SECRET&x=1"} {
		rq := httptest.NewRequest("GET", u, nil); rq.Header.Set("User-Agent", "curl/8"); r.ServeHTTP(httptest.NewRecorder(), rq)
	}
	fmt.Println("  共 4 个请求,日志行数:", strings.Count(buf.String(), "\\n")); lines(&buf)
}''')
out_lines(r)
print('== 五:panic 时有没有日志:取决于 Logger 与 Recovery 的相对顺序')
r = gin('n41e', PRE + '''
func main() {
	var buf bytes.Buffer
	var errbuf bytes.Buffer
	for _, c := range []struct{ name string; mws func(r *gin.Engine) }{
		{"Logger 在外、Recovery 在内(gin.Default 的顺序)", func(r *gin.Engine) { r.Use(gin.LoggerWithWriter(&buf), gin.RecoveryWithWriter(&errbuf)) }},
		{"Recovery 在外、Logger 在内", func(r *gin.Engine) { r.Use(gin.RecoveryWithWriter(&errbuf), gin.LoggerWithWriter(&buf)) }},
	} {
		r := gin.New(); c.mws(r); r.GET("/boom", func(c *gin.Context) { panic("boom") })
		w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest("GET", "/boom", nil))
		fmt.Printf("  %s → 响应状态 %d,访问日志 %d 行\\n", c.name, w.Code, strings.Count(buf.String(), "\\n")); lines(&buf); errbuf.Reset()
	}
}''')
out_lines(r)
print('== 六:Logger 的开销:空 handler,输出到 io.Discard,与没有 Logger 对比')
r = gin('n41f', PRE + '''
type nw struct{ h http.Header }
func (w *nw) Header() http.Header { if w.h == nil { w.h = http.Header{} }; return w.h }
func (w *nw) Write(b []byte) (int, error) { return len(b), nil }
func (w *nw) WriteHeader(int) {}
func main() {
	run := func(name string, r *gin.Engine) {
		req := httptest.NewRequest("GET", "/x", nil); var w nw; var xs, al []float64
		for i := 0; i < 7; i++ { br := testing.Benchmark(func(b *testing.B) { b.ReportAllocs(); for i := 0; i < b.N; i++ { r.ServeHTTP(&w, req) } }); xs = append(xs, float64(br.T.Nanoseconds())/float64(br.N)); al = append(al, float64(br.AllocsPerOp())) }
		sort.Float64s(xs); fmt.Printf("  %-34s 中位 %.0f ns/请求,%.0f allocs/请求\\n", name, xs[3], al[0])
	}
	for round := 1; round <= 2; round++ {
		fmt.Printf("  第 %d 轮\\n", round)
		a := gin.New(); a.GET("/x", func(c *gin.Context) {}); run("无 Logger", a)
		b := gin.New(); b.Use(gin.LoggerWithWriter(io.Discard)); b.GET("/x", func(c *gin.Context) {}); run("Logger(io.Discard)", b)
		c := gin.New(); c.Use(gin.LoggerWithConfig(gin.LoggerConfig{Output: io.Discard, Formatter: func(p gin.LogFormatterParams) string { return "" }})); c.GET("/x", func(c *gin.Context) {}); run("Logger(空 Formatter)", c)
	}
}''', timeout=300)
out_lines(r)
