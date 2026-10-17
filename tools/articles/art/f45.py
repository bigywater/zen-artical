from lib import *
S = SS('f45')
R = J('f45')
steps = [
    step("Last-Modified 与 If-Modified-Since(精度是秒):响应头 Last-Modified: Thu, 01 Oct 2026 12:00:00 GMT。请求带 If-Modified-Since 等于该时间 → 304;晚 1 秒 → 304;早 1 秒 → 200;格式非法(yesterday)→ 200(被忽略)。同时有 ETag 与 Last-Modified 时 If-None-Match 优先:INM 匹配而 IMS 过期 → 304;INM 不匹配而 IMS 匹配 → 200;只有 IMS 匹配 → 304;两者都匹配 → 304。", t=tl(S(1)), done=lidx(S(1), '首次:', 'If-Modified-Since 等于', 'If-Modified-Since 晚'), mark=lidx(S(1), 'If-Modified-Since 早', '格式非法', 'INM 匹配 + IMS 过期', 'INM 不匹配 + IMS 匹配'), kv=KV([['IMS ≥ Last-Modified', '304'], ['IMS 早于 Last-Modified', '200'], ['有 ETag 时', 'If-None-Match 优先']], ['有 ETag 时'])),
    step("Cache-Control 指令的写法:r.cache_control.max_age = 600、public = True、must_revalidate = True 得到 Cache-Control: max-age=600, public, must-revalidate;no_store 与 private 得到 no-store, private;r.expires = 某个时间 得到 Expires: Thu, 01 Oct 2026 13:00:00 GMT。", t=tl(S(2)), done=lidx(S(2), 'GET /cc', 'GET /nostore'), mark=lidx(S(2), 'Expires'), kv=KV([['max_age + public + must_revalidate', 'max-age=600, public, must-revalidate'], ['no_store + private', 'no-store, private']], ['no_store + private'])),
    step("Vary:没有访问 session 的响应没有 Vary 头;读取 session(/sess-read)就会自动加上 Vary: Cookie(即使没有 Set-Cookie);写 session(/sess)有 Vary: Cookie 与 Set-Cookie。自己加的 Vary(Accept-Encoding、Accept-Language)在头里合并成 Vary: Accept-Encoding, Accept-Language。", t=tl(S(3)), done=lidx(S(3), '/nosess', '/sess-read', '/sess  '), mark=lidx(S(3), '/vary'), kv=KV([['不碰 session', '无 Vary'], ['读或写 session', 'Vary: Cookie'], ['自己 vary.add', '合并成一个头']], ['读或写 session'])),
    step("两种校验式缓存对比:Last-Modified + If-Modified-Since 的第二次请求要发给服务器,得到 304、正文 0 字节;max-age=600 的强缓存期间浏览器直接用本地副本、不发请求(这是 HTTP 规范的约定,test client 不能演示)。", t=tl(S(4)), done=lidx(S(4), 'Last-Modified + If-Modified-Since'), mark=lidx(S(4), 'max-age=600(强缓存)'), kv=KV([['Last-Modified', '每次问服务器,304'], ['max-age', '期内不发请求(规范约定)']], ['max-age'])),
    step("缓存与登录态:写了 session 的 /sess 响应有 Vary 与 Set-Cookie,但没有 Cache-Control(Flask 不会替你加)。共享缓存(CDN)可能会把带 Set-Cookie 的响应缓存下来分发给别人,个性化响应要自己加 private 或 no-store。", t=tl(S(5)), done=lidx(S(5), '/sess 的响应头'), kv=KV([['/sess 的 Cache-Control', 'None(没有)'], ['要自己加', 'private / no-store']], ['要自己加'])),
]
A = mkartf('f45', 45, 'Flask,Last-Modified,Cache-Control,缓存,Vary,真实验证,动画演示',
    '实测 Last-Modified 与 If-Modified-Since(秒级精度、非法值被忽略、If-None-Match 优先于它);Cache-Control 各指令的写法;Expires;访问 session 会自动加 Vary: Cookie;响应带登录态时要自己加 private 或 no-store。',
    '页面应该怎么设置缓存头?Last-Modified 怎么比较?Flask 什么时候会自动加 Vary?带登录态的响应会不会被 CDN 缓存?这篇逐项实测。',
    [('Vary: Cookie', '只要读取过 session,Flask 就会自动加的头'), ('秒', 'If-Modified-Since 的比较精度'), ('ETag 优先', '两个条件头同时存在时的决定者')],
    [('Last-Modified', '<p>上一篇:<a href="flask-etag-conditional-request.html">ETag 与条件请求</a>;下一篇:<a href="flask-cookie-read-write.html">Cookie 的读写过程</a>。</p>'), ('Cache-Control 与 Expires', None), ('Vary', None), ('校验式与强缓存', None), ('缓存与登录态', None)],
    steps, [ENV_F, '没有验证:浏览器的启发式缓存(没有 Cache-Control 时按 Last-Modified 估算新鲜度)、CDN 的真实行为、Age 头、stale-while-revalidate 等扩展指令、与 Nginx proxy_cache 的配合'], '缓存响应')
