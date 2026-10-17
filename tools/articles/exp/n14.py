import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n14')
print('== 一:选哪个字符串去匹配路由(handleHTTPRequest 开头的源码)与三个开关的默认值')
gsrcl('gin.go', 690, 706, title='gin.go 的 handleHTTPRequest 开头')
r = gin('n14a', """package main
import ("fmt"; "net/url"; "github.com/gin-gonic/gin")
func main() {
	r := gin.New()
	fmt.Printf("  默认:UseRawPath=%v UseEscapedPath=%v UnescapePathValues=%v RemoveExtraSlash=%v\\n", r.UseRawPath, r.UseEscapedPath, r.UnescapePathValues, r.RemoveExtraSlash)
	for _, s := range []string{"/files/a%2Fb", "/files/a%20b", "/files/%E4%B8%AD", "/files/a+b", "/files/100%25", "/files/a%2fb", "/files/%7Euser", "/files/a%3Fb"} {
		u, _ := url.ParseRequestURI(s)
		fmt.Printf("  %-18s URL.Path=%-14q URL.RawPath=%-16q EscapedPath()=%q\\n", s, u.Path, u.RawPath, u.EscapedPath())
	}
}""")
out_lines(r)
print('== 二:四种开关组合下,/files/:name 取到的 name(404 表示没匹配上)')
r = gin('n14b', """package main
import ("fmt"; "net/http/httptest"; "github.com/gin-gonic/gin"; "strings")
func main() {
	type cfg struct{ name string; raw, esc, unesc bool }
	cfgs := []cfg{{"默认", false, false, true}, {"Raw=true Unescape=true", true, false, true}, {"Raw=true Unescape=false", true, false, false}, {"Escaped=true Unescape=true", false, true, true}, {"Escaped=true Unescape=false", false, true, false}}
	urls := []string{"/files/a%2Fb", "/files/a%20b", "/files/%E4%B8%AD", "/files/a+b", "/files/100%25", "/files/a%2Fb/c"}
	fmt.Printf("  %-30s", "")
	for _, u := range urls { fmt.Printf(" %-17s", strings.TrimPrefix(u, "/files/")) }
	fmt.Println()
	for _, c := range cfgs {
		r := gin.New(); r.UseRawPath, r.UseEscapedPath, r.UnescapePathValues = c.raw, c.esc, c.unesc
		r.GET("/files/:name", func(c *gin.Context) { c.String(200, "%s", c.Param("name")) })
		r.GET("/files/:name/c", func(c *gin.Context) { c.String(200, "%s|c", c.Param("name")) })
		fmt.Printf("  %-30s", c.name)
		for _, u := range urls {
			w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest("GET", u, nil))
			s := w.Body.String(); if w.Code != 200 { s = fmt.Sprint(w.Code) }
			fmt.Printf(" %-17q", s)
		}
		fmt.Println()
	}
}""")
out_lines(r)
print('== 三:RawPath 只在“默认编码和原样不同”时才有值——%20 和中文不受 UseRawPath 影响;通配符 *p 同理')
r = gin('n14c', """package main
import ("fmt"; "net/http/httptest"; "github.com/gin-gonic/gin")
func main() {
	for _, raw := range []bool{false, true} {
		r := gin.New(); r.UseRawPath = raw; r.UnescapePathValues = false
		r.GET("/s/*p", func(c *gin.Context) { c.String(200, "%q", c.Param("p")) })
		fmt.Printf("  UseRawPath=%v UnescapePathValues=false:\\n", raw)
		for _, u := range []string{"/s/a%20b", "/s/a%2Fb/c", "/s/%E4%B8%AD", "/s/a%25b"} {
			w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest("GET", u, nil)); fmt.Printf("    %-14s → %d %s\\n", u, w.Code, w.Body.String())
		}
	}
}""")
out_lines(r)
print('== 四:取到参数之后的路径穿越:UseRawPath 让 %2e%2e%2f 变成 ../ 直接进了参数值')
r = gin('n14d', """package main
import ("fmt"; "net/http/httptest"; "path/filepath"; "github.com/gin-gonic/gin")
func main() {
	for _, c := range []struct{ n string; raw bool }{{"默认", false}, {"UseRawPath=true", true}} {
		r := gin.New(); r.UseRawPath = c.raw; r.UnescapePathValues = true
		r.GET("/dl/:name", func(c *gin.Context) {
			n := c.Param("name")
			c.String(200, "name=%q Join(/srv/files, name)=%q", n, filepath.Join("/srv/files", n))
		})
		fmt.Printf("  [%s]\\n", c.n)
		for _, u := range []string{"/dl/report.pdf", "/dl/..%2F..%2Fetc%2Fpasswd", "/dl/%2e%2e%2fsecret"} {
			w := httptest.NewRecorder(); r.ServeHTTP(w, httptest.NewRequest("GET", u, nil)); fmt.Printf("    %-28s → %d %s\\n", u, w.Code, w.Body.String())
		}
	}
}""")
out_lines(r)
