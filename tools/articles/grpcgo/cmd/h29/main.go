package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"sort"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/grpc-ecosystem/grpc-gateway/v2/runtime"
	"google.golang.org/genproto/googleapis/rpc/errdetails"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/proto"
	. "grpcgo/common"
	"grpcgo/gwpb"
)

var insec = grpc.WithTransportCredentials(insecure.NewCredentials())

type gwServer struct {
	gwpb.UnimplementedGwServer
	mu       sync.Mutex
	lastMD   metadata.MD
	slowDone atomic.Value // "canceled" 或 "completed"
}

func (s *gwServer) Echo(ctx context.Context, it *gwpb.Item) (*gwpb.Item, error) { return it, nil }
func (s *gwServer) GetItem(ctx context.Context, r *gwpb.GetReq) (*gwpb.Item, error) {
	return &gwpb.Item{Id: r.Id, Name: r.Name, Count: 1}, nil
}
func (s *gwServer) Fail(ctx context.Context, r *gwpb.FailReq) (*gwpb.Item, error) {
	st := status.New(codes.Code(r.Code), fmt.Sprintf("failed with %d", r.Code))
	if r.Code == 3 {
		st, _ = st.WithDetails(&errdetails.ErrorInfo{Reason: "BAD", Domain: "demo.example"})
	}
	return nil, st.Err()
}
func (s *gwServer) Slow(ctx context.Context, r *gwpb.SlowReq) (*gwpb.Item, error) {
	select {
	case <-time.After(time.Duration(r.Ms) * time.Millisecond):
		s.slowDone.Store("completed")
		return &gwpb.Item{Id: "slow"}, nil
	case <-ctx.Done():
		s.slowDone.Store("canceled")
		return nil, ctx.Err()
	}
}
func (s *gwServer) Count(r *gwpb.CountReq, st gwpb.Gw_CountServer) error {
	for i := 0; i < int(r.N); i++ {
		st.Send(&gwpb.Item{Id: fmt.Sprint(i)})
	}
	return nil
}
func (s *gwServer) Meta(ctx context.Context, r *gwpb.GetReq) (*gwpb.Item, error) {
	md, _ := metadata.FromIncomingContext(ctx)
	var ks []string
	for k, v := range md {
		if strings.HasPrefix(k, ":") || k == "user-agent" || k == "content-type" || k == "grpc-accept-encoding" {
			continue
		}
		ks = append(ks, k+"="+strings.Join(v, ","))
	}
	sort.Strings(ks)
	return &gwpb.Item{Tags: ks}, nil
}

func startGW(srv *gwServer, opts ...runtime.ServeMuxOption) (grpcAddr, httpAddr string, stop func()) {
	gl, _ := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", FreePort()))
	gs := grpc.NewServer()
	gwpb.RegisterGwServer(gs, srv)
	go gs.Serve(gl)
	mux := runtime.NewServeMux(opts...)
	if err := gwpb.RegisterGwHandlerFromEndpoint(context.Background(), mux, gl.Addr().String(), []grpc.DialOption{insec}); err != nil {
		panic(err)
	}
	hl, _ := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", FreePort()))
	hs := &http.Server{Handler: mux}
	go hs.Serve(hl)
	return gl.Addr().String(), hl.Addr().String(), func() { hs.Close(); gs.Stop() }
}

func do(c *http.Client, method, url string, body string, hdr map[string]string) (int, string, error) {
	var rd io.Reader
	if body != "" {
		rd = strings.NewReader(body)
	}
	req, _ := http.NewRequest(method, url, rd)
	if body != "" {
		req.Header.Set("Content-Type", "application/json")
	}
	for k, v := range hdr {
		req.Header.Set(k, v)
	}
	resp, err := c.Do(req)
	if err != nil {
		return 0, "", err
	}
	defer resp.Body.Close()
	b, _ := io.ReadAll(resp.Body)
	return resp.StatusCode, strings.TrimSpace(string(b)), nil
}

func median(ds []time.Duration) time.Duration {
	sort.Slice(ds, func(i, j int) bool { return ds[i] < ds[j] })
	return ds[len(ds)/2]
}

func main() {
	hc := &http.Client{Timeout: 10 * time.Second}

	Sec("一:REST → gRPC 的映射:POST /v1/echo(JSON 请求体)、GET /v1/items/{id}?name=...(路径参数 + 查询参数)、未知路径")
	{
		_, ha, stop := startGW(&gwServer{})
		base := "http://" + ha
		code, body, _ := do(hc, "POST", base+"/v1/echo", `{"id":"a","name":"alice","count":"123","payload":"aGVsbG8=","tags":["x","y"]}`, nil)
		P("POST /v1/echo → HTTP %d,%s", code, cj(body))
		code, body, _ = do(hc, "GET", base+"/v1/items/abc?name=bob", "", nil)
		P("GET /v1/items/abc?name=bob → HTTP %d,%s", code, cj(body))
		code, body, _ = do(hc, "GET", base+"/v1/items/abc?nope=1", "", nil)
		P("GET /v1/items/abc?nope=1(未知查询参数)→ HTTP %d,%s", code, cj(body))
		code, body, _ = do(hc, "GET", base+"/v1/nothing", "", nil)
		P("GET /v1/nothing → HTTP %d,%s", code, cj(body))
		code, body, _ = do(hc, "DELETE", base+"/v1/echo", "", nil)
		P("DELETE /v1/echo(路径存在但方法不对)→ HTTP %d,%s", code, cj(body))
		code, body, _ = do(hc, "POST", base+"/v1/echo", `{"id": 1`, nil)
		P("POST 非法 JSON → HTTP %d,%s", code, cj(body))
		stop()
	}

	Sec("二:gRPC 状态码 → HTTP 状态码(访问 /v1/fail/{code},服务端返回对应的 gRPC code);code=3 时服务端还带了 ErrorInfo details")
	{
		_, ha, stop := startGW(&gwServer{})
		base := "http://" + ha
		for c := 1; c <= 16; c++ {
			code, body, _ := do(hc, "GET", fmt.Sprintf("%s/v1/fail/%d", base, c), "", nil)
			if c == 3 {
				P("gRPC %-18s → HTTP %d  %s", codes.Code(c), code, cj(body))
			} else {
				P("gRPC %-18s → HTTP %d", codes.Code(c), code)
			}
		}
		stop()
	}

	Sec("三:转换的体积与耗时:同一个 Item,protobuf 字节数 vs JSON 字节数;直接 gRPC 与经过 gateway 的 REST 的单次耗时(中位数)和 16 并发吞吐")
	{
		ga, ha, stop := startGW(&gwServer{})
		base := "http://" + ha
		conn, _ := grpc.NewClient(ga, insec)
		cl := gwpb.NewGwClient(conn)
		for _, sz := range []int{0, 100, 100 * 1024} {
			it := &gwpb.Item{Id: "item-1", Name: "alice", Count: 123456789, Payload: bytes.Repeat([]byte{0xAB}, sz), Tags: []string{"x", "y"}}
			pbB, _ := proto.Marshal(it)
			// 取得 gateway 返回的 JSON 体积
			jb, _ := proto.Marshal(it)
			_ = jb
			js := func() string {
				code, body, _ := do(hc, "POST", base+"/v1/echo", fmt.Sprintf(`{"id":"item-1","name":"alice","count":"123456789","payload":"%s","tags":["x","y"]}`, b64(it.Payload)), nil)
				if code != 200 {
					return fmt.Sprint(code)
				}
				return fmt.Sprint(len(body))
			}()
			// 单次耗时
			var dg, dr []time.Duration
			N := 2000
			if sz >= 100*1024 {
				N = 500
			}
			reqJSON := fmt.Sprintf(`{"id":"item-1","name":"alice","count":"123456789","payload":"%s","tags":["x","y"]}`, b64(it.Payload))
			for i := 0; i < 100; i++ {
				cl.Echo(context.Background(), it)
				do(hc, "POST", base+"/v1/echo", reqJSON, nil)
			}
			for i := 0; i < N; i++ {
				t0 := time.Now()
				cl.Echo(context.Background(), it)
				dg = append(dg, time.Since(t0))
				t0 = time.Now()
				do(hc, "POST", base+"/v1/echo", reqJSON, nil)
				dr = append(dr, time.Since(t0))
			}
			mg, mr := median(dg), median(dr)
			P("payload %6d 字节:protobuf %d 字节,JSON 响应体 %s 字节(%.2f 倍);单次中位数 直接 gRPC %s、经 gateway 的 REST %s(%.1f 倍)", sz, len(pbB), js, atoi(js)/float64(len(pbB)), us(mg), us(mr), float64(mr)/float64(mg))
		}
		// 并发吞吐(小消息)
		it := &gwpb.Item{Id: "item-1", Name: "alice"}
		reqJSON := `{"id":"item-1","name":"alice"}`
		run := func(f func()) float64 {
			var wg sync.WaitGroup
			t0 := time.Now()
			total := 16 * 500
			for w := 0; w < 16; w++ {
				wg.Add(1)
				go func() {
					defer wg.Done()
					for i := 0; i < 500; i++ {
						f()
					}
				}()
			}
			wg.Wait()
			return float64(total) / time.Since(t0).Seconds()
		}
		tr := &http.Transport{MaxIdleConnsPerHost: 64}
		hc2 := &http.Client{Transport: tr}
		rg := run(func() { cl.Echo(context.Background(), it) })
		rr := run(func() { do(hc2, "POST", base+"/v1/echo", reqJSON, nil) })
		P("16 个并发、小消息:直接 gRPC %.0f 请求/秒,经 gateway 的 REST %.0f 请求/秒(%.1f 倍)", rg, rr, rg/rr)
		conn.Close()
		stop()
	}

	Sec("四:HTTP 头 → gRPC metadata:发送 Authorization、X-Custom、Grpc-Metadata-Foo;默认转发哪些;用 WithIncomingHeaderMatcher 才能转发自定义头")
	{
		srv := &gwServer{}
		_, ha, stop := startGW(srv)
		_, body, _ := do(hc, "GET", "http://"+ha+"/v1/meta", "", map[string]string{"Authorization": "Bearer t1", "X-Custom": "c1", "Grpc-Metadata-Foo": "f1"})
		P("默认:服务端 metadata(去掉标准头)= %s", cj(body))
		stop()
		_, ha2, stop2 := startGW(srv, runtime.WithIncomingHeaderMatcher(func(k string) (string, bool) {
			if strings.EqualFold(k, "X-Custom") {
				return strings.ToLower(k), true
			}
			return runtime.DefaultHeaderMatcher(k)
		}))
		_, body, _ = do(hc, "GET", "http://"+ha2+"/v1/meta", "", map[string]string{"Authorization": "Bearer t1", "X-Custom": "c1", "Grpc-Metadata-Foo": "f1"})
		P("WithIncomingHeaderMatcher 放行 X-Custom:%s", cj(body))
		stop2()
	}

	Sec("五:超时与取消:HTTP 客户端 100 ms 就放弃(服务端要 2000 ms)后,后端 handler 的 ctx 是否被取消;请求头 Grpc-Timeout: 300m 时的 HTTP 状态与耗时")
	{
		srv := &gwServer{}
		_, ha, stop := startGW(srv)
		base := "http://" + ha
		short := &http.Client{Timeout: 100 * time.Millisecond}
		t0 := time.Now()
		_, _, err := do(short, "GET", base+"/v1/slow?ms=2000", "", nil)
		el := time.Since(t0)
		time.Sleep(300 * time.Millisecond)
		st, _ := srv.slowDone.Load().(string)
		P("HTTP 客户端超时(%s 后放弃,err 非空=%v);后端 handler 的结果:%q", Ms(el), err != nil, st)
		t0 = time.Now()
		code, body, _ := do(hc, "GET", base+"/v1/slow?ms=2000", "", map[string]string{"Grpc-Timeout": "300m"})
		P("Grpc-Timeout: 300m:HTTP %d,%s 后返回;%s", code, Ms(time.Since(t0)), cj(body))
		stop()
	}

	Sec("六:服务端流 → HTTP:GET /v1/count?n=3 的响应体(分块的 JSON 行)")
	{
		_, ha, stop := startGW(&gwServer{})
		code, body, _ := do(hc, "GET", "http://"+ha+"/v1/count?n=3", "", nil)
		P("HTTP %d,响应体共 %d 行:", code, len(strings.Split(body, "\n")))
		for _, l := range strings.Split(body, "\n") {
			P("    %s", cj(l))
		}
		stop()
	}
}

func b64(b []byte) string {
	const tbl = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
	var sb strings.Builder
	for i := 0; i < len(b); i += 3 {
		var n uint32
		rem := len(b) - i
		n = uint32(b[i]) << 16
		if rem > 1 {
			n |= uint32(b[i+1]) << 8
		}
		if rem > 2 {
			n |= uint32(b[i+2])
		}
		sb.WriteByte(tbl[n>>18&63])
		sb.WriteByte(tbl[n>>12&63])
		if rem > 1 {
			sb.WriteByte(tbl[n>>6&63])
		} else {
			sb.WriteByte('=')
		}
		if rem > 2 {
			sb.WriteByte(tbl[n&63])
		} else {
			sb.WriteByte('=')
		}
	}
	return sb.String()
}

func cj(s string) string {
	var b bytes.Buffer
	if err := json.Compact(&b, []byte(s)); err != nil {
		return s
	}
	return b.String()
}

func us(d time.Duration) string { return fmt.Sprintf("%d µs", d.Microseconds()) }

func atoi(s string) float64 {
	var v float64
	fmt.Sscan(s, &v)
	return v
}
