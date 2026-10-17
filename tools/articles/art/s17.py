from lib import *
S = SS('s17')
steps = [
    step("下载槽的名字:默认是 URL 的主机名(小写,不含端口和协议):http://a.com 与 https://a.com:8443 同属槽 'a.com',www.a.com 是另一个槽 'www.a.com',http://A.COM 变成 'a.com',IPv6 的 [::1] 是 '::1';meta['download_slot'] 优先(指定 'myslot' 就是 'myslot')。设了 CONCURRENT_REQUESTS_PER_IP 后槽名换成解析后的 IP:localhost 和 127.0.0.1 这两个主机名都落到槽 '127.0.0.1'(前提是之前已经解析过,没解析过的 a.com 仍是主机名)。", t=tl(S(1)), mark=lidx(S(1), "'myslot'"), done=lidx(S(1), "'a.com'", "'www.a.com'", "'::1'"), kv=KV([['默认槽名', 'URL 主机名,小写,不含端口和协议'], ['meta["download_slot"]', '优先'], ['CONCURRENT_REQUESTS_PER_IP', '槽名变成解析后的 IP'], ['localhost 与 127.0.0.1', '各自一个槽;PER_IP 下合并']], ['默认槽名'])),
    step("用 meta['download_slot'] 合并或拆开槽(DOWNLOAD_DELAY = 0.2,无抖动):两个主机名各 20 个请求,默认两个槽,延迟各算各的,总耗时 4.0 s;把 40 个请求都指到同一个槽 shared,一个槽排队,7.9 s;同一个主机名 40 个请求按奇偶指到 even / odd 两个槽,两个槽并行,3.8 s——延迟只在同槽之间生效,拆槽等于成倍提高抓取速度(服务器是否接受要自己负责)。", t=tl(S(2)), mark=lidx(S(2), '(b)', '(c)'), done=lidx(S(2), '(a)', '理想值'), b=bars([['(a) 两个主机名,两个槽', 4.0, '4.0 s'], ['(b) 合并成一个槽', 7.9, '7.9 s'], ['(c) 一个主机拆成两个槽', 3.8, '3.8 s']], 7.9, mark=[1], done=[0, 2]), kv=KV([['(a) 两个槽', '4.0 s'], ['(b) 合并为一个槽', '7.9 s'], ['(c) 拆成两个槽', '3.8 s'], ['延迟生效范围', '同一个槽内']], ['(b) 合并为一个槽'])),
    step("DOWNLOAD_SLOTS 的键既可以是主机名也可以是自己起的槽名:{'api': {'delay': 0.05}},20 个请求都用 meta['download_slot']='api' 指过去,相邻间隔中位数 51 ms,总耗时 1.0 s;如果这条设置没生效,全局 DOWNLOAD_DELAY = 0.2 会让它花 4.0 s。每个槽可以单独设 delay(以及 concurrency、jitter)。", t=tl(S(3)), mark=lidx(S(3), 'DOWNLOAD_SLOTS'), kv=KV([['槽名', '主机名或自定义名'], ['delay 0.05', '间隔 51 ms'], ['总耗时', '1.0 s(而不是 4.0 s)']], ['槽名'])),
    step("空闲的槽会被回收:Downloader 每 60 秒检查一次(_SLOT_GC_INTERVAL),回收“没有活动请求且最后一次放行早于 60 秒前”的槽。真实等待 130 秒,每 10 秒记一次:0~50 s 有两个槽(127.0.0.1 和 localhost),60 s 的检查回收了 127.0.0.1,localhost 因为比前一个晚了几毫秒放行,没到 60 秒的门槛,一直留到 120 s 的下一轮检查才被回收,此时槽为空。回收后同一个域名再来请求会新建槽,延迟计时从头开始。", t=tl(S(4)), mark=lidx(S(4), '60 s', '120 s'), done=lidx(S(4), '   0 s', '  50 s'), kv=KV([['检查周期', '60 s'], ['回收条件', '无活动请求且最后放行 > 60 s 前'], ['127.0.0.1', '60 s 时回收'], ['localhost', '120 s 时回收(晚了几毫秒)']], ['回收条件'])),
]
A = mkarts('s17', 17, 'Scrapy,下载槽,slot,download_slot,DOWNLOAD_SLOTS,真实验证,动画演示',
    '实测下载槽:槽名默认是小写主机名(忽略端口和协议),CONCURRENT_REQUESTS_PER_IP 下变成解析后的 IP,meta["download_slot"] 优先;把两个主机名合并成一个槽总耗时从 4.0 s 变 7.9 s,把一个主机拆成两个槽从 7.9 s 变 3.8 s;DOWNLOAD_SLOTS 可按槽名设 delay;空闲的槽在 60~120 秒后被回收。',
    '每个域名一个下载槽,延迟和并发都按槽算。槽的名字是怎么取的?能不能用 meta 把几个域名合并成一个槽、或者把一个域名拆开?空闲的槽什么时候被回收?这篇一项项量出来。',
    [('7.9 → 3.8 s', '同样 40 个请求,合并成一个槽与拆成两个槽的总耗时(延迟 0.2 s)'), ('60 s', '槽的回收检查周期(首次回收在 60 s,另一个在 120 s)'), ('51 ms', 'DOWNLOAD_SLOTS 给自定义槽 api 设 delay 0.05 后的实测间隔')],
    [('槽名', '<p><code>Downloader.get_slot_key</code> 先看 <code>request.meta["download_slot"]</code>,没有就取 URL 的主机名;设了 <code>CONCURRENT_REQUESTS_PER_IP</code> 则换成解析出的 IP。</p>'),
     ('合并与拆开', '<p>延迟(和并发限制)只在同一个槽内生效。想让多个域名共享礼貌间隔,就用 meta 指到同一个槽;想把同一个域名当作几个独立的下载通道,就拆成多个槽。</p>'),
     ('DOWNLOAD_SLOTS', '<p>按槽名给 <code>delay</code>、<code>concurrency</code>、<code>jitter</code> 设置覆盖值,槽名可以是主机名,也可以是自定义的。</p>'),
     ('回收', '<p>每 60 秒检查一次,回收没有活动请求且最后一次放行超过 60 秒的槽。回收是“新建槽、重新计时”的意思,不影响正确性。</p>')],
    steps,
    [ENV_Y + '。槽名取自 Downloader.get_slot_key;合并/拆开实验用 DOWNLOAD_DELAY = 0.2、DOWNLOAD_DELAY_JITTER = 0 并读取服务器端到达时间;回收实验真实等待 130 秒',
     '没有验证:CONCURRENT_REQUESTS_PER_IP 在 2.19 里的弃用(单元测试里见过 “The CONCURRENT_REQUESTS_PER_IP setting is deprecated, use CONCURRENT_REQUESTS_PER_DOMAIN instead.”,真实抓取的日志里没有再看到);IP 槽对 DNS 多记录(多个 A 记录)的主机的行为;槽回收与 AutoThrottle 状态的关系(下一批文章);回收周期 _SLOT_GC_INTERVAL 是类属性,没有改过它'],
    '下载槽')
