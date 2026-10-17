from lib import *
R = J('d84')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("{{ x }} 默认转义五个字符:< → &lt;、> → &gt;、& → &amp;、\" → &quot;、' → &#x27;;{{ x|safe }} 原样输出;mark_safe 的对象、{% autoescape off %} 里也原样。注意 {{ x|safe|upper }}:safe 之后接 upper,结果不再是 safe,又被转义,还把 &amp; 变成了 &AMP;——过滤器的顺序会改变「是否 safe」。", t=tl(L('basic')), kv=KV([['转义五个字符', '< > & \" \\\'']], ['转义五个字符'])),
    step("HTML 转义不是万能的:<a href=\"{{ url }}\"> 里 url='javascript:alert(1)' 被原样输出(不拦截协议,要自己校验);<script>var n = \"{{ name }}\"</script> 里 HTML 转义把 \" 变成 &quot;,在 JS 字符串里并不安全;escapejs 转成 \\u0022 之类;推荐 json_script,输出带 id 的 application/json 块,< > & 都被转成 \\u003C 等。", t=tl(L('context')), mark=[0, 1], kv=KV([['上下文不同', 'HTML 转义 ≠ JS / URL 安全'], ['推荐', 'json_script']], ['推荐'])),
    step("属性引号:<input value={{ v }}>(没加引号)输入 'x onmouseover=alert(1)' 后空格截断属性,新增了事件处理器;单引号属性里 ' 被转成 &#x27;,得到 value='&#x27; onclick=&#x27;x' 是安全的。规则:永远给属性值加引号。", t=tl(L('attr')), mark=[0], done=[1], kv=KV([['不加引号', '空格即可截断']], ['不加引号'])),
    step("在 Python 里拼 HTML:format_html('<p>{}</p>', u) 会转义参数(<p>&lt;img …&gt;</p>);mark_safe('<p>' + u + '</p>') 则把用户输入原样标成安全,注入的 <img onerror=…> 完整输出;escape(u) 只转义。凡是往 mark_safe 里拼用户数据的,都是 XSS。", t=tl(L('py')), mark=[1], done=[0, 2], kv=KV([['format_html', '安全'], ['mark_safe + 拼接', 'XSS']], ['mark_safe + 拼接'])),
    step("其它位置:模板里的字面量 {{ \"<i>lit</i>\" }} 不转义(是你写的);join 对列表元素转义;linebreaksbr 转义内容、只把换行换成 <br>;urlize 转链接并转义(本例 <x> 被转义在链接之外)。", t=tl(L('others')), kv=KV([['模板字面量', '视为你写的,不转义']], ['模板字面量'])),
]
A = dict(
    n=84, series='django', tags='Django,模板,自动转义,XSS,真实验证,动画演示',
    desc='实测 Django 模板自动转义:五个字符的转义结果;safe / mark_safe / autoescape off;safe 之后接 upper 会再次被转义;href=javascript: 不会被拦截、<script> 里的变量需要 json_script;不加引号的属性可被截断;format_html 安全而 mark_safe + 拼接是 XSS。',
    lead='自动转义防住了多少?它防不住什么?这篇不讲原理,直接用一组「攻击字符串」喂给不同的上下文,看输出。',
    facts=[('5 个字符', '< > & " \' 分别转成 &lt; &gt; &amp; &quot; &#x27;'), ('不拦协议', 'href="{{ url }}" 遇到 javascript:alert(1) 原样输出,要自己校验协议'), ('mark_safe + 拼接', '把用户输入拼进 mark_safe 就是 XSS;format_html 才会转义参数')],
    body=[
        sec('转义与 safe', '', term('', blk('d84', 1)), '<p><code>safe</code> 是给字符串打「已经安全」的标记,不是「把它变安全」。</p>'),
        sec('上下文', '', term('', blk('d84', 2)), '<p>自动转义是针对 HTML 文本上下文的。属性、URL、<code>&lt;script&gt;</code>、CSS 各有各的转义规则:URL 要校验协议,JS 要用 <code>json_script</code>(或 <code>escapejs</code>)。</p>'),
        sec('属性引号', '', term('', blk('d84', 3)), '<p>Django 转义了单引号(<code>&amp;#x27;</code>),所以带引号的属性是安全的;没引号的属性靠空格就能破坏。</p>'),
        sec('在 Python 里拼 HTML', '', term('', blk('d84', 4)), '<p>凡是要产出 HTML 的 Python 代码用 <code>format_html</code>、<code>format_html_join</code>,不要手工拼字符串再 <code>mark_safe</code>。</p>'),
        sec('几个易混的过滤器', '', term('', blk('d84', 5)), '<p>这些是常见过滤器在自动转义下的行为。</p>'),
        sec('分步演示:转义与上下文', '', demo('自动转义', [('t', 'term', '实测输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。用 engines["django"].from_string 渲染;攻击字符串仅用于测试转义输出,不涉及真实站点', '没有验证:浏览器里实际执行效果(这里只看输出的 HTML 文本)、CSP 对内联脚本的影响、CSS 上下文、Jinja2 后端的转义规则、custom 过滤器返回 safe 的规则(第 85 篇)'],
)
