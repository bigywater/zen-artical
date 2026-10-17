from lib import *
S = SS('p53')
steps = [
    step("只用 requests 取单页应用的首页(不执行 JavaScript):状态 200,HTML 只有 136 字节,<li> 个数 0,有一个 <script src=\"/app.js\">,ul#list 里什么都没有。数据不在 HTML 里,要等 JS 去取。", t=tl(S(1)), done=lidx(S(1), '状态 200'), b=bars([['HTML 大小 字节', 136, '136'], ['<li> 个数', 0, '0']], 140, done=[0], mark=[1]), kv=KV([['requests 拿到的 HTML', '136 字节,没有商品'], ['<script src>', '/app.js'], ['数据', '页面加载后由 JS 请求']], ['数据'])),
    step("用 Chrome 的 CDP Network 事件记录页面加载:7 个请求。GET / (Document,200)、GET /app.js(Script,由解析器发起)、GET /api/config(Fetch,由脚本发起)、GET /api/products?page=1&limit=10、page=2、page=3(Fetch,都带着请求头 X-Requested-With: XMLHttpRequest)、POST /api/track(Ping,sendBeacon 发的统计请求,Content-Type: text/plain)。页面最终渲染出 25 条商品,第一条是 'Item 1 - 10.37'。真正含数据的是三个 /api/products 请求,其它是配置、脚本和统计。", t=tl(S(2)), done=lidx(S(2), '/api/products?page=1', '/api/products?page=2', '/api/products?page=3', '渲染完成'), mark=lidx(S(2), '/api/track', '/api/config'), b=bars([['总请求数', 7, '7'], ['含数据的请求', 3, '3']], 7, done=[1]), kv=KV([['含数据', '/api/products?page=1..3(Fetch)'], ['配置与统计', '/api/config、/api/track'], ['渲染结果', 'DOM 里 25 条']], ['含数据'])),
    step("直接用 requests 重放 /api/products?page=1&limit=10:什么都不带 → 401;只带 Cookie(sid=abc123)→ 403;只带 X-Requested-With: XMLHttpRequest → 401;两者都带 → 200。缺 Cookie 是 401,缺 X-Requested-With 是 403。这两样浏览器自动带,直接请求时要自己补:Cookie 来自第一次访问 / 时服务器设置的 Set-Cookie。", t=tl(S(3)), done=lidx(S(3), '两者都带:200'), mark=lidx(S(3), '什么都不带', '缺 Cookie'), kv=KV([['什么都不带', '401'], ['只带 Cookie', '403'], ['Cookie + X-Requested-With', '200']], ['Cookie + X-Requested-With'])),
    step("先访问首页拿到 cookie,再加上必需的头,直接翻页:3 次请求取到 25 条,2 ms;浏览器从打开页面到渲染完成是 63 ms(Chrome 已经启动好,时间包括加载页面、运行 JS 和同样的 3 次接口请求)。条数一致、名称一致。API 返回的字段是 id、name、price_cents、internal_sku;DOM 只显示了名称和价格(元),API 里还有页面没显示的 internal_sku='SKU-00001',价格是以分为单位的 price_cents=1037。", t=tl(S(4)), done=lidx(S(4), '3 次请求取到 25 条', '条数一致'), mark=lidx(S(4), 'DOM 里只显示了'), b=bars([['直接调用 API:ms', 2, '2'], ['浏览器渲染:ms', 63, '63']], 65, done=[0], mark=[1]), kv=KV([['API 直接翻页', '3 次请求,25 条,2 ms'], ['结果', '与 DOM 的条数、名称一致'], ['额外字段', 'internal_sku、价格以分计']], ['额外字段'])),
]
A = mkartp('p53', 53, '爬虫,单页应用,XHR,Fetch,CDP,Network,接口分析,requests,Python,真实验证,动画演示',
    '用 Chrome 的 CDP Network 事件记录一个单页应用加载时发的 7 个请求,找到真正含数据的 /api/products;直接用 requests 重放要补上 Cookie(缺了 401)和 X-Requested-With(缺了 403);3 次请求取到 25 条,2 ms,而浏览器渲染要 63 ms;API 还多返回页面没显示的字段。',
    '很多网页用 requests 拿到的 HTML 里没有数据:数据是页面加载后由 JavaScript 请求接口取来的。找到那个接口,直接请求它,往往比启动浏览器渲染便宜得多。这篇用 Chrome 的 DevTools 协议记录一个本机单页应用的请求,再逐步弄清直接重放需要什么。',
    [('136 字节', '用 requests 取单页应用首页拿到的 HTML 大小——没有任何商品'), ('3 / 7', '页面加载时发出的 7 个请求里,真正含商品数据的只有 3 个'), ('2 对 63 ms', '直接调接口翻页取 25 条 与 浏览器渲染完成 的耗时(本机回环)')],
    [('HTML 里没有数据', '<p>首页只有骨架和一个 <code>&lt;script src&gt;</code>。数据由 <code>/app.js</code> 里的 <code>fetch</code> 请求接口得到,再用 JS 写进 DOM。</p>'),
     ('用 CDP 记录请求', '<p>通过 Chrome DevTools 协议的 <code>Network</code> 事件,可以看到页面发的每个请求:方法、URL、资源类型(Document、Script、Fetch、Ping)、发起者、响应状态。本例 7 个请求里 3 个 <code>/api/products</code> 才是数据;<code>/api/config</code> 是配置,<code>/api/track</code> 是统计。再用 <code>Network.getResponseBody</code> 可以读到响应内容。</p>'),
     ('重放需要什么', '<p>直接请求接口会遇到 401(没有会话 Cookie)和 403(没有 <code>X-Requested-With</code> 头)。Cookie 来自首页响应的 <code>Set-Cookie</code>,用 <code>requests.Session</code> 先访问首页即可;必需的头可以从 CDP 记录的请求头里看出来。这个服务器是我写的,真实站点的校验可能更多。</p>'),
     ('直接翻页', '<p>三次请求取到 25 条,和 DOM 里渲染出的一致;而且接口返回的字段比页面显示的多(内部编号、以分为单位的价格)。是否应该使用这些额外字段,取决于你的数据用途和站点的使用条款——本文没有涉及。</p>')],
    steps,
    [ENV_P + '。单页应用是本机服务器上的一个小页面:/ 返回骨架并设置 Cookie,/app.js 里用 fetch 先取 /api/config,再翻页取 /api/products(需要 Cookie 与 X-Requested-With 头),最后用 sendBeacon 发 /api/track;Chrome 154 通过 pcdp.py(websocket-client)的 CDP 控制,开启 Network 域记录事件,独立 user-data-dir,实验后结束该进程;requests 重放时先访问首页拿 Cookie',
     '没有验证:需要签名、时间戳、动态 token 的接口;WebSocket 或 GraphQL 接口(WebSocket 在后面单独讲);接口有速率限制或反爬时的行为;HAR 导出;CDP 里 Cookie 的 ExtraInfo 事件(这里请求头里没显示 Cookie,是 CDP 把它放在另外的事件中);请求体很大的 POST 接口;站点使用条款对直接调用接口的限制'],
    '找到数据接口')
