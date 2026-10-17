import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n32')
PRE = '''package main
import ("bytes"; "encoding/json"; "fmt"; "net/http/httptest"; "strings"; "github.com/gin-gonic/gin")
var _ = bytes.NewReader
var _ = json.Marshal
func post(r *gin.Engine, body string) string {
	rq := httptest.NewRequest("POST", "/x", strings.NewReader(body)); rq.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder(); r.ServeHTTP(w, rq); return strings.TrimSpace(w.Body.String())
}
func get(r *gin.Engine, url string) string { w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest("GET", url, nil)); return strings.TrimSpace(w.Body.String()) }
'''
print('== 一:缺失字段:保持绑定前的值(所以可以预填默认值);null 对非指针字段是空操作;多余字段被忽略')
r = gin('n32a', PRE + '''
type Req struct {
	Page int    `json:"page" form:"page"`
	Size int    `json:"size" form:"size"`
	Sort string `json:"sort" form:"sort"`
	Tag  *string `json:"tag" form:"tag"`
}
func main() {
	r := gin.New()
	dflt := func() Req { s := "预填标签"; return Req{Page: 1, Size: 20, Sort: "id", Tag: &s} }
	show := func(q Req) string { t := "nil"; if q.Tag != nil { t = *q.Tag }; return fmt.Sprintf("{Page:%d Size:%d Sort:%q Tag:%s}", q.Page, q.Size, q.Sort, t) }
	r.POST("/x", func(c *gin.Context) { q := dflt(); err := c.ShouldBindJSON(&q); c.String(200, "%s err=%v", show(q), err) })
	r.GET("/x", func(c *gin.Context) { q := dflt(); err := c.ShouldBindQuery(&q); c.String(200, "%s err=%v", show(q), err) })
	fmt.Println("  预填 Page=1 Size=20 Sort=id Tag=预填标签")
	for _, b := range []string{`{}`, `{"page":3}`, `{"page":0,"sort":""}`, `{"page":null,"size":null,"sort":null,"tag":null}`, `{"unknown":1}`} { fmt.Printf("  JSON %-52s → %s\\n", b, post(r, b)) }
	for _, u := range []string{"/x", "/x?page=3", "/x?page=0&sort=", "/x?page=&size="} { fmt.Printf("  查询 %-51s → %s\\n", u, get(r, u)) }
}''')
out_lines(r)
print('== 二:预填的复合值:map 会合并、切片被替换、嵌套结构体逐字段合并、非 nil 指针原地改写(encoding/json 的规则)')
r = gin('n32b', PRE + '''
type Sub struct{ A int `json:"a"`; B int `json:"b"` }
type Req struct {
	M   map[string]int `json:"m"`
	S   []int          `json:"s"`
	Arr [3]int         `json:"arr"`
	In  Sub            `json:"in"`
	P   *Sub           `json:"p"`
}
func main() {
	r := gin.New()
	var shared = &Sub{A: 100, B: 200}
	r.POST("/x", func(c *gin.Context) {
		q := Req{M: map[string]int{"keep": 1, "over": 2}, S: []int{9, 9, 9, 9}, Arr: [3]int{7, 7, 7}, In: Sub{A: 5, B: 6}, P: shared}
		err := c.ShouldBindJSON(&q)
		p := "nil"; if q.P != nil { p = fmt.Sprintf("%+v", *q.P) }
		c.String(200, "M=%v(nil:%v) S=%v(nil:%v) Arr=%v In=%+v P=%s 同一个 *Sub 被改写:%v err=%v", q.M, q.M == nil, q.S, q.S == nil, q.Arr, q.In, p, q.P == shared, err)
	})
	fmt.Println("  预填 M={keep:1 over:2} S=[9 9 9 9] Arr=[7 7 7] In={5 6} P=&{100 200}")
	for _, b := range []string{`{}`, `{"m":{"over":22,"new":3},"s":[1,2],"arr":[1],"in":{"a":50},"p":{"b":999}}`, `{"m":null,"s":null,"p":null}`} { fmt.Printf("  JSON %s\\n    → %s\\n", b, post(r, b)) }
}''')
out_lines(r)
print('== 三:出错时已经写进去的字段:类型错误不会中止解码(后面的字段照样赋值),只报第一个错误;语法错误则什么都不赋值(先整体校验语法)')
r = gin('n32c', PRE + '''
type Req struct { A int `json:"a"`; B string `json:"b"`; C int `json:"c"`; D []int `json:"d"` }
func main() {
	r := gin.New()
	r.POST("/x", func(c *gin.Context) { var q Req; err := c.ShouldBindJSON(&q); c.String(200, "%+v err=%v", q, err) })
	for _, b := range []string{`{"a":"x","b":"ok","c":3,"d":[1,2]}`, `{"a":1,"b":2,"c":3}`, `{"a":1,"b":"ok","c":"z","d":["q"]}`, `{"a":1,"b":"ok"; "c":3}`, `{"a":1,"b":"ok","c":3`} { fmt.Printf("  %-46s → %s\\n", b, post(r, b)) }
}''')
out_lines(r)
print('== 四:要区分“没传 / 传了 null / 传了零值”(PATCH 语义):三种办法对比')
r = gin('n32d', PRE + '''
type Opt[T any] struct{ Set bool; Null bool; Val T }
func (o *Opt[T]) UnmarshalJSON(b []byte) error { o.Set = true; if string(b) == "null" { o.Null = true; return nil }; return json.Unmarshal(b, &o.Val) }
func (o Opt[T]) String() string { switch { case !o.Set: return "没传"; case o.Null: return "null"; default: return fmt.Sprintf("值=%v", o.Val) } }
type Patch struct {
	Ptr  *int            `json:"ptr"`
	Raw  json.RawMessage `json:"raw"`
	Age  Opt[int]        `json:"age"`
	Name Opt[string]     `json:"name"`
}
func main() {
	r := gin.New()
	r.POST("/x", func(c *gin.Context) {
		var q Patch; err := c.ShouldBindJSON(&q)
		ptr := "nil"; if q.Ptr != nil { ptr = fmt.Sprint("&", *q.Ptr) }
		c.String(200, "Ptr=%s Raw=%q Age=%v Name=%v err=%v", ptr, string(q.Raw), q.Age, q.Name, err)
	})
	for _, b := range []string{`{}`, `{"ptr":null,"raw":null,"age":null,"name":null}`, `{"ptr":0,"raw":0,"age":0,"name":""}`, `{"ptr":5,"raw":{"x":1},"age":30,"name":"ann"}`} { fmt.Printf("  %-52s\\n    → %s\\n", b, post(r, b)) }
}''')
out_lines(r)
