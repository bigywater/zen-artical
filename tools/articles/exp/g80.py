import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g80')
SRC = r'''
package main

import (
	"fmt"
	"io"
	"log"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"sync"
	"testing"
)

func hello(w http.ResponseWriter, r *http.Request) {
	io.WriteString(w, strings.Repeat("a", 100))
}

func info(w http.ResponseWriter, r *http.Request) {
	fmt.Fprintf(w, "RemoteAddr=%s Host=%s Proto=%s TLS=%v BodyNil=%v", r.RemoteAddr, r.Host, r.Proto, r.TLS != nil, r.Body == nil)
}

func twice(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(200)
	w.WriteHeader(500)
	io.WriteString(w, "x")
}

func boom(w http.ResponseWriter, r *http.Request) { panic("handler panic") }

func main() {
	switch os.Args[1] {
	case "headers":
		rec := httptest.NewRecorder()
		hello(rec, httptest.NewRequest("GET", "/", nil))
		res := rec.Result()
		fmt.Printf("  ResponseRecorder:Code=%d Proto=%s Content-Length=%q Content-Type=%q 响应头个数=%d\n", res.StatusCode, res.Proto, res.Header.Get("Content-Length"), res.Header.Get("Content-Type"), len(res.Header))
		ts := httptest.NewServer(http.HandlerFunc(hello))
		defer ts.Close()
		resp, _ := http.Get(ts.URL)
		fmt.Printf("  httptest.Server:Code=%d Proto=%s Content-Length=%q Content-Type=%q 响应头个数=%d\n", resp.StatusCode, resp.Proto, resp.Header.Get("Content-Length"), resp.Header.Get("Content-Type"), len(resp.Header))
	case "request":
		rec := httptest.NewRecorder()
		info(rec, httptest.NewRequest("GET", "/path?x=1", nil))
		fmt.Printf("  NewRequest + Recorder:%s\n", rec.Body.String())
		ts := httptest.NewServer(http.HandlerFunc(info))
		defer ts.Close()
		resp, _ := http.Get(ts.URL)
		b, _ := io.ReadAll(resp.Body)
		fmt.Printf("  httptest.Server:%s\n", string(b))
		r := httptest.NewRequest("GET", "/", nil)
		fmt.Printf("  httptest.NewRequest 的 Body == http.NoBody:%v;自己 http.NewRequest 不给 body 时 Body 是 %v\n", r.Body == http.NoBody, func() any { x, _ := http.NewRequest("GET", "http://x/", nil); return x.Body }())
	case "twice":
		rec := httptest.NewRecorder()
		twice(rec, httptest.NewRequest("GET", "/", nil))
		fmt.Printf("  Recorder:WriteHeader(200) 再 WriteHeader(500) 之后 Code = %d,Body = %q,没有任何错误或日志\n", rec.Code, rec.Body.String())
	case "panic":
		func() {
			defer func() { fmt.Printf("  Recorder:handler 里的 panic 直接传给了测试代码(没有被 recover):%v\n", recover()) }()
			boom(httptest.NewRecorder(), httptest.NewRequest("GET", "/", nil))
		}()
		ts := httptest.NewUnstartedServer(http.HandlerFunc(boom))
		ts.Config.ErrorLog = log.New(io.Discard, "", 0)
		ts.Start()
		defer ts.Close()
		_, err := http.Get(ts.URL)
		fmt.Printf("  httptest.Server:handler panic 时客户端得到 err = %v\n", err)
	case "badurl":
		func() {
			defer func() { fmt.Printf("  httptest.NewRequest(\"GET\", \"://bad\", nil) → panic:%v\n", recover()) }()
			httptest.NewRequest("GET", "://bad", nil)
		}()
		_, err := http.NewRequest("GET", "://bad", nil)
		fmt.Printf("  http.NewRequest(\"GET\", \"://bad\", nil) → 返回 error:%v\n", err)
	case "testserver":
		var once sync.Once
		testing.Benchmark(func(b *testing.B) {
			ts := httptest.NewTestServer(b, http.HandlerFunc(info))
			resp, err := ts.Client().Get(ts.URL)
			if err != nil { fmt.Println("  错误:", err); return }
			body, _ := io.ReadAll(resp.Body)
			once.Do(func() {
				fmt.Printf("  httptest.NewTestServer:ts.URL = %q;ts.Listener == nil:%v;handler 看到 %s\n", ts.URL, ts.Listener == nil, string(body))
				c2, err := ts.Client().Get("http://anything.invalid/other/path")
				if err == nil { b2, _ := io.ReadAll(c2.Body); fmt.Printf("  用 ts.Client() 访问任意地址 http://anything.invalid/other/path 也能到达这个服务器:状态 %d,handler 看到 %s\n", c2.StatusCode, string(b2)) } else { fmt.Printf("  ts.Client() 访问任意地址:%v\n", err) }
			})
		})
	case "bench":
		r1 := testing.Benchmark(func(b *testing.B) {
			h := http.HandlerFunc(hello)
			for i := 0; i < b.N; i++ { rec := httptest.NewRecorder(); h.ServeHTTP(rec, httptest.NewRequest("GET", "/", nil)) }
		})
		ts := httptest.NewServer(http.HandlerFunc(hello))
		defer ts.Close()
		c := ts.Client()
		r2 := testing.Benchmark(func(b *testing.B) {
			for i := 0; i < b.N; i++ { resp, _ := c.Get(ts.URL); io.Copy(io.Discard, resp.Body); resp.Body.Close() }
		})
		r3 := testing.Benchmark(func(b *testing.B) {
			ts := httptest.NewTestServer(b, http.HandlerFunc(hello))
			c := ts.Client()
			b.ResetTimer()
			for i := 0; i < b.N; i++ { resp, _ := c.Get(ts.URL); io.Copy(io.Discard, resp.Body); resp.Body.Close() }
		})
		fmt.Printf("  Recorder 直接调用 handler:%d ns/次(%d 次分配);httptest.NewServer(真实回环端口)+ 客户端往返:%d ns/次(%d 次分配);httptest.NewTestServer(内存网络)+ ts.Client() 往返:%d ns/次(%d 次分配)\n", r1.NsPerOp(), r1.AllocsPerOp(), r2.NsPerOp(), r2.AllocsPerOp(), r3.NsPerOp(), r3.AllocsPerOp())
	}
}
'''
d = gdir('ht2'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(m):
    p = subprocess.run([str(d / 'app'), m], capture_output=True, text=True, timeout=120)
    return tidy(p.stdout + p.stderr)
print('== 一:同一个 handler,经过 ResponseRecorder 与经过真实服务器,响应有什么不同(Go 1.27.1,arm64 macOS)')
print(run('headers'))
print('== 二:请求对象不同')
print(run('request'))
print('== 三:重复 WriteHeader')
print(run('twice'))
print('== 四:handler panic')
print(run('panic'))
print('== 五:NewRequest 的参数错误')
print(run('badurl'))
print('== 六:第三种:Go 1.27.1 里的 httptest.NewTestServer(内存网络)')
print(run('testserver'))
print('== 七:速度')
print(run('bench'))
print('== 八:httptest 包文档')
r, o = go(gdir('doc1'), 'doc', 'net/http/httptest.NewTestServer')
print('  ' + ' '.join(l.strip() for l in o.split('\n')[3:9] if l.strip()))
r, o = go(gdir('doc1'), 'doc', 'net/http/httptest.NewRequest')
print('  ' + ' '.join(l.strip() for l in o.split('\n')[3:14] if l.strip()))
