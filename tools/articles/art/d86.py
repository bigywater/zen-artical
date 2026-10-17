from lib import *
import re
R = J('d86')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
pf = [int(x) for x in re.findall(r'(\d+) µs', R['perf'])]
steps = [
    step("simple_tag:{% hello \"ann\" %} → Hi, ann;关键字参数 {% hello name greeting=\"Yo\" %} → Yo, bob;{% hello \"cat\" as msg %} 把结果存进变量,后面 {{ msg }} 用两次只调用 tag 1 次;不用 as 写两次 {% hello \"x\" %}{% hello \"x\" %} 调用 2 次。", t=tl(L('simple')), kv=KV([['as 变量', '只调用一次,可重复使用']], ['as 变量'])),
    step("输出的转义:simple_tag 返回普通字符串会被自动转义(<b><i></b> → &lt;b&gt;&lt;i&gt;&lt;/b&gt;);用 format_html 返回,参数被转义、外层标签保留;而 mark_safe('<i>' + x + '</i>') 拼了未转义的参数,输出里的 <script>x</script> 原样出现——和第 84 篇一样,mark_safe + 拼接是 XSS。", t=tl(L('escape')), mark=[2], done=[1], kv=KV([['返回 HTML', '用 format_html'], ['mark_safe + 拼接', '危险']], ['返回 HTML'])),
    step("takes_context=True 的 tag 能读、也能写模板上下文:who 读取 request;set_flag 写入 flag,同一模板后面能读到 [set-by-tag];在 {% for %} 里写的变量,循环结束后不可见([]),因为循环体有自己的上下文层(push/pop)。", t=tl(L('ctx')), kv=KV([['写上下文', '只在当前作用域可见']], ['写上下文'])),
    step("inclusion_tag:渲染另一个模板。默认不会传外层变量({% item \"a\" %} → <li>a|</li>,site 为空);takes_context=True 才能拿到外层的 site(<li>b|S</li>)。循环里 4 次调用 inclusion_tag,tag 函数被调用 4 次(每次各渲染一次模板)。", t=tl([l for l in L('incl') if '默认不会传' not in l]), kv=KV([['inclusion_tag', '独立渲染子模板'], ['外层变量', '需要 takes_context']], ['外层变量'])),
    step(f"开销(20 处调用,渲染中位数):直接写 {{{{ v }}}} {pf[0]} µs;simple_tag {pf[1]} µs;inclusion_tag {pf[2]} µs——inclusion_tag 约为直接写的 {pf[2] / pf[0]:.0f} 倍(每次都要构建上下文并渲染子模板)。大量循环里的 inclusion_tag 会是渲染热点。", b=bars([['直接写变量(µs)', pf[0], str(pf[0])], ['simple_tag(µs)', pf[1], str(pf[1])], ['inclusion_tag(µs)', pf[2], str(pf[2])]], pf[2] * 1.1, done=[0, 1], mark=[2]), kv=KV([['inclusion_tag', f"约 {pf[2] / pf[0]:.0f} 倍开销"]], ['inclusion_tag'])),
    step("tag 里的异常原样抛出:ValueError: tag exploded(渲染失败),不会被吞掉。", t=tl(L('err')), kv=KV([['异常', '原样向上抛']], ['异常'])),
]
A = dict(
    n=86, series='django', tags='Django,模板,自定义Tag,simple_tag,inclusion_tag,真实验证,动画演示',
    desc=f'实测自定义模板标签:simple_tag 的参数与 as 变量;返回普通字符串会被转义、mark_safe 拼接未转义参数会 XSS;takes_context 读写上下文(循环里的写入循环外不可见);inclusion_tag 默认不带外层变量;20 处调用的渲染耗时:变量 {pf[0]} µs、simple_tag {pf[1]} µs、inclusion_tag {pf[2]} µs。',
    lead='simple_tag 和 inclusion_tag 有什么区别?返回 HTML 时怎么转义?能不能改模板变量?开销多大?这篇写几个小标签,把这些问题逐个跑出来。',
    facts=[('as 变量', 'simple_tag 用 as 存结果,重复使用时只调用一次'), ('转义', 'simple_tag 返回的字符串默认被转义;format_html 返回才保留标签,mark_safe + 拼接会 XSS'), (f'{pf[2] / pf[0]:.0f} 倍', f'inclusion_tag 相对直接写变量的渲染开销(20 处调用:{pf[2]} vs {pf[0]} µs)')],
    body=[
        sec('simple_tag', '', term('', blk('d86', 1)), '<p>适合「算一个值输出」。要在同一页多次使用同一个结果,用 <code>as</code>。</p>'),
        sec('输出转义', '', term('', blk('d86', 2)), '<p>simple_tag 的返回值会经过 <code>conditional_escape</code>:返回 <code>SafeString</code> 才保持原样。</p>'),
        sec('takes_context', '', term('', blk('d86', 3)), '<p>写上下文会污染模板的变量空间,通常不推荐;确实需要时注意作用域(第 87 篇看块作用域)。</p>'),
        sec('inclusion_tag', '', term('', blk('d86', 4)), '<p>相当于一个「带自己上下文的 include」。</p>'),
        sec('开销', '', term('', blk('d86', 5)), '<p>渲染 200 次取中位数,合成对比,SQLite 无关。</p>'),
        sec('异常', '', term('', blk('d86', 6)), '<p>没有静默吞掉。</p>'),
        sec('分步演示:自定义标签', '', demo('自定义 Tag', [('t', 'term', '实测输出'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。用 engines["django"].from_string 渲染,标签库放在 app 的 templatetags 目录', '没有验证:simple_block_tag(Django 5.2 起)、tag 的 parser 级自定义(@register.tag)、inclusion_tag 的模板加载在无 cached 下的开销、标签参数的位置/关键字混用错误信息'],
)
