import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n20')
PRE = '''package main
import ("bytes"; "fmt"; "io"; "net/http/httptest"; "strings"; "github.com/gin-gonic/gin"; "github.com/gin-gonic/gin/binding")
var _ = bytes.NewReader
var _ = io.ReadAll
var _ = strings.NewReader
var _ = binding.JSON
type P struct{ Name string `json:"name" xml:"name" yaml:"name"`; Age int `json:"age" xml:"age" yaml:"age"` }
func post(r *gin.Engine, body, ct string) string { req := httptest.NewRequest("POST", "/x", strings.NewReader(body)); req.Header.Set("Content-Type", ct); w := httptest.NewRecorder(); r.ServeHTTP(w, req); return fmt.Sprintf("%d %s", w.Code, strings.TrimSpace(w.Body.String())) }
'''
print('== 一:ShouldBindBodyWith 的源码:第一次读完整个 body 存进 c.Keys[BodyBytesKey],之后都从缓存解析')
gfunc('context.go', 'ShouldBindBodyWith')
gfind('context.go', r'BodyBytesKey = ', ctx=0)
print('== 二:同一个请求绑定两次:ShouldBindJSON 两次(第二次 EOF),ShouldBindBodyWith 两次、再换一种格式')
r = gin('n20a', PRE + '''
func main() {
	r := gin.New()
	r.POST("/x", func(c *gin.Context) {
		var a, b P
		e1 := c.ShouldBindJSON(&a); e2 := c.ShouldBindJSON(&b)
		c.String(200, "第 1 次 err=%v a=%+v | 第 2 次 err=%v b=%+v", e1, a, e2, b)
	})
	fmt.Println("  ShouldBindJSON x2:     ", post(r, `{"name":"ann","age":30}`, "application/json"))
	r2 := gin.New()
	r2.POST("/x", func(c *gin.Context) {
		var a, b P
		e1 := c.ShouldBindBodyWith(&a, binding.JSON); e2 := c.ShouldBindBodyWith(&b, binding.JSON)
		bs, _ := c.Get(gin.BodyBytesKey)
		c.String(200, "第 1 次 err=%v a=%+v | 第 2 次 err=%v b=%+v | 缓存了 %d 字节", e1, a, e2, b, len(bs.([]byte)))
	})
	fmt.Println("  ShouldBindBodyWith x2: ", post(r2, `{"name":"ann","age":30}`, "application/json"))
	r3 := gin.New()
	r3.POST("/x", func(c *gin.Context) {
		var a, b P
		e1 := c.ShouldBindBodyWith(&a, binding.JSON); e2 := c.ShouldBindBodyWith(&b, binding.YAML)
		c.String(200, "JSON err=%v a=%+v | YAML err=%v b=%+v", e1, a, e2, b)
	})
	fmt.Println("  JSON 再 YAML(同一份 body,{...} 也是合法 YAML):", post(r3, `{"name":"ann","age":30}`, "application/json"))
	r4 := gin.New()
	r4.POST("/x", func(c *gin.Context) {
		raw, e1 := c.GetRawData(); var a P; e2 := c.ShouldBindJSON(&a)
		c.String(200, "GetRawData 读到 %d 字节 err=%v;之后 ShouldBindJSON err=%v a=%+v", len(raw), e1, e2, a)
	})
	fmt.Println("  GetRawData 之后再绑定:  ", post(r4, `{"name":"ann","age":30}`, "application/json"))
}''')
out_lines(r)
print('== 三:中间件先读了 body(比如验签),handler 再绑定:不还原就是 EOF')
r = gin('n20b', PRE + '''
func main() {
	for _, restore := range []bool{false, true} {
		r := gin.New()
		r.Use(func(c *gin.Context) {
			b, _ := io.ReadAll(c.Request.Body)
			if restore { c.Request.Body = io.NopCloser(bytes.NewReader(b)) }
			c.Set("len", len(b)); c.Next()
		})
		r.POST("/x", func(c *gin.Context) { var a P; err := c.ShouldBindJSON(&a); n, _ := c.Get("len"); c.String(200, "中间件读到 %v 字节;handler 绑定 err=%v a=%+v", n, err, a) })
		fmt.Printf("  中间件还原 Body=%-5v: %s\\n", restore, post(r, `{"name":"ann","age":30}`, "application/json"))
	}
}''')
out_lines(r)
print('== 四:代价:1 MB 的 JSON 请求体,ShouldBindJSON(流式解码)与 ShouldBindBodyWith(先 ReadAll 再解码)的内存与耗时')
r = gin('n20c', """package main
import ("bytes"; "encoding/json"; "fmt"; "net/http/httptest"; "sort"; "testing"; "github.com/gin-gonic/gin"; "github.com/gin-gonic/gin/binding")
type Item struct{ ID int `json:"id"`; Name string `json:"name"`; Tags []string `json:"tags"` }
type Doc struct{ Items []Item `json:"items"` }
func main() {
	var d Doc
	for i := 0; i < 20000; i++ { d.Items = append(d.Items, Item{i, fmt.Sprintf("item-%d", i), []string{"a", "b", "c"}}) }
	body, _ := json.Marshal(d)
	fmt.Printf("  请求体 %d 字节(约 %.2f MB),20000 个对象\\n", len(body), float64(len(body))/1e6)
	gin.SetMode(gin.ReleaseMode)
	run := func(name string, f func(c *gin.Context, v *Doc) error) {
		var xs, bs []float64
		for round := 0; round < 7; round++ {
			br := testing.Benchmark(func(b *testing.B) {
				b.ReportAllocs()
				for i := 0; i < b.N; i++ {
					w := httptest.NewRecorder(); c, _ := gin.CreateTestContext(w)
					c.Request = httptest.NewRequest("POST", "/x", bytes.NewReader(body)); c.Request.Header.Set("Content-Type", "application/json")
					var v Doc; if err := f(c, &v); err != nil { b.Fatal(err) }
				}
			})
			xs = append(xs, float64(br.T.Nanoseconds())/float64(br.N)/1e6); bs = append(bs, float64(br.AllocedBytesPerOp())/1e6)
		}
		sort.Float64s(xs); sort.Float64s(bs)
		fmt.Printf("  %-34s 中位 %.2f ms/请求,%.2f MB/请求分配\\n", name, xs[3], bs[3])
	}
	for round := 1; round <= 2; round++ {
		fmt.Printf("  第 %d 轮\\n", round)
		run("ShouldBindJSON(流式)", func(c *gin.Context, v *Doc) error { return c.ShouldBindJSON(v) })
		run("ShouldBindBodyWith(JSON)", func(c *gin.Context, v *Doc) error { return c.ShouldBindBodyWith(v, binding.JSON) })
		run("ReadAll + json.Unmarshal(对照)", func(c *gin.Context, v *Doc) error { b := new(bytes.Buffer); b.ReadFrom(c.Request.Body); return json.Unmarshal(b.Bytes(), v) })
	}
}""", timeout=400)
out_lines(r)
