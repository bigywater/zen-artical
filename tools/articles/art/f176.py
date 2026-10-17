from lib import *
S = SS('f176')
R = J('f176'); hd = R['hdr']; bn = R['bench']; gz = R['gzip']; vr = R['version']; kh = list(hd)
steps = [
    step(f"Flask 自带的 static 路由返回的缓存相关响应头(46 KB 的 CSS):默认 Cache-Control: no-cache,带 ETag 与 Last-Modified,带 If-None-Match 再请求得到 304——每次都要向服务器确认一次,没变就 304(省了传输,没省往返);把 SEND_FILE_MAX_AGE_DEFAULT 设成 31536000 后变成 Cache-Control: public, max-age=31536000,浏览器一年内不再请求。", t=tl(S(1)), done=lidx(S(1), '默认', 'SEND_FILE_MAX_AGE_DEFAULT'), kv=KV([['默认', 'no-cache + ETag,每次 304 确认'], ['SEND_FILE_MAX_AGE_DEFAULT', '设了才有 max-age']], ['默认'])),
    step(f"吞吐(ApacheBench,4000 个请求、32 并发,同一个 CSS 文件,同机压测,每项一次):Flask 的 static 路由(gunicorn sync×4){bn[0]:.0f} 请求/秒;nginx 直接发同一个文件 {bn[1]:.0f} 请求/秒,约 {bn[1] / bn[0]:.1f} 倍;作为对照,经 nginx 代理到 Flask 的动态页 / 只有 {bn[2]:.0f} 请求/秒(代理多一跳,且没开上游 keep-alive)。静态文件不该占用 Python worker:每个静态请求都占一个 worker,会挤掉动态请求。", b=bars([['Flask static', bn[0], f'{bn[0]:.0f}'], ['nginx 直接发', bn[1], f'{bn[1]:.0f}']], bn[1], mark=[0], done=[1]), t=tl(S(2)), done=lidx(S(2), 'nginx 直接发静态文件'), kv=KV([['Flask static', f'{bn[0]:.0f} 请求/秒'], ['nginx 直接发', f'{bn[1]:.0f} 请求/秒']], ['nginx 直接发'])),
    step(f"nginx 的 gzip 与 expires:不带 Accept-Encoding 时 {gz[0]} 字节,Cache-Control: {gz[2]}(expires 1y);带 Accept-Encoding: gzip 的请求 {gz[1]} 字节(原来的 {gz[1] / gz[0] * 100:.1f}%),Content-Encoding: gzip。注意响应头里没有 Vary: Accept-Encoding(nginx 要加 gzip_vary on 才会发),没有它的话中间缓存可能把压缩版本发给不支持 gzip 的客户端。", t=tl(S(3)), done=lidx(S(3), '不带 Accept-Encoding', '带 Accept-Encoding'), kv=KV([['gzip', f'{gz[0]} → {gz[1]} 字节'], ['Vary', '默认没有,要 gzip_vary on']], ['gzip'])),
    step(f"缓存失效:设了一年的长缓存之后,文件内容改了,浏览器不会再来请求,用户还会看到旧的。解决办法是让 URL 随内容变:这里用内容哈希做查询参数,改之前 /static/app.css?v={vr[0].split('=')[1]},改之后 /static/app.css?v={vr[1].split('=')[1]},URL 变了,浏览器当作新资源重新下载;更彻底的做法是把哈希放进文件名(构建工具生成)。", t=tl(S(4)), done=lidx(S(4), '内容改之前'), kv=KV([['长缓存', '内容变了浏览器也不知道'], ['URL 带哈希', '内容变了 URL 就变']], ['URL 带哈希'])),
]
A = mkartf('f176', 176, 'Flask,静态文件,nginx,缓存,gzip,真实验证,动画演示',
    f'实测静态文件的生产部署:Flask 的 static 默认 Cache-Control: no-cache(每次 304 确认)、SEND_FILE_MAX_AGE_DEFAULT 设了才有 max-age;nginx 直接发文件 {bn[1]:.0f} 请求/秒对 Flask static 路由 {bn[0]:.0f};gzip 压到 {gz[1] / gz[0] * 100:.1f}% 但默认没有 Vary 头;长缓存要靠 URL 带内容哈希失效。',
    '静态文件该由谁来发?缓存头怎么设?gzip 能省多少?长缓存之后怎么更新?这篇用真实的 gunicorn 与 nginx 把每一步的响应头与吞吐量出来。',
    [(f'{bn[0]:.0f} → {bn[1]:.0f}', '同一个 CSS 的请求/秒:Flask static 路由与 nginx 直接发文件'), (f'{gz[1] / gz[0] * 100:.1f}%', '46 KB 的 CSS 经 nginx gzip 后的体积占比'), ('?v=哈希', '让长缓存的静态文件在内容变化后失效的 URL 写法')],
    [('Flask 的缓存头', '<p>上一篇:<a href="flask-proxyfix.html">ProxyFix 的作用</a>;下一篇:<a href="flask-media-production.html">媒体文件生产部署</a>。</p>'), ('吞吐', '<p>压测工具是 ApacheBench,与服务同机运行,每个数字只测一次,只看相对关系。</p>'), ('gzip 与 expires', None), ('缓存失效', None)],
    steps, [ENV_F + '。nginx 1.31.6(自己的配置、非默认端口)、gunicorn sync、ApacheBench', '没有验证:浏览器里实际的缓存命中表现、gzip_static 预压缩、brotli、CDN 的缓存行为、WhiteNoise 这类由 Python 直接发静态文件的方案、HTTP/2 下多个小文件的表现'], '静态文件生产部署')
