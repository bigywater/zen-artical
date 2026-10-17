import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n17')
print('== 一:Set / Get 的源码:RWMutex 保护 Keys;Keys 本身是个导出的普通 map')
gfunc('context.go', 'Set'); gfunc('context.go', 'Get')
gfind('context.go', r'Keys map\[any\]any|mu sync\.RWMutex', ctx=0)
print('== 二:50 个 goroutine 同时 c.Set / c.Get(用 -race 编译):没有任何竞态报告')
SAFE = """package main
import ("fmt"; "net/http"; "net/http/httptest"; "strconv"; "sync"; "io"; "github.com/gin-gonic/gin")
func main() {
	r := gin.New(); var n, miss int
	r.GET("/x", func(c *gin.Context) {
		var wg sync.WaitGroup; var mu sync.Mutex; m := 0
		for g := 0; g < 50; g++ {
			wg.Add(1)
			go func(g int) { defer wg.Done()
				for i := 0; i < 200; i++ { k := "k" + strconv.Itoa(g*1000+i); c.Set(k, i); if v, ok := c.Get(k); !ok || v.(int) != i { mu.Lock(); m++; mu.Unlock() } }
			}(g)
		}
		wg.Wait(); n = len(c.Keys); miss = m
		c.String(200, "ok")
	})
	ts := httptest.NewServer(r); defer ts.Close()
	resp, _ := http.Get(ts.URL + "/x"); io.Copy(io.Discard, resp.Body); resp.Body.Close()
	fmt.Printf("  50 个 goroutine 各 Set+Get 200 次后,Keys 里有 %d 个键(期望 10000),读回不一致 %d 次\\n", n, miss)
}"""
r = gin('n17a', SAFE, race=True, timeout=300)
if r['crc'] != 0: out_lines(r)
else:
    r2 = subprocess.run([r['bin']], cwd=r['d'], env=genv(GIN_MODE='release'), capture_output=True, text=True, timeout=120)
    t = tidy(r2.stdout + r2.stderr); print(t); print('  竞态检测器报告个数:', t.count('WARNING: DATA RACE'), ';退出码', r2.returncode)
print('== 三:绕过 Set,直接在多个 goroutine 里写 c.Keys[...](普通 map 并发写)')
UNSAFE = """package main
import ("fmt"; "net/http"; "net/http/httptest"; "strconv"; "sync"; "io"; "github.com/gin-gonic/gin")
func main() {
	r := gin.New()
	r.GET("/x", func(c *gin.Context) {
		c.Set("init", 1)
		var wg sync.WaitGroup
		for g := 0; g < 8; g++ {
			wg.Add(1)
			go func(g int) { defer wg.Done(); for i := 0; i < 100000; i++ { c.Keys["k"+strconv.Itoa(g*100000+i)] = i } }(g)
		}
		wg.Wait(); c.String(200, "ok")
	})
	ts := httptest.NewServer(r); defer ts.Close()
	resp, _ := http.Get(ts.URL + "/x"); io.Copy(io.Discard, resp.Body); resp.Body.Close()
	fmt.Println("  正常结束(没有崩溃)")
}"""
r = gin('n17b', UNSAFE)
if r['crc'] != 0: out_lines(r)
else:
    for k in range(3):
        r2 = subprocess.run([r['bin']], cwd=r['d'], env=genv(GIN_MODE='release'), capture_output=True, text=True, timeout=120)
        t = tidy(r2.stdout + r2.stderr).split('\n')
        print(f'  第 {k + 1} 次运行:退出码 {r2.returncode};第一行 {t[0][:90]!r}')
r = gin('n17c', UNSAFE, race=True, timeout=300)
if r['crc'] == 0:
    r2 = subprocess.run([r['bin']], cwd=r['d'], env=genv(GIN_MODE='release'), capture_output=True, text=True, timeout=120)
    t = tidy(r2.stdout + r2.stderr).split('\n')
    print('  -race 版本:退出码', r2.returncode, ';报告个数', sum(1 for l in t if 'WARNING: DATA RACE' in l), ';第一份报告里的两个访问:')
    for l in t[:16]:
        if l.strip().startswith(('Write at', 'Previous write', 'Read at', 'Previous read')) or 'main.main' in l: print('   ', l.strip()[:110])
print('== 四:Keys 在第一次 Set 之前是 nil:直接写 c.Keys["a"] 会 panic;读没问题')
r = gin('n17d', """package main
import ("fmt"; "net/http/httptest"; "github.com/gin-gonic/gin")
func main() {
	r := gin.New()
	r.GET("/x", func(c *gin.Context) {
		fmt.Printf("  进入时 c.Keys == nil: %v;读 c.Keys[\\"a\\"] = %v\\n", c.Keys == nil, c.Keys["a"])
		defer func() { fmt.Printf("  直接 c.Keys[\\"a\\"] = 1 → panic: %v\\n", recover()); c.Set("a", 1); fmt.Printf("  c.Set 之后 c.Keys == nil: %v,len=%d\\n", c.Keys == nil, len(c.Keys)) }()
		c.Keys["a"] = 1
	})
	r.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", "/x", nil))
	type K struct{ n int }
	r.GET("/y", func(c *gin.Context) { c.Set(K{1}, "结构体做键"); c.Set(42, "整数做键"); v1, _ := c.Get(K{1}); v2, _ := c.Get(42); fmt.Printf("  v1.12 的 Keys 是 map[any]any:%v / %v\\n", v1, v2) })
	r.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", "/y", nil))
}""")
out_lines(r)
print('== 五:互斥锁的开销:c.Set / c.Get 与直接操作 map 的对比(单 goroutine,无竞争)')
r = gin('n17e', """package main
import ("fmt"; "net/http/httptest"; "sort"; "testing"; "github.com/gin-gonic/gin")
func med(f func(b *testing.B)) float64 {
	var xs []float64
	for i := 0; i < 9; i++ { br := testing.Benchmark(f); xs = append(xs, float64(br.T.Nanoseconds())/float64(br.N)) }
	sort.Float64s(xs); return xs[4]
}
func main() {
	r := gin.New(); var cc *gin.Context
	r.GET("/x", func(c *gin.Context) { cc = c.Copy() })
	r.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", "/x", nil))
	c, _ := gin.CreateTestContext(httptest.NewRecorder()); c.Set("k", 1); _ = cc
	m := map[any]any{"k": 1}
	fmt.Printf("  c.Get(\\"k\\")            %.1f ns/op\\n", med(func(b *testing.B) { for i := 0; i < b.N; i++ { c.Get("k") } }))
	fmt.Printf("  map[any]any 直接读     %.1f ns/op\\n", med(func(b *testing.B) { for i := 0; i < b.N; i++ { _ = m["k"] } }))
	fmt.Printf("  c.Set(\\"k\\", i)         %.1f ns/op\\n", med(func(b *testing.B) { for i := 0; i < b.N; i++ { c.Set("k", i) } }))
	fmt.Printf("  map[any]any 直接写     %.1f ns/op\\n", med(func(b *testing.B) { for i := 0; i < b.N; i++ { m["k"] = i } }))
}""", timeout=300)
out_lines(r)
