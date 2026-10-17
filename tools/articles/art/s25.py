from lib import *
S = SS('s25')
steps = [
    step("二叉树站点(第 d 层 2^d 个页面,共 6 层 63 个页面)。DEPTH_LIMIT = 0(不限)抓满 63 个,request_depth_max = 5,每层请求数 1、2、4、8、16、32;DEPTH_LIMIT = 1 只抓 3 个(层 0 和层 1),= 2 抓 7 个,= 3 抓 15 个,= 4 抓 31 个——每多一层请求数翻倍。超过上限的链接被爬虫中间件丢弃,日志只在 DEBUG 级别打第一条 “Ignoring link (depth > 2)”;response.meta['depth'] 记录页面所在层(t0:0,t1、t2:1,t3~t6:2)。", t=tl(S(1)), mark=lidx(S(1), '           1 ', '           2 ', 'DEPTH_LIMIT=2 的日志'), done=lidx(S(1), '           0 ', '           3 ', '           4 '), b=bars([['DEPTH_LIMIT=1', 3, '3 个'], ['=2', 7, '7 个'], ['=3', 15, '15 个'], ['=4', 31, '31 个'], ['不限', 63, '63 个']], 63, mark=[0, 1], done=[2, 3, 4]), kv=KV([['DEPTH_LIMIT = N', '抓到第 N 层,共 2^(N+1) − 1 个页面'], ['超过上限', '链接被丢弃(DEBUG 日志只打第一条)'], ['response.meta["depth"]', '起始请求为 0,每跟一层 +1']], ['DEPTH_LIMIT = N'])),
    step("DEPTH_PRIORITY 把请求的优先级减去 深度 × DEPTH_PRIORITY:并发 1、DEPTH_LIMIT = 3、15 个页面,服务器收到页面的层号序列——默认是 011223333223333(后进先出,深度优先);DEPTH_PRIORITY = 1 变成 011222233333333(先把浅层抓完,近似广度优先);再换成 FIFO 队列序列相同;DEPTH_PRIORITY = -1 又回到 011223333223333。要广度优先,设 DEPTH_PRIORITY = 1 就够这个例子;文档里再换 FIFO 队列是为了同层严格按先进先出。", t=tl(S(2)), mark=lidx(S(2), 'DEPTH_PRIORITY = 1  ', 'FIFO'), done=lidx(S(2), '默认', '-1'), kv=KV([['默认', '011223333223333(深度优先)'], ['DEPTH_PRIORITY = 1', '011222233333333(广度优先)'], ['DEPTH_PRIORITY = -1', '011223333223333(深度优先)']], ['DEPTH_PRIORITY = 1'])),
    step("depth 怎么传:重定向沿用同一个深度——/red 的请求深度 1,被 302 到 /leaf 后,/leaf 响应的 meta['depth'] 还是 1;meta 里带 depth_reset = True 的 /t2 深度归零(0);想在回调里 meta={'depth': 50} 手动指定 /t3 的深度没用,被中间件覆盖成 1(= 父页面深度 0 + 1)。", t=tl(S(3)), mark=lidx(S(3), 'leaf', 't2', 't3'), kv=KV([['重定向', '沿用请求的 depth(/leaf = 1)'], ['depth_reset = True', '深度归 0'], ['手动 meta depth', '被覆盖(/t3 = 1,不是 50)']], ['depth_reset = True'])),
    step("start() 里的请求自己带 depth 不会被改写:Request('/t0', meta={'depth': 3}) 的响应 depth = 3,它的子请求 /t1 depth = 4;DEPTH_LIMIT = 4 时能继续,DEPTH_LIMIT = 3 时 /t1 深度 4 > 3 被丢弃,回调只被调用一次(t0)。", t=tl(S(4)), mark=lidx(S(4), 't1: depth = 4', 'DEPTH_LIMIT=3'), done=lidx(S(4), 't0: depth = 3'), kv=KV([['start 请求带 depth = 3', '保留 3'], ['子请求', '4'], ['DEPTH_LIMIT = 3', '子请求被丢弃']], ['start 请求带 depth = 3'])),
    step("换域名要不要重新数:链是 127.0.0.1 的 /t0 → localhost 的 /t1 → /t3,DEPTH_LIMIT = 1。不加 depth_reset,/t1 深度 1 能抓,/t3 深度 2 被丢弃,回调只有 t0、t1;跨域链接加 meta depth_reset = True,/t1 深度归 0,/t3 深度 1,三个页面都抓到。depth_reset 让 DEPTH_LIMIT 不在域名切换时误伤。", t=tl(S(5)), mark=lidx(S(5), '跨域链接加 depth_reset'), done=lidx(S(5), '不加 depth_reset'), kv=KV([['不加 depth_reset', '回调:t0(0)、t1(1)'], ['跨域加 depth_reset', '回调:t0(0)、t1(0)、t3(1)']], ['跨域加 depth_reset'])),
]
A = mkarts('s25', 25, 'Scrapy,DepthMiddleware,DEPTH_LIMIT,DEPTH_PRIORITY,depth_reset,真实验证,动画演示',
    '在二叉树站点上实测 DepthMiddleware:DEPTH_LIMIT = 1/2/3/4 分别抓 3/7/15/31 个页面;DEPTH_PRIORITY = 1 把层号序列从 011223333223333(深度优先)变成 011222233333333(广度优先);重定向沿用 depth,depth_reset 归零,手动 meta depth 会被覆盖。',
    'DEPTH_LIMIT 到底从哪里开始数?DEPTH_PRIORITY 为什么能改成广度优先?重定向、起始请求、跨域名的 depth 怎么算?这篇在一个二叉树站点上把层号序列和请求数量都量出来。',
    [('63 → 3', 'DEPTH_LIMIT 从不限到 1,二叉树站点抓取的页面数'), ('011222233333333', 'DEPTH_PRIORITY = 1 时服务器收到页面的层号序列(默认 011223333223333)'), ('depth_reset', '让跨域名的链接从 0 重新数,避免被 DEPTH_LIMIT 误伤的 meta 键')],
    [('DEPTH_LIMIT', '<p>DepthMiddleware 给每个从响应产生的请求设置 <code>meta["depth"] = 响应深度 + 1</code>,超过 <code>DEPTH_LIMIT</code> 就丢掉。起始请求深度为 0,所以 <code>DEPTH_LIMIT = N</code> 会抓到第 N 层。</p>'),
     ('DEPTH_PRIORITY', '<p>请求优先级减去 <code>深度 × DEPTH_PRIORITY</code>。为正数时浅层优先(广度优先),为 0 时按调度器默认顺序(后进先出,深度优先)。</p>'),
     ('depth 的传递', '<p>重定向沿用原请求的 depth;<code>depth_reset</code> 让请求的深度归零;回调里手动写 meta 的 depth 会被覆盖。</p>'),
     ('起始请求', '<p>start() 里的请求自带 depth 时会保留,子请求从这个值 +1 数起。</p>'),
     ('跨域名', '<p>depth 不区分域名,要让每个域名自己从 0 数,给跨域链接加 <code>depth_reset</code>。</p>')],
    steps,
    [ENV_Y + '。二叉树站点:节点 n 的子节点是 2n+1、2n+2;并发 1;DEPTH_STATS_VERBOSE = 1 时 stats 里有 request_depth_count/N',
     '没有验证:重试请求的 depth(应该沿用,没测);DEPTH_STATS_VERBOSE 在真实站点上对 stats 大小的影响;DEPTH_LIMIT 与 CrawlSpider 规则的组合(见后面的文章);depth 与 JOBDIR 恢复;FIFO 队列和 DEPTH_PRIORITY 同层顺序的细节(这里只看了层号序列)'],
    '爬取深度')
