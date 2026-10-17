from lib import *
R = J('d83'); bn = R['bench']
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("上下文处理器只对 RequestContext 运行:render(request, 'page.html') → 处理器 cp_a、cp_b 都被调用;render_to_string('page.html') 不带 request → 处理器一个都没调用,变量为空('a= b=');render_to_string(…, request=req) → 又调用。", t=tl(L('when'), cur=[0, 2], mark=[1]), kv=KV([['需要 request', 'render(request, …) 才会运行处理器']], ['需要 request'])),
    step("处理器每次渲染都运行,不管模板用没用它的变量(模板里没用任何变量时仍被调用);同一次渲染里 {% include %} 两次也只跑一遍(2 个处理器 = 2 次调用);连续渲染 3 次 = 6 次调用(每次渲染各一遍)。", t=tl(L('count')), kv=KV([['粒度', '每次 render 一遍,与模板内容无关']], ['粒度'])),
    step("顺序与优先级:cp_a 先、cp_b 后,后者覆盖前者(a='B 覆盖了 A');视图里 render(…, {'a': '视图里的 a'}) 传入的 context 优先级最高,覆盖处理器。", t=tl(L('override'), cur=[0], mark=[1]), kv=KV([['优先级', '视图 context > 后面的处理器 > 前面的处理器']], ['优先级'])),
    step(f"成本累加在每次渲染上:没有额外处理器时渲染一个空模板 {bn['base']:.3f} ms;加一个 sleep 5 ms 的处理器后 {bn['slow']:.2f} ms——处理器里的耗时(比如查数据库)会加到每个页面。", b=bars([['无额外处理器(ms)', bn['base'], f"{bn['base']:.3f}"], ['加一个 5 ms 处理器(ms)', bn['slow'], f"{bn['slow']:.2f}"]], bn['slow'] * 1.1, done=[0], mark=[1]), kv=KV([['处理器的开销', '每次渲染都付']], ['处理器的开销'])),
    step("Django 总会加入 csrf 处理器(我们配置了 request;实测列表:csrf、request)。auth、messages 等要在 TEMPLATES 的 context_processors 里显式列出。", t=tl(L('builtin')), kv=KV([['csrf', '总是启用']], ['csrf'])),
]
A = dict(
    n=83, series='django', tags='Django,模板,Context Processor,真实验证,动画演示',
    desc=f'实测上下文处理器:只对 RequestContext(render(request, …))运行、render_to_string 不带 request 时不运行;每次渲染各运行一遍(include 不重复);后面的覆盖前面的、视图 context 优先;一个 5 ms 的处理器让空模板渲染从 {bn["base"]:.3f} ms 变成 {bn["slow"]:.2f} ms。',
    lead='上下文处理器往每个模板里塞变量。它们什么时候运行?模板没用到也运行吗?开销多大?这篇给处理器打日志,把运行时机与次数数出来。',
    facts=[('需要 request', 'render(request, …) 才运行;render_to_string 不带 request 不运行'), ('每次渲染一遍', '与模板是否用到无关;{% include %} 不重复'), (f'{bn["base"]:.3f} → {bn["slow"]:.2f} ms', '加一个 5 ms 的处理器后,空模板渲染耗时')],
    body=[
        sec('什么时候运行', '', term('', blk('d83', 1)), '<p>邮件模板常用 <code>render_to_string</code> 且不带 request,这时处理器变量(比如 <code>user</code>)都拿不到。</p>'),
        sec('次数', '', term('', blk('d83', 2)), '<p>所以不要在处理器里做重活(数据库查询、远程调用),或者做成惰性(返回 lazy 对象/函数,模板真的用到时才执行)——惰性做法本文没有测。</p>'),
        sec('顺序与优先级', '', term('', blk('d83', 3)), '<p>变量名冲突时:后面的处理器覆盖前面的,视图传的 context 最高。</p>'),
        sec('开销', '', term('', blk('d83', 4)), '<p>本实验的处理器是 <code>time.sleep(0.005)</code> 的人工延迟,只为说明「每次渲染都付」。</p>'),
        sec('自带的', '', term('', blk('d83', 5)), '<p>项目里要用 <code>request.user</code> 就要启用 <code>auth</code> 处理器,要用 <code>messages</code> 同理。</p>'),
        sec('分步演示:上下文处理器', '', demo('Context Processor', [('t', 'term', '调用记录'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。处理器里打日志到文件;耗时为 40 次中位数', '没有验证:处理器返回 lazy 对象的效果、TemplateResponse 与处理器、Jinja2 后端下的等价机制、处理器抛异常时的错误信息'],
)
