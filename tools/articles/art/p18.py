from lib import *
S = SS('p18')
steps = [
    step("先看默认值:aiohttp.TCPConnector() 的 limit=100(同时打开的连接总数上限),limit_per_host=0(0 表示每个主机不限)。也就是说默认情况下对单个目标站最多会同时开 100 条连接。", t=tl(S(1)), done=lidx(S(1), 'limit=100'), kv=KV([['limit', '100(全部主机合计)'], ['limit_per_host', '0(不限)'], ['含义', '对一个站点默认最多 100 条并发连接']], ['含义'])),
    step("同一个主机 200 个请求(每个 0.1 秒):默认设置服务器同时处理的峰值 100,累计连接 100 条,245 ms;limit=0(不限)峰值 200,200 条连接,158 ms;limit=20 峰值 20,1091 ms;limit_per_host=5 峰值 5,4231 ms。对单个主机而言,limit 和 limit_per_host 效果相同;耗时都接近“请求数 / 上限 × 0.1 秒”。", t=tl(S(2)), done=lidx(S(2), 'limit=20', 'limit_per_host=5'), mark=lidx(S(2), '默认(limit=100', 'limit=0(不限)'), b=bars([['默认 limit=100:服务器峰值', 100, '100'], ['limit=0:峰值', 200, '200'], ['limit=20:峰值', 20, '20'], ['limit_per_host=5:峰值', 5, '5']], 200, mark=[1], done=[2, 3]), kv=KV([['默认', '峰值 100'], ['limit=0', '峰值 200,没有任何限制'], ['limit_per_host=5', '峰值 5,4231 ms']], ['limit=0'])),
    step("三个不同主机(三个本机端口)各 100 个请求:limit=30 是总数上限,三台服务器合起来同时处理的峰值恰好 30,但各自不均匀([14, 24, 14]);limit=0 加 limit_per_host=5,每台服务器峰值 5,合起来 15;limit=30 加 limit_per_host=5,每台仍是 5、合起来 15,limit 30 没起作用。两个参数同时设时,哪个更紧哪个起作用。", t=tl(S(3)), done=lidx(S(3), 'limit=0,limit_per_host=5', 'limit=30,limit_per_host=5'), mark=lidx(S(3), 'limit=30:'), b=bars([['limit=30:合起来的峰值', 30, '30'], ['limit_per_host=5:合起来的峰值', 15, '15']], 30, mark=[0], done=[1]), kv=KV([['limit=30', '合起来 30,各台不均匀'], ['limit_per_host=5', '每台 5,合起来 15'], ['两个都设', '更紧的那个生效']], ['两个都设'])),
    step("limit_per_host 的“主机”是按请求里的主机名(加端口)区分的,不是按真实服务器:用同一个主机名 127.0.0.1 访问,limit_per_host=5,服务器峰值 5,4270 ms;用 a.test、b.test、c.test、d.test 四个不同主机名(都解析到同一台服务器)访问,同样 limit_per_host=5,服务器峰值 20,1523 ms。虚拟主机、多个域名指向同一台服务器时,对方实际看到的并发是各域名的上限之和。", t=tl(S(4)), done=lidx(S(4), '同一个主机名(127.0.0.1)'), mark=lidx(S(4), '4 个不同主机名'), b=bars([['同一个主机名:服务器峰值', 5, '5'], ['4 个主机名:服务器峰值', 20, '20']], 20, done=[0], mark=[1]), kv=KV([['同一个主机名', '峰值 5'], ['4 个主机名指向同一台', '峰值 20'], ['键', '主机名 + 端口']], ['4 个主机名指向同一台'])),
    step("limit 是每个 TCPConnector(也就是每个 ClientSession)自己的上限,多个会话的上限会叠加:1 个 ClientSession、limit=10、100 个请求:服务器峰值 10;3 个 ClientSession 各 limit=10、各 100 个请求:峰值 30,总耗时 1102 ms;同样 300 个请求共用 1 个 ClientSession(limit=10):峰值 10,总耗时 3216 ms。为每个任务或每个 worker 各建一个 ClientSession,限制就失效了。", t=tl(S(5)), done=lidx(S(5), '共用 1 个 ClientSession'), mark=lidx(S(5), '3 个 ClientSession'), b=bars([['1 个会话 limit=10:峰值', 10, '10'], ['3 个会话各 limit=10:峰值', 30, '30'], ['共用 1 个会话:峰值', 10, '10']], 30, mark=[1], done=[0, 2]), kv=KV([['3 个会话各 limit=10', '峰值 30'], ['共用 1 个会话', '峰值 10,耗时 3216 ms'], ['结论', '会话要共用,不要每次新建']], ['结论'])),
]
A = mkartp('p18', 18, '爬虫,aiohttp,TCPConnector,limit,limit_per_host,并发控制,ClientSession,Python,真实验证,动画演示',
    '实测 aiohttp 的 TCPConnector:默认 limit=100、limit_per_host=0,对单个站点最多同时开 100 条连接;limit 是总数上限、limit_per_host 是每个主机的上限,两个都设时更紧的生效;“主机”按主机名区分(4 个域名指向同一台服务器时对方看到 20 个并发);多个 ClientSession 的 limit 会叠加(3 个会话峰值 30)。',
    'aiohttp 把并发限制放在 TCPConnector 里,但 limit 和 limit_per_host 到底各管什么、两个同时设怎么办、几个会话一起跑又怎样,文档里一两句话很难说清。这篇在本机用多台服务器和多个主机名把它们逐一量出来。',
    [('100', 'aiohttp 默认对单个站点允许同时开的连接数上限(limit=100,limit_per_host=0)'), ('20 对 5', 'limit_per_host=5 时,用 4 个不同主机名访问同一台服务器,服务器实际看到的并发峰值(同一主机名是 5)'), ('30', '3 个 ClientSession 各 limit=10 同时运行时的服务器并发峰值')],
    [('默认值', '<p>默认 <code>limit=100</code>、<code>limit_per_host=0</code>。直接用默认值的爬虫,对目标站点最高会同时开 100 条连接;这个数字对某个站点是否合适,取决于那个站点,本文没有拿任何真实站点测它的承受能力。</p>'),
     ('单个主机', '<p>只有一个目标主机时,<code>limit</code> 和 <code>limit_per_host</code> 效果一样:服务器看到的并发峰值就是设定值,总耗时接近 <code>请求数 / 上限 × 单次耗时</code>。<code>limit=0</code> 表示不限制,200 个请求会同时发出。</p>'),
     ('多个主机', '<p><code>limit</code> 限制所有主机合计的连接数,各主机之间分配不均(实测 [14, 24, 14]);<code>limit_per_host</code> 限制每个主机。两个同时设置时,更紧的那个起作用。</p>'),
     ('主机的定义', '<p><code>limit_per_host</code> 按请求里的主机名和端口分组,不关心它们是不是同一台服务器。用 4 个域名访问同一台服务器,服务器实际看到的并发是 4 × 5 = 20。</p>'),
     ('连接器是会话级的', '<p>上限属于 <code>TCPConnector</code>,每个 <code>ClientSession</code> 默认有自己的连接器,所以几个会话同时跑,总并发是它们的上限之和。想要全局的上限,会话要共用,或者在外面再套一层 <code>Semaphore</code>。</p>')],
    steps,
    [ENV_P + '。aiohttp 3.14.3;服务器每个请求停 0.1 秒;同时处理的请求峰值由服务器统计,三台服务器的合计峰值用一个带锁的全局计数器统计(各自峰值相加是不对的,因为峰值出现的时刻不同);用 a.test 等主机名时把 getaddrinfo 替换为都解析到 127.0.0.1;每项各测一次,毫秒数仅供参考',
     '没有验证:limit 满了之后排队的先后顺序;排队等待连接是否受 ClientTimeout 的哪一项约束(第 18 篇测到总超时会算上排队时间);keepalive 连接闲置时是否占用 limit 的名额;HTTP/2 下 aiohttp(不支持)与 curl_cffi 的连接数控制;connector 的 limit 在 HTTPS 与代理下的计数方式'],
    'TCPConnector 的 limit')
