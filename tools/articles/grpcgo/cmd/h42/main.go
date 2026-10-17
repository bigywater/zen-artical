package main

import (
	"bytes"
	"context"
	"fmt"
	"net"
	"os"
	"os/exec"
	"sort"
	"strings"
	"sync"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/channelz/grpc_channelz_v1"
	channelzservice "google.golang.org/grpc/channelz/service"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/grpclog"
	"google.golang.org/grpc/status"
	. "grpcgo/common"
	"grpcgo/pb"
)

var insec = grpc.WithTransportCredentials(insecure.NewCredentials())

// scenario 是被子进程执行的小程序:连一个不存在的服务、正常调用、失败调用、优雅停机。
func scenario() {
	addr, _ := Start(&DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
		if r.N == 1 {
			return nil, status.Error(codes.Internal, "boom")
		}
		return &pb.Resp{}, nil
	}})
	conn, _ := grpc.NewClient(addr, insec)
	cl := pb.NewDemoClient(conn)
	cl.Unary(context.Background(), &pb.Req{})
	cl.Unary(context.Background(), &pb.Req{N: 1})
	conn.Close()
	l, _ := net.Listen("tcp", "127.0.0.1:0")
	dead := l.Addr().String()
	l.Close()
	c2, _ := grpc.NewClient(dead, insec)
	ctx, cancel := context.WithTimeout(context.Background(), 300*time.Millisecond)
	pb.NewDemoClient(c2).Unary(ctx, &pb.Req{})
	cancel()
	c2.Close()
	time.Sleep(100 * time.Millisecond)
}

// customLogger 统计各级别的条数。
type customLogger struct {
	mu     sync.Mutex
	counts map[string]int
	first  []string
}

func (c *customLogger) add(level, s string) {
	c.mu.Lock()
	c.counts[level]++
	if len(c.first) < 3 {
		c.first = append(c.first, level+": "+strings.TrimSpace(s))
	}
	c.mu.Unlock()
}
func (c *customLogger) Info(a ...any)               { c.add("INFO", fmt.Sprint(a...)) }
func (c *customLogger) Infoln(a ...any)             { c.add("INFO", fmt.Sprint(a...)) }
func (c *customLogger) Infof(f string, a ...any)    { c.add("INFO", fmt.Sprintf(f, a...)) }
func (c *customLogger) Warning(a ...any)            { c.add("WARNING", fmt.Sprint(a...)) }
func (c *customLogger) Warningln(a ...any)          { c.add("WARNING", fmt.Sprint(a...)) }
func (c *customLogger) Warningf(f string, a ...any) { c.add("WARNING", fmt.Sprintf(f, a...)) }
func (c *customLogger) Error(a ...any)              { c.add("ERROR", fmt.Sprint(a...)) }
func (c *customLogger) Errorln(a ...any)            { c.add("ERROR", fmt.Sprint(a...)) }
func (c *customLogger) Errorf(f string, a ...any)   { c.add("ERROR", fmt.Sprintf(f, a...)) }
func (c *customLogger) Fatal(a ...any)              { c.add("FATAL", fmt.Sprint(a...)); os.Exit(1) }
func (c *customLogger) Fatalln(a ...any)            { c.Fatal(a...) }
func (c *customLogger) Fatalf(f string, a ...any)   { c.Fatal(fmt.Sprintf(f, a...)) }
func (c *customLogger) V(l int) bool                { return l <= 2 }

func short(s string, n int) string {
	if len(s) > n {
		return s[:n] + "…"
	}
	return s
}

func main() {
	if len(os.Args) > 1 {
		switch os.Args[1] {
		case "scenario":
			scenario()
			return
		case "custom":
			cl := &customLogger{counts: map[string]int{}}
			grpclog.SetLoggerV2(cl)
			scenario()
			var ks []string
			for k, v := range cl.counts {
				ks = append(ks, fmt.Sprintf("%s %d 条", k, v))
			}
			sort.Strings(ks)
			fmt.Println("自定义 logger 收到:" + strings.Join(ks, "、"))
			for _, f := range cl.first {
				fmt.Println("    " + short(f, 150))
			}
			return
		}
	}

	Sec("一:环境变量控制 grpc-go 自带日志(输出到 stderr):同一个小程序(连一个不存在的服务、正常调用、失败调用、关闭)在不同环境变量下 stderr 的行数")
	{
		for _, env := range [][]string{
			nil,
			{"GRPC_GO_LOG_SEVERITY_LEVEL=error"},
			{"GRPC_GO_LOG_SEVERITY_LEVEL=warning"},
			{"GRPC_GO_LOG_SEVERITY_LEVEL=info"},
			{"GRPC_GO_LOG_SEVERITY_LEVEL=info", "GRPC_GO_LOG_VERBOSITY_LEVEL=2"},
			{"GRPC_GO_LOG_SEVERITY_LEVEL=info", "GRPC_GO_LOG_VERBOSITY_LEVEL=99"},
		} {
			cmd := exec.Command(os.Args[0], "scenario")
			cmd.Env = append(os.Environ(), env...)
			var stderr bytes.Buffer
			cmd.Stderr = &stderr
			cmd.Run()
			lines := strings.Split(strings.TrimSpace(stderr.String()), "\n")
			if stderr.Len() == 0 {
				lines = nil
			}
			by := map[string]int{}
			entries := 0
			warn := ""
			for _, l := range lines {
				if len(l) > 20 && l[4] == '/' && l[7] == '/' { // 一条日志以日期开头;其余是续行
					entries++
					for _, lv := range []string{"INFO", "WARNING", "ERROR"} {
						if strings.HasPrefix(l[20:], lv) {
							by[lv]++
							if lv == "WARNING" && warn == "" {
								warn = l[20:]
							}
						}
					}
				}
			}
			name := "(不设置)"
			if env != nil {
				name = strings.Join(env, " ")
			}
			P("%-66s stderr %3d 行,共 %3d 条日志(INFO %d、WARNING %d、ERROR %d)", name, len(lines), entries, by["INFO"], by["WARNING"], by["ERROR"])
			if warn != "" && strings.HasSuffix(name, "warning") {
				P("    那 1 条 WARNING:%s", short(warn, 170))
			}
		}
	}

	Sec("二:INFO 级别时日志里有什么:前几行、以及 JSON 格式(GRPC_GO_LOG_FORMATTER=json)的样子")
	{
		for _, env := range [][]string{{"GRPC_GO_LOG_SEVERITY_LEVEL=info"}, {"GRPC_GO_LOG_SEVERITY_LEVEL=info", "GRPC_GO_LOG_FORMATTER=json"}} {
			cmd := exec.Command(os.Args[0], "scenario")
			cmd.Env = append(os.Environ(), env...)
			var stderr bytes.Buffer
			cmd.Stderr = &stderr
			cmd.Run()
			lines := strings.Split(strings.TrimSpace(stderr.String()), "\n")
			P("%s:共 %d 行,前 6 行:", strings.Join(env, " "), len(lines))
			for i, l := range lines {
				if i >= 6 {
					break
				}
				P("    %s", short(l, 170))
			}
		}
	}

	Sec("三:用自己的 logger(grpclog.SetLoggerV2,必须在使用 grpc 之前设置):同一个小程序里,V(2) 返回 true 时各级别收到多少条")
	{
		cmd := exec.Command(os.Args[0], "custom")
		out, _ := cmd.Output()
		for _, l := range strings.Split(strings.TrimSpace(string(out)), "\n") {
			P("%s", l)
		}
	}

	Sec("四:channelz:服务端注册 channelz 服务后,可以问“当前有哪些通道/连接、调用成功失败各多少”。客户端 100 次成功 + 5 次失败调用之后,从服务端的 channelz 读到的客户端通道和服务端的统计")
	{
		addr, stop := StartReg(&DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
			if r.N == 1 {
				return nil, status.Error(codes.Internal, "boom")
			}
			return &pb.Resp{}, nil
		}}, func(s *grpc.Server) { channelzservice.RegisterChannelzServiceToServer(s) })
		conn, _ := grpc.NewClient(addr, insec)
		cl := pb.NewDemoClient(conn)
		for i := 0; i < 100; i++ {
			cl.Unary(context.Background(), &pb.Req{})
		}
		for i := 0; i < 5; i++ {
			cl.Unary(context.Background(), &pb.Req{N: 1})
		}
		time.Sleep(100 * time.Millisecond)
		// 用一条新连接查询
		qc, _ := grpc.NewClient(addr, insec)
		cz := grpc_channelz_v1.NewChannelzClient(qc)
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		defer cancel()
		tc, err := cz.GetTopChannels(ctx, &grpc_channelz_v1.GetTopChannelsRequest{})
		if err != nil {
			P("GetTopChannels 出错:%v", err)
		}
		for i, ch := range tc.GetChannel() {
			d := ch.GetData()
			P("通道 #%d target=%s 状态=%s;调用 开始 %d、成功 %d、失败 %d;子通道 %d 个", i+1, d.GetTarget(), d.GetState().GetState(), d.GetCallsStarted(), d.GetCallsSucceeded(), d.GetCallsFailed(), len(ch.GetSubchannelRef()))
		}
		ts, _ := cz.GetServers(ctx, &grpc_channelz_v1.GetServersRequest{})
		for _, sv := range ts.GetServer() {
			d := sv.GetData()
			P("服务端 调用 开始 %d、成功 %d、失败 %d;监听 socket %d 个", d.GetCallsStarted(), d.GetCallsSucceeded(), d.GetCallsFailed(), len(sv.GetListenSocket()))
			ss, _ := cz.GetServerSockets(ctx, &grpc_channelz_v1.GetServerSocketsRequest{ServerId: sv.GetRef().GetServerId()})
			for k, so := range ss.GetSocketRef() {
				sk, _ := cz.GetSocket(ctx, &grpc_channelz_v1.GetSocketRequest{SocketId: so.GetSocketId()})
				sd := sk.GetSocket().GetData()
				P("    服务端连接 #%d:流 开始 %d、成功 %d、失败 %d;收到消息 %d、发出消息 %d;keepalive 发出 %d", k+1, sd.GetStreamsStarted(), sd.GetStreamsSucceeded(), sd.GetStreamsFailed(), sd.GetMessagesReceived(), sd.GetMessagesSent(), sd.GetKeepAlivesSent())
			}
		}
		qc.Close()
		conn.Close()
		stop()
	}
}
