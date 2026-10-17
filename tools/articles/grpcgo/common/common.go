// Package common 放 gRPC 系列实验共用的小工具:端口、分节输出、一个会解析 HTTP/2 帧的 TCP 抓包代理。
package common

import (
	"context"
	"fmt"
	"net"
	"sync"
	"time"

	"google.golang.org/grpc"
	"grpcgo/pb"
)

var forbidden = map[int]bool{5432: true, 3306: true, 6379: true, 8181: true, 9101: true, 9333: true}

// FreePort 从 9800 开始找一个能 bind 的端口(用 bind 探测,不要 connect)。
var (
	usedMu sync.Mutex
	used   = map[int]bool{}
)

func FreePort() int {
	usedMu.Lock()
	defer usedMu.Unlock()
	for p := 9800; p < 10200; p++ {
		if forbidden[p] || used[p] {
			continue
		}
		l, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", p))
		if err == nil {
			l.Close()
			used[p] = true
			return p
		}
	}
	panic("no free port")
}

func Sec(s string)              { fmt.Println("== " + s) }
func P(format string, a ...any) { fmt.Printf("  "+format+"\n", a...) }

// DemoServer 是可配置行为的 Demo 服务实现。
type DemoServer struct {
	pb.UnimplementedDemoServer
	OnUnary        func(context.Context, *pb.Req) (*pb.Resp, error)
	OnServerStream func(*pb.Req, pb.Demo_ServerStreamServer) error
	OnClientStream func(pb.Demo_ClientStreamServer) error
	OnBidi         func(pb.Demo_BidiServer) error
}

func (s *DemoServer) Unary(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
	if s.OnUnary != nil {
		return s.OnUnary(ctx, r)
	}
	return &pb.Resp{Msg: "echo:" + r.Msg, N: r.N}, nil
}
func (s *DemoServer) ServerStream(r *pb.Req, st pb.Demo_ServerStreamServer) error {
	if s.OnServerStream != nil {
		return s.OnServerStream(r, st)
	}
	return nil
}
func (s *DemoServer) ClientStream(st pb.Demo_ClientStreamServer) error {
	if s.OnClientStream != nil {
		return s.OnClientStream(st)
	}
	return nil
}
func (s *DemoServer) Bidi(st pb.Demo_BidiServer) error {
	if s.OnBidi != nil {
		return s.OnBidi(st)
	}
	return nil
}

// Start 在 127.0.0.1:port 起一个 grpc 服务器,返回地址和停止函数。
func Start(impl *DemoServer, opts ...grpc.ServerOption) (addr string, stop func()) {
	port := FreePort()
	l, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", port))
	if err != nil {
		panic(err)
	}
	s := grpc.NewServer(opts...)
	pb.RegisterDemoServer(s, impl)
	go s.Serve(l)
	return l.Addr().String(), func() { s.Stop() }
}

func Ms(d time.Duration) string { return fmt.Sprintf("%.1f ms", float64(d.Microseconds())/1000) }

// StartWith 和 Start 一样,但可以传 grpc.ServerOption。
func StartWith(impl *DemoServer, opts ...grpc.ServerOption) (string, func()) {
	return Start(impl, opts...)
}

// StartReg 和 Start 一样,但允许在服务器上额外注册别的服务(例如 health)。
func StartReg(impl *DemoServer, reg func(*grpc.Server), opts ...grpc.ServerOption) (addr string, stop func()) {
	port := FreePort()
	l, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", port))
	if err != nil {
		panic(err)
	}
	s := grpc.NewServer(opts...)
	pb.RegisterDemoServer(s, impl)
	if reg != nil {
		reg(s)
	}
	go s.Serve(l)
	return l.Addr().String(), func() { s.Stop() }
}
