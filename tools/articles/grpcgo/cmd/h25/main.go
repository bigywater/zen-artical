package main

import (
	"context"
	"crypto"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/rsa"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"fmt"
	"math/big"
	"net"
	"sort"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/peer"
	"google.golang.org/grpc/status"
	. "grpcgo/common"
	"grpcgo/pb"
)

// ---------- 证书工具(全部在内存里生成,不落盘) ----------

type ca struct {
	cert *x509.Certificate
	key  *ecdsa.PrivateKey
	pool *x509.CertPool
}

var serial atomic.Int64

func newCA(name string) *ca {
	key, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	tpl := &x509.Certificate{
		SerialNumber: big.NewInt(serial.Add(1)), Subject: pkix.Name{CommonName: name},
		NotBefore: time.Now().Add(-time.Hour), NotAfter: time.Now().Add(24 * time.Hour),
		IsCA: true, BasicConstraintsValid: true, KeyUsage: x509.KeyUsageCertSign | x509.KeyUsageDigitalSignature,
	}
	der, _ := x509.CreateCertificate(rand.Reader, tpl, tpl, &key.PublicKey, key)
	c, _ := x509.ParseCertificate(der)
	p := x509.NewCertPool()
	p.AddCert(c)
	return &ca{c, key, p}
}

type opt struct {
	cn        string
	dns       []string
	ips       []net.IP
	client    bool
	notBefore time.Time
	notAfter  time.Time
	rsaKey    bool
}

func (a *ca) issue(o opt) tls.Certificate {
	var pub any
	var priv crypto.Signer
	if o.rsaKey {
		k, _ := rsa.GenerateKey(rand.Reader, 2048)
		pub, priv = &k.PublicKey, k
	} else {
		k, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
		pub, priv = &k.PublicKey, k
	}
	if o.notBefore.IsZero() {
		o.notBefore = time.Now().Add(-time.Hour)
	}
	if o.notAfter.IsZero() {
		o.notAfter = time.Now().Add(24 * time.Hour)
	}
	eku := x509.ExtKeyUsageServerAuth
	if o.client {
		eku = x509.ExtKeyUsageClientAuth
	}
	tpl := &x509.Certificate{
		SerialNumber: big.NewInt(serial.Add(1)), Subject: pkix.Name{CommonName: o.cn},
		DNSNames: o.dns, IPAddresses: o.ips, NotBefore: o.notBefore, NotAfter: o.notAfter,
		KeyUsage: x509.KeyUsageDigitalSignature, ExtKeyUsage: []x509.ExtKeyUsage{eku},
	}
	der, err := x509.CreateCertificate(rand.Reader, tpl, a.cert, pub, a.key)
	if err != nil {
		panic(err)
	}
	return tls.Certificate{Certificate: [][]byte{der}, PrivateKey: priv}
}

var lo = []net.IP{net.ParseIP("127.0.0.1")}

// ---------- 辅助 ----------

func em(err error) string {
	if err == nil {
		return "成功"
	}
	st, _ := status.FromError(err)
	m := st.Message()
	if len(m) > 230 {
		m = m[:230] + "…"
	}
	return fmt.Sprintf("code=%s message=%q", st.Code(), m)
}

func call(cl pb.DemoClient, wait time.Duration, opts ...grpc.CallOption) error {
	ctx, cancel := context.WithTimeout(context.Background(), wait)
	defer cancel()
	_, err := cl.Unary(ctx, &pb.Req{Msg: "hi"}, opts...)
	return err
}

func tlsVer(v uint16) string { return tls.VersionName(v) }

func main() {
	root := newCA("demo-root-ca")
	other := newCA("other-ca")
	good := root.issue(opt{cn: "server", dns: []string{"svc.demo.test"}, ips: lo})

	Sec("一:最基本的 TLS:服务端证书由 demo-root-ca 签发(SAN 里有 svc.demo.test 和 127.0.0.1),客户端信任这个 CA 并用 ServerName = svc.demo.test;服务端看到的连接信息")
	{
		var info string
		srv := &DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
			if p, ok := peer.FromContext(ctx); ok {
				if ti, ok := p.AuthInfo.(credentials.TLSInfo); ok {
					info = fmt.Sprintf("TLS 版本 %s;密码套件 %s;ALPN 协商结果 %q;客户端证书数 %d", tlsVer(ti.State.Version), tls.CipherSuiteName(ti.State.CipherSuite), ti.State.NegotiatedProtocol, len(ti.State.PeerCertificates))
				}
			}
			return &pb.Resp{}, nil
		}}
		addr, stop := Start(srv, grpc.Creds(credentials.NewTLS(&tls.Config{Certificates: []tls.Certificate{good}})))
		conn, _ := grpc.NewClient(addr, grpc.WithTransportCredentials(credentials.NewClientTLSFromCert(root.pool, "svc.demo.test")))
		P("调用:%s", em(call(pb.NewDemoClient(conn), 3*time.Second)))
		P("服务端看到:%s", info)
		conn.Close()
		stop()
	}

	Sec("二:服务端证书有问题时客户端看到的错误(调用都是 fail-fast,3 秒内;结果都是 Unavailable,原因写在 message 里)")
	type tc struct {
		name   string
		cert   tls.Certificate
		srvCfg func(*tls.Config)
		client credentials.TransportCredentials
		plain  bool // 服务端不用 TLS
	}
	trust := func(name string) credentials.TransportCredentials {
		return credentials.NewClientTLSFromCert(root.pool, name)
	}
	cases := []tc{
		{name: "客户端不信任签发者(用另一个 CA 的池)", cert: good, client: credentials.NewClientTLSFromCert(other.pool, "svc.demo.test")},
		{name: "域名对不上:证书只含 svc.demo.test,客户端要求 wrong.example", cert: good, client: trust("wrong.example")},
		{name: "证书已过期(昨天过期)", cert: root.issue(opt{cn: "server", dns: []string{"svc.demo.test"}, notBefore: time.Now().Add(-48 * time.Hour), notAfter: time.Now().Add(-24 * time.Hour)}), client: trust("svc.demo.test")},
		{name: "证书里没有任何 SAN,只有 CN", cert: root.issue(opt{cn: "svc.demo.test"}), client: trust("svc.demo.test")},
		{name: "客户端没有配置根证书(用系统根,这台是 macOS 的系统验证器)", cert: good, client: credentials.NewTLS(&tls.Config{ServerName: "svc.demo.test"})},
		{name: "服务端是明文,客户端用 TLS", plain: true, client: trust("svc.demo.test")},
		{name: "服务端最高只支持 TLS 1.2,客户端要求至少 TLS 1.3", cert: good, srvCfg: func(c *tls.Config) { c.MaxVersion = tls.VersionTLS12 }, client: credentials.NewTLS(&tls.Config{RootCAs: root.pool, ServerName: "svc.demo.test", MinVersion: tls.VersionTLS13})},
	}
	for _, c := range cases {
		var so []grpc.ServerOption
		if !c.plain {
			cfg := &tls.Config{Certificates: []tls.Certificate{c.cert}}
			if c.srvCfg != nil {
				c.srvCfg(cfg)
			}
			so = append(so, grpc.Creds(credentials.NewTLS(cfg)))
		}
		addr, stop := Start(&DemoServer{}, so...)
		conn, _ := grpc.NewClient(addr, grpc.WithTransportCredentials(c.client))
		t0 := time.Now()
		err := call(pb.NewDemoClient(conn), 3*time.Second)
		P("%s\n      → %s(%s)", c.name, em(err), Ms(time.Since(t0)))
		conn.Close()
		stop()
	}
	{
		addr, stop := Start(&DemoServer{}, grpc.Creds(credentials.NewTLS(&tls.Config{Certificates: []tls.Certificate{good}})))
		conn, _ := grpc.NewClient(addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
		t0 := time.Now()
		err := call(pb.NewDemoClient(conn), 3*time.Second)
		P("服务端 TLS,客户端用明文\n      → %s(%s)", em(err), Ms(time.Since(t0)))
		conn.Close()
		stop()
	}

	Sec("三:mTLS:服务端要求并验证客户端证书(RequireAndVerifyClientCert)——没有证书、证书由别的 CA 签发(两种发法)、证书合法")
	{
		var peerCN atomic.Value
		srv := &DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
			if p, ok := peer.FromContext(ctx); ok {
				if ti, ok := p.AuthInfo.(credentials.TLSInfo); ok && len(ti.State.PeerCertificates) > 0 {
					peerCN.Store(ti.State.PeerCertificates[0].Subject.CommonName)
				}
			}
			return &pb.Resp{}, nil
		}}
		addr, stop := Start(srv, grpc.Creds(credentials.NewTLS(&tls.Config{Certificates: []tls.Certificate{good}, ClientAuth: tls.RequireAndVerifyClientCert, ClientCAs: root.pool})))
		clientCert := root.issue(opt{cn: "client-A", client: true})
		badCert := other.issue(opt{cn: "client-B", client: true})
		for _, c := range []struct {
			name  string
			certs []tls.Certificate
		}{{"客户端没有证书", nil}, {"客户端有 other-ca 签发的证书(正常配置 Certificates)", []tls.Certificate{badCert}}, {"客户端证书由 other-ca 签发(强制发送)", []tls.Certificate{badCert}}, {"客户端证书由 demo-root-ca 签发", []tls.Certificate{clientCert}}} {
			cfg := &tls.Config{RootCAs: root.pool, ServerName: "svc.demo.test", Certificates: c.certs}
			if strings.Contains(c.name, "强制") {
				cfg.Certificates = nil
				bc := badCert
				cfg.GetClientCertificate = func(*tls.CertificateRequestInfo) (*tls.Certificate, error) { return &bc, nil }
			}
			conn, _ := grpc.NewClient(addr, grpc.WithTransportCredentials(credentials.NewTLS(cfg)))
			t0 := time.Now()
			err := call(pb.NewDemoClient(conn), 3*time.Second)
			cn, _ := peerCN.Load().(string)
			P("%-28s → %s(%s);服务端从证书读到的 CN=%q", c.name, em(err), Ms(time.Since(t0)), cn)
			peerCN.Store("")
			conn.Close()
		}
		stop()
	}

	Sec("四:证书轮换:服务端用 GetCertificate 回调,中途换成新证书;已经建好的连接还是旧证书,新连接用新证书(客户端用 VerifyPeerCertificate 记录收到的证书序列号)")
	{
		var cur atomic.Value
		cert1 := root.issue(opt{cn: "server-v1", dns: []string{"svc.demo.test"}})
		cert2 := root.issue(opt{cn: "server-v2", dns: []string{"svc.demo.test"}})
		cur.Store(&cert1)
		addr, stop := Start(&DemoServer{}, grpc.Creds(credentials.NewTLS(&tls.Config{GetCertificate: func(*tls.ClientHelloInfo) (*tls.Certificate, error) { return cur.Load().(*tls.Certificate), nil }})))
		var mu sync.Mutex
		var seen []string
		cfg := &tls.Config{RootCAs: root.pool, ServerName: "svc.demo.test", VerifyPeerCertificate: func(raw [][]byte, _ [][]*x509.Certificate) error {
			c, _ := x509.ParseCertificate(raw[0])
			mu.Lock()
			seen = append(seen, c.Subject.CommonName)
			mu.Unlock()
			return nil
		}}
		conn1, _ := grpc.NewClient(addr, grpc.WithTransportCredentials(credentials.NewTLS(cfg)))
		cl1 := pb.NewDemoClient(conn1)
		call(cl1, 3*time.Second)
		cur.Store(&cert2)
		call(cl1, 3*time.Second)
		mu.Lock()
		P("换证书之后,已有连接再调用:客户端累计握手次数 %d,看到的证书 CN %v", len(seen), seen)
		mu.Unlock()
		conn2, _ := grpc.NewClient(addr, grpc.WithTransportCredentials(credentials.NewTLS(cfg)))
		call(pb.NewDemoClient(conn2), 3*time.Second)
		mu.Lock()
		P("新建一个连接:客户端累计握手次数 %d,看到的证书 CN %v", len(seen), seen)
		mu.Unlock()
		conn1.Close()
		conn2.Close()
		stop()
	}

	Sec("五:握手的代价:新建连接并完成第一次调用的耗时(中位数,各 30 次):明文、TLS(ECDSA P-256 证书)、TLS(RSA 2048 证书)")
	{
		median := func(ds []time.Duration) time.Duration {
			sort.Slice(ds, func(i, j int) bool { return ds[i] < ds[j] })
			return ds[len(ds)/2]
		}
		rsaCert := root.issue(opt{cn: "server", dns: []string{"svc.demo.test"}, rsaKey: true})
		for _, c := range []struct {
			name   string
			so     []grpc.ServerOption
			client credentials.TransportCredentials
		}{
			{"明文", nil, insecure.NewCredentials()},
			{"TLS ECDSA P-256", []grpc.ServerOption{grpc.Creds(credentials.NewTLS(&tls.Config{Certificates: []tls.Certificate{good}}))}, credentials.NewClientTLSFromCert(root.pool, "svc.demo.test")},
			{"TLS RSA 2048", []grpc.ServerOption{grpc.Creds(credentials.NewTLS(&tls.Config{Certificates: []tls.Certificate{rsaCert}}))}, credentials.NewClientTLSFromCert(root.pool, "svc.demo.test")},
		} {
			addr, stop := Start(&DemoServer{}, c.so...)
			var ds []time.Duration
			for i := 0; i < 30; i++ {
				conn, _ := grpc.NewClient(addr, grpc.WithTransportCredentials(c.client))
				t0 := time.Now()
				call(pb.NewDemoClient(conn), 3*time.Second)
				ds = append(ds, time.Since(t0))
				conn.Close()
			}
			P("%-16s 新连接 + 第一次调用 %s(中位数)", c.name, Ms(median(ds)))
			stop()
		}
	}
	_ = strings.Join
}
