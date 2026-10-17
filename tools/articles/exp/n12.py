import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n12')
SRC = """package main
import ("fmt"; "math/rand"; "net/http"; "net/http/httptest"; "runtime"; "sort"; "strings"; "testing"; "time"; "github.com/gin-gonic/gin")
type nw struct{ h http.Header }
func (w *nw) Header() http.Header { if w.h == nil { w.h = http.Header{} }; return w.h }
func (w *nw) Write(b []byte) (int, error) { return len(b), nil }
func (w *nw) WriteHeader(int) {}
func heap() uint64 { runtime.GC(); runtime.GC(); var m runtime.MemStats; runtime.ReadMemStats(&m); return m.HeapAlloc }
func med(f func(b *testing.B), rounds int) float64 {
	var xs []float64
	for i := 0; i < rounds; i++ { br := testing.Benchmark(f); xs = append(xs, float64(br.T.Nanoseconds())/float64(br.N)) }
	sort.Float64s(xs); return xs[len(xs)/2]
}
func main() {
	h := func(c *gin.Context) {}
	for _, shape := range []string{"static", "param"} {
		fmt.Printf("  [%s 路由]\\n", shape)
		fmt.Printf("  %8s %10s %9s %10s %12s %12s\\n", "路由数", "注册耗时", "节点数", "堆增量", "命中 ns/op", "404 ns/op")
		for _, n := range []int{10, 100, 1000, 10000, 100000} {
			h0 := heap()
			r := gin.New()
			t0 := time.Now()
			var paths []string
			for i := 0; i < n; i++ {
				var reg, req string
				if shape == "static" { reg = fmt.Sprintf("/api/v1/resource%d/list", i); req = reg } else { reg = fmt.Sprintf("/svc%d/items/:id", i); req = fmt.Sprintf("/svc%d/items/42", i) }
				r.GET(reg, h); paths = append(paths, req)
			}
			reg := time.Since(t0)
			h1 := heap()
			nodes := strings.Count(r.DumpTree("GET"), "\\n")
			rng := rand.New(rand.NewSource(1)); reqs := make([]*http.Request, 1024)
			for i := range reqs { reqs[i] = httptest.NewRequest("GET", paths[rng.Intn(len(paths))], nil) }
			var w nw
			hit := med(func(b *testing.B) { for i := 0; i < b.N; i++ { r.ServeHTTP(&w, reqs[i&1023]) } }, 5)
			miss := httptest.NewRequest("GET", "/api/v1/nothing/list", nil)
			nf := med(func(b *testing.B) { for i := 0; i < b.N; i++ { r.ServeHTTP(&w, miss) } }, 5)
			fmt.Printf("  %8d %8.1f ms %9d %7.1f MB %12.1f %12.1f\\n", n, float64(reg.Microseconds())/1000, nodes, float64(h1-h0)/1e6, hit, nf)
			runtime.KeepAlive(r)
		}
	}
	// 对照:map[string]HandlerFunc 的静态精确匹配
	fmt.Println("  [对照:Go 的 map[string]func 精确匹配,只能匹配静态路径,不能取参数]")
	for _, n := range []int{10, 1000, 100000} {
		m := map[string]gin.HandlerFunc{}; var paths []string
		for i := 0; i < n; i++ { p := fmt.Sprintf("/api/v1/resource%d/list", i); m[p] = h; paths = append(paths, p) }
		rng := rand.New(rand.NewSource(1)); ps := make([]string, 1024)
		for i := range ps { ps[i] = paths[rng.Intn(len(paths))] }
		var sink gin.HandlerFunc
		ns := med(func(b *testing.B) { for i := 0; i < b.N; i++ { sink = m[ps[i&1023]] } }, 5); _ = sink
		fmt.Printf("  %8d 条 map 查找 %.1f ns/op\\n", n, ns)
	}
}
"""
print('== 一:路由数从 10 增加到 10 万:注册耗时、节点数、堆增量,以及随机命中一条路由和 404 的耗时')
r = gin('n12a', SRC, patched=True, timeout=900)
out_lines(r, n=60)

print('== 二:为什么命中耗时随路由数变大?同一棵 10 万条路由的树:树有多深,重复查同一条 vs 随机查 1024 条')
r = gin('n12b', """package main
import ("fmt"; "math/rand"; "net/http"; "net/http/httptest"; "sort"; "strings"; "testing"; "github.com/gin-gonic/gin")
type nw struct{ h http.Header }
func (w *nw) Header() http.Header { if w.h == nil { w.h = http.Header{} }; return w.h }
func (w *nw) Write(b []byte) (int, error) { return len(b), nil }
func (w *nw) WriteHeader(int) {}
func med(f func(b *testing.B), rounds int) float64 {
	var xs []float64
	for i := 0; i < rounds; i++ { br := testing.Benchmark(f); xs = append(xs, float64(br.T.Nanoseconds())/float64(br.N)) }
	sort.Float64s(xs); return xs[len(xs)/2]
}
func depthOf(dump, full string) int {
	for _, l := range strings.Split(dump, "\\n") { if strings.Contains(l, "full=\\"" + full + "\\"") { return (len(l) - len(strings.TrimLeft(l, " "))) / 2 + 1 } }
	return -1
}
func main() {
	h := func(c *gin.Context) {}
	for _, n := range []int{1000, 100000} {
		r := gin.New(); var paths []string
		for i := 0; i < n; i++ { p := fmt.Sprintf("/api/v1/resource%d/list", i); r.GET(p, h); paths = append(paths, p) }
		d := r.DumpTree("GET")
		maxd := 0
		for _, l := range strings.Split(d, "\\n") { if l != "" { if dd := (len(l)-len(strings.TrimLeft(l, " ")))/2 + 1; dd > maxd { maxd = dd } } }
		fmt.Printf("  %6d 条路由:树最深 %d 层;/api/v1/resource0/list 在第 %d 层,最后一条 %s 在第 %d 层\\n", n, maxd, depthOf(d, paths[0]), paths[n-1], depthOf(d, paths[n-1]))
		var w nw
		same := httptest.NewRequest("GET", paths[n/2], nil)
		rng := rand.New(rand.NewSource(1)); reqs := make([]*http.Request, 1024)
		for i := range reqs { reqs[i] = httptest.NewRequest("GET", paths[rng.Intn(n)], nil) }
		a := med(func(b *testing.B) { for i := 0; i < b.N; i++ { r.ServeHTTP(&w, same) } }, 5)
		b2 := med(func(b *testing.B) { for i := 0; i < b.N; i++ { r.ServeHTTP(&w, reqs[i&1023]) } }, 5)
		fmt.Printf("         重复查同一条:%.1f ns/op;随机查 1024 条轮流:%.1f ns/op\\n", a, b2)
	}
}
""", patched=True, timeout=600)
out_lines(r)
