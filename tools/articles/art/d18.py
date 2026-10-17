from lib import *
R = J('d18')
def L(k): return [l.strip() for l in R[k].splitlines() if l.strip() and not l.strip().startswith('[')]
steps = [
    step("三个钩子的位置(先看普通视图):所有中间件的 __call__ 先依次进入(M1→M2→M3);然后请求已经匹配到视图,process_view 按 M1→M2→M3 依次调用,最后才是视图执行。process_view 在「URL 解析之后、视图执行之前」。", t=tl(L('ok'), cur=[3, 4, 5], mark=[6]), kv=KV([['process_view', '所有 __call__ 进入之后、视图之前,按 M1→M2→M3']], ['process_view'])),
    step("视图返回 TemplateResponse(还没渲染):process_template_response 按相反的顺序 M3→M2→M1 调用,此时 rendered=False,可以改模板或上下文;它们都调用完,响应才被渲染(最终 body 是 hello 1),然后各层 __call__ 依次返回。", t=tl(L('tpl'), cur=[7, 8, 9], done=[10, 11, 12]), kv=KV([['process_template_response', '按 M3→M2→M1,rendered=False'], ['渲染', '在所有钩子之后']], ['process_template_response'])),
    step("M2.process_view 直接返回响应(203):M3 的 process_view 和视图都没有执行;但响应仍然从 M3 开始一层层返回(M3→M2→M1 的 __call__ 都收到 203)。", t=tl(L('pv'), cur=[5], mark=[6, 7]), kv=KV([['process_view 返回响应', '跳过后面的 process_view 和视图']], ['process_view 返回响应'])),
    step("视图抛 ValueError,三个 process_exception 都返回 None:按 M3→M2→M1 依次调用,没有任何一个处理它,最终 500。process_exception 的顺序和 process_view 相反。", t=tl(L('exc_all_none'), cur=[7, 8, 9, 10], mark=[11]), kv=KV([['process_exception', '按 M3→M2→M1']], ['process_exception'])),
    step("M2.process_exception 返回了响应:调用到 M2 就停,M1.process_exception 不再被调用;响应(200,handled by M2)作为正常响应继续向外返回。", t=tl(L('exc_m2'), cur=[7, 8], mark=[9], done=[10, 11]), kv=KV([['第一个返回响应的', '终止后续 process_exception']], ['第一个返回响应的'])),
]
A = dict(
    n=18, series='django', tags='Django,Middleware,钩子,真实验证,动画演示',
    desc='用日志实测 process_view、process_exception、process_template_response 三个中间件钩子的调用位置与顺序:process_view 按声明顺序、后两者反向;process_view 返回响应会跳过视图;process_exception 第一个返回响应的会终止链;TemplateResponse 在所有钩子之后才渲染。',
    lead='除了 __call__,中间件还有三个钩子。它们各在请求生命周期的哪个位置?顺序一样吗?返回响应会怎样?这篇用三层带日志的中间件把答案直接打出来。',
    facts=[('顺序相反', 'process_view 按 M1→M2→M3;process_exception 与 process_template_response 按 M3→M2→M1'), ('短路', 'process_view 返回响应:后面的 process_view 与视图都不执行,响应仍从内层逐层返回'), ('先钩子后渲染', 'TemplateResponse 在所有 process_template_response 之后才渲染')],
    body=[
        sec('process_view 的位置', '', term('', blk('d18', 1)), '<p>所有中间件的 <code>__call__</code> 先依次进入,此时 URL 已经解析,然后统一调用 <code>process_view</code>。所以 <code>process_view</code> 里能拿到 <code>view_func</code> 和参数,做「按视图决定是否放行」的事(比如 CSRF 就在这一层)。</p>'),
        sec('TemplateResponse 与渲染', '', term('', blk('d18', 2)), '<p><code>process_template_response</code> 只对有 <code>render</code> 方法的响应调用,此时还没渲染;可以在这里改 <code>template_name</code>、<code>context_data</code>。渲染发生在所有钩子之后。</p>'),
        sec('process_view 返回响应', '', term('', blk('d18', 3)), '<p>返回响应就等于短路了视图,但因为 <code>__call__</code> 已经全部进入过,响应仍会按洋葱顺序返回。</p>'),
        sec('process_exception', '', term('', blk('d18', 4)), '<p>视图抛异常时按相反顺序询问每个中间件,第一个返回响应的就是最终结果。全都返回 None 时,异常继续向上,最终成为 500(第 17 篇)。</p>'),
        sec('分步演示:三个钩子的顺序', '', demo('中间件钩子', [('t', 'term', '调用日志'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。钩子写在同一个类里,用 django.test.Client 触发', '没有验证:异步中间件的钩子、process_view 抛异常时的行为、process_template_response 返回新响应对象、基于 MiddlewareMixin 的旧式中间件与本文写法的差别'],
)
