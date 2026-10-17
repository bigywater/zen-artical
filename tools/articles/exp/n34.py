import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n34')
HELP = '''
type part struct{ field, filename, ctype string; size int }
func mp(url string, fields map[string]string, parts []part) (int, string) {
	var buf bytes.Buffer; mw := multipart.NewWriter(&buf)
	for k, v := range fields { mw.WriteField(k, v) }
	for _, p := range parts {
		h := textproto.MIMEHeader{}
		h.Set("Content-Disposition", fmt.Sprintf(`form-data; name="%s"; filename="%s"`, p.field, p.filename))
		if p.ctype != "" { h.Set("Content-Type", p.ctype) } else { h.Set("Content-Type", "application/octet-stream") }
		w, _ := mw.CreatePart(h); w.Write(bytes.Repeat([]byte("x"), p.size))
	}
	mw.Close()
	req, _ := http.NewRequest("POST", url, &buf); req.Header.Set("Content-Type", mw.FormDataContentType())
	resp, err := http.DefaultClient.Do(req); if err != nil { return 0, err.Error() }
	b, _ := io.ReadAll(resp.Body); resp.Body.Close(); return resp.StatusCode, strings.TrimSpace(string(b))
}
'''
IMP = '''package main
import ("bytes"; "fmt"; "io"; "mime/multipart"; "net/http"; "net/http/httptest"; "net/textproto"; "os"; "path/filepath"; "strings"; "github.com/gin-gonic/gin")
var _ = os.Getpid
var _ = filepath.Base
'''
print('== 一:同一个字段名上传多个文件:c.FormFile 只给第一个,c.MultipartForm().File[name] 给全部(按请求里的顺序)')
r = gin('n34a', IMP + HELP + '''
func main() {
	r := gin.New()
	r.POST("/one", func(c *gin.Context) { fh, err := c.FormFile("files"); if err != nil { c.String(400, "%v", err); return }; c.String(200, "FormFile(files) → %s %d 字节", fh.Filename, fh.Size) })
	r.POST("/all", func(c *gin.Context) {
		f, err := c.MultipartForm(); if err != nil { c.String(400, "%v", err); return }
		var s []string
		for _, fh := range f.File["files"] { s = append(s, fmt.Sprintf("%s(%d 字节,%s)", fh.Filename, fh.Size, fh.Header.Get("Content-Type"))) }
		keys := []string{}; for k := range f.File { keys = append(keys, k) }
		c.String(200, "File[\\"files\\"] = %s;表单里共有的文件字段名:%d 个;Value=%v", strings.Join(s, " "), len(keys), f.Value)
	})
	ts := httptest.NewServer(r); defer ts.Close()
	parts := []part{{"files", "b.txt", "text/plain", 3}, {"files", "a.png", "image/png", 10}, {"files", "c.bin", "", 0}, {"other", "o.txt", "text/plain", 5}}
	fmt.Println("  请求里的顺序:b.txt、a.png、c.bin(都叫 files),另有 other 字段的 o.txt")
	fmt.Println("  ", func() string { _, b := mp(ts.URL+"/one", map[string]string{"title": "t"}, parts); return b }())
	fmt.Println("  ", func() string { _, b := mp(ts.URL+"/all", map[string]string{"title": "t"}, parts); return b }())
	fmt.Println("  --- 没有这个字段时:")
	fmt.Println("  ", func() string { _, b := mp(ts.URL+"/one", nil, []part{{"zzz", "z.txt", "", 1}}); return b }())
}''')
out_lines(r)
print('== 二:绑定到结构体:[]*multipart.FileHeader 与 *multipart.FileHeader 字段(form 标签),与普通字段、校验一起')
r = gin('n34b', IMP + HELP + '''
type Up struct {
	Title  string                  `form:"title" binding:"required"`
	Avatar *multipart.FileHeader   `form:"avatar" binding:"required"`
	Files  []*multipart.FileHeader `form:"files"`
}
func main() {
	r := gin.New()
	r.POST("/x", func(c *gin.Context) {
		var u Up; err := c.ShouldBind(&u)
		var names []string; for _, f := range u.Files { names = append(names, f.Filename) }
		av := "nil"; if u.Avatar != nil { av = u.Avatar.Filename }
		c.String(200, "Title=%q Avatar=%s Files=%v err=%v", u.Title, av, names, err)
	})
	ts := httptest.NewServer(r); defer ts.Close()
	for _, tc := range []struct{ name string; f map[string]string; p []part }{
		{"全部给出", map[string]string{"title": "t"}, []part{{"avatar", "me.png", "", 5}, {"files", "1.txt", "", 1}, {"files", "2.txt", "", 2}}},
		{"缺 avatar", map[string]string{"title": "t"}, []part{{"files", "1.txt", "", 1}}},
		{"缺 title", nil, []part{{"avatar", "me.png", "", 5}}},
		{"files 只有一个", map[string]string{"title": "t"}, []part{{"avatar", "me.png", "", 5}, {"files", "only.txt", "", 1}}},
	} { _, b := mp(ts.URL+"/x", tc.f, tc.p); fmt.Printf("  %-12s → %s\\n", tc.name, b) }
}''')
out_lines(r)
print('== 三:客户端给的文件名:Go 会先 filepath.Base;但反斜杠在 Unix 上不是分隔符;绝对路径、空文件名')
r = gin('n34c', IMP + HELP + '''
func main() {
	r := gin.New()
	r.POST("/x", func(c *gin.Context) {
		f, err := c.MultipartForm(); if err != nil { c.String(400, "%v", err); return }
		var s []string; for _, fh := range f.File["f"] { s = append(s, fmt.Sprintf("%q", fh.Filename)) }
		c.String(200, "%s", strings.Join(s, " "))
	})
	ts := httptest.NewServer(r); defer ts.Close()
	for _, name := range []string{"report.pdf", "../../etc/passwd", "/etc/passwd", "a/b/c.txt", `..\\..\\win.ini`, `C:\\Users\\x\\a.txt`, "..", ".", "a\\x00b.txt", "  spaced name .txt"} {
		code, b := mp(ts.URL+"/x", nil, []part{{"f", name, "", 1}}); fmt.Printf("  客户端发送 filename=%-26q → 服务端读到 %s(%d)\\n", name, b, code)
	}
}''')
out_lines(r)
print('== 四:SaveUploadedFile(v1.12):会 MkdirAll,而且会对目标目录 Chmod(默认 0750)——已存在的目录权限被改掉')
gfunc('context.go', 'SaveUploadedFile')
r = gin('n34d', IMP + HELP + '''
func main() {
	base, _ := os.MkdirTemp("", "gin-save-"); defer os.RemoveAll(base)
	exist := filepath.Join(base, "exist"); os.Mkdir(exist, 0o755); os.Chmod(exist, 0o755)
	mode := func(p string) string { fi, err := os.Stat(p); if err != nil { return "不存在" }; return fi.Mode().String() }
	r := gin.New()
	r.POST("/x", func(c *gin.Context) {
		fh, _ := c.FormFile("f")
		e1 := c.SaveUploadedFile(fh, filepath.Join(exist, "a.txt"))
		e2 := c.SaveUploadedFile(fh, filepath.Join(base, "new", "deep", "b.txt"))
		e3 := c.SaveUploadedFile(fh, filepath.Join(base, "perm", "c.txt"), 0o700)
		c.String(200, "%v %v %v", e1, e2, e3)
	})
	ts := httptest.NewServer(r); defer ts.Close()
	fmt.Println("  保存之前 exist 目录权限:", mode(exist))
	mp(ts.URL+"/x", nil, []part{{"f", "f.txt", "", 7}})
	fmt.Println("  保存之后 exist 目录权限:", mode(exist), " 新建的 new/deep:", mode(filepath.Join(base, "new", "deep")), " new:", mode(filepath.Join(base, "new")), " perm(传了 0700):", mode(filepath.Join(base, "perm")))
	b, _ := os.ReadFile(filepath.Join(base, "new", "deep", "b.txt")); fmt.Println("  b.txt 内容长度:", len(b))
}''')
out_lines(r)
print('== 五:一个请求里最多多少个 part:Go 标准库默认 1000(GODEBUG multipartmaxparts),超过报 multipart: message too large')
r = gin('n34e', IMP + HELP + '''
func main() {
	r := gin.New()
	r.POST("/x", func(c *gin.Context) { f, err := c.MultipartForm(); if err != nil { c.String(400, "%v", err); return }; c.String(200, "收到 %d 个文件", len(f.File["f"])) })
	ts := httptest.NewServer(r); defer ts.Close()
	for _, n := range []int{999, 1000, 1001} {
		parts := make([]part, n); for i := range parts { parts[i] = part{"f", fmt.Sprintf("f%d.txt", i), "", 1} }
		code, b := mp(ts.URL+"/x", nil, parts); fmt.Printf("  %4d 个文件 → %d %s\\n", n, code, b)
	}
}''')
out_lines(r)
