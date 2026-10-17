import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g78')
SRC = r'''
package main

import (
	"bufio"
	"context"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"strings"
	"time"
)

func ms(d time.Duration) string { return fmt.Sprintf("%.0f ms", float64(d.Microseconds())/1000) }

func serve(srv *http.Server) (string, func()) {
	ln, _ := net.Listen("tcp", "127.0.0.1:0")
	srv.ErrorLog = log.New(io.Discard, "", 0)
	go srv.Serve(ln)
	return ln.Addr().String(), func() { srv.Close() }
}

// 返回:服务器关闭连接用了多久(最长等 3 秒)
func waitClosed(c net.Conn) (time.Duration, string) {
	t0 := time.Now()
	c.SetReadDeadline(time.Now().Add(3 * time.Second))
	b, err := io.ReadAll(c)
	if ne, ok := err.(net.Error); ok && ne.Timeout() { return time.Since(t0), "3 秒内服务器没有关闭连接" }
	return time.Since(t0), fmt.Sprintf("服务器关闭了连接,客户端收到 %d 字节", len(b))
}

func main() {
	switch os.Args[1] {
	case "slowloris":
		for _, rht := range []time.Duration{0, 200 * time.Millisecond} {
			addr, stop := serve(&http.Server{Handler: http.NotFoundHandler(), ReadHeaderTimeout: rht})
			c, _ := net.Dial("tcp", addr)
			fmt.Fprintf(c, "GET / HTTP/1.1\r\nHost: x\r\nX-Slow: ") // 请求头只发一半
			d, what := waitClosed(c)
			fmt.Printf("  ReadHeaderTimeout = %-6v 客户端只发了半个请求头就不再发:%s后——%s\n", rht, ms(d), what)
			c.Close(); stop()
		}
	case "write":
		addr, stop := serve(&http.Server{Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			time.Sleep(500 * time.Millisecond)
			_, err := io.WriteString(w, "late")
			fmt.Printf("  handler 睡了 500 ms,写响应时 err = %v\n", err)
			w.(http.Flusher).Flush()
		}), WriteTimeout: 200 * time.Millisecond})
		defer stop()
		c, _ := net.Dial("tcp", addr)
		fmt.Fprintf(c, "GET / HTTP/1.1\r\nHost: x\r\n\r\n")
		d, what := waitClosed(c)
		fmt.Printf("  WriteTimeout = 200 ms,handler 要 500 ms:客户端在 %s 后看到:%s\n", ms(d), what)
		time.Sleep(100 * time.Millisecond)
	case "idle":
		addr, stop := serve(&http.Server{Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { io.WriteString(w, "ok") }), IdleTimeout: 300 * time.Millisecond})
		defer stop()
		c, _ := net.Dial("tcp", addr)
		fmt.Fprintf(c, "GET / HTTP/1.1\r\nHost: x\r\n\r\n")
		br := bufio.NewReader(c)
		for { l, _ := br.ReadString('\n'); if l == "\r\n" { break } }
		io.ReadFull(br, make([]byte, 2))
		t0 := time.Now()
		c.SetReadDeadline(time.Now().Add(3 * time.Second))
		_, err := br.ReadByte()
		fmt.Printf("  IdleTimeout = 300 ms,一个请求完成后连接保持空闲:%s 后服务器关闭了连接(客户端读到 %v)\n", ms(time.Since(t0)), err)
	case "timeouthandler":
		var ctxErr string
		inner := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			select {
			case <-time.After(500 * time.Millisecond): io.WriteString(w, "done")
			case <-r.Context().Done(): ctxErr = fmt.Sprint(r.Context().Err())
			}
		})
		addr, stop := serve(&http.Server{Handler: http.TimeoutHandler(inner, 100*time.Millisecond, "服务超时")})
		defer stop()
		t0 := time.Now()
		resp, err := http.Get("http://" + addr)
		b, _ := io.ReadAll(resp.Body)
		fmt.Printf("  http.TimeoutHandler(100 ms),handler 要 500 ms:%s 后客户端收到 %d %s,body %q(err=%v)\n", ms(time.Since(t0)), resp.StatusCode, http.StatusText(resp.StatusCode), string(b), err)
		time.Sleep(50 * time.Millisecond)
		fmt.Printf("  handler 里 r.Context() 的状态:%v\n", ctxErr)
	case "client":
		// 服务端立刻发响应头,然后慢慢发 body:每 100 ms 一个字节,共 10 个
		addr, stop := serve(&http.Server{Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(200); w.(http.Flusher).Flush()
			for i := 0; i < 10; i++ { io.WriteString(w, "x"); w.(http.Flusher).Flush(); time.Sleep(100 * time.Millisecond) }
		})})
		defer stop()
		for _, mode := range []string{"Client.Timeout=300ms", "Transport.ResponseHeaderTimeout=300ms", "ctx WithTimeout(300ms)"} {
			var c *http.Client
			ctx := context.Background()
			switch mode {
			case "Client.Timeout=300ms": c = &http.Client{Timeout: 300 * time.Millisecond}
			case "Transport.ResponseHeaderTimeout=300ms": c = &http.Client{Transport: &http.Transport{ResponseHeaderTimeout: 300 * time.Millisecond}}
			default:
				c = &http.Client{}
				var cancel context.CancelFunc
				ctx, cancel = context.WithTimeout(ctx, 300*time.Millisecond)
				defer cancel()
			}
			t0 := time.Now()
			req, _ := http.NewRequestWithContext(ctx, "GET", "http://"+addr, nil)
			resp, err := c.Do(req)
			if err != nil { fmt.Printf("  %-36s Do 就失败了:%v\n", mode, err); continue }
			n, err := io.Copy(io.Discard, resp.Body)
			fmt.Printf("  %-36s 响应头立刻到;读 body %s 后结束,读到 %d 字节,err = %v\n", mode, ms(time.Since(t0)), n, err)
		}
	case "dial":
		d := &net.Dialer{Timeout: 300 * time.Millisecond}
		t0 := time.Now()
		_, err := d.Dial("tcp", "10.255.255.1:80")
		fmt.Printf("  Dialer.Timeout = 300 ms,连接 10.255.255.1:80:%s 后返回:%v\n", ms(time.Since(t0)), err)
		_ = strings.Repeat
	}
}
'''
d = gdir('ht1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(m):
    p = subprocess.run([str(d / 'app'), m], capture_output=True, text=True, timeout=120)
    return tidy(p.stdout + p.stderr)
print('== 一:ReadHeaderTimeout 挡住慢速攻击(Go 1.27.1,arm64 macOS)')
print(run('slowloris'))
print('== 二:WriteTimeout 不会取消 Handler')
print(run('write'))
print('== 三:IdleTimeout')
print(run('idle'))
print('== 四:http.TimeoutHandler')
print(run('timeouthandler'))
print('== 五:客户端三种超时,服务端立刻发响应头、之后每 100 ms 发 1 字节(共 10 个)')
print(run('client'))
print('== 六:连接超时')
print(run('dial'))
print('== 七:文档原文')
r, o = go(gdir('doc1'), 'doc', 'net/http.Server')
ls = [l.strip() for l in o.split('\n')]
def grab(prefix, n):
    i = next((i for i, l in enumerate(ls) if l.startswith(prefix)), None)
    return ' '.join(x.replace('// ', '', 1) if x.startswith('//') else x for x in ls[i:i + n] if x) if i is not None else '(未找到)' + prefix
for pre, n in (('// ReadHeaderTimeout is the amount of time', 4), ('// WriteTimeout is the maximum duration', 5), ('// IdleTimeout is the maximum amount of time', 4)):
    print('  ' + grab(pre, n))
