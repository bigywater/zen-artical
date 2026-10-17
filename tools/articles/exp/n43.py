import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n43')
print('== 一:代码里到底有哪几处判断了 IsDebugging():只有这几处(其余都是 debugPrint 的输出)')
gfind('debug.go', r'IsDebugging\(\)', ctx=0, maxn=6)
gfind('gin.go', r'IsDebugging\(\)', ctx=1, maxn=4)
gfind('recovery.go', r'IsDebugging\(\)', ctx=0, maxn=2)
gsrcl('mode.go', 58, 79, title='mode.go 的 SetMode')
print('== 二:同一个程序在 debug 与 release 下的标准输出:gin.Default() + 几条路由 + 一个 Group + 启动监听')
SRC = """package main
import ("fmt"; "net/http"; "os"; "time"; "io"; "github.com/gin-gonic/gin")
func main() {
	r := gin.Default()
	r.GET("/ping", func(c *gin.Context) { c.String(200, "pong") })
	r.POST("/users", func(c *gin.Context) {})
	g := r.Group("/api", func(c *gin.Context) {})
	g.GET("/items/:id", func(c *gin.Context) {})
	r.Static("/assets", ".")
	go r.Run("127.0.0.1:9731")
	for i := 0; i < 50; i++ { if resp, err := http.Get("http://127.0.0.1:9731/ping"); err == nil { io.Copy(io.Discard, resp.Body); resp.Body.Close(); break }; time.Sleep(50 * time.Millisecond) }
	fmt.Fprintln(os.Stderr, "(程序结束)")
}"""
for mode in ['debug', 'release']:
    r = gin('n43a_' + mode, SRC, env=dict(GIN_MODE=mode), timeout=60)
    ls = [l for l in r['out'].split('\n') if l.strip() and 'GIN] 20' not in l and '(程序结束)' not in l]
    gl = [l for l in r['out'].split('\n') if 'GIN] 20' in l]
    print(f'  [GIN_MODE={mode}] 共 {len(r["out"].splitlines())} 行输出(其中访问日志 {len(gl)} 行)')
    for l in ls: print('    ' + l)
print('== 三:模式是怎么选出来的:环境变量、SetMode、非法值、go test 里的默认值')
r = gin('n43b', """package main
import ("fmt"; "os"; "github.com/gin-gonic/gin")
func main() {
	fmt.Printf("  GIN_MODE=%q → 启动时 gin.Mode()=%q IsDebugging=%v\\n", os.Getenv("GIN_MODE"), gin.Mode(), gin.IsDebugging())
	gin.SetMode(gin.ReleaseMode); fmt.Printf("  SetMode(release) 之后 → %q IsDebugging=%v\\n", gin.Mode(), gin.IsDebugging())
	gin.SetMode(gin.TestMode); fmt.Printf("  SetMode(test) 之后 → %q IsDebugging=%v\\n", gin.Mode(), gin.IsDebugging())
	gin.SetMode(""); fmt.Printf("  SetMode(\\"\\")(空串)→ %q\\n", gin.Mode())
	defer func() { fmt.Printf("  SetMode(\\"prod\\") → panic: %v\\n", recover()) }()
	gin.SetMode("prod")
}""", env=dict(GIN_MODE='release'))
out_lines(r)
r = gin('n43c', """package main
import ("fmt"; "github.com/gin-gonic/gin")
func main() { fmt.Printf("  GIN_MODE 未设置 → gin.Mode()=%q\\n", gin.Mode()) }""", env=dict(GIN_MODE=''))
out_lines(r)
r = gtestn('n43d', {'x_test.go': 'package main\nimport ("testing"; "github.com/gin-gonic/gin")\nfunc TestMode(t *testing.T) { t.Logf("go test 里未设置 GIN_MODE → gin.Mode()=%q", gin.Mode()) }\n', 'main.go': 'package main\nfunc main(){}\n'}, args=('-v', '-run', 'TestMode'), env=dict(GIN_MODE=''))
print('\n'.join('  ' + l for l in r['out'].split('\n') if 'gin.Mode()' in l))
print('== 四:debug 才有的另外两个行为:每次重定向打印一行、路由注册打印一行(可以接管输出)')
r = gin('n43e', """package main
import ("bytes"; "fmt"; "net/http/httptest"; "strings"; "github.com/gin-gonic/gin")
func main() {
	var buf bytes.Buffer
	gin.DefaultWriter = &buf
	gin.DebugPrintRouteFunc = func(method, path, handler string, n int) { fmt.Fprintf(&buf, "ROUTE %s %s -> %s (%d)\\n", method, path, handler, n) }
	gin.SetMode(gin.DebugMode)
	r := gin.New(); r.GET("/dir/", func(c *gin.Context) {})
	r.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", "/dir", nil))
	fmt.Printf("  debug 模式:DefaultWriter 里收到:\\n"); for _, l := range strings.Split(strings.TrimSpace(buf.String()), "\\n") { if strings.TrimSpace(l) != "" { fmt.Printf("    %q\\n", l) } }
	buf.Reset(); gin.SetMode(gin.ReleaseMode)
	r2 := gin.New(); r2.GET("/dir/", func(c *gin.Context) {})
	r2.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", "/dir", nil))
	fmt.Printf("  release 模式:DefaultWriter 里收到 %d 字节\\n", buf.Len())
}""")
out_lines(r)
print('== 五:每个请求的开销:debug 与 release 在命中路由、尾斜杠重定向(debug 下每次多一行输出,这里输出到 io.Discard)时的耗时')
r = gin('n43f', """package main
import ("fmt"; "io"; "net/http"; "net/http/httptest"; "sort"; "testing"; "github.com/gin-gonic/gin")
type nw struct{ h http.Header }
func (w *nw) Header() http.Header { if w.h == nil { w.h = http.Header{} }; return w.h }
func (w *nw) Write(b []byte) (int, error) { return len(b), nil }
func (w *nw) WriteHeader(int) {}
func main() {
	gin.DefaultWriter = io.Discard
	for round := 1; round <= 2; round++ {
		fmt.Printf("  第 %d 轮\\n", round)
		for _, mode := range []string{gin.DebugMode, gin.ReleaseMode} {
			gin.SetMode(mode)
			r := gin.New(); r.GET("/ok", func(c *gin.Context) {}); r.GET("/dir/", func(c *gin.Context) {})
			for _, u := range []string{"/ok", "/dir"} {
				u := u; req := httptest.NewRequest("GET", u, nil); var w nw; var xs []float64
				for i := 0; i < 7; i++ { br := testing.Benchmark(func(b *testing.B) { for i := 0; i < b.N; i++ { req.URL.Path = u; r.ServeHTTP(&w, req) } }); xs = append(xs, float64(br.T.Nanoseconds())/float64(br.N)) }
				sort.Float64s(xs); fmt.Printf("    %-8s GET %-5s 中位 %.0f ns/请求\\n", mode, u, xs[3])
			}
		}
	}
}""", timeout=300)
out_lines(r)
