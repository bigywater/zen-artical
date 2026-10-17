import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n31')
PRE = '''package main
import ("encoding/json"; "fmt"; "net/http/httptest"; "strings"; "github.com/gin-gonic/gin"; "github.com/gin-gonic/gin/binding")
var _ = json.Marshal
var _ = binding.JSON
func post(r *gin.Engine, body string) string {
	rq := httptest.NewRequest("POST", "/x", strings.NewReader(body)); rq.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder(); r.ServeHTTP(w, rq); return strings.TrimSpace(w.Body.String())
}
'''
print('== 一:Gin 的 JSON 绑定默认有多宽松(源码 decodeJSON + 实测)')
gfunc('binding/json.go', 'decodeJSON')
r = gin('n31a', PRE + '''
type P struct { Name string `json:"name"`; Age int `json:"age"` }
func main() {
	r := gin.New()
	r.POST("/x", func(c *gin.Context) { var p P; err := c.ShouldBindJSON(&p); c.String(200, "%+v err=%v", p, err) })
	for _, b := range []string{
		`{"name":"ann","age":30}`,
		`{"name":"ann","age":30,"extra":1,"nested":{"a":[1,2]}}`,
		`{"NAME":"ann","Age":30}`,
		`{"name":"a","name":"b"}`,
		`{"name":"ann","age":30} {"name":"second"}`,
		`{"name":"ann","age":30} garbage`,
		`{"name":"ann","age":30}}}}`,
		`{"name":"ann","age":30.0}`,
		`{"name":"ann","age":30.5}`,
		`{"name":"ann","age":"30"}`,
		`{"name":null,"age":null}`,
	} { fmt.Printf("  %-46s → %s\\n", b, post(r, b)) }
	var p P
	err := json.Unmarshal([]byte(`{"name":"ann","age":30} garbage`), &p)
	fmt.Printf("  对照 json.Unmarshal 同一个“带垃圾”的输入 → %+v err=%v\\n", p, err)
}''')
out_lines(r)
print('== 二:binding.EnableDecoderDisallowUnknownFields = true 之后:未知字段报错(含嵌套对象);这是个全局变量')
r = gin('n31b', PRE + '''
type In struct{ Z int `json:"z"` }
type P struct { Name string `json:"name"`; In In `json:"in"`; Items []In `json:"items"` }
func main() {
	binding.EnableDecoderDisallowUnknownFields = true
	r := gin.New()
	r.POST("/x", func(c *gin.Context) { var p P; err := c.ShouldBindJSON(&p); c.String(200, "%+v err=%v", p, err) })
	for _, b := range []string{`{"name":"ann"}`, `{"name":"ann","extra":1}`, `{"name":"ann","in":{"z":1,"y":2}}`, `{"items":[{"z":1},{"q":2}]}`, `{"NAME":"ann"}`, `{"name":"ann"} garbage`} { fmt.Printf("  %-44s → %s\\n", b, post(r, b)) }
}''')
out_lines(r)
print('== 三:binding.EnableDecoderUseNumber:interface{} / map 里的数字默认是 float64,大整数会丢精度;UseNumber 后是 json.Number')
r = gin('n31c', PRE + '''
type A struct { ID any `json:"id"`; M map[string]any `json:"m"`; I64 int64 `json:"i64"` }
func main() {
	body := `{"id":9007199254740993,"m":{"big":12345678901234567890,"f":1.10,"small":7},"i64":9007199254740993}`
	for _, use := range []bool{false, true} {
		binding.EnableDecoderUseNumber = use
		r := gin.New()
		r.POST("/x", func(c *gin.Context) {
			var a A; err := c.ShouldBindJSON(&a)
			c.String(200, "ID=%v(%T) m.big=%v(%T) m.f=%v m.small=%v(%T) I64=%d err=%v", a.ID, a.ID, a.M["big"], a.M["big"], a.M["f"], a.M["small"], a.M["small"], a.I64, err)
		})
		fmt.Printf("  UseNumber=%-5v → %s\\n", use, post(r, body))
	}
	fmt.Println("  对照:9007199254740993 的 float64 值 =", fmt.Sprintf("%.0f", float64(9007199254740993)))
}''')
out_lines(r)
print('== 四:全局开关的影响面:同一个进程里所有路由、所有绑定器(含 ShouldBindBodyWith)同时受影响;运行中切换会让同一路由前后行为不同')
r = gin('n31d', PRE + '''
type P struct { Name string `json:"name"` }
func main() {
	r := gin.New()
	r.POST("/a", func(c *gin.Context) { var p P; err := c.ShouldBindJSON(&p); c.String(200, "/a ShouldBindJSON err=%v", err) })
	r.POST("/b", func(c *gin.Context) { var p P; err := c.ShouldBindBodyWith(&p, binding.JSON); c.String(200, "/b ShouldBindBodyWith err=%v", err) })
	r.POST("/c", func(c *gin.Context) { var p P; err := c.ShouldBind(&p); c.String(200, "/c ShouldBind err=%v", err) })
	body := `{"name":"x","extra":1}`
	for _, on := range []bool{false, true, false} {
		binding.EnableDecoderDisallowUnknownFields = on
		fmt.Printf("  DisallowUnknownFields=%-5v:\\n", on)
		for _, p := range []string{"/a", "/b", "/c"} {
			rq := httptest.NewRequest("POST", p, strings.NewReader(body)); rq.Header.Set("Content-Type", "application/json"); w := httptest.NewRecorder(); r.ServeHTTP(w, rq)
			fmt.Printf("    %s\\n", w.Body.String())
		}
	}
	fmt.Println("  只想让某一个接口严格:自己用 json.NewDecoder + DisallowUnknownFields,不用全局开关:")
	r2 := gin.New()
	r2.POST("/strict", func(c *gin.Context) {
		var p P; dec := json.NewDecoder(c.Request.Body); dec.DisallowUnknownFields()
		if err := dec.Decode(&p); err != nil { c.String(400, "%v", err); return }
		c.String(200, "ok %+v", p)
	})
	rq := httptest.NewRequest("POST", "/strict", strings.NewReader(body)); w := httptest.NewRecorder(); r2.ServeHTTP(w, rq); fmt.Printf("    %d %s\\n", w.Code, w.Body.String())
}''')
out_lines(r)
