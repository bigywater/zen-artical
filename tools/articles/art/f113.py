from lib import *
S = SS('f113')
R = J('f113'); cs = R['cost']; hs, h3, vs, v3 = cs['哈希 ETag:200(没带头)'], cs['哈希 ETag:304'], cs['版本号 ETag:200'], cs['版本号 ETag:304']; by = R['bytes']
steps = [
    step(f"add_etag() 加 make_conditional(request):第一次 200,ETag 是正文的 SHA-1 十六进制(40 个字符),正文 {by[0]} 字节;带 If-None-Match: 同一个 ETag 再请求 → 304、正文 0 字节,ETag 头仍在;If-None-Match 是别的值 → 200 全量;If-None-Match 是列表(\"x\", ETag, \"y\")里含有它 → 304。make_conditional 只对 GET 与 HEAD 生效。", t=tl(S(1)), done=lidx(S(1), '第一次', '带 If-None-Match', '列表', 'SHA-1'), mark=lidx(S(1), '别的值'), kv=KV([['ETag', '正文哈希'], ['If-None-Match 命中', '304 + 空正文'], ['不命中', '200 全量']], ['If-None-Match 命中'])),
    step(f"哈希 ETag 要先把正文算出来才能比较:慢查询 50 ms 时,200 要 {hs[0]:.1f} ms,带正确 ETag 的 304 也要 {h3[0]:.1f} ms——只省了带宽,没省查询。版本号 ETag(\"v1\")可以先比较、命中就不查数据:304 只要 {v3[0]:.2f} ms,不命中的 200 是 {vs[0]:.1f} ms。数据变了(版本号变成 v2)后,带旧 ETag 的请求得到 200 和新 ETag \"v2\"。", b=bars([['哈希 ETag 304', h3[0], f'{h3[0]:.1f} ms'], ['版本号 ETag 304', max(v3[0], 0.3), f'{v3[0]:.2f} ms']], h3[0], mark=[0], done=[1]), t=tl(S(2)), done=lidx(S(2), '版本号 ETag:304'), mark=lidx(S(2), '哈希 ETag:304'), kv=KV([['哈希 ETag', f'304 仍要 {h3[0]:.0f} ms'], ['版本号 ETag', f'304 只要 {v3[0]:.2f} ms']], ['版本号 ETag'])),
    step("Last-Modified / If-Modified-Since:第一次 200 带 Last-Modified: Thu, 01 Jan 2026 00:00:00 GMT;带同一个时间的 If-Modified-Since → 304;带更早的时间 → 200。精度只有秒,适合有「最后修改时间」的资源。", t=tl(S(3)), done=lidx(S(3), '第一次', '同一时间'), mark=lidx(S(3), '更早'), kv=KV([['Last-Modified', '秒级精度的时间戳']], ['Last-Modified'])),
    step("弱 ETag W/\"abc\":If-None-Match 带 W/\"abc\" 与带强的 \"abc\" 都得到 304——If-None-Match 用弱比较,两种写法都认。弱 ETag 表示「语义上相同,字节可以不同」。", t=tl(S(4)), done=lidx(S(4), 'ETag =', 'If-None-Match'), kv=KV([['If-None-Match', '弱比较']], ['If-None-Match'])),
    step(f"带宽:1000 条记录的列表,200 的响应体 {by[0]} 字节,304 是 {by[1]} 字节;头部估算 200 约 142 字节、304 约 87 字节。适合大而不常变的列表,小响应省不了多少。", b=bars([['200 正文', by[0], f'{by[0]} B'], ['304 正文', 200, f'{by[1]} B']], by[0], mark=[0], done=[1]), t=tl(S(5)), done=lidx(S(5), '200 响应体'), kv=KV([['200', f'{by[0]} 字节'], ['304', f'{by[1]} 字节']], ['304'])),
]
A = mkartf('f113', 113, 'Flask,API,ETag,条件请求,304,真实验证,动画演示',
    f'实测 Flask API 的 ETag 缓存:add_etag 与 make_conditional 得到 304 与空正文、If-None-Match 列表与弱 ETag、哈希 ETag 的 304 仍要 {h3[0]:.0f} ms 而版本号 ETag 的 304 只要 {v3[0]:.2f} ms、Last-Modified 与 If-Modified-Since、48039 字节对 0 字节的带宽差别。',
    'ETag 到底省了什么?用正文哈希做 ETag 是不是真的快?If-None-Match 与 Last-Modified 怎么配合?这篇用慢查询把 304 的耗时和带宽量出来。',
    [(f'{h3[0]:.0f} → {v3[0]:.2f} ms', '同样是 304:哈希 ETag 与版本号 ETag 的耗时(慢查询 50 ms)'), (f'{by[0]} → {by[1]} 字节', '200 与 304 的响应体大小'), ('SHA-1', 'Werkzeug add_etag 对正文计算的哈希')],
    [('304 与空正文', '<p>上一篇:<a href="flask-cors-preflight.html">CORS 预检请求</a>;下一篇:<a href="flask-openapi-generation.html">OpenAPI 文档生成</a>。</p>'), ('哈希与版本号', None), ('Last-Modified', None), ('弱 ETag', None), ('带宽', None)],
    steps, [ENV_F, '没有验证:真实浏览器里的缓存行为与 Cache-Control(max-age、no-cache、must-revalidate)的交互、CDN 与 Vary 的配合、gzip 压缩对 ETag 的影响、If-Match 与 ETag 的并发控制(见第 94 篇)、分页列表整体 ETag 的失效粒度'], 'ETag API 缓存', panels=[('t', 'term', '实验输出'), ('b', 'bars', '耗时 / 大小'), ('kv', 'kv', '要点')])
