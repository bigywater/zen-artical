package main

import (
	"bytes"
	"context"
	"fmt"
	"strings"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/encoding/gzip"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/proto"
	. "grpcgo/common"
	"grpcgo/pb"
)

var insec = grpc.WithTransportCredentials(insecure.NewCredentials())

const MiB = 1 << 20

// 服务端:Req.N > 0 时返回 N 字节的响应;否则回显 payload 的长度。
func srvImpl() *DemoServer {
	return &DemoServer{
		OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
			if r.N > 0 {
				return &pb.Resp{Payload: make([]byte, r.N)}, nil
			}
			return &pb.Resp{N: int32(len(r.Payload))}, nil
		},
		OnClientStream: func(st pb.Demo_ClientStreamServer) error {
			n := 0
			for {
				r, err := st.Recv()
				if err != nil {
					if err.Error() == "EOF" {
						return st.SendAndClose(&pb.Resp{N: int32(n)})
					}
					return err
				}
				n++
				_ = r
			}
		},
	}
}

func em(err error) string {
	if err == nil {
		return "成功"
	}
	st, _ := status.FromError(err)
	m := st.Message()
	if len(m) > 120 {
		m = m[:120] + "…"
	}
	return fmt.Sprintf("code=%s message=%q", st.Code(), m)
}

func try(cl pb.DemoClient, req *pb.Req, opts ...grpc.CallOption) error {
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	_, err := cl.Unary(ctx, req, opts...)
	return err
}

func main() {
	Sec("一:服务端默认接收上限 4 MiB(4194304 字节):用二分找出刚好能通过的 payload 字节数,并算出它对应的整条消息大小")
	{
		addr, stop := Start(srvImpl())
		conn, _ := grpc.NewClient(addr, insec)
		cl := pb.NewDemoClient(conn)
		lo, hi := 4*MiB-1000, 4*MiB+1000
		for hi-lo > 1 {
			mid := (lo + hi) / 2
			if try(cl, &pb.Req{Payload: make([]byte, mid)}) == nil {
				lo = mid
			} else {
				hi = mid
			}
		}
		okSize := proto.Size(&pb.Req{Payload: make([]byte, lo)})
		badSize := proto.Size(&pb.Req{Payload: make([]byte, hi)})
		P("最大能通过的 payload %d 字节 → 序列化后的消息 %d 字节;再多 1 字节的 payload %d → 消息 %d 字节(4 MiB = %d)", lo, okSize, hi, badSize, 4*MiB)
		P("再多一字节时的错误:%s", em(try(cl, &pb.Req{Payload: make([]byte, hi)})))
		conn.Close()
		stop()
	}

	Sec("二:三个方向的限制与各自的错误:服务端收太大的请求、客户端收太大的响应(服务端发 5 MiB)、客户端自己设发送上限 MaxCallSendMsgSize(1 MiB)后发 2 MiB")
	{
		addr, stop := Start(srvImpl())
		tap := NewTap(addr)
		conn, _ := grpc.NewClient(tap.Addr, insec)
		cl := pb.NewDemoClient(conn)
		P("服务端收 5 MiB 的请求:%s", em(try(cl, &pb.Req{Payload: make([]byte, 5*MiB)})))
		P("客户端收 5 MiB 的响应:%s", em(try(cl, &pb.Req{N: 5 * MiB})))
		tap.Reset()
		err := try(cl, &pb.Req{Payload: make([]byte, 2*MiB)}, grpc.MaxCallSendMsgSize(1*MiB))
		time.Sleep(50 * time.Millisecond)
		h := 0
		for _, e := range tap.Snapshot() {
			if e.Dir == "C→S" && e.Type == "HEADERS" {
				h++
			}
		}
		P("客户端 MaxCallSendMsgSize(1 MiB) 发 2 MiB:%s;线上客户端发出的 HEADERS %d 个", em(err), h)
		conn.Close()
		tap.Close()
		stop()
	}

	Sec("三:服务端拒绝一个 64 MiB 的请求之前,线上已经传了多少字节、花了多久")
	{
		addr, stop := Start(srvImpl())
		tap := NewTap(addr)
		conn, _ := grpc.NewClient(tap.Addr, insec)
		cl := pb.NewDemoClient(conn)
		try(cl, &pb.Req{})
		tap.ResetBytes()
		t0 := time.Now()
		err := try(cl, &pb.Req{Payload: make([]byte, 64*MiB)})
		el := time.Since(t0)
		time.Sleep(100 * time.Millisecond)
		P("64 MiB 的请求:%s;耗时 %s;客户端→服务端的线上字节 %d(%.2f MiB,占消息的 %.1f%%)", em(err), Ms(el), tap.BytesCS, float64(tap.BytesCS)/MiB, 100*float64(tap.BytesCS)/float64(64*MiB))
		conn.Close()
		tap.Close()
		stop()
	}

	Sec("四:限制是“每条消息”的,不是每个流的:客户端流里发 10 条 3 MiB 的消息;再发一条 5 MiB 的消息")
	{
		addr, stop := Start(srvImpl())
		conn, _ := grpc.NewClient(addr, insec)
		cl := pb.NewDemoClient(conn)
		ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
		st, _ := cl.ClientStream(ctx)
		var sendErr error
		for i := 0; i < 10; i++ {
			if sendErr = st.Send(&pb.Req{Payload: make([]byte, 3*MiB)}); sendErr != nil {
				break
			}
		}
		r, err := st.CloseAndRecv()
		P("10 条 3 MiB:Send 错误 %v;服务端数到 %d 条;最终 %s(总共 30 MiB)", sendErr, r.GetN(), em(err))
		st2, _ := cl.ClientStream(ctx)
		st2.Send(&pb.Req{Payload: make([]byte, 1*MiB)})
		st2.Send(&pb.Req{Payload: make([]byte, 5*MiB)})
		_, err = st2.CloseAndRecv()
		P("先 1 MiB 再 5 MiB:%s", em(err))
		cancel()
		conn.Close()
		stop()
	}

	Sec("五:压缩后的大小不算数,解压后的大小才算:客户端用 gzip 发 100 MiB 的零(压缩后只有两百 KiB 左右),服务端默认上限 4 MiB;服务端把上限提到 128 MiB 后再发")
	{
		for _, raise := range []bool{false, true} {
			var so []grpc.ServerOption
			if raise {
				so = append(so, grpc.MaxRecvMsgSize(128*MiB))
			}
			addr, stop := Start(srvImpl(), so...)
			tap := NewTap(addr)
			conn, _ := grpc.NewClient(tap.Addr, insec)
			cl := pb.NewDemoClient(conn)
			try(cl, &pb.Req{})
			tap.ResetBytes()
			err := try(cl, &pb.Req{Payload: bytes.Repeat([]byte{0}, 100*MiB)}, grpc.UseCompressor(gzip.Name), grpc.MaxCallSendMsgSize(200*MiB))
			time.Sleep(100 * time.Millisecond)
			name := "默认上限 4 MiB"
			if raise {
				name = "MaxRecvMsgSize(128 MiB)"
			}
			P("%-24s:%s;线上客户端→服务端 %d 字节(%.1f KiB)", name, em(err), tap.BytesCS, float64(tap.BytesCS)/1024)
			conn.Close()
			tap.Close()
			stop()
		}
	}

	Sec("六:调大上限:服务端 MaxRecvMsgSize(64 MiB)、客户端 MaxCallRecvMsgSize(64 MiB),往返 32 MiB 的数据——能通过吗,耗时多少")
	{
		addr, stop := Start(srvImpl(), grpc.MaxRecvMsgSize(64*MiB), grpc.MaxSendMsgSize(64*MiB))
		conn, _ := grpc.NewClient(addr, insec, grpc.WithDefaultCallOptions(grpc.MaxCallRecvMsgSize(64*MiB), grpc.MaxCallSendMsgSize(64*MiB)))
		cl := pb.NewDemoClient(conn)
		try(cl, &pb.Req{})
		t0 := time.Now()
		err1 := try(cl, &pb.Req{Payload: make([]byte, 32*MiB)})
		d1 := time.Since(t0)
		t0 = time.Now()
		err2 := try(cl, &pb.Req{N: 32 * MiB})
		d2 := time.Since(t0)
		P("发 32 MiB 请求:%s,耗时 %s;收 32 MiB 响应:%s,耗时 %s", em(err1), Ms(d1), em(err2), Ms(d2))
		conn.Close()
		stop()
	}
	_ = strings.Join
}
