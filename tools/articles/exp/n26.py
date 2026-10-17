import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n26')
PRE = '''package main
import ("encoding/json"; "fmt"; "net/http/httptest"; "strings"; "github.com/gin-gonic/gin"; "github.com/gin-gonic/gin/binding")
var _ = json.Marshal
var _ = binding.JSON
func show(v any) string { b, _ := json.Marshal(v); return string(b) }
func req(r *gin.Engine, method, url, ct, body string, hdr ...string) string {
	rq := httptest.NewRequest(method, url, strings.NewReader(body)); if ct != "" { rq.Header.Set("Content-Type", ct) }
	for i := 0; i+1 < len(hdr); i += 2 { rq.Header.Set(hdr[i], hdr[i+1]) }
	w := httptest.NewRecorder(); r.ServeHTTP(w, rq); return strings.TrimSpace(w.Body.String())
}
'''
print('== 一:四种来源各自读哪个 tag(同一个结构体,同一个字段名,四个 tag 写成不同的名字)')
r = gin('n26a', PRE + '''
type P struct {
	N int `json:"j_n" form:"f_n" uri:"u_n" header:"X-H-N"`
}
func main() {
	r := gin.New()
	r.GET("/q/:u_n", func(c *gin.Context) {
		var a, b, d P
		e1 := c.ShouldBindQuery(&a); e2 := c.ShouldBindUri(&b); e3 := c.ShouldBindHeader(&d)
		c.String(200, "ShouldBindQuery → %s err=%v | ShouldBindUri → %s err=%v | ShouldBindHeader → %s err=%v", show(a), e1, show(b), e2, show(d), e3)
	})
	fmt.Println(" ", req(r, "GET", "/q/3?f_n=1&j_n=9&u_n=8&n=7&N=6", "", "", "X-H-N", "5", "N", "4"))
	r.POST("/j", func(c *gin.Context) { var a P; err := c.ShouldBindJSON(&a); c.String(200, "ShouldBindJSON → %s err=%v", show(a), err) })
	fmt.Println(" ", req(r, "POST", "/j", "application/json", `{"j_n":11,"f_n":12,"n":13,"N":14}`))
	fmt.Println(" ", req(r, "POST", "/j", "application/json", `{"J_N":15}`) + "   ← JSON 键不区分大小写(encoding/json)")
	r.POST("/f", func(c *gin.Context) { var a P; err := c.ShouldBind(&a); c.String(200, "ShouldBind(表单) → %s err=%v", show(a), err) })
	fmt.Println(" ", req(r, "POST", "/f", "application/x-www-form-urlencoded", "f_n=21&j_n=22&N=23"))
	fmt.Println(" ", req(r, "POST", "/f", "application/x-www-form-urlencoded", "F_N=24") + "   ← 表单键区分大小写")
}''')
out_lines(r)
print('== 二:没有 tag 时,key = 字段名本身(区分大小写,不会自动转小写);form:"-" 与未导出字段被忽略')
r = gin('n26b', PRE + '''
type Q struct {
	Name   string
	Age    int `form:"age"`
	Secret string `form:"-"`
	hidden string
	Page   int `form:"page,default=1"`
}
func main() {
	r := gin.New()
	r.GET("/x", func(c *gin.Context) { var q Q; err := c.ShouldBindQuery(&q); c.String(200, "%s err=%v hidden=%q", show(q), err, q.hidden) })
	for _, u := range []string{"/x?Name=Ann&age=30", "/x?name=Ann&age=30", "/x?NAME=Ann", "/x?Secret=s&hidden=h&age=1", "/x?Age=40&age=41"} { fmt.Printf("  %-34s → %s\\n", u, req(r, "GET", u, "", "")) }
}''')
out_lines(r)
print('== 三:ShouldBind 选哪个绑定器:只看方法和 Content-Type(binding.Default 的返回值)')
r = gin('n26c', """package main
import ("fmt"; "net/http"; "github.com/gin-gonic/gin/binding")
func main() {
	cts := []string{"", "application/json", "application/xml", "text/xml", "application/x-www-form-urlencoded", "multipart/form-data", "application/yaml", "application/toml", "application/x-protobuf", "text/plain"}
	fmt.Printf("  %-36s", "Content-Type \\\\ 方法")
	ms := []string{http.MethodGet, http.MethodPost, http.MethodPut, http.MethodDelete}
	for _, m := range ms { fmt.Printf(" %-14s", m) }
	fmt.Println()
	for _, ct := range cts {
		fmt.Printf("  %-36q", ct)
		for _, m := range ms { fmt.Printf(" %-14s", binding.Default(m, ct).Name()) }
		fmt.Println()
	}
}""")
out_lines(r)
print('== 四:ShouldBind 的实际后果:GET 带 JSON body 会被忽略;POST 不带 Content-Type 走表单;“application/json; charset=utf-8”会怎样')
r = gin('n26d', PRE + '''
type P struct { N int `json:"n" form:"n"` }
func main() {
	r := gin.New()
	r.Any("/x", func(c *gin.Context) { var a P; err := c.ShouldBind(&a); c.String(200, "绑定器=%s → %s err=%v", binding.Default(c.Request.Method, c.ContentType()).Name(), show(a), err) })
	fmt.Println("  GET  + JSON body {n:1}             :", req(r, "GET", "/x", "application/json", `{"n":1}`))
	fmt.Println("  GET  + 查询串 ?n=2                 :", req(r, "GET", "/x?n=2", "", ""))
	fmt.Println("  POST + JSON body {n:3}             :", req(r, "POST", "/x", "application/json", `{"n":3}`))
	fmt.Println("  POST + JSON body 但没有 Content-Type:", req(r, "POST", "/x", "", `{"n":4}`))
	fmt.Println("  POST + JSON body,charset=utf-8     :", req(r, "POST", "/x", "application/json; charset=utf-8", `{"n":5}`))
	fmt.Println("  POST + 表单 n=6 + 查询串 ?n=7       :", req(r, "POST", "/x?n=7", "application/x-www-form-urlencoded", "n=6"))
	fmt.Println("  POST + JSON body 且 URL 里有 ?n=8   :", req(r, "POST", "/x?n=8", "application/json", `{"n":9}`))
}''')
out_lines(r)
print('== 五:嵌套/嵌入结构体与指针字段:form 绑定的展开规则')
r = gin('n26e', PRE + '''
type Base struct { ID int `form:"id"` }
type Opt struct { Level int `form:"level"` }
type Q struct {
	Base
	Inner struct{ X int `form:"x"` }
	Opt *Opt
	P *int `form:"p"`
	Sub Opt `form:"sub"`
}
func main() {
	r := gin.New()
	r.GET("/x", func(c *gin.Context) { var q Q; err := c.ShouldBindQuery(&q); c.String(200, "%s Opt!=nil:%v P!=nil:%v err=%v", show(q), q.Opt != nil, q.P != nil, err) })
	for _, u := range []string{"/x?id=1&x=2&level=3&p=4&sub=%7B%22Level%22%3A5%7D", "/x?sub=5", "/x?id=1", "/x?level=3"} { fmt.Printf("  %-34s → %s\\n", u, req(r, "GET", u, "", "")) }
}''')
out_lines(r)
