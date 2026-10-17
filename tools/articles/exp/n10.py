import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n10')
print('== 一:methodTree 与按方法找树的源码')
gsrcl('tree.go', 45, 59, title='tree.go')
print('== 二:同一个路径,GET 与 POST 各自一棵树;第一次注册某方法才创建它的树')
r = gin('n10a', """package main
import ("fmt"; "github.com/gin-gonic/gin")
func main() {
	r := gin.New(); h := func(c *gin.Context) {}
	r.GET("/users/:id", h); r.POST("/users", h); r.GET("/users", h); r.POST("/users/:id/avatar", h); r.DELETE("/users/:id", h)
	fmt.Println("  trees 的顺序:", r.TreeMethods())
	for _, m := range r.TreeMethods() { fmt.Printf("  [%s]\\n%s", m, r.DumpTree(m)) }
}""", patched=True)
out_lines(r)
print('== 三:r.Any 一次注册多少个方法;Handle 对方法名的检查')
gfunc('routergroup.go', 'Any')
r = gin('n10b', """package main
import ("fmt"; "github.com/gin-gonic/gin")
func main() {
	r := gin.New(); h := func(c *gin.Context) {}
	r.Any("/any", h)
	fmt.Println("  Any 之后 trees:", r.TreeMethods(), "共", len(r.TreeMethods()), "棵")
	for _, m := range []string{"get", "M-SEARCH", "PURGE", "LINK", "", "G E T"} {
		func() {
			defer func() { if e := recover(); e != nil { fmt.Printf("  Handle(%q) → panic: %v\\n", m, e) } }()
			r2 := gin.New(); r2.Handle(m, "/x", h); fmt.Printf("  Handle(%q) → 注册成功,trees=%v\\n", m, r2.TreeMethods())
		}()
	}
}""", patched=True)
out_lines(r)
print('== 四:按方法找树是线性扫描 engine.trees:26 个自定义方法的树里,找第 1 棵与第 26 棵的耗时')
r = gin('n10c', """package main
import ("fmt"; "net/http"; "net/http/httptest"; "sort"; "testing"; "github.com/gin-gonic/gin")
type nw struct{ h http.Header }
func (w *nw) Header() http.Header { if w.h == nil { w.h = http.Header{} }; return w.h }
func (w *nw) Write(b []byte) (int, error) { return len(b), nil }
func (w *nw) WriteHeader(int) {}
func bench(name string, f func(b *testing.B)) {
	var xs []float64
	for i := 0; i < 9; i++ { br := testing.Benchmark(f); xs = append(xs, float64(br.T.Nanoseconds())/float64(br.N)) }
	sort.Float64s(xs)
	fmt.Printf("  %-38s 中位 %.1f ns/op(最小 %.1f / 最大 %.1f)\\n", name, xs[4], xs[0], xs[8])
}
func main() {
	r := gin.New(); h := func(c *gin.Context) {}
	var ms []string
	for ch := 'A'; ch <= 'Z'; ch++ { m := "X" + string(ch); ms = append(ms, m); r.Handle(m, "/x", h) }
	fmt.Println("  trees:", len(r.TreeMethods()), "棵,第 1 棵", ms[0], ",第 26 棵", ms[25])
	do := func(m string) func(b *testing.B) {
		req := httptest.NewRequest(m, "/x", nil); var w nw
		return func(b *testing.B) { for i := 0; i < b.N; i++ { r.ServeHTTP(&w, req) } }
	}
	for round := 1; round <= 2; round++ {
		fmt.Printf("  第 %d 轮\\n", round)
		bench("第 1 棵树的方法 "+ms[0], do(ms[0]))
		bench("第 13 棵树的方法 "+ms[12], do(ms[12]))
		bench("第 26 棵树的方法 "+ms[25], do(ms[25]))
	}
}""", patched=True, timeout=300)
out_lines(r)
