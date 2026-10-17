from lib import *
S = SS('g87')
steps = [
    step("几种拼接方式(每段 16 字节)。100 段:s += piece 10717 ns、99 次分配;strings.Builder 777 ns、9 次;Builder + Grow 348 ns、1 次;bytes.Buffer 985 ns、7 次;strings.Join 1074 ns、2 次;Sprintf 15218 ns、199 次。1000 段:s += 1088907 ns(8.5 MB);Builder 9330 ns;Builder + Grow 3050 ns;Sprintf 1023500 ns。1 万段:s += 60250200 ns(835 MB);Builder 72262 ns;Builder + Grow 28452 ns(1 次分配);Sprintf 122835412 ns(1.5 GB)。5 万段:s += 1446626958 ns(1.45 秒,20.2 GB 分配);Builder 493997 ns;Builder + Grow 170837 ns;Join 540718 ns;bytes.Buffer 359572 ns。", t=tl(S(1)), done=lidx(S(1), 'Builder + Grow'), mark=lidx(S(1), 's += piece', 'Sprintf'), b=bars([['5 万段 s += (ms)', 1447, '1447'], ['5 万段 bytes.Buffer', 0.36, '0.36'], ['5 万段 Builder', 0.49, '0.49'], ['5 万段 Builder+Grow', 0.17, '0.17']], 1447, mark=[0], done=[1, 2, 3]), kv=KV([['s += 的规律', '段数×10 → 耗时约×50–70(平方级)'], ['Builder', '段数×10 → 耗时约×8(接近线性)'], ['Grow 预估大小', '再快 2–3 倍,1 次分配'], ['5 万段 s +=', '1.45 秒、20 GB 分配']], ['5 万段 s +='])),
    step("String() 要不要复制:strings.Builder.String() 每次 0 次分配;bytes.Buffer.String() 每次 1 次分配(复制了一份)。", t=tl(S(2)), mark=lidx(S(2), 'strings.Builder.String()'), kv=KV([['Builder.String()', '0 次分配,零拷贝'], ['Buffer.String()', '1 次分配,复制']], ['Builder.String()'])),
    step("Builder 的容量怎么长:连续写 2000 个 16 字节段(共 32000 字节),容量依次为 16 → 32 → 64 → 128 → 256 → 512 → 896 → 1408 → 2048 → 3072 → 4096 → 5376 → 6912 → 9472 → 12288 → 16384 → 21760 → 28672 → 40960。小的时候翻倍,大了之后增长因子变小(约 1.3–1.5 倍)。", t=tl(S(3)), mark=lidx(S(3), '容量变化依次为'), kv=KV([['起步', '16 → 32 → 64 …(翻倍)'], ['超过约 512 字节', '增长趋缓(512 → 896 → 1408 → …)'], ['最终', '40960 字节容量装 32000 字节']], ['超过约 512 字节'])),
    step("不能复制:复制一个已写入的 Builder 后再往副本里写,panic: strings: illegal use of non-zero Builder copied by value。", t=tl(S(4)), mark=lidx(S(4), 'panic'), kv=KV([['复制已写入的 Builder', '再写就 panic'], ['原因', 'Builder 内部用地址自检']], ['原因'])),
    step("文档:Builder 用 Write 方法高效地构造字符串,它尽量减少内存复制;零值可用;不要复制非零值的 Builder。", t=tl(S(5)), mark=lidx(S(5), 'A Builder is used to efficiently build'), kv=KV([['用途', '高效构造字符串,尽量减少复制'], ['零值', '可直接用'], ['禁止', '复制非零值']], ['禁止'])),
]
A = mkartg('g87', 87, 'Go,strings.Builder,bytes.Buffer,字符串拼接,Grow,真实验证,动画演示',
    '在 Go 1.27.1 里量字符串拼接:5 万段 16 字节,s += 要 1.45 秒、分配 20.2 GB,而 strings.Builder 只要 0.49 ms,预先 Grow 后 0.17 ms 且只 1 次分配;Sprintf 拼接更慢;Builder.String() 零拷贝(0 次分配)而 bytes.Buffer.String() 要复制;Builder 的容量增长曲线;复制已写入的 Builder 会 panic。',
    '循环里 s += x 会很慢是常识,但慢多少、Builder 和 Buffer、Join 又有多大差别?这篇把几种拼接方式在 100 到 5 万段上各量一遍,并看 String() 是否复制、容量怎么增长、为什么不能复制 Builder。',
    [('1447 ms vs 0.17 ms', '拼接 5 万段 16 字节:s += 与 Builder + Grow'), ('20.2 GB', '5 万段 s += 一次拼接累计分配的内存'), ('0 vs 1', 'Builder.String() 与 bytes.Buffer.String() 每次的分配次数')],
    [('s += 是平方级', '<p>段数每增加 10 倍,<code>s +=</code> 的耗时增加约 50–70 倍(10717 ns → 1.09 ms → 60 ms → 1.45 s),分配的内存更夸张:5 万段累计分配 20.2 GB,因为每次都把整个字符串复制一遍。<code>Sprintf("%s%s")</code> 更慢。</p>'),
     ('Builder 接近线性', '<p><code>strings.Builder</code> 在 100、1000、1 万、5 万段下分别是 777 ns、9.3 µs、72 µs、494 µs,每段数量级×10,耗时约×8;如果知道大小就 <code>Grow</code>,只有 1 次分配,再快 2–3 倍。<code>bytes.Buffer</code> 与 Builder 同一量级,<code>strings.Join</code> 在这个测试里略慢(它还要先构造 parts 切片)。</p>'),
     ('String() 与容量', '<p><code>Builder.String()</code> 不复制(0 次分配),<code>bytes.Buffer.String()</code> 每次复制一份。Builder 的容量起步按 2 倍增长,超过约 512 字节后增长因子变小,32000 字节最终是 40960 的容量。</p>'),
     ('不能复制', '<p>Builder 记着自己的地址,复制一个已经写过的再继续写会 panic。把它放在结构体里时,传指针。</p>'),
     ('文档', '<p>文档只用几句话概括:用 <code>Write</code> 方法高效构造字符串,最小化复制,零值可用,不要复制非零值的 Builder。</p>')],
    steps,
    [ENV_G + '。基准用 testing.Benchmark(ReportAllocs);每种拼接 100、1000、1 万、5 万段(s += 与 Sprintf 在最大规模处省略,Sprintf 最大测到 1 万段);容量变化通过 Builder.Cap() 记录;读过的文档:go doc strings.Builder',
     '没有验证:Linux 上的结果、更大的段(几 KB)下的差别、strings.Builder 与 bytes.Buffer 的内部扩容公式(没有读源码)、字符串常量折叠对小规模 += 的影响、fmt.Fprintf 写入 Builder 的成本'],
    '字符串拼接')
