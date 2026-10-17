import sys, os, subprocess, time, socket, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n52')
SRC = """package main
import ("fmt"; "log"; "os"; "runtime/debug"; "sync"; "time"; "github.com/gin-gonic/gin")
// safeGo:在 goroutine 里运行 fn,panic 时记录栈并把错误交给 onErr,而不是让进程崩溃
func safeGo(onErr func(any), fn func()) {
	go func() {
		defer func() { if e := recover(); e != nil { log.Printf("[safeGo] 捕获 panic: %v\\n%s", e, firstLines(string(debug.Stack()), 6)); if onErr != nil { onErr(e) } } }()
		fn()
	}()
}
func firstLines(s string, n int) string { c := 0; for i, ch := range s { if ch == '\\n' { c++; if c == n { return s[:i] } } }; return s }
func main() {
	r := gin.Default()
	r.GET("/ok", func(c *gin.Context) { c.String(200, "ok") })
	r.GET("/slow", func(c *gin.Context) { time.Sleep(800 * time.Millisecond); c.String(200, "slow done") })
	r.GET("/direct", func(c *gin.Context) { panic("handler 里直接 panic") })
	r.GET("/go", func(c *gin.Context) {
		go func() { panic("handler 起的 goroutine 里 panic") }()
		time.Sleep(200 * time.Millisecond); c.String(200, "这一行没有机会返回")
	})
	r.GET("/go-after", func(c *gin.Context) {
		go func() { time.Sleep(300 * time.Millisecond); panic("handler 返回之后 goroutine 才 panic") }()
		c.String(200, "已返回")
	})
	r.GET("/guard", func(c *gin.Context) {
		var wg sync.WaitGroup; wg.Add(1); var perr any
		go func() { defer wg.Done(); defer func() { perr = recover() }(); panic("goroutine 里的 panic,自己 recover") }()
		wg.Wait()
		if perr != nil { c.String(500, "goroutine panic 已被捕获:%v", perr); return }
		c.String(200, "ok")
	})
	r.GET("/safego", func(c *gin.Context) {
		done := make(chan any, 1)
		safeGo(func(e any) { done <- e }, func() { var m map[string]int; m["x"] = 1 })
		select { case e := <-done: c.String(500, "后台任务失败:%v", e); case <-time.After(time.Second): c.String(200, "ok") }
	})
	r.GET("/safego-after", func(c *gin.Context) {
		safeGo(nil, func() { time.Sleep(200 * time.Millisecond); panic("handler 已返回,后台任务 panic") })
		c.String(200, "已返回")
	})
	fmt.Println("启动,pid", os.Getpid())
	r.Run(os.Args[1])
}"""
d = gin_dir('n52', SRC); crc, cout = go(d, 'build', '-o', 'app'); assert crc == 0, cout
def wait_tcp(port):
    for _ in range(100):
        try: socket.create_connection(('127.0.0.1', port), 0.1).close(); return True
        except Exception: time.sleep(0.05)
def curl(url):
    p = subprocess.run(['curl', '-sS', '-m', '3', '-w', ' [HTTP %{http_code}]', url], capture_output=True, text=True)
    return (p.stdout + p.stderr).strip().replace('\n', ' ')
def start(port): 
    p = subprocess.Popen([str(d / 'app'), f'127.0.0.1:{port}'], env=genv(GIN_MODE='release'), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True); assert wait_tcp(port); return p
def finish(p):
    if p.poll() is None: p.terminate(); out, _ = p.communicate(timeout=5); return '仍在运行(由我终止)', out
    out, _ = p.communicate(); return f'进程已退出,退出码 {p.returncode}', out
print('== 一:handler 里直接 panic 与 goroutine 里 panic 的区别(Default = Logger + Recovery)')
port = 9771
for route in ['/direct', '/go', '/go-after', '/guard']:
    port += 1; p = start(port)
    t0 = time.time(); res = curl(f'http://127.0.0.1:{port}{route}'); dt = time.time() - t0
    time.sleep(0.6); alive = p.poll() is None
    res2 = curl(f'http://127.0.0.1:{port}/ok') if alive else '(进程已退出,连接被拒绝)'
    st, out = finish(p)
    print(f'  GET {route:10} → {res}(耗时 {dt*1000:.0f} ms);之后:{st};再请求 /ok:{res2}')
print('== 二:崩溃时进程输出的是什么(goroutine 里的 panic,Recovery 没有机会):panic 值、goroutine 栈、创建它的位置、退出码 2')
p = start(9780); curl('http://127.0.0.1:9780/go-after'); time.sleep(0.6); st, out = finish(p)
ls = [l for l in out.split('\n') if l.strip() and not l.startswith('启动')]
keep = [l for l in ls if l.startswith('panic:') or 'goroutine' in l or 'main.main' in l or 'created by' in l or l.startswith('exit')]
import re
for l in keep[:8]: print('    ' + re.sub(r'\(0x[0-9a-f, x]+\)', '(…)', re.sub(r'\+0x[0-9a-f]+', '', l)).strip().replace(str(d), '<dir>')[:130])
print('    ' + st)
print('== 三:无辜的在途请求也会一起死:/slow 要 800ms,200ms 时另一个请求触发 goroutine panic;对照:触发的是 handler 里直接 panic')
for trig in ['/go-after', '/direct']:
    port += 1; p = start(port); res = {}
    def slow(): res['r'] = curl(f'http://127.0.0.1:{port}/slow')
    th = threading.Thread(target=slow); th.start(); time.sleep(0.2); curl(f'http://127.0.0.1:{port}{trig}'); th.join(); time.sleep(0.3)
    st, out = finish(p); print(f'  触发 {trig:10} → 同时在途的 /slow:{res["r"]};{st}')
print('== 四:安全写法:在 goroutine 里 recover(记录栈、把错误交回 handler);handler 返回之后的后台任务也一样')
for route in ['/safego', '/safego-after']:
    port += 1; p = start(port); res = curl(f'http://127.0.0.1:{port}{route}'); time.sleep(0.5)
    res2 = curl(f'http://127.0.0.1:{port}/ok'); st, out = finish(p)
    print(f'  GET {route:14} → {res};之后再请求 /ok:{res2};{st}')
    for l in out.split('\n'):
        if '[safeGo]' in l: print('      进程日志:' + l.split('[safeGo]')[1].strip()[:90])
