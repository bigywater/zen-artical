from lib import *
S = SS('f177')
R = J('f177'); pu = R['public']; pv = R['private']; k = list(pv); rg = R['range']
steps = [
    step(f"公开的媒体文件(用户上传的头像、图片)由 nginx 的 location /media/ 直接发:GET /media/a.png → 200,Content-Type image/png,并带 X-Content-Type-Options: nosniff、Content-Security-Policy: default-src 'none'; sandbox、Cache-Control: max-age=604800(expires 7d);SVG 文件 /media/v.svg 的 Content-Type 是 image/svg+xml——SVG 可以内嵌脚本,所以这个目录统一加了 CSP sandbox 限制它;不存在的文件 → 404,目录本身(autoindex off)→ 403,不会列出文件;带 .. 绕出去的路径被 nginx 规整后落到 Flask,同样是 404。用户上传的内容要当作不可信的,在媒体目录上默认加这几个头。", t=tl(S(1)), done=lidx(S(1), 'a.png', 'v.svg'), mark=lidx(S(1), 'nope.png', '/media/ ', '../private'), kv=KV([['媒体目录', 'nginx 直接发,带 nosniff 与 CSP sandbox'], ['目录', 'autoindex off → 403']], ['媒体目录'])),
    step(f"私有文件:Flask 先检查权限,通过后返回一个 X-Accel-Redirect: /_protected/<文件>(没有正文),nginx 看到这个头就去 internal location 里找文件发出去。未登录访问 /docs/1 → {pv[k[0]][0]};ann 访问自己的 /docs/1 → {pv[k[1]][0]},内容是 ann 的报告,Content-Disposition 带着 Flask 设的中文文件名(filename*=UTF-8''…);ann 访问 bob 的 /docs/2 → {pv[k[2]][0]};bob 访问自己的 → {pv[k[3]][0]};不存在的 /docs/9 → {pv[k[4]][0]}。直接请求内部地址 /_protected/report.pdf → {R['direct_internal']}(internal 只允许 nginx 内部重定向访问,外部请求当作不存在);带 Range 的授权请求 → {rg[0]},只收到 {rg[1]!r},Content-Range {rg[2]}——断点续传也支持。权限检查留在 Flask,发文件交给 nginx。", t=tl(S(2)), done=lidx(S(2), 'ann 访问自己', 'bob 访问自己', '带 Range'), mark=lidx(S(2), '未登录', 'ann 访问 bob', '直接请求内部地址', '不存在的'), kv=KV([['权限检查', 'Flask(401 / 403 / 404)'], ['发文件', 'nginx internal location'], ['内部地址', '外部直接访问 404']], ['内部地址'])),
]
A = mkartf('f177', 177, 'Flask,媒体文件,X-Accel-Redirect,nginx,权限,真实验证,动画演示',
    '用真实的 nginx 实测媒体文件的生产部署:公开媒体目录由 nginx 直接发并加 nosniff 与 CSP sandbox(应对 SVG 内嵌脚本)、目录不列出;私有文件由 Flask 做权限检查(401、403、404)再用 X-Accel-Redirect 让 nginx 发,internal location 外部直接访问是 404,Range 与中文 Content-Disposition 都正常。',
    '用户上传的文件该由谁来发?公开与私有的媒体怎么区分?怎么既做权限检查又不占 Python worker?这篇用真实的 nginx 把两种方式的响应逐项验证(上传校验见第 126 篇,大文件见第 169 篇)。',
    [('X-Accel-Redirect', 'Flask 通过它把「发文件」交给 nginx,权限检查留在应用里'), ('404', '外部直接访问 internal location 的结果'), ('sandbox', '公开媒体目录上加的 CSP 指令,限制 SVG 等文件执行脚本')],
    [('公开媒体', '<p>上一篇:<a href="flask-static-production.html">静态文件生产部署</a>;下一篇:<a href="flask-docker-deploy.html">Docker 部署 Flask</a>。</p><p>nginx 是自己起的实例(非默认端口)。</p>'), ('私有媒体', None)],
    steps, [ENV_F + '。nginx 1.31.6(自己的配置、非默认端口)、gunicorn', '没有验证:对象存储与预签名 URL、SVG 在真实浏览器里的脚本执行与 CSP 的实际拦截、文件权限与属主、多台机器共享媒体目录(NFS)、图片缩略图的动态生成与缓存'], '媒体文件生产部署')
