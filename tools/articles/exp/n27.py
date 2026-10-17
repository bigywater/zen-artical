import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n27')
PRE = '''package main
import ("encoding/json"; "errors"; "fmt"; "net/http/httptest"; "strings"; "github.com/gin-gonic/gin"; "github.com/go-playground/validator/v10")
var _ = json.Marshal
var _ = errors.New
func post(r *gin.Engine, body string) string {
	rq := httptest.NewRequest("POST", "/x", strings.NewReader(body)); rq.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder(); r.ServeHTTP(w, rq); return strings.TrimSpace(w.Body.String())
}
func fields(err error) string {
	if err == nil { return " nil(校验通过)" }
	var ve validator.ValidationErrors
	if !errors.As(err, &ve) { return fmt.Sprintf("(不是 ValidationErrors) %T: %v", err, err) }
	var sb strings.Builder
	for _, fe := range ve { fmt.Fprintf(&sb, "\\n      %-20s tag=%-10s param=%-12q kind=%-7s value=%v", fe.Namespace(), fe.Tag(), fe.Param(), fe.Kind(), fe.Value()) }
	return sb.String()
}
'''
print('== 一:Gin 的 validator 与 tag 名:binding.Validator.Engine() 就是 validator/v10,tag 名被设成 "binding"')
gsrcl('binding/default_validator.go', 88, 94)
print('== 二:一组常见规则 + 一份“全都不合格”的 JSON:逐项看 FieldError 的 Namespace / Tag / Param / Value')
r = gin('n27a', PRE + '''
type Req struct {
	Name     string   `json:"name" binding:"required,min=3,max=8"`
	Age      int      `json:"age" binding:"gte=18,lte=60"`
	Email    string   `json:"email" binding:"required,email"`
	Role     string   `json:"role" binding:"oneof=admin user guest"`
	Site     string   `json:"site" binding:"omitempty,url"`
	ID       string   `json:"id" binding:"uuid"`
	Tags     []string `json:"tags" binding:"min=1,max=3,dive,alpha"`
	Zip      string   `json:"zip" binding:"len=5,numeric"`
	Birth    string   `json:"birth" binding:"datetime=2006-01-02"`
	IP       string   `json:"ip" binding:"ip"`
	Pass     string   `json:"pass" binding:"required,min=6"`
	Confirm  string   `json:"confirm" binding:"eqfield=Pass"`
}
func main() {
	r := gin.New()
	r.POST("/x", func(c *gin.Context) { var q Req; err := c.ShouldBindJSON(&q); c.String(200, "err=%s", fields(err)) })
	fmt.Println(post(r, `{"name":"ab","age":17,"email":"not-an-email","role":"root","site":"ftp//x","id":"123","tags":["a","b1","c"],"zip":"12a45","birth":"2024-13-01","ip":"999.1.1.1","pass":"abc123","confirm":"abc124"}`))
	fmt.Println("  --- 同一份结构体,全都合格:")
	fmt.Println(post(r, `{"name":"alice","age":30,"email":"a@b.co","role":"user","id":"123e4567-e89b-12d3-a456-426614174000","tags":["a","b"],"zip":"12345","birth":"2024-02-29","ip":"10.0.0.1","pass":"abc123","confirm":"abc123"}`))
}''')
out_lines(r, n=70)
print('== 三:err.Error() 的原文(多项错误用换行连接),与类型不匹配的错误对比')
r = gin('n27b', PRE + '''
type Req struct {
	Name string `json:"name" binding:"required,min=3"`
	Age  int    `json:"age" binding:"gte=18"`
}
func main() {
	r := gin.New()
	r.POST("/x", func(c *gin.Context) { var q Req; err := c.ShouldBindJSON(&q); c.String(200, "%T\\n%v", err, err) })
	for _, b := range []string{`{"name":"ab","age":17}`, `{"name":"alice","age":"x"}`, `{"name":"alice",`, `[]`} { fmt.Printf("  body=%s →\\n%s\\n", b, indent(post(r, b))) }
}
func indent(s string) string { return "    " + strings.ReplaceAll(s, "\\n", "\\n    ") }''')
out_lines(r)
print('== 四:min / max 的含义随类型变:字符串数“字符数”(rune),数字比大小,切片/map 比元素个数;len 与 eq 同理')
r = gin('n27c', PRE + '''
type S struct{ V string `binding:"min=3"` }
type N struct{ V int `binding:"min=3"` }
type L struct{ V []int `binding:"min=3"` }
type M struct{ V map[string]int `binding:"min=3"` }
type F struct{ V float64 `binding:"min=3"` }
func main() {
	ok := func(err error) string { if err == nil { return "通过" }; return "不通过" }
	val := validator.New(); val.SetTagName("binding")
	fmt.Printf("  string \\"abc\\"(3 字节 3 字符)   min=3: %s\\n", ok(val.Struct(S{"abc"})))
	fmt.Printf("  string \\"你好\\"(6 字节 2 字符)    min=3: %s(按字符数,不是字节数)\\n", ok(val.Struct(S{"你好"})))
	fmt.Printf("  string \\"你好吗\\"(9 字节 3 字符)  min=3: %s\\n", ok(val.Struct(S{"你好吗"})))
	fmt.Printf("  int 2   min=3: %s;  int 3: %s;  int 100: %s(数字比大小)\\n", ok(val.Struct(N{2})), ok(val.Struct(N{3})), ok(val.Struct(N{100})))
	fmt.Printf("  float 2.9 min=3: %s;  float 3.0: %s\\n", ok(val.Struct(F{2.9})), ok(val.Struct(F{3})))
	fmt.Printf("  []int{1,2} min=3: %s;  []int{1,2,3}: %s(比元素个数)\\n", ok(val.Struct(L{[]int{1, 2}})), ok(val.Struct(L{[]int{1, 2, 3}})))
	fmt.Printf("  map 2 个键 min=3: %s;  3 个键: %s\\n", ok(val.Struct(M{map[string]int{"a": 1, "b": 2}})), ok(val.Struct(M{map[string]int{"a": 1, "b": 2, "c": 3}})))
}''')
out_lines(r)
print('== 五:嵌套结构体自动校验;切片里的元素要写 dive;顶层切片由 Gin 逐个校验')
r = gin('n27d', PRE.replace('"github.com/go-playground/validator/v10")', '"github.com/go-playground/validator/v10"; "github.com/gin-gonic/gin/binding")') + '''
type Addr struct{ City string `json:"city" binding:"required"` }
type Item struct{ Sku string `json:"sku" binding:"required"` }
type Order struct {
	Addr    Addr    `json:"addr"`
	Ship    *Addr   `json:"ship"`
	Items   []Item  `json:"items"`
	Items2  []Item  `json:"items2" binding:"dive"`
	ByKey   map[string]Item `json:"by_key" binding:"dive"`
}
func main() {
	r := gin.New()
	r.POST("/x", func(c *gin.Context) { var q Order; err := c.ShouldBindJSON(&q); c.String(200, "err=%s", fields(err)) })
	fmt.Println(post(r, `{"addr":{},"ship":{},"items":[{}],"items2":[{}],"by_key":{"k":{}}}`))
	fmt.Println("  --- 顶层是切片:Gin 的 ValidateStruct 逐个校验元素")
	r.POST("/arr", func(c *gin.Context) { var q []Item; err := c.ShouldBindJSON(&q); c.String(200, "%T %v", err, strings.ReplaceAll(fmt.Sprint(err), "\\n", " | ")) })
	rq := httptest.NewRequest("POST", "/arr", strings.NewReader(`[{"sku":"a"},{},{"sku":""}]`)); rq.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder(); r.ServeHTTP(w, rq); fmt.Println("  " + w.Body.String())
	_ = binding.JSON
}''')
out_lines(r, n=60)
