from lib import *
S = SS('s16')
steps = [
    step("DOWNLOAD_DELAY = 0.2,单域名 100 个请求,服务器不延迟,统计相邻两个请求到达服务器的间隔。2.19 用 DOWNLOAD_DELAY_JITTER 控制抖动(默认 0.5,即 ±50%,和显式设 0.5 一样):间隔最小 125、最大 300 ms,平均 243 ms——比设置的 200 ms 长 20%,总耗时 24.2 s;JITTER = 0 时间隔稳稳在 200 ms(中位数 201,平均 201),总耗时 20.1 s;JITTER = 1.0 时最小 30、最大 401,平均 286 ms,总耗时 28.5 s。也就是说开着抖动时实际的平均间隔大于 DOWNLOAD_DELAY。", t=tl(S(1)), mark=lidx(S(1), '(默认)', 'JITTER=0.5', 'JITTER=1.0'), done=lidx(S(1), 'JITTER=0 '), b=bars([['JITTER=0', 201, '平均 201 ms'], ['默认 / 0.5', 243, '平均 243 ms'], ['JITTER=1.0', 286, '平均 286 ms']], 286, mark=[1, 2], done=[0]), kv=KV([['JITTER=0', '间隔固定 ≈ 201 ms'], ['默认 0.5', '125~300 ms,平均 243'], ['JITTER=1.0', '30~401 ms,平均 286'], ['设置值', '200 ms']], ['默认 0.5'])),
    step("旧设置 RANDOMIZE_DOWNLOAD_DELAY 在 2.19 里已弃用,仍然有效但会警告 “The RANDOMIZE_DOWNLOAD_DELAY setting is deprecated, use DOWNLOAD_DELAY_JITTER instead”:设 False,间隔回到 200 ms(中位数 201,平均 201);设 True,间隔 118~301 ms,平均 232 ms。", t=tl(S(2)), mark=lidx(S(2), '=False', '=True'), kv=KV([['RANDOMIZE_DOWNLOAD_DELAY=False', '无抖动,平均 201 ms'], ['=True', '±50% 抖动,平均 232 ms'], ['两者', '都警告已弃用']], ['RANDOMIZE_DOWNLOAD_DELAY=False'])),
    step("延迟是“上一个请求发出之后过多久再发下一个”,不是等响应:服务器每个请求耗时 0.6 s,DOWNLOAD_DELAY = 0.1(无抖动),相邻请求间隔 101 ms,服务器同时处理的请求数峰值是 7(≈ 0.6 ÷ 0.1 = 6),24 个请求总耗时 3.0 s(≈ 24×0.1 + 0.6)。慢响应不会让下一个请求等,只会让在途请求堆起来。", t=tl(S(3)), mark=lidx(S(3), '峰值'), kv=KV([['间隔', '101 ms(发出到发出)'], ['服务器峰值', '7 ≈ 0.6 ÷ 0.1'], ['总耗时', '3.0 s']], ['服务器峰值'])),
    step("每个域名(下载槽)有自己的延迟计时:127.0.0.1 与 localhost 各 20 个请求、DOWNLOAD_DELAY = 0.2 无抖动,两个域名一起跑总耗时 4.0 s,和只跑一个域名 20 个的 4.0 s 一样——两个域名的请求交替发出(l1l1l1…),互不拖累。", t=tl(S(4)), mark=lidx(S(4), '两个域名各 20 个'), done=lidx(S(4), '到达顺序'), b=bars([['一个域名 20 个', 4.0, '4.0 s'], ['两个域名各 20 个', 4.0, '4.0 s']], 4.0, mark=[1], done=[0]), kv=KV([['一个域名', '4.0 s'], ['两个域名各 20 个', '4.0 s(并行,互不拖累)']], ['两个域名各 20 个'])),
    step("DOWNLOAD_SLOTS 可以给单个域名设自己的 delay:127.0.0.1 用 0.05、localhost 用 0.3(全局 DOWNLOAD_DELAY = 0.2),各 20 个请求,无抖动:127.0.0.1 相邻间隔平均 51 ms,localhost 平均 301 ms,总耗时 5.7 s(由慢的 localhost 决定,19×0.3)。", t=tl(S(5)), mark=lidx(S(5), 'localhost', '总耗时'), done=lidx(S(5), '127.0.0.1'), kv=KV([['127.0.0.1(delay 0.05)', '间隔平均 51 ms'], ['localhost(delay 0.3)', '间隔平均 301 ms'], ['总耗时', '5.7 s,由慢的决定']], ['localhost(delay 0.3)'])),
    step("旧写法 spider 属性 download_delay = 0.3 仍然生效(间隔中位数 301 ms,平均 300 ms),但会警告 “The 'download_delay' spider attribute is deprecated. Use the DOWNLOAD_DELAY setting instead.”;它被当成 spider 优先级(30)的设置处理,所以比项目的 settings.py(20)优先。", t=tl(S(6)), mark=lidx(S(6), '警告'), done=lidx(S(6), '只有 spider.download_delay'), kv=KV([['download_delay 属性', '仍生效(≈301 ms)'], ['警告', "deprecated,改用 DOWNLOAD_DELAY"], ['优先级', 'spider(30) > project(20)']], ['download_delay 属性'])),
]
A = mkarts('s16', 16, 'Scrapy,DOWNLOAD_DELAY,抖动,下载延迟,DOWNLOAD_SLOTS,真实验证,动画演示',
    '实测 2.19 的下载延迟:DOWNLOAD_DELAY = 0.2 且默认 ±50% 抖动时,实际平均间隔是 243 ms 而不是 200 ms(总耗时 24.2 s 对 20.1 s);延迟按“发出到发出”计算,慢响应只会让在途请求变多;每个域名独立计时;DOWNLOAD_SLOTS 可以单独设 delay;RANDOMIZE_DOWNLOAD_DELAY 与 download_delay 属性已弃用。',
    'DOWNLOAD_DELAY 设成 0.2 秒,请求之间的间隔真的是 200 毫秒吗?抖动开着的时候间隔是什么分布?这篇在服务器端记录每个请求到达的时间,把间隔分布、慢响应的影响、多域名与单域名覆盖都量出来。',
    [('243 ms', 'DOWNLOAD_DELAY = 0.2、默认抖动时的平均请求间隔(设置值 200 ms)'), ('3.0 s', '24 个请求、延迟 0.1、每个耗时 0.6 s 时的总耗时(延迟按发出到发出)'), ('51 / 301 ms', 'DOWNLOAD_SLOTS 给两个域名分别设 0.05、0.3 s 后的实际间隔')],
    [('抖动的影响', '<p>2.19 里 <code>DOWNLOAD_DELAY_JITTER</code>(默认 0.5)取代旧的 <code>RANDOMIZE_DOWNLOAD_DELAY</code>。开着抖动时,实际平均间隔比设置值长约 20%——每次放行前都重新抽一次随机延迟,延迟没到才继续等,所以间隔偏向抖动范围的上端。要精确的节奏就把抖动设成 0。</p>'),
     ('RANDOMIZE_DOWNLOAD_DELAY', '<p>旧设置 <code>RANDOMIZE_DOWNLOAD_DELAY</code> 仍然生效(<code>False</code> 关掉抖动,<code>True</code> 开启 ±50%),但已弃用并会警告。</p>'),
     ('发出到发出', '<p>延迟计的是两个请求先后放行的间隔,不等响应。响应慢时,延迟不变,在途请求数变成响应耗时除以延迟。</p>'),
     ('按域名计时', '<p>每个下载槽(域名)独立计时,两个域名同时爬不会互相等待。</p>'),
     ('DOWNLOAD_SLOTS', '<p><code>DOWNLOAD_SLOTS</code> 可以给某个域名单独设置 <code>delay</code>(以及 <code>concurrency</code>、<code>jitter</code>),比全局设置优先。</p>'),
     ('spider 的 download_delay 属性', '<p>旧写法 <code>download_delay = 0.3</code> 作为 spider 优先级的设置仍然生效,同样会警告弃用。</p>')],
    steps,
    [ENV_Y + '。服务器端记录每个请求到达的时刻,统计相邻请求的间隔;/seed 请求不计入;抖动实验的样本是 99 个间隔',
     '没有验证:AutoThrottle 对延迟的调整(下一批文章);真实网络时延下抖动分布;用 Request.meta 的 download_slot 把多个域名合并成一个槽(见槽那一篇);各次运行之间的数字会有几毫秒的偏差(表中是最后一次运行);“偏向上端”的原因是读源码 _process_queue 得到的推断,没有逐次验证'],
    '下载延迟')
