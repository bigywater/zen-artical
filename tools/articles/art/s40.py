from lib import *
S = SS('s40')
steps = [
    step("回调的各种写法(pipeline 里看到的 item):def return 一个 dict → item 1;def return [dict, Request] → item 2,新请求也被调度(cb2 被调用);def 生成器 yield → 3;async def return 一个 dict → 4;async def return 列表 → 5 和 6;async def 里 await 之后再 return → 7;async def 里带 yield 的异步生成器 → 8 和 9;async def return None → 没有 item。全部 spider_exceptions = 0。也就是说同步/异步、return/yield、单个/列表都一样接受,引擎只看最后得到的东西是 Request 还是 item。", t=tl(S(1)), mark=lidx(S(1), 'async def', 'def,return 列表'), done=lidx(S(1), 'def,return 一个 dict', 'def 生成器'), kv=KV([['def / async def', '都行'], ['return 单个 / 列表 / yield', '都行'], ['return None', '没有产出'], ['新 Request', '和 item 混在列表里也会被调度']], ['def / async def'])),
    step("异步生成器是流式处理的:回调 yield 第一个 item 之后 await 1 s 再 yield 第二个,pipeline 在回调开始的同一毫秒(136 ms)就看到第一个,1138 ms 才看到第二个——不会等整个生成器跑完才处理(注意:CrawlSpider 的 parse_with_rules 会先把异步生成器收集完再处理,源码里是 collect_asyncgen)。", t=tl(S(2)), mark=lidx(S(2), '1138', '136'), kv=KV([['普通 Spider 的异步生成器', '边产出边处理'], ['第一个 item', '136 ms 就到 pipeline'], ['第二个 item', '1138 ms(await 1 s 之后)']], ['普通 Spider 的异步生成器'])),
    step("回调并行:20 个响应、每个回调 await 0.3 s,async def 版本总耗时 0.33 s(互不阻塞,同一个事件循环里并发);同步 time.sleep(0.3) 的回调 6.25 s(串行,20 × 0.3 = 6.0,外加开销)。回调想等待就用 async def + await。", t=tl(S(3)), mark=lidx(S(3), 'time.sleep'), done=lidx(S(3), 'async def'), b=bars([['async + await 0.3', 0.33, '0.33 s'], ['同步 time.sleep(0.3)', 6.24, '6.25 s']], 6.24, mark=[1], done=[0]), kv=KV([['async def + await', '0.33 s(并行)'], ['def + time.sleep', '6.25 s(串行)']], ['async def + await'])),
    step("asyncio reactor 下 await Twisted 的 Deferred 要转换:直接 await task.deferLater(…) 抛 RuntimeError: Task got bad yield: <Deferred at 0x…>;用 scrapy.utils.defer 里的 maybe_deferred_to_future(d) 或 deferred_to_future(d) 包一层再 await,都能拿到结果 deferred-result。", t=tl(S(4)), mark=lidx(S(4), '直接 await'), done=lidx(S(4), 'maybe_deferred_to_future', 'deferred_to_future'), kv=KV([['await Deferred', 'RuntimeError: Task got bad yield'], ['maybe_deferred_to_future(d)', '可以 await,拿到结果'], ['deferred_to_future(d)', '可以 await,拿到结果']], ['await Deferred'])),
    step("回调里直接用 aiohttp(同一个 asyncio 事件循环):20 个回调各自用 aiohttp.ClientSession 再请求一个 URL 并 yield item,服务器收到 40 个请求(20 个 Scrapy 的加 20 个 aiohttp 的),item_scraped_count = 20,总耗时 0.03 s,可以并发。", t=tl(S(5)), mark=lidx(S(5), '服务器收到'), kv=KV([['aiohttp 在回调里', '同一个事件循环,能并发'], ['40 个请求', '20 个 Scrapy 的 + 20 个 aiohttp 的'], ['注意', '这些请求绕过了 Scrapy 的下载器、去重和中间件']], ['aiohttp 在回调里'])),
    step("async errback 同样可以产出 item:500 响应走 errback(HttpError),async def errback await 之后 yield {'from_errback': 500},pipeline 收到,spider_exceptions = 0;async 回调里抛 ValueError('async boom') 与同步回调一样记 spider_exceptions/ValueError = 1,日志 ERROR “Spider error processing”。", t=tl(S(6)), mark=lidx(S(6), 'async 回调抛异常'), done=lidx(S(6), '500 响应'), kv=KV([['async errback', '可以 await 并 yield item'], ['async 回调抛异常', '计入 spider_exceptions'], ['日志', 'Spider error processing']], ['async errback'])),
]
A = mkarts('s40', 40, 'Scrapy,asyncio,async def,回调,Deferred,异步生成器,真实验证,动画演示',
    '实测 async def 回调:return 单个/列表、yield、异步生成器都被接受;异步生成器边产出边处理(136 ms / 1138 ms);20 个 await 0.3 s 的回调总耗时 0.33 s,同步 sleep 要 6.25 s;直接 await Deferred 抛 RuntimeError,要用 maybe_deferred_to_future;回调里可以用 aiohttp;async errback 可以 yield item。',
    '回调写成 async def 之后,Scrapy 怎么接收它们的返回值、会不会并行、能不能 await Twisted 的 Deferred、能不能直接用 aiohttp?这篇把八种回调写法和几个常见的坑一次测完。',
    [('0.33 vs 6.25 s', '20 个等待 0.3 s 的回调:async + await 与同步 time.sleep 的总耗时'), ('RuntimeError', '在 asyncio reactor 下直接 await Deferred 的结果'), ('136 / 1138 ms', '异步生成器两个 item 到达 pipeline 的时间(中间 await 1 s)')],
    [('返回值', '<p>回调可以是普通函数、生成器、协程或异步生成器;可以 return 一个对象、一个列表,也可以逐个 yield。引擎只区分每个产出物是 Request 还是 item。</p>'),
     ('流式', '<p>普通 Spider 里异步生成器边 yield 边处理;CrawlSpider 的规则回调会先收集完整个异步生成器。</p>'),
     ('并发', '<p>async 回调在同一个事件循环里并发;同步的阻塞调用会把所有回调串行化。</p>'),
     ('Deferred', '<p>asyncio reactor 下要用 <code>maybe_deferred_to_future</code> / <code>deferred_to_future</code> 才能 await Twisted 的 Deferred。</p>'),
     ('第三方异步库', '<p>可以直接在回调里用 aiohttp 等基于 asyncio 的库,但它们的请求不经过 Scrapy 的下载器中间件、去重和限速。</p>'),
     ('错误处理', '<p>async 回调抛的异常和同步回调一样计入 <code>spider_exceptions</code>;async errback 同样可以 yield item。</p>')],
    steps,
    [ENV_Y + '。每个情形是一个单文件 spider,pipeline 里用 EV() 记录收到的 item;aiohttp 使用虚拟环境里的 aiohttp 3.14.5',
     '没有验证:无 reactor 模式(TWISTED_REACTOR_ENABLED=False)下同样的写法;SelectReactor 下 async def 回调的支持程度(上一批文章里只测过 asyncio.sleep 会失败);async 回调里 time.sleep 之外的阻塞调用(如 requests)的整体影响;CrawlSpider 收集异步生成器后的内存影响;回调里使用 Playwright/Selenium 等的细节'],
    '异步回调')
