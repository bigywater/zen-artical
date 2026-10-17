package main

import (
	"context"
	"fmt"
	"sort"
	"strings"
	"sync/atomic"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/health"
	hpb "google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/resolver"
	"google.golang.org/grpc/resolver/manual"
	"google.golang.org/grpc/status"
	. "grpcgo/common"
	"grpcgo/pb"
)

var insec = grpc.WithTransportCredentials(insecure.NewCredentials())

func em(err error) string {
	st, _ := status.FromError(err)
	return fmt.Sprintf("code=%s message=%q", st.Code(), st.Message())
}

func startHealth(hs *health.Server, impl *DemoServer) (string, func()) {
	return StartReg(impl, func(s *grpc.Server) { hpb.RegisterHealthServer(s, hs) })
}

func main() {
	Sec("一:Check:服务名为空(整体)、没登记的服务名、登记为 NOT_SERVING 的服务名各返回什么;List 返回什么")
	{
		hs := health.NewServer()
		addr, stop := startHealth(hs, &DemoServer{})
		conn, _ := grpc.NewClient(addr, insec)
		hc := hpb.NewHealthClient(conn)
		ck := func(svc string) string {
			r, err := hc.Check(context.Background(), &hpb.HealthCheckRequest{Service: svc})
			if err != nil {
				return "RPC 失败 " + em(err)
			}
			return "RPC 成功,status=" + r.Status.String()
		}
		P("新建的 health.Server,Check(\"\"):%s", ck(""))
		P("Check(\"demo.Demo\")(没登记):%s", ck("demo.Demo"))
		hs.SetServingStatus("demo.Demo", hpb.HealthCheckResponse_NOT_SERVING)
		P("SetServingStatus(demo.Demo, NOT_SERVING) 之后 Check:%s", ck("demo.Demo"))
		hs.SetServingStatus("demo.Demo", hpb.HealthCheckResponse_SERVING)
		P("SetServingStatus(demo.Demo, SERVING) 之后 Check:%s", ck("demo.Demo"))
		lr, err := hc.List(context.Background(), &hpb.HealthListRequest{})
		var ks []string
		if err == nil {
			for k, v := range lr.Statuses {
				ks = append(ks, fmt.Sprintf("%q:%s", k, v.Status))
			}
		}
		sort.Strings(ks)
		P("List:err=%v;%s", err, strings.Join(ks, " "))
		conn.Close()
		stop()
	}

	Sec("二:Watch:对没登记的服务名、状态变化、重复设置同一个状态、1000 次快速翻转,客户端各收到什么")
	{
		hs := health.NewServer()
		addr, stop := startHealth(hs, &DemoServer{})
		conn, _ := grpc.NewClient(addr, insec)
		hc := hpb.NewHealthClient(conn)
		ctx, cancel := context.WithCancel(context.Background())
		st, _ := hc.Watch(ctx, &hpb.HealthCheckRequest{Service: "svc"})
		var got atomic.Int64
		msgs := make(chan string, 4096)
		go func() {
			for {
				r, err := st.Recv()
				if err != nil {
					return
				}
				got.Add(1)
				msgs <- r.Status.String()
			}
		}()
		drain := func() []string {
			time.Sleep(200 * time.Millisecond)
			var o []string
			for {
				select {
				case m := <-msgs:
					o = append(o, m)
				default:
					return o
				}
			}
		}
		P("Watch(\"svc\") 刚开始(没登记):收到 %v", drain())
		hs.SetServingStatus("svc", hpb.HealthCheckResponse_SERVING)
		P("SetServingStatus(SERVING):收到 %v", drain())
		hs.SetServingStatus("svc", hpb.HealthCheckResponse_SERVING)
		hs.SetServingStatus("svc", hpb.HealthCheckResponse_SERVING)
		P("再连续设置 2 次 SERVING:收到 %v", drain())
		hs.SetServingStatus("svc", hpb.HealthCheckResponse_NOT_SERVING)
		P("设为 NOT_SERVING:收到 %v", drain())
		t0 := time.Now()
		hs.SetServingStatus("svc", hpb.HealthCheckResponse_SERVING)
		<-func() chan struct{} {
			c := make(chan struct{})
			go func() {
				for got.Load() < 4 {
					time.Sleep(50 * time.Microsecond)
				}
				close(c)
			}()
			return c
		}()
		P("从 SetServingStatus 到客户端收到的延迟:%s", Ms(time.Since(t0)))
		drain()
		got.Store(0)
		for i := 0; i < 1000; i++ {
			if i%2 == 0 {
				hs.SetServingStatus("svc", hpb.HealthCheckResponse_NOT_SERVING)
			} else {
				hs.SetServingStatus("svc", hpb.HealthCheckResponse_SERVING)
			}
		}
		ms := drain()
		P("紧接着快速交替设置 1000 次(最后一次是 SERVING):客户端收到 %d 条,最后一条 %s", len(ms), ms[len(ms)-1])
		cancel()
		conn.Close()
		stop()
	}

	Sec("三:Shutdown / Resume:Shutdown 之后所有服务变成 NOT_SERVING,之后的 SetServingStatus 被忽略;Resume 之后恢复")
	{
		hs := health.NewServer()
		hs.SetServingStatus("svc", hpb.HealthCheckResponse_SERVING)
		addr, stop := startHealth(hs, &DemoServer{})
		conn, _ := grpc.NewClient(addr, insec)
		hc := hpb.NewHealthClient(conn)
		ck := func(svc string) string {
			r, err := hc.Check(context.Background(), &hpb.HealthCheckRequest{Service: svc})
			if err != nil {
				return em(err)
			}
			return r.Status.String()
		}
		P("初始:\"\" → %s;svc → %s", ck(""), ck("svc"))
		hs.Shutdown()
		P("Shutdown 之后:\"\" → %s;svc → %s", ck(""), ck("svc"))
		hs.SetServingStatus("svc", hpb.HealthCheckResponse_SERVING)
		P("Shutdown 之后再 SetServingStatus(svc, SERVING):svc → %s(被忽略)", ck("svc"))
		hs.Resume()
		P("Resume 之后:\"\" → %s;svc → %s", ck(""), ck("svc"))
		conn.Close()
		stop()
	}

	Sec("四:客户端健康检查(服务配置 healthCheckConfig):3 个后端 + round_robin,把后端 1 设成 NOT_SERVING;对照:不配置 healthCheckConfig")
	for _, withHC := range []bool{false, true} {
		var hss []*health.Server
		var hits [3]atomic.Int64
		var addrs []resolver.Address
		var stops []func()
		for i := 0; i < 3; i++ {
			i := i
			hs := health.NewServer()
			hss = append(hss, hs)
			a, s := startHealth(hs, &DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
				hits[i].Add(1)
				return &pb.Resp{N: int32(i)}, nil
			}})
			stops = append(stops, s)
			addrs = append(addrs, resolver.Address{Addr: a})
		}
		r := manual.NewBuilderWithScheme("demo")
		r.InitialState(resolver.State{Addresses: addrs})
		sc := `{"loadBalancingConfig":[{"round_robin":{}}]}`
		if withHC {
			sc = `{"loadBalancingConfig":[{"round_robin":{}}],"healthCheckConfig":{"serviceName":""}}`
		}
		conn, _ := grpc.NewClient("demo:///svc", insec, grpc.WithResolvers(r), grpc.WithDefaultServiceConfig(sc))
		cl := pb.NewDemoClient(conn)
		call := func() error {
			ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
			defer cancel()
			_, err := cl.Unary(ctx, &pb.Req{})
			return err
		}
		for i := 0; i < 30; i++ {
			call()
		}
		time.Sleep(200 * time.Millisecond)
		snap := func() string {
			s := fmt.Sprintf("[%d %d %d]", hits[0].Load(), hits[1].Load(), hits[2].Load())
			for i := range hits {
				hits[i].Store(0)
			}
			return s
		}
		snap()
		for i := 0; i < 60; i++ {
			call()
		}
		name := "无 healthCheckConfig"
		if withHC {
			name = "有 healthCheckConfig"
		}
		P("%s:全部 SERVING,60 次调用各后端收到 %s", name, snap())
		t0 := time.Now()
		hss[1].SetServingStatus("", hpb.HealthCheckResponse_NOT_SERVING)
		lastBad := time.Duration(-1)
		for time.Since(t0) < 1500*time.Millisecond {
			call()
			if hits[1].Load() > 0 {
				lastBad = time.Since(t0)
				hits[1].Store(0)
			}
			time.Sleep(5 * time.Millisecond)
		}
		for i := range hits {
			hits[i].Store(0)
		}
		for i := 0; i < 60; i++ {
			call()
		}
		lb := "之后一次都没有打到后端 1"
		if lastBad >= 0 {
			lb = "最后一次打到后端 1 是在设置之后 " + Ms(lastBad)
		}
		P("%s:后端 1 设为 NOT_SERVING 后 1.5 秒内,%s;之后 60 次调用各后端收到 %s", name, lb, snap())
		if withHC {
			for _, h := range hss {
				h.SetServingStatus("", hpb.HealthCheckResponse_NOT_SERVING)
			}
			time.Sleep(300 * time.Millisecond)
			err := call()
			P("有 healthCheckConfig:3 个后端全部 NOT_SERVING 后的调用:%s", em(err))
			hss[2].SetServingStatus("", hpb.HealthCheckResponse_SERVING)
			time.Sleep(300 * time.Millisecond)
			err = call()
			P("后端 2 恢复 SERVING 后的调用:%v", err)
		}
		conn.Close()
		for _, s := range stops {
			s()
		}
	}
}
