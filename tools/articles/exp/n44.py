import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n44')
PRE = '''package main
import ("fmt"; "net/http/httptest"; "strings"; "github.com/gin-gonic/gin")
var _ = strings.TrimSpace
func ip(r *gin.Engine, remote string, hdr ...string) string {
	rq := httptest.NewRequest("GET", "/ip", nil); rq.RemoteAddr = remote
	for i := 0; i+1 < len(hdr); i += 2 { rq.Header.Add(hdr[i], hdr[i+1]) }
	w := httptest.NewRecorder(); r.ServeHTTP(w, rq); return w.Body.String()
}
func eng(setup func(r *gin.Engine)) *gin.Engine { r := gin.New(); if setup != nil { setup(r) }; r.GET("/ip", func(c *gin.Context) { c.String(200, "%s", c.ClientIP()) }); return r }
'''
print('== 一:ClientIP 的源码骨架(信任平台头 → unix socket → 远端是否受信任代理 → 从头里取)与 validateHeader')
gsrcl('context.go', 975, 1024, title='context.go 的 ClientIP')
gfunc('gin.go', 'validateHeader')
print('== 二:默认配置(信任所有代理):任何客户端都能伪造 X-Forwarded-For')
r = gin('n44a', PRE + '''
func main() {
	r := eng(nil)
	fmt.Println("  默认值:RemoteIPHeaders =", r.RemoteIPHeaders, " ForwardedByClientIP =", r.ForwardedByClientIP)
	cases := []struct{ name, remote string; h []string }{
		{"直连,没有头", "203.0.113.9:5000", nil},
		{"直连,自己伪造 XFF: 1.2.3.4", "203.0.113.9:5000", []string{"X-Forwarded-For", "1.2.3.4"}},
		{"直连,XFF: 1.1.1.1, 2.2.2.2", "203.0.113.9:5000", []string{"X-Forwarded-For", "1.1.1.1, 2.2.2.2"}},
		{"直连,只有 X-Real-IP: 5.5.5.5", "203.0.113.9:5000", []string{"X-Real-IP", "5.5.5.5"}},
		{"XFF 与 X-Real-IP 都有", "203.0.113.9:5000", []string{"X-Forwarded-For", "1.1.1.1", "X-Real-IP", "5.5.5.5"}},
		{"XFF 不是 IP(unknown)+ X-Real-IP", "203.0.113.9:5000", []string{"X-Forwarded-For", "unknown", "X-Real-IP", "5.5.5.5"}},
		{"XFF 带端口 1.2.3.4:5555", "203.0.113.9:5000", []string{"X-Forwarded-For", "1.2.3.4:5555"}},
		{"两行 XFF 头", "203.0.113.9:5000", []string{"X-Forwarded-For", "1.1.1.1", "X-Forwarded-For", "2.2.2.2"}},
		{"IPv6 远端", "[2001:db8::1]:5000", nil},
	}
	for _, c := range cases { fmt.Printf("  %-34s RemoteAddr=%-20s → ClientIP=%s\\n", c.name, c.remote, ip(r, c.remote, c.h...)) }
}''')
out_lines(r)
print('== 三:SetTrustedProxies:只信任自己的反向代理(10.0.0.0/8)后:来自不受信任地址的头被忽略;从右往左跳过受信任的代理,取第一个不受信任的地址')
r = gin('n44b', PRE + '''
func main() {
	r := eng(func(r *gin.Engine) { if err := r.SetTrustedProxies([]string{"10.0.0.0/8", "172.16.1.7"}); err != nil { panic(err) } })
	cases := []struct{ name, remote string; h []string }{
		{"攻击者直连并伪造 XFF", "198.51.100.1:5000", []string{"X-Forwarded-For", "1.2.3.4"}},
		{"经受信任代理 10.0.0.5,代理追加了真实客户端", "10.0.0.5:5000", []string{"X-Forwarded-For", "203.0.113.7"}},
		{"攻击者伪造 + 代理追加:9.9.9.9, 203.0.113.7", "10.0.0.5:5000", []string{"X-Forwarded-For", "9.9.9.9, 203.0.113.7"}},
		{"多层代理:203.0.113.7, 10.0.0.9, 10.0.0.8", "10.0.0.5:5000", []string{"X-Forwarded-For", "203.0.113.7, 10.0.0.9, 10.0.0.8"}},
		{"全是受信任地址:10.1.1.1, 10.2.2.2", "10.0.0.5:5000", []string{"X-Forwarded-For", "10.1.1.1, 10.2.2.2"}},
		{"受信任的单个地址 172.16.1.7", "172.16.1.7:80", []string{"X-Forwarded-For", "203.0.113.7"}},
		{"172.16.1.8(同网段但没列出)", "172.16.1.8:80", []string{"X-Forwarded-For", "203.0.113.7"}},
		{"受信任代理 + 非法的 XFF 末项", "10.0.0.5:5000", []string{"X-Forwarded-For", "203.0.113.7, garbage"}},
	}
	for _, c := range cases { fmt.Printf("  %-46s RemoteAddr=%-20s → ClientIP=%s\\n", c.name, c.remote, ip(r, c.remote, c.h...)) }
	fmt.Println("  SetTrustedProxies 的错误:")
	for _, bad := range [][]string{{"10.0.0.0/33"}, {"not-an-ip"}, {"10.0.0.1", "bad"}} { err := gin.New().SetTrustedProxies(bad); fmt.Printf("    %v → %v\\n", bad, err) }
	r2 := eng(func(r *gin.Engine) { r.SetTrustedProxies(nil) })
	fmt.Printf("  SetTrustedProxies(nil)(不信任任何代理):%s\\n", ip(r2, "10.0.0.5:5000", "X-Forwarded-For", "1.2.3.4"))
}''')
out_lines(r)
print('== 四:RemoteIPHeaders 与 ForwardedByClientIP:改头名、关闭转发解析')
r = gin('n44c', PRE + '''
func main() {
	h := []string{"X-Forwarded-For", "1.1.1.1", "X-Real-IP", "5.5.5.5", "True-Client-IP", "7.7.7.7"}
	trust := func(r *gin.Engine) { r.SetTrustedProxies([]string{"10.0.0.0/8"}) }
	a := eng(func(r *gin.Engine) { trust(r); r.RemoteIPHeaders = []string{"X-Real-IP"} })
	b := eng(func(r *gin.Engine) { trust(r); r.RemoteIPHeaders = []string{"True-Client-IP", "X-Forwarded-For"} })
	c := eng(func(r *gin.Engine) { trust(r); r.ForwardedByClientIP = false })
	d := eng(func(r *gin.Engine) { trust(r); r.RemoteIPHeaders = nil })
	fmt.Printf("  RemoteIPHeaders=[X-Real-IP]                  → %s\\n", ip(a, "10.0.0.5:1", h...))
	fmt.Printf("  RemoteIPHeaders=[True-Client-IP, X-Forwarded-For] → %s\\n", ip(b, "10.0.0.5:1", h...))
	fmt.Printf("  ForwardedByClientIP=false                    → %s\\n", ip(c, "10.0.0.5:1", h...))
	fmt.Printf("  RemoteIPHeaders=nil                          → %s\\n", ip(d, "10.0.0.5:1", h...))
}''')
out_lines(r)
print('== 五:TrustedPlatform(如 Cloudflare 的 CF-Connecting-IP):头里的值原样返回,不检查来源、也不检查是不是 IP')
r = gin('n44d', PRE + '''
func main() {
	r := eng(func(r *gin.Engine) { r.TrustedPlatform = gin.PlatformCloudflare; r.SetTrustedProxies([]string{"10.0.0.0/8"}) })
	fmt.Printf("  来自不受信任的地址 198.51.100.1,CF-Connecting-IP: 8.8.8.8 → %s\\n", ip(r, "198.51.100.1:1", "CF-Connecting-IP", "8.8.8.8"))
	fmt.Printf("  CF-Connecting-IP: not-an-ip → %q\\n", ip(r, "198.51.100.1:1", "CF-Connecting-IP", "not-an-ip"))
	fmt.Printf("  CF-Connecting-IP: <script> → %q\\n", ip(r, "198.51.100.1:1", "CF-Connecting-IP", "<script>"))
	fmt.Printf("  没有这个头时回退到普通规则(受信任代理 + XFF)→ %s\\n", ip(r, "10.0.0.5:1", "X-Forwarded-For", "203.0.113.7"))
	fmt.Printf("  常量:Cloudflare=%q GoogleAppEngine=%q FlyIO=%q\\n", gin.PlatformCloudflare, gin.PlatformGoogleAppEngine, gin.PlatformFlyIO)
}''')
out_lines(r)
