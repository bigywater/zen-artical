from lib import *
S = SS('w92')
steps = [
    step("SNI 在 ClientHello 里是明文。抓 en0 上去 example.com 的一次 TLS 连接:第 1 个有载荷的包(客户端→服务器,1388 字节,ClientHello)里,偏移 130 处能直接找到 \"example.com\" 这串字节;后面所有包——第 2 个客户端包(146 字节)、服务器的 4 个包(1440 + 1440 + 1440 + 760 字节)、客户端 80 和 78 字节的包、服务器 544 和 39 字节的包——都找不到。整个连接里含明文 \"example.com\" 的包只有 1 个(客户端→服务器)。证书、HTTP 的 Host 头和响应都在加密记录里。所以路径上的任何设备都能读出你要访问哪个站点,即使内容是加密的。", t=tl(S(1)), mark=lidx(S(1), '第 1 个有载荷的包'), done=lidx(S(1), '第 2 个有载荷的包', '整个连接里含明文'), b=bars([['含明文 example.com 的包', 1, '1 个'], ['其余 9 个有载荷的包', 9, '9 个']], 10, mark=[0], done=[1]), kv=KV([['明文 SNI', 'ClientHello 偏移 130 处'], ['其余包', '全是密文,找不到 example.com'], ['路径上的设备', '能读出访问的站点']], ['明文 SNI'])),
    step("SNI 与 HTTP Host 头不一致会怎样(“域前置”)。TLS 里用 SNI = example.com 连上,然后在 HTTP 请求里写不同的 Host:Host: example.com → 200 OK,页面标题 Example Domain,928 字节;Host: example.org → 403 Forbidden;Host: www.iana.org → 403 Forbidden;Host: nonexistent-w92.example → 403 Forbidden。也就是说 Cloudflare 这个服务器检查了 SNI 与 Host 是否一致,不一致一律拒绝。域前置(用一个允许的 SNI 隐藏真实目标)依赖服务器不做这个检查,这里行不通。(注意我第一次跑这一节时请求格式写错,四个都得到 400,上面的结果是修正后的。)", t=tl(S(2)), mark=lidx(S(2), 'Host: example.org', 'Host: www.iana.org', 'Host: nonexistent'), done=lidx(S(2), 'Host: example.com  '), kv=KV([['SNI = Host', '200 OK'], ['SNI ≠ Host', '403 Forbidden(三种不同的 Host 都是)'], ['含义', '服务器校验了 SNI 与 Host 一致']], ['SNI ≠ Host'])),
    step("ALPN 协商。客户端提供 [h2, http/1.1] → 选定 h2;提供 [http/1.1, h2](把 http/1.1 写在前面)→ 仍然选定 h2:服务器按自己的偏好在客户端列表里挑,不是按客户端的顺序;只提供 [h2] → h2;只提供 [http/1.1] → http/1.1;提供 [h3](TCP 上不该有)或 [foo](不认识的协议)→ 选定 None,握手并没有失败,只是没有协商出应用层协议;提供 [foo, http/1.1] → 跳过不认识的,选定 http/1.1;完全不提供 ALPN → None。所以 ALPN 不匹配时,这个服务器不报错,而是继续握手、不选协议——客户端得自己决定能不能接受。", t=tl(S(3)), mark=lidx(S(3), "['http/1.1', 'h2']", "['h3']", "['foo']"), done=lidx(S(3), "['h2', 'http/1.1']", "['h2'] ", "['http/1.1'] ", "['foo', 'http/1.1']"), kv=KV([['[http/1.1, h2]', '选 h2(服务器偏好)'], ['[h3] / [foo] / 不提供', '选定 None,握手仍成功'], ['[foo, http/1.1]', '选 http/1.1']], ['[http/1.1, h2]'])),
    step("SNI 的隐私问题与 ECH(加密 ClientHello)。DNS 的 HTTPS 记录(类型 65)可以带 ech 参数,让客户端把真正的 SNI 放进加密的内层 ClientHello。查 1.1.1.1:example.com 的 HTTPS 记录参数是 alpn、ipv4hint、ipv6hint,没有 ech;cloudflare.com 同样没有 ech;www.python.org 和 github.com 根本没有 HTTPS 记录。本机 Python 的 ssl 也不支持 ECH,所以第一节看到的 SNI 仍然是明文。浏览器和服务器都支持并且 DNS 记录里发布了 ech 配置时,才能把 SNI 藏起来;今天这几个站点没有做到。", t=tl(S(4)), mark=lidx(S(4), 'example.com     :', 'cloudflare.com  :'), done=lidx(S(4), 'www.python.org', 'github.com'), kv=KV([['example.com', 'alpn、ipv4hint、ipv6hint;无 ech'], ['cloudflare.com', '同上;无 ech'], ['python.org / github.com', '没有 HTTPS 记录']], ['example.com'])),
]
A = mkartw('w92', 92, '网络协议,TLS,SNI,ALPN,ECH,域前置,真实验证,动画演示',
    '抓包确认 SNI 在 ClientHello 偏移 130 处是明文,其余 9 个包都找不到;Cloudflare 对 SNI 与 Host 不一致的请求一律 403;ALPN 服务器按自己的偏好选 h2,不匹配时握手成功但不选协议;example.com / cloudflare.com 的 HTTPS 记录没有 ech 参数。',
    '同一个 IP 上藏着成千上万个网站,TLS 靠 SNI 找到该给哪张证书,靠 ALPN 决定接着说 HTTP/1.1 还是 HTTP/2。这两个小小的扩展还各有隐私和安全的含义:SNI 是明文泄露你要访问的站点,SNI 与 Host 不一致会被拒绝,ECH 想把 SNI 也加密。这篇逐项实测。',
    [('偏移 130', '明文 SNI "example.com" 在 ClientHello 里的位置;其余 9 个有载荷的包都找不到它'), ('403', 'SNI 是 example.com、HTTP Host 写 example.org / www.iana.org 时 Cloudflare 的回应'), ('选定 h2', '客户端把 http/1.1 写在 ALPN 列表前面时服务器仍选的协议')],
    [('明文 SNI', '<p>ClientHello 里的 SNI 是明文,路径上的设备能读出你访问的站点。</p>'),
     ('SNI 与 Host', '<p>Cloudflare 检查两者一致,不一致返回 403,域前置行不通。</p>'),
     ('ALPN', '<p>服务器按自己的偏好选协议;没有共同协议时握手不报错、只是不选。</p>'),
     ('ECH', '<p>要靠 DNS 的 HTTPS 记录里的 ech 参数,这几个站点没有发布。</p>')],
    steps,
    [ENV_W + '。对 example.com:443 的真实连接(抓包只在第一节);第二节我第一次跑时请求格式写错得到 400,文章用的是修正后的结果;SNI 与 Host 不一致被拒是这一个服务器的行为;本机 Python 不支持 ECH',
     '没有验证:ECH 本身(没有支持它的客户端);SNI 为空或为 IP 地址时的服务器行为(只测了无 SNI 在 w91 里);其它 CDN 的域前置;ALPN 的 h2c、acme-tls/1 等其它协议标识;QUIC 里 ALPN 的作用(w86 只提到 h3)'],
    'SNI 与 ALPN')
