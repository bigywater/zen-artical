package main

import (
	"context"
	"fmt"
	"sort"
	"strings"
	"sync"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
	. "grpcgo/common"
	"grpcgo/pb"
)

func filt(info string) []string {
	var out []string
	for _, kv := range strings.Split(info, "; ") {
		if kv == "" || strings.HasPrefix(kv, ":") || strings.HasPrefix(kv, "te:") {
			continue
		}
		out = append(out, kv)
	}
	return out
}

// reqHdr 返回客户端发出的最后一个 HEADERS 帧里的头(去掉伪头)。
func reqHdr(tap *Tap) []string {
	var last string
	for _, e := range tap.Snapshot() {
		if e.Dir == "C→S" && e.Type == "HEADERS" {
			last = e.Info
		}
	}
	return filt(last)
}

// respHdr 返回服务端发出的第 idx 个 HEADERS 帧里的头(0 是响应头,1 是 trailers)。
func respHdr(tap *Tap, idx int) []string {
	n := 0
	for _, e := range tap.Snapshot() {
		if e.Dir == "S→C" && e.Type == "HEADERS" {
			if n == idx {
				return filt(e.Info)
			}
			n++
		}
	}
	return nil
}

func mdStr(md metadata.MD) string {
	var ks []string
	for k := range md {
		ks = append(ks, k)
	}
	sort.Strings(ks)
	var o []string
	for _, k := range ks {
		o = append(o, fmt.Sprintf("%s=%q", k, md[k]))
	}
	return strings.Join(o, " ")
}

func main() {
	var seen metadata.MD
	var setHdrErr, sendHdrErr atomicStr
	srv := &DemoServer{}
	srv.OnUnary = func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
		seen, _ = metadata.FromIncomingContext(ctx)
		if r.Msg == "reply-header" {
			grpc.SetHeader(ctx, metadata.Pairs("x-server", "node-3", "X-Mixed-Case", "Value"))
			grpc.SetTrailer(ctx, metadata.Pairs("x-late", "t"))
		}
		return &pb.Resp{Msg: "ok"}, nil
	}
	srv.OnServerStream = func(r *pb.Req, st pb.Demo_ServerStreamServer) error {
		if r.Msg == "early" {
			if err := st.SendHeader(metadata.Pairs("x-early", "1")); err != nil {
				sendHdrErr.set(err.Error())
			}
			time.Sleep(100 * time.Millisecond)
			st.Send(&pb.Resp{Msg: "m"})
			return nil
		}
		st.Send(&pb.Resp{Msg: "m"})
		if err := st.SetHeader(metadata.Pairs("x-too-late", "1")); err != nil {
			setHdrErr.set(err.Error())
		}
		if err := st.SendHeader(metadata.Pairs("x-too-late2", "1")); err != nil {
			sendHdrErr.set(err.Error())
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
	cl.Unary(context.Background(), &pb.Req{})
	time.Sleep(30 * time.Millisecond)
	call := func(md metadata.MD, msg string, opts ...grpc.CallOption) (error, uint32) {
		tap.Reset()
		ctx := metadata.NewOutgoingContext(context.Background(), md)
		ctx, cancel := context.WithTimeout(ctx, 3*time.Second)
		defer cancel()
		_, err := cl.Unary(ctx, &pb.Req{Msg: msg}, opts...)
		time.Sleep(30 * time.Millisecond)
		return err, 0
	}

	Sec("一:键名大小写:客户端写 X-Request-ID,线上和服务端看到的是什么")
	err, _ := call(metadata.Pairs("X-Request-ID", "abc-123", "Authorization", "Bearer tkn"), "x")
	P("err=%v", err)
	P("线上自定义头:%v", reqHdr(tap))
	P("服务端 metadata.FromIncomingContext 的键:x-request-id=%v authorization=%v", seen.Get("x-request-id"), seen.Get("authorization"))

	Sec("二:哪些值能放:普通键只允许可打印 ASCII;-bin 结尾的键可以放任意字节(线上 base64);非法的键或值会怎样")
	for _, c := range []struct {
		name string
		md   metadata.MD
	}{
		{"普通键 + 中文值", metadata.Pairs("x-name", "张三")},
		{"普通键 + 含换行的值", metadata.Pairs("x-name", "a\nb")},
		{"-bin 键 + 中文值", metadata.Pairs("x-name-bin", "张三")},
		{"-bin 键 + 随机字节", metadata.Pairs("x-raw-bin", "\x00\xff\x10\x80")},
		{"键里有空格", metadata.Pairs("bad key", "v")},
		{"键里有大写和下划线", metadata.Pairs("X_Under_Score", "v")},
		{"值为空字符串", metadata.Pairs("x-empty", "")},
	} {
		err, _ := call(c.md, "x")
		st, _ := status.FromError(err)
		P("%-22s → 客户端 code=%-9s 线上:%v", c.name, st.Code(), reqHdr(tap))
		if err != nil {
			P("    message=%q", st.Message())
		}
	}

	Sec("三:库自己占用的头:用 metadata 设置 user-agent、content-type、grpc-timeout 会怎样")
	for _, c := range []struct {
		name string
		md   metadata.MD
	}{
		{"user-agent", metadata.Pairs("user-agent", "my-client/2.0")},
		{"content-type", metadata.Pairs("content-type", "application/json")},
		{"grpc-timeout", metadata.Pairs("grpc-timeout", "1H")},
		{"grpc-encoding", metadata.Pairs("grpc-encoding", "gzip")},
	} {
		tap.Reset()
		err, _ := call(c.md, "x")
		st, _ := status.FromError(err)
		var rel []string
		for _, kv := range reqHdr(tap) {
			if strings.HasPrefix(kv, "user-agent") || strings.HasPrefix(kv, "content-type") || strings.HasPrefix(kv, "grpc-timeout") || strings.HasPrefix(kv, "grpc-encoding") {
				rel = append(rel, kv)
			}
		}
		P("设置 %-13s → code=%s 线上相关头:%v", c.name, st.Code(), rel)
	}

	Sec("四:同一个键多个值:客户端 Pairs 里写两次,线上是两个头还是合并成逗号,服务端看到几个值")
	err, _ = call(metadata.Pairs("x-tag", "a", "x-tag", "b"), "x")
	P("线上:%v", reqHdr(tap))
	P("服务端看到 x-tag = %q(%d 个值)", seen.Get("x-tag"), len(seen.Get("x-tag")))

	Sec("五:请求头的总大小限制:客户端带不同大小的自定义头,看是否被拒绝(服务端用默认设置)")
	for _, kb := range []int{1, 8, 64, 512, 4096, 8192, 15000, 16000, 16400, 20000} {
		val := strings.Repeat("v", kb*1024)
		err, _ := call(metadata.Pairs("x-big", val), "x")
		st, _ := status.FromError(err)
		msg := st.Message()
		if len(msg) > 90 {
			msg = msg[:90] + "…"
		}
		P("%6d KiB 的头 → code=%-17s %s", kb, st.Code(), msg)
	}

	Sec("六:服务端的响应头与 trailers:SetHeader 在 handler 返回时和第一条响应一起发出;流式里 SendHeader 可以提前发;第一条消息发出后再 SetHeader/SendHeader 会失败")
	{
		tap.Reset()
		var hmd, tmd metadata.MD
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		cl.Unary(ctx, &pb.Req{Msg: "reply-header"}, grpc.Header(&hmd), grpc.Trailer(&tmd))
		cancel()
		time.Sleep(30 * time.Millisecond)
		P("Unary:客户端 grpc.Header 得到 {%s};grpc.Trailer 得到 {%s}", mdStr(hmd), mdStr(tmd))
		P("   线上响应头 %v", respHdr(tap, 0))
		P("   线上 trailers %v", respHdr(tap, 1))
		for _, m := range []string{"early", "late"} {
			tap.Reset()
			ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
			t0 := time.Now()
			stt, _ := cl.ServerStream(ctx, &pb.Req{Msg: m})
			md, _ := stt.Header()
			el := time.Since(t0)
			for {
				if _, err := stt.Recv(); err != nil {
					break
				}
			}
			cancel()
			time.Sleep(30 * time.Millisecond)
			P("流式 %-5s:stream.Header() 在 %s 返回,得到 {%s};线上响应头 %v", m, Ms(el), mdStr(md), respHdr(tap, 0))
		}
		P("服务端 SendHeader 错误:%q", sendHdrErr.get())
		P("服务端 SetHeader 错误:%q", setHdrErr.get())
	}
	_ = fmt.Sprint
}

type atomicStr struct {
	mu sync.Mutex
	v  string
}

func (a *atomicStr) set(s string) { a.mu.Lock(); a.v = s; a.mu.Unlock() }
func (a *atomicStr) get() string  { a.mu.Lock(); defer a.mu.Unlock(); return a.v }
