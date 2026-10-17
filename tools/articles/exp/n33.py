import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n33')
HELP = '''
func upload(url string, fields map[string]string, files map[string]int) (int, string) {
	pr, pw := io.Pipe(); mw := multipart.NewWriter(pw)
	go func() {
		for k, v := range fields { mw.WriteField(k, v) }
		for name, size := range files {
			fw, _ := mw.CreateFormFile(name, name+".bin")
			buf := make([]byte, 64<<10); for i := range buf { buf[i] = byte(i) }
			for n := 0; n < size; n += len(buf) { m := len(buf); if size-n < m { m = size - n }; fw.Write(buf[:m]) }
		}
		mw.Close(); pw.Close()
	}()
	req, _ := http.NewRequest("POST", url, pr); req.Header.Set("Content-Type", mw.FormDataContentType())
	resp, err := http.DefaultClient.Do(req)
	if err != nil { return 0, err.Error() }
	b, _ := io.ReadAll(resp.Body); resp.Body.Close(); return resp.StatusCode, string(b)
}
func tmpList(dir string) string {
	es, _ := os.ReadDir(dir); var parts []string
	for _, e := range es { if fi, err := e.Info(); err == nil { parts = append(parts, fmt.Sprintf("%s(%.1f MiB)", strings.SplitN(e.Name(), "-", 2)[0], float64(fi.Size())/(1<<20))) } }
	if len(parts) == 0 { return "无" }; return strings.Join(parts, " ")
}
func alloc() uint64 { var m runtime.MemStats; runtime.ReadMemStats(&m); return m.TotalAlloc }
'''
IMP = '''package main
import ("errors"; "fmt"; "io"; "mime/multipart"; "net/http"; "net/http/httptest"; "os"; "runtime"; "strings"; "time"; "github.com/gin-gonic/gin")
var _ = errors.New
var _ = time.Now
'''
print('== 一:默认值与 FormFile 的源码')
r = gin('n33pre', 'package main\nimport ("fmt"; "github.com/gin-gonic/gin")\nfunc main(){ fmt.Printf("  gin.New().MaxMultipartMemory = %d(= %d MiB)\\n", gin.New().MaxMultipartMemory, gin.New().MaxMultipartMemory>>20) }')
out_lines(r)
gfunc('context.go', 'FormFile')
print('== 二:上传 5 MiB 文件:MaxMultipartMemory 为 1 MiB 与 64 MiB 时,handler 里临时目录里有什么、请求结束后还在吗')
r = gin('n33a', IMP + HELP + '''
func main() {
	tmp, _ := os.MkdirTemp("", "gin-upload-"); os.Setenv("TMPDIR", tmp); defer os.RemoveAll(tmp)
	for _, limit := range []int64{1 << 20, 64 << 20} {
		r := gin.New(); r.MaxMultipartMemory = limit
		r.POST("/up", func(c *gin.Context) {
			fh, err := c.FormFile("f")
			if err != nil { c.String(400, "%v", err); return }
			c.String(200, "FormFile 之后临时目录:%s;fh.Size=%.1f MiB", tmpList(tmp), float64(fh.Size)/(1<<20))
		})
		ts := httptest.NewServer(r)
		code, body := upload(ts.URL+"/up", map[string]string{"note": "hi"}, map[string]int{"f": 5 << 20})
		time.Sleep(50 * time.Millisecond)
		fmt.Printf("  MaxMultipartMemory=%-3d MiB → %d %s;请求结束后临时目录:%s\\n", limit>>20, code, body, tmpList(tmp))
		ts.Close()
	}
}''')
out_lines(r)
print('== 三:内存与耗时:上传 40 MiB 文件,FormFile 调用期间的累计分配(TotalAlloc)')
r = gin('n33b', IMP + HELP + '''
func main() {
	tmp, _ := os.MkdirTemp("", "gin-upload-"); os.Setenv("TMPDIR", tmp); defer os.RemoveAll(tmp)
	for round := 1; round <= 2; round++ {
		for _, limit := range []int64{1 << 20, 32 << 20, 64 << 20} {
			r := gin.New(); r.MaxMultipartMemory = limit
			r.POST("/up", func(c *gin.Context) {
				a0 := alloc(); t0 := time.Now()
				_, err := c.FormFile("f")
				c.String(200, "分配 %.1f MiB,耗时 %d ms,err=%v", float64(alloc()-a0)/(1<<20), time.Since(t0).Milliseconds(), err)
			})
			ts := httptest.NewServer(r)
			_, body := upload(ts.URL+"/up", nil, map[string]int{"f": 40 << 20})
			fmt.Printf("  第 %d 轮 MaxMultipartMemory=%-3d MiB:%s\\n", round, limit>>20, body); ts.Close()
		}
	}
}''')
out_lines(r)
print('== 四:上限只管“放内存还是放磁盘”,不管总大小:没有 MaxBytesReader 时 200 MiB 照单全收;加了之后超过上限报 http: request body too large')
r = gin('n33c', IMP + HELP + '''
func main() {
	tmp, _ := os.MkdirTemp("", "gin-upload-"); os.Setenv("TMPDIR", tmp); defer os.RemoveAll(tmp)
	r := gin.New(); r.MaxMultipartMemory = 1 << 20
	r.POST("/open", func(c *gin.Context) { fh, err := c.FormFile("f"); if err != nil { c.String(400, "%v", err); return }; c.String(200, "收下 %d MiB,临时目录:%s", fh.Size>>20, tmpList(tmp)) })
	r.POST("/capped", func(c *gin.Context) {
		c.Request.Body = http.MaxBytesReader(c.Writer, c.Request.Body, 8<<20)
		fh, err := c.FormFile("f")
		var mbe *http.MaxBytesError
		if errors.As(err, &mbe) { c.String(413, "超过上限 %d 字节:%v", mbe.Limit, err); return }
		if err != nil { c.String(400, "%v", err); return }
		c.String(200, "收下 %d MiB", fh.Size>>20)
	})
	ts := httptest.NewServer(r); defer ts.Close()
	code, body := upload(ts.URL+"/open", nil, map[string]int{"f": 200 << 20}); fmt.Printf("  /open   上传 200 MiB → %d %s\\n", code, body)
	code, body = upload(ts.URL+"/capped", nil, map[string]int{"f": 5 << 20}); fmt.Printf("  /capped(上限 8 MiB)上传 5 MiB → %d %s\\n", code, body)
	code, body = upload(ts.URL+"/capped", nil, map[string]int{"f": 20 << 20}); fmt.Printf("  /capped(上限 8 MiB)上传 20 MiB → %d %s\\n", code, body)
}''', timeout=300)
out_lines(r)
print('== 五:非文件字段也有上限:单个字段超过 maxMemory + 10 MiB 就报 multipart: message too large(限制为 1 MiB 时)')
r = gin('n33d', IMP + HELP + '''
func main() {
	r := gin.New(); r.MaxMultipartMemory = 1 << 20
	r.POST("/up", func(c *gin.Context) { v := c.PostForm("big"); c.String(200, "读到 big 字段 %.1f MiB", float64(len(v))/(1<<20)) })
	r.POST("/mf", func(c *gin.Context) { f, err := c.MultipartForm(); if err != nil { c.String(400, "%v", err); return }; c.String(200, "字段数 %d", len(f.Value)) })
	ts := httptest.NewServer(r); defer ts.Close()
	for _, mb := range []int{2, 10, 12} {
		code, body := upload(ts.URL+"/mf", map[string]string{"big": strings.Repeat("x", mb<<20)}, nil)
		fmt.Printf("  MaxMultipartMemory=1 MiB,文本字段 %2d MiB → %d %s\\n", mb, code, body)
	}
}''', timeout=300)
out_lines(r)
