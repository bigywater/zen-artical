from lib import *
S = SS('f20')
R = J('f20'); c = R['cost']
steps = [
    step("规则 /projects/(以斜杠结尾)、/about(不以斜杠结尾)的实测:GET /projects/ → 200;GET /projects → 308,Location 是 http://localhost/projects/;GET /about → 200;GET /about/ → 404(不会自动去掉斜杠)。设了 strict_slashes=False 的 /loose 与 /loose2/:带不带斜杠都是 200,不重定向。", t=tl(S(1)), done=lidx(S(1), 'GET /projects/ ', 'GET /about  ', 'GET /loose '), mark=lidx(S(1), 'GET /projects  ', 'GET /about/'), kv=KV([['/projects/ 的规则收到 /projects', '308 → /projects/'], ['/about 的规则收到 /about/', '404'], ['strict_slashes=False', '都 200']], ['/about 的规则收到 /about/'])),
    step("对规则 /submit/ 发 POST /submit:返回 308,Location 是 http://localhost/submit/;308 要求保留请求方法与请求体,follow_redirects=True 之后得到 200「submitted」,重定向历史是 [(308, 'POST')] —— 没有被改成 GET。", t=tl(S(2)), done=lidx(S(2), 'follow_redirects=True'), mark=lidx(S(2), 'POST /submit'), kv=KV([['POST /submit', '308'], ['跟随之后', 'POST 保持为 POST,200 submitted']], ['跟随之后'])),
    step("Location 头是绝对 URL:对 http://example.test:8080/projects 发请求,Location 是 http://example.test:8080/projects/(用的是请求的 Host)。响应类的 autocorrect_location_header 是 False,说明这个绝对 URL 是路由重定向自己生成的,不是 Response 补全的。", t=tl(S(3)), mark=lidx(S(3), 'Location'), kv=KV([['Location', 'http://example.test:8080/projects/'], ['autocorrect_location_header', 'False']], ['Location'])),
    step("url_for 按规则里写的形式生成:projects → /projects/、about → /about、loose → /loose(规则怎么写,链接就怎么生成)。", t=tl(S(4)), done=lidx(S(4), 'url_for 的结果'), kv=KV([['projects', '/projects/'], ['about', '/about'], ['loose', '/loose']], ['projects'])),
    step("全局设置 url_map.strict_slashes = False 之后,/projects 与 /projects/、/about 与 /about/ 都返回 200,没有重定向。如果同时注册 /x 与 /x/ 两条规则,两个 URL 各自命中自己的端点:/x → 200 no-slash,/x/ → 200 with-slash。", t=tl(S(5)), done=lidx(S(5), 'strict_slashes = False', '同时注册 /x 与 /x/'), kv=KV([['strict_slashes = False', '四个 URL 都 200'], ['同时注册 /x 与 /x/', '各自命中']], ['strict_slashes = False'])),
    step(f"一个多余的重定向就是多一次往返:test client 里直接访问 /projects/ 每次 {c[0]:.1f} µs;访问 /projects(先 308,跟随后再请求)是 {c[1]:.1f} µs,约 {c[1] / c[0]:.1f} 倍。真实网络里还要加上多一次网络往返。所以链接里要用 url_for 生成规范形式。", t=tl(S(6)), b=bars([['/projects/ 直接访问', c[0], f'{c[0]:.1f} µs'], ['/projects(308 后跟随)', c[1], f'{c[1]:.1f} µs']], c[1], done=[0, 1]), kv=KV([['直接访问', f'{c[0]:.1f} µs'], ['经过 308', f'{c[1]:.1f} µs'], ['倍数', f'≈{c[1] / c[0]:.1f}']], ['倍数'])),
]
A = mkartf('f20', 20, 'Flask,尾部斜杠,重定向,strict_slashes,真实验证,动画演示',
    f'实测路由尾部斜杠:规则以 / 结尾时不带斜杠访问得到 308 重定向到带斜杠的形式,规则不带斜杠时带斜杠访问是 404;POST 的 308 保留方法;Location 是绝对 URL;strict_slashes=False 与全局设置;多一次重定向在 test client 里是直接访问的 {c[1] / c[0]:.1f} 倍。',
    '/projects 与 /projects/ 到底是不是同一个 URL?访问另一种形式会怎样?POST 会不会丢?这篇用两个规则和 308 重定向把规则讲清楚。',
    [('308', '不带斜杠访问 /projects/ 规则时的状态码'), ('404', '带斜杠访问 /about 规则时的状态码'), (f'{c[1] / c[0]:.1f}×', '经过一次 308 重定向后的耗时倍数(test client)')],
    [('带不带斜杠', '<p>上一篇:<a href="flask-custom-url-converter.html">自定义 URL Converter</a>;下一篇:<a href="flask-url-for.html">url_for() 如何反向生成 URL</a>。</p>'), ('308 与 POST', None), ('Location 头', None), ('url_for', None), ('strict_slashes', None), ('重定向的代价', None)],
    steps, [ENV_F, '没有验证:反向代理(Nginx)在 Host 头不同时 Location 的内容(见第 175 篇 ProxyFix)、浏览器对 308 缓存的行为、旧版本 Werkzeug 中 301 的表现、merge_slashes 与尾部斜杠同时发生时的重定向次数'], '尾部斜杠')
