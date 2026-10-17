import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n29')
PRE = '''package main
import ("encoding/json"; "errors"; "fmt"; "net/http/httptest"; "strings"; "time"; "github.com/gin-gonic/gin"; "github.com/go-playground/validator/v10")
var _ = json.Marshal
var _ = time.Now
func post(r *gin.Engine, body string) string {
	rq := httptest.NewRequest("POST", "/x", strings.NewReader(body)); rq.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder(); r.ServeHTTP(w, rq); return strings.TrimSpace(w.Body.String())
}
func fields(err error) string {
	if err == nil { return "通过" }
	var ve validator.ValidationErrors
	if !errors.As(err, &ve) { return fmt.Sprintf("%T: %v", err, err) }
	var out []string
	for _, fe := range ve { out = append(out, fe.Namespace()+"("+fe.Tag()+")") }
	return "不通过 " + strings.Join(out, " ")
}
'''
print('== 一:required 的判定(validator 源码 hasValue):指针/切片/map/接口看是不是 nil,其它类型看是不是零值')
r = gin('n29src', 'package main\nfunc main(){}\n')
import glob
vd = sorted(glob.glob(str(GT / '_gopath/pkg/mod/github.com/go-playground/validator/v10@*/baked_in.go')))[0]
L = open(vd).read().split('\n')
a = next(i for i, l in enumerate(L) if l.startswith('func hasValue('))
print('  validator v10.30.1 baked_in.go 的 hasValue:')
for i in range(a, a + 14): print(f'  {i + 1:>6} | {L[i].rstrip()}'.replace('\t', '    '))
print('== 二:同一个字段用 JSON 传“零值”与“不传”,required 的结果(值类型 vs 指针类型)')
r = gin('n29a', PRE + '''
type V struct {
	Age   int    `json:"age" binding:"required"`
	Name  string `json:"name" binding:"required"`
	Admin bool   `json:"admin" binding:"required"`
	Score float64 `json:"score" binding:"required"`
}
type P struct {
	Age   *int     `json:"age" binding:"required"`
	Name  *string  `json:"name" binding:"required"`
	Admin *bool    `json:"admin" binding:"required"`
	Score *float64 `json:"score" binding:"required"`
}
func main() {
	rv := gin.New(); rv.POST("/x", func(c *gin.Context) { var q V; err := c.ShouldBindJSON(&q); c.String(200, "%s", fields(err)) })
	rp := gin.New(); rp.POST("/x", func(c *gin.Context) { var q P; err := c.ShouldBindJSON(&q); c.String(200, "%s", fields(err)) })
	for _, b := range []string{`{"age":18,"name":"a","admin":true,"score":1.5}`, `{"age":0,"name":"","admin":false,"score":0}`, `{}`, `{"age":null,"name":null,"admin":null,"score":null}`} {
		fmt.Printf("  body=%-52s\\n    值类型字段:%s\\n    指针字段 :%s\\n", b, post(rv, b), post(rp, b))
	}
}''')
out_lines(r)
print('== 三:切片、map、字符串空白、时间、嵌套结构体的 required')
r = gin('n29b', PRE + '''
type In struct{ X int `json:"x" binding:"required"` }
type T struct {
	S   []int          `json:"s" binding:"required"`
	M   map[string]int `json:"m" binding:"required"`
	Str string         `json:"str" binding:"required"`
	At  time.Time      `json:"at" binding:"required"`
	In  In             `json:"in" binding:"required"`
	PIn *In            `json:"pin" binding:"required"`
}
func main() {
	r := gin.New(); r.POST("/x", func(c *gin.Context) { var q T; err := c.ShouldBindJSON(&q); c.String(200, "%s", fields(err)) })
	cases := []struct{ name, body string }{
		{"全部给出且非零", `{"s":[1],"m":{"a":1},"str":"x","at":"2024-01-01T00:00:00Z","in":{"x":1},"pin":{"x":1}}`},
		{"s:[] m:{} 空集合", `{"s":[],"m":{},"str":"x","at":"2024-01-01T00:00:00Z","in":{"x":1},"pin":{"x":1}}`},
		{"s、m 不传", `{"str":"x","at":"2024-01-01T00:00:00Z","in":{"x":1},"pin":{"x":1}}`},
		{"str:\\"   \\"(三个空格)", `{"s":[1],"m":{"a":1},"str":"   ","at":"2024-01-01T00:00:00Z","in":{"x":1},"pin":{"x":1}}`},
		{"at 为零时间 0001-01-01", `{"s":[1],"m":{"a":1},"str":"x","at":"0001-01-01T00:00:00Z","in":{"x":1},"pin":{"x":1}}`},
		{"at 不传", `{"s":[1],"m":{"a":1},"str":"x","in":{"x":1},"pin":{"x":1}}`},
		{"in:{}(嵌套结构体字段全零)", `{"s":[1],"m":{"a":1},"str":"x","at":"2024-01-01T00:00:00Z","in":{},"pin":{"x":1}}`},
		{"pin 不传", `{"s":[1],"m":{"a":1},"str":"x","at":"2024-01-01T00:00:00Z","in":{"x":1}}`},
		{"pin:{}", `{"s":[1],"m":{"a":1},"str":"x","at":"2024-01-01T00:00:00Z","in":{"x":1},"pin":{}}`},
	}
	for _, c := range cases { fmt.Printf("  %-26s → %s\\n", c.name, post(r, c.body)) }
}''')
out_lines(r)
print('== 四:表单与查询串:缺失的键和 age=0 的区别(form 绑定在“缺失”时不调用 setter,零值就是零值)')
r = gin('n29c', PRE + '''
type F struct {
	Age  int  `form:"age" binding:"required"`
	Page *int `form:"page" binding:"required"`
	Gt   int  `form:"gt" binding:"gt=0"`
	Opt  int  `form:"opt" binding:"omitempty,gt=0"`
}
func main() {
	r := gin.New(); r.GET("/x", func(c *gin.Context) { var q F; err := c.ShouldBindQuery(&q); pg := "nil"; if q.Page != nil { pg = fmt.Sprint(*q.Page) }; c.String(200, "%s q.Age=%d q.Page=%s", fields(err), q.Age, pg) })
	for _, u := range []string{"/x?age=5&page=2&gt=1", "/x?age=0&page=0&gt=0", "/x?age=&page=&gt=", "/x", "/x?age=5&page=2&gt=1&opt=0", "/x?age=5&page=2&gt=1&opt=-3"} {
		w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest("GET", u, nil)); fmt.Printf("  %-32s → %s\\n", u, w.Body.String())
	}
}''')
out_lines(r)
