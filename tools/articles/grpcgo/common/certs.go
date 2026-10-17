package common

import (
	"crypto"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"math/big"
	"sync/atomic"
	"time"
)

// CA 是内存里生成的测试用根证书,只给实验用。
type CA struct {
	Cert *x509.Certificate
	Key  *ecdsa.PrivateKey
	Pool *x509.CertPool
}

var certSerial atomic.Int64

func NewCA(name string) *CA {
	key, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	tpl := &x509.Certificate{
		SerialNumber: big.NewInt(certSerial.Add(1)), Subject: pkix.Name{CommonName: name},
		NotBefore: time.Now().Add(-time.Hour), NotAfter: time.Now().Add(24 * time.Hour),
		IsCA: true, BasicConstraintsValid: true, KeyUsage: x509.KeyUsageCertSign | x509.KeyUsageDigitalSignature,
	}
	der, _ := x509.CreateCertificate(rand.Reader, tpl, tpl, &key.PublicKey, key)
	c, _ := x509.ParseCertificate(der)
	p := x509.NewCertPool()
	p.AddCert(c)
	return &CA{c, key, p}
}

// IssueServer 签发一张 ECDSA 的服务端证书,SAN 为 dns。
func (a *CA) IssueServer(cn string, dns ...string) tls.Certificate {
	k, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	var priv crypto.Signer = k
	tpl := &x509.Certificate{
		SerialNumber: big.NewInt(certSerial.Add(1)), Subject: pkix.Name{CommonName: cn},
		DNSNames: dns, NotBefore: time.Now().Add(-time.Hour), NotAfter: time.Now().Add(24 * time.Hour),
		KeyUsage: x509.KeyUsageDigitalSignature, ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
	}
	der, err := x509.CreateCertificate(rand.Reader, tpl, a.Cert, &k.PublicKey, a.Key)
	if err != nil {
		panic(err)
	}
	return tls.Certificate{Certificate: [][]byte{der}, PrivateKey: priv}
}
