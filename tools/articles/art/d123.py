from lib import *
R = J('d123')
def S(k): return [l for l in out('d123').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("HTTPS 请求、CSRF_TRUSTED_ORIGINS 为空:Origin 与请求的主机同源(https://app.example.com)并带令牌 → 200;Origin 是 https://evil.example → 403「Origin checking failed - … does not match any trusted origins」;协议不同(http://)、端口不同(:8443)同样 403;同源但没有令牌 → 403「CSRF token missing」。", t=tl(S(1)), done=[0], mark=[1, 2, 3, 4], kv=KV([['同源 + 令牌', '200'], ['协议 / 端口 / 域名不同', '403']], ['协议 / 端口 / 域名不同'])),
    step("前端在另一个域(https://spa.example.org)调用本站接口:CSRF_TRUSTED_ORIGINS 为空时 403;加上 ['https://spa.example.org'] 后 200,而 https://other.example.org 仍然 403。", t=tl(S(2)), mark=[0], done=[1], kv=KV([['信任列表', '精确到 scheme + 主机']], ['信任列表'])),
    step("通配符 'https://*.example.org':a.example.org、a.b.example.org 都是 200,连 https://example.org(没有子域名)也是 200;http://a.example.org(协议不同)是 403。写成不带协议的 'spa.example.org' 时 manage.py check 直接报 4_0.E001(值必须以协议开头)。", t=tl(S(3)), done=[0, 1, 2], mark=[3, 4], kv=KV([['*.example.org', '也匹配 example.org 本身'], ['必须带协议', '否则 check 报 4_0.E001']], ['*.example.org'])),
    step("请求里没有 Origin 头的 HTTPS 请求会检查 Referer:没有 Referer → 403「Referer checking failed - no Referer.」;Referer 同源 → 200;Referer 是别的站 → 403。", t=tl(S(4)), done=[1], mark=[0, 2], kv=KV([['无 Origin', '看 Referer']], ['无 Origin'])),
    step("TLS 在代理处终止时:Django 收到的是 http 请求,浏览器发的 Origin 是 https://app.example.com,没设 SECURE_PROXY_SSL_HEADER → 403(看起来不同源);设了 SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https') 并且代理带上该头 → 200。", t=tl(S(5)), mark=[0], done=[2], kv=KV([['代理后面', 'Django 必须知道原始协议']], ['代理后面'])),
]
A = dict(
    n=123, series='django', tags='Django,安全,CSRF,CSRF_TRUSTED_ORIGINS,真实验证,动画演示',
    desc="CSRF 来源检查的规则:Origin 必须与请求同源(协议、主机、端口都相同)或在 CSRF_TRUSTED_ORIGINS 里;通配符 https://*.example.org 也匹配 example.org 本身;不带协议的写法被 check 拒绝;没有 Origin 时改看 Referer;TLS 终止代理后面需要 SECURE_PROXY_SSL_HEADER。",
    lead='「CSRF verification failed. Origin checking failed」是部署 HTTPS 与前后端分离时最常见的 403。这篇把 CSRF 的来源检查拆开,每一种情形都在 enforce_csrf_checks=True 下请求一遍,并取出 Django 自己记录的失败原因。',
    facts=[('同源才放行', 'Origin 的协议、主机、端口必须与请求一致,否则要在 CSRF_TRUSTED_ORIGINS 里'), ('4_0.E001', "CSRF_TRUSTED_ORIGINS 里不带协议的值被 manage.py check 拒绝"), ('代理后面', '没配 SECURE_PROXY_SSL_HEADER 时,HTTPS 页面的 POST 会被 403')],
    body=[
        sec('同源与不同源', '', term('', blk('d123', 1)), '<p>失败原因来自 <code>django.security.csrf</code> 日志的消息,和 403 页面上展示的 reason 是同一个。</p>'),
        sec('信任另一个域', '', term('', blk('d123', 2))),
        sec('通配符与协议', '', term('', blk('d123', 3)), '<p>通配符也匹配没有子域名的 <code>https://example.org</code>,和 ALLOWED_HOSTS 的「.」写法一样宽松,用之前要想清楚。</p>'),
        sec('没有 Origin 时', '', term('', blk('d123', 4))),
        sec('反向代理后面', '', term('', blk('d123', 5)), '<p>这里是用测试客户端加请求头模拟的代理,没有真的起 nginx。<code>SECURE_PROXY_SSL_HEADER</code> 的风险(头可能被伪造)见第 127 篇。</p>'),
        sec('分步演示', '', demo('CSRF 来源检查', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。Client(enforce_csrf_checks=True);令牌先 GET 取得再放进 POST 表单字段;失败原因取自 django.security.csrf 日志', '没有验证:AJAX 用 X-CSRFToken 头、CSRF_COOKIE_DOMAIN / SAMESITE 对跨站请求的影响、浏览器实际发出的 Origin 头、带凭据的跨域请求(CORS)'],
)
