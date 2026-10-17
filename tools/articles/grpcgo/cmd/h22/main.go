package main

import (
	"context"
	"fmt"
	"strings"
	"time"

	"google.golang.org/genproto/googleapis/rpc/errdetails"
	spb "google.golang.org/genproto/googleapis/rpc/status"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/anypb"
	"google.golang.org/protobuf/types/known/durationpb"
	. "grpcgo/common"
	"grpcgo/pb"
)

var insec = grpc.WithTransportCredentials(insecure.NewCredentials())

func trailerOf(tap *Tap) (hdrs []string) {
	n := 0
	for _, e := range tap.Snapshot() {
		if e.Dir == "S→C" && e.Type == "HEADERS" {
			n++
			if n == 2 || strings.Contains(e.Info, "grpc-status") {
				for _, kv := range strings.Split(e.Info, "; ") {
					if strings.HasPrefix(kv, "grpc-") {
						if len(kv) > 90 {
							kv = fmt.Sprintf("%s…(共 %d 字符)", kv[:60], len(kv))
						}
						hdrs = append(hdrs, kv)
					}
				}
				return
			}
		}
	}
	return
}

func run(h func(context.Context, *pb.Req) (*pb.Resp, error)) (*Tap, pb.DemoClient, func()) {
	addr, stop := Start(&DemoServer{OnUnary: h})
	tap := NewTap(addr)
	conn, _ := grpc.NewClient(tap.Addr, insec)
	return tap, pb.NewDemoClient(conn), func() { conn.Close(); tap.Close(); stop() }
}

func do(cl pb.DemoClient, msg string) error {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_, err := cl.Unary(ctx, &pb.Req{Msg: msg})
	return err
}

func main() {
	Sec("一:status.New(...).WithDetails(...):线上的 trailers 里有什么;客户端怎么取出 details")
	{
		tap, cl, done := run(func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
			st := status.New(codes.InvalidArgument, "参数不合法")
			st, _ = st.WithDetails(&errdetails.ErrorInfo{Reason: "BAD_NAME", Domain: "demo.example", Metadata: map[string]string{"field": "name"}})
			return nil, st.Err()
		})
		err := do(cl, "x")
		time.Sleep(50 * time.Millisecond)
		st, _ := status.FromError(err)
		P("线上 trailers 里的 grpc- 开头的头:%v", trailerOf(tap))
		P("客户端:code=%s message=%q;details 个数 %d", st.Code(), st.Message(), len(st.Details()))
		for _, d := range st.Details() {
			if ei, ok := d.(*errdetails.ErrorInfo); ok {
				P("    ErrorInfo: reason=%s domain=%s metadata=%v", ei.Reason, ei.Domain, ei.Metadata)
			}
		}
		done()
	}

	Sec("二:一个错误里带多种 details:ErrorInfo、BadRequest(字段错误)、RetryInfo(建议等多久再试);客户端按类型取")
	{
		tap, cl, done := run(func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
			st := status.New(codes.ResourceExhausted, "配额用完")
			st, _ = st.WithDetails(
				&errdetails.ErrorInfo{Reason: "QUOTA", Domain: "demo.example"},
				&errdetails.BadRequest{FieldViolations: []*errdetails.BadRequest_FieldViolation{{Field: "n", Description: "n 必须小于 10"}, {Field: "msg", Description: "不能为空"}}},
				&errdetails.RetryInfo{RetryDelay: durationpb.New(1500 * time.Millisecond)},
			)
			return nil, st.Err()
		})
		err := do(cl, "x")
		time.Sleep(50 * time.Millisecond)
		st, _ := status.FromError(err)
		P("details 个数 %d", len(st.Details()))
		for _, d := range st.Details() {
			switch v := d.(type) {
			case *errdetails.ErrorInfo:
				P("    ErrorInfo reason=%s", v.Reason)
			case *errdetails.BadRequest:
				for _, f := range v.FieldViolations {
					P("    BadRequest 字段 %s:%s", f.Field, f.Description)
				}
			case *errdetails.RetryInfo:
				P("    RetryInfo 建议等待 %v", v.RetryDelay.AsDuration())
			default:
				P("    未知类型 %T", d)
			}
		}
		P("线上 trailers:%v", trailerOf(tap))
		done()
	}

	Sec("三:details 越大线上越大:details 里 ErrorInfo 的 metadata 值分别是 1 KiB、64 KiB、1 MiB、20 MiB 时,客户端收到什么")
	for _, kb := range []int{1, 64, 1024, 20 * 1024} {
		tap, cl, done := run(func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
			st := status.New(codes.Internal, "大 details")
			st, _ = st.WithDetails(&errdetails.ErrorInfo{Reason: "BIG", Metadata: map[string]string{"blob": strings.Repeat("x", kb*1024)}})
			return nil, st.Err()
		})
		err := do(cl, "x")
		time.Sleep(50 * time.Millisecond)
		st, _ := status.FromError(err)
		msg := st.Message()
		if len(msg) > 100 {
			msg = msg[:100] + "…"
		}
		P("%5d KiB:code=%s details=%d message=%q;线上 trailers %v", kb, st.Code(), len(st.Details()), msg, trailerOf(tap))
		done()
	}

	Sec("四:不能带 details 的情形:code 为 OK 的 status 调用 WithDetails;详情里放了客户端不认识的类型")
	{
		_, err := status.New(codes.OK, "").WithDetails(&errdetails.ErrorInfo{Reason: "X"})
		P("status.New(codes.OK).WithDetails 返回的错误:%v", err)
		any1 := &anypb.Any{TypeUrl: "type.googleapis.com/nope.Thing", Value: []byte{1, 2, 3}}
		ps := &spb.Status{Code: int32(codes.NotFound), Message: "找不到", Details: []*anypb.Any{any1}}
		tap, cl, done := run(func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
			return nil, status.FromProto(ps).Err()
		})
		err = do(cl, "x")
		time.Sleep(50 * time.Millisecond)
		st, _ := status.FromError(err)
		P("客户端:code=%s message=%q;Details() 个数 %d", st.Code(), st.Message(), len(st.Details()))
		for _, d := range st.Details() {
			if e, ok := d.(error); ok {
				P("    不认识的类型得到的是 error:%v", e)
			} else {
				P("    %T", d)
			}
		}
		P("    线上 trailers:%v", trailerOf(tap))
		done()
	}

	Sec("五:服务 A 调用服务 B,B 的错误怎么传:A 直接 return err、用 status.Convert(err).Err() 重新包装、fmt.Errorf(\"%w\") 包一层,客户端各看到什么")
	{
		tapB, clB, doneB := run(func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
			st, _ := status.New(codes.FailedPrecondition, "B 的错误").WithDetails(&errdetails.ErrorInfo{Reason: "FROM_B"})
			return nil, st.Err()
		})
		_ = tapB
		for _, mode := range []string{"直接 return err", "status.Convert(err).Err()", "fmt.Errorf(\"A: %w\", err)"} {
			mode := mode
			tap, cl, done := run(func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
				_, err := clB.Unary(ctx, &pb.Req{})
				switch mode {
				case "status.Convert(err).Err()":
					return nil, status.Convert(err).Err()
				case "fmt.Errorf(\"A: %w\", err)":
					return nil, fmt.Errorf("A: %w", err)
				}
				return nil, err
			})
			err := do(cl, "x")
			time.Sleep(50 * time.Millisecond)
			st, _ := status.FromError(err)
			var rs []string
			for _, d := range st.Details() {
				if ei, ok := d.(*errdetails.ErrorInfo); ok {
					rs = append(rs, ei.Reason)
				}
			}
			P("%-30s → 客户端 code=%s message=%q details 里的 reason %v", mode, st.Code(), st.Message(), rs)
			_ = tap
			done()
		}
		doneB()
	}
}
