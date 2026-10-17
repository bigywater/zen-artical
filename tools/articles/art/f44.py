from lib import *
S = SS('f44')
R = J('f44'); sv = R['saved']; c = R['cost']
steps = [
    step("add_etag + make_conditional:首次请求 200,正文 401 字节,ETag 是正文的 SHA-1 十六进制(带引号),与自己算的 sha1(正文) 完全相同。带 If-None-Match = 这个 ETag → 304,正文 0 字节、没有 Content-Length、仍然带 ETag;If-None-Match: \"other\" → 200 完整正文;If-None-Match: * → 304;带多个值(含正确的那个)→ 304;POST 带 If-None-Match 得到 405(路由不允许)。", t=tl(S(1)), done=lidx(S(1), '首次:', '与 sha1(正文)'), mark=lidx(S(1), 'If-None-Match = ', 'If-None-Match: "other"', 'If-None-Match: *', '带多个值'), kv=KV([['ETag', '正文的 SHA-1'], ['匹配', '304,无正文'], ['不匹配', '200,完整正文']], ['匹配'])),
    step("弱 ETag W/\"abc\":响应头里是 W/\"abc\";If-None-Match 用强 \"abc\" 或弱 W/\"abc\" 都得到 304(If-None-Match 用弱比较),不同的 \"xyz\" 得到 200。werkzeug.http 的辅助:generate_etag(b\"x\") = 11f6ad8e…(SHA-1)、quote_etag('a', weak=True) = W/\"a\"、parse_etags('W/\"a\", \"b\"') 能解析多个值。", t=tl(S(2)), done=lidx(S(2), '响应的 ETag', '强 "abc"', '弱 W/"abc"'), mark=lidx(S(2), '不同 "xyz"', 'werkzeug 的辅助'), kv=KV([['If-None-Match', '弱比较(强/弱都算匹配)'], ['generate_etag', 'SHA-1 十六进制']], ['If-None-Match'])),
    step("手写 ETag(用数据版本号或哈希):在视图里用 request.if_none_match.contains(etag) 先判断,命中就直接返回 304,不必生成响应体。GET /manual → 200 与 ETag;带这个 ETag 再请求 → 304。这样比 make_conditional 省掉生成响应体的计算。", t=tl(S(3)), done=lidx(S(3), 'GET /manual', '带 ETag 再请求'), kv=KV([['先判断后生成', '命中 → 304,不生成响应体']], ['先判断后生成'])),
    step("ETag 防止丢失更新:GET /doc 得到 ETag;第一个客户端 PUT 带 If-Match = 该 ETag → 200 updated(数据版本变成 2);第二个客户端用同一个已过期的 ETag PUT → 412 Precondition Failed(「precondition failed」)。If-Match 与 If-None-Match 相反:要求资源仍然是客户端读到的那个版本。", t=tl(S(4)), done=lidx(S(4), '第一个客户端 PUT'), mark=lidx(S(4), '第二个客户端', '数据版本现在是'), kv=KV([['第一个 PUT(ETag 当前)', '200 updated'], ['第二个 PUT(ETag 过期)', '412']], ['第二个 PUT(ETag 过期)'])),
    step(f"节省多少:1 万个整数的 JSON,200 响应正文 {sv[0]} 字节 + 头约 {sv[1]} 字节;304 正文 {sv[2]} 字节 + 头约 {sv[3]} 字节。但服务器仍然要生成响应体并算 SHA-1:test client 里 200 耗时 {c[0]:.0f} µs、304 耗时 {c[1]:.0f} µs,几乎一样 —— 节省的是网络流量,不是服务器计算(除非像上一步那样先判断)。", t=tl(S(5)), b=bars([['200 的正文', sv[0], f'{sv[0]} 字节'], ['304 的正文', max(sv[2], 0.5), f'{sv[2]} 字节']], sv[0], done=[0, 1]), kv=KV([['200 / 304 的正文', f'{sv[0]} / {sv[2]} 字节'], ['耗时 200 / 304', f'{c[0]:.0f} / {c[1]:.0f} µs']], ['耗时 200 / 304'])),
]
A = mkartf('f44', 44, 'Flask,ETag,条件请求,304,真实验证,动画演示',
    f'实测 ETag 与条件请求:add_etag 用正文 SHA-1、If-None-Match 命中返回 304 无正文;弱 ETag 的弱比较;手写 ETag 先判断后生成;If-Match 返回 412 防止丢失更新;304 省的是流量({sv[0]} 字节 → 0),不是服务器计算(200 与 304 都约 {c[0]:.0f} µs)。',
    '浏览器带来的 If-None-Match 怎么处理?ETag 怎么生成才合理?强弱 ETag 有什么区别?能不能用 ETag 防止两个人同时修改?这篇用 test client 逐个验证。',
    [('304', 'If-None-Match 命中时的状态码(正文 0 字节)'), ('412', 'If-Match 不匹配时的状态码'), (f'{sv[0]} → 0', '1 万个整数的 JSON:200 与 304 的正文字节数')],
    [('add_etag 与 304', '<p>上一篇:<a href="flask-send-file.html">send_file() 与 send_from_directory()</a>;下一篇:<a href="flask-last-modified-cache.html">Last-Modified 与缓存响应</a>。</p>'), ('弱 ETag', None), ('手写 ETag', None), ('If-Match 与丢失更新', None), ('304 省了什么', None)],
    steps, [ENV_F, '没有验证:CDN 与浏览器对 ETag 的真实处理、gzip 压缩后 ETag 是否应变成弱 ETag、分布式部署下多实例 ETag 的一致性、If-Range 与 ETag 的组合(见第 49 篇)'], 'ETag')
