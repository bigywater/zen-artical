from lib import *
S = SS('f182')
R = J('f182'); B = R['basic']; NP = R['noprop']; BD = R['bad']; BM = R['boom']; NG = R['nginx']
steps = [
    step(f"做法:before_request 里取请求头 X-Request-ID,没有就用 uuid 生成,存进 g;after_request 把它写回响应头;一个 logging.Filter 用 has_request_context 把它加到每条日志里。不带头:服务端生成 {B['id1']},响应头里返回这个值;带 X-Request-ID: client-abc-123:原样沿用。服务 A 调用服务 B 时把同一个 ID 放进请求头,两边的日志里都是同一个 ID:A 的日志 rid={B['id2']},B 的日志也是 rid={B['b'][1]}。一次请求经过几个服务,用一个 ID 就能把日志串起来。", t=tl(S(1)), done=lidx(S(1), '不带头', '带头', 'B 的日志'), mark=[], kv=KV([['入口', '取请求头,没有就生成'], ['出口', '写回响应头'], ['下游调用', '把 ID 放进请求头']], ['下游调用'])),
    step(f"A 调用 B 时如果忘了带上这个头:A 的响应头 ID 是 {NP[0]},B 的日志里却是另一个 ID {NP[1][0]}——B 自己生成了新的,链路在这里断了。传播要靠调用方每次都带上;封装一个带头的 HTTP 客户端函数,比在每个调用处手写更不容易漏。", t=tl(S(2)), done=[], mark=lidx(S(2), 'B 自己生成'), kv=KV([['A', NP[0]], ['B', NP[1][0]], ['结果', '日志对不上']], ['结果'])),
    step(f"客户端传来的 ID 是不可信输入。传一个 300 多字符、含空格和引号的值:不校验时服务端把它原样回显进响应头({BD['不校验']} 个字符)并写进每一行日志;校验(只允许 [A-Za-z0-9._-]、最长 64)时不合规的被丢掉,重新生成一个 {BD['校验']} 位的 ID。把外部传入的值写进日志之前,先限制字符与长度。", t=tl(S(3)), done=lidx(S(3), '校验:'), mark=lidx(S(3), '不校验'), b=bars([['不校验:响应头 ID 长度', BD['不校验'], str(BD['不校验'])], ['校验:响应头 ID 长度', BD['校验'], str(BD['校验'])]], 330, mark=[0], done=[1]), kv=KV([['不校验', f"{BD['不校验']} 字符原样回显"], ['校验', f"{BD['校验']} 字符,重新生成"]], ['校验'])),
    step(f"两个细节。第一,500 的响应:自定义的 500 错误处理器里把 request_id 放进 JSON({BM[1]}),用户报障时报这个 ID 就能查到日志。第二,日志里的 ID 来自 Flask 的请求上下文:视图里的日志有 ID,在视图里启动的后台线程里的日志是 rid=-(线程里没有请求上下文);要在线程里保留,得把 ID 作为参数传进去,或者用 contextvars 复制上下文。", t=tl(S(4)), done=lidx(S(4), '视图里'), mark=lidx(S(4), '后台线程'), kv=KV([['500 响应', '带 request_id'], ['后台线程', 'rid=-,没有请求上下文']], ['后台线程'])),
    step(f"前面有 nginx 时可以由它生成:proxy_set_header X-Request-ID $request_id。nginx 的访问日志(log_format 里写 $request_id)、Flask A、Flask B 的日志里是同一个 ID {NG['nid'][0][:8]}…。一个小坑:nginx 用 add_header 又加了一个 X-Request-ID 响应头,而 Flask 的 after_request 也加了,客户端收到的就是 {len(NG['hdrs'])} 个同名头——两边选一边加即可。", t=tl(S(5)), done=lidx(S(5), 'nginx 访问日志'), mark=lidx(S(5), 'nginx 响应头'), kv=KV([['nginx', '$request_id 生成并转发'], ['响应头', f"{len(NG['hdrs'])} 个同名头(重复)"]], ['响应头'])),
]
A = mkartf('f182', 182, 'Flask,请求ID,链路追踪,日志,nginx,真实验证,动画演示',
    '用两个真实的 gunicorn 服务和 nginx 实现请求 ID:入口沿用或生成 ID、写回响应头、通过日志 filter 进每条日志、调用下游时传播;验证忘记传播时链路断掉、不校验客户端 ID 会原样回显 300 字符、后台线程里拿不到 ID、nginx 的 $request_id 与 Flask 日志一致且响应头重复。',
    '线上出问题时,怎么把一个请求在 nginx、Flask、下游服务里的日志串起来?一个请求 ID 就够了,但有几个地方容易出错:要不要信任客户端传来的 ID、下游调用有没有带上、线程里还能不能拿到。这篇用真实的服务把它们逐项验证(日志基础见第 181 篇)。',
    [('X-Request-ID', '请求头与响应头里用来串联日志的 ID'), (f'{BD["不校验"]} → {BD["校验"]}', '不合规的客户端 ID 在不校验 / 校验时的响应头长度'), ('rid=-', '后台线程里日志拿不到请求 ID')],
    [('入口与传播', '<p>上一篇:<a href="flask-logging-config.html">日志配置</a>;下一篇:<a href="flask-error-monitoring.html">错误监控</a>。</p><p>实验里 A 与 B 是两个 gunicorn 服务,A 用 urllib 调用 B。</p>'), ('漏传播', None), ('客户端传来的 ID', None), ('500 与线程', None), ('nginx', None)],
    steps, [ENV_F + '。gunicorn(两个服务)、nginx(自己的配置、非默认端口)', '没有验证:OpenTelemetry/W3C traceparent 等标准的链路追踪、requests/httpx 客户端的自动传播、Celery 任务里的传播、异步视图里的 contextvars、多级 nginx 与云负载均衡生成 ID 的差别'], '请求 ID 链路追踪')
