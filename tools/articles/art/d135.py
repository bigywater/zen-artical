from lib import *
R = J('d135'); df = R['default']; cf = R['config']
def S(k): return [l for l in out('d135').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"没有 LOGGING 配置、DEBUG=False,gunicorn 上依次请求 /ok/(200)、/boom/(抛异常,500)、不存在的路径(404)、非法 Host(400):整个 gunicorn 日志只有 {df['n_lines']} 行——应用自己的 warning「即将出错」(来自 Python 的最后手段处理器)。500 的 traceback、404、DisallowedHost 都没有出现在日志里:Traceback {df['tb']} 段。", t=tl(S(1)), mark=[1], b=bars([['500 的 traceback', df['tb'], str(df['tb'])]], 3, mark=[0]), kv=KV([['默认 + DEBUG=False', '500 的 traceback 不进日志'], ['原因', 'Django 的 console 处理器只在 DEBUG=True 时生效']], ['默认 + DEBUG=False'])),
    step(f"配置 LOGGING(django、app 两个 logger 输出到 stderr),同样的四个请求:日志 {cf['n_lines']} 行、含 {cf['tb']} 段 traceback。可以看到 ERROR django.request「Internal Server Error: /boom/」、WARNING django.request「Not Found: /nope/」、ERROR django.security.DisallowedHost「Invalid HTTP_HOST header: 'evil.test'」。注意还有一条是我自己的就绪探测用 127.0.0.1 访问造成的 DisallowedHost。", t=tl(S(2)[:8]), done=[2, 3, 4, 5, 6, 7], kv=KV([['5xx', 'ERROR'], ['404', 'WARNING'], ['非法 Host', 'ERROR django.security.DisallowedHost']], ['5xx'])),
    step("加上请求 ID:一个中间件为每个请求生成 8 位 id(放进 contextvar,同时返回 X-Request-ID 响应头),一个日志 Filter 把它写进每条日志。用 /boom/ 的 X-Request-ID 过滤日志,就得到这次请求的 WARNING 与 ERROR 两条——用户报告问题时拿响应头里的 id 就能定位日志。", t=tl(S(2)[8:]), done=[0], kv=KV([['X-Request-ID', '响应头 + 日志字段,一一对应']], ['X-Request-ID'])),
    step("错误追踪工具挂钩的位置:got_request_exception 信号。只有未处理的异常(/boom/)触发,正常 200 与 404 不触发,不依赖 LOGGING 配置。", t=tl(S(3)), done=[0], kv=KV([['got_request_exception', '未处理异常才触发']], ['got_request_exception'])),
]
A = dict(
    n=135, series='django', tags='Django,日志,错误追踪,LOGGING,部署,真实验证,动画演示',
    desc=f'生产环境日志:没有 LOGGING 配置、DEBUG=False 时,gunicorn 日志里只有 {df["n_lines"]} 行,500 的 traceback、404、DisallowedHost 都不见了;配置 LOGGING 后有 {cf["n_lines"]} 行、{cf["tb"]} 段 traceback;请求 ID 过滤器让一次请求的日志可以按 id 查;got_request_exception 信号是错误追踪的挂钩。',
    lead='把 DEBUG 关掉之后,出错了去哪里看?这篇用真实的 gunicorn 对比有没有 LOGGING 配置时日志里到底有什么,再加上请求 ID,最后看错误追踪工具挂钩的信号。',
    facts=[('Traceback 0 段', '默认配置 + DEBUG=False:500 错误的 traceback 不会出现在 gunicorn 日志里'), (f'{cf["n_lines"]} 行', '配置 LOGGING 之后同样四个请求产生的日志行数'), ('X-Request-ID', '响应头与日志字段对应,按 id 过滤日志')],
    body=[
        sec('默认配置下的日志', '', term('', blk('d135', 1)), '<p>这是一个很容易被忽略的坑:本地开发时 <code>DEBUG=True</code>,console 处理器把错误打到终端;上线 <code>DEBUG=False</code> 之后,Django 默认只通过 <code>mail_admins</code> 发邮件(第 129 篇),没配邮件就什么也看不到。这里的结论只对这个最小项目与 gunicorn 的组合,实际现象还取决于你的 LOGGING。</p>'),
        sec('配置之后', '', term('', blk('d135', 2)), '<p>建议至少配置 <code>django</code> 与你自己的 logger,输出到 stderr / stdout,让 gunicorn、容器平台去收集。</p>'),
        sec('请求 ID', '', '<p>用 <code>contextvars</code> 保存当前请求的 id,Filter 把它加到日志记录上。上一个区块的日志里每行都有 <code>rid=…</code>,同一个 id 的行属于同一个请求。本文只测了同步的 gunicorn;异步视图下 contextvar 的传播方式没有验证。</p>'),
        sec('got_request_exception', '', term('', blk('d135', 3)), '<p>Sentry 之类的 SDK 就是挂在这个信号(以及日志)上的。本文没有接入任何真实的错误追踪服务。</p>'),
        sec('分步演示', '', demo('生产环境日志', [('t', 'term', '输出'), ('b', 'bars', 'Traceback'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。gunicorn 26.2.0 单 worker,日志取自它的 stderr 输出(--log-level warning);四个请求依次发出', '没有验证:JSON 格式日志、日志轮转与集中收集、Sentry / OpenTelemetry、异步视图下的 request_id、gunicorn access log 的格式、邮件通知(第 129 篇)'],
)
