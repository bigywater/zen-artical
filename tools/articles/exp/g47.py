import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g47')
SRC = r'''
package main

import (
	"bytes"
	"fmt"
	"net"
	"os"
	"regexp"
	"runtime"
	"runtime/pprof"
	"sort"
	"strconv"
	"sync"
	"syscall"
	"time"
)

func threads() int { return pprof.Lookup("threadcreate").Count() }

func states() string {
	var b bytes.Buffer
	pprof.Lookup("goroutine").WriteTo(&b, 2)
	re := regexp.MustCompile(`(?m)^goroutine \d+ \[([^\],]+)`)
	m := map[string]int{}
	for _, x := range re.FindAllStringSubmatch(b.String(), -1) { m[x[1]]++ }
	var ks []string
	for k := range m { ks = append(ks, k) }
	sort.Strings(ks)
	s := ""
	for _, k := range ks { s += fmt.Sprintf("[%s]×%d ", k, m[k]) }
	return s
}

func main() {
	mode := os.Args[1]
	n, _ := strconv.Atoi(os.Args[2])
	switch mode {
	case "tcp":
		ln, _ := net.Listen("tcp", "127.0.0.1:0")
		var wg sync.WaitGroup
		go func() {
			for {
				c, err := ln.Accept()
				if err != nil { return }
				wg.Add(1)
				go func() { defer wg.Done(); buf := make([]byte, 16); c.Read(buf); c.Close() }()
			}
		}()
		t0 := threads()
		conns := make([]net.Conn, 0, n)
		for i := 0; i < n; i++ {
			c, err := net.Dial("tcp", ln.Addr().String())
			if err != nil { fmt.Println("拨号失败:", err); break }
			conns = append(conns, c)
		}
		time.Sleep(300 * time.Millisecond)
		fmt.Printf("  %d 条 TCP 连接,服务端每条一个 goroutine 阻塞在 Read 上:NumGoroutine = %d;线程创建数 %d → %d\n", len(conns), runtime.NumGoroutine(), t0, threads())
		fmt.Printf("  goroutine 状态:%s\n", states())
		out, _ := exec_lsof()
		fmt.Printf("  lsof 里属于本进程的 KQUEUE 描述符:%s\n", out)
		for _, c := range conns { c.Close() }
		wg.Wait()
		ln.Close()
	case "pipe-os":
		t0 := threads()
		var wg sync.WaitGroup
		var ws []*os.File
		for i := 0; i < n; i++ {
			r, w, _ := os.Pipe()
			ws = append(ws, w)
			wg.Add(1)
			go func() { defer wg.Done(); buf := make([]byte, 1); r.Read(buf); r.Close() }()
		}
		time.Sleep(300 * time.Millisecond)
		fmt.Printf("  %d 个 goroutine 各自从 os.Pipe 的读端 Read(阻塞):线程创建数 %d → %d;状态 %s\n", n, t0, threads(), states())
		for _, w := range ws { w.Write([]byte{1}); w.Close() }
		wg.Wait()
	case "pipe-syscall":
		t0 := threads()
		var wg sync.WaitGroup
		var ws []int
		for i := 0; i < n; i++ {
			var fds [2]int
			syscall.Pipe(fds[:])
			ws = append(ws, fds[1])
			wg.Add(1)
			go func(rfd int) { defer wg.Done(); buf := make([]byte, 1); syscall.Read(rfd, buf); syscall.Close(rfd) }(fds[0])
		}
		time.Sleep(500 * time.Millisecond)
		fmt.Printf("  %d 个 goroutine 各自对阻塞的 pipe 描述符直接 syscall.Read:线程创建数 %d → %d;状态 %s\n", n, t0, threads(), states())
		for _, w := range ws { syscall.Write(w, []byte{1}); syscall.Close(w) }
		wg.Wait()
	case "deadline":
		ln, _ := net.Listen("tcp", "127.0.0.1:0")
		go func() { c, _ := ln.Accept(); time.Sleep(2 * time.Second); c.Close() }()
		c, _ := net.Dial("tcp", ln.Addr().String())
		c.SetReadDeadline(time.Now().Add(100 * time.Millisecond))
		t0 := time.Now()
		_, err := c.Read(make([]byte, 1))
		fmt.Printf("  SetReadDeadline(100ms) 之后 Read:%.0f ms 后返回,错误:%v;是超时错误?%v\n", float64(time.Since(t0).Microseconds())/1000, err, err.(net.Error).Timeout())
	}
}

func exec_lsof() (string, error) {
	return lsofKqueue()
}
'''
d = gdir('np1'); write(d, {'main.go': SRC, 'lsof.go': r'''
package main

import (
	"fmt"
	"os"
	"os/exec"
	"strings"
)

func lsofKqueue() (string, error) {
	out, err := exec.Command("lsof", "-p", fmt.Sprint(os.Getpid())).Output()
	var ls []string
	for _, l := range strings.Split(string(out), "\n") {
		if strings.Contains(l, "KQUEUE") {
			f := strings.Fields(l)
			ls = append(ls, f[3]+" "+f[4])
		}
	}
	if len(ls) == 0 { return "(没有)", err }
	return strings.Join(ls, ", "), err
}
'''}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(*a, tmo=120):
    p = subprocess.run([str(d / 'app'), *map(str, a)], capture_output=True, text=True, timeout=tmo)
    return (p.stdout + p.stderr).rstrip()
print('== 一:大量连接都阻塞在 Read 上,线程数几乎不变(Go 1.27.1,macOS;网络轮询器在 macOS 上用 kqueue)')
for n in (100, 2000):
    print(run('tcp', n))
print('== 二:同样是“阻塞读”,走不走网络轮询器差别很大:200 个 goroutine 各读一个 pipe')
print(run('pipe-os', 200))
print(run('pipe-syscall', 200))
print('== 三:读写超时靠轮询器里的定时器')
print(run('deadline', 0))
