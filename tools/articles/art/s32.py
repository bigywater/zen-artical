from lib import *
S = SS('s32')
steps = [
    step("sitemap_urls 指向 /robots.txt:先读 robots.txt 里的 “Sitemap:” 行(源码按行首 sitemap: 不分大小写识别),相对路径 /sitemap_index.xml 按 robots.txt 的地址补成绝对 URL,绝对地址 …/extra.html 照用;/sitemap_index.xml 是索引(sitemapindex),里面三个子 sitemap 逐个请求:products.xml、真正的 .xml.gz 压缩文件(自动解压)、news.xml(服务器用 Content-Encoding: gzip 即时压缩的,由压缩中间件解开);子 sitemap 里的 6 个页面最后全部被 parse 回调。/extra.html 其实是 HTML,只打一条 WARNING “Ignoring invalid sitemap”,不影响其它。", t=tl(S(1)), mark=lidx(S(1), '警告', '服务器收到'), done=lidx(S(1), 'parse 回调的页面'), kv=KV([['robots.txt', '读 Sitemap: 行,相对路径补全'], ['sitemapindex', '递归请求每个子 sitemap'], ['.xml.gz / 即时 gzip', '都能解开'], ['无效 sitemap', 'WARNING,不影响其它']], ['sitemapindex'])),
    step("sitemap_rules 是 (正则, 回调) 的列表,按顺序第一个匹配的生效:[('/p/', 'parse_product'), ('/blog/', 'parse_blog')] 时 /p/1~3 走 parse_product、/blog/a、/blog/b 走 parse_blog;/news/1 没有任何规则匹配,根本不会被请求(服务器没收到)。默认规则 [('', 'parse')] 匹配全部。", t=tl(S(2)), mark=lidx(S(2), '规则'), kv=KV([['匹配方式', '正则 search,按顺序取第一个'], ['没有规则匹配', '这个 URL 不请求'], ['默认', '[("", "parse")] 全部匹配']], ['没有规则匹配'])),
    step("sitemap_follow 过滤索引里的子 sitemap(也是正则 search):['products', 'news'] 时只请求 /sitemap_index.xml、/sm/products.xml、/sm/news.xml,blog.xml.gz 没被请求,parse 页面只有 /news/1 和 /p/1~3。默认 [''] 跟踪全部。", t=tl(S(3)), mark=lidx(S(3), 'sitemap_follow'), kv=KV([['sitemap_follow', '只对 sitemapindex 里的子 sitemap 生效'], ['未匹配的子 sitemap', '不请求']], ['sitemap_follow'])),
    step("sitemap_filter(entries) 收到的每个 entry 是字典:带 xhtml 备用链接的 products 条目有 alternate、lastmod、loc 三个键,其它条目是 lastmod、loc。重写它按 lastmod ≥ '2025-02' 过滤:p/1(2025-01)和 blog/a(2024-01)被丢掉,最后 parse 的页面是 /blog/b、/news/1、/p/2、/p/3。", t=tl(S(4)), mark=lidx(S(4), '只保留 lastmod'), done=lidx(S(4), 'entry p/1', 'entry blog/a'), kv=KV([['entry 字典', 'loc、lastmod,有备用链接时多 alternate'], ['sitemap_filter', '返回要保留的 entry'], ['本例', '只留 lastmod ≥ 2025-02']], ['entry 字典'])),
    step("sitemap_alternate_links:条目里带 <xhtml:link rel=\"alternate\" href=…> 时,默认(False)只抓 loc,parse 页面是 /p/1~3;设成 True,每个备用链接也当成页面,变成 6 个:/p/1、/p/1?lang=en、/p/2、/p/2?lang=en、/p/3、/p/3?lang=en。", t=tl(S(5)), mark=lidx(S(5), 'True:'), done=lidx(S(5), 'False(默认)'), kv=KV([['False(默认)', '只取 loc,3 个页面'], ['True', '备用链接也取,6 个页面']], ['True'])),
    step("什么响应会被当作 sitemap(源码 _get_sitemap_body):XmlResponse(Content-Type 是 xml 类)、带 gzip 魔数的、或者 URL 以 .xml / .xml.gz 结尾。/sm/products.xml(application/xml)、/sitemap.php(text/xml)、/sm/news.xml(即时 gzip)、/sm/blog.xml.gz 都正常;/sm/plain-ct 内容是合法的 sitemap,但 Content-Type 是 text/plain 且 URL 不以 .xml 结尾,于是被警告 “Ignoring invalid sitemap” 并忽略,parse 页面为空。", t=tl(S(6)), mark=lidx(S(6), '/sm/plain-ct'), done=lidx(S(6), '/sm/products.xml', '/sitemap.php', '/sm/news.xml', '/sm/blog.xml.gz'), kv=KV([['XmlResponse', '当作 sitemap'], ['gzip 魔数', '先解压再解析'], ['URL 以 .xml / .xml.gz 结尾', '当作 sitemap'], ['以上都不满足', 'Ignoring invalid sitemap']], ['以上都不满足'])),
]
A = mkarts('s32', 32, 'Scrapy,SitemapSpider,sitemap,robots.txt,sitemap_rules,真实验证,动画演示',
    '实测 SitemapSpider:从 robots.txt 的 Sitemap: 行出发递归索引、解开 .xml.gz 与即时 gzip;sitemap_rules 取第一个匹配并丢弃不匹配的 URL;sitemap_follow 过滤子 sitemap;sitemap_filter 按 lastmod 过滤;sitemap_alternate_links 把 3 个页面变 6 个;Content-Type 是 text/plain 的合法 sitemap 会被当作无效而忽略。',
    'SitemapSpider 怎么从 robots.txt 找到 sitemap、怎么处理索引和压缩、怎么用正则分流到不同回调?哪些响应会被认定为 sitemap?这篇在一个带索引、gz、备用链接的假站点上逐项验证。',
    [('6 个', '从 robots.txt 出发经索引递归后抓到的页面数(3 个子 sitemap)'), ('3 → 6', 'sitemap_alternate_links 从 False 变 True 时的页面数'), ('text/plain', '内容合法但会被忽略的 sitemap 的 Content-Type(URL 也不以 .xml 结尾)')],
    [('发现 sitemap', '<p><code>sitemap_urls</code> 可以直接是 sitemap,也可以是 robots.txt:后者读取其中的 <code>Sitemap:</code> 行。sitemapindex 里的子 sitemap 会递归请求,.xml.gz 和即时压缩的响应都能解开。</p>'),
     ('回调分流', '<p><code>sitemap_rules</code> 按顺序取第一个匹配的正则,没匹配的 URL 不请求。</p>'),
     ('sitemap_follow', '<p><code>sitemap_follow</code> 决定索引里哪些子 sitemap 要跟,默认全部。</p>'),
     ('sitemap_filter', '<p>重写 <code>sitemap_filter</code> 可以按 <code>lastmod</code> 等字段筛选条目。</p>'),
     ('备用链接', '<p><code>sitemap_alternate_links = True</code> 会把 <code>xhtml:link</code> 的备用地址也当作页面。</p>'),
     ('识别规则', '<p>响应必须是 XmlResponse、gzip 或 URL 以 <code>.xml</code>/<code>.xml.gz</code> 结尾,否则被当作无效 sitemap 忽略。服务器发 <code>text/plain</code> 的 sitemap 要特别留意。</p>')],
    steps,
    [ENV_Y + '。站点:robots.txt 里一个相对路径和一个绝对路径的 Sitemap: 行;sitemapindex 指向 products.xml、blog.xml.gz(真 gzip 文件)、news.xml(Content-Encoding: gzip);并发 1,先进先出队列',
     '没有验证:超大 sitemap(超过 50,000 条或 50 MB)的内存占用;DOWNLOAD_MAXSIZE 对 sitemap 解压的限制(源码里有,未实测);sitemap 里 <image:image>、<video:video> 扩展标签;lastmod 的各种日期格式;同一个 URL 出现在多个 sitemap 里的去重(靠调度器的去重,未单独测);sitemap 与 CrawlSpider 的混用'],
    'sitemap')
