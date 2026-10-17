import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g76')
SRC = r'''
package main

import (
	"bufio"
	"bytes"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"runtime"
	"strings"
	"sync"
	"time"
)

func startServer(h http.Handler, state func(net.Conn, http.ConnState), logw io.Writer) (string, func()) {
	ln, _ := net.Listen("tcp", "127.0.0.1:0")
	srv := &http.Server{Handler: h, ConnState: state, ErrorLog: log.New(logw, "", 0)}
	go srv.Serve(ln)
	return ln.Addr().String(), func() { srv.Close() }
}

func readResp(br *bufio.Reader) (string, string) {
	var head strings.Builder
	var cl int
	chunked := false
	for {
		l, err := br.ReadString('\n')
		if err != nil { return head.String(), "" }
		head.WriteString(l)
		if strings.HasPrefix(strings.ToLower(l), "content-length:") { fmt.Sscanf(strings.TrimSpace(l[15:]), "%d", &cl) }
		if strings.HasPrefix(strings.ToLower(l), "transfer-encoding: chunked") { chunked = true }
		if l == "\r\n" { break }
	}
	var body []byte
	if chunked {
		for {
			l, _ := br.ReadString('\n')
			var n int
			fmt.Sscanf(strings.TrimSpace(l), "%x", &n)
			if n == 0 { br.ReadString('\n'); break }
			b := make([]byte, n); io.ReadFull(br, b); body = append(body, b...); br.ReadString('\n')
		}
	} else {
		body = make([]byte, cl); io.ReadFull(br, body)
	}
	return head.String(), string(body)
}

func main() {
	switch os.Args[1] {
	case "states":
		var mu sync.Mutex
		var seq []string
		addr, stop := startServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { io.WriteString(w, "ok") }), func(c net.Conn, s http.ConnState) {
			mu.Lock(); seq = append(seq, s.String()); mu.Unlock()
		}, io.Discard)
		defer stop()
		c, _ := net.Dial("tcp", addr)
		br := bufio.NewReader(c)
		for i := 0; i < 2; i++ {
			fmt.Fprintf(c, "GET /%d HTTP/1.1\r\nHost: x\r\n\r\n", i)
			readResp(br)
		}
		c.Close()
		time.Sleep(50 * time.Millisecond)
		mu.Lock()
		fmt.Printf("  一个 TCP 连接上连续发 2 个请求再关闭,ConnState 依次是:%s\n", strings.Join(seq, " → "))
		mu.Unlock()
	case "goroutines":
		release := make(chan struct{})
		addr, stop := startServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { <-release; io.WriteString(w, "ok") }), nil, io.Discard)
		defer stop()
		base := runtime.NumGoroutine()
		var conns []net.Conn
		for i := 0; i < 500; i++ {
			c, _ := net.Dial("tcp", addr)
			fmt.Fprintf(c, "GET / HTTP/1.1\r\nHost: x\r\n\r\n")
			conns = append(conns, c)
		}
		time.Sleep(300 * time.Millisecond)
		fmt.Printf("  500 个连接各有一个请求卡在 Handler 里:goroutine 数 %d → %d(增加 %d,约每个连接 %.1f 个)\n", base, runtime.NumGoroutine(), runtime.NumGoroutine()-base, float64(runtime.NumGoroutine()-base)/500)
		close(release)
		for _, c := range conns { c.Close() }
		time.Sleep(200 * time.Millisecond)
		fmt.Printf("  放行并关闭连接后 goroutine 数 %d\n", runtime.NumGoroutine())
	case "headers":
		var logb bytes.Buffer
		mux := http.NewServeMux()
		mux.HandleFunc("/small", func(w http.ResponseWriter, r *http.Request) { io.WriteString(w, strings.Repeat("a", 100)) })
		mux.HandleFunc("/flush", func(w http.ResponseWriter, r *http.Request) { io.WriteString(w, "part1"); w.(http.Flusher).Flush(); io.WriteString(w, "part2") })
		mux.HandleFunc("/big", func(w http.ResponseWriter, r *http.Request) { io.WriteString(w, strings.Repeat("b", 10000)) })
		mux.HandleFunc("/twice", func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(200); w.WriteHeader(500); io.WriteString(w, "x") })
		addr, stop := startServer(mux, nil, &logb)
		defer stop()
		for _, p := range []string{"/small", "/flush", "/big", "/twice"} {
			c, _ := net.Dial("tcp", addr)
			fmt.Fprintf(c, "GET %s HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n", p)
			head, body := readResp(bufio.NewReader(c))
			var keep []string
			for _, l := range strings.Split(head, "\r\n") {
				ll := strings.ToLower(l)
				if strings.HasPrefix(l, "HTTP/") || strings.HasPrefix(ll, "content-length") || strings.HasPrefix(ll, "transfer-encoding") || strings.HasPrefix(ll, "content-type") { keep = append(keep, l) }
			}
			fmt.Printf("  %-7s → %s;body %d 字节\n", p, strings.Join(keep, " | "), len(body))
			c.Close()
		}
		time.Sleep(50 * time.Millisecond)
		fmt.Printf("  /twice 时服务器的错误日志:%q\n", strings.TrimSpace(logb.String()))
	case "panic":
		var logb bytes.Buffer
		mux := http.NewServeMux()
		mux.HandleFunc("/boom", func(w http.ResponseWriter, r *http.Request) { panic("handler 里 panic") })
		mux.HandleFunc("/ok", func(w http.ResponseWriter, r *http.Request) { io.WriteString(w, "ok") })
		addr, stop := startServer(mux, nil, &logb)
		defer stop()
		c, _ := net.Dial("tcp", addr)
		fmt.Fprintf(c, "GET /boom HTTP/1.1\r\nHost: x\r\n\r\n")
		c.SetReadDeadline(time.Now().Add(time.Second))
		b, err := io.ReadAll(c)
		fmt.Printf("  请求 /boom:客户端收到 %d 字节(%q),读结束原因 %v——连接被直接关掉了\n", len(b), string(b), err)
		c2, _ := net.Dial("tcp", addr)
		fmt.Fprintf(c2, "GET /ok HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")
		_, body := readResp(bufio.NewReader(c2))
		fmt.Printf("  之后再请求 /ok:正常返回 %q(进程没有崩溃)\n", body)
		time.Sleep(50 * time.Millisecond)
		first := strings.SplitN(strings.TrimSpace(logb.String()), "\n", 2)[0]
		fmt.Printf("  服务器日志第一行:%s\n", first)
	case "cancel":
		done := make(chan string, 1)
		addr, stop := startServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			t0 := time.Now()
			select {
			case <-r.Context().Done(): done <- fmt.Sprintf("handler 在 %.0f ms 后发现 r.Context() 已取消:%v", float64(time.Since(t0).Microseconds())/1000, r.Context().Err())
			case <-time.After(2 * time.Second): done <- "handler 一直等到 2 秒(没有收到取消)"
			}
		}), nil, io.Discard)
		defer stop()
		c, _ := net.Dial("tcp", addr)
		fmt.Fprintf(c, "GET / HTTP/1.1\r\nHost: x\r\n\r\n")
		time.Sleep(100 * time.Millisecond)
		c.Close()
		fmt.Printf("  客户端在请求发出 100 ms 后直接关闭连接:%s\n", <-done)
	}
}
'''
d = gdir('hs1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(m):
    p = subprocess.run([str(d / 'app'), m], capture_output=True, text=True, timeout=120)
    return tidy(p.stdout + p.stderr)
print('== 一:一个连接的状态变化(Go 1.27.1,arm64 macOS;用 ConnState 回调记录)')
print(run('states'))
print('== 二:每个连接一个 goroutine')
print(run('goroutines'))
print('== 三:响应头是怎么自动生成的')
print(run('headers'))
print('== 四:Handler 里 panic')
print(run('panic'))
print('== 五:客户端断开,Handler 怎么知道')
print(run('cancel'))
print('== 六:net/http 文档里 Server 与 ConnState 的几句话')
r, o = go(gdir('doc1'), 'doc', 'net/http.ConnState')
print('  ' + ' '.join(l.strip() for l in o.split('\n')[3:12] if l.strip()))
r, o = go(gdir('doc1'), 'doc', 'net/http.Server.Serve')
print('  ' + ' '.join(l.strip() for l in o.split('\n')[3:12] if l.strip()))
sp = GOROOT + '/src/net/http/server.go'
sl = open(sp).read().split('\n')
for pat in ('func (cr *connReader) startBackgroundRead() {', '\tgo cr.backgroundRead()', 'w.conn.r.startBackgroundRead()'):
    i = next(i for i, l in enumerate(sl) if pat in l)
    print(f'  server.go:{i + 1}: {sl[i].strip()}')
