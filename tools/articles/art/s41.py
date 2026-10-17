from lib import *
S = SS('s41')
steps = [
    step("IgnoreRequest 在不同位置抛出的后果:下载器中间件 process_request 里抛、process_response 里抛、爬虫中间件 process_spider_input 里抛,请求的 errback 都会收到 IgnoreRequest(消息分别是 mw says no、resp says no、spider-mw says no),spider_exceptions = 0,stats 里 downloader/exception_type_count/scrapy.exceptions.IgnoreRequest = 1,没有 ERROR 日志;但在回调里抛 IgnoreRequest 就是普通的回调异常:回调/errback 都不再调用,spider_exceptions = 1,日志 ERROR “Spider error processing”。", t=tl(S(1)), mark=lidx(S(1), '回调里抛'), done=lidx(S(1), '下载器中间件 process_request', 'process_response', 'process_spider_input'), kv=KV([['中间件里抛', 'errback 收到 IgnoreRequest,不算 spider 异常'], ['回调里抛', '当作普通异常:spider_exceptions + ERROR 日志'], ['被过滤的请求', '没有回调']], ['回调里抛'])),
    step("CloseSpider(reason) 只在回调和 start() 里被识别:回调里第 5 个页面抛 CloseSpider('my_reason') → finish_reason = my_reason(服务器收到 7 个请求,并发 1,关闭有延迟);start() 里抛 CloseSpider('start_reason') → finish_reason = start_reason。但在 pipeline.process_item 里抛(第 5 个 item)只是 ERROR “Error processing {…}”,爬虫照样抓完 31 个请求、finish_reason = finished;在下载器中间件 process_request 里抛是 ERROR “Error downloading”,30 个请求照常;在信号处理函数里抛是 ERROR “Error caught on signal handler”,31 个请求照常。想从这些地方关爬虫,得用 crawler.engine.close_spider() 之类。", t=tl(S(2)), mark=lidx(S(2), 'pipeline.process_item', '下载器中间件', '信号处理函数'), done=lidx(S(2), '回调里 raise', 'start() 里抛'), kv=KV([['回调 / start()', 'CloseSpider 生效'], ['pipeline / 下载器中间件 / 信号处理函数', 'CloseSpider 只是一个普通错误,不关爬虫'], ['替代办法', 'crawler.engine.close_spider(...)']], ['pipeline / 下载器中间件 / 信号处理函数'])),
    step("NotConfigured:扩展、下载器中间件、pipeline 的 __init__ 或 from_crawler 里抛 NotConfigured,这个组件就被禁用,爬虫照常跑完(finish_reason = finished)。不带消息的 QuietExt 一声不吭;带消息的打一条 WARNING——“Disabled <class 'spider.LoudExt'>: missing LOUD_SETTING”、“Disabled <class 'spider.DM'>: no config for DM”、“Disabled <class 'spider.P'>: pipeline off”;日志里 “Enabled item pipelines” 因此是空列表。", t=tl(S(3)), mark=lidx(S(3), 'Disabled', 'Enabled item pipelines'), done=lidx(S(3), '爬虫照常跑完'), kv=KV([['抛 NotConfigured', '组件被禁用,爬虫继续'], ['不带消息', '静默'], ['带消息', 'WARNING Disabled …: 消息']], ['抛 NotConfigured'])),
    step("不支持的 URL 协议:请求 foo://bar/x,errback 收到 scrapy.exceptions.NotSupported,消息 “Unsupported URL scheme 'foo': no handler available for that scheme”;不重试(retry/count = 0),downloader/exception_count = 1。", t=tl(S(4)), mark=lidx(S(4), 'foo://bar/x'), kv=KV([['没有处理器的协议', 'NotSupported → errback'], ['重试', '不会(retry/count = 0)']], ['没有处理器的协议'])),
]
A = mkarts('s41', 41, 'Scrapy,异常,IgnoreRequest,CloseSpider,NotConfigured,NotSupported,真实验证,动画演示',
    '实测 Scrapy 的控制异常:中间件里抛 IgnoreRequest 走 errback、回调里抛则是普通错误;CloseSpider 只在回调和 start() 里生效,在 pipeline、下载器中间件、信号处理函数里抛只记 ERROR 不关爬虫;NotConfigured 悄悄(或带 WARNING)禁用组件;不支持的协议抛 NotSupported 且不重试。',
    'DropItem、IgnoreRequest、CloseSpider、NotConfigured……这些异常是 Scrapy 给你控制流程的开关,但“在哪里抛”决定它是否有效。这篇把它们放进回调、中间件、pipeline、信号处理函数里各抛一次,看引擎怎么处理。',
    [('回调 / start()', 'CloseSpider 真正能关掉爬虫的两个位置'), ('3 处', 'IgnoreRequest 在下载器中间件两个钩子和爬虫中间件里,都是 errback 收到'), ('Disabled', 'NotConfigured 带消息时的 WARNING 前缀')],
    [('IgnoreRequest', '<p>在中间件里抛表示“丢弃这个请求/响应”,errback 会收到它;在回调里抛没有这个含义,只是普通的回调异常。</p>'),
     ('CloseSpider', '<p>只有回调和 <code>start()</code> 里抛的 <code>CloseSpider</code> 才会按给定原因关闭爬虫;其它位置抛只会变成普通的错误日志,爬虫继续跑。</p>'),
     ('NotConfigured', '<p>组件构造时抛出,Scrapy 就跳过它,爬虫继续;给了消息会打 WARNING。常用于“没配置就不启用”。</p>'),
     ('NotSupported', '<p>没有对应下载处理器的协议会抛 <code>NotSupported</code>,走 errback,不重试。</p>')],
    steps,
    [ENV_Y + '。站点 30 个页面,并发 1;异常实验里每种位置写一个最小的组件;日志级别 DEBUG;被异常打断后“服务器收到几个请求”受关闭的异步延迟影响',
     '没有验证:DropItem 在回调里抛(当作普通异常,未测);StopDownload(见信号那一篇);DontCloseSpider(见引擎那一篇);UsageError、ScrapyDeprecationWarning 等命令行与弃用类异常;CloseSpider 在爬虫中间件里抛的行为;NotConfigured 在下载处理器里的行为'],
    '控制异常')
