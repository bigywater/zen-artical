import sys, os, subprocess, time, socket, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
tee('n48')
SRC = """package main
import ("crypto/ecdsa"; "crypto/elliptic"; "crypto/rand"; "crypto/x509"; "crypto/x509/pkix"; "encoding/pem"; "fmt"; "math/big"; "net"; "os"; "path/filepath"; "time"; "github.com/gin-gonic/gin")
func mkcert(dir string) (string, string) {
	k, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	tpl := &x509.Certificate{SerialNumber: big.NewInt(1), Subject: pkix.Name{CommonName: "localhost"}, NotBefore: time.Now().Add(-time.Hour), NotAfter: time.Now().Add(24 * time.Hour), KeyUsage: x509.KeyUsageDigitalSignature, ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth}, DNSNames: []string{"localhost"}, IPAddresses: []net.IP{net.ParseIP("127.0.0.1")}}
	der, _ := x509.CreateCertificate(rand.Reader, tpl, tpl, &k.PublicKey, k)
	kb, _ := x509.MarshalECPrivateKey(k)
	cf, kf := filepath.Join(dir, "c.pem"), filepath.Join(dir, "k.pem")
	os.WriteFile(cf, pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: der}), 0o600)
	os.WriteFile(kf, pem.EncodeToMemory(&pem.Block{Type: "EC PRIVATE KEY", Bytes: kb}), 0o600)
	return cf, kf
}
func main() {
	mode, addr, dir := os.Args[1], os.Args[2], os.Args[3]
	r := gin.New()
	r.GET("/info", func(c *gin.Context) {
		tls := "无"; if c.Request.TLS != nil { tls = fmt.Sprintf("版本0x%x ALPN=%q", c.Request.TLS.Version, c.Request.TLS.NegotiatedProtocol) }
		c.String(200, "Proto=%s ProtoMajor=%d TLS=%s ClientIP=%q RemoteAddr=%q", c.Request.Proto, c.Request.ProtoMajor, tls, c.ClientIP(), c.Request.RemoteAddr)
	})
	r.GET("/h2", func(c *gin.Context) {
		p := c.Writer.Pusher(); ps := "Pusher() 为 nil"
		if p != nil { ps = fmt.Sprintf("Push 返回 %v", p.Push("/info", nil)) }
		c.String(200, "%s", ps)
	})
	r.GET("/hj", func(c *gin.Context) {
		defer func() { if e := recover(); e != nil { c.String(200, "Hijack panic: %v", e) } }()
		conn, _, err := c.Writer.Hijack()
		if err != nil { c.String(200, "Hijack 返回错误: %v", err); return }
		msg := "Hijack 成功(HTTP/1.1)"; conn.Write([]byte(fmt.Sprintf("HTTP/1.1 200 OK\\r\\nContent-Length: %d\\r\\nConnection: close\\r\\n\\r\\n%s", len(msg), msg))); conn.Close()
	})
	var err error
	switch mode {
	case "plain": err = r.Run(addr)
	case "h2c": r.UseH2C = true; err = r.Run(addr)
	case "tls": cf, kf := mkcert(dir); err = r.RunTLS(addr, cf, kf)
	case "badtls": err = r.RunTLS(addr, filepath.Join(dir, "nope.pem"), filepath.Join(dir, "nope.key"))
	case "unix": r.SetTrustedProxies(nil); err = r.RunUnix(addr)
	}
	fmt.Println("服务结束:", err)
}"""
d = gin_dir('n48', SRC); crc, cout = go(d, 'build', '-o', 'app'); assert crc == 0, cout
tmp = pathlib.Path(d) / 'run'; tmp.mkdir(exist_ok=True)
def wait_tcp(port):
    for _ in range(100):
        try: socket.create_connection(('127.0.0.1', port), 0.1).close(); return True
        except Exception: time.sleep(0.05)
    return False
def serve(mode, port):
    return subprocess.Popen([str(d / 'app'), mode, f'127.0.0.1:{port}', str(tmp)], env=genv(GIN_MODE='release'), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
def curl(*a):
    p = subprocess.run(['curl', '-sS', '-m', '5', *a], capture_output=True, text=True)
    return (p.stdout + p.stderr).strip().replace('\n', ' ')
W = '[%{http_version}] %{http_code} '
print('== 一:Run / RunTLS / RunUnix 的源码:都是 http.Server{Handler: engine.Handler()},UseH2C 才会在 Handler() 里套 h2c')
gfunc('gin.go', 'Handler'); gfunc('gin.go', 'RunTLS')
print('== 二:明文端口:HTTP/1.1 正常;HTTP/2 prior knowledge(curl --http2-prior-knowledge)在没开 UseH2C 时失败,开了之后成功;同一端口 HTTP/1.1 仍可用')
for mode, port in [('plain', 9751), ('h2c', 9752)]:
    p = serve(mode, port); assert wait_tcp(port)
    print(f'  [{mode}]')
    print('    curl --http1.1:           ', curl('-w', W, '--http1.1', f'http://127.0.0.1:{port}/info'))
    print('    curl --http2-prior-knowledge:', curl('-w', W, '--http2-prior-knowledge', f'http://127.0.0.1:{port}/info'))
    print('    curl --http2(带 Upgrade: h2c): ', curl('-w', W, '--http2', f'http://127.0.0.1:{port}/info'))
    p.terminate(); p.wait()
print('== 三:RunTLS:证书是程序启动时生成的自签名 ECDSA 证书;curl 协商出 HTTP/2,强制 --http1.1 则是 HTTP/1.1;handler 里看到的 Proto / TLS 版本 / ALPN')
p = serve('tls', 9753); assert wait_tcp(9753); time.sleep(0.2)
print('    curl -k(默认):            ', curl('-k', '-w', W, 'https://127.0.0.1:9753/info'))
print('    curl -k --http1.1:         ', curl('-k', '-w', W, '--http1.1', 'https://127.0.0.1:9753/info'))
print('    curl -k --tlsv1.1 --tls-max 1.1:', curl('-k', '-w', W, '--tlsv1.1', '--tls-max', '1.1', 'https://127.0.0.1:9753/info'))
print('    curl 不加 -k(证书不受信任):', curl('-w', W, 'https://127.0.0.1:9753/info'))
print('    HTTP/2 下的 Pusher:         ', curl('-k', '-w', W, 'https://127.0.0.1:9753/h2'))
print('    HTTP/2 下的 Hijack:         ', curl('-k', '-w', W, 'https://127.0.0.1:9753/hj'))
print('    HTTP/1.1 下的 Pusher:       ', curl('-k', '-w', W, '--http1.1', 'https://127.0.0.1:9753/h2'))
print('    HTTP/1.1 下的 Hijack:       ', curl('-k', '-w', W, '--http1.1', 'https://127.0.0.1:9753/hj'))
p.terminate(); p.wait()
print('== 四:证书文件不存在时 RunTLS 立刻返回错误(不会静默起一个不安全的服务)')
p = serve('badtls', 9754); out, _ = p.communicate(timeout=10); print('   ', out.strip().replace(str(tmp), '<tmp>'))
print('== 五:unix socket:RunUnix;ClientIP 对 unix socket 的连接一律信任转发头(即使 SetTrustedProxies(nil));进程被信号杀死时 socket 文件会残留')
sock = str(tmp / 'g.sock')
p = subprocess.Popen([str(d / 'app'), 'unix', sock, str(tmp)], env=genv(GIN_MODE='release'), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
for _ in range(100):
    if os.path.exists(sock): break
    time.sleep(0.05)
print('    socket 文件存在:', os.path.exists(sock), ' 权限:', oct(os.stat(sock).st_mode & 0o777))
print('    无头:                     ', curl('--unix-socket', sock, 'http://localhost/info'))
print('    X-Forwarded-For: 1.2.3.4:  ', curl('--unix-socket', sock, '-H', 'X-Forwarded-For: 1.2.3.4', 'http://localhost/info'))
print('    X-Forwarded-For: 9.9.9.9, 1.2.3.4:', curl('--unix-socket', sock, '-H', 'X-Forwarded-For: 9.9.9.9, 1.2.3.4', 'http://localhost/info'))
p.terminate(); p.wait(); time.sleep(0.2)
print('    SIGTERM 之后 socket 文件仍存在:', os.path.exists(sock), '(进程被信号杀死,defer os.Remove 没有机会执行)')
p2 = subprocess.Popen([str(d / 'app'), 'unix', sock, str(tmp)], env=genv(GIN_MODE='release'), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
out2, _ = p2.communicate(timeout=10); print('    在残留的 socket 文件上重启:', out2.strip().replace(str(tmp), '<tmp>'))
os.remove(sock)
