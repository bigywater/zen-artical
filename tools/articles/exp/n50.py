import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n50')
PRE = '''package main
import ("fmt"; "math/rand"; "net/http"; "net/http/httptest"; "sort"; "strings"; "testing"; "github.com/gin-gonic/gin")
var _ = strings.TrimSpace
var _ = rand.Int
type nw struct{ h http.Header }
func (w *nw) Header() http.Header { if w.h == nil { w.h = http.Header{} }; return w.h }
func (w *nw) Write(b []byte) (int, error) { return len(b), nil }
func (w *nw) WriteHeader(int) {}
func med(f func(b *testing.B), rounds int) (float64, float64) {
	var xs []float64; var al float64
	for i := 0; i < rounds; i++ { br := testing.Benchmark(f); xs = append(xs, float64(br.T.Nanoseconds())/float64(br.N)); al = float64(br.AllocsPerOp()) }
	sort.Float64s(xs); return xs[len(xs)/2], al
}
'''
print('== 一:行为差异(同样的路由意图,Go 1.27.1 的 http.ServeMux 与 Gin v1.12.0):405、尾斜杠、通配符、大小写')
r = gin('n50a', PRE + '''
func main() {
	gin.SetMode(gin.ReleaseMode)
	mux := http.NewServeMux()
	mux.HandleFunc("GET /users/{id}", func(w http.ResponseWriter, r *http.Request) { fmt.Fprintf(w, "mux id=%s", r.PathValue("id")) })
	mux.HandleFunc("GET /files/{path...}", func(w http.ResponseWriter, r *http.Request) { fmt.Fprintf(w, "mux path=%s", r.PathValue("path")) })
	mux.HandleFunc("GET /dir/", func(w http.ResponseWriter, r *http.Request) { fmt.Fprint(w, "mux dir") })
	mux.HandleFunc("GET /users/new", func(w http.ResponseWriter, r *http.Request) { fmt.Fprint(w, "mux new") })
	g := gin.New()
	g.GET("/users/:id", func(c *gin.Context) { c.String(200, "gin id=%s", c.Param("id")) })
	g.GET("/files/*path", func(c *gin.Context) { c.String(200, "gin path=%s", c.Param("path")) })
	g.GET("/dir/", func(c *gin.Context) { c.String(200, "gin dir") })
	g.GET("/users/new", func(c *gin.Context) { c.String(200, "gin new") })
	do := func(h http.Handler, method, url string) string {
		w := httptest.NewRecorder(); h.ServeHTTP(w, httptest.NewRequest(method, url, nil))
		extra := ""; if a := w.Header().Get("Allow"); a != "" { extra += " Allow=" + a }; if l := w.Header().Get("Location"); l != "" { extra += " Location=" + l }
		return fmt.Sprintf("%d %q%s", w.Code, strings.TrimSpace(w.Body.String()), extra)
	}
	for _, c := range [][2]string{{"GET", "/users/42"}, {"GET", "/users/new"}, {"POST", "/users/42"}, {"GET", "/users/42/"}, {"GET", "/files/a/b.txt"}, {"GET", "/files/"}, {"GET", "/dir"}, {"GET", "/dir/x"}, {"GET", "/USERS/42"}, {"HEAD", "/users/42"}, {"GET", "/users//42"}, {"GET", "/nope"}} {
		fmt.Printf("  %-5s %-16s ServeMux → %-52s Gin → %s\\n", c[0], c[1], do(mux, c[0], c[1]), do(g, c[0], c[1]))
	}
}''')
out_lines(r)
print('== 二:路由数量 1 / 100 / 1000 / 10000 条时命中一条路由的耗时(随机 1024 个请求轮流;handler 为空;输出丢弃)')
r = gin('n50b', PRE + '''
func build(n int, param bool) (*http.ServeMux, *gin.Engine, []string) {
	mux := http.NewServeMux(); g := gin.New(); var reqs []string
	for i := 0; i < n; i++ {
		if param {
			mux.HandleFunc(fmt.Sprintf("GET /api/v1/resource%d/items/{id}", i), func(w http.ResponseWriter, r *http.Request) { _ = r.PathValue("id") })
			g.GET(fmt.Sprintf("/api/v1/resource%d/items/:id", i), func(c *gin.Context) { _ = c.Param("id") })
			reqs = append(reqs, fmt.Sprintf("/api/v1/resource%d/items/42", i))
		} else {
			mux.HandleFunc(fmt.Sprintf("GET /api/v1/resource%d/list", i), func(w http.ResponseWriter, r *http.Request) {})
			g.GET(fmt.Sprintf("/api/v1/resource%d/list", i), func(c *gin.Context) {})
			reqs = append(reqs, fmt.Sprintf("/api/v1/resource%d/list", i))
		}
	}
	return mux, g, reqs
}
func main() {
	gin.SetMode(gin.ReleaseMode)
	for _, param := range []bool{false, true} {
		kind := "静态路由"; if param { kind = "带 {id} / :id 的路由" }
		fmt.Printf("  [%s]\\n  %7s | %-22s | %-22s\\n", kind, "路由数", "http.ServeMux", "Gin")
		for _, n := range []int{1, 100, 1000, 10000} {
			mux, g, paths := build(n, param)
			rng := rand.New(rand.NewSource(1)); reqs := make([]*http.Request, 1024)
			for i := range reqs { reqs[i] = httptest.NewRequest("GET", paths[rng.Intn(len(paths))], nil) }
			var w nw
			a, aa := med(func(b *testing.B) { b.ReportAllocs(); for i := 0; i < b.N; i++ { mux.ServeHTTP(&w, reqs[i&1023]) } }, 5)
			c, ca := med(func(b *testing.B) { b.ReportAllocs(); for i := 0; i < b.N; i++ { g.ServeHTTP(&w, reqs[i&1023]) } }, 5)
			fmt.Printf("  %7d | %7.0f ns %2.0f allocs | %7.0f ns %2.0f allocs\\n", n, a, aa, c, ca)
		}
	}
}''', timeout=900)
out_lines(r, n=30)
print('== 三:加上一点真实的工作:同样写一个小 JSON({"id":"42"}),1 个参数路由;三种写法')
r = gin('n50c', PRE.replace('"fmt";', '"encoding/json"; "fmt";') + """
func main() {
	gin.SetMode(gin.ReleaseMode)
	mux := http.NewServeMux()
	mux.HandleFunc("GET /users/{id}", func(w http.ResponseWriter, r *http.Request) { w.Header().Set("Content-Type", "application/json"); json.NewEncoder(w).Encode(map[string]string{"id": r.PathValue("id")}) })
	g := gin.New()
	g.GET("/users/:id", func(c *gin.Context) { c.JSON(200, gin.H{"id": c.Param("id")}) })
	g.GET("/s/:id", func(c *gin.Context) { c.String(200, `{"id":%q}`, c.Param("id")) })
	m2 := http.NewServeMux()
	m2.HandleFunc("GET /s/{id}", func(w http.ResponseWriter, r *http.Request) { fmt.Fprintf(w, `{"id":%q}`, r.PathValue("id")) })
	var w nw; req := httptest.NewRequest("GET", "/users/42", nil); req2 := httptest.NewRequest("GET", "/s/42", nil)
	for round := 1; round <= 2; round++ {
		a, aa := med(func(b *testing.B) { b.ReportAllocs(); for i := 0; i < b.N; i++ { mux.ServeHTTP(&w, req) } }, 5)
		c, ca := med(func(b *testing.B) { b.ReportAllocs(); for i := 0; i < b.N; i++ { g.ServeHTTP(&w, req) } }, 5)
		d, da := med(func(b *testing.B) { b.ReportAllocs(); for i := 0; i < b.N; i++ { m2.ServeHTTP(&w, req2) } }, 5)
		e, ea := med(func(b *testing.B) { b.ReportAllocs(); for i := 0; i < b.N; i++ { g.ServeHTTP(&w, req2) } }, 5)
		fmt.Printf("  第 %d 轮:JSON:ServeMux(json.Encoder) %.0f ns %.0f allocs | Gin c.JSON(gin.H) %.0f ns %.0f allocs;字符串:ServeMux(Fprintf) %.0f ns %.0f allocs | Gin c.String %.0f ns %.0f allocs\\n", round, a, aa, c, ca, d, da, e, ea)
	}
}""", timeout=300)
out_lines(r)
