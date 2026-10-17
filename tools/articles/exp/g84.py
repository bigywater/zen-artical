import sys, os, re, time, statistics, subprocess, threading, signal as sig, socket, http.client; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g84')
SRC = r'''
package main

import (
	"context"
	"fmt"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

func main() {
	mode := os.Args[1]
	port := os.Args[2]
	mux := http.NewServeMux()
	mux.HandleFunc("/slow", func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(2 * time.Second)
		fmt.Fprint(w, "slow done")
	})
	mux.HandleFunc("/hijack", func(w http.ResponseWriter, r *http.Request) {
		c, _, _ := w.(http.Hijacker).Hijack()
		go func() { time.Sleep(2 * time.Second); c.Write([]byte("HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\nhijack done")); c.Close() }()
	})
	srv := &http.Server{Handler: mux}
	ln, _ := net.Listen("tcp", "127.0.0.1:"+port)
	t0 := time.Now()
	logf := func(f string, a ...any) { fmt.Printf("  [服务进程 +%4.0f ms] "+f+"\n", append([]any{float64(time.Since(t0).Microseconds()) / 1000}, a...)...) }
	switch mode {
	case "nohandler":
		logf("没有处理信号,开始服务")
		srv.Serve(ln)
	case "shutdown", "shutdown-short":
		ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
		defer stop()
		go srv.Serve(ln)
		logf("开始服务,等待 SIGINT/SIGTERM")
		<-ctx.Done()
		stop()
		logf("收到信号,调用 srv.Shutdown")
		to := 10 * time.Second
		if mode == "shutdown-short" { to = 500 * time.Millisecond }
		sc, cancel := context.WithTimeout(context.Background(), to)
		defer cancel()
		err := srv.Shutdown(sc)
		logf("Shutdown 返回:%v", err)
	}
}
'''
d = gdir('sg1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o

def req(port, path, out, key, hdr_conn=None):
    t0 = time.time()
    try:
        c = http.client.HTTPConnection('127.0.0.1', port, timeout=8)
        c.request('GET', path)
        r = c.getresponse(); b = r.read()
        out[key] = f'{time.time() - t0:.2f} 秒后收到 {r.status} {b.decode()!r}'
    except Exception as e:
        out[key] = f'{time.time() - t0:.2f} 秒后失败:{type(e).__name__}: {str(e)[:60]}'

def scenario(mode, port, path, sigdelay=0.5, after_probe=True, extra_paths=()):
    p = subprocess.Popen([str(d / 'app'), mode, str(port)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for _ in range(100):
        try:
            socket.create_connection(('127.0.0.1', port), timeout=0.2).close(); break
        except OSError:
            time.sleep(0.05)
    time.sleep(0.2)
    res = {}
    t = threading.Thread(target=req, args=(port, path, res, 'in-flight')); t.start()
    time.sleep(sigdelay)
    t0 = time.time()
    p.send_signal(sig.SIGTERM)
    time.sleep(0.2)
    if after_probe:
        # 信号之后新来的请求
        r2 = {}; req(port, '/slow', r2, 'new'); res['signal 之后的新请求'] = r2['new']
    t.join()
    try:
        rc = p.wait(timeout=10)
    except subprocess.TimeoutExpired:
        p.kill(); rc = 'timeout'
    elapsed = time.time() - t0
    out = p.stdout.read().rstrip()
    return res, rc, elapsed, out

print('== 一:不处理信号:收到 SIGTERM 时正在处理的请求怎么样(Go 1.27.1,macOS;服务进程是单独的 Go 程序,由本脚本发 SIGTERM)')
res, rc, el, out = scenario('nohandler', 19601, '/slow')
print(f'  客户端发出一个要处理 2 秒的 /slow 请求,0.5 秒后给服务进程发 SIGTERM:')
print(f'    客户端的这个请求:{res["in-flight"]}')
print(f'    SIGTERM 之后新发的请求:{res["signal 之后的新请求"]}')
print(f'    服务进程退出码 {rc}(负数表示被信号杀死),发信号后 {el:.2f} 秒内退出')
print('== 二:signal.NotifyContext + srv.Shutdown(10 秒超时)')
res, rc, el, out = scenario('shutdown', 19602, '/slow')
print(f'    客户端的这个请求:{res["in-flight"]}')
print(f'    SIGTERM 之后新发的请求:{res["signal 之后的新请求"]}')
print(f'    服务进程退出码 {rc},发信号后 {el:.2f} 秒退出')
print(out)
print('== 三:Shutdown 的超时比请求短(500 ms 对 2 秒的请求)')
res, rc, el, out = scenario('shutdown-short', 19603, '/slow', after_probe=False)
print(f'    客户端的这个请求:{res["in-flight"]}')
print(f'    服务进程退出码 {rc},发信号后 {el:.2f} 秒退出')
print(out)
print('== 四:被 Hijack 的连接(WebSocket 一类)Shutdown 不会等')
res, rc, el, out = scenario('shutdown', 19604, '/hijack', after_probe=False)
print(f'    客户端的这个请求:{res["in-flight"]}')
print(f'    服务进程退出码 {rc},发信号后 {el:.2f} 秒退出')
print(out)
print('== 五:文档:Server.Shutdown')
r, o = go(gdir('doc1'), 'doc', 'net/http.Server.Shutdown')
print('  ' + ' '.join(l.strip() for l in o.split('\n')[3:18] if l.strip()))
