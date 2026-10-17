import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n16')
print('== 一:Copy 的源码:复制什么、清掉什么')
gfunc('context.go', 'Copy')
print('== 二:goroutine 里直接用 c(不 Copy):每个请求在 goroutine 里等 50ms 再读 c.Param("id"),连续串行发 200 个请求,统计读到别人的 id 的个数')
SRC = """package main
import ("fmt"; "net/http"; "net/http/httptest"; "os"; "runtime"; "strconv"; "sync"; "time"; "io"; "github.com/gin-gonic/gin")
func main() {
	N := 200
	if len(os.Args) > 1 { N, _ = strconv.Atoi(os.Args[1]) }
	var mu sync.Mutex; bad := map[string]int{}; total := map[string]int{}
	var wg sync.WaitGroup
	r := gin.New()
	r.GET("/raw/:id", func(c *gin.Context) {
		id := c.Param("id"); wg.Add(1)
		go func() { defer wg.Done(); time.Sleep(50 * time.Millisecond)
			got := c.Param("id"); mu.Lock(); total["raw"]++; if got != id { bad["raw"]++ }; mu.Unlock() }()
		c.String(200, "ok")
	})
	r.GET("/copy/:id", func(c *gin.Context) {
		id := c.Param("id"); cp := c.Copy(); wg.Add(1)
		go func() { defer wg.Done(); time.Sleep(50 * time.Millisecond)
			got := cp.Param("id"); mu.Lock(); total["copy"]++; if got != id { bad["copy"]++ }; mu.Unlock() }()
		c.String(200, "ok")
	})
	ts := httptest.NewServer(r); defer ts.Close()
	get := func(p string) { resp, err := http.Get(ts.URL + p); if err == nil { io.Copy(io.Discard, resp.Body); resp.Body.Close() } }
	for _, kind := range []string{"raw", "copy"} {
		for i := 0; i < N; i++ { get("/" + kind + "/id" + strconv.Itoa(i)) }
		wg.Wait()
	}
	fmt.Printf("  GOMAXPROCS=%d:不 Copy:%d 个 goroutine 里读到别的请求 id 的有 %d 个;c.Copy():%d 个里有 %d 个\\n", runtime.GOMAXPROCS(0), total["raw"], bad["raw"], total["copy"], bad["copy"])
}"""
r = gin('n16a', SRC)
for gmp in ['10', '4', '1']:
    r2 = subprocess.run([r['bin']], cwd=r['d'], env=genv(GIN_MODE='release', GOMAXPROCS=gmp), capture_output=True, text=True)
    print(tidy(r2.stdout + r2.stderr))
print('== 三:同一个程序用 -race 编译,Go 的竞态检测器怎么说(只发 20 个请求)')
r = gin('n16b', SRC, race=True, timeout=300)
if r['crc'] != 0: out_lines(r)
else:
    r2 = subprocess.run([r['bin'], '20'], cwd=r['d'], env=genv(GIN_MODE='release'), capture_output=True, text=True, timeout=120)
    t = tidy(r2.stdout + r2.stderr).split('\n')
    print('  检测到 "WARNING: DATA RACE" 共', sum(1 for l in t if 'WARNING: DATA RACE' in l), '处;退出码', r2.returncode)
    k = next(i for i, l in enumerate(t) if 'WARNING: DATA RACE' in l)
    for l in t[k:k + 9]: print('  ' + l[:150])
    fr = [l.strip() for l in t if 'gin.(*Context).' in l or 'gin.(*Engine).' in l]
    print('  报告里出现的 Gin 函数:', sorted(set(x.split('(')[0] + '(' + x.split('(')[1].split(')')[0] + ').' + x.split(').')[1].split('(')[0] for x in fr if ').' in x)))
print('== 四:Copy 出来的 Context 能做什么、不能做什么')
r = gin('n16c', """package main
import ("fmt"; "net/http"; "net/http/httptest"; "io"; "github.com/gin-gonic/gin")
func main() {
	var res []string
	r := gin.New()
	r.Use(func(c *gin.Context) { c.Set("user", "alice"); c.Next() })
	r.GET("/u/:id", func(c *gin.Context) {
		cp := c.Copy()
		u, _ := cp.Get("user"); c.Set("after", 1)
		_, has := cp.Get("after")
		res = append(res, fmt.Sprintf("Copy 之后原 Context 新增的 key 在副本里吗: %v;副本里 user=%v;副本 Param=%q FullPath=%q", has, u, cp.Param("id"), cp.FullPath()))
		res = append(res, fmt.Sprintf("副本 IsAborted=%v(index=abortIndex,Next 什么也不会执行)", cp.IsAborted()))
		cp.Next()
		func() {
			defer func() { res = append(res, fmt.Sprintf("在副本上写响应 cp.String(200, ...):panic=%v", recover())) }()
			cp.String(200, "x")
		}()
		c.String(200, "orig ok")
	})
	ts := httptest.NewServer(r); defer ts.Close()
	resp, _ := http.Get(ts.URL + "/u/7"); b, _ := io.ReadAll(resp.Body); resp.Body.Close()
	for _, s := range res { fmt.Println("  " + s) }
	fmt.Printf("  原请求的响应:%d %q\\n", resp.StatusCode, b)
}""")
out_lines(r)
print('== 五:请求结束后 Request.Context() 会被取消——Copy 不改变这一点')
r = gin('n16d', """package main
import ("fmt"; "net/http"; "net/http/httptest"; "io"; "sync"; "time"; "github.com/gin-gonic/gin")
func main() {
	var wg sync.WaitGroup; var out []string
	r := gin.New()
	r.GET("/x", func(c *gin.Context) {
		cp := c.Copy(); wg.Add(1)
		go func() { defer wg.Done()
			out = append(out, fmt.Sprintf("handler 刚返回时 cp.Request.Context().Err()=%v", cp.Request.Context().Err()))
			time.Sleep(150 * time.Millisecond)
			out = append(out, fmt.Sprintf("150ms 后 cp.Request.Context().Err()=%v", cp.Request.Context().Err()))
		}()
		c.String(200, "ok")
	})
	ts := httptest.NewServer(r); defer ts.Close()
	resp, _ := http.Get(ts.URL + "/x"); io.Copy(io.Discard, resp.Body); resp.Body.Close(); wg.Wait()
	for _, s := range out { fmt.Println("  " + s) }
}""")
out_lines(r)
