from lib import *
S = SS('h32')
steps = [
    step("只看 protobuf 编解码(payload 是 bytes 字段,用 testing.Benchmark 测):Marshal 和 Unmarshal 的耗时随 payload 近似线性增长——1 KiB:0.2 µs / 0.2 µs;100 KiB:10.5 µs / 10.3 µs;1 MiB:74.0 µs / 52.6 µs;8 MiB:279.9 µs / 260.9 µs。每次分配的字节数大约就是 payload 本身(1 MiB 时 Marshal 1056770 字节、Unmarshal 1048674 字节,各 1.01 倍和 1.00 倍):编码要把字节拷进新缓冲,解码要把 bytes 字段拷出来。也就是说每经过一次序列化或反序列化,大消息就复制一份。", t=tl(S(1)), done=lidx(S(1), '8 MiB'), mark=lidx(S(1), '1 MiB '), b=bars([['1 MiB Marshal µs', 74.0, '74.0'], ['1 MiB Unmarshal µs', 52.6, '52.6'], ['8 MiB Marshal µs', 279.9, '279.9'], ['8 MiB Unmarshal µs', 260.9, '260.9']], 300, mark=[0, 1], done=[2, 3]), kv=KV([['1 MiB', 'Marshal 74.0 µs,Unmarshal 52.6 µs'], ['分配', '约等于 payload(1.00~1.12 倍)'], ['含义', '每次编码/解码复制一份大消息']], ['含义'])),
    step("整个 RPC 的内存分配(客户端和服务端在同一个进程里,echo:请求和响应都带 payload,顺序调用,TotalAlloc 的增量):1 KiB:每次调用分配 11632 字节(11.36 倍,小消息的固定开销约 11 KiB);16 KiB:47274(2.89 倍);100 KiB:422102(4.12 倍);512 KiB:1847324(3.52 倍);1 MiB:3172576(3.03 倍);2 MiB:6622418(3.16 倍);8 MiB:27044150(3.22 倍),耗时 9.4 ms/次。大消息稳定在 payload 的 3~4 倍:echo 路径上理论上至少有客户端 Marshal、服务端 Unmarshal、服务端 Marshal、客户端 Unmarshal 四次拷贝(我的推断),缓冲池复用了其中一部分。注意:grpc-go 的缓冲池(默认分 256 B、4 KiB、16 KiB、32 KiB、1 MiB 几档)的开关在这个版本里是不导出的,应用不能调。", t=tl(S(2)), done=lidx(S(2), '8 MiB'), mark=lidx(S(2), '1 KiB'), b=bars([['1 KiB 的分配倍数', 11.36, '11.36'], ['100 KiB', 4.12, '4.12'], ['1 MiB', 3.03, '3.03'], ['8 MiB', 3.22, '3.22']], 12, mark=[0], done=[1, 2, 3]), kv=KV([['小消息(1 KiB)', '每次约 11 KiB 固定开销'], ['大消息(1~8 MiB)', '每次约 3~4 倍 payload'], ['缓冲池', '默认 5 档,应用不能配置']], ['大消息(1~8 MiB)'])),
    step("bytes 和 string 字段的反序列化:string 要校验 UTF-8。1 MiB 的 ASCII string:Unmarshal 62.8 µs;1 MiB 的中文 string:568.5 µs(约 9 倍);同样 1 MiB 的 bytes:48.2 µs。三者线上都约 1048580 字节,分配也都约 1048673 字节。string 里放非法 UTF-8(0xff 0xfe)时 Unmarshal 返回错误“string field contains invalid UTF-8”。所以存放不需要当文本校验的二进制数据(图片、压缩包、已序列化的内容)用 bytes,而不是 string。", t=tl(S(3)), done=lidx(S(3), 'string 字段里放非法'), mark=lidx(S(3), 'string(ASCII)'), b=bars([['bytes µs', 48.2, '48.2'], ['string(ASCII) µs', 62.8, '62.8'], ['string(中文) µs', 568.5, '568.5']], 600, mark=[2], done=[0, 1]), kv=KV([['bytes', '48.2 µs'], ['string ASCII', '62.8 µs(要校验 UTF-8)'], ['string 中文', '568.5 µs']], ['string 中文'])),
]
A = mkarth('h32', 32, 'gRPC,protobuf,序列化,内存分配,UTF-8,bytes,大消息,Go,真实验证,动画演示',
    '实测 grpc-go 序列化与内存:Marshal/Unmarshal 分配约等于 payload;整个 echo RPC 大消息稳定分配 payload 的 3~4 倍;小消息每次约 11 KiB 固定开销;1 MiB 中文 string 的反序列化比 bytes 慢约 12 倍;缓冲池的开关在这个版本不导出。',
    '一个 100 MiB 的 RPC 要在内存里复制多少份?小消息每次调用的固定开销是多少?string 和 bytes 的反序列化差多少?这篇用 testing.Benchmark 和 MemStats 把这些数字量出来。',
    [('3~4 倍', '1 MiB 到 8 MiB 的 echo 调用,每次分配的字节数相对 payload 的倍数'), ('约 11 KiB', '1 KiB 小消息每次 RPC 的分配(固定开销)'), ('568.5 µs vs 48.2 µs', '1 MiB 中文 string 与 1 MiB bytes 的 Unmarshal 耗时')],
    [('每次序列化都复制', '<p>Marshal 把字段拷进新缓冲,Unmarshal 把 bytes 字段拷出来。大消息每经过一次编码或解码就多一份拷贝。</p>'),
     ('整条 RPC 的倍数', '<p>echo 一次大消息,客户端和服务端合计分配的内存稳定在 payload 的 3~4 倍;小消息每次还有约 11 KiB 的框架固定开销。</p>'),
     ('string 与 bytes', '<p>string 要校验 UTF-8,中文文本的校验明显更慢;不需要文本语义的数据用 bytes。</p>')],
    steps,
    [ENV_H + '。编解码部分用 testing.Benchmark(只测 protobuf-go);整条 RPC 的分配在同一进程内用 MemStats.TotalAlloc 的增量除以调用次数(客户端和服务端的分配合计,GC 前后各读一次);服务端调大到 64 MiB 的接收/发送上限,否则 8 MiB 的消息会被拒绝;缓冲池的档位读自 mem/buffer_pool.go,选项在包内是不导出的',
     '没有验证:“四次拷贝”是推断(没有逐步追踪每次分配);缓冲池对不同大小消息的实际命中率;对 GC 暂停、尾延迟的影响;零拷贝方案(自定义 codec、mem.Buffer 引用计数);流式分块与单条大消息的内存对比(第 24 篇);压缩开启时的额外分配'],
    '序列化成本')
