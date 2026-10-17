from lib import *
S = SS('f123')
steps = [
    step("实验设置:同一个 Flask 页面,9 种不同的输出位置,每种用一个攻击载荷(参数 q),在真实的无头 Chrome 里加载,页面末尾的脚本检查 window.__x 有没有被置位(攻击载荷里的代码会把它置 1)。每一步先看服务端输出的 HTML,再看浏览器里是否真的执行。", t=tl(S(1)), done=lidx(S(1), '同一个 Flask 页面'), kv=KV([['判定', 'window.__x 被置位 = 脚本执行了']], ['判定'])),
    step("正文里 {{ q }}:Jinja 自动转义,<script> 变成 &lt;script&gt;,浏览器里没有执行。正文里 {{ q|safe }}:原样输出 <script>window.__x=1</script>,执行了。|safe 就是告诉模板「这段不用转义」,对用户输入用它就是主动关掉防护。", t=tl(S(1)), done=lidx(S(1), '正文里 {{ q }}'), mark=lidx(S(1), 'q|safe'), kv=KV([['{{ q }}', '自动转义,安全'], ['{{ q|safe }}', '原样输出,执行']], ['{{ q|safe }}'])),
    step("属性位置:不加引号的 <input value={{ q }}>,载荷 x onfocus=window.__x=1 autofocus 输出成 <input value=x onfocus=window.__x=1 autofocus>(空格不会被转义),执行了;属性加引号 value=\"{{ q }}\" 时,同类载荷里的引号被转义成 &#34;,留在属性值里,没有执行。属性值永远要加引号。", t=tl(S(1)), mark=lidx(S(1), '属性不加引号'), done=lidx(S(1), '属性加引号'), kv=KV([['不加引号', '空格就能注入新属性'], ['加引号', '引号被转义,安全']], ['不加引号'])),
    step("脚本里的位置:var name = \"{{ q }}\" 载荷 \";window.__x=1;// 输出成 \"&#34;;window.__x=1;//\"(引号被转成 HTML 实体,脚本里不会被当作引号),没有执行;但 var n = {{ q }}(没有引号)载荷 1;window.__x=1 原样输出成 var n = 1;window.__x=1;,执行了——HTML 转义对「没有引号的 JS 上下文」不起作用。正确做法是 {{ q|tojson }}:输出成带引号的 JS 字符串 \"1;window.__x=1\",没有执行。", t=tl(S(1)), mark=lidx(S(1), '脚本里直接'), done=lidx(S(1), '脚本里的字符串', 'tojson'), kv=KV([['JS 上下文', 'HTML 转义不够用'], ['|tojson', '输出合法的 JS 字面量']], ['|tojson'])),
    step("URL 位置:<a href=\"{{ q }}\">(页面自动点击这个链接)载荷 javascript:window.__x=1 输出成 href=\"javascript:window.__x=1\",点击后执行了——自动转义不检查 URL 协议。用户提供的链接要校验协议白名单(只允许 http、https)。", t=tl(S(1)), mark=lidx(S(1), 'href='), kv=KV([['href', '转义不拦 javascript:'], ['对策', '协议白名单']], ['href'])),
    step("Markup 的误用:Markup('<b>' + q + '</b>') 先拼接再标记为安全,载荷 <img src=x onerror=window.__x=1> 原样进了页面,onerror 执行了。Markup 只该用在自己写的、确定安全的 HTML 上;要拼用户输入,用 Markup('<b>%s</b>') % q(这样 q 会被转义)或 markupsafe.escape(q)(这个写法本篇没有验证)。", t=tl(S(1)), mark=lidx(S(1), 'Markup'), kv=KV([['Markup(拼接后的字符串)', '把用户输入标记成安全,执行'], ['原则', '只对自己写的 HTML 用 Markup']], ['Markup(拼接后的字符串)'])),
]
A = mkartf('f123', 123, 'Flask,XSS,Jinja2,自动转义,tojson,Chrome,真实验证,动画演示',
    '在真实的 Chrome 里验证 Flask/Jinja2 的 XSS 防护:自动转义挡住正文里的 script、|safe 与 Markup 误用让攻击执行、不加引号的属性被注入、JS 里没有引号的位置 HTML 转义无效而 |tojson 安全、href 里的 javascript: 协议不被转义拦截。',
    'Jinja2 的自动转义到底保护哪些位置?哪些位置它不管?|safe、Markup、属性不加引号、JS 上下文、href 各自会怎样?这篇用 9 种输出位置的攻击载荷,在真实的 Chrome 里逐个看脚本到底有没有执行。',
    [('9 种', '实验的输出位置,其中 5 种被攻击成功'), ('|tojson', 'JS 上下文里唯一安全的输出方式'), ('javascript:', '自动转义不会拦截的 URL 协议')],
    [('9 种输出位置', '<p>上一篇:<a href="flask-csrf-protection.html">CSRF 防护</a>;下一篇:<a href="flask-sql-injection.html">SQL Injection 与参数化查询</a>。</p><p>浏览器是本机的 Google Chrome 无头模式。「脚本是否执行」的判断是载荷里把 window.__x 置位、页面末尾读取它,没有弹窗。</p>')],
    steps, [ENV_F + '。本机 Google Chrome(无头模式)、MarkupSafe', '没有验证:CSP 响应头对这些攻击的缓解效果(见第 133 篇)、DOM 型 XSS(前端 JS 里 innerHTML)、富文本清洗库(bleach 或 nh3)的效果、模板之外的响应(如直接返回字符串的视图的 Content-Type 与 XSS)、Markdown 渲染后的 XSS'], 'XSS 防护', panels=[('t', 'term', '实验输出'), ('kv', 'kv', '要点')])
