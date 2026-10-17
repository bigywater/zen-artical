import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g77')
SRC = r'''
package main

import (
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"runtime"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

type srv struct {
	url    string
	newc   atomic.Int64
	closed atomic.Int64
	stop   func()
}

func start(h http.Handler) *srv {
	s := &srv{}
	ln, _ := net.Listen("tcp", "127.0.0.1:0")
	hs := &http.Server{Handler: h, ConnState: func(c net.Conn, st http.ConnState) {
		switch st { case http.StateNew: s.newc.Add(1); case http.StateClosed: s.closed.Add(1) }
	}}
	go hs.Serve(ln)
	s.url = "http://" + ln.Addr().String()
	s.stop = func() { hs.Close() }
	return s
}

func body(n int) http.Handler {
	b := strings.Repeat("x", n)
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { io.WriteString(w, b) })
}

func newTransport() *http.Transport { return &http.Transport{} }

func main() {
	switch os.Args[1] {
	case "reuse":
		for _, size := range []int{1000, 1 << 20} {
			for _, mode := range []string{"读完并关闭", "只关闭不读", "既不读也不关"} {
				s := start(body(size))
				c := &http.Client{Transport: newTransport()}
				base := runtime.NumGoroutine()
				for i := 0; i < 20; i++ {
					resp, err := c.Get(s.url)
					if err != nil { fmt.Println("  错误:", err); break }
					switch mode {
					case "读完并关闭": io.Copy(io.Discard, resp.Body); resp.Body.Close()
					case "只关闭不读": resp.Body.Close()
					}
				}
				time.Sleep(100 * time.Millisecond)
				fmt.Printf("  响应体 %7d 字节,%-8s:20 个串行请求,服务端新建连接 %2d 个;客户端 goroutine 增加 %d\n", size, mode, s.newc.Load(), runtime.NumGoroutine()-base)
				c.CloseIdleConnections()
				s.stop()
			}
		}
	case "perhost":
		for _, idle := range []int{0, 20} {
			s := start(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { time.Sleep(50 * time.Millisecond); io.WriteString(w, "ok") }))
			tr := newTransport()
			tr.MaxIdleConnsPerHost = idle
			c := &http.Client{Transport: tr}
			burst := func() {
				var wg sync.WaitGroup
				for i := 0; i < 20; i++ {
					wg.Add(1)
					go func() { defer wg.Done(); resp, err := c.Get(s.url); if err == nil { io.Copy(io.Discard, resp.Body); resp.Body.Close() } }()
				}
				wg.Wait()
			}
			burst()
			n1 := s.newc.Load()
			time.Sleep(100 * time.Millisecond)
			burst()
			n2 := s.newc.Load()
			label := map[int]string{0: "默认(0 = 使用 DefaultMaxIdleConnsPerHost)", 20: "MaxIdleConnsPerHost = 20"}[idle]
			fmt.Printf("  %-40s 第一波 20 个并发请求新建连接 %d 个;间隔 100 ms 后第二波 20 个并发请求,又新建 %d 个\n", label, n1, n2-n1)
			c.CloseIdleConnections()
			s.stop()
		}
		fmt.Printf("  http.DefaultMaxIdleConnsPerHost 的值 = %d\n", http.DefaultMaxIdleConnsPerHost)
	case "newtransport":
		s := start(body(10))
		base := runtime.NumGoroutine()
		for i := 0; i < 50; i++ {
			c := &http.Client{Transport: newTransport()} // 每次请求都新建一个 Transport
			resp, _ := c.Get(s.url)
			io.Copy(io.Discard, resp.Body)
			resp.Body.Close()
		}
		time.Sleep(100 * time.Millisecond)
		fmt.Printf("  每个请求新建一个 Transport(并且不 CloseIdleConnections):50 个请求之后,服务端新建连接 %d 个、仍未关闭 %d 个;客户端 goroutine 增加 %d\n", s.newc.Load(), s.newc.Load()-s.closed.Load(), runtime.NumGoroutine()-base)
		s.stop()
	case "shared":
		s2 := start(body(10))
		c := &http.Client{Transport: newTransport()}
		base := runtime.NumGoroutine()
		for i := 0; i < 50; i++ {
			resp, _ := c.Get(s2.url)
			io.Copy(io.Discard, resp.Body)
			resp.Body.Close()
		}
		time.Sleep(100 * time.Millisecond)
		fmt.Printf("  共用一个 Transport:50 个请求之后,服务端新建连接 %d 个、仍未关闭 %d 个;客户端 goroutine 增加 %d\n", s2.newc.Load(), s2.newc.Load()-s2.closed.Load(), runtime.NumGoroutine()-base)
		s2.stop()
	case "timeout":
		ln, _ := net.Listen("tcp", "127.0.0.1:0")
		go func() { for { c, err := ln.Accept(); if err != nil { return }; _ = c } }() // 接受连接但永远不回应
		url := "http://" + ln.Addr().String()
		c := &http.Client{Timeout: 300 * time.Millisecond}
		t0 := time.Now()
		_, err := c.Get(url)
		fmt.Printf("  Client.Timeout = 300 ms,服务器接受连接后不回应:%.0f ms 后返回错误:%v\n", float64(time.Since(t0).Microseconds())/1000, err)
		dc := http.DefaultClient
		fmt.Printf("  http.DefaultClient.Timeout = %v(0 表示没有超时)\n", dc.Timeout)
	case "defaults":
		t := http.DefaultTransport.(*http.Transport)
		fmt.Printf("  DefaultTransport:MaxIdleConns=%d MaxIdleConnsPerHost=%d(0=用默认值 %d) IdleConnTimeout=%v TLSHandshakeTimeout=%v ExpectContinueTimeout=%v ForceAttemptHTTP2=%v MaxConnsPerHost=%d\n", t.MaxIdleConns, t.MaxIdleConnsPerHost, http.DefaultMaxIdleConnsPerHost, t.IdleConnTimeout, t.TLSHandshakeTimeout, t.ExpectContinueTimeout, t.ForceAttemptHTTP2, t.MaxConnsPerHost)
	}
}
'''
d = gdir('hc1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(m):
    p = subprocess.run([str(d / 'app'), m], capture_output=True, text=True, timeout=120)
    return tidy(p.stdout + p.stderr)
print('== 一:响应体不读完、不关闭,连接就回不了池(Go 1.27.1,arm64 macOS;服务端用 ConnState 数新建的连接)')
print(run('reuse'))
print('== 二:MaxIdleConnsPerHost 默认只留 2 个空闲连接')
print(run('perhost'))
print('== 三:每个请求新建一个 Transport')
print(run('newtransport'))
print(run('shared'))
print('== 四:没有超时的客户端')
print(run('timeout'))
print('== 五:DefaultTransport 的默认值')
print(run('defaults'))
