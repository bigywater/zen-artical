import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n35')
PRE = '''package main
import ("encoding/json"; "fmt"; "net/http/httptest"; "strings"; "github.com/gin-gonic/gin")
var _ = json.Marshal
var _ = strings.TrimSpace
var payload = gin.H{"html": "<b>a&b</b>", "cn": "中文", "emoji": "😀", "sep": "x\\u2028y"}
func get(r *gin.Engine, url string) (*httptest.ResponseRecorder, string) { w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest("GET", url, nil)); return w, w.Body.String() }
'''
print('== 一:同一份数据(含 < > & 中文 emoji U+2028)用六种 JSON 渲染,看原始字节、Content-Type、结尾换行')
r = gin('n35a', PRE + '''
func main() {
	r := gin.New()
	r.GET("/json", func(c *gin.Context) { c.JSON(200, payload) })
	r.GET("/indent", func(c *gin.Context) { c.IndentedJSON(200, payload) })
	r.GET("/pure", func(c *gin.Context) { c.PureJSON(200, payload) })
	r.GET("/ascii", func(c *gin.Context) { c.AsciiJSON(200, payload) })
	r.GET("/secure", func(c *gin.Context) { c.SecureJSON(200, payload) })
	r.GET("/jsonp", func(c *gin.Context) { c.JSONP(200, payload) })
	for _, p := range []string{"/json", "/indent", "/pure", "/ascii", "/secure", "/jsonp?callback=cb"} {
		w, b := get(r, p)
		fmt.Printf("  %-18s Content-Type=%-34q 长度=%-3d 结尾换行=%v\\n    %q\\n", p, w.Header().Get("Content-Type"), len(b), strings.HasSuffix(b, "\\n"), b)
	}
}''')
out_lines(r, n=40)
print('== 二:各自的转义规则:HTML 字符、U+2028、非 ASCII;输出再用标准 JSON 解析器解析,和原值是否一致')
r = gin('n35b', PRE + """
func main() {
	r := gin.New()
	r.GET("/json", func(c *gin.Context) { c.JSON(200, payload) })
	r.GET("/pure", func(c *gin.Context) { c.PureJSON(200, payload) })
	r.GET("/ascii", func(c *gin.Context) { c.AsciiJSON(200, payload) })
	has := func(b, s string) bool { return strings.Contains(b, s) }
	for _, p := range []string{"/json", "/pure", "/ascii"} {
		_, b := get(r, p)
		var back map[string]string; err := json.Unmarshal([]byte(b), &back)
		fmt.Printf("  %-6s HTML 字符转义成 \\\\u003c:%-5v | 非 ASCII 原样保留:%-5v | 解析 err=%v | cn 往返一致:%v emoji 往返一致:%v\\n", p, has(b, "\\\\u003c"), has(b, "中文"), err, back["cn"] == "中文", back["emoji"] == "😀")
		if p == "/ascii" { k := strings.Index(b, "emoji"); fmt.Printf("    AsciiJSON 输出里 emoji 那一段:%s;标准解析器还原出的 emoji 是 %q(原值 %q)\\n", b[k-1:k+17], back["emoji"], "😀") }
	}
}""")
out_lines(r)
gsrcl('render/json.go', 155, 176, title='render/json.go 的 AsciiJSON 转义循环')
print('== 三:SecureJSON:只有“顶层是数组”时才加前缀 while(1);,对象不加;前缀可以改')
r = gin('n35c', PRE + '''
func main() {
	r := gin.New()
	r.GET("/obj", func(c *gin.Context) { c.SecureJSON(200, gin.H{"a": 1}) })
	r.GET("/arr", func(c *gin.Context) { c.SecureJSON(200, []int{1, 2}) })
	r.GET("/empty", func(c *gin.Context) { c.SecureJSON(200, []int{}) })
	r.GET("/nested", func(c *gin.Context) { c.SecureJSON(200, gin.H{"list": []int{1}}) })
	r.GET("/str", func(c *gin.Context) { c.SecureJSON(200, "[x]") })
	for _, p := range []string{"/obj", "/arr", "/empty", "/nested", "/str"} { _, b := get(r, p); fmt.Printf("  %-8s → %q\\n", p, b) }
	r.SecureJsonPrefix(")]}',\\n")
	_, b := get(r, "/arr"); fmt.Printf("  SecureJsonPrefix 之后 /arr → %q\\n", b)
}''')
out_lines(r)
print('== 四:JSONP:callback 只经过 JSEscapeString,圆括号、点号、分号都原样保留;没有 callback 就是普通 JSON')
r = gin('n35d', PRE + '''
func main() {
	r := gin.New()
	r.GET("/p", func(c *gin.Context) { c.JSONP(200, gin.H{"a": 1}) })
	for _, u := range []string{"/p", "/p?callback=cb", "/p?callback=app.handle", "/p?callback=a(1)%3Bb", "/p?callback=%3Cscript%3E", `/p?callback=x%27y%22z`} {
		w, b := get(r, u); fmt.Printf("  %-26s → Content-Type=%q %q\\n", u, w.Header().Get("Content-Type"), b)
	}
}''')
out_lines(r)
print('== 五:序列化失败时 c.JSON 会怎样:channel、NaN、循环引用;Render 的错误处理')
r = gin('n35e', PRE + '''
type Node struct{ Name string; Next *Node }
func main() {
	r := gin.New()
	r.GET("/ch", func(c *gin.Context) { c.JSON(200, gin.H{"c": make(chan int)}) })
	r.GET("/nan", func(c *gin.Context) { c.JSON(200, gin.H{"f": func() float64 { var z float64; return z / z }()}) })
	r.GET("/cycle", func(c *gin.Context) { n := &Node{Name: "a"}; n.Next = n; c.JSON(200, n) })
	r.GET("/ok", func(c *gin.Context) { c.JSON(200, gin.H{"a": 1}) })
	for _, p := range []string{"/ok", "/ch", "/nan"} {
		var errs int; var lastErr string
		r2 := gin.New(); r2.Use(func(c *gin.Context) { c.Next(); errs = len(c.Errors); if errs > 0 { lastErr = c.Errors[0].Error() } }); r2.GET("/ok", func(c *gin.Context) { c.JSON(200, gin.H{"a": 1}) })
		r2.GET("/ch", func(c *gin.Context) { c.JSON(200, gin.H{"c": make(chan int)}) })
		r2.GET("/nan", func(c *gin.Context) { c.JSON(200, gin.H{"f": func() float64 { var z float64; return z / z }()}) })
		w, b := get(r2, p); fmt.Printf("  %-5s → 状态 %d 正文 %q Content-Type=%q c.Errors=%d", p, w.Code, b, w.Header().Get("Content-Type"), errs)
		if errs > 0 { fmt.Printf("(第一条:%s)", lastErr) }
		fmt.Println()
	}
}''')
out_lines(r)
