import sys, os, subprocess, time, socket; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n51')
SRC = """package main
import ("fmt"; "io"; "os"; "github.com/gin-gonic/gin")
func main() {
	r := gin.New()
	r.HandleMethodNotAllowed = os.Getenv("MNA") == "1"
	h := func(name string) gin.HandlerFunc { return func(c *gin.Context) { b, _ := io.ReadAll(c.Request.Body); c.Header("X-Handler", name); c.String(200, "%s: method=%s path=%s body=%q", name, c.Request.Method, c.FullPath(), b) } }
	r.GET("/hello", h("hello"))
	r.Handle("PURGE", "/cache/*key", h("purge"))
	r.Handle("PROPFIND", "/dav/:name", h("propfind"))
	r.Handle("REPORT", "/dav/:name", h("report"))
	r.Any("/any", h("any"))
	r.Match([]string{"GET", "POST"}, "/m", h("match"))
	r.OPTIONS("/cors", func(c *gin.Context) { c.Header("Allow", "GET, POST, OPTIONS"); c.Status(204) })
	r.HEAD("/headonly", func(c *gin.Context) { c.Header("X-Handler", "headonly"); c.String(200, "这段正文 HEAD 不会发出") })
	r.GET("/headonly", h("getonly"))
	fmt.Println("路由表(Routes()):")
	for _, ri := range r.Routes() { fmt.Printf("  %-8s %s\\n", ri.Method, ri.Path) }
	r.Run(os.Args[1])
}"""
d = gin_dir('n51', SRC); crc, cout = go(d, 'build', '-o', 'app'); assert crc == 0, cout
def wait_tcp(port):
    for _ in range(100):
        try: socket.create_connection(('127.0.0.1', port), 0.1).close(); return True
        except Exception: time.sleep(0.05)
def curl(*a):
    p = subprocess.run(['curl', '-sS', '-m', '5', '-i', *a], capture_output=True, text=True)
    t = (p.stdout + p.stderr).replace('\r', '')
    head, _, body = t.partition('\n\n'); hl = head.split('\n')
    keep = [hl[0]] + [l for l in hl[1:] if l.split(':')[0].lower() in ('allow', 'x-handler', 'content-length', 'content-type', 'location')]
    return ' | '.join(keep) + (' || 正文: ' + body.strip().replace('\n', ' ') if body.strip() else ' || 无正文')
def run(env_extra, port):
    env = genv(GIN_MODE='release'); env.update(env_extra)
    p = subprocess.Popen([str(d / 'app'), f'127.0.0.1:{port}'], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True); assert wait_tcp(port); return p
U = 'http://127.0.0.1:9761'
p = run({}, 9761)
print('== 一:自定义 HTTP 方法(PURGE、PROPFIND、REPORT)用 Handle 注册,真实 curl 请求')
for a in [['-X', 'PURGE', U + '/cache/a/b.png'], ['-X', 'PROPFIND', U + '/dav/folder', '-d', '<xml/>'], ['-X', 'REPORT', U + '/dav/folder'], ['-X', 'PURGE', U + '/dav/folder']]:
    print('  curl', ' '.join(x.replace(U, '') for x in a), '→', curl(*a))
print('== 二:Any 与 Match:Any 注册 9 个方法(含 CONNECT、TRACE),Match 只注册指定的;路由表里的方法')
for a in [['-X', 'TRACE', U + '/any'], ['-X', 'DELETE', U + '/any'], ['-X', 'PATCH', U + '/m'], ['-X', 'POST', U + '/m', '-d', 'x'], ['-X', 'PUT', U + '/m']]:
    print('  curl', ' '.join(x.replace(U, '') for x in a), '→', curl(*a))
print('== 三:HEAD、OPTIONS 与方法名大小写:只注册了 GET 的路径,HEAD 与 OPTIONS 都是 404;lowercase 的 get 也是 404;HEAD 路由的正文不会发出')
for a in [['-I', U + '/hello'], ['-X', 'OPTIONS', U + '/hello'], ['-X', 'get', U + '/hello'], ['-X', 'OPTIONS', U + '/cors'], ['-I', U + '/headonly'], [U + '/headonly']]:
    print('  curl', ' '.join(x.replace(U, '') for x in a), '→', curl(*a))
p.terminate(); out, _ = p.communicate(timeout=10)
print('  服务端启动时打印的路由表:'); [print('    ' + l) for l in out.strip().split('\n')[1:] if l.strip()]
print('== 四:打开 HandleMethodNotAllowed 之后:Allow 头里有自定义方法,顺序是各方法第一次注册的顺序')
p = run({'MNA': '1'}, 9762); U = 'http://127.0.0.1:9762'
for a in [['-X', 'DELETE', U + '/dav/folder'], ['-X', 'GET', U + '/cache/x'], ['-X', 'DELETE', U + '/any'], ['-X', 'DELETE', U + '/m'], ['-X', 'PURGE', U + '/hello']]:
    print('  curl', ' '.join(x.replace(U, '') for x in a), '→', curl(*a))
p.terminate(); p.wait()
