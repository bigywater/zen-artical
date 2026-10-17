from lib import *
S = SS('f181')
R = J('f181'); LV = R['lv']; G = R['g']; JS = R['json']; DV = R['dev']
kl = list(LV); kg = list(G); kd = list(DV)
steps = [
    step(f"app.logger 是 Flask 自带的 logger。什么都不配、debug 关:只输出 {LV[kl[0]][0]}(info 和 debug 被丢掉,因为有效级别是 WARNING;格式是 Flask 自带的 [时间] 级别 in 模块: 消息);app.debug = True:四个级别全输出({LV[kl[1]][0]});app.logger.setLevel(INFO):{LV[kl[2]][0]};先 logging.basicConfig(level=INFO) 再建应用:输出用的是根 logger 的格式('INFO root-handler: …'),app.logger 上的 handler 列表是空的——Flask 发现已经有合适级别的 handler 就不再添加自己的了。结论:要看到 info,必须自己设置级别;一旦配置了根 logger,Flask 就不插手。", t=tl(S(1)), done=lidx(S(1), 'setLevel', 'basicConfig'), mark=lidx(S(1), '什么都不配'), kv=KV([['默认', 'WARNING 及以上'], ['debug=True', '全部'], ['basicConfig 在前', 'Flask 不再加 handler']], ['默认'])),
    step(f"在 gunicorn 下(--log-level info):什么都不配时,view 里的 app.logger.info 看不到,只有 warning 一行(Flask 的格式,不是 gunicorn 的);未捕获异常的 \"Exception on /boom [GET]\" 带完整 traceback 记为 ERROR(模块名是 flask 的 app,所以显示 'in app')。把 gunicorn.error 的 handler 与级别接到 app.logger 上(两行代码)之后,info、warning、ERROR 都用 gunicorn 的格式输出,带 worker pid,并服从 --log-level。--log-level 只管 gunicorn 自己的 logger,不会自动影响 app.logger。", t=tl(S(2)), done=lidx(S(2), '接到 app.logger', 'info from view'), mark=lidx(S(2), '什么都不配', 'Exception'), kv=KV([['不接', 'info 丢失'], ['接 gunicorn.error', 'info 可见,格式统一']], ['接 gunicorn.error'])),
    step(f"用 dictConfig 配一个 JSON formatter 加一个 filter(filter 里用 has_request_context 把请求的 method 与 path 写进日志记录),挂在根 logger 上:/hello 里的 info 输出一行 JSON({JS[0][:80]}…);未捕获异常变成 level=ERROR 的一行,exc 字段里是异常最后一行。这样每条日志都带上请求信息、可以被日志系统按字段检索。注意 JSON 里只放了异常最后一行,完整 traceback 要自己决定是否保留。", t=tl(S(3)), done=lidx(S(3), 'hello'), mark=lidx(S(3), 'boom', 'ZeroDivision'), kv=KV([['格式', 'JSON,一行一条'], ['请求信息', 'filter 里取 method/path']], ['请求信息'])),
    step(f"开发服务器的访问日志('GET / HTTP/1.1 200')不是 Flask 的 logger,而是 werkzeug 的:默认每个请求一行({len(DV[kd[0]])} 行);getLogger('werkzeug').setLevel(WARNING) 之后是 {len(DV[kd[1]])} 行。注意 gunicorn 下的访问日志是 gunicorn 自己的(--access-logfile),和 werkzeug 的 logger 无关,所以生产环境的访问日志要在 gunicorn 一侧配置。", t=tl(S(4)), done=lidx(S(4), 'WARNING'), mark=lidx(S(4), '默认'), kv=KV([['默认', f'{len(DV[kd[0]])} 行'], ['werkzeug=WARNING', f'{len(DV[kd[1]])} 行']], ['werkzeug=WARNING'])),
]
A = mkartf('f181', 181, 'Flask,日志,logging,dictConfig,gunicorn,真实验证,动画演示',
    'app.logger 默认只输出 WARNING 以上,先配根 logger 时 Flask 不再加自己的 handler;gunicorn 下 info 默认丢失,接上 gunicorn.error 的 handler 后格式统一;用 dictConfig 配 JSON 格式并带上请求信息;开发服务器的访问日志来自 werkzeug 的 logger。全部用真实进程运行验证。',
    'Flask 的日志该怎么配?默认的 app.logger 做了什么、为什么在 gunicorn 下 info 看不到、怎么输出结构化日志?这篇用真实的进程逐项验证(请求 ID 见第 182 篇,多进程日志重复见第 185 篇)。',
    [('WARNING', '什么都不配时 app.logger 的有效级别(info 与 debug 被丢弃)'), ('0 个', '先 logging.basicConfig 之后 app.logger 自己的 handler 数量'), ('JSON', 'dictConfig 配出的一行一条结构化日志')],
    [('app.logger 的默认行为', '<p>上一篇:<a href="flask-graceful-shutdown.html">优雅关闭</a>;下一篇:<a href="flask-request-id-tracing.html">请求 ID 链路追踪</a>。</p>'), ('在 gunicorn 下', None), ('结构化日志', None), ('访问日志', None)],
    steps, [ENV_F + '。gunicorn、Flask 开发服务器', '没有验证:日志写文件与轮转(RotatingFileHandler)、多进程同时写同一个文件、QueueHandler 异步日志、日志采集到 ELK 或云服务、日志性能开销、敏感信息脱敏'], 'Flask 日志配置')
