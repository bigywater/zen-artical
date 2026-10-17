from lib import *
S = SS('h28')
steps = [
    step("proto3 的默认值(0、空字符串、false)不上线。Req{} 序列化 0 字节,线上请求的 DATA 帧载荷只有 5 字节(gRPC 的消息前缀,没有消息体);显式写 Req{N: 0, Msg: \"\"} 也是 0 字节、5 字节;Req{N: 1} 序列化 2 字节,DATA 帧 7 字节。服务端看到的 N,前两种都是 0——接收方分不清“没设置”和“设成了 0”。", t=tl(S(1)), done=lidx(S(1), 'Req{N: 1}'), mark=lidx(S(1), 'Req{}    '), b=bars([['Req{}:DATA 帧载荷', 5, '5'], ['Req{N: 0, Msg: ""}', 5, '5'], ['Req{N: 1}', 7, '7']], 8, mark=[0, 1], done=[2]), kv=KV([['Req{}', '序列化 0 字节,DATA 5 字节'], ['显式写默认值', '同样 0 字节,服务端看到 N=0'], ['Req{N: 1}', '2 字节,DATA 7 字节']], ['显式写默认值'])),
    step("optional(proto3_optional)记录“有没有设置”。普通 int32:未设置和设为 0 都序列化成 0 字节,接收方 Has(n) 都是 false;optional int32:未设置还是 0 字节、Has 为 false,设为 0 则序列化成 2 字节 0800,接收方 Has(n)=true、值为 0。多出来的 2 字节记录了“我明确设了 0”。需要区分“没填”和“填了 0”的字段(比如可选的过滤条件、要清零的计数)应该用 optional。", t=tl(S(2)), done=lidx(S(2), 'optional int32,设为 0'), mark=lidx(S(2), 'optional int32,未设置'), b=bars([['普通 int32 设为 0:序列化字节', 0, '0'], ['optional int32 设为 0:序列化字节', 2, '2']], 3, mark=[0], done=[1]), kv=KV([['普通 int32', '未设置 = 设为 0,0 字节'], ['optional int32 设为 0', '2 字节 0800,Has=true'], ['用途', '区分“没填”和“填了 0”']], ['用途'])),
    step("用包装类型 google.protobuf.Int32Value 表示“可能没有”:未设置:0 字节、Has=false;Int32Value{0}:2 字节 0a00、Has=true、值 0;Int32Value{7}:4 字节 0a020807、Has=true、值 7。包装类型靠“子消息存在与否”表达有无,代价是多 2 个字节的前缀,并且在代码里是一层嵌套;proto3 加入 optional 之前这是常见的做法,现在新代码一般直接用 optional。", t=tl(S(3)), done=lidx(S(3), 'Int32Value{7}'), mark=lidx(S(3), 'Int32Value{0}'), b=bars([['未设置:字节', 0, '0'], ['Int32Value{0}', 2, '2'], ['Int32Value{7}', 4, '4']], 5, mark=[1], done=[2]), kv=KV([['未设置', '0 字节,Has=false'], ['Int32Value{0}', '2 字节 0a00,Has=true'], ['Int32Value{7}', '4 字节,值 7']], ['Int32Value{0}'])),
    step("“部分更新”的陷阱:库里已有 {msg: hello, n: 7},客户端想把 n 清零,发补丁 {n: 0},服务端用 proto.Merge 合并。普通字段 n:补丁序列化成 0 字节(0 没上线),Merge 之后库里还是 {msg=hello, n=7}——清不掉;optional 字段 n:补丁 2 字节,Merge 之后 {msg=hello, n=0},清掉了。如果不用 optional,更新接口应该用 FieldMask 明确列出要改的字段,否则无法表达“把它设为 0/空”。", t=tl(S(4)), done=lidx(S(4), 'optional int32 n'), mark=lidx(S(4), '普通 int32 n'), b=bars([['普通 n:Merge 之后 n 的值(想清零)', 7, '7(没清掉)'], ['optional n:Merge 之后 n 的值', 0, '0']], 8, mark=[0], done=[1]), kv=KV([['普通 int32 补丁 {n: 0}', '0 字节,Merge 不起作用'], ['optional', '补丁 2 字节,清零成功'], ['另一种办法', 'FieldMask 列出要改的字段']], ['普通 int32 补丁 {n: 0}'])),
    step("子消息的存在性:inner 未设置:0 字节、Has=false,但在 Go 里读 inner 的字段不会 panic,得到默认值 0;inner 设置成空消息:2 字节 0a00,接收方 Has=true。生成代码里对 nil 的 *pb.Req 调 GetN()、GetMsg() 也不 panic,返回 0 和空字符串——getter 对 nil 是安全的。所以读字段用 GetXxx(),需要区分有无时才用 Has/判断是否为 nil。", t=tl(S(5)), done=lidx(S(5), '生成代码里'), mark=lidx(S(5), 'inner 未设置'), b=bars([['inner 未设置:序列化字节', 0, '0'], ['inner 设置为空消息:序列化字节', 2, '2']], 3, mark=[0], done=[1]), kv=KV([['未设置的子消息', 'Has=false,读字段得默认值'], ['设置为空消息', '2 字节,Has=true'], ['nil 指针的 getter', '返回默认值,不 panic']], ['nil 指针的 getter'])),
    step("JSON 里的默认值:protojson 默认不输出零值——{\"msg\":\"hi\",\"big\":\"9007199254740993\",\"x\":1.5}(n=0 没出现);EmitUnpopulated 才输出 \"n\":0。int64 输出成字符串(9007199254740993 超过 JavaScript 的安全整数范围,所以用字符串);读入时把 int64 写成数字 9007199254740993 也能接受,读到同样的值。double 的 \"NaN\" 用字符串可以读入。写 JSON 接口的客户端要知道:int64 是字符串,缺省字段表示默认值。", t=tl(S(6)), done=lidx(S(6), 'double'), mark=lidx(S(6), '默认:'), b=bars([['默认输出的字段数', 3, '3'], ['EmitUnpopulated 输出的字段数', 4, '4']], 5, mark=[0], done=[1]), kv=KV([['默认', '不输出零值字段'], ['int64', '输出成字符串'], ['读入', '数字和字符串都接受']], ['int64'])),
]
A = mkarth('h28', 28, 'gRPC,protobuf,proto3,默认值,optional,Has,FieldMask,protojson,Go,真实验证,动画演示',
    '实测 proto3 默认值与存在性:默认值不上线、服务端分不清没设置和设为 0;optional 多 2 字节记录有无;包装类型的做法;部分更新用 Merge 清不了零值;子消息和 nil getter;protojson 默认不输出零值、int64 是字符串。',
    'proto3 里 0、空字符串和没设置是一回事?想把一个字段清零、想区分“没填”和“填了 0”该怎么设计接口?这篇用字节级的实验把这些坑一个个摆出来。',
    [('0 字节', 'Req{} 与显式写了默认值的 Req{N: 0} 序列化后都是 0 字节,线上 DATA 只有 5 字节前缀'), ('n=7 清不掉', '普通 int32 的补丁 {n: 0} 经 proto.Merge 合并后,库里的 n 仍是 7'), ('"big":"9007199254740993"', 'protojson 把 int64 输出成字符串')],
    [('默认值不上线', '<p>proto3 的标量字段等于默认值时不序列化。接收方读到 0 时无法区分没设置和设成 0。</p>'),
     ('optional', '<p>给字段加 optional 会记录是否设置:设为 0 也会上线,接收方可以用 Has 判断。需要区分有无的字段用它。</p>'),
     ('包装类型', '<p>Int32Value 等包装类型靠子消息的存在表达有无,多 2 个字节,代码里多一层。是 optional 出现之前的做法。</p>'),
     ('部分更新', '<p>用 Merge 合并补丁时,默认值不会覆盖已有值,清零做不到。用 optional 或 FieldMask 明确表达要改哪些字段。</p>'),
     ('子消息与 nil', '<p>子消息有存在性:未设置和设为空消息不同。生成代码的 getter 对 nil 安全,返回默认值。</p>'),
     ('JSON', '<p>protojson 默认不输出零值;int64 输出成字符串,避免 JavaScript 丢精度。</p>')],
    steps,
    [ENV_H + '。线上 DATA 帧长度来自抓包代理;其余用 protobuf-go 在进程内构造的描述符(含 proto3_optional 的合成 oneof)与 dynamicpb 序列化、解析、Merge,字节为 proto.Marshal 真实输出;“补丁”是进程内模拟,没有经过 gRPC 的 Update 接口',
     '没有验证:FieldMask(fieldmaskpb)的实际用法与嵌套路径;oneof 的存在性语义;proto2 的 required/default 值;其它语言(Java、Python 的 has 方法)的行为;repeated/map 字段“空”与“未设置”的区别;自定义默认值(只有 proto2 有)'],
    '默认值')
