from lib import *
R = J('d121')
def S(k): return [l for l in out('d121').split('== ')[k].splitlines()[1:] if l.strip()]
c1, c2 = R['check']
steps = [
    step("只启用 SecurityMiddleware 和 XFrameOptionsMiddleware、不改任何安全设置,响应头已经有:X-Content-Type-Options: nosniff、Referrer-Policy: same-origin、Cross-Origin-Opener-Policy: same-origin、X-Frame-Options: DENY(这一条来自 XFrameOptionsMiddleware);没有 Strict-Transport-Security,也没有 Content-Security-Policy。", t=tl(S(1)), done=[0, 1, 2, 3], mark=[4, 5], kv=KV([['默认就有', 'nosniff / Referrer-Policy / COOP / X-Frame-Options'], ['默认没有', 'HSTS / CSP']], ['默认没有'])),
    step("HSTS 要主动开:SECURE_HSTS_SECONDS=31536000 加 include_subdomains 与 preload,HTTPS 请求的响应头是「max-age=31536000; includeSubDomains; preload」;同一个设置下的 http 请求没有这个头(HSTS 只该在 HTTPS 响应上发)。", t=tl(S(2)), done=[0], mark=[1], kv=KV([['HTTPS 响应', '带 HSTS'], ['HTTP 响应', '不带']], ['HTTPS 响应'])),
    step("SECURE_SSL_REDIRECT=True:http 请求得到 301,Location 是 https://localhost/。SECURE_REDIRECT_EXEMPT=[r'^healthz/$'] 里的路径不会被重定向(这里 /healthz/ 没有路由,所以是 404,而不是 301)。", t=tl(S(3)), kv=KV([['http', '301 → https'], ['豁免路径', '不重定向']], ['http'])),
    step(f"manage.py check --deploy:DEBUG=False、ALLOWED_HOSTS 已设,其它保持实验默认时 {len(c1)} 条警告({'、'.join(x.replace('security.', '') for x in c1)}):没设 HSTS、没开 SSL 重定向、密钥太短、没有 CSRF 中间件。把密钥换长、开 HSTS / 重定向 / 安全 cookie 后只剩 {len(c2)} 条({'、'.join(x.replace('security.', '') for x in c2)}:我的最小中间件列表里确实没有 CsrfViewMiddleware)。", t=tl(S(4)[:2]), b=bars([['默认警告数', len(c1), str(len(c1))], ['加固后警告数', len(c2), str(len(c2))]], 5, mark=[0], done=[1]), kv=KV([['命令', 'check --deploy']], ['命令'])),
    step("Django 6 内置了 CSP 中间件:加入 django.middleware.csp.ContentSecurityPolicyMiddleware,SECURE_CSP 生成 Content-Security-Policy(default-src 'self'; frame-ancestors 'none'),SECURE_CSP_REPORT_ONLY 生成 Content-Security-Policy-Report-Only(default-src 'self'; img-src https:),后者只上报不拦截。", t=tl(S(5)), done=[5, 6], kv=KV([['SECURE_CSP', '执行策略'], ['SECURE_CSP_REPORT_ONLY', '只上报']], ['SECURE_CSP'])),
]
A = dict(
    n=121, series='django', tags='Django,安全,SecurityMiddleware,HSTS,CSP,真实验证,动画演示',
    desc=f'SecurityMiddleware 与 XFrameOptionsMiddleware 默认发出 nosniff、Referrer-Policy: same-origin、COOP: same-origin、X-Frame-Options: DENY;HSTS / SSL 重定向要手动开;check --deploy 默认 {len(c1)} 条警告、加固后 {len(c2)} 条;Django 6 内置 CSP 中间件。',
    lead='Django 的安全响应头有多少是默认就发的?哪些要自己打开?这篇用 Client 直接看响应头,再用 manage.py check --deploy 给一个最小项目「体检」,最后试一下 Django 6 新增的 CSP 中间件。',
    facts=[('4 个默认头', 'nosniff、Referrer-Policy、COOP、X-Frame-Options 无需任何设置就有'), ('HSTS 与 CSP 默认没有', '要分别配置 SECURE_HSTS_SECONDS 与 SECURE_CSP'), (f'{len(c1)} → {len(c2)}', 'check --deploy 的警告条数:实验默认设置 → 加固后')],
    body=[
        sec('默认的响应头', '', term('', blk('d121', 1)), '<p>注意 <code>X-Frame-Options</code> 来自 <code>XFrameOptionsMiddleware</code>,不是 <code>SecurityMiddleware</code>;两个都要在 <code>MIDDLEWARE</code> 里。</p>'),
        sec('HSTS', '', term('', blk('d121', 2)), '<p>HSTS 告诉浏览器「以后只用 HTTPS 访问这个域名」,只在 HTTPS 响应上发才有意义。浏览器收到后的行为发生在浏览器里,本文没有验证。开 <code>preload</code> 之前要确认所有子域名都能走 HTTPS,这是设计上的提醒,本文没有做实验。</p>'),
        sec('SSL 重定向', '', term('', blk('d121', 3))),
        sec('check --deploy', '', term('', blk('d121', 4)), '<p>这个命令只检查设置,不检查你的服务器配置。加固后剩下的 W003 是因为我的最小中间件列表里没有 <code>CsrfViewMiddleware</code>,真实项目里不会出现。</p>'),
        sec('内置 CSP', '', term('', blk('d121', 5)), '<p>Django 6 之前要靠第三方包(django-csp 等)。CSP 策略写错会拦掉页面自己的脚本和样式,所以先用 <code>SECURE_CSP_REPORT_ONLY</code> 观察,本文只验证了响应头的生成,没有验证浏览器的拦截与上报。</p>'),
        sec('分步演示', '', demo('安全响应头', [('t', 'term', '输出'), ('b', 'bars', '警告数'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。django.test.Client 请求最小项目;secure=True 模拟 HTTPS;check --deploy 用 DEBUG=False、ALLOWED_HOSTS=["example.com"]', '没有验证:浏览器里对 HSTS / CSP 的实际处理、CSP 的 nonce 用法、Permissions-Policy 之类 Django 没有内置的头、反向代理对响应头的改写、SECURE_CROSS_ORIGIN_OPENER_POLICY 的其它取值'],
)
