package main

import (
	"bytes"
	"context"
	"fmt"
	"runtime"
	"strings"
	"testing"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/protobuf/proto"
	. "grpcgo/common"
	"grpcgo/pb"
)

var insec = grpc.WithTransportCredentials(insecure.NewCredentials())

func human(n int) string {
	switch {
	case n >= 1<<20:
		return fmt.Sprintf("%d MiB", n>>20)
	case n >= 1<<10:
		return fmt.Sprintf("%d KiB", n>>10)
	}
	return fmt.Sprintf("%d B", n)
}

func main() {
	sizes := []int{1 << 10, 16 << 10, 100 << 10, 512 << 10, 1 << 20, 2 << 20, 8 << 20}

	Sec("一:只看 protobuf 编解码(proto.Marshal / proto.Unmarshal,payload 是 bytes 字段):每次耗时与分配")
	for _, sz := range sizes {
		req := &pb.Req{Payload: bytes.Repeat([]byte{7}, sz)}
		wire, _ := proto.Marshal(req)
		m := testing.Benchmark(func(b *testing.B) {
			b.ReportAllocs()
			for i := 0; i < b.N; i++ {
				proto.Marshal(req)
			}
		})
		u := testing.Benchmark(func(b *testing.B) {
			b.ReportAllocs()
			for i := 0; i < b.N; i++ {
				var r pb.Req
				proto.Unmarshal(wire, &r)
			}
		})
		P("%-8s Marshal %8.1f µs、分配 %9d 字节/次(%.2f 倍 payload);Unmarshal %8.1f µs、分配 %9d 字节/次(%.2f 倍 payload)", human(sz), float64(m.NsPerOp())/1000, m.AllocedBytesPerOp(), float64(m.AllocedBytesPerOp())/float64(sz), float64(u.NsPerOp())/1000, u.AllocedBytesPerOp(), float64(u.AllocedBytesPerOp())/float64(sz))
	}

	Sec("二:整个 RPC 的内存分配:客户端和服务端在同一个进程里,echo(请求和响应各带 payload),顺序调用,统计每次调用分配的字节数(runtime.MemStats.TotalAlloc 的增量)")
	{
		addr, stop := Start(&DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
			return &pb.Resp{Payload: r.Payload}, nil
		}}, grpc.MaxRecvMsgSize(64<<20), grpc.MaxSendMsgSize(64<<20))
		conn, _ := grpc.NewClient(addr, insec, grpc.WithDefaultCallOptions(grpc.MaxCallRecvMsgSize(64<<20), grpc.MaxCallSendMsgSize(64<<20)))
		cl := pb.NewDemoClient(conn)
		_ = stop
		for _, sz := range sizes {
			req := &pb.Req{Payload: bytes.Repeat([]byte{7}, sz)}
			n := 200
			if sz >= 1<<20 {
				n = 40
			}
			for i := 0; i < 20; i++ {
				if _, err := cl.Unary(context.Background(), req); err != nil {
					panic(err)
				}
			}
			runtime.GC()
			var a, b runtime.MemStats
			runtime.ReadMemStats(&a)
			t0 := time.Now()
			for i := 0; i < n; i++ {
				if _, err := cl.Unary(context.Background(), req); err != nil {
					panic(err)
				}
			}
			el := time.Since(t0)
			runtime.ReadMemStats(&b)
			per := float64(b.TotalAlloc-a.TotalAlloc) / float64(n)
			mal := float64(b.Mallocs-a.Mallocs) / float64(n)
			P("%-8s 每次调用分配 %10.0f 字节(= %.2f 倍 payload;请求加响应共 %d 字节 payload 来回);%.0f 次内存分配;耗时 %s/次", human(sz), per, per/float64(sz), 2*sz, mal, Ms(el/time.Duration(n)))
		}
		conn.Close()
		stop()
	}

	Sec("三:bytes 和 string 字段的反序列化:string 要校验 UTF-8。1 MiB 的纯 ASCII string、1 MiB 的中文 string、1 MiB 的 bytes,proto.Unmarshal 的耗时")
	{
		ascii := strings.Repeat("a", 1<<20)
		zh := strings.Repeat("中", (1<<20)/3)
		for _, c := range []struct {
			name string
			req  *pb.Req
		}{{"string(ASCII)", &pb.Req{Msg: ascii}}, {"string(中文)", &pb.Req{Msg: zh}}, {"bytes", &pb.Req{Payload: []byte(ascii)}}} {
			wire, _ := proto.Marshal(c.req)
			u := testing.Benchmark(func(b *testing.B) {
				b.ReportAllocs()
				for i := 0; i < b.N; i++ {
					var r pb.Req
					proto.Unmarshal(wire, &r)
				}
			})
			P("%-14s 线上 %d 字节;Unmarshal %.1f µs/次,分配 %d 字节/次", c.name, len(wire), float64(u.NsPerOp())/1000, u.AllocedBytesPerOp())
		}
		bad := append([]byte{0x0a, 0x02}, 0xff, 0xfe)
		var r pb.Req
		P("string 字段里放非法 UTF-8(0xff 0xfe):proto.Unmarshal 的错误:%v", proto.Unmarshal(bad, &r))
	}
}
