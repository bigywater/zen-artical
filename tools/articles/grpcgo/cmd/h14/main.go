package main

import (
	"context"
	"fmt"
	"strings"
	"sync/atomic"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/resolver"
	"google.golang.org/grpc/resolver/manual"
	"google.golang.org/grpc/status"
	. "grpcgo/common"
	"grpcgo/pb"
)

var insec = grpc.WithTransportCredentials(insecure.NewCredentials())

type backend struct {
	addr  string
	hits  atomic.Int64
	delay atomic.Int64 // ns
	stop  func()
}

func newBackend(idx int) *backend {
	b := &backend{}
	b.addr, b.stop = Start(&DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
		b.hits.Add(1)
		if d := b.delay.Load(); d > 0 {
			time.Sleep(time.Duration(d))
		}
		return &pb.Resp{N: int32(idx)}, nil
	}})
	return b
}

func addrsOf(bs []*backend) []resolver.Address {
	var as []resolver.Address
	for _, b := range bs {
		as = append(as, resolver.Address{Addr: b.addr})
	}
	return as
}

func dial(bs []*backend, lb string) (*grpc.ClientConn, pb.DemoClient, *manual.Resolver) {
	r := manual.NewBuilderWithScheme("demo")
	r.InitialState(resolver.State{Addresses: addrsOf(bs)})
	conn, _ := grpc.NewClient("demo:///svc", insec, grpc.WithResolvers(r), grpc.WithDefaultServiceConfig(fmt.Sprintf(`{"loadBalancingConfig":[%s]}`, lb)))
	return conn, pb.NewDemoClient(conn), r
}

const (
	PF = `{"pick_first":{}}`
	RR = `{"round_robin":{}}`
)

func call(cl pb.DemoClient) (int, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	r, err := cl.Unary(ctx, &pb.Req{})
	if err != nil {
		return -1, err
	}
	return int(r.N), nil
}

func hits(bs []*backend) []int64 {
	var o []int64
	for _, b := range bs {
		o = append(o, b.hits.Load())
	}
	return o
}
func resetHits(bs []*backend) {
	for _, b := range bs {
		b.hits.Store(0)
	}
}

func seq(xs []int) string {
	var o []string
	for _, x := range xs {
		if x < 0 {
			o = append(o, "x")
		} else {
			o = append(o, fmt.Sprint(x))
		}
	}
	return strings.Join(o, " ")
}

func main() {
	var bs []*backend
	for i := 0; i < 3; i++ {
		bs = append(bs, newBackend(i))
	}
	defer func() {
		for _, b := range bs {
			b.stop()
		}
	}()

	Sec("一:3 个后端,300 次顺序调用,每个后端各收到多少次")
	for _, c := range []struct{ name, lb string }{{"pick_first", PF}, {"round_robin", RR}} {
		resetHits(bs)
		conn, cl, _ := dial(bs, c.lb)
		for i := 0; i < 300; i++ {
			call(cl)
		}
		P("%-11s 三个后端收到的次数 %v", c.name, hits(bs))
		conn.Close()
	}

	Sec("二:round_robin 的顺序:全新的客户端各发 9 次调用,每次是哪个后端回的(6 个全新的客户端)")
	for i := 0; i < 6; i++ {
		conn, cl, _ := dial(bs, RR)
		var xs []int
		for j := 0; j < 9; j++ {
			n, _ := call(cl)
			xs = append(xs, n)
		}
		P("客户端 %d:%s", i+1, seq(xs))
		conn.Close()
	}

	Sec("三:调用到一半,正在用的后端 0 被停掉(Stop):接下来每次调用谁回的(x 表示失败)。pick_first 的地址列表是 [0 1 2]")
	for _, c := range []struct{ name, lb string }{{"pick_first", PF}, {"round_robin", RR}} {
		// 停掉后等 50 ms 再继续:看切换之后的样子
		{
			var fresh []*backend
			for i := 0; i < 3; i++ {
				fresh = append(fresh, newBackend(i))
			}
			conn, cl, _ := dial(fresh, c.lb)
			var xs []int
			for j := 0; j < 24; j++ {
				if j == 8 {
					fresh[0].stop()
					time.Sleep(50 * time.Millisecond)
				}
				n, _ := call(cl)
				xs = append(xs, n)
			}
			P("%-11s 前 8 次之后停掉后端 0、等 50 ms:%s", c.name, seq(xs))
			conn.Close()
			for _, b := range fresh[1:] {
				b.stop()
			}
		}
		// 停掉后马上继续调用,重复 20 次:有没有失败的调用
		failedRuns, failedCalls, total := 0, 0, 0
		firstErr := ""
		for trial := 0; trial < 20; trial++ {
			var fresh []*backend
			for i := 0; i < 3; i++ {
				fresh = append(fresh, newBackend(i))
			}
			conn, cl, _ := dial(fresh, c.lb)
			for j := 0; j < 8; j++ {
				call(cl)
			}
			fresh[0].stop()
			bad := 0
			for j := 0; j < 16; j++ {
				total++
				if _, err := call(cl); err != nil {
					bad++
					if firstErr == "" {
						st, _ := status.FromError(err)
						firstErr = fmt.Sprintf("code=%s message=%q", st.Code(), st.Message())
					}
				}
			}
			if bad > 0 {
				failedRuns++
				failedCalls += bad
			}
			conn.Close()
			for _, b := range fresh[1:] {
				b.stop()
			}
		}
		if firstErr == "" {
			firstErr = "(没有失败)"
		}
		P("%-11s 停掉后端 0 之后马上继续调用,重复 20 次、共 %d 次调用:有失败的有 %d 次,失败的调用共 %d 个;第一个失败 %s", c.name, total, failedRuns, failedCalls, firstErr)
	}

	Sec("四:服务发现推来新的地址列表:从 [0 1] 变成 [0 1 2](加一个后端),再变成 [1 2](去掉 0)。每个阶段 60 次调用各后端的次数")
	for _, c := range []struct{ name, lb string }{{"pick_first", PF}, {"round_robin", RR}} {
		conn, cl, r := dial(bs[:2], c.lb)
		phase := func(label string) {
			resetHits(bs)
			for i := 0; i < 60; i++ {
				call(cl)
			}
			P("%-11s %-18s 三个后端收到的次数 %v", c.name, label, hits(bs))
		}
		phase("地址 [0 1]")
		r.UpdateState(resolver.State{Addresses: addrsOf(bs[0:3])})
		time.Sleep(100 * time.Millisecond)
		phase("加入 2 → [0 1 2]")
		r.UpdateState(resolver.State{Addresses: addrsOf(bs[1:3])})
		time.Sleep(100 * time.Millisecond)
		phase("去掉 0 → [1 2]")
		conn.Close()
	}

	Sec("五:其中一个后端很慢(每次 100 ms),30 次顺序调用的总耗时;慢的是第几个地址有区别")
	for _, slow := range []int{0, 2} {
		for _, b := range bs {
			b.delay.Store(0)
		}
		bs[slow].delay.Store(int64(100 * time.Millisecond))
		for _, c := range []struct{ name, lb string }{{"pick_first", PF}, {"round_robin", RR}} {
			conn, cl, _ := dial(bs, c.lb)
			call(cl)
			resetHits(bs)
			t0 := time.Now()
			for i := 0; i < 30; i++ {
				call(cl)
			}
			P("慢的是后端 %d:%-11s 30 次共 %s;各后端次数 %v", slow, c.name, Ms(time.Since(t0)), hits(bs))
			conn.Close()
		}
	}
	for _, b := range bs {
		b.delay.Store(0)
	}

	Sec("六:pick_first 的 shuffleAddressList:全新的客户端(30 个)各发 1 次调用,落到哪个后端")
	for _, c := range []struct{ name, lb string }{{"默认", PF}, {"shuffleAddressList=true", `{"pick_first":{"shuffleAddressList":true}}`}} {
		resetHits(bs)
		for i := 0; i < 30; i++ {
			conn, cl, _ := dial(bs, c.lb)
			call(cl)
			conn.Close()
		}
		P("%-24s 三个后端收到的次数 %v", c.name, hits(bs))
	}
}
