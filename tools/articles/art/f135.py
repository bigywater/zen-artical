from lib import *
S = SS('f135')
R = J('f135')
steps = [
    step("实验设置:真实的客户端是本机 127.0.0.1;客户端自己在请求里写了一个假的 X-Forwarded-For: 203.0.113.9。nginx 在中间,gunicorn 不信任任何代理地址,由 Flask 这一层决定信不信 XFF。五种配置,看 Flask 最终认定的客户端地址是真的 127.0.0.1 还是被客户端写的假地址。", t=tl(S(1)), done=lidx(S(1), '实际的客户端'), kv=KV([['真实客户端', '127.0.0.1'], ['请求里的假 XFF', '203.0.113.9']], ['请求里的假 XFF'])),
    step("A:nginx 用 proxy_set_header X-Forwarded-For $remote_addr 覆盖这个头,服务端收到的 XFF 只有 '127.0.0.1'(客户端写的被丢掉了),ProxyFix(x_for=1) 之后 request.remote_addr = 127.0.0.1,正确。E:同样的 nginx 覆盖配置,没有 ProxyFix,只看 remote_addr 也是 127.0.0.1(这里 remote_addr 是 nginx 所在的地址,恰好与客户端相同,所以看不出区别)。", t=tl(S(1)), done=lidx(S(1), '[A]', '[E]'), kv=KV([['覆盖 XFF', '客户端写的被丢弃'], ['ProxyFix(x_for=1)', '取最后一层代理看到的地址']], ['覆盖 XFF'])),
    step("B:nginx 用 $proxy_add_x_forwarded_for 追加(保留客户端写的,再加上自己看到的),服务端收到 '203.0.113.9, 127.0.0.1',access_route 是 ['203.0.113.9', '127.0.0.1']。ProxyFix(x_for=1) 取最后一个——request.remote_addr = 127.0.0.1,仍然正确:x_for 的数字就是「信任几层代理」,从右往左数。", t=tl(S(1)), done=lidx(S(1), '[B]'), kv=KV([['追加', '客户端写的在左边,代理加的在右边'], ['x_for=1', '只信右边第 1 个']], ['x_for=1'])),
    step("C:同样追加,但 ProxyFix 配成 x_for=2(多信任了一层):request.remote_addr = 203.0.113.9——取到了客户端自己写的假地址。信任的层数必须等于前面真实的代理层数,多配一层就是把客户端可控的那一段当成了可信的。", t=tl(S(1)), mark=lidx(S(1), '[C]'), kv=KV([['x_for=2,实际只有 1 层代理', '取到假地址']], ['x_for=2,实际只有 1 层代理'])),
    step("D:nginx 追加、没有 ProxyFix,代码里取 XFF 的第一个元素(很常见的写法):得到 203.0.113.9——第一个元素是客户端最先写的,最不可信;而 request.remote_addr 是 127.0.0.1(没有 ProxyFix 时就是直接连接的对端)。不要自己拆 XFF 取第一个。", t=tl(S(1)), mark=lidx(S(1), '[D]'), kv=KV([['取 XFF 第一个元素', '取到客户端自己写的'], ['正确做法', 'ProxyFix 按层数从右往左取']], ['取 XFF 第一个元素'])),
    step("不经过 nginx、直连 gunicorn 时,请求头里客户端自己写的 X-Forwarded-For: 203.0.113.9,在配了 ProxyFix(x_for=1) 的应用里 request.remote_addr 直接变成 203.0.113.9——没有可信代理却配了 ProxyFix,就等于让每个客户端自己决定自己的 IP,这会让按 IP 限流、按 IP 记审计日志全部失效(第 111 篇)。所以要保证应用只能通过代理访问(监听回环地址或防火墙限制)。", t=tl(S(2)), done=lidx(S(2), '直连'), kv=KV([['没有可信代理 + ProxyFix', '客户端自己决定自己的 IP'], ['对策', '应用只接受来自代理的连接']], ['没有可信代理 + ProxyFix'])),
]
A = mkartf('f135', 135, 'Flask,ProxyFix,X-Forwarded-For,nginx,真实验证,动画演示',
    '用真实的 nginx 与 gunicorn 实测信任代理头的配置:nginx 覆盖或追加 X-Forwarded-For、ProxyFix 的 x_for 层数、多信任一层会取到客户端伪造的地址、取 XFF 第一个元素的常见写法不可信、没有可信代理却配 ProxyFix 时客户端能决定自己的 IP。',
    'ProxyFix 的 x_for 到底该写几?nginx 的 X-Forwarded-For 用覆盖还是追加?直接取 XFF 第一个元素行不行?这篇用一个写了假 X-Forwarded-For 的请求,把五种配置下 Flask 认定的客户端地址逐个对照(防御向,只验证配置的效果)。',
    [('x_for', 'ProxyFix 信任的代理层数,从右往左数,必须等于实际的代理层数'), ('203.0.113.9', '客户端自己写的假地址,在多信任一层或直连时被 Flask 当真'), ('$remote_addr', 'nginx 覆盖 X-Forwarded-For 的写法,丢弃客户端写的内容')],
    [('五种配置的对照', '<p>上一篇:<a href="flask-https-reverse-proxy.html">HTTPS 与反向代理</a>;下一篇:<a href="flask-sync-request-model.html">Flask 同步请求模型</a>。</p><p>客户端、nginx、gunicorn 都在本机,真实客户端地址与代理看到的地址都是 127.0.0.1,所以用请求里写的假地址 203.0.113.9 来区分「被信任」与「没被信任」的取值。</p>'), ('直连时的风险', '<p>这一部分是第一个实验的补充:没有 nginx,直接连 gunicorn。</p>')],
    steps, [ENV_F + '。nginx 1.31.6(自己的配置、非默认端口)、gunicorn(--forwarded-allow-ips 不信任回环)', '没有验证:两层及以上代理(CDN 加 nginx)的真实链路、Forwarded 标准头(RFC 7239)与 X-Real-IP、云负载均衡器的 XFF 追加行为、IPv6 地址、第 129 篇限流 key 在 ProxyFix 之后的实际取值'], '信任代理头配置')
