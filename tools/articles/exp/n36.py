import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n36')
PRE = '''package main
import ("fmt"; "net/http/httptest"; "strings"; "github.com/gin-gonic/gin"; "github.com/gin-gonic/gin/binding")
var _ = binding.JSON
var _ = strings.TrimSpace
func get(r *gin.Engine, url, accept string) (*httptest.ResponseRecorder, string) {
	rq := httptest.NewRequest("GET", url, nil); if accept != "<无>" { rq.Header.Set("Accept", accept) }
	w := httptest.NewRecorder(); r.ServeHTTP(w, rq); return w, strings.TrimSpace(w.Body.String())
}
'''
print('== 一:NegotiateFormat 与 parseAccept 的源码:q 值被直接丢掉,按 Accept 里出现的顺序匹配')
gfunc('utils.go', 'parseAccept')
gsrcl('context.go', 1394, 1422, title='context.go 的 NegotiateFormat')
print('== 二:NegotiateFormat(JSON, XML, HTML)对各种 Accept 头选了什么')
r = gin('n36a', PRE + '''
func main() {
	r := gin.New()
	r.GET("/x", func(c *gin.Context) { c.String(200, "%q", c.NegotiateFormat(gin.MIMEJSON, gin.MIMEXML, gin.MIMEHTML)) })
	for _, a := range []string{"<无>", "", "application/json", "application/xml", "text/html", "text/html,application/xml;q=0.9,*/*;q=0.8", "text/html;q=0.1, application/json;q=0.9", "application/json;q=0, text/html", "*/*", "application/*", "text/*", "image/png", "image/png, */*", "TEXT/HTML", "application/vnd.api+json", "application/json, text/html"} {
		_, b := get(r, "/x", a); fmt.Printf("  Accept: %-46q → %s\\n", a, b)
	}
}''')
out_lines(r)
print('== 三:c.Negotiate:按选出的格式渲染;没有可用格式时返回 406;Offered 与 Data / JSONData / XMLData 的选取')
r = gin('n36b', PRE + '''
type U struct{ Name string `json:"name" xml:"name" yaml:"name"`; Age int `json:"age" xml:"age" yaml:"age"` }
func main() {
	r := gin.New()
	r.GET("/u", func(c *gin.Context) {
		c.Negotiate(200, gin.Negotiate{Offered: []string{gin.MIMEJSON, gin.MIMEXML, gin.MIMEYAML}, Data: U{"ann", 30}})
	})
	r.GET("/data", func(c *gin.Context) {
		c.Negotiate(200, gin.Negotiate{Offered: []string{gin.MIMEJSON, gin.MIMEXML}, Data: "通用数据", JSONData: gin.H{"only": "给 JSON 的数据"}})
	})
	for _, a := range []string{"application/json", "application/xml", "application/x-yaml", "application/yaml", "text/html", "text/html,application/xml", "<无>", "*/*"} {
		w, b := get(r, "/u", a); fmt.Printf("  Accept: %-26q → %d Content-Type=%-34q %q\\n", a, w.Code, w.Header().Get("Content-Type"), b)
	}
	for _, a := range []string{"application/json", "application/xml"} { w, b := get(r, "/data", a); fmt.Printf("  /data Accept: %-18q → %d %q\\n", a, w.Code, b) }
}''')
out_lines(r)
print('== 四:406 的细节:Negotiate 没有匹配时调用 AbortWithStatus(406);写之前已有的头、c.Accepted 的缓存;没有 Offered 会 panic')
gsrcl('context.go', 1388, 1392, title='context.go 的 Negotiate 末尾')
r = gin('n36c', PRE + '''
func main() {
	r := gin.New()
	r.GET("/x", func(c *gin.Context) {
		c.Header("X-Before", "1")
		c.Negotiate(200, gin.Negotiate{Offered: []string{gin.MIMEJSON}, Data: gin.H{"a": 1}})
		c.Header("X-After", "1")
	})
	r.GET("/two", func(c *gin.Context) {
		a := c.NegotiateFormat(gin.MIMEJSON); b := c.NegotiateFormat(gin.MIMEXML)
		c.String(200, "第一次 %q;同一请求里再用另一组 Offered %q;c.Accepted=%v", a, b, c.Accepted)
	})
	r.GET("/none", func(c *gin.Context) { defer func() { c.String(200, "panic: %v", recover()) }(); c.NegotiateFormat() })
	w, b := get(r, "/x", "text/html"); fmt.Printf("  Accept: text/html → 状态 %d 正文 %q X-Before=%q Content-Type=%q\\n", w.Code, b, w.Header().Get("X-Before"), w.Header().Get("Content-Type"))
	_, b = get(r, "/two", "text/html, application/xml"); fmt.Println("  ", b)
	_, b = get(r, "/none", "*/*"); fmt.Println("  ", b)
}''')
out_lines(r)
