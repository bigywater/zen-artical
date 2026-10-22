from lib import *
S = SS('v24')
steps = [
    step("流式响应(SSE 之类)。上游每 0.2 s 发一个数据块,共 10 个,约 2 s 发完。100 字节的块:proxy_buffering on(默认)第一批响应体 0.00 s 就到,收到一半字节 1.04 s,收完 2.07 s,recv 11 次;buffering off 和上游发 X-Accel-Buffering: no 几乎一样(0.00 s、1.03 s、2.06 s)。16 KB 的块:on 是 0.00 / 1.04 / 2.07 s;off 的 recv 次数是 14,on 是 11,到达的时刻一样。也就是说缓冲打开时,nginx 并没有把小块攒到最后才发,流式照样一块一块到。但打开 gzip(对 text/event-stream 压缩)就不一样了:100 字节的块第一批响应体 2.09 s 才到,收一半和收完也都是 2.09 s,recv 只有 1 次;16 KB 的块是 2.06 s,也是 1 次——gzip 把整个流攒到了最后。", t=tl(S(1)), mark=lidx(S(1), 'gzip on'), done=lidx(S(1), 'buffering on', 'buffering off', 'X-Accel-Buffering'), b=bars([['buffering on:第一批到达 s', 0.0, '0.00'], ['buffering off:第一批到达 s', 0.0, '0.00'], ['gzip on 100 B:第一批到达 s', 2.09, '2.09'], ['gzip on 16 KB:第一批到达 s', 2.06, '2.06']], 2.1, done=[0, 1], mark=[2, 3]), kv=KV([['buffering on(默认)', '第一块 0.00 s,逐块到达'], ['buffering off / X-Accel-Buffering: no', '同样 0.00 s'], ['gzip on', '攒到 2.09 s 才一次性到达']], ['gzip on'])),
    step("慢 client。上游要发 40 MB(64 KB 一块往 socket 里写),client 约 5 MB/s 地读,收完要 10 s 左右。proxy_buffering on(默认):上游 0.0 s 就写完 40 MB(上游连接马上释放),client 收完用了 11.3 s,nginx 的 worker 打开的临时文件最大 38.9 MB——nginx 把响应整个收进了 proxy_temp_path 下的临时文件(打开后立刻 unlink 目录项,目录里看不到)。on + proxy_max_temp_file_size 0(不写临时文件):上游写完用了 9.2 s,临时文件 0.0 MB。buffering off:上游写完用了 10.1 s,临时文件 0.0 MB。关掉缓冲或不让写临时文件,上游连接被占住的时间就接近 client 收完的时间。", t=tl(S(2)), mark=lidx(S(2), 'buffering off', 'proxy_max_temp_file_size 0'), done=lidx(S(2), 'buffering on(默认)'), b=bars([['on:上游写完 s', 0.0, '0.0'], ['temp 0:上游写完 s', 9.2, '9.2'], ['off:上游写完 s', 10.1, '10.1'], ['on:临时文件 MB', 38.9, '38.9 MB']], 40, done=[0], mark=[1, 2], cur=[3]), kv=KV([['buffering on', '上游 0.0 s 写完,临时文件 38.9 MB'], ['max_temp_file_size 0', '上游 9.2 s'], ['buffering off', '上游 10.1 s']], ['buffering on'])),
]
A = mkartv('v24', 24, '微服务,网关,nginx,proxy_buffering,SSE,gzip,真实验证,动画演示',
    '实测 proxy_buffering:开着缓冲时 SSE 流式响应照样每块立刻到达,真正把流攒到最后的是 gzip(第一批 2.09 s 才到);40 MB 响应遇到慢 client,缓冲打开时上游 0.0 s 写完(nginx 在 38.9 MB 的临时文件里替它缓冲),关掉则上游被占 9.2 到 10.1 s。',
    'proxy_buffering 开着,流式响应会不会被攒住?慢 client 到底占用谁的资源?gzip 对 SSE 又有什么影响?这篇用一个能控制节奏的上游和 nginx 1.31.6 量出来,和常见的说法对一对。',
    [('0.00 s', 'proxy_buffering 开着(默认)时,SSE 式流的第一块到达 client 的时刻;打开 gzip 后是 2.09 s'), ('0.0 s 对 9.2 到 10.1 s', '40 MB 响应遇到慢 client,上游把它写完用的时间:缓冲打开 对 proxy_max_temp_file_size 0 / buffering off'), ('38.9 MB', '缓冲打开时 nginx worker 为这个慢 client 打开的临时文件的大小(目录项已被 unlink,用 lsof 量到)')],
    [('流式响应', '<p>缓冲打开时 nginx 也会随到随转发,小块不会被攒到最后;gzip 才会。</p>'),
     ('慢 client', '<p>缓冲打开时 nginx 用临时文件吸收整个响应,上游很快释放;关掉缓冲上游被占到 client 收完。</p>')],
    steps,
    [ENV_V + '。nginx 是 Homebrew 的 1.31.6;上游是我写的原始 TCP 服务(chunked 流式响应、一次性写 40 MB);client 是原始 socket,慢 client 每 10 ms 读 50 KB;临时文件大小用 lsof 看 worker 进程打开的 proxy_temp_path 下的文件(我最初扫目录得到 0,是因为 nginx 打开后立刻 unlink 了目录项);“收到一半字节”按接收的字节累计;每种配置只测一次',
     '没有验证:旧版本 nginx 在缓冲打开时对 SSE 的行为(一些资料说会攒住,这里没有观察到);proxy_buffers 数量与大小对内存的影响;gzip 配合上游主动 flush 的情形;HTTP/2 client 的流控对缓冲的影响;X-Accel-Buffering 头在这个实验里没有表现出可见的差别,因为缓冲打开时本来就没有被攒住'],
    '缓冲 proxy_buffering')
