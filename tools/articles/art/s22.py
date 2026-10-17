from lib import *
S = SS('s22')
steps = [
    step("默认 COOKIES_ENABLED = 1:/login?u=alice 返回 Set-Cookie: sid=alice; Path=/,之后同一个爬虫的 /other、/me 请求自动带上 Cookie: sid=alice(登录请求本身没有 Cookie);COOKIES_ENABLED = 0 时三个请求都不带 Cookie,响应里的 Set-Cookie 也不会保存。", t=tl(S(1)), mark=lidx(S(1), 'COOKIES_ENABLED=1', 'COOKIES_ENABLED=0'), kv=KV([['默认', 'Set-Cookie 存进 jar,后续请求自动带'], ['COOKIES_ENABLED = 0', '不存、不带'], ['jar', '一个爬虫默认只有一个(键 None)']], ['默认'])),
    step("手动加 Cookie:headers={'Cookie': 'via=header'} 会被中间件覆盖(源码里 process_request 先 pop 掉 Cookie 头再按 jar 重建),服务器收到的是“无”;改用 cookies={'via': 'cookies-param'} 才行,而且这个 cookie 会存进 jar,影响之后的请求(/later 也带着 via=cookies-param)。关掉 COOKIES_ENABLED 后反过来:headers 里的 Cookie 原样发出(via=header),cookies 参数被忽略。", t=tl(S(2)), mark=lidx(S(2), '/h ', 'COOKIES_ENABLED=0'), done=lidx(S(2), '/c ', '/later'), kv=KV([['headers 里的 Cookie', '默认被覆盖(服务器收到“无”)'], ['cookies={…}', '有效,并留在 jar 里'], ['COOKIES_ENABLED = 0', 'headers 里的 Cookie 原样发出']], ['headers 里的 Cookie'])),
    step("多个 cookiejar:alice 和 bob 用 meta['cookiejar'] 各自登录;后续请求带着各自的 cookiejar 键就各带各的(/me?jar=alice 带 sid=alice,/me?jar=bob 带 sid=bob);忘了带 meta 的 /forgot、以及 response.follow 出来的 /follow 都不带任何 Cookie,因为 meta 不会自动继承,它们落到默认 jar(没有 cookie)。", t=tl(S(3)), mark=lidx(S(3), '/forgot', '/follow'), done=lidx(S(3), '/me?jar=alice', '/me?jar=bob'), kv=KV([['meta["cookiejar"] = 键', '每个键一个独立的 jar'], ['后续请求', '必须自己继续传这个 meta'], ['忘了传 / response.follow', '落到默认 jar,不带 cookie']], ['忘了传 / response.follow'])),
    step("cookie 的作用域与过期:Path=/admin 的 cookie 只发给 /admin/x,不发给 /public/x;Secure 的 cookie 在 http 协议下不发;Domain=localhost 的 cookie 对 127.0.0.1 的请求被拒绝(不发);Max-Age=1 的 cookie 立即请求带上 a=1,等 2 秒后不再带;Max-Age=0 相当于删除;HttpOnly、SameSite=Lax 不影响爬虫发送(a=1 照常带)。", t=tl(S(4)), mark=lidx(S(4), 'Path=/admin', 'Secure', 'Domain=localhost', 'Max-Age=1'), done=lidx(S(4), 'Max-Age=0', 'HttpOnly'), kv=KV([['Path', '只发给匹配路径'], ['Secure', 'http 不发'], ['Domain 不匹配', '被拒绝'], ['Max-Age', '到期不再发;0 = 删除']], ['Domain 不匹配'])),
    step("COOKIES_DEBUG = 1 时中间件在 DEBUG 日志里打印两种消息:“Received cookies from: <200 …/login?u=alice>”下面一行 Set-Cookie: sid=alice; Path=/;“Sending cookies to: <GET …/other>”下面一行 Cookie: sid=alice。调试 cookie 问题时看这两种日志最直接。", t=tl(S(5)), mark=lidx(S(5), 'Received cookies', 'Sending cookies'), kv=KV([['Received cookies from', '响应里的 Set-Cookie'], ['Sending cookies to', '请求发出的 Cookie 头'], ['级别', 'DEBUG']], ['Sending cookies to'])),
    step("meta dont_merge_cookies = True 的请求既不发送 jar 里的 cookie,也不保存响应里的 Set-Cookie:carol 的登录带了这个 meta,之后的 /me1 没有 cookie(carol 的 sid 没存);dave 的登录正常保存,/me3 带 sid=dave;/me4 带 dont_merge_cookies 又不发 cookie。", t=tl(S(6)), mark=lidx(S(6), 'login?u=carol', '/me4'), done=lidx(S(6), '/me3'), kv=KV([['dont_merge_cookies', '不发 jar 里的 cookie,也不存 Set-Cookie'], ['carol 登录', '没存,/me1 无 cookie'], ['dave 登录', '正常存,/me3 带 sid=dave']], ['dont_merge_cookies'])),
]
A = mkarts('s22', 22, 'Scrapy,CookiesMiddleware,cookiejar,Cookie,Set-Cookie,真实验证,动画演示',
    '实测 CookiesMiddleware:Set-Cookie 自动存进 jar 并带到后续请求;headers 里的 Cookie 会被覆盖,要用 cookies 参数;meta["cookiejar"] 隔离多个会话,但必须自己一路传下去;Path、Secure、Domain、Max-Age 都按规则生效;COOKIES_DEBUG 的日志;dont_merge_cookies。',
    '爬虫登录之后为什么后面的请求会自动带 cookie?手写 Cookie 头为什么没用?多个账号要怎么隔离?这篇用一个会发 Set-Cookie 的服务器,把 CookiesMiddleware 的行为一项项量出来。',
    [('被覆盖', 'headers={"Cookie": …} 在默认设置下服务器收到的结果(应该用 cookies 参数)'), ('不继承', 'response.follow 产生的请求带不带上一个请求的 cookiejar meta'), ('Max-Age=1', '等 2 秒后 cookie 不再发送')],
    [('自动保存与发送', '<p><code>process_response</code> 把 <code>Set-Cookie</code> 存进 cookie jar,<code>process_request</code> 按域名/路径等规则给请求加上 <code>Cookie</code> 头。</p>'),
     ('手写 Cookie 头', '<p>中间件在发送前会先删掉请求上已有的 <code>Cookie</code> 头再重建,所以要通过 <code>Request(cookies=…)</code> 设置,并且这些 cookie 会存进 jar,影响之后的请求。</p>'),
     ('多个 cookiejar', '<p><code>meta["cookiejar"]</code> 的值是 jar 的键,不同键互不干扰;但 meta 不会自动继承,链路上的每个请求都要继续传。</p>'),
     ('作用域', '<p>标准 cookie 规则:Path 限定路径、Secure 只在 https 发送、Domain 不匹配被拒绝、Max-Age 到期删除。</p>'),
     ('调试', '<p><code>COOKIES_DEBUG</code> 打印每个收到的 <code>Set-Cookie</code> 和发出的 <code>Cookie</code>。</p>'),
     ('单个请求排除', '<p><code>dont_merge_cookies</code> 让一个请求不参与 cookie 机制:既不发也不存。</p>')],
    steps,
    [ENV_Y + '。服务器 /login 返回 Set-Cookie,/setc 按 query 里给的完整 Set-Cookie 值设置,并记录每个请求收到的 Cookie 头;并发 1',
     '没有验证:公共后缀域名(如 .com)cookie 的拒绝规则(源码里有 tldextract 判断,本机没有真实域名可测);子域名之间的 cookie 共享;大量 cookie(超过 4 KB)的行为;cookie 值里的特殊字符编码;COOKIES_ENABLED 与重定向跨域的组合(重定向那一篇只测了 Cookie 头)'],
    'Cookie')
