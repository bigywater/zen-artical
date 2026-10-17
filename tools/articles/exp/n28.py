import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n28')
PRE = '''package main
import ("encoding/json"; "errors"; "fmt"; "net/http/httptest"; "reflect"; "strings"; "time"; "github.com/gin-gonic/gin"; "github.com/gin-gonic/gin/binding"; "github.com/go-playground/validator/v10")
var _ = binding.JSON
var _ = reflect.TypeOf
var _ = json.Marshal
var _ = errors.New
var _ = time.Now
func post(r *gin.Engine, path, body string) string {
	rq := httptest.NewRequest("POST", path, strings.NewReader(body)); rq.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder(); r.ServeHTTP(w, rq); return strings.TrimSpace(w.Body.String())
}
func fields(err error) string {
	if err == nil { return "nil(校验通过)" }
	var ve validator.ValidationErrors
	if !errors.As(err, &ve) { return fmt.Sprintf("%T: %v", err, err) }
	var out []string
	for _, fe := range ve { out = append(out, fmt.Sprintf("%s[tag=%s param=%q]", fe.Namespace(), fe.Tag(), fe.Param())) }
	return strings.Join(out, " ")
}
'''
print('== 一:拿到 validator 引擎并注册自定义规则:Engine() 返回 *validator.Validate')
r = gin('n28a', PRE + '''
type Req struct {
	Day   string    `json:"day" binding:"required,weekday"`
	Start time.Time `json:"start" binding:"required"`
	End   time.Time `json:"end" binding:"required,gtfield=Start"`
	Code  string    `json:"code" binding:"code8"`
}
func main() {
	v, ok := binding.Validator.Engine().(*validator.Validate)
	fmt.Printf("  binding.Validator.Engine() 的类型是 *validator.Validate: %v\\n", ok)
	v.RegisterValidation("weekday", func(fl validator.FieldLevel) bool {
		switch fl.Field().String() { case "mon", "tue", "wed", "thu", "fri": return true }
		return false
	})
	v.RegisterAlias("code8", "len=8,alphanum")
	r := gin.New()
	r.POST("/x", func(c *gin.Context) { var q Req; err := c.ShouldBindJSON(&q); c.String(200, "%s", fields(err)) })
	for _, b := range []string{
		`{"day":"mon","start":"2024-05-01T10:00:00Z","end":"2024-05-01T11:00:00Z","code":"ab12cd34"}`,
		`{"day":"sat","start":"2024-05-01T10:00:00Z","end":"2024-05-01T09:00:00Z","code":"short"}`,
	} { fmt.Println("  ", post(r, "/x", b)) }
}''')
out_lines(r)
print('== 二:带参数的规则与自定义类型;结构体级校验(跨字段);RegisterTagNameFunc 让错误里用 json 名')
r = gin('n28b', PRE + '''
type Range struct {
	Min int `json:"min" binding:"required"`
	Max int `json:"max" binding:"required"`
	Tag string `json:"tag" binding:"startswithx=ID-"`
}
type Range2 struct {
	Min int `json:"min" binding:"required"`
	Max int `json:"max" binding:"required"`
	Tag string `json:"tag" binding:"startswithx=ID-"`
}
func main() {
	v := binding.Validator.Engine().(*validator.Validate)
	v.RegisterValidation("startswithx", func(fl validator.FieldLevel) bool { return strings.HasPrefix(fl.Field().String(), fl.Param()) })
	v.RegisterStructValidation(func(sl validator.StructLevel) {
		r := sl.Current().Interface().(Range)
		if r.Min > r.Max { sl.ReportError(r.Max, "Max", "max", "gtefield_min", "") }
	}, Range{})
	r := gin.New()
	r.POST("/x", func(c *gin.Context) { var q Range; err := c.ShouldBindJSON(&q); c.String(200, "%s", fields(err)) })
	for _, b := range []string{`{"min":1,"max":5,"tag":"ID-1"}`, `{"min":9,"max":5,"tag":"X-1"}`} { fmt.Println("  ", post(r, "/x", b)) }
	v.RegisterTagNameFunc(func(f reflect.StructField) string { n := strings.SplitN(f.Tag.Get("json"), ",", 2)[0]; if n == "" || n == "-" { return f.Name }; return n })
	fmt.Println("  --- 之后才注册 RegisterTagNameFunc:已经校验过的类型 Range 的名字不变,第一次校验的新类型 Range2 用 json 名")
	r2 := gin.New()
	r2.POST("/x", func(c *gin.Context) { var q Range; err := c.ShouldBindJSON(&q); c.String(200, "Range  → %s", fields(err)) })
	r2.POST("/y", func(c *gin.Context) { var q Range2; err := c.ShouldBindJSON(&q); c.String(200, "Range2 → %s", fields(err)) })
	fmt.Println("  ", post(r2, "/x", `{"min":9,"max":5,"tag":"X-1"}`))
	fmt.Println("  ", post(r2, "/y", `{"min":9,"max":5,"tag":"X-1"}`))
}''')
out_lines(r)
print('== 三:用了没有注册的 tag:不是启动时报错,而是第一次校验时 panic')
r = gin('n28c', PRE + '''
type Req struct{ Name string `json:"name" binding:"required,nosuchrule"` }
func main() {
	r := gin.New(); r.Use(gin.CustomRecoveryWithWriter(nil, func(c *gin.Context, e any) { c.String(500, "panic: %v", e) }))
	fmt.Println("  路由注册完成、程序已启动,到这里没有任何报错")
	r.POST("/x", func(c *gin.Context) { var q Req; err := c.ShouldBindJSON(&q); c.String(200, "%v", err) })
	fmt.Println("  第一个请求 →", post(r, "/x", `{"name":"a"}`))
	fmt.Println("  第二个请求 →", post(r, "/x", `{"name":"b"}`))
}''')
out_lines(r)
print('== 四:整体换掉校验器:binding.Validator 是个接口变量(StructValidator)')
r = gin('n28d', PRE + '''
type myV struct{ calls int }
func (m *myV) ValidateStruct(obj any) error { m.calls++; return fmt.Errorf("自定义校验器第 %d 次被调用,拿到 %T", m.calls, obj) }
func (m *myV) Engine() any { return nil }
type Req struct{ Name string `json:"name" binding:"required"` }
func main() {
	mv := &myV{}; binding.Validator = mv
	r := gin.New()
	r.POST("/x", func(c *gin.Context) { var q Req; err := c.ShouldBindJSON(&q); c.String(200, "%v", err) })
	fmt.Println("  ", post(r, "/x", `{"name":"a"}`)); fmt.Println("  ", post(r, "/x", `{}`))
	binding.Validator = nil
	r2 := gin.New()
	r2.POST("/x", func(c *gin.Context) { var q Req; err := c.ShouldBindJSON(&q); c.String(200, "Validator=nil 时 err=%v q=%+v", err, q) })
	fmt.Println("  ", post(r2, "/x", `{}`))
}''')
out_lines(r)
