package main

import (
	"context"
	"fmt"
	"sort"
	"strings"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/health"
	hpb "google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/reflection"
	rpb "google.golang.org/grpc/reflection/grpc_reflection_v1"
	rpba "google.golang.org/grpc/reflection/grpc_reflection_v1alpha"
	"google.golang.org/protobuf/encoding/protojson"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/reflect/protodesc"
	"google.golang.org/protobuf/reflect/protoreflect"
	"google.golang.org/protobuf/types/descriptorpb"
	"google.golang.org/protobuf/types/dynamicpb"
	. "grpcgo/common"
)

var insec = grpc.WithTransportCredentials(insecure.NewCredentials())

func listServices(ctx context.Context, conn *grpc.ClientConn) ([]string, error) {
	st, err := rpb.NewServerReflectionClient(conn).ServerReflectionInfo(ctx)
	if err != nil {
		return nil, err
	}
	st.Send(&rpb.ServerReflectionRequest{MessageRequest: &rpb.ServerReflectionRequest_ListServices{}})
	r, err := st.Recv()
	if err != nil {
		return nil, err
	}
	var o []string
	for _, s := range r.GetListServicesResponse().Service {
		o = append(o, s.Name)
	}
	sort.Strings(o)
	st.CloseSend()
	return o, nil
}

func fileOf(st rpb.ServerReflection_ServerReflectionInfoClient, sym string) ([]*descriptorpb.FileDescriptorProto, *rpb.ErrorResponse, error) {
	if err := st.Send(&rpb.ServerReflectionRequest{MessageRequest: &rpb.ServerReflectionRequest_FileContainingSymbol{FileContainingSymbol: sym}}); err != nil {
		return nil, nil, err
	}
	r, err := st.Recv()
	if err != nil {
		return nil, nil, err
	}
	if e := r.GetErrorResponse(); e != nil {
		return nil, e, nil
	}
	var fs []*descriptorpb.FileDescriptorProto
	for _, b := range r.GetFileDescriptorResponse().FileDescriptorProto {
		fd := &descriptorpb.FileDescriptorProto{}
		if err := proto.Unmarshal(b, fd); err != nil {
			return nil, nil, err
		}
		fs = append(fs, fd)
	}
	return fs, nil, nil
}

func main() {
	Sec("一:Register 之后能列出哪些服务;v1 和 v1alpha 都能用吗;用 ServerOptions.Services 可以只公开一部分")
	{
		hs := health.NewServer()
		var gs *grpc.Server
		addr, stop := StartReg(&DemoServer{}, func(s *grpc.Server) {
			gs = s
			hpb.RegisterHealthServer(s, hs)
			reflection.Register(s)
		})
		_ = gs
		conn, _ := grpc.NewClient(addr, insec)
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		names, err := listServices(ctx, conn)
		P("v1 ListServices:err=%v;%s", err, strings.Join(names, " "))
		sta, err := rpba.NewServerReflectionClient(conn).ServerReflectionInfo(ctx)
		sta.Send(&rpba.ServerReflectionRequest{MessageRequest: &rpba.ServerReflectionRequest_ListServices{}})
		ra, err2 := sta.Recv()
		var na []string
		for _, s := range ra.GetListServicesResponse().GetService() {
			na = append(na, s.Name)
		}
		sort.Strings(na)
		P("v1alpha ListServices:err=%v/%v;%s", err, err2, strings.Join(na, " "))
		cancel()
		conn.Close()
		stop()

		// 只公开 demo.Demo
		addr2, stop2 := StartReg(&DemoServer{}, func(s *grpc.Server) {
			hpb.RegisterHealthServer(s, hs)
			svr := reflection.NewServerV1(reflection.ServerOptions{Services: onlyDemo{s}})
			rpb.RegisterServerReflectionServer(s, svr)
		})
		conn2, _ := grpc.NewClient(addr2, insec)
		ctx2, cancel2 := context.WithTimeout(context.Background(), 3*time.Second)
		names, err = listServices(ctx2, conn2)
		P("自定义 Services 只含 demo.Demo:err=%v;%s", err, strings.Join(names, " "))
		cancel2()
		conn2.Close()
		stop2()
	}

	Sec("二:FileContainingSymbol(\"demo.Demo\"):客户端拿到的文件描述符(服务端把 .proto 的描述编进了二进制)——文件名、依赖、服务的方法、消息的字段")
	{
		addr, stop := StartReg(&DemoServer{}, func(s *grpc.Server) { reflection.Register(s) })
		conn, _ := grpc.NewClient(addr, insec)
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		st, _ := rpb.NewServerReflectionClient(conn).ServerReflectionInfo(ctx)
		fs, _, err := fileOf(st, "demo.Demo")
		P("err=%v;返回的文件描述符 %d 个", err, len(fs))
		for _, fd := range fs {
			P("文件 %s(package %s,依赖 %v)", fd.GetName(), fd.GetPackage(), fd.GetDependency())
			for _, sv := range fd.Service {
				for _, m := range sv.Method {
					P("    %s.%s(%s%s) returns (%s%s)", sv.GetName(), m.GetName(), map[bool]string{true: "stream ", false: ""}[m.GetClientStreaming()], m.GetInputType(), map[bool]string{true: "stream ", false: ""}[m.GetServerStreaming()], m.GetOutputType())
				}
			}
			for _, ms := range fd.MessageType {
				var fl []string
				for _, f := range ms.Field {
					fl = append(fl, fmt.Sprintf("%s=%d(%s)", f.GetName(), f.GetNumber(), strings.TrimPrefix(f.GetType().String(), "TYPE_")))
				}
				P("    message %s { %s }", ms.GetName(), strings.Join(fl, ", "))
			}
		}
		cancel()
		conn.Close()
		stop()
	}

	Sec("三:只靠反射得到的描述符,不用生成的代码,动态调用 /demo.Demo/Unary(请求 {\"msg\":\"hello\",\"n\":7})")
	{
		addr, stop := StartReg(&DemoServer{}, func(s *grpc.Server) { reflection.Register(s) })
		tap := NewTap(addr)
		conn, _ := grpc.NewClient(tap.Addr, insec)
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		st, _ := rpb.NewServerReflectionClient(conn).ServerReflectionInfo(ctx)
		fs, _, _ := fileOf(st, "demo.Demo")
		files := &descriptorpb.FileDescriptorSet{File: fs}
		reg, err := protodesc.NewFiles(files)
		if err != nil {
			panic(err)
		}
		d, err := reg.FindDescriptorByName("demo.Demo")
		sd := d.(protoreflect.ServiceDescriptor)
		md := sd.Methods().ByName("Unary")
		in := dynamicpb.NewMessage(md.Input())
		if err := protojson.Unmarshal([]byte(`{"msg":"hello","n":7}`), in); err != nil {
			panic(err)
		}
		out := dynamicpb.NewMessage(md.Output())
		err = conn.Invoke(ctx, "/"+string(sd.FullName())+"/"+string(md.Name()), in, out)
		js, _ := protojson.Marshal(out)
		P("err=%v;响应(protojson)%s", err, js)
		P("请求的 Go 类型 %T,响应的 Go 类型 %T(都是由反射返回的描述符构造的 dynamicpb.Message,不是生成的 pb.Req / pb.Resp)", in, out)
		cancel()
		conn.Close()
		tap.Close()
		stop()
	}

	Sec("四:找不到的符号:FileContainingSymbol(\"nope.Foo\") 返回什么;同一个反射流里连续问 3 次与开 3 个流的 HEADERS 个数")
	{
		addr, stop := StartReg(&DemoServer{}, func(s *grpc.Server) { reflection.Register(s) })
		tap := NewTap(addr)
		conn, _ := grpc.NewClient(tap.Addr, insec)
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		st, _ := rpb.NewServerReflectionClient(conn).ServerReflectionInfo(ctx)
		_, e, err := fileOf(st, "nope.Foo")
		P("err=%v;ErrorResponse code=%d message=%q", err, e.GetErrorCode(), e.GetErrorMessage())
		// 一个流里连问 3 次
		tap.Reset()
		st3, _ := rpb.NewServerReflectionClient(conn).ServerReflectionInfo(ctx)
		for i := 0; i < 3; i++ {
			fileOf(st3, "demo.Demo")
		}
		st3.CloseSend()
		time.Sleep(100 * time.Millisecond)
		h1 := 0
		for _, ev := range tap.Snapshot() {
			if ev.Dir == "C→S" && ev.Type == "HEADERS" {
				h1++
			}
		}
		tap.Reset()
		for i := 0; i < 3; i++ {
			s2, _ := rpb.NewServerReflectionClient(conn).ServerReflectionInfo(ctx)
			fileOf(s2, "demo.Demo")
			s2.CloseSend()
		}
		time.Sleep(100 * time.Millisecond)
		h3 := 0
		for _, ev := range tap.Snapshot() {
			if ev.Dir == "C→S" && ev.Type == "HEADERS" {
				h3++
			}
		}
		P("同一个流里问 3 次:客户端发出 HEADERS %d 个;开 3 个流各问 1 次:HEADERS %d 个", h1, h3)
		cancel()
		conn.Close()
		tap.Close()
		stop()
	}
}

type onlyDemo struct{ s *grpc.Server }

func (o onlyDemo) GetServiceInfo() map[string]grpc.ServiceInfo {
	all := o.s.GetServiceInfo()
	return map[string]grpc.ServiceInfo{"demo.Demo": all["demo.Demo"]}
}
