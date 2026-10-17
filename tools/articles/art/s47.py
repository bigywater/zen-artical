from lib import *
S = SS('s47')
steps = [
    step("-a NAME=VALUE 把参数交给 spider 的 __init__。默认的 Spider.__init__(name=None, **kwargs) 把所有关键字参数写成实例属性(self.__dict__.update(kwargs)):-a category=books -a page=3 → self.category = 'books'(覆盖了类属性 category = 'default-cat'),self.page = '3'——类型是字符串 str,不是整数;值里含 = 的按第一个 = 拆开(url=http://x/?a=1&b=2 完整保留,eq=a=b=c 的值是 a=b=c)。", t=tl(S(1)), mark=lidx(S(1), "'page_type': 'str'", '值里带 ='), kv=KV([['-a NAME=VALUE', '默认 __init__ 写成实例属性'], ['值的类型', '总是字符串(page = "3")'], ['值里有 =', '按第一个 = 拆分'], ['同名类属性', '被覆盖']], ['值的类型'])),
    step("自己写 __init__ 要接收 **kwargs 并传给 super:__init__(self, category=None, **kwargs) + super().__init__(**kwargs) 时,-a other=1 也能作为属性(self.other = '1');漏了 **kwargs 的 __init__(self, category=None),只要多传一个没声明的 -a,就在启动时 TypeError: S.__init__() got an unexpected keyword argument 'other',退出码 1。", t=tl(S(2)), mark=lidx(S(2), '漏了 **kwargs'), done=lidx(S(2), '推荐写法'), kv=KV([['推荐', '__init__(self, x=None, **kwargs) + super().__init__(**kwargs)'], ['漏了 **kwargs', '多传参数 → TypeError,退出码 1']], ['推荐'])),
    step("几个坑:-a start_urls=http://…/only 传的是字符串,start_urls 按列表遍历,于是一个字符一个字符地当 URL——第一个字符 “h” 就让 start() 抛 ValueError “Missing scheme in request url”,日志 ERROR “Error while reading start items and requests”,退出码却是 0,服务器收到 0 个请求;JSON 风格的 -a start_urls=[\"…\"] 同样的结果;-a novalue 没有 =,argparse 直接报 “Invalid -a value, use -a NAME=VALUE”,退出码 2。", t=tl(S(3)), mark=lidx(S(3), 'start_urls=http', 'start_urls=[', 'novalue'), kv=KV([['-a start_urls=字符串', '按字符遍历 → Missing scheme,退出码仍为 0'], ['-a 没有 =', '退出码 2,Invalid -a value'], ['结论', '列表型参数要自己在 __init__ 里解析']], ['-a start_urls=字符串'])),
    step("正确传 URL 列表:-a urls=http://…/a,http://…/b(逗号分隔),在 __init__ 里 urls.split(',') 赋给 self.start_urls,服务器收到 /a 和 /b 两个请求。", t=tl(S(4)), mark=lidx(S(4), '服务器收到'), kv=KV([['-a urls=a,b', '字符串'], ['__init__ 里 split(",")', '变成列表 start_urls']], ['__init__ 里 split(",")'])),
    step("在程序里启动不受字符串限制:CrawlerProcess.crawl(S, page=3, opts={'k': [1, 2]}) 传的参数类型原样保留(page 是 int,opts 是 dict);它们是 spider 参数,和同名的设置 PAGE(值 'from-settings')是两回事——一个在 self.page,一个在 self.settings。", t=tl(S(5)), mark=lidx(S(5), 'p.crawl'), kv=KV([['CrawlerProcess.crawl(S, **kwargs)', '参数类型保留(int、dict)'], ['spider 参数 vs 设置', '互相独立:self.page 与 self.settings["PAGE"]']], ['CrawlerProcess.crawl(S, **kwargs)'])),
]
A = mkarts('s47', 47, 'Scrapy,spider参数,-a,start_urls,__init__,真实验证,动画演示',
    '实测 spider 参数:-a 的值总是字符串并写成实例属性(覆盖同名类属性);__init__ 漏了 **kwargs 会 TypeError;-a start_urls=字符串 被按字符遍历,抛 Missing scheme 却退出码为 0;-a 没有 = 退出码 2;CrawlerProcess.crawl(S, page=3) 保留类型,与设置互相独立。',
    'scrapy crawl myspider -a category=books 里的 -a 到底把值交给了谁?为什么 page=3 变成了字符串?start_urls 能不能直接传?__init__ 要怎么写?这篇逐个实测,把最容易踩的坑列出来。',
    [('"3"', '-a page=3 之后 self.page 的值(字符串,不是整数)'), ('退出码 0', '-a start_urls=字符串 时,什么都没抓却仍然正常退出'), ('**kwargs', '自己写 __init__ 时必须接收的参数')],
    [('参数怎么到 spider 里', '<p><code>-a</code> 的键值对作为关键字参数传给 spider 的构造函数,默认的 <code>Spider.__init__</code> 把它们设成实例属性,同名的类属性被覆盖。</p>'),
     ('写 __init__', '<p>自己写 <code>__init__</code> 时要接收 <code>**kwargs</code> 并传给 <code>super().__init__</code>,否则多传一个参数就 <code>TypeError</code>。</p>'),
     ('start_urls 之类的坑', '<p>命令行上的值总是字符串。<code>start_urls</code> 直接传字符串会被按字符遍历,抛 <code>Missing scheme</code> 却以退出码 0 结束;没有 <code>=</code> 的 <code>-a</code> 直接报参数错误。</p>'),
     ('列表型参数', '<p>列表要自己解析,比如逗号分隔再 <code>split</code> 成 <code>start_urls</code>。</p>'),
     ('程序里传参', '<p><code>CrawlerProcess.crawl(S, **kwargs)</code> 可以传任意类型,原样保留,与同名设置互不影响。</p>')],
    steps,
    [ENV_Y + '。命令行用 scrapy runspider spider.py -a …;spider 在 start() 里用 EV() 记录属性;程序里启动用单文件脚本里的 CrawlerProcess',
     '没有验证:scrapy crawl(项目内)与 runspider 在参数传递上的差异(行为一致,源码里同一个 spargs);custom_settings 能否通过 -a 修改(不能,它是类属性,没有实测);参数名与 Spider 已有属性(如 name、logger、settings)冲突的后果;从 scrapyd 传参(scrapyd 会把参数转成 -a)'],
    'spider 参数')
