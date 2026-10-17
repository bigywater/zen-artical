package main

import (
	"bytes"
	"context"
	"encoding/binary"
	"fmt"
	"strings"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/encoding/gzip"
	"google.golang.org/grpc/status"
	. "grpcgo/common"
	"grpcgo/pb"
)

func dataFrames(ev []Event, dir string, stream uint32) (n int, lens []int) {
	for _, e := range ev {
		if e.Dir == dir && e.Type == "DATA" && e.Stream == stream {
			n++
			lens = append(lens, int(e.Len))
		}
	}
	return
}

// parseMessages 把一个方向上某条流的 DATA 负载拼起来,按 5 字节前缀切成消息。
func parseMessages(ev []Event, dir string, stream uint32) (msgs []struct {
	Flag byte
	Len  int
}, rest int) {
	var buf bytes.Buffer
	for _, e := range ev {
		if e.Dir == dir && e.Type == "DATA" && e.Stream == stream {
			buf.Write(e.Data)
		}
	}
	b := buf.Bytes()
	for len(b) >= 5 {
		l := int(binary.BigEndian.Uint32(b[1:5]))
		if len(b) < 5+l {
			break
		}
		msgs = append(msgs, struct {
			Flag byte
			Len  int
		}{b[0], l})
		b = b[5+l:]
	}
	return msgs, len(b)
}

type msg = struct {
	Flag byte
	Len  int
}

func fm(ms []msg) string {
	var o []string
	for _, m := range ms {
		o = append(o, fmt.Sprintf("(标志 %d,长度 %d)", m.Flag, m.Len))
	}
	return strings.Join(o, " ")
}

func main() {
	srv := &DemoServer{}
	srv.OnUnary = func(ctx context.Context, r *pb.Req) (*pb.Resp, error) { return &pb.Resp{Msg: "ok", Payload: r.Payload[:min(len(r.Payload), 0)]}, nil }
	srv.OnServerStream = func(r *pb.Req, st pb.Demo_ServerStreamServer) error {
		for i := 0; i < int(r.N); i++ {
			if err := st.Send(&pb.Resp{Msg: fmt.Sprintf("m%d", i), N: int32(i)}); err != nil {
				return err
			}
		}
		return nil
	}
	addr, stop := Start(srv)
	defer stop()
	tap := NewTap(addr)
	defer tap.Close()
	conn, _ := grpc.NewClient(tap.Addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	defer conn.Close()
	cl := pb.NewDemoClient(conn)
	call := func(r *pb.Req, opts ...grpc.CallOption) error {
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		_, err := cl.Unary(ctx, r, opts...)
		return err
	}
	cl.Unary(context.Background(), &pb.Req{Msg: "warmup"}) // 先建立连接
	time.Sleep(50 * time.Millisecond)

	Sec("一:请求消息的大小不同时,DATA 帧怎么切(HTTP/2 默认单帧最多 16384 字节;下面看客户端发出的 DATA 帧)")
	P("%-18s %-10s %-10s %-34s %s", "payload 大小", "protobuf", "消息总长", "客户端 DATA 帧负载长度", "5 字节前缀里的长度")
	var nextStream uint32 = 3
	for _, sz := range []int{0, 1, 300, 16000, 20000, 70000, 1 << 20} {
		tap.Reset()
		r := &pb.Req{Msg: "x", Payload: bytes.Repeat([]byte{'a'}, sz)}
		if err := call(r); err != nil {
			P("%d: %v", sz, err)
			continue
		}
		time.Sleep(30 * time.Millisecond)
		ev := tap.Snapshot()
		n, lens := dataFrames(ev, "C→S", nextStream)
		msgs, rest := parseMessages(ev, "C→S", nextStream)
		short := fmt.Sprint(lens)
		if len(lens) > 6 {
			short = fmt.Sprint(lens[:4]) + fmt.Sprintf("…共 %d 帧,最后一帧 %d", n, lens[len(lens)-1])
		}
		total := 0
		for _, l := range lens {
			total += l
		}
		P("%-18d %-10d %-10d %-34s %s(剩余字节 %d)", sz, total-5, total, short, fm(msgs), rest)
		nextStream += 2
	}

	Sec("二:一条流里的多条消息:服务端流返回 3 条消息,每条自己带 5 字节前缀;消息边界与 DATA 帧边界的关系")
	tap.Reset()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	st, _ := cl.ServerStream(ctx, &pb.Req{N: 3})
	for {
		if _, err := st.Recv(); err != nil {
			break
		}
	}
	cancel()
	time.Sleep(50 * time.Millisecond)
	ev := tap.Snapshot()
	n, lens := dataFrames(ev, "S→C", nextStream)
	msgs, rest := parseMessages(ev, "S→C", nextStream)
	P("服务端 DATA 帧 %d 个,负载长度 %v;按前缀切出 %d 条消息:%s,剩余 %d 字节", n, lens, len(msgs), fm(msgs), rest)
	nextStream += 2

	Sec("三:开启 gzip 压缩(grpc.UseCompressor(gzip.Name)):压缩标志变成 1,请求头多出 grpc-encoding")
	tap.Reset()
	payload := []byte(strings.Repeat("hello gRPC ", 500))
	if err := call(&pb.Req{Msg: "x", Payload: payload}, grpc.UseCompressor(gzip.Name)); err != nil {
		P("错误 %v", err)
	}
	time.Sleep(50 * time.Millisecond)
	ev = tap.Snapshot()
	for _, e := range ev {
		if e.Dir == "C→S" && e.Type == "HEADERS" && e.Stream == nextStream {
			for _, kv := range strings.Split(e.Info, "; ") {
				if strings.HasPrefix(kv, "grpc-") {
					P("请求头 %s", kv)
				}
			}
		}
	}
	msgs, rest = parseMessages(ev, "C→S", nextStream)
	P("原始 payload %d 字节;线上这一条消息:压缩标志 %d,长度字段 %d(压缩后的 gzip 字节数);剩余 %d", len(payload), msgs[0].Flag, msgs[0].Len, rest)
	for _, e := range ev {
		if e.Dir == "S→C" && e.Type == "HEADERS" && e.Stream == nextStream {
			P("响应头 %s", e.Info)
			break
		}
	}
	nextStream += 2

	Sec("四:空消息 Req{} 的编码:5 字节前缀,长度 0,没有载荷")
	tap.Reset()
	call(&pb.Req{})
	time.Sleep(50 * time.Millisecond)
	ev = tap.Snapshot()
	for _, e := range ev {
		if e.Dir == "C→S" && e.Type == "DATA" && e.Stream == nextStream {
			P("DATA 帧负载 %d 字节:%x,标志 END_STREAM=%v", e.Len, e.Data, strings.Contains(e.Flags, "END_STREAM"))
		}
	}
	nextStream += 2

	Sec("五:客户端发超过服务端接收上限(默认 4 MiB)的消息会怎样:5 MiB 的请求,线上实际传了多少字节")
	tap.Reset()
	tap.ResetBytes()
	t0 := time.Now()
	err := call(&pb.Req{Msg: "big", Payload: bytes.Repeat([]byte{'b'}, 5<<20)})
	el := time.Since(t0)
	time.Sleep(100 * time.Millisecond)
	cs, sc := tap.Bytes()
	s, _ := status.FromError(err)
	P("客户端得到 code=%s message=%q,用时 %s", s.Code(), s.Message(), Ms(el))
	P("线上客户端→服务端 %d 字节(消息本身 %d 字节);服务端→客户端 %d 字节", cs, 5<<20, sc)
	_ = codes.OK
	ev = tap.Snapshot()
	for _, e := range ev {
		if e.Dir == "S→C" && (e.Type == "RST_STREAM" || e.Type == "HEADERS") {
			P("%s 流 %d %s %s", e.Dir, e.Stream, e.Type, e.Info)
		}
	}
}
