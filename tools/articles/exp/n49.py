import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n49')
APP = '''package main
import ("github.com/gin-gonic/gin")
func setup() *gin.Engine {
	r := gin.Default()
	r.Use(func(c *gin.Context) { c.Header("X-MW", "1"); c.Next() })
	r.GET("/users/:id", func(c *gin.Context) { c.JSON(200, gin.H{"id": c.Param("id"), "q": c.Query("q"), "full": c.FullPath(), "ip": c.ClientIP()}) })
	r.POST("/echo", func(c *gin.Context) { var v map[string]any; if err := c.ShouldBindJSON(&v); err != nil { c.JSON(400, gin.H{"error": err.Error()}); return }; c.JSON(201, v) })
	r.GET("/late", func(c *gin.Context) { c.String(200, "body"); c.Header("X-Late", "1") })
	return r
}
func getUser(c *gin.Context) { c.JSON(200, gin.H{"id": c.Param("id"), "path": c.Request.URL.Path}) }
func main() {}
'''
TEST = '''package main
import ("encoding/json"; "net/http"; "net/http/httptest"; "strings"; "testing"; "github.com/gin-gonic/gin")
func TestHTTPTest(t *testing.T) {
	r := setup()
	w := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/users/42?q=x", nil)
	r.ServeHTTP(w, req)
	var out map[string]any; json.Unmarshal(w.Body.Bytes(), &out)
	t.Logf("NewRecorder:状态 %d,Content-Type=%q,X-MW=%q,body=%v", w.Code, w.Header().Get("Content-Type"), w.Header().Get("X-MW"), out)
	t.Logf("httptest.NewRequest 的默认值:Host=%q RemoteAddr=%q Proto=%q", req.Host, req.RemoteAddr, req.Proto)
	w = httptest.NewRecorder()
	r.ServeHTTP(w, httptest.NewRequest("POST", "/echo", strings.NewReader(`{"a":1}`)))
	t.Logf("POST 没设 Content-Type:ShouldBindJSON 仍按 JSON 解码 → %d %s", w.Code, strings.TrimSpace(w.Body.String()))
	w = httptest.NewRecorder()
	r.ServeHTTP(w, httptest.NewRequest("POST", "/echo", strings.NewReader(`{bad`)))
	t.Logf("坏 JSON → %d %s", w.Code, strings.TrimSpace(w.Body.String()))
}
func TestCreateTestContext(t *testing.T) {
	w := httptest.NewRecorder()
	c, eng := gin.CreateTestContext(w)
	t.Logf("CreateTestContext:c.Request==nil %v;c.Params=%v;c.FullPath()=%q;eng 路由数 %d", c.Request == nil, c.Params, c.FullPath(), len(eng.Routes()))
	func() {
		defer func() { t.Logf("没设 Request 就调 getUser(c) → panic: %v", recover()) }()
		getUser(c)
	}()
	c.Request = httptest.NewRequest("GET", "/users/7", nil)
	getUser(c)
	t.Logf("设了 Request 但 c.Param(\\"id\\") 为空 → %s", strings.TrimSpace(w.Body.String()))
	w2 := httptest.NewRecorder(); c2, _ := gin.CreateTestContext(w2)
	c2.Request = httptest.NewRequest("GET", "/users/7", nil); c2.Params = gin.Params{{Key: "id", Value: "7"}}
	getUser(c2)
	t.Logf("手工设置 c.Params 之后 → %s(状态 %d)", strings.TrimSpace(w2.Body.String()), w2.Code)
	c3, _ := gin.CreateTestContext(httptest.NewRecorder())
	c3.Request = httptest.NewRequest("GET", "/x", nil)
	c3.Set("k", "v"); v, _ := c3.Get("k")
	t.Logf("c.Set / c.Get 可用:%v;c.Next() 无 handler,c.IsAborted()=%v;c.Writer.Status()=%d", v, c3.IsAborted(), c3.Writer.Status())
}
func TestRecorderVsReal(t *testing.T) {
	r := setup(); w := httptest.NewRecorder()
	r.ServeHTTP(w, httptest.NewRequest("GET", "/late", nil))
	t.Logf("写完 body 之后才设的头:w.Header()(活的 map)X-Late=%q;w.Result().Header(响应快照)X-Late=%q", w.Header().Get("X-Late"), w.Result().Header.Get("X-Late"))
	ts := httptest.NewServer(r); defer ts.Close()
	resp, _ := http.Get(ts.URL + "/late"); resp.Body.Close()
	t.Logf("真实服务器 + 真实客户端:X-Late=%q(这才是客户端会看到的)", resp.Header.Get("X-Late"))
}
func TestMode(t *testing.T) { t.Logf("go test 里 gin.Mode()=%q(setup 里的 gin.Default() 在 debug 下会打印上面的 [GIN-debug] 行)", gin.Mode()) }
'''
def run(name, files, pat, env=None):
    r = gtestn(name, files, args=('-v', '-count=1', '-run', pat), env=env or dict(GIN_MODE=''))
    for l in r['out'].split('\n'):
        if 'main_test.go' in l or l.startswith('ok') or l.startswith('FAIL') or 'GIN-debug' in l: print('  ' + l.strip()[:230])
FILES = {'app.go': APP, 'main_test.go': TEST}
print('== 一:httptest.NewRecorder + r.ServeHTTP:状态、头、JSON;httptest.NewRequest 的默认值;坏请求')
run('n49a', FILES, 'TestHTTPTest')
print('== 二:gin.CreateTestContext:没有路由、没有 Request、没有 Params,要自己补')
run('n49b', FILES, 'TestCreateTestContext')
print('== 三:记录器与真实服务器的差别:写完正文后才设的响应头')
run('n49c', FILES, 'TestRecorderVsReal')
print('== 四:go test 里的模式:默认是 debug(会输出 [GIN-debug] 行);TestMain 里 gin.SetMode(gin.TestMode) 之后安静')
run('n49d0', FILES, 'TestMode')
TEST2 = TEST.replace('func TestMode(', 'func TestMain(m *testing.M) { gin.SetMode(gin.TestMode); os.Exit(m.Run()) }\nfunc TestMode(').replace('import ("encoding/json";', 'import ("os"; "encoding/json";')
r = gtestn('n49d1', {'app.go': APP, 'main_test.go': TEST2}, args=('-v', '-count=1', '-run', 'TestMode'), env=dict(GIN_MODE=''))
print('  加了 TestMain + SetMode(TestMode) 之后,输出共', len([l for l in r['out'].split('\n') if l.strip()]), '行:')
for l in r['out'].split('\n'):
    if l.strip(): print('  | ' + l.strip()[:200])
print('== 五:一次请求的耗时:ServeHTTP + 记录器 vs 真实 HTTP(本机回环)')
r = gin('n49c', """package main
import ("fmt"; "io"; "net/http"; "net/http/httptest"; "sort"; "testing"; "github.com/gin-gonic/gin")
func main() {
	gin.SetMode(gin.ReleaseMode)
	r := gin.New(); r.GET("/ping", func(c *gin.Context) { c.JSON(200, gin.H{"msg": "pong"}) })
	med := func(f func(b *testing.B)) float64 { var xs []float64; for i := 0; i < 5; i++ { br := testing.Benchmark(f); xs = append(xs, float64(br.T.Nanoseconds())/float64(br.N)) }; sort.Float64s(xs); return xs[2] }
	a := med(func(b *testing.B) { for i := 0; i < b.N; i++ { w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest("GET", "/ping", nil)) } })
	ts := httptest.NewServer(r); defer ts.Close(); cl := &http.Client{}
	bb := med(func(b *testing.B) { for i := 0; i < b.N; i++ { resp, err := cl.Get(ts.URL + "/ping"); if err != nil { b.Fatal(err) }; io.Copy(io.Discard, resp.Body); resp.Body.Close() } })
	fmt.Printf("  NewRecorder + NewRequest + ServeHTTP:%.1f µs/次\\n  真实 HTTP(httptest.NewServer + http.Client,keep-alive):%.1f µs/次(约 %.0f 倍)\\n", a/1000, bb/1000, bb/a)
}""", timeout=300)
out_lines(r)
