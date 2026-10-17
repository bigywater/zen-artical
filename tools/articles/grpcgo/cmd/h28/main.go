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
	"google.golang.org/protobuf/encoding/protojson"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/reflect/protodesc"
	"google.golang.org/protobuf/reflect/protoreflect"
	"google.golang.org/protobuf/reflect/protoregistry"
	"google.golang.org/protobuf/types/descriptorpb"
	"google.golang.org/protobuf/types/dynamicpb"
	_ "google.golang.org/protobuf/types/known/wrapperspb"
	. "grpcgo/common"
	"grpcgo/pb"
)

var insec = grpc.WithTransportCredentials(insecure.NewCredentials())
var seq atomic.Int64

type fd struct {
	name     string
	num      int32
	typ      descriptorpb.FieldDescriptorProto_Type
	optional bool
	tname    string
}

const (
	TI32  = descriptorpb.FieldDescriptorProto_TYPE_INT32
	TI64  = descriptorpb.FieldDescriptorProto_TYPE_INT64
	TSTR  = descriptorpb.FieldDescriptorProto_TYPE_STRING
	TBOOL = descriptorpb.FieldDescriptorProto_TYPE_BOOL
	TMSG  = descriptorpb.FieldDescriptorProto_TYPE_MESSAGE
	TDBL  = descriptorpb.FieldDescriptorProto_TYPE_DOUBLE
)

func mk(fields ...fd) protoreflect.MessageDescriptor {
	pkg := fmt.Sprintf("dflt%d", seq.Add(1))
	m := &descriptorpb.DescriptorProto{Name: proto.String("M")}
	for _, f := range fields {
		fp := &descriptorpb.FieldDescriptorProto{Name: proto.String(f.name), Number: proto.Int32(f.num), Type: f.typ.Enum(), Label: descriptorpb.FieldDescriptorProto_LABEL_OPTIONAL.Enum(), JsonName: proto.String(f.name)}
		if f.typ == TMSG {
			fp.TypeName = proto.String(f.tname)
		}
		if f.optional {
			fp.Proto3Optional = proto.Bool(true)
			fp.OneofIndex = proto.Int32(int32(len(m.OneofDecl)))
			m.OneofDecl = append(m.OneofDecl, &descriptorpb.OneofDescriptorProto{Name: proto.String("_" + f.name)})
		}
		m.Field = append(m.Field, fp)
	}
	file := &descriptorpb.FileDescriptorProto{Name: proto.String(pkg + ".proto"), Package: proto.String(pkg), Syntax: proto.String("proto3"), MessageType: []*descriptorpb.DescriptorProto{m},
		Dependency: []string{"google/protobuf/wrappers.proto"}}
	f, err := protodesc.NewFile(file, protoregistry.GlobalFiles)
	if err != nil {
		panic(err)
	}
	return f.Messages().ByName("M")
}

func show(m proto.Message) string {
	r := m.ProtoReflect()
	var fs []protoreflect.FieldDescriptor
	r.Range(func(f protoreflect.FieldDescriptor, v protoreflect.Value) bool { fs = append(fs, f); return true })
	sort.Slice(fs, func(i, j int) bool { return fs[i].Number() < fs[j].Number() })
	var o []string
	for _, f := range fs {
		o = append(o, fmt.Sprintf("%s=%v", f.Name(), r.Get(f).Interface()))
	}
	return "{" + strings.Join(o, ", ") + "}"
}

func dataLens(tap *Tap) []int {
	var o []int
	for _, e := range tap.Snapshot() {
		if e.Dir == "C→S" && e.Type == "DATA" {
			o = append(o, int(e.Len))
		}
	}
	return o
}

func main() {
	Sec("一:proto3 的默认值不上线:Req{} 、Req{N: 0, Msg: \"\"}、Req{N: 1} 在 gRPC 线上的 DATA 帧长度(5 字节前缀 + 消息),以及服务端看到的 N")
	{
		var seenN int32
		addr, stop := Start(&DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) { seenN = r.N; return &pb.Resp{}, nil }})
		tap := NewTap(addr)
		conn, _ := grpc.NewClient(tap.Addr, insec)
		cl := pb.NewDemoClient(conn)
		cl.Unary(context.Background(), &pb.Req{})
		for _, c := range []struct {
			name string
			req  *pb.Req
		}{{"Req{}", &pb.Req{}}, {"Req{N: 0, Msg: \"\"}(显式写了默认值)", &pb.Req{N: 0, Msg: ""}}, {"Req{N: 1}", &pb.Req{N: 1}}} {
			tap.Reset()
			cl.Unary(context.Background(), c.req)
			time.Sleep(50 * time.Millisecond)
			b, _ := proto.Marshal(c.req)
			P("%-34s proto.Marshal 得到 %d 字节;线上请求 DATA 帧载荷 %v 字节;服务端看到 N=%d", c.name, len(b), dataLens(tap), seenN)
		}
		conn.Close()
		tap.Close()
		stop()
	}

	Sec("二:optional(proto3_optional)记录“有没有设置”:n 显式设为 0 的序列化字节与未设置的区别,接收方的 Has")
	{
		plain := mk(fd{"n", 1, TI32, false, ""})
		opt := mk(fd{"n", 1, TI32, true, ""})
		for _, c := range []struct {
			name string
			d    protoreflect.MessageDescriptor
			set  bool
		}{{"普通 int32,未设置", plain, false}, {"普通 int32,设为 0", plain, true}, {"optional int32,未设置", opt, false}, {"optional int32,设为 0", opt, true}} {
			m := dynamicpb.NewMessage(c.d)
			f := c.d.Fields().ByName("n")
			if c.set {
				m.Set(f, protoreflect.ValueOfInt32(0))
			}
			b, _ := proto.Marshal(m)
			r := dynamicpb.NewMessage(c.d)
			proto.Unmarshal(b, r)
			P("%-22s 序列化 %d 字节 %x;接收方 Has(n)=%v,值=%d", c.name, len(b), b, r.Has(f), r.Get(f).Int())
		}
	}

	Sec("三:用包装类型(google.protobuf.Int32Value)表示“可能没有”:未设置、设为 0、设为 7 的序列化字节与接收方的判断")
	{
		d := mk(fd{"n", 1, TMSG, false, ".google.protobuf.Int32Value"})
		f := d.Fields().ByName("n")
		wd := f.Message()
		for _, c := range []struct {
			name string
			set  *int32
		}{{"未设置", nil}, {"Int32Value{0}", ptr(0)}, {"Int32Value{7}", ptr(7)}} {
			m := dynamicpb.NewMessage(d)
			if c.set != nil {
				w := dynamicpb.NewMessage(wd)
				w.Set(wd.Fields().ByName("value"), protoreflect.ValueOfInt32(*c.set))
				m.Set(f, protoreflect.ValueOfMessage(w))
			}
			b, _ := proto.Marshal(m)
			r := dynamicpb.NewMessage(d)
			proto.Unmarshal(b, r)
			val := int64(-1)
			if r.Has(f) {
				val = r.Get(f).Message().Get(wd.Fields().ByName("value")).Int()
			}
			P("%-16s 序列化 %d 字节 %x;接收方 Has(n)=%v,值=%d(-1 表示没有)", c.name, len(b), b, r.Has(f), val)
		}
	}

	Sec("四:“部分更新”的陷阱:库里已有 {msg: hello, n: 7},客户端想把 n 清零——用 proto.Merge 合并补丁({n: 0}),普通字段与 optional 字段分别的结果")
	{
		for _, optional := range []bool{false, true} {
			d := mk(fd{"msg", 1, TSTR, false, ""}, fd{"n", 2, TI32, optional, ""})
			stored := dynamicpb.NewMessage(d)
			stored.Set(d.Fields().ByName("msg"), protoreflect.ValueOfString("hello"))
			stored.Set(d.Fields().ByName("n"), protoreflect.ValueOfInt32(7))
			patch := dynamicpb.NewMessage(d)
			patch.Set(d.Fields().ByName("n"), protoreflect.ValueOfInt32(0))
			bp, _ := proto.Marshal(patch)
			wire := dynamicpb.NewMessage(d) // 补丁经过网络
			proto.Unmarshal(bp, wire)
			proto.Merge(stored, wire)
			name := "普通 int32 n"
			if optional {
				name = "optional int32 n"
			}
			P("%-18s 补丁 {n: 0} 序列化为 %d 字节;Merge 之后库里是 %s", name, len(bp), show(stored))
		}
	}

	Sec("五:子消息的存在性:没设置的子消息与设置了空的子消息;Go 里读未设置的子消息的字段会不会 panic")
	{
		d := mk(fd{"inner", 1, TMSG, false, ".google.protobuf.Int32Value"})
		f := d.Fields().ByName("inner")
		m1 := dynamicpb.NewMessage(d)
		m2 := dynamicpb.NewMessage(d)
		m2.Set(f, protoreflect.ValueOfMessage(dynamicpb.NewMessage(f.Message())))
		b1, _ := proto.Marshal(m1)
		b2, _ := proto.Marshal(m2)
		P("inner 未设置:序列化 %d 字节 %x;Has=%v;读 inner.value(不 panic)=%v", len(b1), b1, m1.Has(f), m1.Get(f).Message().Get(f.Message().Fields().ByName("value")).Int())
		r2 := dynamicpb.NewMessage(d)
		proto.Unmarshal(b2, r2)
		P("inner 设置为空消息:序列化 %d 字节 %x;接收方 Has=%v", len(b2), b2, r2.Has(f))
		var nilReq *pb.Req
		P("生成代码里对 nil 的 *pb.Req 调 GetN()/GetMsg():%d / %q(不 panic)", nilReq.GetN(), nilReq.GetMsg())
	}

	Sec("六:JSON(protojson)的默认值与 int64:默认不输出零值;EmitUnpopulated 才输出;int64 输出成字符串;读入时数字和字符串都接受;double 的 \"NaN\" 可以用字符串读入")
	{
		d := mk(fd{"msg", 1, TSTR, false, ""}, fd{"n", 2, TI32, false, ""}, fd{"big", 3, TI64, false, ""}, fd{"x", 4, TDBL, false, ""})
		m := dynamicpb.NewMessage(d)
		m.Set(d.Fields().ByName("msg"), protoreflect.ValueOfString("hi"))
		m.Set(d.Fields().ByName("big"), protoreflect.ValueOfInt64(9007199254740993))
		m.Set(d.Fields().ByName("x"), protoreflect.ValueOfFloat64(1.5))
		compact := func(b []byte) string { return strings.Join(strings.Fields(string(b)), "") }
		j1, _ := protojson.Marshal(m)
		j2, _ := protojson.MarshalOptions{EmitUnpopulated: true}.Marshal(m)
		P("默认:%s", compact(j1))
		P("EmitUnpopulated:%s", compact(j2))
		r := dynamicpb.NewMessage(d)
		err := protojson.Unmarshal([]byte(`{"big":9007199254740993}`), r)
		P("JSON 里把 int64 写成数字 9007199254740993:err=%v;读到 %s", err, show(r))
		r = dynamicpb.NewMessage(d)
		err = protojson.Unmarshal([]byte(`{"x":"NaN"}`), r)
		P(`JSON 里把 double 写成 "NaN":err=%v;读到 %s`, err, show(r))
	}
}

func ptr(v int32) *int32 { return &v }
