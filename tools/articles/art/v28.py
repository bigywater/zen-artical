from lib import *
S = SS('v28')
steps = [
    step("Content-Length 超限。client_max_body_size 1m(默认),POST 的 Content-Length 分别是 0.5 / 2 / 20 / 200 MB。0.5 MB:200,上游收到 0.50 MB。2 MB、20 MB、200 MB:都是 413,上游一次也没收到(没到上游),但 client 还是把 2.0 / 20.0 / 200.0 MB 请求体全部发了出去,200 MB 用了 0.08 s。nginx 看到 Content-Length 超限就在读请求体之前回 413,然后“延迟关闭”(lingering close):把 client 还在发的请求体读掉丢弃,所以 client 能收到 413,但流量已经白白发出去了。", t=tl(S(1)), mark=lidx(S(1), '2 MB ', '20 MB', '200 MB'), done=lidx(S(1), '0.5 MB'), b=bars([['0.5 MB:上游收到 MB', 0.5, '0.50'], ['2 MB:client 发出 MB', 2, '2.0(上游 0)'], ['20 MB:client 发出 MB', 20, '20.0(上游 0)'], ['200 MB:client 发出 MB', 200, '200.0(上游 0)']], 200, done=[0], mark=[1, 2, 3]), kv=KV([['超限请求', '413,不到上游'], ['client 的流量', '请求体仍被全部发完(nginx 丢弃)'], ['200 MB', 'client 发完用了 0.08 s']], ['client 的流量'])),
    step("chunked 上传没有 Content-Length。client 用 Transfer-Encoding: chunked 上传 5 MB,client_max_body_size 1m。proxy_request_buffering on(默认,nginx 先收完请求体再转给上游):client 看到 413,发出 5.0 MB,上游没收到。proxy_request_buffering off(边收边转):client 同样看到 413、发出 5.0 MB,但上游已经收到了 1.05 MB 的请求体,然后连接被掐断,上游看到的是残缺的请求。chunked 不事先声明长度,nginx 只能边读边数,超过限制才知道超限。", t=tl(S(2)), mark=lidx(S(2), 'proxy_request_buffering off'), done=lidx(S(2), 'proxy_request_buffering on'), b=bars([['buffering on:上游收到 MB', 0.0, '0(没到上游)'], ['buffering off:上游收到 MB', 1.05, '1.05(残缺)'], ['两种:client 看到', 413, '413']], 413, done=[0], mark=[1], cur=[2]), kv=KV([['request_buffering on', '上游完全不知情'], ['request_buffering off', '上游收到 1.05 MB 残缺请求体']], ['request_buffering off'])),
    step("按 location 放宽,以及 Expect: 100-continue。server 级 1m,/upload 放宽到 50m。0.5 MB:/api 200、/upload 200。5 MB:/api 413、/upload 200。60 MB:/api 413、/upload 413(超过 50m 也被拒)。5 MB 超限的请求:不带 Expect 的 client 把 5.0 MB 请求体全发完才看到 413;带 Expect: 100-continue 的 client 先发头、等 nginx 的回应,拿到 413 后 0.0 MB 请求体都没发。", t=tl(S(3)), mark=lidx(S(3), '带 Expect'), done=lidx(S(3), '5 MB   ', '60 MB', '不带 Expect'), b=bars([['5 MB → /api', 413, '413'], ['5 MB → /upload', 200, '200'], ['不带 Expect:client 发出 MB', 5.0, '5.0'], ['带 Expect:client 发出 MB', 0.0, '0.0']], 413, mark=[0], done=[1, 3], cur=[2]), kv=KV([['/api(1m)', '5 MB 413'], ['/upload(50m)', '5 MB 200,60 MB 413'], ['Expect: 100-continue', '超限时不发请求体']], ['Expect: 100-continue'])),
]
A = mkartv('v28', 28, '微服务,网关,nginx,client_max_body_size,413,真实验证,动画演示',
    '实测 nginx 请求体大小限制:Content-Length 超限的 200 MB 请求也返回 413、不到上游,但 client 仍把 200 MB 发完;chunked 加 proxy_request_buffering off 时上游会收到 1.05 MB 残缺请求体;按 location 放宽到 50m;带 Expect: 100-continue 的 client 超限时不发请求体。',
    '请求体超限时 nginx 在什么时候回 413?client 还会不会把整个请求体发完?chunked 上传和流式转发会怎样?怎么按路径放宽?这篇用原始 socket 把几种情形量出来。',
    [('200.0 MB', 'Content-Length 为 200 MB、限制 1m 时,client 实际发出的请求体大小;上游一次都没收到,client 看到 413'), ('1.05 MB', 'chunked 上传 5 MB、proxy_request_buffering off 时,超限被拒之前上游已经收到的请求体(残缺)'), ('0.0 MB', '带 Expect: 100-continue 的 client 在 5 MB 超限时实际发出的请求体(不带的发了 5.0 MB)')],
    [('Content-Length 超限', '<p>读请求体之前就回 413,但 client 仍会把请求体发完,nginx 延迟关闭并丢弃。</p>'),
     ('chunked 与缓冲', '<p>chunked 只能边读边数;关掉请求缓冲时,上游会收到一部分残缺的请求体。</p>'),
     ('按路径放宽与 Expect', '<p>location 级的 client_max_body_size 可以覆盖;Expect: 100-continue 让 client 在超限时省下请求体。</p>')],
    steps,
    [ENV_V + '。nginx 是 Homebrew 的 1.31.6;上游是我写的原始 TCP 服务(数请求体字节,支持 Content-Length 和 chunked);client 是原始 socket(发头、发请求体、读响应);“client 发出的字节数”是 client 自己的 sendall 累计,不等于 nginx 收到的字节数;每个场景只测一次',
     '没有验证:lingering_close / lingering_time 的参数对 client 能否收到 413 的影响;HTTP/2 上的请求体限制;client_body_buffer_size 与临时文件;上游自己的请求体限制(例如 Tomcat、Spring)与网关限制不一致的情形;自定义 413 的 error_page'],
    '请求体大小限制与 413')
