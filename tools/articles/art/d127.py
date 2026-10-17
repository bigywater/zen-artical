from lib import *
R = J('d127'); tls = R['tls']
def S(k): return [l for l in out('d127').split('== ')[k].splitlines()[1:] if l.strip()]
s1, s2, s3 = S(1), S(2), S(3)
steps = [
    step("TLS 在代理处终止时,Django 只收到 http。没有配置 SECURE_PROXY_SSL_HEADER:无论代理头是什么,request.is_secure() 都是 False、scheme 是 http。", t=tl(s1[:4]), mark=[1, 2, 3], kv=KV([['未配置', 'is_secure() 永远 False']], ['未配置'])),
    step("配置 SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'):代理带 X-Forwarded-Proto: https 时 is_secure() 为 True、scheme 为 https;带 http 或没有该头时是 False。风险:Django 不知道这个头是谁发的——客户端直连 Django,或者代理不清除客户端自带的同名头,任何人都能自称 https。", t=tl(s1[4:9]), mark=[2], done=[4], kv=KV([['风险', '头可被伪造'], ['对策', '代理必须覆盖 / 清除该头,且不能直连 Django']], ['风险'])),
    step("SECURE_SSL_REDIRECT=True 放在 TLS 终止代理后面、又没配置代理头:代理总是用 http 转发给 Django,每一次都得到 301 → https://localhost/,浏览器跟过去后又回到同一个地方,永远是 301——重定向循环(这里用测试客户端重复 5 次模拟,没有真起代理)。配置了代理头、代理带上 X-Forwarded-Proto: https 之后是 200。", t=tl(s2), mark=[0, 1, 2, 3, 4], done=[6], kv=KV([['SSL_REDIRECT + 无代理头', '重定向循环'], ['配置代理头', '200']], ['SSL_REDIRECT + 无代理头'])),
    step(f"真实 TLS:gunicorn 加载自签名证书(openssl 生成),HTTPS 请求得到 200、is_secure=True,并带 Strict-Transport-Security: {tls['hsts']};对同一个 TLS 端口发明文 HTTP 得到 {R['plain']}(连接被直接断开),没有正常的 HTTP 响应。", t=tl(s3[:2]), done=[0], kv=KV([['HTTPS', '200 + HSTS 头'], ['明文 HTTP 发到 TLS 端口', R['plain']]], ['HTTPS'])),
    step("没有验证的部分:浏览器收到 HSTS 之后的行为(记住 max-age、把 http 自动升级为 https、证书错误时不允许点击继续)发生在浏览器里,本文没有测;preload 列表的提交也没有做。", t=tl(s3[2:]), kv=KV([['未验证', '浏览器侧的 HSTS 行为']], ['未验证'])),
]
A = dict(
    n=127, series='django', tags='Django,安全,HSTS,HTTPS,SECURE_PROXY_SSL_HEADER,真实验证,动画演示',
    desc='HTTPS 部署的几个坑:不配 SECURE_PROXY_SSL_HEADER 时 is_secure() 永远 False;配了之后客户端能伪造 X-Forwarded-Proto;SECURE_SSL_REDIRECT 放在 TLS 终止代理后面会重定向循环;真实 TLS 的 gunicorn 上验证了 HSTS 头。',
    lead='HSTS 只是 HTTPS 部署的一小部分。更常见的事故是:Django 不知道自己在 HTTPS 后面。这篇模拟 TLS 终止代理,把 SECURE_PROXY_SSL_HEADER 的作用、被伪造的风险、以及 SECURE_SSL_REDIRECT 造成的重定向循环跑出来,再用真实的 TLS(自签名证书)验证 HSTS 头。',
    facts=[('is_secure() = False', '不配 SECURE_PROXY_SSL_HEADER,代理后面的 Django 永远认为是 http'), ('头可被伪造', '直连 Django 时带 X-Forwarded-Proto: https 就能让 is_secure() 为 True'), ('301 循环', 'SECURE_SSL_REDIRECT + 代理始终用 http 转发 + 没配代理头')],
    body=[
        sec('Django 怎么知道请求是 HTTPS', '', term('', blk('d127', 1)), '<p><code>request.is_secure()</code> 影响很多东西:安全 cookie、CSRF 的 Origin 检查(第 123 篇)、<code>build_absolute_uri</code> 的协议、HSTS 头。</p>'),
        sec('重定向循环', '', term('', blk('d127', 2)), '<p>如果代理本身已经做了 http → https 重定向,Django 这边就不必再开 <code>SECURE_SSL_REDIRECT</code>(这是设计建议,本文没有测)。</p>'),
        sec('真实 TLS', '', term('', blk('d127', 3))),
        sec('分步演示', '', demo('HTTPS 与代理', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。代理用测试客户端加 X-Forwarded-Proto 头模拟(没有真起 nginx);TLS 部分用 gunicorn --certfile / --keyfile 与 openssl 生成的自签名证书,客户端不校验证书', '没有验证:真实反向代理(nginx / Caddy)的头处理、HSTS 在浏览器里的行为、Let’s Encrypt 证书、SECURE_SSL_HOST、SECURE_REDIRECT_EXEMPT 与健康检查的配合(见第 136 篇)'],
)
