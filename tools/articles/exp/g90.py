import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g90')
SRC = r'''
package main

import (
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
	"os"
	"sort"
	"time"
)

type pki struct {
	caCert *x509.Certificate
	caKey  *ecdsa.PrivateKey
	pool   *x509.CertPool
}

func newCA() *pki {
	k, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	tpl := &x509.Certificate{SerialNumber: big.NewInt(1), Subject: pkix.Name{CommonName: "测试根证书"}, NotBefore: time.Now().Add(-time.Hour), NotAfter: time.Now().Add(24 * time.Hour), IsCA: true, BasicConstraintsValid: true, KeyUsage: x509.KeyUsageCertSign}
	der, _ := x509.CreateCertificate(rand.Reader, tpl, tpl, &k.PublicKey, k)
	c, _ := x509.ParseCertificate(der)
	pool := x509.NewCertPool(); pool.AddCert(c)
	return &pki{c, k, pool}
}

func (p *pki) leaf(names []string, notBefore, notAfter time.Time, useRSA bool) tls.Certificate {
	var pub, priv any
	if useRSA { k, _ := rsa.GenerateKey(rand.Reader, 2048); pub, priv = &k.PublicKey, k } else { k, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader); pub, priv = &k.PublicKey, k }
	tpl := &x509.Certificate{SerialNumber: big.NewInt(time.Now().UnixNano()), Subject: pkix.Name{CommonName: names[0]}, DNSNames: names, NotBefore: notBefore, NotAfter: notAfter, KeyUsage: x509.KeyUsageDigitalSignature, ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth}}
	der, _ := x509.CreateCertificate(rand.Reader, tpl, p.caCert, pub, p.caKey)
	return tls.Certificate{Certificate: [][]byte{der}, PrivateKey: priv}
}

func serve(cfg *tls.Config) (string, func()) {
	ln, _ := tls.Listen("tcp", "127.0.0.1:0", cfg)
	go func() { for { c, err := ln.Accept(); if err != nil { return }; go func() { defer c.Close(); buf := make([]byte, 1); c.Read(buf); c.Write([]byte("k")) }() } }()
	return ln.Addr().String(), func() { ln.Close() }
}

func dial(addr string, cfg *tls.Config) (*tls.Conn, time.Duration, error) {
	t0 := time.Now()
	raw, err := net.Dial("tcp", addr)
	if err != nil { return nil, 0, err }
	c := tls.Client(raw, cfg)
	err = c.Handshake()
	return c, time.Since(t0), err
}

func med(xs []float64) float64 { sort.Float64s(xs); return xs[len(xs)/2] }

func main() {
	ca := newCA()
	now := time.Now()
	good := ca.leaf([]string{"example.test"}, now.Add(-time.Hour), now.Add(time.Hour), false)
	switch os.Args[1] {
	case "state":
		addr, stop := serve(&tls.Config{Certificates: []tls.Certificate{good}, NextProtos: []string{"h2", "http/1.1"}})
		defer stop()
		c, d, err := dial(addr, &tls.Config{RootCAs: ca.pool, ServerName: "example.test", NextProtos: []string{"http/1.1"}})
		if err != nil { fmt.Println("  错误:", err); return }
		st := c.ConnectionState()
		fmt.Printf("  握手成功(%.2f ms):版本 %s,密码套件 %s,ALPN 协商结果 %q,服务端名 %q,证书链长度 %d,验证后的链数 %d\n", float64(d.Microseconds())/1000, tls.VersionName(st.Version), tls.CipherSuiteName(st.CipherSuite), st.NegotiatedProtocol, st.ServerName, len(st.PeerCertificates), len(st.VerifiedChains))
		c.Close()
	case "errors":
		expired := ca.leaf([]string{"example.test"}, now.Add(-48*time.Hour), now.Add(-24*time.Hour), false)
		wrongName := ca.leaf([]string{"other.test"}, now.Add(-time.Hour), now.Add(time.Hour), false)
		cases := []struct{ name string; srv *tls.Config; cli *tls.Config }{
			{"客户端没有信任这个 CA(RootCAs 为空,用系统根证书)", &tls.Config{Certificates: []tls.Certificate{good}}, &tls.Config{ServerName: "example.test"}},
			{"服务端证书已过期", &tls.Config{Certificates: []tls.Certificate{expired}}, &tls.Config{RootCAs: ca.pool, ServerName: "example.test"}},
			{"证书里的名字是 other.test,客户端要的是 example.test", &tls.Config{Certificates: []tls.Certificate{wrongName}}, &tls.Config{RootCAs: ca.pool, ServerName: "example.test"}},
			{"服务端最高只到 TLS 1.2,客户端要求最低 TLS 1.3", &tls.Config{Certificates: []tls.Certificate{good}, MaxVersion: tls.VersionTLS12}, &tls.Config{RootCAs: ca.pool, ServerName: "example.test", MinVersion: tls.VersionTLS13}},
			{"客户端不设 ServerName(用 IP 地址拨号)", &tls.Config{Certificates: []tls.Certificate{good}}, &tls.Config{RootCAs: ca.pool}},
			{"同上,但 InsecureSkipVerify: true", &tls.Config{Certificates: []tls.Certificate{good}}, &tls.Config{InsecureSkipVerify: true}},
		}
		for _, c := range cases {
			addr, stop := serve(c.srv)
			conn, _, err := dial(addr, c.cli)
			res := "握手成功"
			if err != nil { res = "失败:" + err.Error() } else { conn.Close() }
			fmt.Printf("  %s → %s\n", c.name, res)
			stop()
		}
	case "resume":
		addr, stop := serve(&tls.Config{Certificates: []tls.Certificate{good}})
		defer stop()
		var full, resumed []float64
		for i := 0; i < 30; i++ {
			c, d, _ := dial(addr, &tls.Config{RootCAs: ca.pool, ServerName: "example.test"})
			full = append(full, float64(d.Microseconds())/1000)
			c.Close()
		}
		cache := tls.NewLRUClientSessionCache(10)
		cfg := &tls.Config{RootCAs: ca.pool, ServerName: "example.test", ClientSessionCache: cache}
		c, _, _ := dial(addr, cfg)
		c.Write([]byte("x")); c.Read(make([]byte, 1)) // 读一下才能收到服务端的会话票据
		c.Close()
		var did int
		for i := 0; i < 30; i++ {
			c, d, _ := dial(addr, cfg)
			if c.ConnectionState().DidResume { did++ }
			resumed = append(resumed, float64(d.Microseconds())/1000)
			c.Write([]byte("x")); c.Read(make([]byte, 1)); c.Close()
		}
		fmt.Printf("  本机回环上完整握手(30 次):中位 %.2f ms;配 ClientSessionCache 的复用握手(30 次中 DidResume 为真 %d 次):中位 %.2f ms\n", med(full), did, med(resumed))
	case "keytype":
		for _, rsaKey := range []bool{false, true} {
			cert := ca.leaf([]string{"example.test"}, now.Add(-time.Hour), now.Add(time.Hour), rsaKey)
			addr, stop := serve(&tls.Config{Certificates: []tls.Certificate{cert}})
			var xs []float64
			for i := 0; i < 50; i++ { c, d, _ := dial(addr, &tls.Config{RootCAs: ca.pool, ServerName: "example.test"}); xs = append(xs, float64(d.Microseconds())/1000); c.Close() }
			c, _, _ := dial(addr, &tls.Config{RootCAs: ca.pool, ServerName: "example.test"})
			fmt.Printf("  服务端证书 %s:50 次完整握手中位 %.2f ms;密码套件 %s\n", map[bool]string{false: "ECDSA P-256", true: "RSA 2048"}[rsaKey], med(xs), tls.CipherSuiteName(c.ConnectionState().CipherSuite))
			c.Close(); stop()
		}
	}
}
'''
d = gdir('tl1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(m):
    p = subprocess.run([str(d / 'app'), m], capture_output=True, text=True, timeout=300)
    return tidy(p.stdout + p.stderr)
print('== 一:一次成功的握手之后能读到什么(Go 1.27.1,arm64 macOS;进程内生成的 CA 与服务端证书,本机回环)')
print(run('state'))
print('== 二:各种握手/验证失败的错误原文')
print(run('errors'))
print('== 三:会话复用')
print(run('resume'))
print('== 四:证书密钥类型对握手耗时的影响')
print(run('keytype'))
print('== 五:crypto/tls 文档里关于 InsecureSkipVerify 与 MinVersion 的说明')
r, o = go(gdir('doc1'), 'doc', 'crypto/tls.Config')
ls = [l.strip() for l in o.split('\n')]
for pre in ('// InsecureSkipVerify controls whether', '// MinVersion contains the minimum TLS version'):
    i = next((i for i, l in enumerate(ls) if l.startswith(pre)), None)
    print('  ' + (' '.join(x.replace('// ', '', 1) for x in ls[i:i + 6] if x) if i is not None else '(未找到)' + pre))
