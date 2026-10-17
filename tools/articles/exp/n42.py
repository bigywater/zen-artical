import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n42')
PRE = '''package main
import ("bytes"; "errors"; "fmt"; "io"; "net/http"; "net/http/httptest"; "regexp"; "strings"; "syscall"; "github.com/gin-gonic/gin")
var _ = errors.New
var _ = io.EOF
var _ = syscall.EPIPE
var _ = regexp.MustCompile
var _ = http.StatusOK
var hexRe = regexp.MustCompile(`\\(0x[0-9a-f]+\\)`)
func clean(s string) string { return hexRe.ReplaceAllString(s, "(0x…)") }
func do(r *gin.Engine, url string, hdr ...string) *httptest.ResponseRecorder {
	rq := httptest.NewRequest("GET", url, nil); for i := 0; i+1 < len(hdr); i += 2 { rq.Header.Set(hdr[i], hdr[i+1]) }
	w := httptest.NewRecorder(); r.ServeHTTP(w, rq); return w
}
func show(buf *bytes.Buffer, maxLines int) {
	ls := strings.Split(strings.TrimSpace(clean(buf.String())), "\\n"); n := len(ls)
	for i, l := range ls { if i < maxLines { fmt.Printf("    | %s\\n", strings.TrimRight(l, "\\r")) } }
	if n > maxLines { fmt.Printf("    | …(共 %d 行,其余是栈帧)\\n", n) }
	buf.Reset()
}
'''
print('== 一:Recovery 的源码骨架:defer + recover;断管类错误(EPIPE / ECONNRESET / http.ErrAbortHandler)单独处理')
gsrcl('recovery.go', 64, 100)
print('== 二:默认 Recovery:panic 之后客户端看到什么、日志里写了什么(release 模式)')
r = gin('n42a', PRE + '''
func main() {
	var buf bytes.Buffer
	r := gin.New(); r.Use(gin.RecoveryWithWriter(&buf))
	r.GET("/boom", func(c *gin.Context) { panic("boom 的细节") })
	r.GET("/ok", func(c *gin.Context) { c.String(200, "ok") })
	w := do(r, "/boom", "Authorization", "Bearer SECRET-TOKEN")
	fmt.Printf("  客户端:状态 %d,正文 %q,Content-Type=%q\\n  Recovery 写到日志的内容(release 模式):\\n", w.Code, w.Body.String(), w.Header().Get("Content-Type")); show(&buf, 9)
	w = do(r, "/ok"); fmt.Printf("  panic 之后同一个引擎继续服务:/ok → %d %q\\n", w.Code, w.Body.String())
}''')
out_lines(r, n=40)
print('== 三:debug 模式的日志多出一份请求转储,Authorization 头被打码')
r = gin('n42b', PRE + '''
func main() {
	var buf bytes.Buffer
	r := gin.New(); r.Use(gin.RecoveryWithWriter(&buf))
	r.GET("/boom", func(c *gin.Context) { panic("boom") })
	do(r, "/boom?x=1", "Authorization", "Bearer SECRET-TOKEN", "Cookie", "sid=abc", "X-Api-Key", "k-123")
	s := buf.String()
	fmt.Printf("  含 SECRET-TOKEN: %v;含 Authorization: *: %v;含 Cookie 内容 sid=abc: %v;含 X-Api-Key 内容 k-123: %v\\n", strings.Contains(s, "SECRET-TOKEN"), strings.Contains(s, "Authorization: *"), strings.Contains(s, "sid=abc"), strings.Contains(s, "k-123"))
	show(&buf, 12)
}''', env=dict(GIN_MODE='debug'))
out_lines(r, n=40)
print('== 四:各种 panic 值:字符串、error、结构体、nil(Go 1.21+)、运行时错误;handler 收到的 err 是什么')
r = gin('n42c', PRE + '''
type MyErr struct{ Code int }
func main() {
	var buf bytes.Buffer; var got []string
	r := gin.New()
	r.Use(gin.CustomRecoveryWithWriter(&buf, func(c *gin.Context, err any) { got = append(got, fmt.Sprintf("%T → %v", err, err)); c.AbortWithStatus(500) }))
	r.GET("/str", func(c *gin.Context) { panic("text") })
	r.GET("/err", func(c *gin.Context) { panic(errors.New("an error")) })
	r.GET("/struct", func(c *gin.Context) { panic(MyErr{42}) })
	r.GET("/nil", func(c *gin.Context) { panic(nil) })
	r.GET("/nilptr", func(c *gin.Context) { var m map[string]int; m["a"] = 1 })
	r.GET("/index", func(c *gin.Context) { s := []int{1}; i := 5; _ = s[i] })
	r.GET("/deref", func(c *gin.Context) { var p *MyErr; _ = p.Code })
	r.GET("/div", func(c *gin.Context) { z := 0; _ = 1 / z })
	for _, p := range []string{"/str", "/err", "/struct", "/nil", "/nilptr", "/index", "/deref", "/div"} { do(r, p) }
	for _, g := range got { fmt.Println("  收到 err:", g) }
}''')
out_lines(r)
print('== 五:自定义恢复:返回 JSON;如果 panic 之前已经写了响应,状态与正文改不了;http.ErrAbortHandler / EPIPE 走“断管”分支(不记栈、不调自定义函数)')
r = gin('n42d', PRE + '''
func main() {
	var buf bytes.Buffer; var called []string; var errN int
	r := gin.New()
	r.Use(func(c *gin.Context) { c.Next(); errN = len(c.Errors) })
	r.Use(gin.CustomRecoveryWithWriter(&buf, func(c *gin.Context, err any) { called = append(called, fmt.Sprint(err)); c.AbortWithStatusJSON(500, gin.H{"error": "内部错误", "id": "req-1"}) }))
	r.GET("/early", func(c *gin.Context) { panic("early") })
	r.GET("/late", func(c *gin.Context) { c.String(200, "已经写出的前半段"); c.Writer.Flush(); panic("late") })
	r.GET("/abort", func(c *gin.Context) { panic(http.ErrAbortHandler) })
	r.GET("/epipe", func(c *gin.Context) { panic(syscall.EPIPE) })
	r.GET("/wrapped", func(c *gin.Context) { panic(fmt.Errorf("write failed: %w", syscall.ECONNRESET)) })
	for _, p := range []string{"/early", "/late", "/abort", "/epipe", "/wrapped"} {
		buf.Reset(); w := do(r, p); s := clean(buf.String())
		has := strings.Contains(s, "goroutine") || strings.Contains(s, ".go:")
		fmt.Printf("  %-9s → 状态 %d 正文 %-44q 日志里有栈:%-5v 自定义函数累计调用:%d 次 c.Errors:%d 条\\n", p, w.Code, w.Body.String(), has, len(called), errN)
	}
}''')
out_lines(r)
