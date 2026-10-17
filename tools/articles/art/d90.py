from lib import *
R = J('d90'); dv = R['dev']; hs = R['hashed']; hg = R['hashed_gz']; hb = R['hashed_br']; pl = R['plain']
steps = [
    step(f"开发服务器(runserver、DEBUG=True):staticfiles 应用直接从源目录提供 CSS(200,{dv['size']} 字节,只有 Last-Modified,没有 Cache-Control);带 If-Modified-Since 得到 {R['dev_304']} Not Modified;/media/upload.txt → {R['dev_media']}(runserver 只处理静态文件,不服务媒体文件)。", t=tl([f"/static/css/site.css → {dv['status']} 头:" + ', '.join(f"{k}={v}" for k, v in dv['headers'].items() if v), f"带 If-Modified-Since → {R['dev_304']}", f"/media/upload.txt → {R['dev_media']}"]), kv=KV([['开发', '只有 Last-Modified,无 Cache-Control']], ['开发'])),
    step(f"生产(gunicorn、DEBUG=False)且没有 WhiteNoise:GET /static/css/site.css → {R['prod_plain']}。Django 在 DEBUG=False 时不再提供静态文件——要么由 nginx 等前端服务器提供,要么用 WhiteNoise 之类。", t=tl([f"gunicorn + DEBUG=False,无 WhiteNoise:/static/css/site.css → {R['prod_plain']}"], mark=[0]), kv=KV([['DEBUG=False', 'Django 自己不服务静态文件']], ['DEBUG=False'])),
    step(f"WhiteNoise + CompressedManifestStaticFilesStorage:带哈希的文件 Cache-Control: max-age=315360000, public, immutable(约 10 年,immutable),有 ETag 与 Last-Modified,{hs['size']} 字节;不带哈希的原名文件只有 Cache-Control: max-age=60, public(1 分钟)。同一个 CSS 内容,缓存策略按「文件名是否带哈希」区分。", t=tl(['带哈希:' + ', '.join(f"{k}={v}" for k, v in hs['headers'].items() if v and k in ('cache-control', 'etag', 'content-length', 'vary')), '原名:' + ', '.join(f"{k}={v}" for k, v in pl['headers'].items() if v and k in ('cache-control', 'etag', 'content-length', 'vary'))], cur=[0], mark=[1]), kv=KV([['带哈希', '一年以上 + immutable'], ['不带哈希', '60 秒']], ['带哈希'])),
    step(f"压缩:collectstatic 时同时生成 .gz 与 .br。同一个带哈希文件,不带 Accept-Encoding → {hs['size']} 字节;Accept-Encoding: gzip → Content-Encoding: gzip,{hg['size']} 字节;Accept-Encoding: br, gzip → Content-Encoding: br,{hb['size']} 字节(响应带 Vary: Accept-Encoding)。这份重复的 CSS 压缩效果被放大了,真实 CSS 的压缩比要低得多。", b=bars([['未压缩(字节)', hs['size'], str(hs['size'])], ['gzip(字节)', hg['size'], str(hg['size'])], ['br(字节)', hb['size'], str(hb['size'])]], hs['size'] * 1.1, mark=[0], done=[1, 2]), kv=KV([['压缩', f"{hs['size']} → gzip {hg['size']} → br {hb['size']}"]], ['压缩'])),
    step(f"条件请求:带上 If-None-Match: ETag → {R['etag304']} Not Modified,响应体 0 字节,仍带 Cache-Control。媒体文件(用户上传):WhiteNoise 不服务 MEDIA_URL,/media/upload.txt → {R['media']}——用户上传的文件必须由 Web 服务器(nginx)或对象存储提供(第 133 篇)。", t=tl([f"If-None-Match → {R['etag304']}", f"/media/upload.txt → {R['media']}"]), kv=KV([['静态文件', 'WhiteNoise / nginx'], ['媒体文件', 'nginx / 对象存储,不是 Django']], ['媒体文件'])),
]
A = dict(
    n=90, series='django', tags='Django,静态文件,媒体文件,缓存,WhiteNoise,真实验证,动画演示',
    desc=f'在 runserver 与 gunicorn(有无 WhiteNoise)下看静态 / 媒体文件的响应头:开发只有 Last-Modified;DEBUG=False 无 WhiteNoise 静态文件 404;WhiteNoise 给带哈希文件 max-age=315360000, public, immutable、原名 max-age=60;gzip {hs["size"]}→{hg["size"]}、br {hb["size"]} 字节;条件请求 304;MEDIA 不被提供。',
    lead='静态文件放哪里、怎么缓存;用户上传的媒体文件又该怎么办?这篇分别在 runserver、没有 WhiteNoise 的 gunicorn、有 WhiteNoise 的 gunicorn 三种环境里请求同一批文件,直接对比响应头。',
    facts=[('immutable', 'WhiteNoise 给带哈希的文件 max-age=315360000, public, immutable;不带哈希的只有 max-age=60'), (f'{hs["size"]} → {hg["size"]} / {hb["size"]}', '同一 CSS:未压缩 → gzip / br 的字节数(重复内容的合成文件,压缩比被夸大)'), ('404', 'DEBUG=False 时 Django 不提供静态文件;WhiteNoise 也不提供 MEDIA')],
    body=[
        sec('开发环境', '', term('', blk('d90', 1)), '<p>开发服务器提供静态文件只是为了方便,它没有缓存策略、也不是为生产设计的。</p>'),
        sec('DEBUG=False 且无 WhiteNoise', '', term('', blk('d90', 2)), '<p>这是「本地好好的,上线静态文件全 404」的经典原因。</p>'),
        sec('WhiteNoise', '', term('', blk('d90', 3)), '<p>WhiteNoise 把 <code>STATIC_ROOT</code> 里的文件由 WSGI 应用自己提供,根据文件名里是否有哈希来选缓存策略。配合前面的 CDN,可以让 Django 进程不成为静态文件瓶颈。</p>'),
        sec('压缩与条件请求', '', '<p>上面的输出里同一个文件在不同 Accept-Encoding 下得到不同字节数,并且带 ETag 的条件请求回 304。压缩文件是 <code>collectstatic</code> 时预先生成的,请求时直接读,没有实时压缩的 CPU 开销。</p>'),
        sec('媒体文件怎么办', '', '<p>用户上传的文件(<code>MEDIA_ROOT</code>)不应该由 Django 进程提供:让 nginx 直接读 <code>MEDIA_ROOT</code>,或用对象存储加 CDN(本文没有测)。</p>'),
        sec('分步演示:静态与媒体的响应头', '', demo('静态与媒体缓存', [('t', 'term', '响应头'), ('b', 'bars', '字节数'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。WhiteNoise 6.12.0、brotli 1.2.0、gunicorn 26.2 单 worker;请求用 http.client', '没有验证:nginx 的静态与 X-Accel-Redirect、CDN 的行为、WhiteNoise 的 max-age 配置项(WHITENOISE_MAX_AGE)、immutable 对各浏览器的支持、私有媒体文件的鉴权下载(第 133 篇)'],
)
