from lib import *
S = SS('s31')
steps = [
    step("follow 的默认值取决于有没有 callback(源码:follow = follow if follow is not None else not callback)。规则 allow=r'/list/|/item/':没有 callback → follow=True,只跟踪不回调,站点 11 个页面全部抓到,回调 0 次;加上 callback='item' → follow=False,回调但不再往下跟,只抓 /、/item/1、/list/1、/list/2 共 4 个请求(起始页上直接看到的链接),回调 3 次;再显式写 follow=True → 11 个请求都抓,回调 10 次(起始页本身不走 callback)。", t=tl(S(1)), mark=lidx(S(1), 'callback="item"):', '同上,再加 follow=True'), done=lidx(S(1), '无 callback'), b=bars([['无 callback', 11, '11 个请求 / 回调 0'], ['callback(follow=False)', 4, '4 个请求 / 回调 3'], ['callback + follow=True', 11, '11 个请求 / 回调 10']], 11, mark=[1], done=[0, 2]), kv=KV([['没有 callback', 'follow=True:只跟踪'], ['有 callback', 'follow=False:只回调'], ['callback + follow=True', '回调并继续跟踪']], ['有 callback'])),
    step("同一个链接被多条规则命中时只归第一条规则:规则顺序是 /list/ → /item/1(callback other)→ /item/(callback item),/item/1、/item/10、/item/11 同时满足后两条,全部由 other 处理;/item/20、/item/21、/item/30、/item/31 才归 item。把 /item/ 规则调到 /item/1 之前,所有页面都归 item。源码里每条规则只提取 seen 里没有的链接,提取到的立刻加进 seen。", t=tl(S(2)), mark=lidx(S(2), '/item/1   → other', '/item/10  → other', '/item/11  → other'), done=lidx(S(2), '/item/20  → item'), kv=KV([['多条规则命中同一链接', '第一条规则处理'], ['seen', '前面规则提取过的链接,后面的规则不会再提取'], ['结论', '更具体的规则要放前面']], ['多条规则命中同一链接'])),
    step("规则产生的请求自带 meta['rule'](规则序号)和 meta['link_text'](链接文字);Rule 的 cb_kwargs 传给回调:/item/1 的回调拿到 rule=1、link_text='/item/1'、cb_kwargs={'tag': 'from-rule'}。", t=tl(S(3)), mark=lidx(S(3), 'meta rule'), kv=KV([['meta["rule"]', '规则序号(从 0 开始)'], ['meta["link_text"]', '链接文字'], ['cb_kwargs', '回调额外参数']], ['meta["rule"]'])),
    step("process_links 过滤 Link 列表、process_request 改写或丢弃请求:/list/ 规则只跟踪;/item/ 规则的 process_links 丢掉以 1 结尾的链接,process_request 丢掉 /item/10 并给其余请求加 meta['seen_from'];结果服务器只收到 /item/20 和 /item/30,回调拿到的 seen_from 分别是 list/2 和 list/3(请求来自哪个页面)。process_request 返回 None 就是丢弃这个请求。", t=tl(S(4)), mark=lidx(S(4), '服务器收到的 /item'), kv=KV([['process_links(links)', '返回过滤/改写后的 Link 列表'], ['process_request(request, response)', '返回请求或 None(丢弃)'], ['结果', '只剩 /item/20、/item/30']], ['process_request(request, response)'])),
    step("起始页的响应也走规则:/about 链接被规则抓取,回调 other 被调用;起始页本身交给 parse_start_url 钩子(默认什么都不做,这里改成记录)。在 CrawlSpider 子类里自己定义 parse 方法,2.19 里不会破坏规则:规则照常触发(服务器仍收到 / 和 /about,回调 other),自己的 parse 没有被调用——起始请求的默认回调是 _parse,它调用 parse_with_rules。", t=tl(S(5)), mark=lidx(S(5), '定义了自己的 parse', 'CrawlSpider 子类里'), done=lidx(S(5), '起始页响应'), kv=KV([['起始页', '走规则 + parse_start_url 钩子'], ['自己定义 parse', '不影响规则,也不会被调用'], ['入口', '_parse → parse_with_rules']], ['自己定义 parse'])),
    step("CrawlSpider 只对 HtmlResponse 应用规则(源码 _requests_to_follow 开头的类型检查):起始页有一个到 /feed.xml 的链接,/feed.xml 的 Content-Type 是 application/xml,里面有 <a href=\"/hidden\">——服务器收到 /feed.xml 但没有收到 /hidden,XML 响应里的链接不会被规则跟踪。", t=tl(S(6)), mark=lidx(S(6), 'feed.xml'), kv=KV([['HTML 响应', '应用规则、提取链接'], ['XML 响应', '规则不提取链接'], ['/hidden', '没有被请求']], ['XML 响应'])),
]
A = mkarts('s31', 31, 'Scrapy,CrawlSpider,Rule,follow,process_links,process_request,真实验证,动画演示',
    '实测 CrawlSpider 的 Rule:没有 callback 时 follow=True、有 callback 时 follow=False(11 个页面 vs 4 个);同一链接被多条规则命中只归第一条;meta 里有 rule 和 link_text;process_links / process_request 可过滤和丢弃;自己定义 parse 不破坏规则;XML 响应里的链接不被跟踪。',
    'CrawlSpider 的规则到底怎么工作?callback 和 follow 的默认值有什么联系?多条规则命中同一个链接听谁的?为什么有些链接没被抓?这篇在一个小站点上把每条规则语义跑出来。',
    [('11 vs 4', '同一条规则 allow="/list/|/item/",无 callback 与有 callback 抓取的请求数'), ('第一条', '多条规则命中同一链接时处理它的规则'), ('HtmlResponse', 'CrawlSpider 只对这个类型的响应应用规则')],
    [('follow 的默认值', '<p><code>follow</code> 没写时等于“有没有 callback 取反”:有 callback 默认不继续跟,没有 callback 默认继续跟;需要两样都做就显式写 <code>follow=True</code>。</p>'),
     ('规则顺序', '<p>每个响应上规则按顺序依次提取链接,前面规则提取过的链接后面的规则不会再提取,所以更具体的规则要放在前面。</p>'),
     ('请求上的信息', '<p>规则产生的请求带 <code>meta["rule"]</code>、<code>meta["link_text"]</code>,回调还能收到规则里写的 <code>cb_kwargs</code>。</p>'),
     ('过滤与改写', '<p><code>process_links</code> 过滤 Link 列表,<code>process_request</code> 改写请求或返回 <code>None</code> 丢弃它。</p>'),
     ('起始页与 parse', '<p>起始页走 <code>parse_start_url</code> 加规则;自己定义 <code>parse</code> 在 2.19 里不会影响规则。</p>'),
     ('响应类型', '<p>只有 <code>HtmlResponse</code> 会被提取链接,XML、JSON 等响应不会。</p>')],
    steps,
    [ENV_Y + '。站点:/ 链接到 /list/1、/list/2、/item/1、/about、/feed.xml;/list/N 链接到 /item/N0、/item/N1 和下一页(到 3);并发 1;规则用的都是默认的 LinkExtractor 配 allow 正则',
     '没有验证:Rule 的 errback;process_request 返回新 Request 时 callback 是否被覆盖(规则的 callback 在 Request 上,返回 None 以外的请求不会重新套规则);深度(DEPTH_LIMIT)与规则的组合;大量规则时的耗时;非 UTF-8 页面上的链接提取;CRAWLSPIDER_FOLLOW_LINKS 设置(源码里已弃用并会警告,没有实测);rules 里 callback 写字符串与可调用对象的区别(只测了字符串)'],
    'CrawlSpider 规则')
