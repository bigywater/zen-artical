from lib import *
S = SS('g69')
steps = [
    step("本文用的是 golang.org/x/time v0.16.0 的 rate 包(通过本机代理下载,不在标准库里)。", t=tl(S(1)), mark=lidx(S(1), 'golang.org/x/time v0.16.0'), kv=KV([['模块', 'golang.org/x/time'], ['版本', 'v0.16.0'], ['包', 'rate']], ['版本'])),
    step("Allow:NewLimiter(10/s, burst 5),桶是满的,连续调用 Allow() 8 次:[true true true true true false false false]——先放行 5 个,其余被拒绝。等 105 ms 后再 Allow() 成功,紧接着再 Allow() 失败。再空闲 1.2 秒(按速率本应攒 12 个令牌,但桶只装 5 个)后,连续 Allow() 成功了 5 次。", t=tl(S(2)), done=lidx(S(2), '[true true true true true false false false]', '等 105 ms 后'), mark=lidx(S(2), '成功了 5 次'), b=bars([['连续 8 次 Allow 放行', 5, '5'], ['空闲 1.2 秒后一口气放行', 5, '5'], ['按速率本应攒到', 12, '12']], 12, done=[0, 1], mark=[2]), kv=KV([['桶满时', '先放行 burst 个(5)'], ['空闲很久后', '最多再放行 burst 个'], ['含义', 'burst 是上限,攒不多']], ['含义'])),
    step("Wait 把请求均匀地摊开:NewLimiter(20/s, burst 1),连续 Wait 11 次,放行的时刻(ms)依次是 0 51 101 151 201 251 301 351 401 451 501;相邻两次放行的间隔最小 49.9 ms、最大 51.1 ms(理论 50 ms)。", t=tl(S(3)), done=lidx(S(3), '放行的时刻'), mark=lidx(S(3), '相邻两次放行的间隔'), b=bars([['最小间隔 (ms)', 49.9, '49.9'], ['理论', 50, '50'], ['最大间隔', 51.1, '51.1']], 51.1, done=[0, 1, 2]), kv=KV([['速率', '20/s,理论间隔 50 ms'], ['实测间隔', '49.9–51.1 ms']], ['实测间隔'])),
    step("Wait 的两种错误:WaitN(ctx, 6) 超过桶容量 5,返回 rate: Wait(n=6) exceeds limiter's burst 5。速率 1/s、桶已空、ctx 期限 200 ms 时,Wait 返回 rate: Wait(n=1) would exceed context deadline,耗时 0 ms——它预先算出要等约 1 秒,超过期限就立即失败,没有真的等。", t=tl(S(4)), mark=lidx(S(4), 'exceeds limiter', 'would exceed context deadline'), kv=KV([['n 大于 burst', '立即返回错误'], ['等待会超过 ctx 期限', '立即返回错误,不空等']], ['等待会超过 ctx 期限'])),
    step("Reserve 与 Cancel:桶空时 Reserve() OK=true,Delay=100 ms;Cancel 之后再 Reserve(),Delay 仍是 100 ms(令牌还回去了)。不 Cancel 连续 Reserve 3 次,Delay 是 100 / 200 / 300 ms——预约一个比一个往后排。", t=tl(S(5)), done=lidx(S(5), 'Cancel 之后再 Reserve()'), mark=lidx(S(5), '不 Cancel'), b=bars([['第 1 次预约 Delay (ms)', 100, '100'], ['第 2 次', 200, '200'], ['第 3 次', 300, '300']], 300, mark=[0, 1, 2]), kv=KV([['Reserve', '返回要等多久'], ['Cancel', '把令牌还回去'], ['不 Cancel', '后面的预约越排越远']], ['不 Cancel'])),
    step("多个 goroutine 共用一个限流器,限速 1000/s,各自循环 Wait,3 秒内:1 个 goroutine 通过 3010 次(1003 次/秒);8 个 3017 次(1003 次/秒);64 个 3073 次(1003 次/秒)。总吞吐与 goroutine 个数无关。", t=tl(S(6)), mark=lidx(S(6), '1 个 goroutine', '8 个 goroutine', '64 个 goroutine'), b=bars([['1 个 goroutine', 1003, '1003'], ['8 个', 1003, '1003'], ['64 个', 1003, '1003']], 1003, done=[0, 1, 2]), kv=KV([['限速', '1000/s'], ['实测', '1003/s(1、8、64 个 goroutine 都是)']], ['实测'])),
    step("调用本身的成本:Allow() 在 rate.Inf 下 45 ns/次;有限速率单线程 66 ns/次;10 个 P 并行争同一个限流器 200 ns/次。", t=tl(S(7)), mark=lidx(S(7), 'rate.Inf'), b=bars([['rate.Inf (ns)', 45, '45'], ['有限速率,单线程', 66, '66'], ['10 个 P 并行', 200, '200']], 200, done=[0, 1], mark=[2]), kv=KV([['Inf', '45 ns'], ['单线程', '66 ns'], ['并行争用', '200 ns']], ['并行争用'])),
    step("源码注释:Limiter 控制事件发生的频率,实现一个大小为 b 的令牌桶,初始是满的,以每秒 r 个令牌补充;r == Inf 时 b 被忽略;零值是合法的 Limiter 但会拒绝所有事件;有 Allow、Reserve、Wait 三个主要方法,多数调用者应该用 Wait;没有令牌时,Allow 返回 false,Reserve 返回对未来令牌的预约和需要等待的时间,Wait 阻塞直到拿到令牌或 context 被取消;Limiter 可被多个 goroutine 同时使用。", t=tl(S(8)), done=lidx(S(8), 'token bucket', 'initially full'), mark=lidx(S(8), 'zero value is a valid Limiter', 'Most callers should use Wait', 'safe for simultaneous use'), kv=KV([['令牌桶', '大小 b,初始满,每秒补 r 个'], ['零值', '合法但拒绝所有事件'], ['推荐', '多数调用者用 Wait']], ['推荐'])),
]
A = mkartg('g69', 69, 'Go,限流,令牌桶,x/time/rate,Allow,Wait,Reserve,真实验证,动画演示',
    '用 golang.org/x/time v0.16.0 的 rate 实测令牌桶:桶满时 Allow 连放 5 个再拒绝,空闲 1.2 秒也只能一口气放 5 个;Wait 以 20/s 放行,间隔 49.9–51.1 ms;n 超过 burst 或等待会超过 ctx 期限时立即返回错误;Reserve 的预约依次排到 100/200/300 ms;1、8、64 个 goroutine 共用一个限流器,吞吐都是约 1003 次/秒。',
    '令牌桶限流器的 Allow、Wait、Reserve 有什么区别?burst 到底是什么?这篇用真实运行回答:桶能攒多少、Wait 摊开请求有多均匀、什么情况下 Wait 会立即报错、多个 goroutine 共用时总吞吐是多少,再读 rate.go 里的说明。',
    [('5', '桶满或空闲很久后,burst=5 的限流器一次最多连续放行的个数'), ('49.9–51.1 ms', '20/s 的限流器 Wait 放行的相邻间隔(理论 50 ms)'), ('1003/s', '限速 1000/s 时,1、8、64 个 goroutine 共用限流器的实测吞吐')],
    [('依赖说明', '<p>rate 包来自 <code>golang.org/x/time</code>(v0.16.0),不在标准库里。</p>'),
     ('burst 是上限', '<p>桶满时 <code>Allow</code> 连续放行 burst 个(5),然后被拒绝;空闲 1.2 秒本应攒 12 个令牌,桶装不下,只能一口气放行 5 个。</p>'),
     ('Wait 摊得很匀', '<p>20/s、burst 1 的限流器,<code>Wait</code> 的放行间隔在 49.9–51.1 ms 之间,几乎就是理论的 50 ms。</p>'),
     ('不空等的错误', '<p><code>WaitN</code> 的 n 超过 burst 会立即报错;如果预计等待时间会超出 ctx 的期限,<code>Wait</code> 也立即返回 “would exceed context deadline”,不会白白等到超时。</p>'),
     ('Reserve', '<p><code>Reserve</code> 返回需要等待多久,不 <code>Cancel</code> 的话预约会占用未来的令牌:连续 3 次的延迟是 100、200、300 ms。要放弃就调 <code>Cancel</code> 把令牌还回去。</p>'),
     ('共用一个限流器', '<p>限速 1000/s 时,无论 1 个、8 个还是 64 个 goroutine 一起等,总吞吐都是约 1003 次/秒。限流器是整个进程的总量,不是每个 goroutine 各 1000。</p>'),
     ('自身成本', '<p><code>Allow</code> 单线程 66 ns,10 个 P 争同一个限流器 200 ns;速率为 <code>Inf</code> 时 45 ns。对每个请求限流没问题,但每秒几百万次的热点路径要注意。</p>'),
     ('读文档', '<p>注释写明:令牌桶初始是满的;零值合法但拒绝所有事件;多数调用者应该用 <code>Wait</code>;可以被多个 goroutine 同时使用。</p>')],
    steps,
    [ENV_G + '。限流器来自 golang.org/x/time v0.16.0(本机代理下载);时间用 time.Now 测,精度毫秒;吞吐实验每种 3 秒;Allow 的成本用 testing.Benchmark;源码注释摘自 rate.go',
     '没有验证:SetLimit/SetBurst 动态调整、WaitN 对大 n 的行为、长时间运行的漂移、Sometimes 等较新的辅助类型、与 HTTP 中间件的集成、其它限流算法(漏桶、滑动窗口)'],
    '令牌桶限流')
