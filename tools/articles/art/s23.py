from lib import *
S = SS('s23')
steps = [
    step("ROBOTSTXT_OBEY 的内置默认值是 False,而 scrapy startproject 生成的 settings.py 里写的是 ROBOTSTXT_OBEY = True(同时 USER_AGENT 被注释掉,用默认的 Scrapy/2.19.0 (+https://scrapy.org))。解析器默认是 ProtegoRobotParser,ROBOTSTXT_USER_AGENT 默认 None。所以用 runspider 写的单文件爬虫默认不看 robots.txt,用项目模板建的爬虫默认看。", t=tl(S(1)), mark=lidx(S(1), '项目模板'), done=lidx(S(1), '默认值'), kv=KV([['内置默认', 'ROBOTSTXT_OBEY = False'], ['startproject 模板', 'ROBOTSTXT_OBEY = True'], ['解析器', 'ProtegoRobotParser'], ['ROBOTSTXT_USER_AGENT', 'None(用请求的 UA)']], ['startproject 模板'])),
    step("robots.txt 写 Disallow: /private:5 个请求里 /a、/b 通过,/private、/private/x、/privatefoo(前缀匹配)被拒绝,errback 收到 IgnoreRequest: Forbidden by robots.txt,stats robotstxt/forbidden = 3。服务器只收到一次 robots.txt(按 netloc 缓存;robotstxt/request_count = 1、response_count = 1、response_status_count/200 = 1),并且排在 /a、/b 之前,被禁止的请求根本没发出去。", t=tl(S(2)), mark=lidx(S(2), '被拒', '服务器收到的顺序'), done=lidx(S(2), '通过'), kv=KV([['被禁请求', 'IgnoreRequest,errback 收到,不发出'], ['robots.txt', '只下载 1 次,排在最前面'], ['stats', 'forbidden = 3,request_count = 1']], ['被禁请求'])),
    step("匹配哪个 User-agent:robots.txt 里有 User-agent: Scrapy、mybot 和 * 三组。默认 USER_AGENT(Scrapy/2.19.0 …)匹配 Scrapy 组:/scrapy-only 被拒,/mybot-only 通过;ROBOTSTXT_USER_AGENT = mybot 改按 mybot 匹配:/mybot-only 被拒,/scrapy-only 通过;USER_AGENT = mybot/1.0 (+http://x) 同样匹配 mybot 组(取产品名)。有具体组时 * 组不再生效(/all 对三者都通过)。", t=tl(S(3)), mark=lidx(S(3), 'ROBOTSTXT_USER_AGENT=mybot', 'USER_AGENT=mybot'), done=lidx(S(3), '默认 USER_AGENT'), kv=KV([['默认 UA', '匹配 Scrapy 组'], ['ROBOTSTXT_USER_AGENT = mybot', '匹配 mybot 组'], ['USER_AGENT = mybot/1.0 …', '也匹配 mybot(产品名)'], ['* 组', '有具体组时不生效']], ['默认 UA'])),
    step("robots.txt 自己出问题时一律放行:200 正常时 /private 被拒;robots.txt 返回 404、返回 500(被重试 2 次,服务器收到 robots.txt 共 3 次)、超时(DownloadTimeoutError,计入 robotstxt/exception_count)、返回 1024 字节二进制垃圾,/private 全部通过。也就是说 robots.txt 获取失败不会阻止抓取。", t=tl(S(4)), mark=lidx(S(4), '404', '500', '超时', '垃圾'), done=lidx(S(4), '200 正常'), kv=KV([['200 正常', '/private 被拒'], ['404 / 500 / 超时 / 垃圾', '/private 通过(放行)'], ['500', 'robots.txt 也会被重试(共 3 次)'], ['异常', '记入 robotstxt/exception_count']], ['404 / 500 / 超时 / 垃圾'])),
    step("robots.txt 下载慢(服务器延迟 1.0 s)时其它请求要等它:服务器先收到 /robots.txt(0.00 s),1.02 s 之后 /a、/b、/c 才几乎同时到达,总耗时 1.03 s。meta dont_obey_robotstxt = True 的请求既不下载 robots.txt 也不受限制:/private/x 直接发出,总耗时 0.01 s。", t=tl(S(5)), mark=lidx(S(5), '到达服务器的时刻', 'dont_obey_robotstxt'), kv=KV([['robots.txt 下载中', '其它请求等待'], ['到达时刻', '/a /b /c 在 1.02~1.03 s'], ['dont_obey_robotstxt', '不等待、不受限制']], ['robots.txt 下载中'])),
    step("两点限制:robots.txt 里的 Crawl-delay: 2 被 Scrapy 忽略,四个页面请求之间只隔 1 ms、1 ms、1 ms,总耗时 0.01 s,要自己用 DOWNLOAD_DELAY;robots.txt 按 netloc(含端口)缓存,同一个主机 127.0.0.1 的两个端口各自下载一次自己的 robots.txt(robotstxt/request_count = 2)。", t=tl(S(6)), mark=lidx(S(6), 'Crawl-delay', '同一个主机'), kv=KV([['Crawl-delay', '被忽略,请求间隔 ~1 ms'], ['缓存键', 'netloc(主机 + 端口)'], ['两个端口', '各下载一次 robots.txt']], ['Crawl-delay'])),
]
A = mkarts('s23', 23, 'Scrapy,RobotsTxtMiddleware,robots.txt,爬虫礼仪,真实验证,动画演示',
    '实测 RobotsTxtMiddleware:内置默认 ROBOTSTXT_OBEY = False 而项目模板写 True;被禁请求抛 IgnoreRequest 且不发出,robots.txt 每个 netloc 只下载一次并排在前面;默认 UA 匹配 User-agent: Scrapy 组;robots.txt 404/500/超时/乱码一律放行;Crawl-delay 被忽略。',
    'ROBOTSTXT_OBEY 打开后 Scrapy 具体怎么做?什么时候下载 robots.txt、下载失败怎么办、按哪个 User-agent 匹配、Crawl-delay 管不管?这篇用一个能返回各种 robots.txt 的服务器逐项实测。',
    [('False / True', '内置默认值与 scrapy startproject 模板里 ROBOTSTXT_OBEY 的差别'), ('放行', 'robots.txt 返回 404、500、超时、乱码时 /private 的结果'), ('忽略', 'robots.txt 里 Crawl-delay: 2 对请求间隔的影响')],
    [('开关与默认', '<p>内置默认关闭,项目模板打开。打开后 <code>RobotsTxtMiddleware</code> 在每个请求前先取该 netloc 的 robots.txt(优先级 1000),解析后缓存,之后同一个 netloc 的请求直接用缓存的解析器。</p>'),
     ('被禁止的请求', '<p>不被允许的请求抛 <code>IgnoreRequest("Forbidden by robots.txt")</code>,不会发出,计入 <code>robotstxt/forbidden</code>;errback 能收到。</p>'),
     ('User-agent 匹配', '<p>用 <code>ROBOTSTXT_USER_AGENT</code>(没设就用请求的 User-agent)去匹配 robots.txt 的组;存在匹配的具体组时 <code>*</code> 组不生效。</p>'),
     ('失败即放行', '<p>robots.txt 下载失败(404、5xx、超时)或内容无法解析时,所有请求都被允许。</p>'),
     ('等待', '<p>robots.txt 下载期间,同一个 netloc 的其它请求会等待它;<code>dont_obey_robotstxt</code> 的请求例外。</p>'),
     ('Crawl-delay 与 Sitemap', '<p>Scrapy 不使用 <code>Crawl-delay</code>,要控制节奏用 <code>DOWNLOAD_DELAY</code> 或 AutoThrottle。</p>')],
    steps,
    [ENV_Y + '。服务器按需返回 robots.txt(200、404、500、睡 2 s、二进制垃圾),记录所有请求的到达时刻;并发 1;匹配实验的三组 User-agent 写在同一个 robots.txt 里',
     '没有验证:Protego 对通配符(*、$)、Allow/Disallow 优先级的细节;其它解析器(PythonRobotParser、ReppyRobotParser 等);Sitemap: 行的使用(见 SitemapSpider 那一篇);robots.txt 内容改变后的更新(中间件在爬虫运行期间不重新下载);robots_parsed 信号;HTTPS 与 HTTP 同主机是否各取一次(缓存键是 netloc,不含协议,只用 netloc 的字面推断)'],
    'robots.txt')
