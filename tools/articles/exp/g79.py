import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g79')
SRC = r'''
package main

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"fmt"
	"io"
	"log"
	"math/big"
	"net"
	"net/http"
	"os"
	"sync"
	"sync/atomic"
	"time"
)

func cert() tls.Certificate {
	k, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	tpl := &x509.Certificate{SerialNumber: big.NewInt(1), Subject: pkix.Name{CommonName: "localhost"}, NotBefore: time.Now().Add(-time.Hour), NotAfter: time.Now().Add(time.Hour), DNSNames: []string{"localhost"}, IPAddresses: []net.IP{net.ParseIP("127.0.0.1")}, KeyUsage: x509.KeyUsageDigitalSignature, ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth}}
	der, _ := x509.CreateCertificate(rand.Reader, tpl, tpl, &k.PublicKey, k)
	return tls.Certificate{Certificate: [][]byte{der}, PrivateKey: k}
}

type srv struct {
	addr   string
	newc   atomic.Int64
	cur    atomic.Int64
	maxCur atomic.Int64
	stop   func()
}

func start(configure func(*http.Server), tlsOn bool, hold time.Duration) *srv {
	s := &srv{}
	ln, _ := net.Listen("tcp", "127.0.0.1:0")
	hs := &http.Server{Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n := s.cur.Add(1)
		for { m := s.maxCur.Load(); if n <= m || s.maxCur.CompareAndSwap(m, n) { break } }
		time.Sleep(hold)
		s.cur.Add(-1)
		fmt.Fprintf(w, "proto=%s", r.Proto)
	}), ConnState: func(c net.Conn, st http.ConnState) { if st == http.StateNew { s.newc.Add(1) } }}
	hs.ErrorLog = log.New(io.Discard, "", 0)
	if tlsOn { hs.TLSConfig = &tls.Config{Certificates: []tls.Certificate{cert()}} }
	if configure != nil { configure(hs) }
	if tlsOn { go hs.ServeTLS(ln, "", "") } else { go hs.Serve(ln) }
	s.addr = ln.Addr().String()
	s.stop = func() { hs.Close() }
	return s
}

func get(c *http.Client, url string) string {
	resp, err := c.Get(url)
	if err != nil { return "错误:" + err.Error() }
	b, _ := io.ReadAll(resp.Body); resp.Body.Close()
	return fmt.Sprintf("客户端看到 resp.Proto=%s;服务端看到 %s", resp.Proto, string(b))
}

func burst(c *http.Client, url string, n int) time.Duration {
	var wg sync.WaitGroup
	t0 := time.Now()
	for i := 0; i < n; i++ { wg.Add(1); go func() { defer wg.Done(); resp, err := c.Get(url); if err == nil { io.Copy(io.Discard, resp.Body); resp.Body.Close() } }() }
	wg.Wait()
	return time.Since(t0)
}

func main() {
	newInsecure := func() *tls.Config { return &tls.Config{InsecureSkipVerify: true} }
	switch os.Args[1] {
	case "negotiate":
		s := start(nil, true, 0)
		fmt.Printf("  HTTPS 服务器(默认配置)+ DefaultTransport 的副本(只改 TLSClientConfig 跳过证书校验):%s\n", get(&http.Client{Transport: func() *http.Transport { t := http.DefaultTransport.(*http.Transport).Clone(); t.TLSClientConfig = newInsecure(); return t }()}, "https://"+s.addr))
		fmt.Printf("  自己写 &http.Transport{TLSClientConfig: 新建的配置}(没有 ForceAttemptHTTP2):%s\n", get(&http.Client{Transport: &http.Transport{TLSClientConfig: newInsecure()}}, "https://"+s.addr))
		fmt.Printf("  同上并设 ForceAttemptHTTP2: true:%s\n", get(&http.Client{Transport: &http.Transport{TLSClientConfig: newInsecure(), ForceAttemptHTTP2: true}}, "https://"+s.addr))
		s.stop()
		s2 := start(func(hs *http.Server) { hs.TLSNextProto = map[string]func(*http.Server, *tls.Conn, http.Handler){} }, true, 0)
		fmt.Printf("  服务器把 TLSNextProto 设为空 map(关闭 HTTP/2)+ 默认配置的客户端:%s\n", get(&http.Client{Transport: func() *http.Transport { t := http.DefaultTransport.(*http.Transport).Clone(); t.TLSClientConfig = newInsecure(); return t }()}, "https://"+s2.addr))
		s2.stop()
		s3 := start(nil, false, 0)
		fmt.Printf("  明文 HTTP(没有 TLS)+ 默认客户端:%s\n", get(http.DefaultClient, "http://"+s3.addr))
		s3.stop()
	case "sharedcfg":
		s := start(nil, true, 0)
		shared := newInsecure()
		fmt.Printf("  共享的 tls.Config 在使用前 NextProtos = %v\n", shared.NextProtos)
		t1 := &http.Transport{TLSClientConfig: shared, ForceAttemptHTTP2: true}
		fmt.Printf("  第一个 Transport(ForceAttemptHTTP2)发一个请求:%s\n", get(&http.Client{Transport: t1}, "https://"+s.addr))
		fmt.Printf("  之后同一个 tls.Config 的 NextProtos = %v(被 Transport 改过了)\n", shared.NextProtos)
		fmt.Printf("  第二个 Transport 用同一个 tls.Config、不设 ForceAttemptHTTP2:%s\n", get(&http.Client{Transport: &http.Transport{TLSClientConfig: shared}}, "https://"+s.addr))
		s.stop()
	case "h2c":
		s := start(func(hs *http.Server) { var p http.Protocols; p.SetHTTP1(true); p.SetUnencryptedHTTP2(true); hs.Protocols = &p }, false, 0)
		var p http.Protocols
		p.SetUnencryptedHTTP2(true)
		c := &http.Client{Transport: &http.Transport{Protocols: &p}}
		fmt.Printf("  明文 TCP 上的 HTTP/2(h2c):Server.Protocols 设 HTTP1 + UnencryptedHTTP2;客户端 Transport.Protocols 只设 UnencryptedHTTP2:%s\n", get(c, "http://"+s.addr))
		s.stop()
	case "streams":
		run1 := func(label string, configure func(*http.Server), mk func() *http.Client, tlsOn bool) {
			s := start(configure, tlsOn, 200*time.Millisecond)
			c := mk()
			get(c, "https://"+s.addr) // 先发一个请求把连接建好
			base := s.newc.Load()
			s.maxCur.Store(0)
			d := burst(c, "https://"+s.addr, 300)
			fmt.Printf("  %-44s 预热后 300 个并发请求(handler 各 200 ms):新增 TCP 连接 %d 个、同时在跑的 handler 最多 %d 个、总用时 %.0f ms\n", label, s.newc.Load()-base, s.maxCur.Load(), float64(d.Microseconds())/1000)
			s.stop()
		}
		h2c := func() *http.Client { return &http.Client{Transport: &http.Transport{TLSClientConfig: newInsecure(), ForceAttemptHTTP2: true}} }
		run1("HTTP/2,服务端默认 MaxConcurrentStreams", nil, h2c, true)
		run1("HTTP/2,Server.HTTP2.MaxConcurrentStreams = 10", func(hs *http.Server) { hs.HTTP2 = &http.HTTP2Config{MaxConcurrentStreams: 10} }, h2c, true)
		run1("HTTP/1.1(服务器关闭 h2)", func(hs *http.Server) { hs.TLSNextProto = map[string]func(*http.Server, *tls.Conn, http.Handler){} }, func() *http.Client { return &http.Client{Transport: &http.Transport{TLSClientConfig: newInsecure()}} }, true)
		// 不预热:第一批并发请求同时拨号
		s := start(nil, true, 200*time.Millisecond)
		c := h2c()
		d := burst(c, "https://"+s.addr, 300)
		fmt.Printf("  %-44s 不预热直接 300 个并发请求:服务端看到 TCP 连接 %d 个、总用时 %.0f ms\n", "HTTP/2,服务端默认(冷启动)", s.newc.Load(), float64(d.Microseconds())/1000)
		s.stop()
		// 客户端 StrictMaxConcurrentRequests = true,服务端限制 10 个流
		s = start(func(hs *http.Server) { hs.HTTP2 = &http.HTTP2Config{MaxConcurrentStreams: 10} }, true, 200*time.Millisecond)
		c = &http.Client{Timeout: 5 * time.Second, Transport: &http.Transport{TLSClientConfig: newInsecure(), ForceAttemptHTTP2: true, HTTP2: &http.HTTP2Config{StrictMaxConcurrentRequests: true}}}
		get(c, "https://"+s.addr)
		base := s.newc.Load()
		var ok, fail atomic.Int64
		var wg sync.WaitGroup
		for i := 0; i < 30; i++ { wg.Add(1); go func() { defer wg.Done(); resp, err := c.Get("https://" + s.addr); if err != nil { fail.Add(1); return }; io.Copy(io.Discard, resp.Body); resp.Body.Close(); ok.Add(1) }() }
		wg.Wait()
		fmt.Printf("  服务端限 10 个流 + 客户端 StrictMaxConcurrentRequests = true:30 个并发请求(各 200 ms,客户端超时 5 秒):成功 %d 个、失败 %d 个;新增 TCP 连接 %d 个、同时在跑的 handler 最多 %d 个\n", ok.Load(), fail.Load(), s.newc.Load()-base, s.maxCur.Load())
		s.stop()
	}
}
'''
d = gdir('h2'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(m):
    p = subprocess.run([str(d / 'app'), m], capture_output=True, text=True, timeout=120)
    return tidy(p.stdout + p.stderr)
print('== 一:什么时候会用上 HTTP/2(Go 1.27.1,arm64 macOS;自签名证书)')
print(run('negotiate'))
print('== 一·补:同一个 tls.Config 被多个 Transport 共用的坑')
print(run('sharedcfg'))
print('== 二:不用 TLS 的 HTTP/2(h2c)')
print(run('h2c'))
print('== 三:一个连接上的并发流(同一组实验重复 5 次,给出每项的最小–最大)')
import collections
agg = collections.OrderedDict()
for _ in range(5):
    for line in run('streams').split('\n'):
        m = re.match(r'\s*(.*?)[\s:]+(预热后|不预热直接|30 个并发)', line)
        if not m: continue
        key = m.group(1).strip()
        nums = {k: [int(x) for x in re.findall(pat, line)] for k, pat in (('conn', r'(?:新增 TCP 连接|看到 TCP 连接|新增 TCP 连接) (\d+)'), ('max', r'最多 (\d+)'), ('ms', r'总用时 (\d+) ms'), ('ok', r'成功 (\d+)'), ('fail', r'失败 (\d+)'))}
        a = agg.setdefault(key, collections.defaultdict(list))
        for k, v in nums.items():
            if v: a[k].append(v[0])
for key, a in agg.items():
    parts = []
    if a['conn']: parts.append(f"TCP 连接 {min(a['conn'])}–{max(a['conn'])} 个")
    if a['max']: parts.append(f"同时在跑的 handler 最多 {min(a['max'])}–{max(a['max'])} 个")
    if a['ms']: parts.append(f"总用时 {min(a['ms'])}–{max(a['ms'])} ms")
    if a['ok'] or a['fail']: parts.append(f"成功 {min(a['ok'])}–{max(a['ok'])} 个、失败 {min(a['fail'])}–{max(a['fail'])} 个")
    print(f'  {key}:' + ';'.join(parts))
print('== 四:文档(go doc net/http.HTTP2Config 与 Protocols)')
r, o = go(gdir('doc1'), 'doc', 'net/http.HTTP2Config')
ls = [l.strip() for l in o.split('\n')]
i = next(i for i, l in enumerate(ls) if l.startswith('// MaxConcurrentStreams optionally'))
print('  ' + ' '.join(x.replace('// ', '', 1) for x in ls[i:i + 5] if x))
i = next(i for i, l in enumerate(ls) if l.startswith('// StrictMaxConcurrentRequests'))
print('  ' + ' '.join(x.replace('// ', '', 1) for x in ls[i:i + 8] if x))
r, o = go(gdir('doc1'), 'doc', 'net/http.Protocols')
ls = [l.strip() for l in o.split('\n')]
for pre in ('- HTTP1 is', '- HTTP2 is', '- UnencryptedHTTP2 is'):
    i = next(i for i, l in enumerate(ls) if l.startswith(pre))
    print('  ' + ' '.join(x for x in ls[i:i + 2] if x))
