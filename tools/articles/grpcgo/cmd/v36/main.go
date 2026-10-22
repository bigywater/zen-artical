package main

import (
	"context"
	"fmt"
	"net"
	"os"
	"sort"
	"strconv"
	"strings"
	"time"

	"grpcgo/pb"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
)

type srv struct {
	pb.UnimplementedDemoServer
	name string
}

func (s *srv) Unary(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
	if strings.HasPrefix(r.Msg, "sleep:") {
		ms, _ := strconv.Atoi(strings.TrimPrefix(r.Msg, "sleep:"))
		time.Sleep(time.Duration(ms) * time.Millisecond)
	}
	return &pb.Resp{Msg: s.name, N: int32(len(r.Payload))}, nil
}

// ServerStream:共发 r.N 条消息,每条之前 sleep r.Msg(毫秒)
func (s *srv) ServerStream(r *pb.Req, st pb.Demo_ServerStreamServer) error {
	gap, _ := strconv.Atoi(r.Msg)
	for i := 0; i < int(r.N); i++ {
		time.Sleep(time.Duration(gap) * time.Millisecond)
		if err := st.Send(&pb.Resp{Msg: s.name, N: int32(i)}); err != nil {
			return err
		}
	}
	return nil
}

func dial(addr string) *grpc.ClientConn {
	c, err := grpc.NewClient(addr, grpc.WithTransportCredentials(insecure.NewCredentials()), grpc.WithDefaultCallOptions(grpc.MaxCallSendMsgSize(64<<20)))
	if err != nil {
		panic(err)
	}
	return c
}

func main() {
	switch os.Args[1] {
	case "server":
		l, err := net.Listen("tcp", "127.0.0.1:"+os.Args[2])
		if err != nil {
			panic(err)
		}
		g := grpc.NewServer(grpc.MaxRecvMsgSize(64 << 20))
		pb.RegisterDemoServer(g, &srv{name: os.Args[3]})
		g.Serve(l)
	case "unary": // unary <addr> <n> <payloadBytes> <msg> <timeoutMs>
		n, _ := strconv.Atoi(os.Args[3])
		pl, _ := strconv.Atoi(os.Args[4])
		to, _ := strconv.Atoi(os.Args[6])
		c := dial(os.Args[2])
		cl := pb.NewDemoClient(c)
		cnt := map[string]int{}
		var first time.Duration
		for i := 0; i < n; i++ {
			ctx := context.Background()
			if to > 0 {
				var cancel context.CancelFunc
				ctx, cancel = context.WithTimeout(ctx, time.Duration(to)*time.Millisecond)
				defer cancel()
			}
			t0 := time.Now()
			r, err := cl.Unary(ctx, &pb.Req{Msg: os.Args[5], Payload: make([]byte, pl)})
			if i == 0 {
				first = time.Since(t0)
			}
			if err != nil {
				s := status.Convert(err)
				cnt["ERR:"+s.Code().String()+":"+short(s.Message())]++
			} else {
				cnt["OK:"+r.Msg]++
			}
		}
		keys := []string{}
		for k := range cnt {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		for _, k := range keys {
			fmt.Printf("RESULT %s %d\n", k, cnt[k])
		}
		fmt.Printf("FIRST_MS %.1f\n", float64(first.Microseconds())/1000)
	case "stream": // stream <addr> <gapMs> <count> <timeoutMs>
		gap, _ := strconv.Atoi(os.Args[3])
		cn, _ := strconv.Atoi(os.Args[4])
		to, _ := strconv.Atoi(os.Args[5])
		c := dial(os.Args[2])
		cl := pb.NewDemoClient(c)
		ctx := context.Background()
		if to > 0 {
			var cancel context.CancelFunc
			ctx, cancel = context.WithTimeout(ctx, time.Duration(to)*time.Millisecond)
			defer cancel()
		}
		t0 := time.Now()
		st, err := cl.ServerStream(ctx, &pb.Req{Msg: strconv.Itoa(gap), N: int32(cn)})
		got := 0
		var last error
		if err == nil {
			for {
				_, e := st.Recv()
				if e != nil {
					last = e
					break
				}
				got++
			}
		} else {
			last = err
		}
		code := "EOF(正常结束)"
		if last != nil && last.Error() != "EOF" {
			s := status.Convert(last)
			code = s.Code().String() + ":" + short(s.Message())
		}
		fmt.Printf("STREAM got=%d code=%s elapsed_ms=%.0f\n", got, code, float64(time.Since(t0).Milliseconds()))
	}
	_ = codes.OK
}

func short(m string) string {
	m = strings.ReplaceAll(m, " ", "_")
	if len(m) > 60 {
		m = m[:60]
	}
	return m
}
