import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n30')
PRE = '''package main
import ("encoding/json"; "fmt"; "net/http/httptest"; "strings"; "time"; "github.com/gin-gonic/gin")
var _ = json.Marshal
var _ = time.Now
func get(r *gin.Engine, url string) string { w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest("GET", url, nil)); return strings.TrimSpace(w.Body.String()) }
'''
print('== 一:time.Time 的 form 绑定:默认 RFC3339;time_format / time_utc / time_location / unix(进程时区设为 America/New_York 以便看出差别)')
r = gin('n30a', PRE + '''
type Q struct {
	Def   time.Time `form:"def"`
	Day   time.Time `form:"day" time_format:"2006-01-02"`
	DayU  time.Time `form:"dayu" time_format:"2006-01-02" time_utc:"1"`
	DayS  time.Time `form:"days" time_format:"2006-01-02" time_location:"Asia/Shanghai"`
	Unix  time.Time `form:"unix" time_format:"unix"`
	UnixM time.Time `form:"unixm" time_format:"unixmilli"`
}
func main() {
	r := gin.New()
	r.GET("/x", func(c *gin.Context) {
		var q Q; err := c.ShouldBindQuery(&q)
		p := func(n string, t time.Time) string { return fmt.Sprintf("    %-5s %s  (Location=%s)", n, t.Format(time.RFC3339), t.Location()) }
		c.String(200, "err=%v\\n%s\\n%s\\n%s\\n%s\\n%s\\n%s", err, p("Def", q.Def), p("Day", q.Day), p("DayU", q.DayU), p("DayS", q.DayS), p("Unix", q.Unix), p("UnixM", q.UnixM))
	})
	fmt.Println("  time.Local =", time.Local, ";请求 ?def=2024-05-01T10:00:00Z&day=2024-05-01&dayu=2024-05-01&days=2024-05-01&unix=1714557600&unixm=1714557600123")
	fmt.Println(get(r, "/x?def=2024-05-01T10:00:00Z&day=2024-05-01&dayu=2024-05-01&days=2024-05-01&unix=1714557600&unixm=1714557600123"))
}''', env=dict(TZ='America/New_York'))
out_lines(r)
print('== 二:time.Time 的各种错误与空值;JSON 里的 time.Time 只认 RFC3339')
r = gin('n30b', PRE + '''
type Q struct{ T time.Time `form:"t"`; D time.Time `form:"d" time_format:"2006-01-02"` }
type J struct{ T time.Time `json:"t"` }
func main() {
	r := gin.New()
	r.GET("/x", func(c *gin.Context) { var q Q; err := c.ShouldBindQuery(&q); c.String(200, "T=%v err=%v", q.T.IsZero(), err) })
	for _, u := range []string{"/x?t=2024-05-01", "/x?t=", "/x?t=2024-05-01T10:00:00%2B08:00", "/x?t=2024-05-01+10:00:00", "/x?d=2024-02-30", "/x?d=2024/05/01"} { fmt.Printf("  %-44s → %s\\n", u, get(r, u)) }
	r2 := gin.New()
	r2.POST("/j", func(c *gin.Context) { var q J; err := c.ShouldBindJSON(&q); c.String(200, "%s err=%v", q.T.Format(time.RFC3339), err) })
	for _, b := range []string{`{"t":"2024-05-01T10:00:00Z"}`, `{"t":"2024-05-01"}`, `{"t":1714557600}`, `{"t":null}`} {
		w := httptest.NewRecorder(); rq := httptest.NewRequest("POST", "/j", strings.NewReader(b)); rq.Header.Set("Content-Type", "application/json"); r2.ServeHTTP(w, rq)
		fmt.Printf("  JSON %-34s → %s\\n", b, w.Body.String())
	}
}''', env=dict(TZ='UTC'))
out_lines(r)
print('== 三:切片:重复的键(multi)、collection_format、default、空值、固定长度数组')
r = gin('n30c', PRE + '''
type Q struct {
	Multi []int    `form:"multi"`
	Csv   []int    `form:"csv" collection_format:"csv"`
	Ssv   []string `form:"ssv" collection_format:"ssv"`
	Pipes []string `form:"pipes" collection_format:"pipes"`
	Def   []int    `form:"def,default=7;8;9"`
	Arr   [3]int   `form:"arr" collection_format:"csv"`
	Strs  []string `form:"strs"`
}
func main() {
	r := gin.New()
	r.GET("/x", func(c *gin.Context) { var q Q; err := c.ShouldBindQuery(&q); b, _ := json.Marshal(q); c.String(200, "%s err=%v", b, err) })
	for _, u := range []string{"/x?multi=1&multi=2&multi=3", "/x?multi=1,2,3", "/x?csv=1,2,3", "/x?csv=1&csv=2,3", "/x?ssv=a+b+c", "/x?pipes=a|b|c", "/x", "/x?def=1", "/x?arr=1,2,3", "/x?arr=1,2", "/x?multi=", "/x?strs=&strs=", "/x?strs=a,b"} {
		fmt.Printf("  %-34s → %s\\n", u, get(r, u))
	}
}''')
out_lines(r)
print('== 四:类型转换错误的原文:整数溢出、不是数字、bool、Duration;空值被当作 0 / false')
r = gin('n30d', PRE + '''
type Q struct { N int `form:"n"`; U uint8 `form:"u"`; B bool `form:"b"`; F float64 `form:"f"`; D time.Duration `form:"d"` }
func main() {
	r := gin.New()
	r.GET("/x", func(c *gin.Context) { var q Q; err := c.ShouldBindQuery(&q); c.String(200, "%+v err=%v", q, err) })
	for _, u := range []string{"/x?n=12&u=200&b=true&f=1.5&d=1m30s", "/x?n=abc", "/x?n=99999999999999999999", "/x?u=256", "/x?u=-1", "/x?b=maybe", "/x?b=1&f=1e3", "/x?d=5+minutes", "/x?n=&b=&f=&d=", "/x?n=%2012%20"} {
		fmt.Printf("  %-34s → %s\\n", u, get(r, u))
	}
}''')
out_lines(r)
print('== 五:自定义类型:实现 UnmarshalParam(BindUnmarshaler);带 form 标签的 []struct 元素按 JSON 解码')
r = gin('n30e', PRE + '''
type Level int
func (l *Level) UnmarshalParam(s string) error {
	switch strings.ToLower(s) { case "low": *l = 1; case "mid": *l = 2; case "high": *l = 3; default: return fmt.Errorf("未知等级 %q", s) }
	return nil
}
type Item struct{ Sku string `json:"sku"`; N int `json:"n"` }
type Q struct {
	Lv  Level   `form:"lv"`
	Lvs []Level `form:"lvs"`
	Items []Item `form:"items"`
}
func main() {
	r := gin.New()
	r.GET("/x", func(c *gin.Context) { var q Q; err := c.ShouldBindQuery(&q); c.String(200, "%+v err=%v", q, err) })
	for _, u := range []string{"/x?lv=high", "/x?lv=ultra", "/x?lvs=low&lvs=high", `/x?items={"sku":"a","n":1}&items={"sku":"b","n":2}`, "/x?items=oops"} { fmt.Printf("  %-52s → %s\\n", u, get(r, u)) }
}''')
out_lines(r)
