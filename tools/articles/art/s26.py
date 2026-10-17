from lib import *
S = SS('s26')
steps = [
    step("allowed_domains 的匹配规则是正则 ^(.*\\.)?(域名1|域名2)$,只比主机名:allowed_domains = ['example.org'] 时 example.org、www.example.org、bob.www.example.org、大写的 EXAMPLE.ORG、带端口的 example.org:8080、api.example.org 都通过(子域名自动算),notexample.org、example.org.evil.com、example.orgx 和 [::1] 被拒;['www.example.org'] 只放行 www 及其子域(example.org 本身被拒);写成 ['example.org:8080'] 或 ['http://example.org'] 一个都匹配不上,全部被拒,没有任何警告;[] 或不设则全部放行。", t=tl(S(1)), mark=lidx(S(1), "['example.org:8080']", "['http://example.org']", "['www.example.org']"), done=lidx(S(1), "['example.org']  ", "allowed_domains=[]"), kv=KV([['example.org', '含所有子域名,不含 notexample.org'], ['www.example.org', '不含 example.org 本身'], ['带端口 / 带协议', '一个都匹配不上'], ['空 / 不设', '全部放行']], ['带端口 / 带协议'])),
    step("真实抓取:allowed_domains = ['127.0.0.1'],起始页 / 和站内页 /on 各有 2 个去 localhost 的链接。回调只被调用 / 和 on 两次,服务器只收到 / 和 /on;offsite/filtered = 4(两个页面各 2 个链接)、offsite/domains = 1(只有 localhost 一个域名);日志只记每个被过滤域名的第一条:“Filtered offsite request to 'localhost': <GET …/off1>”。", t=tl(S(2)), mark=lidx(S(2), 'offsite stats', 'Filtered offsite'), kv=KV([['被过滤', '4 个请求(offsite/filtered)'], ['涉及域名', '1 个(offsite/domains)'], ['日志', '每个域名只记第一条']], ['被过滤'])),
    step("三种办法能让站外请求通过:meta allow_offsite = True、dont_filter = True、不设 allowed_domains,三种情形服务器都收到了 /、/off2、/on、/off1(站外的两个 localhost 请求也发出),offsite 的 stats 为空,没有任何过滤。", t=tl(S(3)), mark=lidx(S(3), 'allow_offsite', 'dont_filter', '不设'), kv=KV([['allow_offsite = True', '单个请求放行'], ['dont_filter = True', '同时绕过去重和站外过滤'], ['不设 allowed_domains', '全部放行']], ['allow_offsite = True'])),
    step("起始请求和重定向同样受限:allowed_domains = ['127.0.0.1'] 时 start() 里写站外 localhost 的请求被过滤,站内的 /to-local 虽然发出了,但它的 302 跳到 localhost 之后产生的请求也被过滤:offsite/filtered = 2、offsite/domains = 1,服务器只收到 /to-local;被过滤的请求既不调用回调也不调用 errback,静默丢弃。", t=tl(S(4)), mark=lidx(S(4), '回调/errback 被调用的次数'), done=lidx(S(4), '服务器收到'), kv=KV([['站外起始请求', '被过滤'], ['跳到站外的重定向', '被过滤'], ['回调 / errback', '都不调用(静默)']], ['回调 / errback'])),
    step("start_urls 默认走的是 dont_filter = True 的请求,所以即使指向站外的 localhost 也不会被过滤:回调被调用(via-start-urls),服务器收到该请求,offsite 的 stats 为空。需要过滤起始 URL 时得在 start() 里自己写 Request 且不加 dont_filter。", t=tl(S(5)), mark=lidx(S(5), 'start_urls 指向站外'), kv=KV([['start_urls', '默认 dont_filter = True,不过滤'], ['start() 里自己写的 Request', '不加 dont_filter 才会被过滤']], ['start_urls'])),
]
A = mkarts('s26', 26, 'Scrapy,OffsiteMiddleware,allowed_domains,allow_offsite,真实验证,动画演示',
    '实测 allowed_domains 与 OffsiteMiddleware:正则 ^(.*\\.)?(域名)$ 只比主机名,子域名自动放行,写成带端口或带协议的值一个都匹配不上且没有警告;被过滤请求静默丢弃(无回调、无 errback),stats offsite/filtered、offsite/domains,日志每个域名只记一条;allow_offsite / dont_filter 可绕过;start_urls 默认不被过滤。',
    'allowed_domains 到底怎么匹配?子域名算不算?写错格式会怎样?被过滤的请求会通知谁?这篇既直接对着中间件做匹配表,也跑了真实抓取看 stats 与日志。',
    [('0 / 11', 'allowed_domains 写成 example.org:8080 或 http://example.org 时能匹配上的 URL 数(11 个里 0 个)'), ('静默', '被站外过滤的请求不会调用回调,也不会调用 errback'), ('dont_filter', '默认 start_urls 的请求自带,所以不受站外过滤')],
    [('匹配规则', '<p>主机名必须等于 allowed_domains 的某一项,或者是它的子域名;大小写不敏感(主机名先小写),端口和协议被忽略,所以带端口或协议的写法永远匹配不上。</p>'),
     ('被过滤的请求', '<p>OffsiteMiddleware 在请求进入调度器时就抛 <code>IgnoreRequest</code>,请求不会发出,也没有回调,stats 里记 <code>offsite/filtered</code> 和 <code>offsite/domains</code>。</p>'),
     ('绕过', '<p>请求 meta 里 <code>allow_offsite = True</code> 或 <code>dont_filter = True</code> 就不受限制;不设 <code>allowed_domains</code> 则全部放行。</p>'),
     ('起始请求与重定向', '<p>手写的起始请求和重定向产生的请求同样受限;默认的 <code>start_urls</code> 请求自带 <code>dont_filter = True</code>,不受限。</p>'),
     ('start_urls', '<p>起始 URL 想受 allowed_domains 约束,就在 <code>start()</code> 里自己 yield 不带 <code>dont_filter</code> 的 <code>Request</code>。</p>')],
    steps,
    [ENV_Y + '。匹配表直接构造 OffsiteMiddleware 和 Spider 判断 11 个 URL;真实抓取用 127.0.0.1(站内)与 localhost(站外)当两个域名',
     '没有验证:IDN(中文)域名的匹配;子域名过滤时 www 前缀的特殊处理(没有特殊处理,表里只有 www.example.org 是自己写的);自定义 should_follow 子类;spider 运行期间修改 allowed_domains 的生效时机(源码里 _update_host_regex 会在下次判断时更新,没有实测);与 CrawlSpider 的 LinkExtractor allow_domains 的关系(见后面的文章)'],
    '站外过滤')
