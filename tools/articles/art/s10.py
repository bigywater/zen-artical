from lib import *
S = SS('s10')
steps = [
    step("站点里有环(/a→/b,/c;/b→/a,/c;/c→/a)时:默认去重,服务器收到 3 个请求就结束,dupefilter/filtered = 3;所有请求都 dont_filter=True,爬虫就绕着环一直转——靠 CLOSESPIDER_PAGECOUNT=50 在第 50 个页面被关掉(finish_reason = closespider_pagecount,request_depth_max = 26);靠 DEPTH_LIMIT=4 在深度 4 处停下,服务器收到 19 个请求;靠 CLOSESPIDER_TIMEOUT=1 一秒内转了 799 个请求、深度 400。", t=tl(S(1)), mark=lidx(S(1), 'CLOSESPIDER_PAGECOUNT', 'CLOSESPIDER_TIMEOUT', 'DEPTH_LIMIT'), done=lidx(S(1), '默认(去重)'), b=bars([['默认去重', 3, '3 个请求'], ['DEPTH_LIMIT=4', 19, '19 个'], ['PAGECOUNT=50', 50, '50 个'], ['TIMEOUT=1 s', 799, '799 个']], 799, mark=[3], done=[0, 1, 2]), kv=KV([['有环 + 去重', '3 个请求,过滤 3 个'], ['有环 + dont_filter=True', '永远转,要靠别的开关刹车'], ['刹车', 'DEPTH_LIMIT / CLOSESPIDER_PAGECOUNT / CLOSESPIDER_TIMEOUT']], ['有环 + dont_filter=True'])),
    step("Scrapy 自己产生的请求怎么设 dont_filter:重试出来的请求是 True(/flaky 第 1、2 次重试都是 dont_filter=True),不然重试请求的指纹和原请求一样,会被去重吃掉;重定向产生的请求沿用原请求的值(/go 是 False,重定向到的 /target 也是 False);robots.txt 请求是 False;你自己写的 Request 默认也是 False。", t=tl(S(2)), mark=lidx(S(2), '/flaky        True', '/target'), done=lidx(S(2), '/robots.txt', '/go  '), kv=KV([['重试请求', 'dont_filter=True'], ['重定向请求', '沿用原请求(默认 False)'], ['robots.txt', 'False'], ['自己写的 Request', '默认 False']], ['重试请求'])),
    step("重定向也要过去重,这是个坑:先抓了 /target,回调里又请求 /go(服务器把 /go 重定向到 /target)。默认 dont_filter=False 时服务器收到 /target、/go,重定向产生的第二个 /target 请求被去重过滤(dupefilter/filtered = 1),/go 的回调根本没被调用;/go 请求设 dont_filter=True 后,重定向的 /target 也沿用 True,服务器收到 /target、/go、/target,/go 的回调被调用。", t=tl(S(3)), mark=lidx(S(3), '/go 的回调没有被调用'), done=lidx(S(3), '/go 的回调被调用'), kv=KV([['dont_filter=False', '重定向目标已抓过 → 被过滤,回调不调用'], ['dont_filter=True', '重定向照样走完,回调被调用']], ['dont_filter=False'])),
    step("轮询同一个 URL(状态页)必须 dont_filter=True:回调里想再请求 /status 共 5 次,不加 dont_filter 只发出了 1 个请求,dupefilter/filtered = 1,爬虫第一轮之后就结束了;加了 dont_filter=True 才发出 5 个请求,没有任何过滤。", t=tl(S(4)), mark=lidx(S(4), '不加 dont_filter'), done=lidx(S(4), 'dont_filter=True'), b=bars([['不加', 1, '1 个请求'], ['dont_filter=True', 5, '5 个请求']], 5, mark=[0], done=[1]), kv=KV([['不加 dont_filter', '1 个请求,过滤 1 个'], ['dont_filter=True', '5 个请求,过滤 0 个']], ['不加 dont_filter'])),
]
A = mkarts('s10', 10, 'Scrapy,去重,dont_filter,重试,重定向,CLOSESPIDER,真实验证,动画演示',
    '实测 dont_filter 何时该用:有环的站点全部 dont_filter=True 会一直转(1 秒 799 个请求),要靠 DEPTH_LIMIT / CLOSESPIDER_* 刹车;重试请求自带 True;重定向沿用原请求的值,重定向到已抓过的 URL 会被去重吃掉,回调不被调用;轮询同一个 URL 必须加。',
    'dont_filter=True 能让请求绕过去重。什么情形必须用,什么情形用了会出事?这篇用有环的站点、重试、重定向和轮询四个场景实测:什么时候少了它会丢请求,什么时候多了它会停不下来。',
    [('799 个', '有环站点全部 dont_filter=True,1 秒内发出的请求数(去重时只要 3 个)'), ('0 次', '重定向到已抓过的 URL 时 /go 回调被调用的次数(dont_filter 默认 False)'), ('True', '重试请求的 dont_filter 值')],
    [('绕过去重的代价', '<p>去重是防止爬虫在环里打转的第一道防线;对所有请求关掉它,就必须有 <code>DEPTH_LIMIT</code>、<code>CLOSESPIDER_PAGECOUNT</code> 或 <code>CLOSESPIDER_TIMEOUT</code> 之类的刹车。</p>'),
     ('Scrapy 内部请求', '<p>重试请求会被设成 <code>dont_filter=True</code>,所以不会被去重吃掉;重定向沿用原请求的值;robots.txt 请求是 False。</p>'),
     ('重定向的坑', '<p>重定向产生的请求同样经过去重。如果重定向目标之前已经抓过,默认会被过滤,回调不会被调用。想要这个响应就给原请求设 <code>dont_filter=True</code>。</p>'),
     ('轮询', '<p>反复请求同一个 URL 想拿最新数据时,每次都要 <code>dont_filter=True</code>,否则第二次起就被过滤。</p>')],
    steps,
    [ENV_Y + '。有环站点是三个页面互相链接;重定向用 302;重试用前两次返回 503 的路径;刹车开关用 CLOSESPIDER_PAGECOUNT=50、DEPTH_LIMIT=4、CLOSESPIDER_TIMEOUT=1;并发均为 1',
     '没有验证:dont_filter 请求在 HTTP 缓存里的表现;自定义 dupefilter 里对 dont_filter 的处理;redirect 中间件里 meta 的 dont_redirect 与 dont_filter 的组合;CLOSESPIDER_TIMEOUT 下“799”这个数字随机器速度变化(只作量级参考)'],
    'dont_filter')
