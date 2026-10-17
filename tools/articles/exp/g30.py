import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g30')
MAIN = r'''
package main

import (
	"embed"
	"fmt"
	"io/fs"
	"net/http"
	"net/http/httptest"
	"sort"
	"strings"
	"testing"
)

//go:embed hello.txt
var helloStr string

//go:embed hello.txt
var helloBytes []byte

//go:embed hello.txt
var helloFS embed.FS

//go:embed assets
var dirFS embed.FS

//go:embed all:assets
var allFS embed.FS

//go:embed assets/*.txt assets/sub/*.md
var globFS embed.FS

func list(name string, fsys fs.FS) {
	var names []string
	fs.WalkDir(fsys, ".", func(p string, d fs.DirEntry, err error) error {
		if err != nil { return err }
		if !d.IsDir() { names = append(names, p) }
		return nil
	})
	fmt.Printf("  %-34s %d 个文件:%s\n", name, len(names), strings.Join(names, " "))
}

var sink int

func main() {
	fmt.Printf("  string 变量:%q;[]byte 变量:%q(len %d);embed.FS 单文件:", helloStr, helloBytes, len(helloBytes))
	b, _ := helloFS.ReadFile("hello.txt")
	fmt.Printf("%q\n", b)
	list("//go:embed assets", dirFS)
	list("//go:embed all:assets", allFS)
	list("//go:embed assets/*.txt assets/sub/*.md", globFS)

	fmt.Println("== 二:embed.FS 里的文件信息:只读、时间为零、按名字排序")
	entries, _ := dirFS.ReadDir("assets")
	var ns []string
	for _, e := range entries { ns = append(ns, e.Name()) }
	fmt.Printf("  ReadDir(\"assets\") 的顺序:%s(sort.StringsAreSorted = %v)\n", strings.Join(ns, " "), sort.StringsAreSorted(ns))
	fi, _ := fs.Stat(dirFS, "assets/a.txt")
	fmt.Printf("  Stat(assets/a.txt):Size = %d,Mode = %v,ModTime.IsZero() = %v\n", fi.Size(), fi.Mode(), fi.ModTime().IsZero())
	_, err := dirFS.ReadFile("assets/不存在.txt")
	fmt.Printf("  读不存在的文件:%v\n", err)
	_, err = dirFS.ReadFile("/assets/a.txt")
	fmt.Printf("  路径带前导斜杠:%v\n", err)
	sub, _ := fs.Sub(dirFS, "assets")
	d, _ := fs.ReadFile(sub, "sub/c.md")
	fmt.Printf("  fs.Sub(dirFS, \"assets\") 后读 sub/c.md:%q\n", d)
	helloBytes[0] = 'J'
	fmt.Printf("  修改 []byte 变量(helloBytes[0] = 'J'):%q;再从 embed.FS 读:%q\n", helloBytes, func() string { x, _ := helloFS.ReadFile("hello.txt"); return string(x) }())

	fmt.Println("== 三:配合 net/http:http.FS 提供静态文件")
	srv := http.FileServer(http.FS(sub))
	for _, p := range []string{"/a.txt", "/sub/c.md", "/missing", "/"} {
		rec := httptest.NewRecorder()
		srv.ServeHTTP(rec, httptest.NewRequest("GET", p, nil))
		h := rec.Header()
		fmt.Printf("  GET %-10s → %d,Content-Type %q,Last-Modified %q,Content-Length %q,正文前 20 字节 %q\n", p, rec.Code, h.Get("Content-Type"), h.Get("Last-Modified"), h.Get("Content-Length"), truncate(rec.Body.String(), 20))
	}

	fmt.Println("== 四:读取成本(7 轮取中位数)与分配")
	bench("使用 string 变量(无读取)", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += len(helloStr) } })
	bench("embed.FS.ReadFile(\"hello.txt\")", func(b *testing.B) { for i := 0; i < b.N; i++ { x, _ := helloFS.ReadFile("hello.txt"); sink += len(x) } })
	bench("fs.ReadFile(dirFS, \"assets/a.txt\")", func(b *testing.B) { for i := 0; i < b.N; i++ { x, _ := fs.ReadFile(dirFS, "assets/a.txt"); sink += len(x) } })
	bench("dirFS.Open + Stat + Close", func(b *testing.B) { for i := 0; i < b.N; i++ { f, _ := dirFS.Open("assets/a.txt"); st, _ := f.Stat(); sink += int(st.Size()); f.Close() } })
	fmt.Printf("  AllocsPerRun:ReadFile %.0f 次;使用 string 变量 %.0f 次\n", testing.AllocsPerRun(1000, func() { x, _ := helloFS.ReadFile("hello.txt"); sink += len(x) }), testing.AllocsPerRun(1000, func() { sink += len(helloStr) }))
}

func truncate(s string, n int) string {
	if len(s) > n { return s[:n] }
	return s
}
''' + GBENCH
FILES = {'main.go': MAIN, 'hello.txt': 'hello, embed',
         'assets/a.txt': 'file a\n', 'assets/b.txt': 'file b\n', 'assets/.hidden': 'hidden file\n', 'assets/_under.txt': 'underscore file\n',
         'assets/sub/c.md': '# c\n', 'assets/sub/.secret': 'secret\n', 'assets/sub/_x.md': 'x\n'}
print('== 一:几种 //go:embed 的写法与目录规则(Go 1.27.1)')
r = grun('em1', FILES, timeout=600)
print(r['out'] if r['crc'] == 0 else r['cout'])

print('== 五:二进制里的位置与体积:嵌入 1 MiB 随机文件')
d = gdir('em2'); mod(d)
write(d, {'main.go': '''package main

import (
	_ "embed"
	"fmt"
)

//go:embed blob.bin
var blob []byte

//go:embed blob.bin
var blobStr string

func main() { fmt.Println(len(blob), len(blobStr)) }
'''})
d0 = gdir('em3'); mod(d0)
write(d0, {'main.go': 'package main\n\nimport "fmt"\n\nfunc main() { fmt.Println(0, 0) }\n'})
(d / 'blob.bin').write_bytes(os.urandom(1 << 20))
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
rc, o = go(d0, 'build', '-o', 'app'); assert rc == 0, o
s1, s0 = os.path.getsize(d / 'app'), os.path.getsize(d0 / 'app')
print(f'  不嵌入的同类程序 {s0} 字节;嵌入 1 MiB(1048576 字节)文件,同时用 []byte 与 string 各声明一次:{s1} 字节,增加 {s1 - s0} 字节(约 {(s1 - s0) / 1048576:.2f} MiB)')
rc, nm = go(d, 'tool', 'nm', '-size', '-n', 'app')
big = [l for l in nm.split('\n') if len(l.split()) >= 4 and l.split()[1].isdigit() and int(l.split()[1]) >= 1 << 20]
print('  go tool nm -size 里 ≥ 1 MiB 的符号:')
for l in big[:4]: print('    ' + re.sub(r'^\s*[0-9a-f]+', '<地址>', l.strip()))
print(f'  同一个文件用 []byte 与 string 各声明一次,体积共多 {(s1 - s0) / 1048576:.2f} MiB:[]byte 的数据在可写的数据段(符号类型 D),string 在只读段(R),各占一份,没有合并')

print('== 六:写错时编译器的报错')
def ce(title, code, files=None, n=2):
    dd = gdir('emc'); mod(dd); write(dd, {'main.go': code, 'a.txt': 'a\n', **(files or {})})
    rc, o = go(dd, 'build', '-o', 'app')
    ls = [re.sub(r'^\./', '', l) for l in o.split('\n') if re.match(r'^(\./)?main\.go:\d+', l)][:n]
    print(f'  {title}:')
    for l in (ls or ['(无 main.go 行)原始输出:' + o[:200]]): print('    ' + l)
HDR = 'package main\n\nimport "embed"\n\nvar _ embed.FS\n\n'
ce('匹配不到文件', HDR + '//go:embed nothing.txt\nvar s string\n\nfunc main() { _ = s }\n')
ce('写到模块之外(../)', HDR + '//go:embed ../a.txt\nvar s string\n\nfunc main() { _ = s }\n')
ce('在函数里声明', HDR + 'func main() {\n\t//go:embed a.txt\n\tvar s string\n\t_ = s\n}\n')
ce('变量类型是 int', HDR + '//go:embed a.txt\nvar s int\n\nfunc main() { _ = s }\n')
ce('string 变量没有导入 embed 包', 'package main\n\n//go:embed a.txt\nvar s string\n\nfunc main() { _ = s }\n')
ce('把含两个文件的目录嵌进 string', HDR + '//go:embed sub\nvar s string\n\nfunc main() { _ = s }\n', files={'sub/x.txt': 'x', 'sub/y.txt': 'y'})
dd = gdir('emd'); mod(dd); write(dd, {'main.go': HDR + '//go:embed sub\nvar s string\n\nfunc main() { println(len(s), s) }\n', 'sub/x.txt': 'xx'})
rc, o = go(dd, 'build', '-o', 'app')
pr_ = subprocess.run([str(dd / 'app')], capture_output=True, text=True)
print(f'  把只含 1 个文件(内容 "xx")的目录嵌进 string:编译 rc={rc};运行输出 len, s = {pr_.stderr.strip()!r}')
shutil.rmtree(GT / 'emc', ignore_errors=True)
