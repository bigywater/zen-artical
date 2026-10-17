from lib import *
S = SS('f160')
R = J('f160'); hm = R['hook_vs_mw']; ov = R['overhead']; pc = R['pct']
steps = [
    step(f"钩子计时与 WSGI 中间件计时对同一个请求记到的耗时:/fast after_request 记 {hm['/fast'][0]:.2f} ms、中间件 {hm['/fast'][1]:.2f} ms;/work(视图睡 50 ms){hm['/work'][0]:.2f} ms 对 {hm['/work'][1]:.2f} ms,基本一致;/stream(流式响应,三块各等 0.1 秒)after_request 只记到 {hm['/stream'][0]:.2f} ms——它在响应对象创建之后、响应体还没生成之前就执行了,而包在 WSGI 层、等响应体迭代完才记录的中间件记到 {hm['/stream'][1]:.0f} ms。Server-Timing 头(app;dur=…)可以直接让浏览器开发者工具显示服务端耗时,但它用的是前一种口径。流式响应的耗时只能在 WSGI 层统计。", b=bars([['/stream after_request', max(hm['/stream'][0], 1), f"{hm['/stream'][0]:.2f} ms"], ['/stream WSGI 中间件', hm['/stream'][1], f"{hm['/stream'][1]:.0f} ms"]], hm['/stream'][1], mark=[0], done=[1]), t=tl(S(1)), done=lidx(S(1), '/fast', '/work'), mark=lidx(S(1), '/stream'), kv=KV([['after_request', '响应体生成之前就记录了'], ['WSGI 中间件', '包含响应体迭代完']], ['WSGI 中间件'])),
    step(f"视图抛出未处理的异常(返回 500)时:4 个请求(其中 2 个抛异常)after_request 被调用 {R['calls'][0]} 次,teardown_request 被调用 {R['calls'][1]} 次——默认的 500 响应也走 after_request,所以计时钩子在出错请求上同样会记录。但需要「无论如何都记录」(包括钩子本身出错)时,teardown_request 是更保险的位置。", t=tl(S(2)), done=lidx(S(2), '4 个请求'), kv=KV([['after_request', '500 响应也会调用'], ['teardown_request', '总会调用']], ['teardown_request'])),
    step(f"计时本身的开销:无计时 {ov[0]:.0f} µs/请求,带 before/after 钩子和 WSGI 中间件 {ov[1]:.0f} µs/请求,多约 {ov[1] - ov[0]:.0f} µs(test client,3000 次取最小)。几乎可以忽略,所以请求耗时统计可以常开。", t=tl(S(3)), done=lidx(S(3), '无计时'), kv=KV([['计时开销', f'约 {ov[1] - ov[0]:.0f} µs/请求']], ['计时开销'])),
    step(f"平均值会骗人:5% 的请求很慢(约 200 ms),其余约 5 ms,统计 {pc[0]} 个请求:平均 {pc[1]:.1f} ms,但 p50 只有 {pc[2]:.1f} ms,p95 是 {pc[3]:.1f} ms,p99 是 {pc[4]:.1f} ms,最大 {pc[5]:.1f} ms。平均数既不代表典型请求,也看不出慢的那一部分;监控要看分位数(p50、p95、p99)。", b=bars([['平均', pc[1], f'{pc[1]:.1f} ms'], ['p50', pc[2], f'{pc[2]:.1f} ms'], ['p95', pc[3], f'{pc[3]:.0f} ms'], ['p99', pc[4], f'{pc[4]:.0f} ms']], pc[4], mark=[3], done=[0, 1]), t=tl(S(4)), mark=lidx(S(4), '400 个样本'), kv=KV([['平均', f'{pc[1]:.1f} ms'], ['p50 / p95 / p99', f'{pc[2]:.1f} / {pc[3]:.0f} / {pc[4]:.0f} ms']], ['p50 / p95 / p99'])),
]
A = mkartf('f160', 160, 'Flask,请求耗时,Server-Timing,分位数,真实验证,动画演示',
    f'实测请求耗时统计:after_request 钩子记不到流式响应的真实耗时({hm["/stream"][0]:.2f} ms 对中间件 {hm["/stream"][1]:.0f} ms)、500 响应也会走 after_request、计时开销约 {ov[1] - ov[0]:.0f} µs/请求、5% 慢请求时平均 {pc[1]:.1f} ms 而 p99 是 {pc[4]:.0f} ms。',
    '怎么统计 Flask 每个请求的耗时?钩子与 WSGI 中间件有什么区别?出错的请求会不会被统计到?为什么要看分位数而不是平均数?这篇逐项量出来。',
    [(f'{hm["/stream"][0]:.2f} vs {hm["/stream"][1]:.0f} ms', '流式响应:after_request 与 WSGI 中间件记到的耗时'), (f'约 {ov[1] - ov[0]:.0f} µs', '计时钩子加中间件每个请求的额外开销'), (f'{pc[1]:.0f} / {pc[4]:.0f} ms', '5% 慢请求时的平均值与 p99')],
    [('钩子与中间件的口径', '<p>上一篇:<a href="flask-test-blueprint.html">测试 Blueprint</a>;下一篇:<a href="flask-slow-sql.html">慢 SQL 统计</a>。</p>'), ('出错的请求', None), ('计时的开销', None), ('平均值与分位数', '<p>这里用 test client 的 400 个样本,耗时是 time.sleep 模拟的。</p>')],
    steps, [ENV_F, '没有验证:真实 gunicorn 下排队时间(请求在 worker 前等待)不会被应用内计时记到、Prometheus 直方图与 OpenTelemetry 的实现、采样率、多进程下分位数的聚合方式'], '请求耗时统计')
