from lib import *
S = SS('f111')
R = J('f111'); rc = R['race']; ky = R['keyby']; sp = R['spoof']
na, at = rc['先 GET 再 SET(非原子)'], rc['Lua 令牌桶(原子,容量 10,不补充)']
steps = [
    step("令牌桶(容量 5、每秒补 2 个):连发 7 次,前 5 次放行(突发),第 6、7 次被拒,需要等 0.5 秒;等 1.1 秒(补了约 2.2 个令牌)后连发 3 次:放行、放行、被拒(还要再等约 0.39 秒)。令牌桶既允许突发,又限制长期平均速率。", t=tl(S(1)), done=lidx(S(1), '连发 7 次'), mark=lidx(S(1), '等 1.1 秒'), kv=KV([['容量', '允许的突发'], ['补充速度', '长期平均速率'], ['被拒时', '告诉调用方还要等多久']], ['容量'])),
    step(f"Redis 里的原子性:20 个线程同时抢 10 个名额。「先 GET 再 SET」的非原子实现放行了 {na} 个(全部通过,限流形同虚设);把读、算、写放进一个 Lua 脚本(Redis 单线程执行脚本)的令牌桶只放行 {at} 个。限流器的检查与扣减必须是同一个原子操作。", b=bars([['非原子 GET + SET', na, str(na)], ['Lua 脚本', at, str(at)]], 20, mark=[0], done=[1]), t=tl(S(2)), mark=lidx(S(2), '先 GET 再 SET'), done=lidx(S(2), 'Lua'), kv=KV([['GET 再 SET', f'{na} / 上限 10'], ['Lua', f'{at} / 上限 10']], ['Lua'])),
    step("429 响应带上头:前 3 次 200,RateLimit-Limit: 3、RateLimit-Remaining 依次 2、1、0;第 4、5 次 429,Retry-After: 1(按桶补满一个令牌还要等的秒数向上取整)。调用方据此退避,不用盲目重试。(RateLimit-* 是 IETF 草案里的头名,这里只是照着用,没有核对草案的最新写法。)", t=tl(S(3)), done=lidx(S(3), '200'), mark=lidx(S(3), '429'), kv=KV([['RateLimit-Remaining', '剩余额度'], ['Retry-After', '多久之后可以重试']], ['Retry-After'])),
    step(f"限流的 key 从哪来:不信任代理头(用 remote_addr)时,8 个请求每个伪造不同的 X-Forwarded-For,状态码是 {sp['不信任代理头(用 remote_addr)']}(同一个客户端地址,第 4 个起 429);用 ProxyFix(x_for=1) 信任 X-Forwarded-For、而前面其实没有代理时,同样的 8 个请求全部 200——攻击者随便伪造头就绕过了限流。只有确实有可信代理在前面、并且按代理的层数配置 ProxyFix 才应该信任。", t=tl(S(4)), mark=lidx(S(4), 'ProxyFix'), done=lidx(S(4), '不信任代理头'), kv=KV([['不信任', '用连接的 remote_addr'], ['无条件信任 X-Forwarded-For', '攻击者可伪造,限流失效']], ['无条件信任 X-Forwarded-For'])),
    step(f"按用户还是按 IP:3 个用户共用一个 IP(公司出口)轮流请求 9 次,按 IP 限流只放行 {ky['按 IP(未登录,3 个用户共用 1 个 IP)'][0]} 个、{ky['按 IP(未登录,3 个用户共用 1 个 IP)'][1]} 个 429(互相挤占额度);按用户限流 9 个全部放行。已登录接口按用户限流,未登录接口(登录、注册)才退回到按 IP。", t=tl(S(5)), mark=lidx(S(5), '按 IP'), done=lidx(S(5), '按用户'), kv=KV([['按 IP', '同一出口的用户互相影响'], ['按用户', '额度独立']], ['按用户'])),
]
A = mkartf('f111', 111, 'Flask,API限流,令牌桶,Redis,Lua,真实验证,动画演示',
    f'实测 API 限流的实现细节:令牌桶的突发与补充、20 个线程抢 10 个名额时非原子 GET+SET 放行 {na} 个而 Lua 脚本只放行 {at} 个、429 的 Retry-After 与 RateLimit 头、无条件信任 X-Forwarded-For 时限流被随意绕过、按用户与按 IP 限流的差别。',
    '自己实现限流要注意什么?为什么要用 Lua 脚本?限流的 key 取错了会有什么后果?这篇用自己起的 redis 与多线程,把令牌桶、原子性与伪造请求头的绕过逐个验证。',
    [(f'{na} → {at}', '20 个线程抢 10 个名额:非原子实现与 Lua 脚本放行的个数'), ('8 / 8', '无条件信任 X-Forwarded-For 时,8 个伪造请求里放行的个数'), ('Retry-After', '被限流时告诉调用方还要等多久的响应头')],
    [('令牌桶', '<p>上一篇:<a href="flask-refresh-token.html">Refresh Token</a>;下一篇:<a href="flask-cors-preflight.html">CORS 预检请求</a>。</p><p>第 76 篇讲过 Flask-Limiter 的用法,这一篇讲自己实现时的细节。</p>'), ('原子性', '<p>redis 是自己在非默认端口起的临时实例,验证完就关掉了。</p>'), ('429 与响应头', None), ('限流的 key', None), ('用户与 IP', None)],
    steps, [ENV_F + '。redis-py 8.1.0、自己起的 redis(非默认端口)', '没有验证:滑动窗口日志与滑动窗口计数的实现、redis 故障时限流器的降级策略(放行还是拒绝)、分布式多实例下的时钟偏差、真实反向代理链下 ProxyFix 的层数配置(见第 135 篇)、限流对正常用户体验的影响'], 'API 限流', panels=[('t', 'term', '实验输出'), ('b', 'bars', '放行个数'), ('kv', 'kv', '要点')])
