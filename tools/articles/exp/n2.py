import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n2')
print('== 一:incrementChildPrio 的源码(每注册一条经过某子节点的路由,该子节点 priority+1 并向前冒泡)')
gsrcl('tree.go', 111, 135)
print('== 二:逐条注册路由,看根节点 indices 与 priority 的变化')
r = gin('n2a', '''package main
import ("fmt"; "strings"; "github.com/gin-gonic/gin")
func main() {
	r := gin.New(); h := func(c *gin.Context) {}
	for _, p := range []string{"/a/1", "/b/1", "/c/1", "/b/2", "/c/2", "/c/3", "/c/4", "/a/2", "/a/3", "/a/4", "/a/5"} {
		r.GET(p, h)
		first := strings.SplitN(r.DumpTree("GET"), "\\n", 2)[0]
		fmt.Printf("注册 %-6s → %s\\n", p, first)
	}
	fmt.Println("最终的树:"); fmt.Print(r.DumpTree("GET"))
}''', patched=True)
out_lines(r)
print('== 三:priority 是“子树里的路由条数”,不是访问次数:对 /z/hot 发 20 万次请求,树不会变')
r = gin('n2b', """package main
import ("fmt"; "net/http"; "net/http/httptest"; "strings"; "github.com/gin-gonic/gin")
func main() {
	r := gin.New(); h := func(c *gin.Context) {}
	for i := 0; i < 20; i++ { r.GET(fmt.Sprintf("/a/%d", i), h) }
	r.GET("/z/hot", h)
	before := r.DumpTree("GET")
	fmt.Println("请求前,根节点和它的两个孩子:"); for _, l := range strings.Split(before, "\\n") { if strings.HasPrefix(l, "\\"/\\"") || strings.HasPrefix(l, "  \\"a/\\"") || strings.HasPrefix(l, "  \\"z/") { fmt.Println("  " + l) } }
	req := httptest.NewRequest("GET", "/z/hot", nil)
	var w nw
	for i := 0; i < 200000; i++ { r.ServeHTTP(&w, req) }
	after := r.DumpTree("GET")
	fmt.Println("200000 次 GET /z/hot 之后整棵树(", strings.Count(after, "\\n"), "个节点)与之前逐字节相同:", after == before)
}
type nw struct{ h http.Header }
func (w *nw) Header() http.Header { if w.h == nil { w.h = http.Header{} }; return w.h }
func (w *nw) Write(b []byte) (int, error) { return len(b), nil }
func (w *nw) WriteHeader(int) {}
""", patched=True)
out_lines(r)
print('== 四:顺序对速度有多大影响?两棵形状相同的树:A 每个首字母 1 条路由(z 排在 indices 最后),B 的 z 组有 10 条(z 排第一),都查 /z/item0')
r = gin('n2c', """package main
import ("fmt"; "net/http"; "net/http/httptest"; "sort"; "strings"; "testing"; "github.com/gin-gonic/gin")
type nw struct{ h http.Header }
func (w *nw) Header() http.Header { if w.h == nil { w.h = http.Header{} }; return w.h }
func (w *nw) Write(b []byte) (int, error) { return len(b), nil }
func (w *nw) WriteHeader(int) {}
func bench(name string, f func(b *testing.B)) {
	var xs []float64
	for i := 0; i < 9; i++ { br := testing.Benchmark(f); xs = append(xs, float64(br.T.Nanoseconds())/float64(br.N)) }
	sort.Float64s(xs)
	fmt.Printf("  %-30s 中位 %.1f ns/op(最小 %.1f / 最大 %.1f)\\n", name, xs[4], xs[0], xs[8])
}
func build(zn int) *gin.Engine {
	r := gin.New(); h := func(c *gin.Context) {}
	for ch := 'a'; ch <= 'z'; ch++ {
		n := 1
		if ch == 'z' { n = zn }
		for i := 0; i < n; i++ { r.GET(fmt.Sprintf("/%c/item%d", ch, i), h) }
	}
	return r
}
func main() {
	A, B := build(1), build(10)
	root := func(r *gin.Engine) string { return strings.SplitN(r.DumpTree("GET"), "\\n", 2)[0] }
	fmt.Println("  树 A 的根:", root(A)); fmt.Println("  树 B 的根:", root(B))
	do := func(r *gin.Engine, path string) func(b *testing.B) {
		req := httptest.NewRequest("GET", path, nil); var w nw
		return func(b *testing.B) { for i := 0; i < b.N; i++ { r.ServeHTTP(&w, req) } }
	}
	for round := 1; round <= 2; round++ {
		fmt.Printf("  第 %d 轮\\n", round)
		bench("A: GET /z/item0(z 在第 26 位)", do(A, "/z/item0"))
		bench("B: GET /z/item0(z 在第 1 位)", do(B, "/z/item0"))
		bench("A: GET /a/item0(a 在第 1 位)", do(A, "/a/item0"))
		bench("B: GET /a/item0(a 在第 2 位)", do(B, "/a/item0"))
	}
}
""", patched=True, timeout=300)
out_lines(r)
