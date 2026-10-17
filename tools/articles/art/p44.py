from lib import *
S = SS('p44')
steps = [
    step("站点:60 个商品各有 5 种地址(/product/i、/product/i/、/product/i?ref=mail、/p/i、/product/i?sort=asc),10 个分页列表页 /list?page=n(内容各不相同,但都声明 canonical 是 /list),共 310 个 URL,真实不同的内容 70 个。canonical 的声明方式:HTML 里的 <link rel=\"canonical\"> 250 个、只有 Link 响应头的 60 个(/product/i?sort=asc)。/product/i?ref=mail 里写的是相对路径 \"/product/i\",要用页面 URL 解析成绝对地址(解析后是 <站点>/product/3)。", t=tl(S(1)), done=lidx(S(1), '每种地址怎么声明 canonical', '相对路径的 canonical'), b=bars([['URL 总数', 310, '310'], ['真实不同的内容', 70, '70'], ['HTML 声明 canonical', 250, '250'], ['只有 Link 头声明', 60, '60']], 310, done=[1]), kv=KV([['310 个 URL', '70 种真实内容'], ['HTML canonical', '250 个'], ['Link 响应头 canonical', '60 个']], ['Link 响应头 canonical'])),
    step("几种合并方式(理想:70 组、0 错并、0 个真实页面被拆成多组):不合并 310 组,60 个商品被拆分;只做 URL 规范化(去斜杠、ref、sort)130 组,60 被拆分(/p/i 这种别名合并不了,10 个列表页也各自一组);信任 canonical 61 组,错并 1 组(把 10 个不同的列表页都合成了一个),拆分 0;canonical 加内容校验(canonical 目标内容一致才信任)70 组、0 错并、0 拆分;只看正文哈希(去掉页脚时间戳)70 组,同样完美;整页字节哈希 310 组——页脚里的时间戳每次都不同,什么都合并不了。", t=tl(S(2)), done=lidx(S(2), 'canonical + 内容校验', '只看正文哈希'), mark=lidx(S(2), '信任 canonical(没有则规范化 URL)', '整页字节哈希', '只做 URL 规范化'), b=bars([['不合并:组数', 310, '310'], ['只规范化 URL', 130, '130'], ['信任 canonical', 61, '61'], ['canonical + 校验', 70, '70'], ['整页字节哈希', 310, '310']], 310, mark=[2, 4], done=[3]), kv=KV([['信任 canonical', '61 组,错并 1 组'], ['canonical + 内容校验', '70 组,0 错并'], ['整页字节哈希', '310 组,合并不了']], ['canonical + 内容校验'])),
    step("canonical 指错了:10 个分页列表页内容各不相同(items 100–199、200–299 …),都声明 canonical 是 /list。信任 canonical 之后这 10 页合成 1 组,被丢掉的页面 9 个。加上内容校验(canonical 目标 /list 的内容与自己不一致就不信任):9 / 10 个页面保留了自己的身份——剩下那个是第 1 页,它的内容和 /list 本来就一样。", t=tl(S(3)), done=lidx(S(3), '加了内容校验'), mark=lidx(S(3), '信任 canonical 之后'), b=bars([['信任 canonical:被丢掉的页面', 9, '9'], ['加内容校验:保留自己身份', 9, '9']], 10, mark=[0], done=[1]), kv=KV([['信任 canonical', '10 页合成 1 组,丢 9 页'], ['内容校验', '9 / 10 保留'], ['原因', '分页页面常被错写成指向第 1 页']], ['原因'])),
    step("canonical 链、环与失效的目标:a → b → c(c 指向自己)可以一路追到终点 /chain/c;a → b → a 的环会回到已访问过的页面,要有访问记录来打断;canonical 指向 404:/bad → /gone → HTTP 404,指向了一个不存在的页面。追 canonical 时要限制跳数、记录已访问、遇到非 200 就放弃。", t=tl(S(4)), done=lidx(S(4), 'canonical 链'), mark=lidx(S(4), 'canonical 环', 'canonical 指向 404'), kv=KV([['链', '追到终点自指'], ['环', '要靠访问记录打断'], ['指向 404', '遇到非 200 就放弃']], ['环'])),
    step("同一个页面里多处声明互相冲突:两个 <link rel=\"canonical\">(/html-says、/html-second)、一个 Link 响应头(/header-says)、一个 og:url(/og-says)——3 个来源给出 4 个地址。取哪个由爬虫自己的策略决定;上面的“信任 canonical”取的是 HTML 里第一个、没有才取 Link 头。搜索引擎怎么处理这种冲突,我没有验证。", t=tl(S(5)), done=lidx(S(5), 'HTML 里的', 'Link 响应头里', 'og:url'), mark=lidx(S(5), '三处给出'), kv=KV([['HTML 里的 canonical', '2 个不同'], ['Link 头', '1 个'], ['og:url', '1 个']], ['HTML 里的 canonical'])),
]
A = mkartp('p44', 44, '爬虫,canonical,去重,重复URL,内容哈希,rel=canonical,Link头,Python,真实验证,动画演示',
    '60 个商品各有 5 种地址加 10 个分页列表页(共 310 个 URL,70 种内容):只规范化 URL 剩 130 组;信任 canonical 61 组但把 10 个不同的分页合成一组;canonical 加内容校验和只看正文哈希都得到正好 70 组;整页字节哈希因为页脚时间戳合并不了(310 组)。',
    '同一个内容有多个地址时,canonical 链接是站点主动告诉你“哪个是正主”。可是站点会写错,还可能有链、环、冲突。这篇在一个故意写错 canonical 的本机站点上,对比只规范化 URL、信任 canonical、canonical 加内容校验和内容哈希。',
    [('9 个', '10 个内容不同的分页列表页都声明 canonical 是 /list,信任它时被丢掉的页面数'), ('70 / 70', 'canonical 加内容校验和正文哈希两种方式得到的页面组数(真实内容数 70)'), ('310', '整页字节哈希得到的组数——页脚时间戳让每个响应都不同')],
    [('站点与声明方式', '<p>商品页有 5 种地址,canonical 的声明方式不一:HTML 里的绝对地址、相对地址(要用页面 URL 解析)、只有 <code>Link</code> 响应头。分页列表页的 canonical 全写成了 <code>/list</code>。</p>'),
     ('合并方式对比', '<p>只做 URL 规范化合并不了 <code>/p/i</code> 这种别名(130 组);信任 canonical 能合并别名,但会把内容不同的分页合成一个(61 组,错并 1);先检查 canonical 目标的内容是否与自己一致再信任,得到 70 组;只看正文哈希(去掉页脚时间戳)也是 70 组。整页字节哈希因为页脚里每次变化的时间戳完全失效。</p>'),
     ('canonical 写错', '<p>分页页面把 canonical 指向第 1 页是常见写法。直接信任会丢掉第 2 到第 10 页(9 页)。内容校验的代价是每个 canonical 目标要多抓一次(这里用了缓存)。</p>'),
     ('链、环、失效', '<p>追 canonical 要限制跳数并记录已访问的地址:链最终自指,环会回到起点,指向 404 的目标要放弃。</p>'),
     ('多处声明冲突', '<p>HTML 里可以有多个 <code>rel="canonical"</code>,还有 <code>Link</code> 响应头和 <code>og:url</code>,它们可以互相矛盾。爬虫需要明确的优先级策略并记录来源。</p>')],
    steps,
    [ENV_P + '。站点由本机服务器生成;商品页内容含页脚时间戳(time.time_ns),用来模拟动态内容;canonical 从 HTML <link rel=canonical>、Link 响应头提取并用页面 URL 解析为绝对地址;“错并”=一个组里含多种真实内容,“被拆分”=一种真实内容被分在多个组;正文哈希只对 h1 和 p 文本做 sha1',
     '没有验证:搜索引擎对 canonical 的实际处理(它们把 canonical 当作提示而不是命令,这里没有核对);hreflang、amp 等其它 rel 关系;canonical 与 301 重定向同时存在时的优先级;跨域 canonical;JavaScript 注入的 canonical;内容哈希在轻微差异(近似去重,见 SimHash 一篇)下的失效'],
    'canonical 与重复 URL')
