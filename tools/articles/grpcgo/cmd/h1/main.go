package main

import (
	"context"
	"encoding/binary"
	"encoding/hex"
	"fmt"
	"strings"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/protobuf/proto"
	. "grpcgo/common"
	"grpcgo/pb"
)

func main() {
	addr, stop := Start(&DemoServer{})
	defer stop()
	tap := NewTap(addr)
	defer tap.Close()
	conn, err := grpc.NewClient(tap.Addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		panic(err)
	}
	defer conn.Close()
	cl := pb.NewDemoClient(conn)

	Sec("一:建立连接并调用一次 Unary(Req{msg:\"hello\"}),代理看到的全部 HTTP/2 帧(按到达顺序)")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	t0 := time.Now()
	resp, err := cl.Unary(ctx, &pb.Req{Msg: "hello", N: 7})
	el := time.Since(t0)
	cancel()
	if err != nil {
		panic(err)
	}
	time.Sleep(100 * time.Millisecond)
	P("调用返回 %q,n=%d,用时(含建立连接)%s", resp.Msg, resp.N, Ms(el))
	tap.Dump()
	ev := tap.Snapshot()

	Sec("二:请求的 HEADERS 帧里的每个头(HPACK 解码后)")
	for _, e := range ev {
		if e.Dir == "C→S" && e.Type == "HEADERS" {
			for _, kv := range strings.Split(e.Info, "; ") {
				P("%s", kv)
			}
			P("(这个 HEADERS 帧的负载 %d 字节)", e.Len)
			break
		}
	}

	Sec("三:请求消息(DATA 帧)= 5 字节前缀 + protobuf 载荷,逐字节拆开")
	for _, e := range ev {
		if e.Dir == "C→S" && e.Type == "DATA" {
			d := e.Data
			P("DATA 帧负载共 %d 字节:%s", len(d), hex.EncodeToString(d))
			P("第 1 字节 压缩标志 = %d(0 表示没压缩);第 2–5 字节 消息长度 = %d(大端)", d[0], binary.BigEndian.Uint32(d[1:5]))
			want, _ := proto.Marshal(&pb.Req{Msg: "hello", N: 7})
			P("载荷 %s;我自己 proto.Marshal(Req{msg:hello,n:7}) = %s;%s", hex.EncodeToString(d[5:]), hex.EncodeToString(want), map[bool]string{true: "两者字节相同", false: "两者字节不同"}[hex.EncodeToString(d[5:]) == hex.EncodeToString(want)])
			break
		}
	}

	Sec("四:响应的三段:HEADERS(:status、content-type)、DATA(同样的 5 字节前缀)、最后带 END_STREAM 的 HEADERS(trailers:grpc-status)")
	for _, e := range ev {
		if e.Dir == "S→C" && (e.Type == "HEADERS" || e.Type == "DATA") {
			flags := e.Flags
			if flags == "" { flags = "-" }
			if e.Type == "DATA" {
				P("流 %d DATA   负载 %d 字节  前缀+载荷:%s", e.Stream, e.Len, hex.EncodeToString(e.Data))
			} else {
				P("流 %d HEADERS 标志 %s  %s", e.Stream, flags, e.Info)
			}
		}
	}

	Sec("五:一次调用在网线上一共多少字节(代理统计的 TCP 字节数,含建立连接时的 preface 和 SETTINGS)")
	cs, sc := tap.Bytes()
	P("客户端→服务端 %d 字节;服务端→客户端 %d 字节;请求消息本身 protobuf %d 字节,响应消息 %d 字节", cs, sc, proto.Size(&pb.Req{Msg: "hello", N: 7}), proto.Size(resp))

	Sec("六:在同一条连接上第二次调用:没有新的 SETTINGS,请求头因为 HPACK 动态表变得更短")
	tap.Reset()
	tap.ResetBytes()
	ctx, cancel = context.WithTimeout(context.Background(), 5*time.Second)
	t0 = time.Now()
	_, err = cl.Unary(ctx, &pb.Req{Msg: "hello", N: 7})
	el = time.Since(t0)
	cancel()
	time.Sleep(100 * time.Millisecond)
	cs, sc = tap.Bytes()
	P("第二次调用用时 %s;这一次调用的 TCP 字节数:客户端→服务端 %d,服务端→客户端 %d", Ms(el), cs, sc)
	tap.Dump()
	first := 0
	for _, e := range ev {
		if e.Dir == "C→S" && e.Type == "HEADERS" { first = int(e.Len); break }
	}
	second := 0
	for _, e := range tap.Snapshot() {
		if e.Dir == "C→S" && e.Type == "HEADERS" { second = int(e.Len); break }
	}
	P("请求 HEADERS 帧负载:第一次 %d 字节,第二次 %d 字节", first, second)
	fmt.Print()
}
