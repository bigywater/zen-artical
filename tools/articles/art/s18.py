from lib import *
S = SS('s18')
steps = [
    step("源码里的更新规则(extensions/throttle.py):目标延迟 target = 延迟 ÷ AUTOTHROTTLE_TARGET_CONCURRENCY;新延迟 = max(target, (旧延迟 + target) ÷ 2),再夹在 [DOWNLOAD_DELAY, AUTOTHROTTLE_MAX_DELAY] 之间。服务器恒定 0.2 s、START_DELAY = 1.0 s:第一个值 501 是 /seed 响应(延迟极短,(1000 + 5)÷2);之后目标并发 1 时 delay 依次是 354、279、241、224、212、207……最终 203 ms,趋近 latency ÷ 1 = 200;目标并发 2 时 301、201、152、126、114 …… 最终 101 ms,趋近 100。每次向目标走一半,约 8 个响应收敛。", t=tl(S(1)), mark=lidx(S(1), 'TARGET_CONCURRENCY=1', 'TARGET_CONCURRENCY=2'), kv=KV([['更新规则', 'max(target, (旧 + target)/2),target = latency/N'], ['N = 1', '收敛到 203 ms'], ['N = 2', '收敛到 101 ms'], ['起点', 'AUTOTHROTTLE_START_DELAY']], ['更新规则'])),
    step("服务器先 0.1 s、中间 15 个请求 0.8 s、之后又 0.1 s:变慢时 delay 一步跳到目标(max 规则):第 16 个响应起 803~808 ms;变快后每响应约折半往下降:802、454、278、192、149、127……回到约 105 ms。变慢时 delay 来不及抬高,服务器上同时处理的请求峰值到了 7。", t=tl(S(2)), mark=lidx(S(2), '803', '802'), done=lidx(S(2), '50  105'), kv=KV([['变慢', '一步跳到 ≈ 800 ms'], ['变快', '每次折半下降:802→454→278→192…'], ['服务器并发峰值', '7(delay 滞后于变慢)']], ['变慢'])),
    step("非 200 的响应不会让 delay 下降(error 页面通常很小很快,会诱导节流放松):前 10 个请求 0.5 s、delay 约 504~507 ms,之后 20 个请求都很快(0.02 s):返回 200 时 delay 一路降到 25 ms;返回 404 时 delay 纹丝不动,一直 506 ms。", t=tl(S(3)), mark=lidx(S(3), '404'), done=lidx(S(3), '200:'), b=bars([['快速 200 后最终 delay', 25, '25 ms'], ['快速 404 后最终 delay', 506, '506 ms']], 506, mark=[1], done=[0]), kv=KV([['后面返回 200', 'delay 降到 25 ms'], ['后面返回 404', 'delay 保持 506 ms'], ['规则', 'status != 200 且新延迟 ≤ 旧延迟 → 不调整']], ['后面返回 404'])),
    step("上下限:服务器每个请求 2 s,目标并发 1,理想 delay 2000 ms——默认 MAX_DELAY = 60 时 delay 轨迹是 50(seed)、2002、2002、2003;AUTOTHROTTLE_MAX_DELAY = 0.5 时被夹在 500 ms。另一头,DOWNLOAD_DELAY 是最小值:服务器只要 0.05 s,DOWNLOAD_DELAY = 0.3 时 delay 始终是 300 ms,理想的 50 ms 被抬到了 300。", t=tl(S(4)), mark=lidx(S(4), 'MAX_DELAY=0.5', 'DOWNLOAD_DELAY=0.3'), done=lidx(S(4), 'MAX_DELAY=60'), kv=KV([['MAX_DELAY = 60(默认)', '2002 ms(跟着延迟走)'], ['MAX_DELAY = 0.5', '夹在 500 ms'], ['DOWNLOAD_DELAY = 0.3', '最小值,理想 50 ms 变 300 ms']], ['MAX_DELAY = 0.5'])),
    step("AutoThrottle 只调节延迟,不直接限制并发。服务器 0.4 s,目标并发 1、2、4:最终 delay 约 406、202、101 ms(≈ 0.4 ÷ N);服务器实际并发峰值 2、3、7,比目标大,因为默认抖动 ±50% 让间隔忽大忽小,而且延迟的调整滞后于响应;总耗时 20.1、10.3、5.0 s,基本和目标并发成反比。", t=tl(S(5)), mark=lidx(S(5), '                   4 '), done=lidx(S(5), '                   1 ', '                   2 '), b=bars([['目标并发 1', 20.1, '20.1 s(峰值 2)'], ['目标并发 2', 10.3, '10.3 s(峰值 3)'], ['目标并发 4', 5.0, '5.0 s(峰值 7)']], 20.1, mark=[2], done=[0, 1]), kv=KV([['最终 delay', '406 / 202 / 101 ms'], ['服务器峰值', '2 / 3 / 7(大于目标)'], ['总耗时', '20.1 / 10.3 / 5.0 s']], ['服务器峰值'])),
    step("meta['autothrottle_dont_adjust_delay'] = True 的请求不参与调整:前 10 个请求 0.1 s 正常参与,后 10 个请求服务器要 1.0 s 但带了这个 meta——服务器确实收到 20 个请求、总耗时 3.7 s,debug 行只有 11 条(seed + 前 10 个),delay 一直停在 102~106 ms,没有因为后面的慢响应而升到 1000 ms。", t=tl(S(6)), mark=lidx(S(6), '服务器收到 20 个请求'), kv=KV([['带 meta 的请求', '不参与 delay 调整'], ['debug 行', '11 条(不含带 meta 的)'], ['delay', '停在 ≈ 105 ms,没有升到 1000 ms']], ['带 meta 的请求'])),
]
A = mkarts('s18', 18, 'Scrapy,AutoThrottle,自动限速,延迟,真实验证,动画演示',
    '实测 AutoThrottle:延迟每次向 latency ÷ 目标并发 走一半,约 8 个响应收敛;变慢时一步跳升、变快时折半下降;非 200 响应不会让延迟下降(404 后 delay 保持 506 ms,200 后降到 25 ms);DOWNLOAD_DELAY 是下限、MAX_DELAY 是上限;它只调延迟,实际并发峰值会超过目标。',
    'AutoThrottle 声称“根据服务器的响应时间自动调整延迟”。它具体怎么调?变慢变快各多快?404 会不会骗过它?能不能保证并发?这篇用能改变延迟的服务器逐项实测,并对照 2.19 里它的几行源码。',
    [('≈ 8 个响应', '延迟收敛到 latency ÷ N 附近所需的响应数(每次走一半)'), ('25 vs 506 ms', '后面都是快速 200 与快速 404 时,最终的 delay'), ('2 / 3 / 7', '目标并发 1 / 2 / 4 时服务器上实际的同时处理峰值')],
    [('更新规则', '<p>每个响应下载完成后,AutoThrottle 取目标延迟 <code>latency / AUTOTHROTTLE_TARGET_CONCURRENCY</code>,新延迟 = <code>max(目标, (旧延迟 + 目标)/2)</code>,并夹在 <code>DOWNLOAD_DELAY</code> 与 <code>AUTOTHROTTLE_MAX_DELAY</code> 之间。</p>'),
     ('变慢与变快', '<p>变慢时由于取 max,延迟一步跳到目标;变快时每个响应只走一半,所以收敛比升高慢。</p>'),
     ('非 200 响应', '<p>状态码不是 200 且新延迟比旧延迟小时,不调整:避免错误页(又小又快)诱导放松限速。</p>'),
     ('上下限', '<p><code>DOWNLOAD_DELAY</code> 是最小延迟,<code>AUTOTHROTTLE_MAX_DELAY</code> 是上限(默认 60 秒),<code>AUTOTHROTTLE_START_DELAY</code> 是起点。</p>'),
     ('不保证并发', '<p>AutoThrottle 只改延迟,不限制并发;默认的 ±50% 抖动和调整的滞后会让实际并发超过 <code>TARGET_CONCURRENCY</code>。</p>'),
     ('排除个别请求', '<p>给请求加 <code>meta["autothrottle_dont_adjust_delay"] = True</code>,它的响应不参与调整。</p>')],
    steps,
    [ENV_Y + '。服务器按到达顺序决定每个请求的延迟和状态码;AUTOTHROTTLE_DEBUG = 1 的日志行解析出每个响应之后槽的 delay;请求用先进先出队列保证顺序',
     '没有验证:多个域名各自的槽独立调整(只测了一个槽);与 CONCURRENT_REQUESTS_PER_DOMAIN 的组合(受上一篇的发现影响,这里没有靠它限制并发);抖动关掉(DOWNLOAD_DELAY_JITTER = 0)时并发是否贴近目标;真实服务器上 latency 的抖动对收敛的影响;download_latency 的含义(Twisted 与 aiohttp 处理器是否一致)'],
    'AutoThrottle')
