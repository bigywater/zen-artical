from lib import *
S = SS('f171')
R = J('f171'); b = R['bench']; k = list(b); dv, nt, gs, gt = [b[x] for x in k]
steps = [
    step("开发服务器启动时自己打印警告:「WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.」——官方明确说它不是为生产设计的。", t=tl(S(1)), done=lidx(S(1), 'WARNING'), kv=KV([['flask run', '启动即警告,不用于生产']], ['flask run'])),
    step(f"吞吐与并发(ApacheBench,32 并发,本机,每项测一次,只看相对关系):轻量接口 /hello:flask run 默认多线程 {dv[0]:.0f} 请求/秒、gunicorn sync×4 {gs[0]:.0f}、gunicorn gthread 2×8 {gt[0]:.0f},差距不大(开发服务器不是「慢」到不能用);flask run --without-threads 只有 {nt[0]:.0f} 请求/秒、p99 {nt[1]} ms。每个请求等 0.5 秒的 /wait(64 个请求):开发服务器多线程 {dv[3]:.1f} 秒(每个请求一个线程,不设上限)、gunicorn gthread 2×8 {gt[3]:.1f} 秒、sync×4 {gs[3]:.1f} 秒、单线程开发服务器 {nt[3]:.1f} 秒(完全串行)。区别主要不在速度,而在稳定性与安全性:没有对并发线程数、慢客户端、请求头大小等的限制,也没有进程管理、优雅重启与健康检查支持。", b=bars([['flask run 多线程', dv[3], f'{dv[3]:.1f} s'], ['gunicorn gthread 2×8', gt[3], f'{gt[3]:.1f} s'], ['gunicorn sync×4', gs[3], f'{gs[3]:.1f} s'], ['flask run 单线程', nt[3], f'{nt[3]:.0f} s']], nt[3], mark=[3], done=[0, 1, 2]), t=tl(S(2)), done=lidx(S(2), 'gunicorn', '开发服务器,默认多线程'), mark=lidx(S(2), 'without-threads'), kv=KV([['/hello 请求/秒', f'{dv[0]:.0f} / {gs[0]:.0f} / {gt[0]:.0f}(dev / sync×4 / gthread)'], ['/wait 64 个请求', f'{dv[3]:.1f} / {gs[3]:.1f} / {gt[3]:.1f} 秒']], ['/hello 请求/秒'])),
    step(f"自动重载(flask run --debug):改动代码文件之后,约 {R['reload'][2]:.1f} 秒内请求就得到新的内容('hi' → 'hi v2'),重载器重启了进程;gunicorn(没有 --reload)改了文件 2 秒之后仍然是旧内容('hi')——生产服务器不会监视文件。部署新代码要靠重启或发信号(第 172、180 篇)。", t=tl(S(3)), done=lidx(S(3), '改文件之前', 'gunicorn'), kv=KV([['flask run --debug', '改文件自动重启'], ['gunicorn', '不会自动重载']], ['gunicorn'])),
    step("进程模型:开发服务器是一个进程(每个请求一个线程),gunicorn 配 4 个 sync worker 是 5 个进程(1 个 master 加 4 个 worker)。进程模型决定了能不能利用多核、一个 worker 崩了会怎样、怎么平滑重启。", t=tl(S(4)), done=lidx(S(4), 'flask run', 'gunicorn'), kv=KV([['开发服务器', '1 个进程'], ['gunicorn sync×4', '1 master + 4 worker']], ['gunicorn sync×4'])),
]
A = mkartf('f171', 171, 'Flask,开发服务器,gunicorn,生产部署,真实验证,动画演示',
    f'实测 Flask 开发服务器与生产服务器:启动即打印不能用于生产的警告;轻量接口吞吐差距不大({dv[0]:.0f} 对 {gs[0]:.0f} 请求/秒)而单线程模式只有 {nt[0]:.0f};64 个各等 0.5 秒的请求在多线程开发服务器 {dv[3]:.1f} 秒、单线程 {nt[3]:.0f} 秒;自动重载与进程模型的差别。',
    'flask run 为什么不能用在生产?它真的慢吗?和 gunicorn 差在哪?这篇用真实的压测把速度、并发、重载与进程模型逐项对比,答案和「它慢所以不能用」可能不一样。',
    [(f'{dv[0]:.0f} vs {gs[0]:.0f}', '轻量接口的请求/秒:开发服务器与 gunicorn sync×4'), (f'{nt[3]:.0f} 秒', '--without-threads 的开发服务器处理 64 个各等 0.5 秒的请求的总耗时'), ('自动重载', '开发服务器改文件会重启,gunicorn 默认不会')],
    [('启动警告', '<p>上一篇:<a href="flask-load-test-global-state.html">压测下的全局状态问题</a>;下一篇:<a href="flask-gunicorn-start.html">Gunicorn 启动 Flask</a>。</p>'), ('吞吐与并发', '<p>压测工具是系统自带的 ApacheBench,与被测服务同机运行,每个数字只测一次。</p>'), ('自动重载', None), ('进程模型', None)],
    steps, [ENV_F + '。Werkzeug 开发服务器、gunicorn、ApacheBench', '没有验证:开发服务器对恶意输入(超大请求头、慢客户端)的处理、HTTP/1.1 keep-alive 与分块传输的完整支持、TLS 终止(开发服务器的 ssl_context)、并发线程数无上限时的内存增长'], 'Flask 开发服务器与生产服务器', panels=[('t', 'term', '实验输出'), ('b', 'bars', '总耗时'), ('kv', 'kv', '要点')])
