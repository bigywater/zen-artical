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
	"google.golang.org/protobuf/types/descriptorpb"
	"google.golang.org/protobuf/types/dynamicpb"
	. "grpcgo/common"
	"grpcgo/pb"
)

var insec = grpc.WithTransportCredentials(insecure.NewCredentials())
var fileSeq atomic.Int64

type fd struct {
	name  string
	num   int32
	typ   descriptorpb.FieldDescriptorProto_Type
	rep   bool
	tname string // 枚举类型名
}

const (
	TI32  = descriptorpb.FieldDescriptorProto_TYPE_INT32
	TI64  = descriptorpb.FieldDescriptorProto_TYPE_INT64
	TS32  = descriptorpb.FieldDescriptorProto_TYPE_SINT32
	TBOOL = descriptorpb.FieldDescriptorProto_TYPE_BOOL
	TSTR  = descriptorpb.FieldDescriptorProto_TYPE_STRING
	TBYT  = descriptorpb.FieldDescriptorProto_TYPE_BYTES
	TF32  = descriptorpb.FieldDescriptorProto_TYPE_FIXED32
	TENUM = descriptorpb.FieldDescriptorProto_TYPE_ENUM
)

// mk 在一个独立的 .proto 文件(proto3)里建一个叫 M 的消息;enum 里是枚举 E 的值。
func mk(fields []fd, enum ...string) protoreflect.MessageDescriptor {
	n := fileSeq.Add(1)
	pkg := fmt.Sprintf("compat%d", n)
	m := &descriptorpb.DescriptorProto{Name: proto.String("M")}
	for _, f := range fields {
		lab := descriptorpb.FieldDescriptorProto_LABEL_OPTIONAL
		if f.rep {
			lab = descriptorpb.FieldDescriptorProto_LABEL_REPEATED
		}
		fp := &descriptorpb.FieldDescriptorProto{Name: proto.String(f.name), Number: proto.Int32(f.num), Type: f.typ.Enum(), Label: lab.Enum(), JsonName: proto.String(f.name)}
		if f.typ == TENUM {
			fp.TypeName = proto.String("." + pkg + ".E")
		}
		m.Field = append(m.Field, fp)
	}
	file := &descriptorpb.FileDescriptorProto{Name: proto.String(pkg + ".proto"), Package: proto.String(pkg), Syntax: proto.String("proto3"), MessageType: []*descriptorpb.DescriptorProto{m}}
	if len(enum) > 0 {
		e := &descriptorpb.EnumDescriptorProto{Name: proto.String("E")}
		for i, v := range enum {
			e.Value = append(e.Value, &descriptorpb.EnumValueDescriptorProto{Name: proto.String(v), Number: proto.Int32(int32(i))})
		}
		file.EnumType = append(file.EnumType, e)
	}
	f, err := protodesc.NewFile(file, nil)
	if err != nil {
		panic(err)
	}
	return f.Messages().ByName("M")
}

// show 把消息里的已知字段(按编号)和未知字段的字节数列出来。
func show(m proto.Message) string {
	r := m.ProtoReflect()
	var fs []protoreflect.FieldDescriptor
	r.Range(func(f protoreflect.FieldDescriptor, v protoreflect.Value) bool { fs = append(fs, f); return true })
	sort.Slice(fs, func(i, j int) bool { return fs[i].Number() < fs[j].Number() })
	var o []string
	for _, f := range fs {
		v := r.Get(f)
		var s string
		switch {
		case f.IsList():
			var xs []string
			for i := 0; i < v.List().Len(); i++ {
				xs = append(xs, fmt.Sprint(v.List().Get(i).Interface()))
			}
			s = "[" + strings.Join(xs, " ") + "]"
		case f.Kind() == protoreflect.EnumKind:
			s = fmt.Sprintf("%d", v.Enum())
			if ev := f.Enum().Values().ByNumber(v.Enum()); ev != nil {
				s = string(ev.Name())
			} else {
				s = fmt.Sprintf("(未知枚举值 %d)", v.Enum())
			}
		default:
			s = fmt.Sprintf("%v", v.Interface())
		}
		o = append(o, fmt.Sprintf("%s=%s", f.Name(), s))
	}
	out := "{" + strings.Join(o, ", ") + "}"
	if u := r.GetUnknown(); len(u) > 0 {
		out += fmt.Sprintf(" + 未知字段 %d 字节 %x", len(u), []byte(u))
	}
	return out
}

func set(md protoreflect.MessageDescriptor, kv ...any) *dynamicpb.Message {
	m := dynamicpb.NewMessage(md)
	for i := 0; i < len(kv); i += 2 {
		f := md.Fields().ByName(protoreflect.Name(kv[i].(string)))
		switch v := kv[i+1].(type) {
		case int:
			switch f.Kind() {
			case protoreflect.Int32Kind, protoreflect.Sint32Kind:
				m.Set(f, protoreflect.ValueOfInt32(int32(v)))
			case protoreflect.Int64Kind:
				m.Set(f, protoreflect.ValueOfInt64(int64(v)))
			case protoreflect.EnumKind:
				m.Set(f, protoreflect.ValueOfEnum(protoreflect.EnumNumber(v)))
			case protoreflect.Fixed32Kind:
				m.Set(f, protoreflect.ValueOfUint32(uint32(v)))
			}
		case string:
			if f.Kind() == protoreflect.BytesKind {
				m.Set(f, protoreflect.ValueOfBytes([]byte(v)))
			} else {
				m.Set(f, protoreflect.ValueOfString(v))
			}
		case bool:
			m.Set(f, protoreflect.ValueOfBool(v))
		case []int:
			l := m.Mutable(f).List()
			for _, x := range v {
				l.Append(protoreflect.ValueOfInt32(int32(x)))
			}
		}
	}
	return m
}

// cross 用写入方的描述符序列化,再用读取方的描述符解析。
func cross(w proto.Message, rd protoreflect.MessageDescriptor) (*dynamicpb.Message, []byte) {
	b, _ := proto.Marshal(w)
	r := dynamicpb.NewMessage(rd)
	err := proto.Unmarshal(b, r)
	if err != nil {
		fmt.Println("  解析出错:", err)
	}
	return r, b
}

func main() {
	Sec("一:加字段(新→旧):新版本多了 extra = 4;旧版本读到后不认识这个字段,但会保留着,再转发(或写回)时原样带出去——经过旧服务端的 gRPC 往返")
	{
		oldD := mk([]fd{{"msg", 1, TSTR, false, ""}, {"n", 2, TI32, false, ""}})
		newD := mk([]fd{{"msg", 1, TSTR, false, ""}, {"n", 2, TI32, false, ""}, {"extra", 4, TSTR, false, ""}})
		w := set(newD, "msg", "hello", "n", 7, "extra", "新字段")
		r, b := cross(w, oldD)
		P("新版本写出 %x(%d 字节);旧版本读到:%s", b, len(b), show(r))
		b2, _ := proto.Marshal(r)
		back := dynamicpb.NewMessage(newD)
		proto.Unmarshal(b2, back)
		P("旧版本原样写回(%d 字节),新版本再读:%s", len(b2), show(back))
		// 真实 gRPC:服务端用生成的旧版 pb.Req,把收到的请求原样序列化放进响应
		addr, stop := Start(&DemoServer{OnUnary: func(ctx context.Context, rq *pb.Req) (*pb.Resp, error) {
			bb, _ := proto.Marshal(rq)
			return &pb.Resp{Payload: bb}, nil
		}})
		conn, _ := grpc.NewClient(addr, insec)
		reqD := mk([]fd{{"msg", 1, TSTR, false, ""}, {"n", 2, TI32, false, ""}, {"payload", 3, TBYT, false, ""}, {"extra", 4, TSTR, false, ""}})
		req := set(reqD, "msg", "hi", "n", 1, "extra", "新字段")
		var resp pb.Resp
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		err := conn.Invoke(ctx, "/demo.Demo/Unary", req, &resp)
		cancel()
		back2 := dynamicpb.NewMessage(reqD)
		proto.Unmarshal(resp.Payload, back2)
		P("真实 gRPC:新版客户端(带 extra)→ 用旧版生成代码的服务端 → 服务端把收到的请求原样放进响应:err=%v;新版客户端解出 %s", err, show(back2))
		conn.Close()
		stop()
	}

	Sec("二:改字段名(name → full_name,编号不变):二进制完全兼容;JSON(protojson 按名字)不兼容")
	{
		oldD := mk([]fd{{"name", 1, TSTR, false, ""}})
		newD := mk([]fd{{"full_name", 1, TSTR, false, ""}})
		r, b := cross(set(oldD, "name", "alice"), newD)
		P("二进制:旧写 %x,新读:%s", b, show(r))
		js, _ := protojson.MarshalOptions{UseProtoNames: true}.Marshal(set(oldD, "name", "alice"))
		nm := dynamicpb.NewMessage(newD)
		err := protojson.Unmarshal(js, nm)
		P("JSON:旧写 %s,新版 protojson 解析的结果:%s;err=%v", strings.ReplaceAll(string(js), "  ", " "), show(nm), err)
	}

	Sec("三:改字段编号(n 从 2 改成 5):旧数据里的值读不出来(变成未知字段)")
	{
		oldD := mk([]fd{{"msg", 1, TSTR, false, ""}, {"n", 2, TI32, false, ""}})
		newD := mk([]fd{{"msg", 1, TSTR, false, ""}, {"n", 5, TI32, false, ""}})
		r, b := cross(set(oldD, "msg", "x", "n", 42), newD)
		P("旧写 n=42 的 %x,新读:%s", b, show(r))
	}

	Sec("四:改字段类型:写入方写 int32 的值,读取方把同一个编号当成别的类型读")
	{
		w := mk([]fd{{"v", 1, TI32, false, ""}})
		for _, c := range []struct {
			name string
			t    descriptorpb.FieldDescriptorProto_Type
			val  int
		}{{"int32 → int64", TI64, 5}, {"int32 → int64(值为 -1)", TI64, -1}, {"int32 → sint32", TS32, 5}, {"int32 → sint32(值为 -1)", TS32, -1}, {"int32 → bool", TBOOL, 5}, {"int32 → string", TSTR, 5}, {"int32 → fixed32", TF32, 5}} {
			rd := mk([]fd{{"v", 1, c.t, false, ""}})
			r, b := cross(set(w, "v", c.val), rd)
			P("%-22s 线上 %x,读到:%s", c.name, b, show(r))
		}
		w2 := mk([]fd{{"v", 1, TSTR, false, ""}})
		r, b := cross(set(w2, "v", "abc"), mk([]fd{{"v", 1, TBYT, false, ""}}))
		P("%-22s 线上 %x,读到:%s", "string → bytes", b, show(r))
	}

	Sec("五:删掉字段后把编号复用成别的类型:旧客户端仍然在发 n = 42(int32,编号 2);新版本把编号 2 改成了 string label")
	{
		oldD := mk([]fd{{"msg", 1, TSTR, false, ""}, {"n", 2, TI32, false, ""}})
		newD := mk([]fd{{"msg", 1, TSTR, false, ""}, {"label", 2, TSTR, false, ""}})
		r, b := cross(set(oldD, "msg", "x", "n", 42), newD)
		P("旧写 %x,新读(编号 2 当 string):%s", b, show(r))
		newD2 := mk([]fd{{"msg", 1, TSTR, false, ""}, {"label", 2, TI32, false, ""}})
		r2, _ := cross(set(oldD, "msg", "x", "n", 42), newD2)
		P("如果复用成另一个 int32 字段(含义完全不同):%s ← 读到的是旧字段的值,但含义已不同,不会有任何报错", show(r2))
	}

	Sec("六:枚举加新值:新版本发出枚举值 3,旧版本的枚举只定义了 0、1、2")
	{
		oldD := mk([]fd{{"s", 1, TENUM, false, ""}}, "UNKNOWN", "OK", "FAIL")
		newD := mk([]fd{{"s", 1, TENUM, false, ""}}, "UNKNOWN", "OK", "FAIL", "RETRY")
		r, b := cross(set(newD, "s", 3), oldD)
		P("新写 %x(枚举值 3),旧读:%s", b, show(r))
		bb, _ := proto.Marshal(r)
		back := dynamicpb.NewMessage(newD)
		proto.Unmarshal(bb, back)
		P("旧版本原样写回,新版本再读:%s", show(back))
	}

	Sec("七:标量 ↔ repeated:int32 nums = 2 改成 repeated int32(或反过来)")
	{
		sc := mk([]fd{{"nums", 2, TI32, false, ""}})
		rp := mk([]fd{{"nums", 2, TI32, true, ""}})
		r, b := cross(set(sc, "nums", 5), rp)
		P("标量 5 → repeated:线上 %x,读到:%s", b, show(r))
		r, b = cross(set(rp, "nums", []int{1, 2, 3}), sc)
		P("repeated [1 2 3] → 标量:线上 %x,读到:%s", b, show(r))
	}
}
