from lib import *
R = J('d124')
def S(k): return [l for l in out('d124').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("恶意字符串 P = <script>alert(1)</script>。{{ p }} 渲染成 &lt;script&gt;…(已转义);format_html('<b>{}</b>', P) 也转义了参数。而 {{ p|safe }}、{% autoescape off %}、变量被 mark_safe 过、mark_safe('<b>' + P + '</b>') 拼接,输出里都是原样的 <script>——这四种写法关掉了保护。", t=tl(S(1)), done=[0, 4], mark=[1, 2, 3, 5], kv=KV([['安全', '{{ p }} / format_html'], ['关掉保护', '|safe / autoescape off / mark_safe']], ['关掉保护'])),
    step("属性里:title=\"{{ q }}\" 时引号被转义,onmouseover 逃不出来;但 title={{ q }}(没加引号)时,值里的空格没有被转义,多出了 onmouseover=alert(1) 属性——属性值一定要加引号。href=\"{{ u }}\" 时 javascript:alert(1) 原样保留,自动转义不处理 URL 协议;url_has_allowed_host_and_scheme 对 javascript: 和 //evil.example 返回 False。", t=tl(S(2)), mark=[1, 2], done=[0, 3, 6], kv=KV([['不加引号的属性', '可以多出新属性'], ['javascript: URL', '自动转义不拦']], ['javascript: URL'])),
    step("放进 <script>:用 |escapejs 时 < > 被转成 \\u003C \\u003E;json_script 输出的 JSON 里同样是 \\u003C…,输出里没有原样的 </script>;只靠 HTML 自动转义把值放进 JS 字符串得到 &quot;,那不是 JS 的转义方式,不要这样用。", t=tl(S(3)), done=[0, 1, 2], mark=[3], kv=KV([['放进 JS', 'escapejs / json_script'], ['不要', '只靠 HTML 转义']], ['放进 JS'])),
    step("过滤器的组合:|linebreaks、|urlize、|linebreaksbr、|truncatechars 在自动转义下输出都已转义;|striptags 把标签去掉只剩 alert(1);但 |safe 放在前面(|safe|linebreaks、|safe|truncatechars:40)就又是原样的 <script>。", t=tl(S(4)), done=[0, 1, 2, 3, 4], mark=[5, 6], kv=KV([['|safe', '让后面所有过滤器的输出都不再转义']], ['|safe'])),
]
A = dict(
    n=124, series='django', tags='Django,安全,XSS,模板,自动转义,真实验证,动画演示',
    desc='用同一个恶意字符串看模板自动转义:{{ p }}、format_html 安全;|safe、autoescape off、mark_safe 输出原样 <script>;不加引号的属性值会被插入新属性;href 里的 javascript: 不被拦截;放进 script 要用 escapejs / json_script。',
    lead='Django 模板默认对变量做 HTML 转义,大部分 XSS 就这样挡掉了。这篇不重复概念,只用同一个恶意字符串把「哪些写法安全、哪些写法悄悄关掉了保护」逐个渲染出来。',
    facts=[('默认转义', '{{ p }} 和 format_html 会转义 < > & 引号'), ('关掉保护的 4 种写法', '|safe、{% autoescape off %}、mark_safe 过的变量、mark_safe 拼接'), ('自动转义不拦 javascript:', 'href="{{ u }}" 里的 javascript:alert(1) 原样保留')],
    body=[
        sec('自动转义与关掉它的写法', '', term('', blk('d124', 1)), '<p>用户输入一旦经过 <code>mark_safe</code> 或 <code>|safe</code>,后面的模板引擎就认为它是可信的 HTML。<code>mark_safe</code> 只该用在你自己完全控制的字符串上。</p>'),
        sec('属性与 URL', '', term('', blk('d124', 2)), '<p>自动转义是针对 HTML 文本和带引号属性的。属性值不加引号、URL 里的 <code>javascript:</code> 协议都不在它的保护范围;用户提供的链接要先校验协议与主机再输出。</p>'),
        sec('放进 JavaScript', '', term('', blk('d124', 3))),
        sec('过滤器的组合', '', term('', blk('d124', 4)), '<p>官方文档对 <code>striptags</code> 有「不能当作安全清洗工具」的提醒,本文没有验证这一点,只演示了它对这个字符串的输出。</p>'),
        sec('分步演示', '', demo('模板转义', [('t', 'term', '渲染结果'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。直接用 django.template.Template 渲染字符串,只检查输出文本,没有在浏览器里执行', '没有验证:浏览器里脚本是否真的执行、CSP 对内联脚本的拦截(见第 121 篇)、富文本场景下 bleach / nh3 之类的清洗库、DOM 型 XSS、Jinja2 后端'],
)
