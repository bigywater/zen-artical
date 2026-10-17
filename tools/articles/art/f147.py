from lib import *
S = SS('f147')
R = J('f147'); gu = R['gun']; ng = R['nginx']; dl = R['deadline']; dok = R['deadline_ok']
sy, gt = gu['sync worker'], gu['gthread worker']
steps = [
    step(f"gunicorn --timeout 2,视图要 5 秒:sync worker 在 {sy[1]:.0f} ms 时被 master 杀掉,客户端得到 {sy[0]}(gunicorn 的 Internal Server Error 页面),日志里有 WORKER TIMEOUT({sy[2]});gthread worker 同样的设置下,客户端等了 {gt[1]:.0f} ms 得到 {gt[0]}「slow done」,日志里没有 WORKER TIMEOUT({gt[2]})——gthread 的 worker 在请求线程之外还有心跳线程在通知 master,慢请求不会触发这个超时。所以 --timeout 对 sync worker 是「请求超时」,对 gthread 与 gevent 并不是。", t=tl(S(1)), mark=lidx(S(1), 'sync worker'), done=lidx(S(1), 'gthread worker'), kv=KV([['sync worker', '--timeout 到点就杀掉 worker'], ['gthread worker', '慢请求不触发这个超时']], ['gthread worker'])),
    step(f"nginx proxy_read_timeout 2 秒、gunicorn --timeout 30:客户端在 {ng[1]:.0f} ms 得到 {ng[0]}(504 Gateway Time-out,nginx 的页面);而 4 秒之后看服务端,那个慢请求仍然跑完了(日志里有 slow finished)——客户端或代理放弃之后,后端没有被通知,白白做完了整个请求。超时的各层要配合,耗时操作要能感知放弃。", b=bars([['客户端拿到 504', ng[1], f'{ng[1]:.0f} ms'], ['后端实际做完', 5000, '约 5000 ms']], 5000, mark=[0], done=[1]), t=tl(S(2)), mark=lidx(S(2), '客户端'), done=lidx(S(2), '4 秒之后'), kv=KV([['nginx proxy_read_timeout', '到点返回 504'], ['后端', '不会被中止,继续做完']], ['后端'])),
    step(f"应用层的截止时间:Flask 本身没有请求超时。协作式的做法是在循环里检查已用时间,超过就提前返回:/deadline?limit=1 在 {dl[1]:.0f} ms 时返回 504 与 {{error: took too long, steps: 10}}(只做了 10 步就停了);limit 够大时(20 秒)走完全部 50 步,{dok[1]:.0f} ms 返回 200。它只对「能分步检查」的工作有效;卡在一个阻塞调用里时(比如一条慢 SQL)检查不到,要靠数据库与 HTTP 客户端各自的超时设置(statement_timeout、请求的 timeout 参数)。", t=tl(S(3)), done=lidx(S(3), 'limit=1', 'limit=20'), kv=KV([['协作式截止时间', '循环里检查,超时提前返回'], ['阻塞调用里', '检查不到,要靠下游的超时']], ['协作式截止时间'])),
]
A = mkartf('f147', 147, 'Flask,请求超时,gunicorn,nginx,真实验证,动画演示',
    f'实测请求超时的各层:gunicorn --timeout 对 sync worker 在 {sy[1]:.0f} ms 杀掉 worker 返回 500 而对 gthread worker 不生效;nginx proxy_read_timeout 到点返回 504 但后端仍然把请求做完;应用层用协作式截止时间在 {dl[1]:.0f} ms 提前返回 504。',
    '请求超时到底由谁负责?gunicorn 的 --timeout 是不是请求超时?nginx 超时了后端还在跑吗?Flask 自己怎么限时?这篇用真实的 gunicorn 与 nginx 把每一层超时的行为量出来。',
    [('500 vs 200', 'gunicorn --timeout 2、视图 5 秒时,sync worker 与 gthread worker 的客户端结果'), (f'{ng[0]}', 'nginx proxy_read_timeout 到点返回的状态码'), ('仍然跑完', '客户端与代理放弃之后,后端慢请求的结果')],
    [('gunicorn --timeout', '<p>上一篇:<a href="flask-background-thread-app-context.html">后台线程与 Application Context</a>;下一篇:<a href="flask-long-polling.html">长轮询</a>。</p>'), ('nginx 的超时', '<p>nginx 是自己起的实例(自签证书),上游是 gthread 的 gunicorn。</p>'), ('应用层的截止时间', None)],
    steps, [ENV_F + '。gunicorn sync 与 gthread worker、nginx 1.31.6(自己的配置、非默认端口)', '没有验证:gevent worker 的 --timeout 行为、proxy_connect_timeout 与 proxy_send_timeout、客户端断开时 gunicorn 的处理、数据库 statement_timeout 与 requests 的 timeout 参数、负载均衡器的空闲超时'], '请求超时')
