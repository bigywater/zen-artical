from lib import *
S = SS('p32')
steps = [
    step("urllib3 的 Retry 默认只对幂等方法重试:DEFAULT_ALLOWED_METHODS 是 DELETE、GET、HEAD、OPTIONS、PUT、TRACE。Retry(total=3, status_forcelist=[503]) 对 GET、HEAD、PUT、DELETE、OPTIONS、TRACE 遇到 503 都会重试(True),对 POST 和 PATCH 不会(False)。把 allowed_methods 设成 None,POST 也会被重试。", t=tl(S(1)), done=lidx(S(1), '对 GET', '对 PUT', 'allowed_methods=None'), mark=lidx(S(1), '对 POST', '对 PATCH'), kv=KV([['GET / HEAD / PUT / DELETE / OPTIONS / TRACE', '默认会重试'], ['POST / PATCH', '默认不重试'], ['allowed_methods=None', '所有方法都重试']], ['POST / PATCH'])),
    step("下单服务器在“创建订单之后、回应之前”丢了连接(订单已创建,客户端没收到回应)。默认 Retry(total=3):POST 不重试,客户端得到 ConnectionError,服务器收到 1 次、1 个订单。allowed_methods=None:POST 被重试,客户端得到 200(订单号 2),服务器收到 2 次 POST、创建了 2 个订单——重复下单。同样 allowed_methods=None 但请求带 Idempotency-Key,服务器按这个 key 去重:客户端 200(订单号 1),服务器收到 2 次 POST、只创建 1 个订单。", t=tl(S(2)), done=lidx(S(2), '请求带 Idempotency-Key'), mark=lidx(S(2), 'allowed_methods=None)(对所有方法重试)'), b=bars([['默认:创建的订单', 1, '1'], ['allowed_methods=None:创建的订单', 2, '2'], ['加 Idempotency-Key:创建的订单', 1, '1']], 2, mark=[1], done=[2]), kv=KV([['默认 Retry', 'POST 不重试,客户端报错'], ['allowed_methods=None', '重复下单(2 个订单)'], ['带 Idempotency-Key', '重试但只有 1 个订单(服务器必须支持)']], ['allowed_methods=None'])),
    step("服务器先创建订单、再回 503(客户端看到的是失败)。POST 默认不重试:客户端拿到 503,服务器 1 个订单;allowed_methods=None 加 status_forcelist=[503]:重试成功,客户端 200(订单号 2),服务器收到 2 次、创建了 2 个订单;加 Idempotency-Key:服务器收到 2 次、只有 1 个订单。5xx 不代表“服务器什么都没做”。", t=tl(S(3)), done=lidx(S(3), '同上 + Idempotency-Key'), mark=lidx(S(3), 'allowed_methods=None, status_forcelist'), kv=KV([['503 之前订单已创建', '5xx 不等于没执行'], ['重试 POST', '2 个订单'], ['Idempotency-Key', '1 个订单']], ['503 之前订单已创建'])),
    step("幂等方法的重试没有副作用:PUT 到固定资源,第一次被连接重置,默认 Retry 自动重试,结果 200,服务器收到 2 次,资源值还是 v=1;GET 同样收到 2 次、成功。PUT 的“多做一次结果不变”正是它在 allowed_methods 里的原因。", t=tl(S(4)), done=lidx(S(4), 'PUT 被重置', 'GET 被重置'), kv=KV([['PUT 重试', '服务器收到 2 次,资源值不变'], ['GET 重试', '成功'], ['原因', '多做一次结果不变(幂等)']], ['原因'])),
    step("Retry 的分项上限:GET 被连接重置一次(读取阶段出错)。Retry(total=3):重试,结果 200,服务器收到 2 次;Retry(total=3, read=0):读取阶段不重试,结果 ConnectionError,服务器收到 1 次;Retry(total=3, read=1):重试一次,200,收到 2 次;Retry(total=0):不重试,ConnectionError,收到 1 次。total 是总数,read、connect、status 是各类的上限,取更严的。", t=tl(S(5)), done=lidx(S(5), 'Retry(total=3):', 'read=1'), mark=lidx(S(5), 'read=0', 'total=0'), kv=KV([['total=3', '读取阶段出错会重试'], ['read=0', '读取阶段不重试'], ['total 与分项', '取更严的']], ['read=0'])),
]
A = mkartp('p32', 32, '爬虫,重试,幂等,POST,Idempotency-Key,urllib3,Retry,requests,Python,真实验证,动画演示',
    '实测 POST 重试:urllib3 的 Retry 默认只重试 DELETE/GET/HEAD/OPTIONS/PUT/TRACE;对 POST 打开重试后,创建订单后丢回应的场景重复下了 2 个订单;带 Idempotency-Key 且服务器去重时只有 1 个;服务器先创建订单再回 503 同样重复。',
    '重试 GET 几乎无害,重试 POST 却可能重复下单。这篇用一个会“创建订单后丢掉回应”的本机服务器,把 urllib3 的 Retry 对不同方法的默认行为、POST 重试的后果、以及 Idempotency-Key 的作用都量一遍。',
    [('2 个订单', '对 POST 打开重试后,“创建订单后丢掉回应”的场景最终创建的订单数(默认不重试是 1,带 Idempotency-Key 是 1)'), ('6 个', 'Retry 默认允许重试的方法数:DELETE、GET、HEAD、OPTIONS、PUT、TRACE'), ('503 之前', '服务器可能已经把订单创建好了——5xx 不代表什么都没做')],
    [('哪些方法会被重试', '<p><code>Retry.DEFAULT_ALLOWED_METHODS</code> 只有 DELETE、GET、HEAD、OPTIONS、PUT、TRACE(按 HTTP 语义是幂等的)。POST 和 PATCH 默认不会因为状态码或错误被重试。</p>'),
     ('重试 POST 的后果', '<p>如果你把 <code>allowed_methods=None</code> 打开,在“订单已创建、回应丢了”时,重试会再创建一个订单(2 个)。让重复安全需要服务器配合:请求里带 <code>Idempotency-Key</code>,服务器按它去重(这里我写的服务器做了),重试时只剩 1 个订单。客户端单方面加头没有用。</p>'),
     ('5xx 不等于没做', '<p>先创建订单再回 503,客户端看到的是失败,但副作用已经发生。重试 POST 时必须假设“上一次可能已经生效”。</p>'),
     ('幂等方法', '<p>PUT 到固定资源,重试后资源值不变;GET 无副作用。这两类自动重试是安全的(前提是服务器真的按语义实现)。</p>'),
     ('分项上限', '<p><code>Retry</code> 除了 <code>total</code>,还有 <code>connect</code>、<code>read</code>、<code>status</code> 等分项;读取阶段出错的 GET,<code>read=0</code> 时不重试,默认会重试。</p>')],
    steps,
    [ENV_P + '。“下单”服务器:POST /order 创建一个订单(记录在内存列表里),按 Idempotency-Key 去重(如果请求带了);可配置在创建订单后丢掉回应(SO_LINGER=0 重置连接)或先回 503;客户端 requests 2.34.2 的 Session 挂 HTTPAdapter(max_retries=Retry(…)),urllib3 2.7.0;订单数以服务器列表长度为准',
     '没有验证:真实支付/下单 API 的 Idempotency-Key 语义和有效期;GET 请求带副作用的网站(爬虫遇到的“删除”链接用 GET 就会被重试);redirect 307/308 对 POST 的重放(第 6 篇测了方法与请求体);aiohttp 或 httpx 里没有内置重试时自己写重试循环的类似问题;事务性补偿的做法'],
    'POST 重试')
