from lib import *
R = J('d17')
def L(k): return [l.strip() for l in R[k].splitlines() if l.strip() and not l.strip().startswith('[')]
steps = [
    step("三层中间件 M1、M2、M3 的正常请求:进入按 M1 → M2 → M3,视图执行,响应按 M3 → M2 → M1 返回。像洋葱一层层包起来。", t=tl(L('normal'), cur=[0, 1, 2, 3], done=[4, 5, 6]), n=fl([['M1', '进入'], ['M2', '进入'], ['M3', '进入'], ['view', '执行']], done=[0, 1, 2, 3]), kv=KV([['进入顺序', 'M1 → M2 → M3'], ['返回顺序', 'M3 → M2 → M1']], ['进入顺序'])),
    step("M2 直接返回响应(短路):M3 和视图都没有执行,响应直接回到 M1,M1 看到的是 status=202。外层中间件仍然会「收到响应」——短路只是跳过了内层。", t=tl(L('short'), cur=[2], mark=[3]), n=fl([['M1 进入', ''], ['M2 短路返回 202', ''], ['M3 / view', '未执行'], ['M1 收到 202', '']], done=[0, 1, 3], mark=[2]), kv=KV([['短路', '内层与视图都不执行,外层照常收到响应']], ['短路'])),
    step("视图抛 ValueError(DEBUG=False):M3、M2、M1 收到的都是 status=500 的响应,而不是异常——Django 在每一层外面套了一个把异常转换成响应的包装。同样,视图抛 Http404 时各层看到 404。", t=tl(L('viewbad'), cur=[3], mark=[4, 5, 6]), kv=KV([['中间件看到的', '500 响应,不是异常']], ['中间件看到的'])),
    step("中间件自己抛异常(M2 在调用 get_response 之前抛 ValueError):M3 和视图没执行,M1 收到 status=500 的响应。异常被最近的外层转换成了 500。", t=tl(L('mwboom'), cur=[2], mark=[3]), kv=KV([['M2 抛异常', 'M1 收到 500 响应']], ['M2 抛异常'])),
    step("DEBUG=True 时流程完全一样,只是 500 响应的正文是技术调试页(以 <!DOCTYPE html> 开头);中间件仍然看到 500 响应。DEBUG 只影响响应内容,不影响异常转换的方式。", t=tl(L('debug'), mark=[4, 5, 6]), kv=KV([['DEBUG=True', '同样的转换,正文是调试页']], ['DEBUG=True'])),
]
A = dict(
    n=17, series='django', tags='Django,Middleware,异常,真实验证,动画演示',
    desc='用三层带日志的中间件实测:正常请求的进入/返回顺序、某层短路后内层与视图不执行、视图或中间件抛异常时每一层看到的是 500 响应而不是异常(DEBUG 只改变响应正文)。',
    lead='中间件里怎么处理异常?一层直接返回响应会发生什么?这篇不背结论,用 M1、M2、M3 三层中间件加日志,在真实请求里把每种情形的调用顺序和每层看到的东西都记下来。',
    facts=[('洋葱', '进入 M1→M2→M3,返回 M3→M2→M1;短路则内层不执行,外层照常收到响应'), ('响应而非异常', '视图或内层中间件抛异常时,外层看到的是 500(或 404)响应,不是异常'), ('DEBUG', 'DEBUG 只改变 500 响应的正文,不改变异常转换的方式')],
    body=[
        sec('正常与短路', '', term('', blk('d17', 1)), '<p>M2 的短路在响应阶段仍会流过 M1,因此「在外层做统一的响应头 / 日志」对短路的请求同样有效。</p>'),
        sec('视图抛异常', '', term('', blk('d17', 2)), '<p>写 <code>try: response = self.get_response(request) except Exception:</code> 在新式中间件里通常是抓不到视图异常的:异常已经在更里层被转换成响应了。要在异常发生时做事,用 <code>process_exception</code> 钩子(第 18 篇)或 <code>got_request_exception</code> 信号(本文没测)。</p>'),
        sec('中间件自己抛异常', '', term('', blk('d17', 3)), '<p>M2 抛出的异常由 M1 外面的转换层处理,M1 收到 500 响应;M3 与视图不会执行。</p>'),
        sec('DEBUG=True', '', term('', blk('d17', 4)), '<p>同样的转换流程,正文换成调试页。</p>'),
        sec('分步演示:洋葱模型与异常', '', demo('中间件与异常', [('t', 'term', '调用日志'), ('n', 'flow', '过程'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。用 django.test.Client(raise_request_exception=False),日志写在进程内列表里', '没有验证:异步中间件(async def __call__)下的行为、StreamingHttpResponse 出错时的处理(响应已经开始发送后异常无法转换)、got_request_exception 信号、真实服务器(gunicorn / runserver)与测试客户端在异常处理上的细微差异'],
)
