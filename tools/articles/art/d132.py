from lib import *
R = J('d132'); lat = R['lat']; col = R['collect']; wn = R['wn']; mo = R['manifest_ok']
def S(k): return [l for l in out('d132').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("DEBUG=False、没有 collectstatic、没有任何静态文件服务:GET /static/app.css → 404。DEBUG=False 时 Django 自己不提供静态文件(runserver 也一样,第 129 篇)。", t=tl(S(1)), mark=[0], kv=KV([['Django 自己', 'DEBUG=False 不提供 /static/']], ['Django 自己'])),
    step(f"python manage.py collectstatic(INSTALLED_APPS 里有 admin):复制了 {col['n']} 个文件到 STATIC_ROOT,其中自己的 app.css、img.png 在根目录,admin 的在 admin/ 子目录下。不改文件再运行一次:0 个文件被复制。", t=tl(S(2)), done=[0, 1, 2], kv=KV([['collectstatic', f"{col['n']} 个文件"], ['再次运行', '0 个']], ['collectstatic'])),
    step(f"collectstatic 之后只靠 gunicorn 仍然 404;加上 WhiteNoiseMiddleware 才是 200,响应头 Cache-Control: {wn['cc']}(没哈希的文件缓存 60 秒),并带 Last-Modified。", t=tl(S(3)), mark=[0], done=[1], kv=KV([['collectstatic', '只负责收集,不负责提供'], ['WhiteNoise', '负责提供']], ['WhiteNoise'])),
    step(f"ManifestStaticFilesStorage:没有 collectstatic 时页面 500,模板渲染抛 ValueError: Missing staticfiles manifest entry for 'app.css';collectstatic 之后 {{% static %}} 输出 /static/{mo['name']},该文件的 Cache-Control 是 {mo['cc']},CSS 里的 url() 也被改写成带哈希的 img.….png。", t=tl(S(4)), mark=[0, 1], done=[2, 3, 4], kv=KV([['忘了 collectstatic', '页面 500'], ['哈希文件', 'immutable 长缓存']], ['忘了 collectstatic'])),
    step(f"WhiteNoise 提供静态文件与 Django 视图用 FileResponse 读同一个文件,200 个串行请求的中位延迟:WhiteNoise {lat['wn']:.3f} ms、FileResponse 视图 {lat['dyn']:.3f} ms——这个测法下没有可见差别(没有测并发与大文件)。", t=tl(S(5)), b=bars([['WhiteNoise', lat['wn'], f"{lat['wn']:.3f} ms"], ['FileResponse 视图', lat['dyn'], f"{lat['dyn']:.3f} ms"]], 0.5, done=[0, 1]), kv=KV([['WhiteNoise 的价值', '缓存头与压缩,不是更快(本测法)']], ['WhiteNoise 的价值'])),
]
A = dict(
    n=132, series='django', tags='Django,静态文件,collectstatic,WhiteNoise,部署,真实验证,动画演示',
    desc=f'静态文件上线:DEBUG=False 时 /static/ 是 404;collectstatic 复制 {col["n"]} 个文件(含 admin)但不提供服务;WhiteNoise 才提供({wn["cc"]});Manifest 存储忘了 collectstatic 会让页面 500,收集后文件名带哈希并长期缓存。',
    lead='开发时静态文件「自己就能用」,上线后就不行了。这篇用真实的 gunicorn 把整个链条走一遍:谁提供文件、collectstatic 做了什么、WhiteNoise 加了什么、用了 Manifest 存储后忘了收集会怎样。',
    facts=[('404', 'DEBUG=False 时 Django 不提供 /static/'), (f'{col["n"]} 个文件', 'collectstatic 的复制数量(含 admin 的静态文件)'), ('忘了 collectstatic', 'Manifest 存储下 {% static %} 抛 ValueError,页面 500')],
    body=[
        sec('Django 自己不提供', '', term('', blk('d132', 1))),
        sec('collectstatic', '', term('', blk('d132', 2)), '<p><code>collectstatic</code> 只是把各处的静态文件收集到 <code>STATIC_ROOT</code>,第二次运行只复制有变化的文件。</p>'),
        sec('需要有人来提供', '', term('', blk('d132', 3)), '<p>可以是 nginx、CDN,也可以是 WhiteNoise(这里用的方案)。我机器上没有 nginx,所以没有测 nginx 的配置。</p>'),
        sec('Manifest 存储', '', term('', blk('d132', 4))),
        sec('性能', '', term('', blk('d132', 5)), '<p>别指望 WhiteNoise 比 Django 视图快很多;它的价值是正确的缓存头、压缩与不用改代码。这里只测了单个小文件的串行请求。</p>'),
        sec('分步演示', '', demo('静态文件上线', [('t', 'term', '输出'), ('b', 'bars', '延迟'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。gunicorn 单 worker;WhiteNoise 6.12.0;一个自己写的 app.css(约 2.8 KB)与 admin 的静态文件', '没有验证:nginx / CDN 的配置、WhiteNoise 的压缩文件(gzip / brotli)与 Content-Encoding、大文件、并发下的吞吐、STATIC_URL 带域名(CDN)时的写法、容器里 collectstatic 放在构建阶段还是启动阶段'],
)
