from lib import *
S = SS('g102')
steps = [
    step("类型信息只发一次:同一个 Encoder 连续 Encode 4 个 Point{X,Y,Name},每条消息的字节数是 [51 11 11 11]——第一条含类型定义;每次新建 Encoder 则是 [51 51 51 51],类型定义每次都重发。同一个值的 JSON 是 24 字节。全是零值的 Point{} 用新 Encoder 编码仍有 44 字节(只有类型定义,零值字段不编码)。同一个 Encoder 的第 2 条消息十六进制是 0aff800104010401017000(11 字节)。", t=tl(S(1)), done=lidx(S(1), '同一个 Encoder 连续', '第 2 条消息'), mark=lidx(S(1), '每次新建 Encoder', '全是零值'), b=bars([['第 1 条(含类型定义)(字节)', 51, '51'], ['同一个 Encoder 的第 2 条', 11, '11'], ['JSON', 24, '24']], 51, mark=[0], done=[1, 2]), kv=KV([['第 1 条', '51 字节(含类型定义)'], ['之后每条', '11 字节,比 JSON 的 24 字节还小'], ['每次新建 Encoder', '每条都 51 字节']], ['之后每条'])),
    step("字段按名字匹配,顺序无关,多出来的字段被忽略。V1{A:7,B:\"hi\"} 解码进字段顺序不同、多了 C 的 V2:得到 {B:hi C:0 A:7},err=nil;解码进 A 变成 string 的 V3:err=gob: wrong type (string) for received field V1.A;解码进字段名完全不同的结构体:err=gob: type mismatch: no fields matched compiling decoder for Empty。", t=tl(S(2)), done=lidx(S(2), '解码进字段顺序不同'), mark=lidx(S(2), 'wrong type', 'no fields matched'), kv=KV([['字段顺序不同 / 多字段', '按名字匹配,正常解码'], ['字段类型变了', '报错 wrong type'], ['没有任何字段匹配', '报错 no fields matched']], ['字段类型变了'])),
    step("接口字段必须 Register:没有 Register 就编码含接口字段 A Animal 的结构体,err=gob: type not registered for interface: main.Dog;gob.Register(Dog{}) 之后编码和解码都没有错,得到 main.Holder{A:main.Dog{Name:\"旺财\"}}。", t=tl(S(3)), mark=lidx(S(3), 'type not registered'), done=lidx(S(3), 'gob.Register(Dog{}) 之后'), kv=KV([['没 Register', 'type not registered for interface'], ['Register 之后', '编码解码都正常'], ['范围', '本实验在同一进程里,没有分开测两端']], ['没 Register'])),
    step("大小与速度(Big 结构体,有字符串、切片、map):JSON 118 字节;gob 新 Encoder 的单条 190 字节;同一个 Encoder 的第 2 条 62 字节。编码:gob 每次新建 Encoder 2163 ns/次、27 次分配;gob 复用 Encoder 347 ns/次、5 次分配;JSON 675 ns/次、7 次分配。解码:gob 每次新建 Decoder 9360 ns/次、200 次分配;JSON 1043 ns/次、8 次分配;一个 Decoder 连续解 1000 条消息,平均每条 619 ns、14 次分配(含第一条编译解码器的成本)。", t=tl(S(4)), done=lidx(S(4), '复用 Encoder', '一个 Decoder 连续解'), mark=lidx(S(4), '每次新建 Encoder', '每次新建 Decoder'), b=bars([['gob 编码:新 Encoder (ns)', 2163, '2163'], ['gob 编码:复用 Encoder', 347, '347'], ['JSON 编码', 675, '675'], ['gob 解码:新 Decoder', 9360, '9360'], ['gob 解码:流式每条', 619, '619'], ['JSON 解码', 1043, '1043']], 9360, mark=[0, 3], done=[1, 4]), kv=KV([['复用 Encoder / Decoder', '编码 347 ns、解码 619 ns/条,比 JSON 快'], ['每次新建', '编码 2163 ns、解码 9360 ns,比 JSON 慢 3–9 倍'], ['原因', '每次都要为类型编译/传输编解码器']], ['原因'])),
    step("文档(go doc encoding/gob):实现为流里每个数据类型编译一个定制的编解码器,当单个 Encoder 用来传输一串值时效率最高,摊薄了编译的成本。", t=tl(S(5)), done=lidx(S(5), 'compiles a custom codec', 'amortizing the cost'), kv=KV([['实现', '为每个类型编译定制的编解码器'], ['最佳用法', '一个 Encoder 传输一串值']], ['最佳用法'])),
]
A = mkartg('g102', 102, 'Go,encoding/gob,序列化,类型信息,Encoder,真实验证,动画演示',
    '在 Go 1.27.1 里实测 encoding/gob:同一个 Encoder 连续编码,第一条消息 51 字节(含类型定义),之后每条只有 11 字节,每次新建 Encoder 则每条都是 51 字节;字段按名字匹配、多出的字段被忽略、类型变了才报错;接口字段必须 Register;复用 Encoder/Decoder 时编码 347 ns、解码 619 ns/条,比 JSON 快,每次新建则慢 3–9 倍。',
    'gob 是 Go 自己的二进制编码,第一次传输一个类型时会把类型描述一起发过去,后面的消息只带数据。这篇用字节数和耗时验证这个设计:什么时候又小又快,什么时候(每次新建 Encoder/Decoder)反而比 JSON 慢得多;并看它怎么处理字段增减、接口字段。',
    [('51 → 11 字节', '同一个 Encoder 连续编码同一个类型,第一条与之后每条的大小'), ('347 vs 2163 ns', 'gob 编码一个结构体:复用 Encoder 与每次新建 Encoder'), ('619 vs 9360 ns', 'gob 解码:一个 Decoder 连续解 1000 条的平均与每次新建 Decoder')],
    [('类型信息只发一次', '<p>第一条消息 51 字节,其中大部分是类型定义;之后每条只有 11 字节(JSON 是 24 字节)。每次新建 <code>Encoder</code> 就每条都是 51 字节。所以 gob 适合“一个连接上持续传一串同类型的值”,不适合每条消息单独编码(比如存进数据库的一个字段)。</p>'),
     ('兼容性', '<p>接收方按字段名匹配,字段顺序不同、接收方多出来的字段(保持零值)都没问题;字段类型变了(int → string)或者一个字段名都对不上才报错。不过接口字段必须 <code>gob.Register</code> 具体类型(文档说两端都要注册;本实验在同一个进程里,没有把两端分开测)。</p>'),
     ('接口字段', '<p>没注册就编码,报 <code>type not registered for interface: main.Dog</code>;<code>gob.Register(Dog{})</code> 之后能正常往返。</p>'),
     ('速度', '<p>复用 <code>Encoder</code> 编码一个结构体 347 ns,比 JSON 的 675 ns 快,只有 5 次分配;每次新建 <code>Encoder</code> 要 2163 ns、27 次分配,比 JSON 慢。解码的差距更大:每次新建 <code>Decoder</code> 9360 ns、200 次分配,是 JSON(1043 ns)的 9 倍;一个 <code>Decoder</code> 连续解 1000 条平均 619 ns。</p>'),
     ('为什么', '<p>文档说得很直接:它为流里每个类型编译一个定制编解码器,单个 <code>Encoder</code> 传一串值时摊薄了编译成本。</p>')],
    steps,
    [ENV_G + '。大小来自 bytes.Buffer 的长度;速度用 testing.Benchmark;Big 结构体含字符串、切片、map;“一个 Decoder 连续解 1000 条”的平均已包含第一条编译解码器的成本;读过的文档:go doc encoding/gob 开头的一句话',
     '没有验证:gob 的线格式细节(只展示了一条消息的十六进制)、与 protobuf 等格式的对比、很大的切片/嵌套结构下的表现、跨 Go 版本的兼容性、net/rpc 里的实际用法'],
    'encoding/gob')
