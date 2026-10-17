from lib import *
R = J('d122')
def S(k): return [l for l in out('d122').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("DEBUG=False、ALLOWED_HOSTS=['example.com']:Host 为 example.com、example.com:8000、EXAMPLE.com 都是 200(端口被忽略、不区分大小写);www.example.com、example.com.evil.com、evil.com 都是 400(Bad Request)。精确写法不含子域名。", t=tl(S(1)), done=[0, 1, 2], mark=[3, 4, 5], kv=KV([['精确匹配', '忽略端口与大小写'], ['子域名', '不匹配']], ['子域名'])),
    step("写成 '.example.com' 才匹配域名本身及任意层子域名:example.com、a.example.com、a.b.example.com 都是 200;evilexample.com、example.com.evil.com 是 400(开头的点不会变成「后缀匹配」)。", t=tl(S(2)), done=[0, 1, 2], mark=[3, 4], kv=KV([["'.example.com'", '域名 + 所有子域名'], ['evilexample.com', '不匹配']], ["'.example.com'"])),
    step("ALLOWED_HOSTS 为空:DEBUG=True 时 localhost、127.0.0.1、[::1] 是 200,testserver 和 evil.com 是 400;DEBUG=False 时连 localhost 和 127.0.0.1 也全是 400。所以上线把 DEBUG 关掉却忘了填 ALLOWED_HOSTS,站点就是 400。", t=tl(S(3)), mark=[4, 5, 7, 8, 9], done=[1, 2, 3], kv=KV([['DEBUG=True + 空', '只放行本机三个名字'], ['DEBUG=False + 空', '全部 400']], ['DEBUG=False + 空'])),
    step("格式不合法的 Host:带空格、带 /、带 @、端口不是数字、空字符串,即使 ALLOWED_HOSTS=['*'] 也全部是 400。", t=tl(S(4)), mark=[0, 1, 2, 3, 4], kv=KV([["'*' 也挡不住", '格式非法的 Host']], ["'*' 也挡不住"])),
    step("X-Forwarded-Host:USE_X_FORWARDED_HOST=False(默认)时被完全忽略,get_host() 仍是 example.com;设为 True 后 proxy.example.com 被采用,而 evil.com 因为不在 ALLOWED_HOSTS 里得到 400——采用之后仍要校验。", t=tl(S(5)), kv=KV([['默认', '忽略 X-Forwarded-Host'], ['USE_X_FORWARDED_HOST=True', '采用,但仍校验']], ['USE_X_FORWARDED_HOST=True'])),
    step("为什么要校验:ALLOWED_HOSTS=['*'] 时,Host: evil.example 会让 build_absolute_uri()(比如密码重置邮件里的链接)生成 http://evil.example/reset/abc/——链接指向攻击者的域名。ALLOWED_HOSTS=['example.com'] 时同一个请求直接 400。", t=tl(S(6)), mark=[0], done=[1], kv=KV([["'*'", '链接可被攻击者改写'], ['明确的域名', '400']], ["'*'"])),
]
A = dict(
    n=122, series='django', tags='Django,安全,ALLOWED_HOSTS,Host头,真实验证,动画演示',
    desc="ALLOWED_HOSTS 的校验:精确写法忽略端口与大小写但不含子域名;'.example.com' 匹配域名及所有子域名;空列表在 DEBUG=True 只放行 localhost / 127.0.0.1 / [::1]、DEBUG=False 全部 400;格式非法的 Host 连 '*' 也被拒;'*' 时 build_absolute_uri 会用攻击者给的 Host。",
    lead='ALLOWED_HOSTS 常被当成「上线要填的一项」。这篇把它的匹配规则一条条跑出来:端口、大小写、子域名、空列表、非法格式、X-Forwarded-Host,最后看不校验时 Host 头会把什么东西污染掉。',
    facts=[("'.example.com'", '匹配域名本身和任意层子域名;evilexample.com 不匹配'), ('DEBUG=False + 空列表', '所有请求都是 400,包括 localhost'), ("'*'", 'build_absolute_uri() 会使用攻击者给的 Host')],
    body=[
        sec('精确匹配', '', term('', blk('d122', 1))),
        sec('子域名写法', '', term('', blk('d122', 2))),
        sec('空列表', '', term('', blk('d122', 3))),
        sec('格式非法的 Host', '', term('', blk('d122', 4)), '<p>格式校验与 ALLOWED_HOSTS 是两层:先检查主机名语法,再检查是否在列表里。</p>'),
        sec('X-Forwarded-Host', '', term('', blk('d122', 5)), '<p>只有反向代理真的会设置这个头、并且会清除客户端自己带来的同名头时,才应该开 <code>USE_X_FORWARDED_HOST</code>;这是设计上的提醒,本文没有测试代理。</p>'),
        sec('不校验会怎样', '', term('', blk('d122', 6)), '<p>这是在自己的测试项目里用自己的 Host 头请求得到的现象:Django 用 Host 头拼出绝对 URL,如果它可以被任意指定,密码重置邮件之类的链接就可能指向别的域名。</p>'),
        sec('分步演示', '', demo('ALLOWED_HOSTS 的规则', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。django.test.Client 用 HTTP_HOST 指定主机名;400 页面只看标题', '没有验证:真实反向代理(nginx)对 Host 的改写、IDN / punycode 域名、IPv6 带端口的写法、ALLOWED_HOSTS 与 CSRF_TRUSTED_ORIGINS 的交互(第 123 篇)'],
)
