from lib import *
S = SS('v22')
steps = [
    step("哪些问题会被换到下一个上游重试。A 总是出某种问题,B 正常,proxy_read_timeout 1 s,各发一个 GET。默认(error timeout):连接被拒、读响应超时、连接被 RST 都被重试到 B;HTTP 500/502/503/504/404 都不重试,原样转给 client;状态行正常但有一行响应头没有冒号:client 拿到 nginx 的 502;状态行就不是 HTTP 的整行垃圾:client 的 HTTP 库抛 BadStatusLine(nginx 按 HTTP/0.9 简单响应把那行当响应体转发);响应头发完后只给 2 个字节响应体就断开:client IncompleteRead。加 http_500 只让 500 被重试;加 http_502 http_503 http_504 让这三个被重试;加 invalid_header 让没有冒号的响应头被重试到 B;加 http_404 让 404 被重试。off:连接被拒 502、超时 504、RST 502,全都不重试。", t=tl(S(1)), mark=lidx(S(1), 'HTTP 503', 'HTTP 500'), done=lidx(S(1), '连接被拒', '读响应超时', '没有冒号'), b=bars([['默认:连接被拒 → 重试到 B', 1, '重试了'], ['默认:HTTP 503', 503, '原样转给 client'], ['+ http_502/3/4:HTTP 503', 1, '重试到 B'], ['+ invalid_header:无冒号的头', 1, '重试到 B']], 503, done=[0, 2, 3], mark=[1]), kv=KV([['默认 error timeout', '连接错误、超时重试;5xx 原样转发'], ['http_5xx', '要重试 5xx 必须显式写'], ['响应体发了一半', '无论怎么配都不能换上游']], ['默认 error timeout'])),
    step("非幂等请求的风险。A 收到 POST /orders 后先把订单记下来,再处理 1.8 s 才回(超过 proxy_read_timeout 1 s);B 是正常的订单服务;100 个 POST,每个带唯一订单号。默认(POST 已经发给上游就不重试):client 看到 504 有 50 个、200 有 50 个;A 记下 50 个订单,B 记下 50 个,没有重复,但那 50 个 504 的订单其实已经成功创建。加 non_idempotent:client 全部 200;A 仍然记下 50 个,B 记下 100 个,有 50 个订单在 A 和 B 都被创建一次(重复创建)。", t=tl(S(2)), mark=lidx(S(2), 'non_idempotent'), done=lidx(S(2), '默认  '), b=bars([['默认:client 504', 50, '50'], ['默认:被 504 但已创建的订单', 50, '50'], ['non_idempotent:client 504', 0, '0'], ['non_idempotent:重复创建的订单', 50, '50']], 50, done=[0, 1], mark=[3], cur=[2]), kv=KV([['默认', '50 个 504,但订单已被 A 记下'], ['non_idempotent', '全部 200,50 个订单重复创建']], ['non_idempotent'])),
    step("换几次。三个上游 A1、A2、A3 都回 503,proxy_next_upstream error timeout http_503,发 30 个请求。默认(试遍所有上游):上游共收到 90 次,每个请求 3.0 次(A1 / A2 / A3 各 30)。proxy_next_upstream_tries 2:共 60 次,每个请求 2.0 次。tries 1:共 30 次,每个请求 1.0 次。三种配置 client 看到的都是 503。默认会把一个失败的请求放大成有几个上游就打几次;tries 给重试次数封顶。", t=tl(S(3)), mark=lidx(S(3), '默认'), done=lidx(S(3), 'tries 2', 'tries 1'), b=bars([['默认:每个请求打上游', 3.0, '3.0 次'], ['tries 2', 2.0, '2.0 次'], ['tries 1', 1.0, '1.0 次']], 3, mark=[0], done=[1, 2]), kv=KV([['默认', '90 次 / 30 个请求 = 3.0'], ['tries 2', '60 次 = 2.0'], ['tries 1', '30 次 = 1.0']], ['默认'])),
]
A = mkartv('v22', 22, '微服务,网关,nginx,proxy_next_upstream,重试,幂等,真实验证,动画演示',
    '实测 nginx proxy_next_upstream:默认只重试连接错误与超时,5xx 原样转给 client;加 non_idempotent 后 100 个 POST 里 50 个订单在 A 和 B 重复创建;三个上游全失败时默认放大 3.0 倍,tries 2 / 1 封顶为 2.0 / 1.0。',
    '哪些错误会被 nginx 换到下一个上游重试?5xx 算不算?POST 这样的非幂等请求重试了会怎样?换几次由谁决定?这篇用 10 种上游故障 × 6 种配置的矩阵,加订单重复创建的实验量出来。',
    [('50 个', '加 non_idempotent 后,100 个 POST 里被 A 和 B 都创建了一次的订单数(默认配置是 0,但有 50 个 504 的订单其实已经被 A 创建)'), ('3.0 → 1.0', '三个上游都回 503 时,默认与 proxy_next_upstream_tries 1 下,每个请求打到上游的次数'), ('502 / BadStatusLine', '上游响应头有一行没有冒号时 client 看到 nginx 的 502(invalid_header 才重试);状态行就不是 HTTP 时 client 的 HTTP 库抛 BadStatusLine')],
    [('哪些问题会重试', '<p>默认只有连接错误和超时;5xx 要显式写 http_5xx;响应体发了一半无论怎么配都不能换上游。</p>'),
     ('非幂等请求', '<p>POST 超时后默认不重试,client 看到失败但订单已创建;允许重试则会重复创建。要靠幂等键。</p>'),
     ('重试次数', '<p>默认试遍所有上游,会把一个失败的请求放大;tries 封顶。</p>')],
    steps,
    [ENV_V + '。nginx 是 Homebrew 的 1.31.6(proxy_read_timeout 1 s,所有 server 写了 max_fails=0);“A”的各种坏行为由本进程里的 Python 服务(HTTP 状态码)或原始 TCP 服务(沉默、RST、非法头、中途断开)扮演;矩阵里每个格子只测一次',
     '没有验证:POST 在 nginx 其他版本里的默认重试行为;proxy_next_upstream 与 upstream keepalive 的相互作用;http_403 / http_429 / http_404 以外的更多条件;gRPC 的 grpc_next_upstream;请求体很大且已经部分发送时的重试行为'],
    'proxy_next_upstream')
