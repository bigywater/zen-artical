import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n45')
PRE = '''package main
import ("encoding/base64"; "fmt"; "net/http/httptest"; "sort"; "strings"; "testing"; "github.com/gin-gonic/gin")
var _ = base64.StdEncoding
var _ = sort.Strings
var _ = strings.TrimSpace
var _ = testing.Benchmark
func call(r *gin.Engine, url string, hdr ...string) *httptest.ResponseRecorder {
	rq := httptest.NewRequest("GET", url, nil); for i := 0; i+1 < len(hdr); i += 2 { rq.Header.Set(hdr[i], hdr[i+1]) }
	w := httptest.NewRecorder(); r.ServeHTTP(w, rq); return w
}
func basic(u, p string) string { return "Basic " + base64.StdEncoding.EncodeToString([]byte(u+":"+p)) }
'''
print('== 一:BasicAuth 的源码:账号在注册时预先算成 "Basic base64(user:pass)" 字符串,请求时逐个常量时间比较')
gfunc('auth.go', 'processAccounts')
gfunc('auth.go', 'BasicAuthForRealm')
gfunc('auth.go', 'searchCredential')
print('== 二:基本行为:成功、失败、没有头、状态码与 WWW-Authenticate;c.MustGet(gin.AuthUserKey)')
r = gin('n45a', PRE + '''
func main() {
	r := gin.New()
	adm := r.Group("/admin", gin.BasicAuth(gin.Accounts{"alice": "s3cret", "bob": "p:w:d", "中文": "密码", "al": "pw"}))
	adm.GET("/me", func(c *gin.Context) { c.String(200, "hello %s", c.MustGet(gin.AuthUserKey)) })
	r.GET("/public", func(c *gin.Context) { c.String(200, "public") })
	for _, t := range []struct{ name, hdr string }{
		{"正确的 alice", basic("alice", "s3cret")},
		{"正确的 bob(密码里有冒号)", basic("bob", "p:w:d")},
		{"正确的 中文 / 密码", basic("中文", "密码")},
		{"alice 密码错", basic("alice", "wrong")},
		{"不存在的用户", basic("eve", "s3cret")},
		{"没有 Authorization 头", ""},
		{"小写 scheme: basic ...", "basic " + base64.StdEncoding.EncodeToString([]byte("alice:s3cret"))},
		{"scheme 后多一个空格", "Basic  " + base64.StdEncoding.EncodeToString([]byte("alice:s3cret"))},
		{"al:pw 的 base64 带 = 填充", basic("al", "pw")},
		{"al:pw 的 base64 去掉 = 填充", strings.TrimRight(basic("al", "pw"), "=")},
		{"Bearer 令牌", "Bearer abc"},
		{"空用户名 :s3cret", basic("", "s3cret")},
	} {
		var w *httptest.ResponseRecorder
		if t.hdr == "" { w = call(r, "/admin/me") } else { w = call(r, "/admin/me", "Authorization", t.hdr) }
		fmt.Printf("  %-26s → %d %-14q WWW-Authenticate=%q\\n", t.name, w.Code, w.Body.String(), w.Header().Get("WWW-Authenticate"))
	}
	w := call(r, "/admin/nothing"); fmt.Printf("  组内不存在的路径 /admin/nothing(不带凭据)→ %d %q WWW-Authenticate=%q(组中间件不管 404,见 Group 一篇)\\n", w.Code, w.Body.String(), w.Header().Get("WWW-Authenticate"))
	w = call(r, "/public"); fmt.Printf("  /public → %d\\n", w.Code)
}''')
out_lines(r)
print('== 三:realm、BasicAuthForProxy(407)与注册时的检查')
r = gin('n45b', PRE + '''
func main() {
	r := gin.New()
	r.GET("/a", gin.BasicAuthForRealm(gin.Accounts{"u": "p"}, "我的 \\"后台\\""), func(c *gin.Context) { c.String(200, "ok") })
	r.GET("/b", gin.BasicAuth(gin.Accounts{"u": "p"}), func(c *gin.Context) { c.String(200, "ok") })
	r.GET("/p", gin.BasicAuthForProxy(gin.Accounts{"u": "p"}, ""), func(c *gin.Context) { c.String(200, "ok %v", c.MustGet(gin.AuthProxyUserKey)) })
	w := call(r, "/a"); fmt.Printf("  自定义 realm → %d WWW-Authenticate=%s\\n", w.Code, w.Header().Get("WWW-Authenticate"))
	w = call(r, "/b"); fmt.Printf("  默认 realm   → %d WWW-Authenticate=%s\\n", w.Code, w.Header().Get("WWW-Authenticate"))
	w = call(r, "/p"); fmt.Printf("  BasicAuthForProxy 没有凭据 → %d Proxy-Authenticate=%q WWW-Authenticate=%q\\n", w.Code, w.Header().Get("Proxy-Authenticate"), w.Header().Get("WWW-Authenticate"))
	w = call(r, "/p", "Proxy-Authorization", basic("u", "p")); fmt.Printf("  BasicAuthForProxy 带 Proxy-Authorization → %d %q\\n", w.Code, w.Body.String())
	w = call(r, "/p", "Authorization", basic("u", "p")); fmt.Printf("  BasicAuthForProxy 带的是 Authorization → %d\\n", w.Code)
	func() { defer func() { fmt.Printf("  用户名为空的账号 → panic: %v\\n", recover()) }(); gin.BasicAuth(gin.Accounts{"": "p"}) }()
	func() { defer func() { fmt.Printf("  空 Accounts → recover=%v(不 panic,所有请求 401)\\n", recover()) }(); h := gin.BasicAuth(gin.Accounts{}); r := gin.New(); r.GET("/x", h); fmt.Printf("    空 Accounts 时 → %d\\n", call(r, "/x", "Authorization", basic("a", "b")).Code) }()
}''')
out_lines(r)
print('== 四:账号数量的代价:每个请求遍历所有账号逐个比较;ConstantTimeCompare 长度不同就立刻返回,长度相同才逐字节比较')
r = gin('n45c', PRE + """
func main() {
	for round := 1; round <= 2; round++ {
		fmt.Printf("  第 %d 轮\\n", round)
		for _, n := range []int{1, 10, 100, 1000} {
			acc := gin.Accounts{}; for i := 0; i < n; i++ { acc[fmt.Sprintf("user%04d", i)] = fmt.Sprintf("password-%04d", i) }
			r := gin.New(); r.GET("/x", gin.BasicAuth(acc), func(c *gin.Context) {})
			bench := func(h string) float64 {
				var xs []float64
				for i := 0; i < 5; i++ { br := testing.Benchmark(func(b *testing.B) { rq := httptest.NewRequest("GET", "/x", nil); rq.Header.Set("Authorization", h); for i := 0; i < b.N; i++ { r.ServeHTTP(httptest.NewRecorder(), rq) } }); xs = append(xs, float64(br.T.Nanoseconds())/float64(br.N)) }
				sort.Float64s(xs); return xs[2]
			}
			fmt.Printf("    %4d 个账号:错误凭据(长度不同)%5.0f ns;错误凭据(长度相同:userXXXX:password-0000)%5.0f ns\\n", n, bench(basic("nobody", "x")), bench(basic("userXXXX", "password-0000")))
		}
	}
}""", timeout=500)
out_lines(r)
