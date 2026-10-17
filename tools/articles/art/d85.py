from lib import *
R = J('d85')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("@register.filter 装饰一个函数:{{ v|shout }} → HI!;带参数 {{ v|add_str:\"-x\" }} → hi-x;链式 {{ v|shout|add_str:\"?\" }} → HI!?;变量也能作参数(add_str:suffix)。过滤器最多接受一个参数:写两个 → TemplateSyntaxError: Could not parse the remainder。", t=tl(L('basic')), kv=KV([['参数', '最多一个']], ['参数'])),
    step("自动转义:普通过滤器返回的字符串会被再转义(<I>! → &lt;I&gt;!);is_safe=True 的过滤器:输入本来是 safe 时保持 safe(<i><end>),输入不是 safe 时仍转义;needs_autoescape=True 的过滤器自己按 autoescape 参数决定转义:自动转义开时对输入转义再包 <b>,{% autoescape off %} 里不转义。", t=tl(L('escape')), kv=KV([['is_safe', '不把不安全的输入变安全'], ['needs_autoescape', '自己负责转义']], ['needs_autoescape'])),
    step("过滤器里的异常不会被吞掉:boom 抛 ValueError → 渲染直接抛出;对 None 用 len 的过滤器 → TypeError;不存在的过滤器 → TemplateSyntaxError: Invalid filter: 'nofilter';变量不存在时过滤器收到空字符串(shout 得到 '!')——过滤器要能处理空值。", t=tl(L('errors')), mark=[0, 3], kv=KV([['过滤器里的异常', '原样向上抛']], ['过滤器里的异常'])),
    step("调用次数:同一个表达式在模板里写两次就调用两次(不缓存);{% for %} 里每次迭代一次(5 次循环 5 次);想只算一次用 {% with x=v|counted %} 存下来再用(调用 1 次)。", t=tl(L('calls')), b=bars([['写两次', 2, '2'], ['5 次循环', 5, '5'], ['{% with %} 存一次', 1, '1']], 5, mark=[1], done=[2]), kv=KV([['重复计算', '用 {% with %} 缓存']], ['重复计算'])),
    step("过滤器必须先 {% load 库名 %}:没有加载 myf 直接用 {{ v|shout }} → TemplateSyntaxError: Invalid filter: 'shout'(注意报错说的是「无效过滤器」,不是「库没加载」)。库文件放在 app 的 templatetags/ 目录里,app 要在 INSTALLED_APPS 中。", t=tl(L('load')), kv=KV([['加载', '{% load myf %}']], ['加载'])),
]
A = dict(
    n=85, series='django', tags='Django,模板,自定义Filter,真实验证,动画演示',
    desc='实测自定义模板过滤器:参数只能有一个;is_safe / needs_autoescape 与自动转义的配合;过滤器里的异常原样抛出;同一表达式写两次调用两次、for 里每次迭代一次,{% with %} 可缓存;不 {% load %} 会报 Invalid filter。',
    lead='自定义过滤器几行就能写完,但转义、异常、调用次数这三件事常被忽略。这篇写七个小过滤器,逐个验证它们在模板里的真实行为。',
    facts=[('1 个参数', '过滤器最多接受一个参数;两个会 TemplateSyntaxError'), ('is_safe / needs_autoescape', '决定过滤器的返回值是否被再转义'), ('不缓存', '同一个过滤器表达式每写一次、每次循环迭代都调用一次')],
    body=[
        sec('基本用法', '', term('', blk('d85', 1)), '<p>过滤器就是普通函数,第一个参数是变量值,第二个(可选)是过滤器参数。</p>'),
        sec('转义', '', term('', blk('d85', 2)), '<p>返回 HTML 的过滤器要么用 <code>needs_autoescape</code> 自己转义输入再 <code>mark_safe</code>,要么用 <code>format_html</code>;<code>is_safe=True</code> 只是「如果输入是 safe,输出仍是 safe」,不会让不安全的输入变安全。</p>'),
        sec('错误', '', term('', blk('d85', 3)), '<p>模板里访问不存在的变量不报错(得到 <code>string_if_invalid</code>),但过滤器里的异常一定会传出来。</p>'),
        sec('调用次数', '', term('', blk('d85', 4)), '<p>过滤器里做数据库查询或重计算时要注意调用次数。</p>'),
        sec('加载', '', term('', blk('d85', 5)), '<p><code>templatetags</code> 目录需要有 <code>__init__.py</code>,库名就是文件名。</p>'),
        sec('分步演示:自定义过滤器', '', demo('自定义 Filter', [('t', 'term', '实测输出'), ('b', 'bars', '调用次数'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。用 engines["django"].from_string 渲染', '没有验证:expects_localtime、stringfilter 装饰器、过滤器抛 ValidationError 之外的错误页表现、在 Jinja2 后端里的写法'],
)
