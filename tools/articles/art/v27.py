from lib import *
S = SS('v27')
steps = [
    step("burst 与 nodelay。limit_req_zone rate=10r/s,30 个请求在同一时刻发出。(a) 无 burst:放行 1 个、拒绝 29 个(429)。(b) burst=5:放行 6 个、拒绝 24 个;放行的请求耗时 6、107、202、305、405、504 ms——排队的 5 个被漏桶每隔约 100 ms 放一个。(c) burst=5 nodelay:同样放行 6 个、拒绝 24 个,但 6 个都立刻处理(4 到 10 ms)。(d) burst=10 delay=3:放行 11 个、拒绝 19 个,前 4 个立刻(8、8、9、9 ms),后 7 个按 104、202、303、403、504、604、703 ms 排队放行。burst 决定能多放几个,nodelay / delay 决定这些多放的请求是排队还是立刻处理。", t=tl(S(1)), mark=lidx(S(1), '(b)', '(d)'), done=lidx(S(1), '(a)', '(c)'), b=bars([['(a) 无 burst:放行', 1, '1'], ['(b) burst=5:放行', 6, '6(最慢 504 ms)'], ['(c) nodelay:放行', 6, '6(最慢 10 ms)'], ['(d) burst=10 delay=3:放行', 11, '11(最慢 703 ms)']], 11, done=[0, 2], mark=[1, 3]), kv=KV([['无 burst', '同一时刻只放行 1 个'], ['burst=5', '放行 6 个,排队的间隔约 100 ms'], ['burst=5 nodelay', '放行 6 个,都立刻处理'], ['burst=10 delay=3', '放行 11 个,前 4 个立刻']], ['burst=5 nodelay'])),
    step("持续过载。client 以 20 个/秒的开环速率发 5 秒共 100 个请求,limit_req rate=10r/s。burst 0:共放行 40 个(第 0 到 4 秒各 9、8、9、7、7),比 rate × 时间 = 50 还少;我的解释是请求每 50 ms 到一个,而放行要求距离上一个放行的请求至少 100 ms,到达时刻稍有抖动就差一点点被拒绝(这个解释没有单独验证)。burst 5:共放行 55 个(第一秒 15 个,后面每秒 10 个),55 = 50 + burst 的 5 个;burst 5 nodelay:同样 55 个。速率上限是 rate × 时间,burst 一次性多送 5 个额度。", t=tl(S(2)), mark=lidx(S(2), 'burst 0'), done=lidx(S(2), 'burst 5  ', 'nodelay'), b=bars([['burst 0:放行', 40, '40'], ['burst 5:放行', 55, '55'], ['burst 5 nodelay:放行', 55, '55'], ['rate × 时间', 50, '50']], 55, mark=[0], done=[1, 2], cur=[3]), kv=KV([['burst 0', '40 个(比 50 还少)'], ['burst 5', '55 个 = 50 + 5'], ['burst 5 nodelay', '55 个']], ['burst 5'])),
    step("limit_conn。后端 1 s 才回,limit_conn c 3(同一个 key 最多 3 个并发连接),12 个请求同时发出:放行 3 个、拒绝 9 个(429)。对照 limit_req rate=10r/s burst=20 nodelay:12 个全部放行、0 个拒绝——12 个请求在同一时刻到达,没有超过 burst,limit_req 不管它们处理多久。limit_req 数的是单位时间内到达的请求,limit_conn 数的是同时在处理的请求,慢上游需要的是 limit_conn。", t=tl(S(3)), mark=lidx(S(3), 'limit_conn c 3'), done=lidx(S(3), 'limit_req rate'), b=bars([['limit_conn 3:放行', 3, '3 / 12'], ['limit_conn 3:拒绝', 9, '9'], ['limit_req burst=20:放行', 12, '12 / 12']], 12, mark=[1], done=[0], cur=[2]), kv=KV([['limit_conn c 3', '12 个并发里放行 3、拒绝 9'], ['limit_req burst=20 nodelay', '12 个全放行'], ['区别', 'limit_req 数到达速率,limit_conn 数并发']], ['区别'])),
]
A = mkartv('v27', 27, '微服务,网关,nginx,限流,limit_req,limit_conn,burst,nodelay,真实验证,动画演示',
    '实测 nginx 限流:limit_req 同一时刻 30 个请求,无 burst 放行 1 个、burst=5 放行 6 个(排队的每隔约 100 ms 一个)、burst=5 nodelay 6 个都立刻处理;持续 20 个/秒打 10r/s 的限额,burst 5 共放行 55 个;limit_conn 3 在 12 个并发里放行 3 个。',
    'limit_req 的 burst 和 nodelay 到底改变了什么?持续过载时放行多少?limit_conn 和 limit_req 守的是同一件事吗?这篇用 nginx 1.31.6 逐项量出来。',
    [('1 / 6 / 6', '30 个请求同一时刻到达、rate=10r/s 时,无 burst / burst=5 / burst=5 nodelay 放行的数量;burst=5 的最慢一个等了 504 ms,nodelay 只要 10 ms'), ('55', '20 个/秒打 5 秒、rate=10r/s、burst 5 时共放行的数量(= 50 + burst 的 5 个);burst 0 只有 40'), ('3 / 12', 'limit_conn 3 在 12 个并发请求里放行的数量,同样的请求 limit_req burst=20 nodelay 全部放行')],
    [('burst 与 nodelay', '<p>burst 决定能多放几个,nodelay / delay 决定这些多放的请求排队还是立刻处理。</p>'),
     ('持续过载', '<p>放行总量是 rate × 时间加 burst;闭环 client 会被排队拖慢到 rate,所以看不到拒绝。</p>'),
     ('limit_conn', '<p>数的是同时在处理的请求,和 limit_req 数到达速率不同。</p>')],
    steps,
    [ENV_V + '。nginx 是 Homebrew 的 1.31.6;所有请求来自 127.0.0.1,限流 key 是 $binary_remote_addr,所以是同一个 key;后端是本进程里的 Python 服务;第一节用 barrier 让 30 个请求同时发出;第二节是开环 client;每个场景只测一次;我最初在第二节用的是顺序(闭环)client,burst 5 时一个都没被拒绝,因为排队放行拖慢了 client 自己,所以改成开环',
     '没有验证:多个 worker 进程之间限流计数的共享(要用 zone,这里是单 worker);limit_req_dry_run;limit_req 的 $limit_req_status;limit_req 作用于 HTTP/2 同一连接上的多个请求;按 XFF 取 key 时的 realip 先后顺序(见第 26 篇)'],
    'nginx 限流')
