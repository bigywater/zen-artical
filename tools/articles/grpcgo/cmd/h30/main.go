// h30 的服务端:由 exp/h30.py 启动,浏览器(Chrome)在 Python 一侧驱动。
// 启动后打印三行地址,然后一直运行,直到标准输入被关闭。
package main

import (
	"context"
	"crypto/tls"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/improbable-eng/grpc-web/go/grpcweb"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	. "grpcgo/common"
	"grpcgo/pb"
)

func main() {
	ca := NewCA("demo-ca")
	cert := ca.IssueServer("server", "localhost")
	impl := &DemoServer{
		OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
			if r.Msg == "deny" {
				return nil, status.Error(codes.Unauthenticated, "no token")
			}
			return &pb.Resp{Msg: "echo:" + r.Msg, N: r.N}, nil
		},
		OnServerStream: func(r *pb.Req, st pb.Demo_ServerStreamServer) error {
			for i := 0; i < 3; i++ {
				st.Send(&pb.Resp{Msg: fmt.Sprintf("m%d", i), N: int32(i)})
				time.Sleep(200 * time.Millisecond)
			}
			return nil
		},
		OnClientStream: func(st pb.Demo_ClientStreamServer) error {
			n := 0
			for {
				if _, err := st.Recv(); err != nil {
					if err == io.EOF {
						return st.SendAndClose(&pb.Resp{N: int32(n)})
					}
					return err
				}
				n++
			}
		},
	}
	// 原生 gRPC:grpc.Server 作为 http.Handler 挂在一个 HTTPS(HTTP/2)服务器上,
	// application/grpc 的请求交给 gRPC,其它请求返回一个普通页面(这样浏览器页面和 gRPC 同源)。
	gs := grpc.NewServer()
	pb.RegisterDemoServer(gs, impl)
	nl, _ := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", FreePort()))
	ns := &http.Server{TLSConfig: &tls.Config{Certificates: []tls.Certificate{cert}}, Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.ProtoMajor == 2 && strings.HasPrefix(r.Header.Get("Content-Type"), "application/grpc") {
			gs.ServeHTTP(w, r)
			return
		}
		w.Header().Set("Content-Type", "text/html")
		w.Write([]byte("<!doctype html><title>native</title>native"))
	})}
	go ns.ServeTLS(nl, "", "")

	// grpc-web 包装:另起一个不带 TLS 的 grpc.Server,由 grpcweb 的 http.Handler 转发
	gs2 := grpc.NewServer()
	pb.RegisterDemoServer(gs2, impl)
	wrapped := grpcweb.WrapServer(gs2, grpcweb.WithOriginFunc(func(origin string) bool { return true }))
	wl, _ := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", FreePort()))
	ws := &http.Server{Handler: wrapped, TLSConfig: &tls.Config{Certificates: []tls.Certificate{cert}}}
	go ws.ServeTLS(wl, "", "")

	// 页面服务器:另一个 origin
	pl, _ := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", FreePort()))
	go http.Serve(pl, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html")
		w.Write([]byte("<!doctype html><title>page</title>page"))
	}))

	fmt.Printf("NATIVE %d\nWEB %d\nPAGE %d\n", nl.Addr().(*net.TCPAddr).Port, wl.Addr().(*net.TCPAddr).Port, pl.Addr().(*net.TCPAddr).Port)
	io.Copy(io.Discard, os.Stdin)
	ns.Close()
	gs.Stop()
	gs2.Stop()
	ws.Close()
}
