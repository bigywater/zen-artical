package main

import (
	"bufio"
	"bytes"
	"context"
	"crypto/rand"
	"fmt"
	"io"
	"os"
	"os/exec"
	"sort"
	"strings"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/encoding"
	"google.golang.org/grpc/encoding/gzip"
	"google.golang.org/grpc/status"
	. "grpcgo/common"
	"grpcgo/pb"
)

var insec = grpc.WithTransportCredentials(insecure.NewCredentials())

func compressible(n int) []byte {
	return bytes.Repeat([]byte(`{"user":"alice","action":"login","ok":true}`), n/42+1)[:n]
}
func random(n int) []byte { b := make([]byte, n); rand.Read(b); return b }
func jsonish(n int) []byte {
	var sb strings.Builder
	for i := 0; sb.Len() < n; i++ {
		fmt.Fprintf(&sb, `{"id":%d,"name":"user-%d","email":"user%d@example.com","tags":["a","b","c"],"score":%d.%d},`, i, i*7%1000, i*13%5000, i%100, i%10)
	}
	return []byte(sb.String()[:n])
}

func flags(tap *Tap, dir string) string {
	for _, e := range tap.Snapshot() {
		if e.Dir == dir && e.Type == "DATA" && len(e.Data) >= 5 {
			return fmt.Sprint(e.Data[0])
		}
	}
	return "无"
}
func hdr(tap *Tap, dir, name string) string {
	for _, e := range tap.Snapshot() {
		if e.Dir == dir && e.Type == "HEADERS" {
			for _, kv := range strings.Split(e.Info, "; ") {
				if strings.HasPrefix(kv, name+":") {
					return strings.TrimSpace(strings.TrimPrefix(kv, name+":"))
				}
			}
		}
	}
	return "无"
}

func median(ds []time.Duration) time.Duration {
	sort.Slice(ds, func(i, j int) bool { return ds[i] < ds[j] })
	return ds[len(ds)/2]
}

func main() {
	if len(os.Args) > 1 && os.Args[1] == "srv" {
		addr, stop := Start(&DemoServer{})
		fmt.Println(addr)
		io.Copy(io.Discard, os.Stdin)
		stop()
		return
	}
	echo := &DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
		return &pb.Resp{Payload: r.Payload}, nil
	}}

	Sec("一:请求和响应各带 100 KiB 的可压缩数据(重复的 JSON 片段)、100 KiB 的随机数据、100 KiB 的类 JSON 文本:不压缩与客户端 UseCompressor(gzip) 的线上字节数(代理统计两个方向的全部字节)")
	{
		addr, stop := Start(echo)
		tap := NewTap(addr)
		conn, _ := grpc.NewClient(tap.Addr, insec)
		cl := pb.NewDemoClient(conn)
		cl.Unary(context.Background(), &pb.Req{})
		for _, c := range []struct {
			name string
			data []byte
		}{{"重复的 JSON 片段", compressible(100 * 1024)}, {"随机字节", random(100 * 1024)}, {"类 JSON 文本", jsonish(100 * 1024)}} {
			var cs [2]int64
			var sc [2]int64
			for i, opt := range []grpc.CallOption{nil, grpc.UseCompressor(gzip.Name)} {
				tap.Reset()
				tap.ResetBytes()
				var opts []grpc.CallOption
				if opt != nil {
					opts = append(opts, opt)
				}
				cl.Unary(context.Background(), &pb.Req{Payload: c.data}, opts...)
				time.Sleep(50 * time.Millisecond)
				cs[i], sc[i] = tap.BytesCS, tap.BytesSC
				if i == 1 {
					P("%-10s 客户端→服务端 不压缩 %d 字节 / gzip %d 字节(%.1f%%);服务端→客户端 不压缩 %d / gzip %d 字节(%.1f%%);gzip 时请求的压缩标志位 %s、grpc-encoding=%s;响应的压缩标志位 %s、grpc-encoding=%s", c.name, cs[0], cs[1], 100*float64(cs[1])/float64(cs[0]), sc[0], sc[1], 100*float64(sc[1])/float64(sc[0]), flags(tap, "C→S"), hdr(tap, "C→S", "grpc-encoding"), flags(tap, "S→C"), hdr(tap, "S→C", "grpc-encoding"))
				}
			}
		}
		conn.Close()
		tap.Close()
		stop()
	}

	Sec("二:谁决定响应是否压缩:客户端用 gzip 发请求而服务端什么都不做 vs 客户端不压缩但服务端 handler 里调用 grpc.SetSendCompressor(ctx, gzip);客户端声明的 grpc-accept-encoding")
	{
		var setErr error
		mode := "none"
		srv := &DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
			if mode == "set" {
				setErr = grpc.SetSendCompressor(ctx, gzip.Name)
			}
			return &pb.Resp{Payload: r.Payload}, nil
		}}
		addr, stop := Start(srv)
		tap := NewTap(addr)
		conn, _ := grpc.NewClient(tap.Addr, insec)
		cl := pb.NewDemoClient(conn)
		data := compressible(100 * 1024)
		for _, c := range []struct {
			name string
			mode string
			opts []grpc.CallOption
		}{{"客户端 gzip,服务端不设置", "none", []grpc.CallOption{grpc.UseCompressor(gzip.Name)}}, {"客户端不压缩,服务端 SetSendCompressor(gzip)", "set", nil}} {
			mode = c.mode
			tap.Reset()
			tap.ResetBytes()
			cl.Unary(context.Background(), &pb.Req{Payload: data}, c.opts...)
			time.Sleep(50 * time.Millisecond)
			P("%-40s 请求标志位 %s、响应标志位 %s;请求头 grpc-accept-encoding=%s;响应头 grpc-encoding=%s;请求字节 %d、响应字节 %d;SetSendCompressor 返回 %v", c.name, flags(tap, "C→S"), flags(tap, "S→C"), hdr(tap, "C→S", "grpc-accept-encoding"), hdr(tap, "S→C", "grpc-encoding"), tap.BytesCS, tap.BytesSC, setErr)
		}
		conn.Close()
		tap.Close()
		stop()
	}

	Sec("三:压缩的 CPU 代价:本机回环(带宽几乎无限),往返 1 MiB 的数据,各 30 次的中位数耗时:不压缩 vs gzip(默认级别)")
	{
		addr, stop := Start(echo)
		conn, _ := grpc.NewClient(addr, insec)
		cl := pb.NewDemoClient(conn)
		for _, c := range []struct {
			name string
			data []byte
		}{{"重复的 JSON 片段", compressible(1 << 20)}, {"类 JSON 文本", jsonish(1 << 20)}, {"随机字节", random(1 << 20)}} {
			var res [2]time.Duration
			for i, opt := range []grpc.CallOption{nil, grpc.UseCompressor(gzip.Name)} {
				var opts []grpc.CallOption
				if opt != nil {
					opts = append(opts, opt)
				}
				for w := 0; w < 3; w++ {
					cl.Unary(context.Background(), &pb.Req{Payload: c.data}, opts...)
				}
				var ds []time.Duration
				for k := 0; k < 30; k++ {
					t0 := time.Now()
					cl.Unary(context.Background(), &pb.Req{Payload: c.data}, opts...)
					ds = append(ds, time.Since(t0))
				}
				res[i] = median(ds)
			}
			P("%-10s 不压缩 %s;gzip %s(%.1f 倍)", c.name, Ms(res[0]), Ms(res[1]), float64(res[1])/float64(res[0]))
		}
		conn.Close()
		stop()
	}

	Sec("四:gzip 级别:类 JSON 文本 1 MiB,级别 1(最快)、默认(-1)、9(最小)——请求方向的线上字节和单次往返耗时(中位数)")
	{
		addr, stop := Start(echo)
		tap := NewTap(addr)
		conn, _ := grpc.NewClient(tap.Addr, insec)
		cl := pb.NewDemoClient(conn)
		data := jsonish(1 << 20)
		for _, lv := range []int{1, -1, 9} {
			gzip.SetLevel(lv)
			cl.Unary(context.Background(), &pb.Req{Payload: data}, grpc.UseCompressor(gzip.Name))
			var ds []time.Duration
			var cs int64
			for k := 0; k < 20; k++ {
				tap.ResetBytes()
				t0 := time.Now()
				cl.Unary(context.Background(), &pb.Req{Payload: data}, grpc.UseCompressor(gzip.Name))
				ds = append(ds, time.Since(t0))
				cs = tap.BytesCS
			}
			P("级别 %2d:请求 %d 字节(原始 %d);往返 %s", lv, cs, len(data), Ms(median(ds)))
		}
		gzip.SetLevel(-1)
		conn.Close()
		tap.Close()
		stop()
	}

	Sec("五:服务端不认识的压缩算法:客户端注册了一个假的 \"fake\" 压缩器(只在客户端进程里),服务端是另一个进程")
	{
		cmd := exec.Command(os.Args[0], "srv")
		stdin, _ := cmd.StdinPipe()
		out, _ := cmd.StdoutPipe()
		cmd.Start()
		addr, _ := bufio.NewReader(out).ReadString('\n')
		addr = strings.TrimSpace(addr)
		encoding.RegisterCompressor(fakeComp{})
		tap := NewTap(addr)
		conn, _ := grpc.NewClient(tap.Addr, insec)
		cl := pb.NewDemoClient(conn)
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		_, err := cl.Unary(ctx, &pb.Req{Msg: "hello"}, grpc.UseCompressor("fake"))
		cancel()
		time.Sleep(50 * time.Millisecond)
		st, _ := status.FromError(err)
		P("服务端不认识 fake:code=%s message=%q;响应头里 grpc-accept-encoding=%s", st.Code(), st.Message(), hdr(tap, "S→C", "grpc-accept-encoding"))
		ctx, cancel = context.WithTimeout(context.Background(), 3*time.Second)
		_, err = cl.Unary(ctx, &pb.Req{Msg: "hello"})
		cancel()
		P("同一个连接上之后不压缩的调用:err=%v", err)
		conn.Close()
		tap.Close()
		stdin.Close()
		cmd.Wait()
	}
}

type fakeComp struct{}

func (fakeComp) Compress(w io.Writer) (io.WriteCloser, error) { return nopWC{w}, nil }
func (fakeComp) Decompress(r io.Reader) (io.Reader, error)    { return r, nil }
func (fakeComp) Name() string                                 { return "fake" }

type nopWC struct{ io.Writer }

func (nopWC) Close() error { return nil }
